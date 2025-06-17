import torchaudio as ta
from chatterbox.tts import ChatterboxTTS

import sounddevice as sd
import soundfile as si

import time
from queue import Queue
import threading

import nltk
import uuid
import os

model = ChatterboxTTS.from_pretrained(device="cuda")

AUDIO_PROMPT_PATH = "./prompts/tony_stark_tts_prompt_2.wav"
OUTPUT_DIR = "./output"
os.makedirs(OUTPUT_DIR, exist_ok=True)
LOG_FILE = "./tts.log"

# Ensure punkt is downloaded for sentence tokenization
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

def play_wav(filename: str):
    """Play a WAV file using sounddevice."""
    try:
        data, samplerate = si.read(filename, dtype='float32')
        sd.play(data, samplerate)
        sd.wait()  # Wait until the sound has finished playing
    except Exception as e:
        print(f"[Error] Failed to play {filename}: {e}")


def text_to_speech(text: str, gap: float = 0.5):
    """
    Split text into sentences, generate audio for each, and play with a gap.
    Audio generation and playback are threaded for efficiency.
    """
    sentences = nltk.sent_tokenize(text)
    audio_queue = Queue()
    stop_signal = object()

    def audio_worker():
        for sentence in sentences:
            uid = str(uuid.uuid4())
            filename = f"{OUTPUT_DIR}/{uid}.wav"
            wav = model.generate(sentence, audio_prompt_path=AUDIO_PROMPT_PATH, temperature=1.1, exaggeration=0.7, cfg_weight=0.5)
            ta.save(filename, wav, model.sr)
            # Log the UUID and sentence
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