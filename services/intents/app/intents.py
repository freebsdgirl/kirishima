
from fastapi import APIRouter, HTTPException, status
from shared.models.intents import IntentRequest
from shared.models.proxy import ProxyMessage

import app.mode

router = APIRouter()

@router.post("/intents", response_model=dict)
async def process_intents(payload: IntentRequest) -> dict:
    """
    At least one boolean flag must be true.
    If a flag is true, call its function, passing in the list if needed.
    """
    
    if not (payload.mode):  # add more booleans with `or payload.foo`
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one intent flag must be set to true."
        )

    # Get the very last message
    if payload.message:
        last_message: ProxyMessage = payload.message[-1]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No messages in payload.message"
        )
    
    # Get the last 10 messages (or fewer, if there aren’t 10 yet)
    last_ten: list[ProxyMessage] = payload.message[-10:]

    if payload.mode:
        try:
            code = await app.mode.process_mode(last_message)
            if code != status.HTTP_200_OK:
                raise HTTPException(
                    status_code=code,
                    detail=f"mode handler returned {code}"
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error in mode: {e}"
            )

    return {"detail": "All requested intents processed successfully"}
