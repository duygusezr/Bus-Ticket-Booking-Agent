# 🎭 ELA: Gerçek Zamanlı 3D Avatar AI Companion

**ELA**, Google Gemini, ElevenLabs TTS, Whisper STT ve Three.js VRM teknolojilerini bir araya getiren gerçek zamanlı bir dijital arkadaştır. Duygu Sezer tarafından geliştirilmiştir.

---

## ✨ Özellikler

### 🤖 AI & Dil

- **Google Gemini 2.5 Flash** ile akıllı, hızı sohbet
- **Çoklu API Key Rotasyonu** — kota dolunca otomatik sıradaki key'e geçer
- **Türkçe / İngilizce** dil desteği — sekme bazlı dil seçimi
- Dil kuralı zorunlu: TR sekmesinde Türkçe, EN sekmesinde İngilizce cevap
- Kimlik koruması: ELA kendini asla "Google Gemini" veya "yapay zeka" olarak tanıtmaz

### 🎭 Duygu & Hareket Sistemi (ACT)

- LLM yanıtlarından `<|ACT:"emotion":{"name":"..."}|>` tokenları parse edilir
- 10 duygu: `happy`, `sad`, `angry`, `think`, `surprised`, `awkward`, `curious`, `question`, `relaxed`, `neutral`
- Duyguya göre kafa açısı, yüz ifadesi ve göz hareketi değişir
- Backend + Frontend çift katmanlı parse sistemi

### 🗣️ Ses Sistemi

- **ElevenLabs Scribe** ile yüksek kaliteli STT
- **ElevenLabs TTS** ile doğal seslendirme
- ACT tokenları TTS'e gönderilmeden temizlenir — sadece saf metin seslendirilir
- ElevenLabs rate limit (429) hatalarında kullanıcıya anlamlı mesaj

### 💾 Semantic Cache

- `sentence-transformers/all-MiniLM-L6-v2` ile anlam bazlı cache
- Diske kayıt — sunucu yeniden başlatılınca cache korunur
- Score 0.95+ eşiğinde HIT, ~0.005-0.010s yanıt süresi
- Maksimum 500 öğe, FIFO temizleme

### 🧠 Duygu Analizi

- **Öncelik 1:** LLM yanıtındaki ACT token (en güvenilir)
- **Öncelik 2:** `cardiffnlp/twitter-xlm-roberta-base-sentiment` — Türkçe dahil 100+ dil
- **Öncelik 3:** Fallback → neutral

### 👁️ 3D Avatar (Three.js + VRM)

- Nefes alma animasyonu (omuz, göğüs, boyun)
- Boşta kafa hareketi (idle)
- Göz kırpma (rastgele, çift kırpma dahil)
- Dudak senkronizasyonu (Web Audio API frekans analizi)
- Göz hareketi (yaw/pitch kontrolü)

---

## 🛠️ Kurulum

### Gereksinimler

- Python 3.11+
- Node.js (opsiyonel, sadece geliştirme için)
- Google Gemini API key
- ElevenLabs API key

### Backend Kurulumu

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Yapılandırma (.env)

```dotenv
ELEVENLABS_API_KEY=your_key
ELEVENLABS_VOICE_ID=your_voice_id
GOOGLE_API_KEY=your_primary_key
GOOGLE_API_KEYS=key1,key2,key3        # Çoklu key rotasyonu
GEMINI_CHAT_MODEL=gemini-2.5-flash
DEFAULT_LANG=tr
PORT=8001
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

> **Not:** System prompt artık `.env`'de değil, `backend/config.py` içinde tanımlıdır.

---

## 🚀 Çalıştırma

### Tek Komutla Başlat (Önerilen)

```powershell
# Proje ana dizininde
start.bat
```

`start.bat` otomatik olarak backend ve frontend'i başlatır, tarayıcıyı açar.

### Manuel Başlatma

**Backend:**

```powershell
cd backend
.\venv\Scripts\python.exe main.py
```

**Frontend:**

```powershell
# Proje ana dizininde (backend değil)
python -m http.server 3000
```

Tarayıcıda `http://localhost:3000` aç.

> ⚠️ Live Server kullanma — WebSocket bağlantısını koparır.

---

## 📂 Proje Yapısı

```text
avatar/
├── start.bat                     # Tek tıkla başlatma
├── index.html                    # Ana sayfa
├── main.js                       # Three.js, VRM, WebSocket, ACT parser
├── style.css                     # UI tasarımı
├── models/
│   └── character.vrm             # 3D avatar modeli
└── backend/
    ├── main.py                   # FastAPI uygulaması
    ├── config.py                 # Ayarlar + System Prompt
    ├── requirements.txt
    ├── .env                      # API key'ler
    ├── routers/
    │   ├── chat.py               # WebSocket + REST sohbet endpoint'leri
    │   ├── stt.py                # Ses → Metin endpoint'i
    │   └── tts.py                # Metin → Ses endpoint'i
    └── services/
        ├── llm_service.py        # Gemini entegrasyonu + key rotasyonu
        ├── tts_service.py        # ElevenLabs TTS
        ├── stt_service.py        # ElevenLabs Scribe STT
        ├── emotion_service_v2.py # ACT token + XLM-RoBERTa duygu analizi
        ├── semantic_cache_service.py  # Anlam bazlı cache
        └── memory_service.py     # Konuşma özeti (her 10 mesajda bir)
```

---

## ⚡ Performans

| Metrik | Süre |
| --- | --- |
| STT (ses → metin) | ~0.8–1.2s |
| Semantic Cache HIT | ~0.005–0.012s |
| LLM yanıt (stream) | ~1.5–3.5s |
| TTS (metin → ses) | ~1.2–1.6s |
| Duygu analizi (ACT token) | ~0.000s |
| Duygu analizi (transformer) | ~0.02–0.04s |

---

## 🔧 Mimari Notlar

- **WebSocket** üzerinden streaming — metin LLM'den gelirken ekranda görünür
- **API key rotasyonu** — 429 hatası alınınca otomatik sıradaki key'e geçer, maksimum `n_keys` deneme sonrası hata mesajı verir
- **Memory service** — her 10 mesajda bir Gemini ile özet üretir, RAM'de tutar
- **CORS** — sadece `.env`'deki `CORS_ORIGINS` listesindeki originlere izin verir
- **Lifespan** — FastAPI modern `lifespan` context manager kullanır (`@app.on_event` deprecated)

---

## 👩‍💻 Geliştirici

**Duygu Sezer** — ELA'nın yaratıcısı
