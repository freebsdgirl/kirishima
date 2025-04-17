from pydantic import BaseModel
from typing import Optional, List
from shared.models.proxy import ProxyMessage

class IntentRequest(BaseModel):
    """
    IntentRequest is a data model representing a request with optional flags.

    Attributes:
        message (List[ProxyMessage]): A list of messages representing the conversation history.
        mode (Optional[bool]): A flag indicating the mode of the request. Defaults to False.
    """
    message: List[ProxyMessage] = []
    mode: Optional[bool] = False
