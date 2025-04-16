from pydantic import BaseModel
from typing import Optional


class IntentRequest(BaseModel):
    """
    IntentRequest is a data model representing a request with optional flags.

    Attributes:
        mode (Optional[bool]): A flag indicating the mode of the request. Defaults to False.
        # Additional flags can be added as needed, such as:
        # sync (Optional[bool]): A flag indicating whether the request should be synchronized. Defaults to False.
        # cleanup (Optional[bool]): A flag indicating whether cleanup operations should be performed. Defaults to False.
    """
    mode: Optional[bool] = False
    # add more flags here, e.g.:
    # sync: Optional[bool] = False
    # cleanup: Optional[bool] = False