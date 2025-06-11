import sys
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import wave
import time
import os
from app import whisper_stt

# Set your model path here
MODEL_PATH = "/app/vosk-model-en-us-0.22"

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

def mic_test():
    """Record 5 seconds from the microphone and save to /app/output/mic_test.wav for testing input."""
    import numpy as np
    duration = 5  # seconds
    samplerate = 16000
    print("[Test] Recording 5 seconds from microphone for test...")
    try:
        recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16', device="hw:3,0")
        sd.wait()
        filename = "/app/output/mic_test.wav"
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(samplerate)
            wf.writeframes(recording.tobytes())
        print(f"[Test] Saved test recording to {filename}")
    except Exception as e:
        print(f"[Test] Error recording from microphone: {e}")

def transcribe_wav_file(filename):
    """Transcribe a wav file using Vosk (offline, not streaming)."""
    print(f"[Vosk] Transcribing file: {filename}")
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, 16000)
    with wave.open(filename, "rb") as wf:
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            recognizer.AcceptWaveform(data)
        result = recognizer.FinalResult()
        print(f"[Vosk] Transcription result: {result}")

def main():
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, 16000)

    # Try to use 'default', but if it fails, fall back to the first available input device
    try:
        with sd.RawInputStream(device="hw:3,0", samplerate=16000, blocksize=4096, dtype='int16',
                               channels=1, callback=callback):
            _main_loop(recognizer)
    except Exception as e:
        print(f"[Vosk] Could not open 'default' device: {e}")
        # Try to find the first available input device
        devices = sd.query_devices()
        input_indices = [i for i, d in enumerate(devices) if d['max_input_channels'] > 0]
        if not input_indices:
            print("[Vosk] No input devices available. Exiting.")
            return
        print(f"[Vosk] Trying input device index {input_indices[0]}: {devices[input_indices[0]]['name']}")
        with sd.RawInputStream(device=input_indices[0], samplerate=16000, blocksize=8000, dtype='int16',
                               channels=1, callback=callback):
            _main_loop(recognizer)

def _main_loop(recognizer):
    utterance_audio = b''
    file_counter = 1
    print("Listening for wake word 'Kirishima'... Press Ctrl+C to stop.")
    in_conversation = False
    last_utterance_time = 0
    CONVO_TIMEOUT = 30  # seconds
    while True:
        data = q.get()
        utterance_audio += data
        if recognizer.AcceptWaveform(data):
            result = eval(recognizer.Result())
            text = result.get('text', '').strip()
            if text:
                print("[Vosk] You said:", text)
                filename = f"/app/output/utterance_{int(time.time())}_{file_counter}.wav"
                save_wav(filename, utterance_audio)
                file_counter += 1
                now = time.time()
                if not in_conversation:
                    if text.lower().startswith("charisma") or text.lower().startswith("karishma"):
                        in_conversation = True
                        last_utterance_time = now
                else:
                    last_utterance_time = now
            utterance_audio = b''
        # Conversation mode timeout
        if in_conversation and (time.time() - last_utterance_time > CONVO_TIMEOUT):
            in_conversation = False

if __name__ == "__main__":
    import os
    if os.environ.get("MIC_TEST") == "1":
        mic_test()
    elif os.environ.get("VOSK_FILE_TEST") == "1":
        transcribe_wav_file("/app/output/mic_test.wav")
    else:
        try:
            main()
        except KeyboardInterrupt:
            print("\nExiting.")
        except Exception as e:
            print(str(e))