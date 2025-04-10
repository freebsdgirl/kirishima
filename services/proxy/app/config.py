import os

LLM_MODEL_NAME                          = os.getenv('LLM_MODEL_NAME', 'nemo')
OLLAMA_SERVER_HOST                      = os.getenv('OLLAMA_SERVER_HOST', 'localhost')
OLLAMA_SERVER_PORT                      = os.getenv('OLLAMA_SERVER_PORT', '11434')
OLLAMA_URL                              = os.getenv('OLLAMA_URL', f'http://{OLLAMA_SERVER_HOST}:{OLLAMA_SERVER_PORT}')