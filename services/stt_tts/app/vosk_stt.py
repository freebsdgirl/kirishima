from app.whisper_stt import transcribe_wav
from app.chatterbox_tts import text_to_speech

from vosk import Model, KaldiRecognizer
import sounddevice as sd
import wave

import sys
import os
import time
import queue

import requests

MODEL_PATH = "./vosk-model-en-us-0.22"

if not os.path.exists(MODEL_PATH):
    print(f"[Vosk] MODEL_PATH does not exist: {MODEL_PATH}")
    sys.exit(1)

RECORDING_DIR = "./input"
os.makedirs(RECORDING_DIR, exist_ok=True)

LLM_URL = "http://localhost:4200/v1/chat/completions"
LLM_MODEL = "tts"
LLM_TIMEOUT = 60


q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    # Debug print removed for normal operation
    q.put(bytes(indata))

def save_wav(filename, audio_bytes):
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(16000)
        wf.writeframes(audio_bytes)

def main():
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, 16000)

    def start_stream(device=None):
        return sd.RawInputStream(
            samplerate=16000,
            blocksize=4096,
            dtype='int16',
            channels=1,
            callback=callback,
            device=device
        )

    # Try to use 'default', but if it fails, fall back to the first available input device
    try:
        stream = start_stream()
        stream.start()
        device_info = sd.query_devices(stream.device)
        print(f"Listening for speech on device: {device_info['name']} (Press Ctrl+C to stop.)")
        _main_loop(recognizer, stream)
    except Exception as e:
        print(f"[Vosk] Could not open 'default' device: {e}")
        devices = sd.query_devices()
        input_indices = [i for i, d in enumerate(devices) if d['max_input_channels'] > 0]
        if not input_indices:
            print("[Vosk] No input devices available. Exiting.")
            return
        print(f"[Vosk] Trying input device index {input_indices[0]}: {devices[input_indices[0]]['name']}")
        stream = start_stream(device=input_indices[0])
        stream.start()
        device_info = sd.query_devices(stream.device)
        print(f"Listening for speech on device: {device_info['name']} (Press Ctrl+C to stop.)")
        _main_loop(recognizer, stream)


def _main_loop(recognizer, stream):
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
                try:
                    stream.stop()  # Stop listening
                    save_wav(filename, utterance_audio)
                    file_counter += 1
                    # Send to Whisper for transcription
                    try:
                        whisper_result = transcribe_wav(filename)
                        print(f"[Whisper] Transcription: {whisper_result}")
                        # Send to OpenAI-style /chat/completions endpoint
                        payload = {
                            "model": LLM_MODEL,
                            "messages": [
                                {"role": "user", "content": whisper_result}
                            ]
                        }
                        try:
                            response = requests.post(
                                LLM_URL,
                                json=payload,
                                timeout=LLM_TIMEOUT
                            )
                            # Parse and play TTS response
                            try:
                                resp_json = response.json()
                                assistant_content = resp_json["choices"][0]["message"]["content"]
                                print(f"[TTS] Response: {assistant_content}")
                                text_to_speech(assistant_content)
                            except Exception as e:
                                print(f"[TTS] Error parsing or playing TTS response: {e}")
                        except Exception as e:
                            print(f"[TTS] Error sending to /chat/completions: {e}")
                    except Exception as e:
                        print(f"[Whisper] Error: {e}")
                    # Delete the wav file unless DEBUG is enabled
                    if not DEBUG:
                        try:
                            os.remove(filename)
                        except Exception as e:
                            print(f"[Cleanup] Error deleting {filename}: {e}")
                except Exception as e:
                    print(f"[Vosk] Error saving wav file: {e}")
                utterance_audio = b''
                stream.start()  # Resume listening
                print("Listening for speech... Press Ctrl+C to stop.")
            else:
                utterance_audio = b''

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting.")
    except Exception as e:
        print(str(e))