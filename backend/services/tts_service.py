import base64
import tempfile
import os
import edge_tts
from elevenlabs.client import ElevenLabs
from config import settings

def get_eleven_client():
    """Anahtari her seferinde guncel ayarlardan alarak client olusturur."""
    if settings.ELEVENLABS_API_KEY and "your_" not in settings.ELEVENLABS_API_KEY.lower():
        return ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
    return None

async def generate_tts(text: str, lang: str = None, voice: str = "default") -> str:
    """
    Gelen metni sese dönüştürür.
    Birincil: ElevenLabs (SDK ile)
    Yedek: Microsoft Edge TTS (Ücretsiz)
    """
    if not text or not text.strip():
        return ""

    try:
        lang = lang or settings.DEFAULT_LANG
        import re
        # ACT ve DELAY tokenlarını temizle (seslendirme için)
        clean_text = re.sub(r'<\|ACT:.*?\|>', '', text)
        clean_text = re.sub(r'<\|DELAY:.*?\|>', '', clean_text)
        clean_text = clean_text.strip()
        
        # ElevenLabs SDK Kullanımı (Birincil)
        client = get_eleven_client()
        if client:
            try:
                print(f"ElevenLabs SDK (SDK) çağrılıyor... (Metin boyutu: {len(clean_text)})")
                voice_id = settings.ELEVENLABS_VOICE_ID or "EXAVITQu4vr4xnSDxMaL"
                
                # SDK ile Text-to-Speech dönüşümü
                # Not: convert() fonksiyonu bir iterator döner, biz tüm içeriği tek seferde alacağız.
                audio_iterator = client.text_to_speech.convert(
                    text=clean_text,
                    voice_id=voice_id,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )
                
                # Bütün ses verisini birleştir
                audio_content = b"".join(audio_iterator)
                
                if not audio_content:
                    raise Exception("ElevenLabs boş ses verisi döndürdü.")
                    
                return base64.b64encode(audio_content).decode("utf-8")
                
            except Exception as e:
                error_msg = str(e)
                print(f"ElevenLabs SDK Hatası: {error_msg}")
                if "invalid_api_key" in error_msg.lower() or "permission" in error_msg.lower():
                    print("KRİTİK: ElevenLabs API anahtarınız hatalı! Lütfen .env dosyasını kontrol edin.")
                print("Edge-TTS'e dönülüyor...")
        
        # Edge-TTS (Yedek)
        print(f"Edge-TTS çağrılıyor... (Dil: {lang})")
        edge_voice = "tr-TR-EmelNeural"
        if lang.startswith("en"):
            edge_voice = "en-US-JennyNeural"
            
        communicate = edge_tts.Communicate(clean_text, edge_voice)
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = temp_file.name
            
        try:
            await communicate.save(temp_path)
            with open(temp_path, "rb") as audio_file:
                audio_data = audio_file.read()
                return base64.b64encode(audio_data).decode("utf-8")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        print(f"KRİTİK TTS HATASI: {str(e)}")
        raise Exception(f"TTS Motoru Hatası: {str(e)}")
