import whisper

model = whisper.load_model("medium")

def transcribe_wav(wav_path):
    result = model.transcribe(wav_path)
    return result['text']
