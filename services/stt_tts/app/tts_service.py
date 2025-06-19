"""
Text-to-Speech (TTS) FastAPI Service using ChatterboxTTS
This module provides a FastAPI-based web service for converting text to speech using the ChatterboxTTS model.
It supports streaming audio responses, configurable voice prompts, and model parameters for speech synthesis.
The service includes endpoints compatible with OpenAI's TTS API, as well as endpoints for listing available voices and model configurations.
Features:
- Loads the ChatterboxTTS model on application startup for efficient inference.
- Converts input text into speech audio (WAV format) using customizable voice prompts and generation parameters.
- Streams generated audio files to clients and optionally plays them on the server.
- Provides endpoints for listing available voice prompts and model configurations.
- Logs generated audio files and associated text for traceability.
Endpoints:
- POST /tts/speak: Converts text to speech, streams the audio file, and plays it on the server.
- POST /v1/audio/speech: OpenAI-compatible endpoint for TTS with configurable voice and model options.
- GET /v1/audio/voices: Lists available voice prompts.
- GET /v1/audio/models: Lists predefined model configurations.
Dependencies:
- FastAPI, torchaudio, chatterbox.tts, nltk, sounddevice, soundfile, uvicorn
Directory Structure:
- Output audio files and logs are stored in directories relative to the parent of this script's directory.
- Voice prompts are expected as WAV files in the 'prompts' directory.
Usage:
- Run as a standalone service with `python tts_service.py` or via Uvicorn.
- Configure voice prompts and model parameters as needed for different speech synthesis styles.
"""
import os
import time
import uuid

from queue import Queue
import threading

import mimetypes
import glob

import nltk

import torchaudio as ta
from chatterbox.tts import ChatterboxTTS

import sounddevice as sd
import soundfile as si

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Asynchronous context manager for loading the ChatterboxTTS model during FastAPI application startup.

    This lifespan manager handles the global initialization of the TTS model, ensuring it is loaded 
    into memory before the application begins serving requests. The model is loaded onto the CUDA device 
    for improved performance.

    Args:
        app (FastAPI): The FastAPI application instance being initialized.

    Yields:
        None: Provides a context for model initialization before the application starts.
    """
    global model
    print("[TTS] Loading ChatterboxTTS model...")
    model = ChatterboxTTS.from_pretrained(device="cuda")
    print("[TTS] Model loaded.")
    yield


app = FastAPI(lifespan=lifespan)

model = None  # Will be loaded on startup
# Set output and prompt directories relative to the parent of this script's directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
PROMPT_DIR = os.path.join(BASE_DIR, "prompts")
os.makedirs(OUTPUT_DIR, exist_ok=True)
LOG_FILE = os.path.join(BASE_DIR, "tts.log")

# Ensure punkt and punkt_tab are downloaded for sentence tokenization
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab')


def play_wav(filename: str):
    """
    Play a WAV audio file using sounddevice.
    
    Args:
        filename (str): Path to the WAV audio file to be played.
    
    Raises:
        Exception: If there is an error reading or playing the audio file.
    """
    try:
        data, samplerate = si.read(filename, dtype='float32')
        sd.play(data, samplerate)
        sd.wait()
    except Exception as e:
        print(f"[Error] Failed to play {filename}: {e}")


def text_to_speech(text: str, gap: float = 0.5):
    """
    Convert text to speech by generating audio for each sentence and playing them sequentially.
    
    This function breaks down the input text into sentences, generates audio for each sentence
    using a TTS model, and plays the audio with a configurable gap between sentences.
    
    Args:
        text (str): The text to convert to speech.
        gap (float, optional): Time delay between playing each sentence. Defaults to 0.5 seconds.
    """
    sentences = nltk.sent_tokenize(text)
    audio_queue = Queue()
    stop_signal = object()

    def audio_worker():
        """
        Processes a list of sentences by generating audio files for each sentence using a TTS model,
        saving the audio files to disk, logging the generated file information, and placing the file
        paths into an audio queue for further processing. Signals completion by placing a stop signal
        in the queue.

        Actions:
            - Writes audio files to OUTPUT_DIR.
            - Appends log entries to LOG_FILE.
            - Puts generated audio file paths and a stop signal into audio_queue.
        """
        for sentence in sentences:
            uid = str(uuid.uuid4())
            filename = f"{OUTPUT_DIR}/{uid}.wav"

            wav = model.generate(sentence, audio_prompt_path=os.path.join(PROMPT_DIR, "tony_stark_2.wav"), temperature=1.1, exaggeration=0.7, cfg_weight=0.5)

            ta.save(filename, wav, model.sr)

            with open(LOG_FILE, "a") as logf:
                logf.write(f"{uid}: {sentence}\n")

            audio_queue.put(filename)
        audio_queue.put(stop_signal)

    threading.Thread(target=audio_worker, daemon=True).start()

    while True:
        filename = audio_queue.get()
        if filename is stop_signal:
            break

        play_wav(filename)
        time.sleep(gap)


def text_to_speech_to_wav(text: str, voice: str = "tony_stark_2", options: dict = None) -> str:
    """
    Convert text to a WAV audio file using a specified voice model.
    
    Args:
        text (str): The text to convert to speech.
        voice (str, optional): The voice prompt to use. Defaults to "tony_stark_2".
        options (dict, optional): Generation options for the TTS model. Defaults to None.
            Supported options:
            - temperature (float): Controls randomness of generation. Defaults to 1.1.
            - exaggeration (float): Controls speech style. Defaults to 0.7.
            - cfg_weight (float): Classifier-free guidance weight. Defaults to 0.5.
            - gap (float): Not used in generation, but can be used for playback timing.
    
    Returns:
        str: Path to the generated WAV audio file.
    """
    if options is None:
        options = {
            "temperature": 1.1,
            "exaggeration": 0.7,
            "cfg_weight": 0.5,
            "gap": 0.5
        }

    audio_prompt_path = os.path.join(PROMPT_DIR, f"{voice}.wav")
    uid = str(uuid.uuid4())
    filename = f"{OUTPUT_DIR}/{uid}.wav"

    wav = model.generate(
        text,
        audio_prompt_path=audio_prompt_path,
        temperature=options.get("temperature", 1.1),
        exaggeration=options.get("exaggeration", 0.7),
        cfg_weight=options.get("cfg_weight", 0.5)
    )

    ta.save(filename, wav, model.sr)

    with open(LOG_FILE, "a") as logf:
        logf.write(f"{uid}: {text}\n")

    return filename


@app.post("/tts/speak")
async def tts_speak_endpoint(request: Request):
    """
    Endpoint for text-to-speech conversion that generates and streams an audio file.

    Args:
        request (Request): JSON request containing the text to convert to speech.
            Expected format: {"text": "string to convert"}

    Returns:
        StreamingResponse: A streaming response with the generated WAV audio file,
        which is also played synchronously on the server.

    Raises:
        Any exceptions during audio generation or playback will be printed to console.
    """
    data = await request.json()

    text = data.get("text", "")
    wav_path = text_to_speech_to_wav(text)

    def iterfile_and_play():
        # Play audio while streaming it
        try:
            with open(wav_path, mode="rb") as file_like:
                data = file_like.read()

                # Play the audio synchronously
                try:
                    audio_data, samplerate = si.read(wav_path, dtype='float32')
                    sd.play(audio_data, samplerate)
                    sd.wait()  # Block until playback is finished
                except Exception as e:
                    print(f"[TTS] Error playing audio: {e}")
                yield data
        finally:
            pass  # Optionally delete wav_path here if desired

    content_type = mimetypes.guess_type(wav_path)[0] or "audio/wav"

    return StreamingResponse(iterfile_and_play(), media_type=content_type, headers={
        "Content-Disposition": f"attachment; filename=output.wav"
    })


@app.post("/v1/audio/speech")
async def openai_compatible_tts(request: Request):
    """
    OpenAI-compatible text-to-speech endpoint that generates audio from input text.

    Args:
        request (Request): HTTP request containing TTS parameters
            - input (str): Text to convert to speech
            - voice (str, optional): Voice prompt to use for generation
            - model (str, optional): Model configuration with generation parameters

    Returns:
        StreamingResponse: Audio file streamed as a WAV response with appropriate headers

    Raises:
        HTTPException: If input text is missing or model options are invalid
    """
    data = await request.json()

    input_text = data.get("input", "")
    if not input_text:
        return {"error": "No input text provided"}
    voice = data.get("voice", "tony_stark_2")
    model = data.get("model", "temperature=1.1,exaggeration=0.7,cfg_weight=0.5,gap=0.5")

    options = {
        "temperature": 1.1,
        "exaggeration": 0.7,
        "cfg_weight": 0.5,
        "gap": 0.5
    }

    if model:
        try:
            options.update(dict(item.split('=') for item in model.split(',')))
        except Exception as e:
            return {"error": f"Invalid model options format: {e}"}

    try:
        options["temperature"] = float(options["temperature"])
        options["exaggeration"] = float(options["exaggeration"])
        options["cfg_weight"] = float(options["cfg_weight"])
        options["gap"] = float(options["gap"])
    except ValueError as e:
        return {"error": f"Invalid numeric value in model options: {e}"}

    wav_path = text_to_speech_to_wav(input_text, voice=voice, options=options)

    def iterfile():
        with open(wav_path, mode="rb") as file_like:
            yield from file_like

    content_type = mimetypes.guess_type(wav_path)[0] or "audio/wav"

    return StreamingResponse(iterfile(), media_type=content_type, headers={
        "Content-Disposition": f"attachment; filename=output.wav"
    })


@app.get("/v1/audio/voices")
def list_voices():
    """
    Get a list of available TTS voice prompts.
    
    Returns:
        dict: A dictionary containing a list of voice names extracted from WAV files 
        in the predefined prompt directory.
    """
    prompt_files = glob.glob(os.path.join(PROMPT_DIR, "*.wav"))
    voices = [os.path.splitext(os.path.basename(f))[0] for f in prompt_files]
    return {"voices": voices}


@app.get("/v1/audio/models")
def list_models():
    """
    Get a list of predefined TTS model configurations.

    Returns:
        dict: A dictionary containing a list of model configurations with different 
        temperature, exaggeration, cfg_weight, and gap parameters for text-to-speech generation.
    """
    models = [
        "temperature=1.1,exaggeration=0.7,cfg_weight=0.5,gap=0.5",
        "temperature=1.2,exaggeration=0.7,cfg_weight=0.5,gap=0.5",
        "temperature=0.7,exaggeration=0.5,cfg_weight=0.5,gap=0.5",
    ]
    return {"models": models}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("tts_service:app", host="0.0.0.0", port=4210)
