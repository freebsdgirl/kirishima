# TTS/STT Services

The voice input/output stack for the Kirishima system, providing continuous speech-to-text recognition and high-quality text-to-speech synthesis. These services run outside Docker containers due to PulseAudio and audio hardware access requirements.

## Architecture Overview

The STT/TTS system consists of three main components:

1. **Controller Service** (`controller.py`): Process manager and API gateway running on port 4208
2. **TTS Service** (`tts_service.py`): ChatterboxTTS-based speech synthesis on port 4210  
3. **STT Service** (`stt_service.py`): Continuous speech recognition and conversation loop

### Service Communication Flow

```mermaid
External Client → Controller (4208) → TTS Service (4210) → ChatterboxTTS Model
                      ↓
STT Service → Vosk (Real-time) → Whisper (Transcription) → Brain API → TTS Service
```

## Controller API (`controller.py`)

The controller provides a REST API for managing TTS and STT subprocesses and forwarding requests. Runs on port 4208.

### Process Management Endpoints

- **POST /tts/start** — Launch TTS subprocess with graceful shutdown handling
- **POST /tts/stop** — Terminate TTS subprocess (SIGTERM → SIGKILL fallback)  
- **GET /tts/status** — Check if TTS subprocess is running
- **POST /stt/start** — Launch continuous STT subprocess
- **POST /stt/stop** — Terminate STT subprocess with graceful cleanup
- **GET /stt/status** — Check STT subprocess status

### Audio Processing Endpoints

- **POST /tts/speak** — Forward TTS request to local backend (port 4210)
- **POST /v1/audio/speech** — OpenAI-compatible TTS endpoint with streaming response

**Thread Safety**: Uses `threading.Lock()` for process management operations. Subprocesses are launched via `subprocess.Popen()` and terminated gracefully with 10-second timeout before force kill.

**OpenWebUI Integration**: The `/v1/audio/speech` endpoint is fully OpenAI TTS API compatible. Configure OpenWebUI's TTS settings to point to `http://localhost:4208/v1/audio/speech` to enable automatic audio playback for all agent responses.

## TTS Service (`tts_service.py`)

High-quality neural text-to-speech using ChatterboxTTS. Runs independently on port 4210.

### Technical Implementation

**Model**: ChatterboxTTS loaded on CUDA device during FastAPI lifespan startup for optimal performance
**Audio Processing**: Generates WAV files using torchaudio, supports real-time streaming via `StreamingResponse`
**Voice Cloning**: Uses audio prompt files (WAV) from `prompts/` directory for voice characteristic transfer

### Audio Generation Pipeline

1. **Text Processing**: Sentence tokenization using NLTK punkt
2. **Voice Synthesis**: ChatterboxTTS with configurable parameters:
   - `temperature`: Controls speech randomness/naturalness (default: 1.1)
   - `exaggeration`: Speech style intensity (default: 0.7)
   - `cfg_weight`: Classifier-free guidance strength (default: 0.5)
   - `gap`: Inter-sentence pause duration (default: 0.5s)
3. **Audio Output**: 16kHz WAV files saved to `output/` with UUID filenames
4. **Logging**: All generations logged to `tts.log` with UUID-text mapping

### API Endpoints

- **POST /tts/speak** — Generate and stream TTS audio with local playback
- **POST /v1/audio/speech** — OpenAI-compatible endpoint (input, voice, model params)
- **GET /v1/audio/voices** — List available voice prompts from `prompts/` directory
- **GET /v1/audio/models** — List predefined model parameter configurations

### Voice Prompt System

Voice characteristics are defined by WAV files in `prompts/` directory:

- `tony_stark_2.wav` (default)
- `david_attenborough_1.wav`
- `billie_eilish_1.wav`
- `corpse_husband_1.wav`
- Additional celebrity/character voices

Model parameters can be specified as comma-separated string: `"temperature=1.2,exaggeration=0.8,cfg_weight=0.4"`

## STT Service (`stt_service.py`)

Continuous speech recognition with conversational AI integration. Provides hands-free interaction loop.

### Technical Architecture

**Real-time Audio Capture**:

- `sounddevice.RawInputStream` with 16kHz mono, 4096-sample blocks
- Thread-safe audio queue for stream processing
- Automatic microphone muting during TTS playback

**Two-Stage Recognition**:

1. **Vosk** (Real-time): Lightweight model for utterance boundary detection and basic recognition
2. **Whisper** (Accuracy): OpenAI Whisper "medium" model for high-quality transcription of detected utterances

### Conversation Flow

```text
Microphone Input → Vosk Detection → WAV File Save → Whisper Transcription → 
Brain API Request → LLM Response → TTS Generation → Audio Playback → Resume Listening
```

### Configuration

**Hardcoded Services** (TODO: move to config.json):

- LLM API: `http://localhost:4200/v1/chat/completions`
- TTS API: `http://localhost:4210/v1/audio/speak`
- Model: `tts` mode for brain service
- Timeout: 60 seconds for LLM requests

**Required Models**:

- Vosk model: `vosk-model-en-us-0.22/` in service directory
- Whisper model: "medium" (auto-downloaded)

### Audio File Management

**Input Files**: Utterances saved to `input/utterance_{timestamp}_{counter}.wav`
**TTS Files**: Responses saved to `input/tts_{timestamp}_{counter}.wav`  
**Debug Mode**: Set `DEBUG=1` environment variable to preserve audio files for analysis

### Error Handling

- Graceful recovery from transcription errors
- Automatic stream restart after TTS playback
- Network timeout handling for LLM/TTS requests
- Audio device error recovery

## Dependencies

```text
fastapi - Web framework for API services
sounddevice - Cross-platform audio I/O 
soundfile - Audio file reading/writing
vosk - Lightweight speech recognition
whisper - OpenAI transcription model
nltk - Natural language processing (sentence tokenization)
chatterbox.tts - Neural TTS model
torchaudio - PyTorch audio processing
```

## Directory Structure

```text
stt_tts/
├── app/
│   ├── controller.py      # Process manager (port 4208)
│   ├── tts_service.py     # TTS service (port 4210)
│   └── stt_service.py     # Continuous STT loop
├── vosk-model-en-us-0.22/ # Vosk speech recognition model
├── prompts/               # Voice prompt WAV files  
├── input/                 # STT utterance recordings
├── output/                # TTS generated audio files
└── tts.log               # Generation log
```

## Production Deployment

**Hardware Requirements**:

- CUDA-capable GPU (strongly recommended for TTS performance)
- Audio input/output devices accessible to host system
- Sufficient disk space for audio file storage

**Host System Requirements**:

- PulseAudio or equivalent audio system
- Python 3.8+ with audio device access permissions
- Manual service startup (not containerized)

**Service Startup**:

```bash
# Start controller (manages other services)
cd /path/to/stt_tts/app && python controller.py

# Or start services individually
python tts_service.py  # Port 4210
python stt_service.py  # Continuous loop
```

## Integration Notes

- **OpenWebUI**: Configure TTS endpoint to `http://localhost:4208/v1/audio/speech` for automatic agent speech
- **Brain Service**: STT sends transcriptions to brain API using "tts" model mode
- **Service Dependencies**: STT requires both TTS service and Brain API to be running
- **Audio Conflicts**: Only one STT instance should run to avoid microphone conflicts
