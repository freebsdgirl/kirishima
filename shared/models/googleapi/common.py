"""
Common models for GoogleAPI service.
Contains shared response models used across multiple services.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    """
    Generic response model for API operations representing the result of any action.
    
    Attributes:
        success (bool): Indicates whether the operation was completed successfully.
        message (str): A descriptive message about the result of the operation.
        data (Optional[Dict[str, Any]]): Optional dictionary containing additional response details.
    """
    success: bool                         = Field(..., description="Indicates if the operation was successful")
    message: str                          = Field(..., description="Response message")
    data: Optional[Dict[str, Any]]        = Field(None, description="Response data")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Operation completed successfully",
                    "data": {
                        "id": "1234567890abcdef",
                        "details": "Additional information"
                    }
                },
                {
                    "success": False,
                    "message": "Operation failed: Error description",
                    "data": None
                }
            ]
        }
    } 