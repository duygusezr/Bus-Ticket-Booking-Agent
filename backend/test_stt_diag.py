import io
import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

# .env yukle
load_dotenv('.env', override=True)
api_key = os.getenv('ELEVENLABS_API_KEY')
_key_preview = (api_key[:10] + "...") if api_key else "(ayarlanmamis)"
print(f"Test anahtari: {_key_preview}")

client = ElevenLabs(api_key=api_key or "")

def test_stt():
    try:
        # Sahte bir sessiz ses dosyasi (WAV formatinda cok kucuk veri)
        # 44 byte'lik bos bir WAV basligi + sessizlik
        fake_wav = b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
        audio_file = io.BytesIO(fake_wav)
        
        print("ElevenLabs Scribe STT testi basliyor...")
        resp = client.speech_to_text.convert(
            file=("test.wav", audio_file, "audio/wav"),
            model_id="scribe_v1",
        )
        transcript = str(getattr(resp, "text", "") or getattr(resp, "transcript", "") or "")
        print("Basarili! Transkripsiyon sonucu:", transcript)
    except Exception as e:
        print("\n!!! STT HATASI ALINDI !!!")
        print(f"Hata detayi: {str(e)}")
        if "401" in str(e) or "invalid_api_key" in str(e):
            print("Teshis: Bu anahtar STT (Scribe) servisi icin yetkili degil veya gecersiz.")
        else:
            print("Teshis: Bilinmeyen bir sunucu hatasi.")

if __name__ == "__main__":
    test_stt()
