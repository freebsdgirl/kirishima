"""
Text-to-Speech (TTS) FastAPI Service using Chatterbox Turbo on CPU.

The service is English-only and uses WAV prompt files for voice conditioning.
It exposes a local playback endpoint plus an OpenAI-compatible speech endpoint.
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
from chatterbox.tts_turbo import ChatterboxTurboTTS

import sounddevice as sd
import soundfile as si

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Asynchronous context manager for loading the Chatterbox Turbo model during startup.

    The model is intentionally loaded on CPU so it does not compete with other
    local inference workloads for VRAM.

    Args:
        app (FastAPI): The FastAPI application instance being initialized.

    Yields:
        None: Provides a context for model initialization before the application starts.
    """
    global model
    print("[TTS] Loading Chatterbox Turbo model on CPU...")
    model = ChatterboxTurboTTS.from_pretrained(device="cpu")
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
DEFAULT_VOICE = "hasan"
DEFAULT_OPTIONS = {
    "temperature": 0.8,
    "exaggeration": 0.0,
    "cfg_weight": 0.0,
    "repetition_penalty": 1.2,
    "min_p": 0.0,
    "top_p": 0.95,
    "top_k": 1000,
    "norm_loudness": True,
    "gap": 0.5,
}

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

            wav = model.generate(
                sentence,
                audio_prompt_path=os.path.join(PROMPT_DIR, f"{DEFAULT_VOICE}.wav"),
                temperature=DEFAULT_OPTIONS["temperature"],
                exaggeration=DEFAULT_OPTIONS["exaggeration"],
                cfg_weight=DEFAULT_OPTIONS["cfg_weight"],
                repetition_penalty=DEFAULT_OPTIONS["repetition_penalty"],
                min_p=DEFAULT_OPTIONS["min_p"],
                top_p=DEFAULT_OPTIONS["top_p"],
                top_k=DEFAULT_OPTIONS["top_k"],
                norm_loudness=DEFAULT_OPTIONS["norm_loudness"],
            )

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


def text_to_speech_to_wav(text: str, voice: str = DEFAULT_VOICE, options: dict = None) -> str:
    """
    Convert text to a WAV audio file using a specified voice model.
    
    Args:
        text (str): The text to convert to speech.
        voice (str, optional): The voice prompt to use. Defaults to the service voice.
        options (dict, optional): Generation options for the TTS model. Defaults to None.
            Supported options:
            - temperature (float): Controls randomness of generation.
            - repetition_penalty (float): Penalizes token repetition.
            - min_p (float): Minimum token probability threshold.
            - top_p (float): Nucleus sampling threshold.
            - top_k (int): Maximum candidate tokens for sampling.
            - exaggeration (float): Kept for Turbo API compatibility.
            - cfg_weight (float): Kept for Turbo API compatibility.
            - norm_loudness (bool): Normalize prompt loudness before conditioning.
            - gap (float): Not used in generation, but can be used for playback timing.
    
    Returns:
        str: Path to the generated WAV audio file.
    """
    if options is None:
        options = DEFAULT_OPTIONS.copy()

    audio_prompt_path = os.path.join(PROMPT_DIR, f"{voice}.wav")
    uid = str(uuid.uuid4())
    filename = f"{OUTPUT_DIR}/{uid}.wav"

    wav = model.generate(
        text,
        audio_prompt_path=audio_prompt_path,
        temperature=options.get("temperature", DEFAULT_OPTIONS["temperature"]),
        exaggeration=options.get("exaggeration", DEFAULT_OPTIONS["exaggeration"]),
        cfg_weight=options.get("cfg_weight", DEFAULT_OPTIONS["cfg_weight"]),
        repetition_penalty=options.get("repetition_penalty", DEFAULT_OPTIONS["repetition_penalty"]),
        min_p=options.get("min_p", DEFAULT_OPTIONS["min_p"]),
        top_p=options.get("top_p", DEFAULT_OPTIONS["top_p"]),
        top_k=options.get("top_k", DEFAULT_OPTIONS["top_k"]),
        norm_loudness=options.get("norm_loudness", DEFAULT_OPTIONS["norm_loudness"]),
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
    print(data)

    text = data.get("text", "")
    voice = data.get("voice", DEFAULT_VOICE)
    wav_path = text_to_speech_to_wav(text, voice=voice)

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
            - model (str, optional): Optional model identifier. Legacy callers may
              still pass comma-separated key=value generation overrides here.

    Returns:
        StreamingResponse: Audio file streamed as a WAV response with appropriate headers

    Raises:
        HTTPException: If input text is missing or model options are invalid
    """
    data = await request.json()
    print(data)

    input_text = data.get("input", "")
    if not input_text:
        return {"error": "No input text provided"}
    voice = data.get("voice", DEFAULT_VOICE)
    model_name = data.get("model")

    options = DEFAULT_OPTIONS.copy()

    if isinstance(model_name, str) and "=" in model_name:
        try:
            options.update(dict(item.split('=') for item in model_name.split(',')))
        except Exception as e:
            return {"error": f"Invalid model options format: {e}"}

    try:
        options["temperature"] = float(options["temperature"])
        options["exaggeration"] = float(options["exaggeration"])
        options["cfg_weight"] = float(options["cfg_weight"])
        options["repetition_penalty"] = float(options["repetition_penalty"])
        options["min_p"] = float(options["min_p"])
        options["top_p"] = float(options["top_p"])
        options["top_k"] = int(options["top_k"])
        options["gap"] = float(options["gap"])
        if isinstance(options["norm_loudness"], str):
            options["norm_loudness"] = options["norm_loudness"].strip().lower() in {"1", "true", "yes", "on"}
        else:
            options["norm_loudness"] = bool(options["norm_loudness"])
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
    Get the supported TTS model identifiers.

    Returns:
        dict: A dictionary containing the available model identifiers and the
        active runtime device.
    """
    return {"models": ["chatterbox-turbo"], "default": "chatterbox-turbo", "device": "cpu"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("tts_service:app", host="0.0.0.0", port=4210)
