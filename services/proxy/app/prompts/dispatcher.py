
import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import httpx
from fastapi import HTTPException, status


async def get_prompt_builder():
    # Get mode from brain.
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            brain_address, brain_port = shared.consul.get_service_address('brain')
            if not brain_address or not brain_port:
                logger.error("Brain service address or port is not available.")

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Brain service is unavailable."
                )
            
            response = await client.get(f"http://{brain_address}:{brain_port}/mode")
            response.raise_for_status()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from brain service: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error forwarding to brain service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error forwarding to brain service: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error to brain service: {req_err}"
            )
     
        json_response = response.json()
        mode = json_response.get("message", None)

    if mode:
        if mode == "nsfw":
            from app.prompts.nsfw.generate import build_prompt

        elif mode == "work":
            from app.prompts.work.generate import build_prompt

        else:
            from app.prompts.default.generate import build_prompt

    else:
        from app.prompts.guest.generate import build_prompt

    return build_prompt
