"""
This module provides an EmailMonitor class and related functions to monitor a Gmail inbox for new unread emails,
process them using an external "brain" service, and take actions such as replying, forwarding, saving drafts, or ignoring emails
based on the response from the brain service.
Classes:
    EmailMonitor: Monitors a Gmail inbox for new unread emails, processes them, and takes actions (reply, forward, draft, ignore)
                  as determined by the brain service. Handles authentication, polling, and communication with the brain service.
Functions:
    get_config(): Loads configuration from a JSON file.
    start_email_monitoring(): Starts the global email monitoring service asynchronously.
    stop_email_monitoring(): Stops the global email monitoring service.
    get_monitor_status(): Returns the current status of the email monitor, including running state, last check time, seen emails count, and poll interval.
Dependencies:
    - shared.prompt_loader
    - shared.models.proxy
    - shared.models.googleapi
    - app.services.gmail.auth
    - app.services.gmail.search
    - app.services.gmail.send
    - shared.log_config
    - httpx
    - asyncio
    - json
    - os
Usage:
    Instantiate and start the EmailMonitor to begin monitoring a Gmail inbox for new unread emails and process them
    according to the logic defined in the brain service.
"""

from shared.prompt_loader import load_prompt
from shared.models.proxy import MultiTurnRequest
from shared.models.googleapi import ForwardEmailRequest, SaveDraftRequest

from app.services.gmail.auth import get_gmail_service
from app.services.gmail.search import get_unread_emails, get_email_by_id
from app.services.gmail.send import forward_email, save_draft
from app.services.gmail.email_cleaner import clean_email_for_brain, format_email_for_brain_prompt, get_email_summary_stats

from app.services.gmail.util import get_config

from shared.log_config import get_logger
logger = get_logger(f"googleapi.{__name__}")

import asyncio
import json
from typing import Dict, Any, Set
import httpx
import os


class EmailMonitor:
    """
    Monitor Gmail inbox for new emails and forward them to the brain service.
    """
    
    def __init__(self, brain_url: str = None, poll_interval: int = None):
        config = get_config()
        monitor_config = config.get('gmail', {}).get('monitor', {})
        gmail_config = config.get('gmail', {})
        
        brain_port = os.getenv("BRAIN_PORT", 4207)

        self.brain_url = brain_url or monitor_config.get('brain_url', f'http://brain:{brain_port}/api/multiturn')
        self.poll_interval = poll_interval or monitor_config.get('poll_interval', 30)
        self.ai_email = gmail_config.get('ai_email', 'nemokirishima@gmail.com')
        self.service = None
        self.last_check_time = None
        self.seen_email_ids: Set[str] = set()
        self.running = False


    async def start(self):
        """Start the email monitoring loop."""
        logger.info(f"Starting email monitor - filtering emails from AI address: {self.ai_email}")
        self.running = True
        self.service = get_gmail_service()
        
        # Initialize with current unread emails to avoid duplicate processing
        await self._initialize_seen_emails()
        
        while self.running:
            try:
                await self._check_for_new_emails()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in email monitoring loop: {e}")
                await asyncio.sleep(self.poll_interval)


    def stop(self):
        """Stop the email monitoring loop."""
        logger.info("Stopping email monitor")
        self.running = False


    async def _initialize_seen_emails(self):
        """Initialize the set of seen emails to avoid processing existing unread emails."""
        try:
            response = get_unread_emails(self.service, max_results=100)
            if response.success and response.data and 'emails' in response.data:
                self.seen_email_ids = {email['id'] for email in response.data['emails']}
                logger.info(f"Initialized with {len(self.seen_email_ids)} existing unread emails")
            else:
                self.seen_email_ids = set()
                logger.warning("No unread emails found during initialization.")
        except Exception as e:
            logger.error(f"Error initializing seen emails: {e}")


    async def _check_for_new_emails(self):
        """Check for new unread emails and process them."""
        try:
            response = get_unread_emails(self.service, max_results=50)
            if response.success and response.data and 'emails' in response.data:
                current_unread = response.data['emails']
                new_emails = [email for email in current_unread if email['id'] not in self.seen_email_ids]
                if new_emails:
                    logger.info(f"Found {len(new_emails)} new emails")
                    for email_summary in new_emails:
                        await self._process_new_email(email_summary['id'])
                        self.seen_email_ids.add(email_summary['id'])
            else:
                logger.warning("No unread emails found during check.")
        except Exception as e:
            logger.error(f"Error checking for new emails: {e}")


    async def _process_new_email(self, email_id: str):
        """Process a new email and forward it to the brain service."""
        try:
            # Get full email details
            response = get_email_by_id(self.service, email_id)
            if not response.success or not response.data or 'email' not in response.data:
                logger.error(f"Could not retrieve email {email_id}")
                return
            email_dict = response.data['email']
            
            # Check if email is from the AI itself - skip processing to avoid infinite loops
            from_header = email_dict.get('from', '')
            sender_email = self._extract_sender_email(from_header)
            if sender_email.lower() == self.ai_email.lower():
                logger.info(f"Skipping email {email_id} from AI itself ({sender_email}) to prevent infinite loop")
                return
                
            # Create MultiTurnRequest for the brain
            multiturn_request = self._create_multiturn_request(email_dict)
            # Forward to brain service and get the response string which is json
            brain_response = await self._send_to_brain(multiturn_request)

            if not brain_response:
                raise ValueError(f"Brain service did not return a valid response for email {email_id}: {brain_response}")

        except Exception as e:
            logger.error(f"Error processing email {email_id}: {e}")

        try:
            response_data = json.loads(brain_response)
            logger.info(f"Processed response for email {email_id}: {response_data}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode brain service response for email {email_id}: {e}")

        thread_id = email_dict['threadId']

        # get the action from the response
        if response_data and 'action' in response_data:
            action = response_data['action']
            logger.info(f"Action for email {email_id}: {action}")

        if action == 'reply':
            # Handle reply action - save as draft for review instead of auto-sending
            reply_content = response_data.get('content', '')
            bcc = response_data.get('bcc', [])
            cc = response_data.get('cc', [])
            
            # Extract reply-to email (prefer Reply-To header over From header)
            reply_to_header = email_dict.get('reply_to', '')
            from_header = email_dict.get('from', '')
            
            if reply_to_header:
                reply_email = self._extract_sender_email(reply_to_header)
            else:
                reply_email = self._extract_sender_email(from_header)
            
            # Create draft instead of direct reply
            draft_subject = f"Re: {email_dict.get('subject', 'No Subject')}"
            draft_request = SaveDraftRequest(
                to=reply_email,
                subject=draft_subject,
                body=reply_content,
                cc=', '.join(cc) if cc else None,
                bcc=', '.join(bcc) if bcc else None
            )
            
            # Save as draft for manual review
            draft_response = save_draft(self.service, draft_request)
            if not draft_response.success:
                logger.error(f"Failed to save reply draft for email {email_id}: {draft_response.message}")
                return
            logger.info(f"Reply saved as draft for email {email_id} - Subject: {draft_subject}, To: {reply_email}, Draft ID: {draft_response.data.get('draft_id')} (BCC: {bcc}, CC: {cc})")
        elif action == 'forward':
            # Handle forward action
            forward_content = response_data.get('content', '')
            to = response_data.get('to', [])
            forward_request = ForwardEmailRequest(
                thread_id=thread_id,
                body=forward_content,
                to=to
            )
            # Use the forward_email function to send the forward
            forward_response = forward_email(self.service, forward_request)
            if not forward_response.success:
                logger.error(f"Failed to forward email {email_id}: {forward_response.message}")
                return
            logger.info(f"Email {email_id} forwarded successfully to: {to} with content: {forward_content}")
        elif action == 'draft':
            # Handle draft action - save as draft for review
            draft_content = response_data.get('content', '')
            draft_to = response_data.get('to', '')
            draft_subject = response_data.get('subject', f"Re: {email_dict.get('subject', 'No Subject')}")
            draft_cc = response_data.get('cc', '')
            draft_bcc = response_data.get('bcc', '')
            
            draft_request = SaveDraftRequest(
                to=draft_to,
                subject=draft_subject,
                body=draft_content,
                cc=draft_cc if draft_cc else None,
                bcc=draft_bcc if draft_bcc else None
            )
            # Use the save_draft function to save the draft
            draft_response = save_draft(self.service, draft_request)
            if not draft_response.success:
                logger.error(f"Failed to save draft for email {email_id}: {draft_response.message}")
                return
            logger.info(f"Draft saved for email {email_id} - Subject: {draft_subject}, To: {draft_to}, Draft ID: {draft_response.data.get('draft_id')}")
        elif action == 'ignore':
            # Handle ignore action
            logger.info(f"Ignoring email {email_id}")


    def _create_multiturn_request(self, email_data: Dict[str, Any]) -> MultiTurnRequest:
        """
        Create a MultiTurnRequest object for the brain service from email data.
        
        Args:
            email_data: Full email data from Gmail API
        
        Returns:
            MultiTurnRequest dictionary
        """
        # Clean and process the email content for better LLM processing
        # Pass the Gmail service for thread context retrieval
        cleaned_email = clean_email_for_brain(email_data, gmail_service=self.service)
        
        # Log summary statistics for monitoring
        stats = get_email_summary_stats(cleaned_email)
        logger.info(f"Processing email {cleaned_email.get('id', 'unknown')}: "
                   f"{stats['word_count']} words, is_reply={stats['is_reply']}, "
                   f"has_html={stats['has_html']}, has_thread_context={cleaned_email.get('has_thread_context', False)}")
        
        # Format the cleaned email content for the brain prompt
        formatted_email_content = format_email_for_brain_prompt(cleaned_email)
        
        # Load the monitor prompt template
        prompt = load_prompt("googleapi", "gmail", "monitor")

        request = MultiTurnRequest(
            model='email',
            messages=[
                {
                    'role': 'user',
                    'content': prompt + formatted_email_content
                }
            ],
            platform='gmail',
            user_id='c63989a3-756c-4bdf-b0c2-13d01e129e02'
        )

        return request


    def _extract_sender_name(self, from_header: str) -> str:
        """Extract sender name from From header."""
        if '<' in from_header:
            return from_header.split('<')[0].strip().strip('"')
        return from_header.strip()


    def _extract_sender_email(self, from_header: str) -> str:
        """Extract sender email from From header."""
        if '<' in from_header and '>' in from_header:
            return from_header.split('<')[1].split('>')[0].strip()
        return from_header.strip()


    async def _send_to_brain(self, multiturn_request: MultiTurnRequest) -> str:
        """
        Send MultiTurnRequest to the brain service.
        
        Args:
            multiturn_request: The request to send to brain

        Returns:
            str: Response from the brain service
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.brain_url,
                    json=multiturn_request.model_dump()
                )
                logger.info(f"Brain service responded with {response.status_code}: {response.text}")
                if response.status_code == 200:
                    logger.info(f"Successfully forwarded email to brain")
                else:
                    logger.error(f"Brain service returned {response.status_code}: {response.text}")
                data = response.json()
                if 'response' in data:
                    return data['response']
                else:
                    logger.error("Brain service response did not contain 'response' key")
                    return
        except httpx.RequestError as e:
            logger.error(f"Request error while sending to brain service: {e}")
            return
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error while sending to brain service: {e}")
            return
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error while sending to brain service: {e}")
            return

        except Exception as e:
            logger.error(f"Error sending to brain service: {e}")


# Global monitor instance
email_monitor = EmailMonitor()


async def start_email_monitoring():
    """Start the email monitoring service."""
    await email_monitor.start()


def stop_email_monitoring():
    """Stop the email monitoring service."""
    email_monitor.stop()


def get_monitor_status() -> Dict[str, Any]:
    """Get the current status of the email monitor."""
    return {
        'running': email_monitor.running,
        'last_check_time': email_monitor.last_check_time,
        'seen_emails_count': len(email_monitor.seen_email_ids),
        'poll_interval': email_monitor.poll_interval
    }
