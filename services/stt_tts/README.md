# TTS/STT Services

Voice input/output stack for the system. These services are run outside Docker due to PulseAudio and hardware constraints.

## Controller API

Provides a REST API to start/stop/check the status of TTS and STT subprocesses, and to forward TTS requests:

- POST /tts/start — Start TTS subprocess
- POST /tts/stop — Stop TTS subprocess
- GET /tts/status — Status of TTS subprocess
- POST /tts/speak — Forward TTS request to local backend
- POST /v1/audio/speech — OpenAI-compatible TTS; streams audio from backend
- POST /stt/start — Start STT subprocess
- POST /stt/stop — Stop STT subprocess
- GET /stt/status — STT subprocess status

Thread safety is handled with locks. Subprocesses are launched and killed gracefully, with fallback to SIGKILL if needed.

## STT Service

Continuous speech interface (can be started via controller):

- Microphone input captured in real-time using Vosk for utterance detection
- Each utterance saved as an audio file
- Transcription by OpenAI Whisper (default: medium)
- User input sent to LLM; response played back via TTS
- Handles automatic mic muting during playback
- Debug mode: disables temp file deletion for troubleshooting
- Hardcoded API URLs and paths (needs cleanup)
- Dependencies: vosk, whisper, sounddevice, soundfile, requests
- vosk-model-en-us-0.22 must be in the service directory

## TTS Service

Runs independently of STT, but STT requires TTS to function:

- FastAPI service; uses ChatterboxTTS for speech generation
- Streams TTS audio as WAV, supports OpenAI-compatible endpoints
- Loads voice prompts from a /prompts directory
- Voice = prompt filename; model = comma-separated config string (e.g. temperature=1.1,exaggeration=0.7,cfg_weight=0.5,gap=0.5)
- Supports streaming, async model loading, and sentence-level playback
- GET /v1/audio/voices — List available voice prompts
- GET /v1/audio/models — List TTS model configs
- Output audio/logs stored relative to the script’s parent directory
- CUDA strongly recommended for performance
- Dependencies: FastAPI, torchaudio, sounddevice, soundfile, nltk, threading, uvicorn, ChatterboxTTS

## Directory Structure

- vosk-model-en-us-0.22 in service directory for STT
- prompts/ folder for TTS voice prompts (WAV files)
- Output audio/logs stored next to the service scripts

## Notes

- TTS can run standalone; STT is dependent on TTS
- Voice/model options are passed directly in the OpenAI-compatible API
- Hardcoded config in STT should eventually be parameterized