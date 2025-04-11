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


class OllamaModel(ModelInfoBase):
    """
    Represents an Ollama model.
    
    Attributes:
        name (str): The model name.
        modified_at (str): Last modified time (ISO 8601 formatted).
        parameter_size (int): Size of the model (number of parameters).
        quantization_level (str): The quantization level of the model.
        context_length (Optional[int]): The model's context length.
    """
    name: str                           = Field(..., description="Name of the model")
    modified_at: str                    = Field(..., description="Last modified time of the model")
    parameter_size: str                 = Field(..., description="Size of the model in parameters")
    quantization_level: str             = Field(..., description="Quantization level of the model")
    context_length: Optional[int]       = Field(None, description="Context length of the model")


    def to_openai_model(self) -> OpenAIModel:
        """
        Converts this OllamaModel into an OpenAIModel.
        
        For the OpenAI model, we assign:
          - id from self.name
          - created from parsing the modified_at value (if possible)
          - owned_by a default value.
        
        Returns:
            OpenAIModel: A converted model object.
        """
        try:
            # Try to parse modified_at (which is an ISO8601 string) into a UNIX timestamp.
            dt = datetime.fromisoformat(self.modified_at)
            created = int(dt.timestamp())
        except Exception:
            # If parsing fails, fall back to current time.
            created = int(datetime.now().timestamp())
        return OpenAIModel(
            id=self.name,
            created=created,
            owned_by="Randi-Lee-Harper"
        )


class OpenAIModelList(BaseModel):
    data: List[OpenAIModel]             = Field(..., description="List of OpenAI models")


class OllamaModelList(BaseModel):
    data: List[OllamaModel]             = Field(..., description="List of Ollama models")
