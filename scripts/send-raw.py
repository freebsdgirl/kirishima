import sys
import requests
import json
from pydantic import BaseModel, Field

class RespondJsonRequest(BaseModel):
    model: str                          = Field(..., description="The model to be used for generating the response.")
    prompt: str                         = Field(..., description="The prompt or input text for the model.")
    temperature: float                  = Field(..., description="The temperature setting for randomness in the model's output.")
    max_tokens: int                     = Field(..., description="The maximum number of tokens to generate in the response.")
    format: object                      = Field(None, description="the class of the response, typically a Pydantic model.")


proxy_url = "http://localhost:4205/json"

prompt_text = """### TASK
Determine the intent of the user's latest message.
Only consider the latest message in the conversation - other messages are for context only.
Choose from the list of intents. If nothing applies, respond with "Conversation".
Include metadata about the intent in the response.
If the intent is "conversation", include a "summary" in the metadata.
This summary should be a short, one-sentence summary that will be used to lookup memories.



### INTENTS

- mode: the user is asking about the current mode of the system.
    metadata: 
        set: (string) The mode the user is asking to set.
- memory: The user is asking about the current memory of the system.
    metadata:
        create: (string) The user is asking to create a new memory.
        priority: (float) The priority of the created memory.
        delete: (string) The user is asking to delete a memory.
        search: (string) The user is asking to search for a memory.
- anime: The user is asking about anime.
    metadata:
        title: (string) The title of the anime.
        character: (string) The character from the anime.
        genre: (string) The genre of the anime.
- email: The user is asking about email.
    metadata:
        check_inbox: (boolean) The user is asking to check their inbox.
        send_email: (boolean) The user is asking to send an email.
        email: (string) the content of the email the user is asking to send.
        to: (string) The recipient of the email.
        subject: (string) The subject of the email.



### EXAMPLE

User: Set the mode to 'nsfw'.

Response:
{
    "intent": "mode",
    "metadata": {
        "set": true,
        "mode": "nsfw"
    }
}



### EXAMPLE

User: Can you email my boss and tell him I need to take a day off? His email is john@doe.com

Response:
{
    "intent": "email",
    "metadata": {
        "send_email": true,
        "to": "john@doe.com",
        "email": "Hey! Something has come up and I need to take a day off. Thanks for your understanding.",
        "subject": "Day off request"
    }
}



### MESSAGE

User: I love the character Kirishima from Yakuza Fiance. 
Assistant: Me too! He's so cool and strong.
User: What's the current mode?
Assistant: I think it's set to 'default'.
User: Can you set it to 'nsfw'?
Assistant: Sure! Setting the mode to 'nsfw' now.
User: I'm so tired today. :(



### TASK
Determine the intent of the user's latest message.
Only consider the latest message in the conversation - other messages are for context only.
Choose from the list of intents. If nothing applies, respond with "Conversation".
Include metadata about the intent in the response.
If the intent is "conversation", include a "summary" in the metadata.
This summary should be a short, one-sentence summary that will be used to lookup memories.
"""

prompt = f"""[INST]<<SYS>>{prompt_text}<<SYS>>[/INST]\n """

class ChatResponse(BaseModel):
    intent: str
    metadata: dict

payload = RespondJsonRequest(
    model="nemo:latest",
    prompt=prompt,
    temperature=0.3,
    max_tokens=1024,
    raw=True,
    stream=False,
    format=ChatResponse.model_json_schema()
)


for n in range(5):
    try:
        response = requests.post(proxy_url, json=payload.model_dump())
        response.raise_for_status()
        data = response.json()
        try:
            parsed = json.loads(data['response'])
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, TypeError, KeyError):
            print(data['response'])
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        sys.exit(1)