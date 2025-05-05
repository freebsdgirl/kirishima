import shared.consul
from shared.config import TIMEOUT

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx
import json

from shared.models.contacts import Contact
from shared.models.imessage import iMessage, ProxyiMessageRequest
from shared.models.proxy import ChatMessage, ProxyResponse
from shared.models.intents import IntentRequest
from shared.models.memory import MemoryListQuery
from shared.models.summary import Summary
from shared.models.notification import LastSeen

from app.modes import mode_get
from app.util import get_admin_user_id, sanitize_messages, post_to_service
from app.memory.get import list_memory
from app.last_seen import update_last_seen

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
router = APIRouter()


@router.post("/imessage/incoming")
async def imessage_incoming(message: iMessage):
    logger.debug(f"/imessage/incoming Request: {message.model_dump()}")
    
    # get the user id from the contacts service
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            contacts_address, contacts_port = shared.consul.get_service_address('contacts')

            # look up the user by imessage
            contact_data = await client.get(
                f"http://{contacts_address}:{contacts_port}/search",
                params={"key": "imessage", "value": str(message.author_id)}
            )

            # if the user isn't found, tell them to register.
            # note that soon imessage won't expect a response from us, so this will be a bit different.
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

    user_id = contact_data.json().get("id")
    is_admin = (await get_admin_user_id()) == user_id

    # if user is an admin:
    if is_admin:

        # check for intents on user input
        # component probably really doesn't even need to be a thing with intents at this point.
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
        platform_msg_id = message.id
        messages = [m if isinstance(m, ChatMessage) else ChatMessage(**m) for m in messages]
        sync_snapshot = [
            {
                "user_id": user_id,
                "platform": 'imessage',
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
    
    # get a list of summaries for the user 
    try:
        chromadb_address, chromadb_port = shared.consul.get_service_address('chromadb')

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"http://{chromadb_address}:{chromadb_port}/summary?user_id={user_id}&limit=4")
            response.raise_for_status()
            summaries = response.json()

    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_404_NOT_FOUND:
            logger.info(f"No summaries found for {user_id}, skipping.")
        else:
            logger.error(f"HTTP error from chromadb: {e.response.status_code} - {e.response.text}")
            raise

    except Exception as e:
        logger.error(f"Failed to contact chromadb to get a list of summaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve summaries: {e}")

    if not summaries:
        logger.warning("No summaries found for the specified period.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No summaries found for the specified period."
        )

    # construct summary string here
    summary_lines = []
    for s in summaries:
        summary = Summary.model_validate(s) if not isinstance(s, Summary) else s
        meta = summary.metadata
        if meta is not None:
            if meta.summary_type.value == "daily":
                # Split on space to get the date part
                date_str = meta.timestamp_begin.split(" ")[0]
                label = date_str
            else:
                label = meta.summary_type.value
        else:
            label = "summary"
        summary_lines.append(f"[{label}] {summary.content}")

        summaries = "\n".join(summary_lines)

    # Start constructing our ProxyiMessageRequest
    proxy_request = ProxyiMessageRequest(
        message=message,
        messages=messages or [ChatMessage(role="user", content=message.content)],
        contact=Contact(**contact_data.json()),
        is_admin=is_admin,
        mode=mode or 'guest',
        memories=memories or None,
        summaries=summaries or None
    )

    # send to LLM via imessage endpoint in proxy service
    response = await post_to_service(
        'proxy', '/imessage', proxy_request.model_dump(),
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
        # we're going to use a callback for the imessage microservice. soon!
        sync_snapshot = [{
            "user_id": user_id,
            "platform": 'imessage',
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

    # update last seen
    update_last_seen(LastSeen(
        user_id=user_id,
        platform="imessage"
    ))

    logger.debug(f"/imessage/incoming Returns:\n{proxy_response.model_dump_json(indent=4)}")

    return proxy_response