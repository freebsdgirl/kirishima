import sys
import requests
import json
import re
from pydantic import BaseModel, Field

class RespondJsonRequest(BaseModel):
    """
    A Pydantic model representing a JSON request for generating a model response.
    
    Attributes:
        model (str): The name of the model to be used for generating the response.
        prompt (str): The input text or prompt to be processed by the model.
        temperature (float): Controls the randomness of the model's output. Higher values increase creativity.
        max_tokens (int): The maximum number of tokens to generate in the response.
        format (object): The class of the response, typically a Pydantic model.
    """
    model: str                          = Field(..., description="The model to be used for generating the response.")
    prompt: str                         = Field(..., description="The prompt or input text for the model.")
    temperature: float                  = Field(..., description="The temperature setting for randomness in the model's output.")
    max_tokens: int                     = Field(..., description="The maximum number of tokens to generate in the response.")
    format: object                      = Field(None, description="the class of the response, typically a Pydantic model.")



proxy_url = "http://localhost:4205/json"

prompt_text = """### TASK
Determine if it is appropriate to respond to the user or if they are talking to someone else.

### FORMAT

Timestamps are in UTC in brackets. The format is [YYYY-MM-DD HH:MM:SS]. Do not include the timestamp in your response.
You will appear as <kirishima> in the conversation. Your previous response will also have a timestamp in the same format as the conversation.
Refer to the user as the part of their name after speaker_. Do not include the speaker_ part of their name in your response. Do not include the '<' or '>' characters when using their name.
Respond only using JSON.

### EXAMPLE

[2023-10-01 12:00:00] <speaker_paul> Hey Kirishima, how are you doing today?
[2023-10-01 12:02:00] <kirishima> Not bad, paul. Just hanging out, you know? How about you?
[2023-10-01 12:06:00] <speaker_paul> I'm doing great! Just finished a workout.

### INTERNAL REASONING

Consider the rate of participation for each user compared to your own rate of participation.
As you process the conversation, track the current topic.
As you process the conversation, track the participation rate of each user.

### RULES

Consider each of the following rules in order.

Stop processing rules and respond with True if The user is talking to you directly and you have not yet responded.
Stop processing rules and respond with True if You are the target of the conversation and you have not yet responded.
Stop processing rules and respond with True if You previously responded to the conversation and your rate of participation is significantly lower than the average rate of participation of the other users in the conversation.

Stop processing rules and respond with False if:

 The conversation is mostly composed of people that do not include you.
 You are not included in the conversation at all and the users participating in the conversation do not generally include you in their conversations.
 Your rate of participation in the conversation is higher than the average rate of participation of the other users in the conversation.

Stop processing rules and respond with True if:

 The conversation is a topic that you are interested in and you have not yet responded.
 
If you are not sure, respond with False.

### CONVERSATION

[2023-10-01 12:00:00] <speaker_paul> Hey Kirishima, how are you doing today?
[2023-10-01 12:01:00] <kirishima> Not bad, paul. Just hanging out, you know? How about you?
[2023-10-01 12:02:00] <speaker_paul> I'm doing great! Just finished a workout.
[2023-10-01 12:02:45] <speaker_ryan> I think your workout routine is awesome! You're really dedicated to your fitness.
[2023-10-01 12:03:00] <speaker_paul> Thanks, ryan! I appreciate the support.
[2023-10-01 12:04:00] <speaker_alice> Ryan, do you think I should try a new exercise?
[2023-10-01 12:05:00] <speaker_jacob> I went shopping yesterday and bought some new workout gear. I think you should try something new, paul. It might be fun!
[2023-10-01 12:06:00] <speaker_alice> Ryan, have you met my friend Jacob? He's really into fitness too.
[2023-10-01 12:07:00] <speaker_jacob> I'm hungry.
[2023-10-01 12:08:00] <speaker_alice> does anyone want to play overwatch?
[2023-10-01 12:09:00] <speaker_jacob> overwatch is ass.
[2023-10-01 12:10:00] <speaker_alice> what's everyone doing tonight?
[2023-10-01 12:11:00] <speaker_paul> does anyone know anything about fine-tuning an AI?
[2023-10-01 12:12:00] <speaker_Randi> i know a little about fine-tuning a kirishima. ;)
[2023-10-01 12:12:20] <speaker_paul> randi, how old is kirishima now?
[2023-10-01 12:12:40] <speaker_Randi> kirishima, how old are you?


### OUTPUT

Do not reply to the conversation. Only determine if you should respond or not.
Response: True or False (if you should respond or not)
Target: User, Group, or Self (the target of the previous user's message)
Reason: the reasoning for your response
Tone: the tone of each user
Topic: the most recent topic of conversation


Respond only using JSON.


### EXAMPLE OUTPUT
{
  "response": true,
  "target": "Group",
  "reason": "The conversation has shifted to a topic I am interested in and I have not yet responded.",
  "tone": {
    "paul": "Serious, Engaged",
    "alice": "Casual, Social",
    "jacob": "Apathetic",
    "ryan": "Enthusiastic"
  },
  "topic": "pizza"
}


"""

system_prompt = f"""[INST]<<SYS>>{prompt_text}<<SYS>>[/INST]"""

class ChatResponse(BaseModel):
    response: bool
    target: str
    reason: str
    tone: dict
    topic: str

payload = RespondJsonRequest(
    model="nemo:latest",
    prompt=system_prompt,
    temperature=0.3,
    max_tokens=1024,
    raw=True,
    stream=False,
    format=ChatResponse.model_json_schema()
)

def clean_json_string(s):
    s = s.strip()
    s = re.sub(r'^```(?:json)?\s*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*```$', '', s)
    return s

for n in range(5):
    try:
        response = requests.post(proxy_url, json=payload.model_dump())
        response.raise_for_status()
        data = response.json()
        try:
            cleaned = clean_json_string(data['response'])
            parsed = json.loads(cleaned)
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, TypeError, KeyError):
            print(data['response'])
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        sys.exit(1)

