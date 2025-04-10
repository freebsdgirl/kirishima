import app.config

from shared.log_config import get_logger

logger = get_logger(__name__)

from app.v1.chat.completions import ChatRequest
from app.v1.chat.functions.function import is_this_a_user_function, is_this_a_llm_function
from app.v1.chat.functions.memories import list_memories
from app.v1.chat.buffer import add_to_buffer, get_buffer_prompt

#import app.prompts.generate

import json
import re
import time

# Try to send the Mistral chat completion request
from fastapi import HTTPException
import httpx

# Load a tokenizer (using a compatible model; adjust model name as needed)
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained(app.config.CHROMADB_MODEL_NAME)


def trim_conversation_history(conversation_history, max_tokens):
    """
    Trims conversation history to fit within a specified token limit.
    
    Args:
        conversation_history (list): A list of message strings, with oldest messages at the start.
        max_tokens (int): Maximum number of tokens allowed in the trimmed conversation history.
    
    Returns:
        list: A subset of the original conversation history that does not exceed the specified token limit,
            preserving the most recent messages while maintaining the original chronological order.
    """
    token_count = 0
    trimmed = []

    # Process messages from newest to oldest
    for message in reversed(conversation_history):
        # Encode the message to get the token IDs; adjust parameters as needed.
        tokens = tokenizer.encode(message, add_special_tokens=False)
        if token_count + len(tokens) > max_tokens:
            break
        token_count += len(tokens)
        trimmed.append(message)

    # Since we built our list in reverse (newest first), reverse it back to original order.
    trimmed.reverse()
    return trimmed


def format_openai_to_chatml_chat_history(messages):
    return [
        f"<|im_start|>{msg['role']}\n{msg['content']}\n<|im_end|>"
        for msg in messages
    ]

def format_openai_to_instruct_chat_history(messages: list[dict]) -> list[dict]:
    """
    Converts OpenAI-style chat messages into an array of instruct-style conversation turns.
    Each item is a {"text": "[INST] user [/INST] assistant"} pair.
    Useful for trimming context by turn.
    """
    pairs = []
    user_message = None

    for msg in messages:
        role = msg["role"]
        content = msg["content"].strip()

        if role == "user":
            user_message = content
        elif role == "assistant" and user_message:
            pairs.append(f"[INST] {user_message} [/INST] {content}")
            user_message = None

    return pairs



async def generate_completion(request_data: ChatRequest):
    """
    Asynchronously generate a chat completion using Ollama API.
    
    Processes the input messages, formats conversation history, retrieves relevant memories,
    and sends a request to the Ollama API to generate a response. Handles various configuration
    options like instruction mode, temperature, and token limits.
    
    Args:
        request_data (ChatRequest): The chat request containing messages and generation parameters.
    
    Returns:
        dict: A standardized chat completion response in OpenAI-compatible format, 
              including the generated assistant message and metadata.
    
    Raises:
        HTTPException: If there are issues with the Ollama API request or response processing.
    """
    messages = request_data.messages

    function_output = ""

    user_input = str(messages[-1]["content"])  # Extract the last user message

    # Check if the user input matches the ignore pattern
    if user_input.startswith("### Task:"):
        logger.debug("⚠️ Ignoring system-generated prompt. Skipping keyword extraction and ChromaDB search.")
    else:
        # check for functions from user side
        function_output = is_this_a_user_function(user_input)
        add_to_buffer(user_input, 'Randi')

    if app.config.INSTRUCT:
        conversation_history = format_openai_to_instruct_chat_history(messages)
    else:
        conversation_history = format_openai_to_chatml_chat_history(messages)

    # construct our new history.
    limited_history = trim_conversation_history(conversation_history, app.config.CONVERSATION_TOKENS_SOFT_LIMIT)

    if len(limited_history) >= 4:
        # Construct the request payload for Ollama's completion API
        memory_list = list_memories()
    else:
        memory_list = "No relevant memories found for this conversation. Let's start fresh."

    buffer_prompt = get_buffer_prompt()

    payload = {
        "model": app.config.DEFAULT_SETTINGS["model"],
        "prompt": app.prompts.generate.prompt().format(
            memory_list=memory_list,
            function_output=function_output,
            buffer_prompt=buffer_prompt,
            formatted_history="\n".join(limited_history),
            user_input=user_input
        ),
        "stream": app.config.DEFAULT_SETTINGS["stream"],
        "options": {
            "temperature": request_data.temperature,
            "top_p": request_data.top_p,
            "max_tokens": app.config.DEFAULT_SETTINGS["max_tokens"]
        }
    }


    # Log a debug message before sending the Mistral chat completion request
    logger.debug(f"📤 Sending Ollama Chat Completion Request: {json.dumps(payload, indent=2)}")
    try:
        # Create an asynchronous client with a timeout of 30 seconds
        async with httpx.AsyncClient(timeout=60.0) as client:

            if function_output:
                response_text = function_output
            else:
                # Send a POST request to the Mistral API with the payload
                response = await client.post(app.config.OLLAMA_API_URL, json=payload)

                # Check if the response status code is not 200
                if response.status_code != 200:
                    # Raise an HTTPException with the status code and detail from the response
                    raise HTTPException(status_code=response.status_code, detail=response.text)

                # Extract and clean response text
                response_text = regex_completion(
                    extract_response_text(response)
                )

                await is_this_a_llm_function(response_text)

            return {
                "id": "chatcmpl-abc123",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": app.config.DEFAULT_SETTINGS["model"],
                "choices": [
                    {
                        "index": 0, 
                        "message": {
                            "role": "assistant", 
                            "content": response_text
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 1
                }
            }

    except json.JSONDecodeError:
        # Log an error message if JSON decoding fails
        logger.error("JSON decoding failed. Invalid response from Ollama.")
        raise HTTPException(status_code=500, detail="Invalid JSON response from Ollama.")

    except Exception as e:
        # Log any other exceptions and re-raise them
        logger.error(f"ERROR in chat completion: {str(e)}")
        raise 


# regex out 😏 when followed by possible whitespace at start of response.
# regex out [TOOL_CALLS] and anything that comes after it. this is usually on the last line, unless it's by itself.
# regex out 👀 or 🤔 which may be followed by whitespace if it's on the first line.
# If the response is not empty and is not exactly a backtick or a smirk emoji, accept it.
def regex_completion(response_text) -> str:
    """
    Clean and sanitize AI-generated response text by removing specific emoji markers,
    tool call indicators, and empty lines.
        
    Args:
        response_text (str): The raw text response from an AI model.
        
    Returns:
        str: A cleaned version of the response with unwanted markers removed.
    """
    lines = response_text.strip().split('\n')
    cleaned_lines = []

    for line in lines:
        # 1. Remove 😏 if it's at the start, followed by optional whitespace
        line = re.sub(r'^\s*😏\s*', '', line)

        # 2. Remove 👀 or 🤔 at the start, followed by optional whitespace
        line = re.sub(r'^\s*[👀🤔]\s*', '', line)

        # 3. Check for [TOOL_CALLS] — if present, discard this line and any after
        if '[TOOL_CALLS]' in line:
            break

        # If the line isn't empty after cleaning, keep it
        if line.strip():
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines).strip()


def extract_response_text(response):
    try:
        ollama_response = response.json()
    except ValueError:
        raise ValueError("Failed to decode Ollama response as JSON.")

    if "response" not in ollama_response:
        raise ValueError("No 'response' field in Ollama output.")

    sanitized_response = dict(ollama_response)
    sanitized_response.pop("context", None)
    logger.debug(f"Ollama Response: {json.dumps(sanitized_response, indent = 2, ensure_ascii=False)}") 

    return ollama_response["response"].strip()
