"""
This module defines data models for representing and converting between OpenAI and Ollama models.
Classes:
    ModelInfoBase:
        A base class for model information with common properties.
    OpenAIModel:
        Represents an OpenAI model with attributes such as ID, creation time, and owner.
    OllamaModel:
        Represents an Ollama model with attributes such as name, modification time, parameter size, 
        quantization level, and optional context length. Includes a method to convert to an OpenAIModel.
    OpenAIModelList:
        A container for a list of OpenAIModel instances.
    OllamaModelList:
        A container for a list of OllamaModel instances.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ModelInfoBase(BaseModel):
    """
    Base model for model info with common properties.
    
    Attributes:
        object (str): The type of the object; always "model".
    """
    object: Literal["model"]            = Field("model", description="Type of the model")

    model_config = {
        "json_schema_extra": {
            "example": {
                "object": "model"
            }
        }
    }


class OpenAIModel(ModelInfoBase):
    """
    Represents an OpenAI model.
    
    Attributes:
        id (str): The model name.
        created (int): Model creation time (UNIX timestamp).
        owned_by (str): Owner of the model.
    """
    id: str                             = Field(..., description="Name of the model")
    created: int                        = Field(..., description="Creation time of the model")
    owned_by: str                       = Field("Randi-Lee-Harper", description="Owner of the model")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "gpt-3.5-turbo",
                "created": 1672531199,
                "owned_by": "Randi-Lee-Harper"
            }
        }
    }


class OpenAIModelList(BaseModel):
    data: List[OpenAIModel]             = Field(..., description="List of OpenAI models")

    model_config = {
        "json_schema_extra": {
            "example": {
                "data": [
                    {
                        "id": "gpt-3.5-turbo",
                        "created": 1672531199,
                        "owned_by": "Randi-Lee-Harper"
                    }
                ]
            }
        }
    }
