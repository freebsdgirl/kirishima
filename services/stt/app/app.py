from app import vosk_stt
import os

if __name__ == "__main__":
    if os.environ.get("MIC_TEST") == "1":
        vosk_stt.mic_test()
    elif os.environ.get("VOSK_FILE_TEST") == "1":
        vosk_stt.transcribe_wav_file("/app/output/mic_test.wav")
    else:
        vosk_stt.main()
