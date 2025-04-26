import shared.consul
from shared.config import TIMEOUT

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx
import json

from shared.models.contacts import Contact
from shared.models.discord import DiscordDirectMessage
from shared.models.proxy import ProxyDiscordDMRequest, ChatMessage, ProxyResponse
from shared.models.intents import IntentRequest
from shared.models.chromadb import MemoryListQuery

from app.modes import mode_get
from app.util import get_admin_user_id, sanitize_messages, post_to_service
from app.memory.list import list_memory
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/discord/message/incoming")
async def discord_message_incoming(message: DiscordDirectMessage):
    logger.debug(f"/discord/message/incoming Request: {message.model_dump()}")
    
    # get the user id from the contacts service
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            contacts_address, contacts_port = shared.consul.get_service_address('contacts')

            # look up the user by discord_id
            contact_data = await client.get(
                f"http://{contacts_address}:{contacts_port}/search",
                params={"key": "discord_id", "value": str(message.author_id)}
            )

            # if the user isn't found, tell them to register.
            # note that soon discord won't expect a response from us, so this will be a bit different.
            # we'll be sending a message to the user, not returning a response.
            if contact_data.status_code == status.HTTP_404_NOT_FOUND:
                resp = ProxyResponse(
                    response=f"Stranger danger! I don't know you. Please register with the bot first.",
                    generated_tokens=16,
                    timestamp=datetime.now().isoformat()
                )
                return resp

            # Only raise for other errors
            contact_data.raise_for_status()

            logger.debug(f"found contact data: {contact_data.json()}")

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error forwarding from contacts: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from contacts: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error when contacting contacts: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )

        except Exception as e:
            logger.exception("Error retrieving service address for contacts:", e)


    messages=[ChatMessage(role="user", content=message.content)]

    is_admin = (await get_admin_user_id()) == contact_data.json().get("id")

    # if user is an admin:
    if is_admin:

        # check for intents on user input
        # compontent probably really doesn't even need to be a thing with intents at this point.
        # but we need to pass it in the request, so
        intentreq = IntentRequest(
            mode=True,
            memory=True,
            component="proxy",
            message=messages,
        )

        response = await post_to_service(
            'intents', '/intents', intentreq.model_dump(),
            error_prefix="Error forwarding to intents service"
        )

        try:
            new_messages = response.json()
            # Only update messages if the response was successful and valid
            if isinstance(new_messages, list) and new_messages:
                messages = new_messages

        except Exception as e:
            logger.debug(f"Error decoding JSON from intents service response: {e}")
            # Log and continue, but do not update messages


    # get the mode, or just use 'guest' if the user isn't an admin
    if is_admin:
        mode_response = mode_get()
        if hasattr(mode_response, 'body'):
            mode_json = json.loads(mode_response.body)
            mode = mode_json.get('message')
        else:
            mode = 'guest'

    else:
        mode = 'guest'

    # get list of memories. eventually we'll have this for every user, but only handle admin for now.
    # well, okay, maybe every user. idk. users get summaries, maybe they get memories too.
    # memories take a lot of compute power, so maybe not.
    if is_admin:
        memory_query = MemoryListQuery(component="proxy", limit=100, mode=mode)
        listed_memories = await list_memory(memory_query)
        memories = [m.model_dump() for m in listed_memories]
    else:
        memories = None

    # sync with ledger
    try:
        user_id = contact_data.json().get("id")
        platform = 'discord'
        platform_msg_id = message.message_id
        messages = [m if isinstance(m, ChatMessage) else ChatMessage(**m) for m in messages]
        sync_snapshot = [
            {
                "user_id": user_id,
                "platform": platform,
                "platform_msg_id": str(platform_msg_id),
                "role": m.role,
                "content": m.content
            }
            for m in messages
        ]

        ledger_response = await post_to_service(
            'ledger',
            f'/ledger/user/{user_id}/sync',
            {"snapshot": sync_snapshot},
            error_prefix="Error forwarding to ledger service"
        )

        # Convert ledger buffer to ProxyMessage list
        ledger_buffer = ledger_response.json()
        messages = [ChatMessage(role=msg["role"], content=msg["content"]).model_dump() for msg in ledger_buffer]

    except Exception as e:
        logger.error(f"Error sending messages to ledger sync endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync messages with ledger service: {e}"
        )

    # sanitize proxy messages
    messages = sanitize_messages(messages)
    
    # get a list of summaries for the user - note that we are ONLY getting the last 4 summaries.
    # this will be changed to more of a daily/weekly/yearly format in the future, but for now just 
    # limit to the 4 most recent
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        address, port = shared.consul.get_service_address('ledger')
        if not address or not port:
            logger.error(f"ledger service address or port is not available.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"ledger service is unavailable."
            )

        try:
            summary_response = await client.get(f"http://{address}:{port}/summaries/user/{user_id}?limit=4")
            summary_response.raise_for_status()
            summaries = summary_response.json().get("summaries", [])
            combined_content = "\n".join(s["content"] for s in summaries)
        
            summaries = combined_content

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from ledger service: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"ledger: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to ledger service: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error to ledger service: {req_err}"
            )
        
        except Exception as e:
            logger.exception("Error contacting ledger ledger:", e)

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error contacting ledger service: {e}"
            )

    # Start constructing our ProxyDiscordDMRequest
    proxy_request = ProxyDiscordDMRequest(
        message=message,
        messages=messages or [ChatMessage(role="user", content=message.content)],
        contact=Contact(**contact_data.json()),
        is_admin=is_admin,
        mode=mode or 'guest',
        memories=memories or None,
        summaries=summaries or None
    )

    # send to LLM via discord endpoint in proxy service
    response = await post_to_service(
        'proxy', '/discord/dm', proxy_request.model_dump(),
        error_prefix="Error forwarding to proxy service"
    )
    try:
        json_response = response.json()
        proxy_response = ProxyResponse.model_validate(json_response)

    except Exception as e:
        logger.debug(f"Error parsing response from proxy service: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse response from proxy service: {e}"
        )

    # validate the response
    response_content = proxy_response.response
    if not isinstance(response_content, str):
        logger.debug(f"proxy_response.response is not a string: {type(response_content)}. Converting to string.")
        response_content = str(response_content)

    if is_admin:
        # send to intents, but only if the original message was from an admin.
        intentreq = IntentRequest(
            mode=True,
            component="proxy",
            memory=True,
            message=[ChatMessage(role="assistant", content=response_content)]
        )

        response = await post_to_service(
            'intents', '/intents', intentreq.model_dump(),
            error_prefix="Error forwarding to intents service"
        )

        try:
            returned_messages = response.json()

        except Exception as e:
            logger.debug(f"Error decoding JSON from intents service response (final): {e}")

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid JSON response from intents service (final)."
            )

        if isinstance(returned_messages, list) and returned_messages:
            proxy_response.response = returned_messages[0].get('content', proxy_response.response)

    try:
        # Send proxy_response to ledger as a single RawUserMessage
        # we're not sending the platform_msg_id here, because we don't have it yet. this is one of the reasons
        # we're going to use a callback for the discord microservice. soon!
        user_id = contact_data.json().get("id")
        platform = 'discord'
        platform_msg_id = None
        sync_snapshot = [{
            "user_id": contact_data.json().get("id"),
            "platform": 'discord',
            "platform_msg_id":  None,
            "role": "assistant",
            "content": proxy_response.response
        }]
    
        await post_to_service(
            'ledger',
            f'/ledger/user/{user_id}/sync',
            {"snapshot": sync_snapshot},
            error_prefix="Error forwarding to ledger service (proxy_response)"
        )

    except Exception as e:
        logger.error(f"Error sending proxy_response to ledger sync endpoint: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync proxy_response with ledger service {e}"
        )

    logger.debug(f"/discord/message/incoming Returns:\n{proxy_response.model_dump_json(indent=4)}")

    return proxy_response