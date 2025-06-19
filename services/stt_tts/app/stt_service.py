"""
stt_service.py
A speech-to-text (STT) and text-to-speech (TTS) service integrating Vosk, Whisper, and external LLM/TTS APIs.
This module provides a main loop for real-time speech recognition and conversational interaction. It listens to microphone input, detects utterances using Vosk, transcribes them with Whisper, sends the transcription to a language model (LLM) for a response, and plays back the response using a TTS service. Audio files are managed for each utterance and response, with optional debugging controls for file retention.
Key Components:
- Audio input and streaming using sounddevice.
- Speech recognition using Vosk for utterance detection.
- Transcription using OpenAI Whisper.
- Conversational response via HTTP API to an LLM.
- Text-to-speech synthesis via HTTP API and playback.
- Temporary audio file management and cleanup.
- Configurable via environment variables and constants.
Intended for use as a standalone service or as part of a larger voice assistant system.
"""
import sys
import os
import time
import queue

import requests

import sounddevice as sd
import wave

from vosk import Model, KaldiRecognizer
import whisper

LLM_URL = "http://localhost:4200/v1/chat/completions"
LLM_MODEL = "tts"
LLM_TIMEOUT = 60
TTS_URL = "http://localhost:4210/v1/audio/speak"

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vosk-model-en-us-0.22")
RECORDING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "input")
os.makedirs(RECORDING_DIR, exist_ok=True)

q = queue.Queue()

stream = None
recognizer = None


def callback(indata, frames, time, status):
    """
    Callback function for audio input stream processing.
    
    This function is used with sounddevice to handle incoming audio data from a recording stream.
    It captures audio input, converts it to bytes, and puts the data into a shared queue for further processing.
    
    Args:
        indata (numpy.ndarray): Input audio data buffer
        frames (int): Number of frames in the input data
        time (dict): Timing information for the callback
        status (sounddevice.CallbackFlags, optional): Status flags indicating any stream errors
    
    Raises:
        Prints any status errors to standard error stream
    """
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))


def save_wav(filename, audio_bytes):
    """
    Saves raw audio bytes as a WAV file with specified parameters.

    Args:
        filename (str): The path where the WAV file will be saved.
        audio_bytes (bytes): The raw audio data to write to the file.

    The WAV file will be saved with:
        - 1 audio channel (mono)
        - 16-bit sample width
        - 16,000 Hz sample rate
    """
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(audio_bytes)


def main_loop():
    """
    Main loop for speech-to-text (STT) and text-to-speech (TTS) service.

    Continuously listens for audio data from a queue, processes speech recognition using Vosk,
    transcribes the recognized utterance with Whisper, sends the transcription to a language model (LLM),
    and plays back the LLM's response using a TTS service. Handles audio file saving, error handling,
    and microphone stream management for seamless interaction.

    Workflow:
        1. Collects audio data from the queue.
        2. Uses Vosk to detect end of utterance and extract recognized text.
        3. If the utterance is sufficiently long, saves the audio to a WAV file.
        4. Transcribes the WAV file using Whisper.
        5. Sends the transcription to an LLM and retrieves the assistant's response.
        6. Sends the response to a TTS service, saves and plays back the resulting audio.
        7. Manages microphone stream state during TTS playback.
        8. Cleans up temporary files unless in DEBUG mode.
        9. Handles errors gracefully and resumes listening after each cycle.

    Globals:
        stream: Microphone stream object for audio input.
        recognizer: Vosk recognizer object for speech recognition.

    Environment Variables:
        DEBUG: If set, disables deletion of temporary audio files.

    Requires:
        - Vosk for speech recognition
        - Whisper for transcription
        - Requests for HTTP requests to LLM and TTS services
        - Soundfile and sounddevice for audio playback
        - Properly initialized global variables and constants (e.g., RECORDING_DIR, LLM_MODEL, LLM_URL, etc.)
    """
    global stream, recognizer
    utterance_audio = b''
    file_counter = 1
    DEBUG = os.environ.get("DEBUG", "0") in ("1", "true", "True")

    while True:
        data = q.get()
        utterance_audio += data

        if recognizer.AcceptWaveform(data):
            result = eval(recognizer.Result())
            text = result.get('text', '').strip()

            if text and len(text.split()) > 2:
                print("[Vosk] You said:", text)
                filename = f"{RECORDING_DIR}/utterance_{int(time.time())}_{file_counter}.wav"
                error_occurred = False

                try:
                    stream.stop()  # Stop listening
                    save_wav(filename, utterance_audio)
                    file_counter += 1
                    whisper_result = transcribe_wav(filename)
                    print(f"[Whisper] Transcription: {whisper_result}")

                except Exception as e:
                    print(f"[Vosk/Whisper] Error saving or transcribing wav file: {e}")
                    error_occurred = True

                if not error_occurred:
                    assistant_content = None

                    try:
                        payload = {
                            "model": LLM_MODEL,
                            "messages": [
                                {"role": "user", "content": whisper_result}
                            ]
                        }
                        response = requests.post(
                            LLM_URL,
                            json=payload,
                            timeout=LLM_TIMEOUT
                        )
                        resp_json = response.json()
                        assistant_content = resp_json["choices"][0]["message"]["content"]
                        print(f"[TTS] Response: {assistant_content}")

                    except Exception as e:
                        print(f"[TTS] Error sending to /chat/completions or parsing response: {e}")

                    if assistant_content:
                        try:
                            if stream:
                                print("[STT] Pausing microphone stream for TTS playback...")
                                stream.stop()
                            tts_payload = {"input": assistant_content}
                            tts_resp = requests.post(TTS_URL, json=tts_payload, timeout=60)

                            if tts_resp.status_code == 200:
                                tts_wav_path = os.path.join(RECORDING_DIR, f"tts_{int(time.time())}_{file_counter}.wav")
                                with open(tts_wav_path, "wb") as f:
                                    f.write(tts_resp.content)
                                print(f"[TTS] Playing TTS audio: {tts_wav_path}")
                                import soundfile as sf
                                import sounddevice as sd
                                data, samplerate = sf.read(tts_wav_path, dtype='float32')
                                sd.play(data, samplerate)
                                sd.wait()

                            else:
                                print(f"[TTS] Error: TTS service returned status {tts_resp.status_code}")

                        except Exception as e:
                            print(f"[TTS] Error during TTS playback: {e}")

                        finally:
                            # Always resume the stream after TTS attempt
                            if stream:
                                print("[STT] Resuming microphone stream after TTS playback...")
                                try:
                                    stream.start()
                                except Exception as e:
                                    print(f"[STT] Error resuming stream: {e}")

                    if not DEBUG:
                        try:
                            os.remove(filename)
                        except Exception as e:
                            print(f"[Cleanup] Error deleting {filename}: {e}")

                # Reset for next utterance
                utterance_audio = b''
                if stream and not stream.active:
                    try:
                        stream.start()
                    except Exception as e:
                        print(f"[STT] Error starting stream: {e}")

                print("Listening for speech... Press Ctrl+C to stop.")

            else:
                utterance_audio = b''


def load_models_and_stream():
    """
    Initializes and loads the Vosk and Whisper speech recognition models, sets up the microphone audio stream, 
    and starts listening for audio input.

    Returns:
        whisper_model: The loaded Whisper model instance.

    Side Effects:
        - Sets up and starts a global microphone audio stream (`stream`) using sounddevice.
        - Initializes a global KaldiRecognizer (`recognizer`) with the Vosk model.
        - Prints status messages to the console.

    Raises:
        Any exceptions raised by the underlying model loading or audio stream setup will propagate.
    """
    global stream, recognizer
    print(f"[Startup] Using Vosk model: {MODEL_PATH}")
    print("[Startup] Loading Whisper model...")
    whisper_model = whisper.load_model("medium")
    print("[Startup] Whisper model loaded.")
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, 16000)
    stream = sd.RawInputStream(
        samplerate=16000,
        blocksize=4096,
        dtype='int16',
        channels=1,
        callback=callback
    )
    stream.start()
    print("[STT] Microphone stream started. Listening...")
    return whisper_model


def transcribe_wav(wav_path):
    """
    Transcribes speech from a WAV audio file to text using the configured Whisper model.

    Args:
        wav_path (str): The file path to the WAV audio file to be transcribed.

    Returns:
        str: The transcribed text from the audio file.
    """
    result = transcribe_wav.whisper_model.transcribe(wav_path)
    return result['text']


if __name__ == "__main__":
    transcribe_wav.whisper_model = load_models_and_stream()
    main_loop()