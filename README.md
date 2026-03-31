# 🚌 Ela — Yapay Zekâ Destekli Otobüs Bileti Rezervasyon Asistanı

> **Sesli ve yazılı etkileşim destekli, 3D avatarlı, uçtan uca akıllı otobüs bileti rezervasyon sistemi.**

---

## 📌 Projenin Amacı

Bu proje, geleneksel web tabanlı otobüs bileti satın alma sürecini **yapay zekâ destekli bir konuşma arayüzüne** dönüştürmeyi amaçlamaktadır. Kullanıcı, ekrandaki 3D avatar (Ela) ile Türkçe sesli veya yazılı olarak etkileşime girerek menülere, formlara veya karmaşık filtre panellerine ihtiyaç duymadan bilet rezervasyonu yapabilir.

### Çözmek İstediğimiz Problem

Mevcut otobüs bileti platformlarında kullanıcı, güzergah seçimi → tarih seçimi → koltuk seçimi → yolcu bilgileri → ödeme gibi çok adımlı bir form sürecinden geçmek zorundadır. Bu süreç özellikle yaşlı kullanıcılar, teknolojiye uzak bireyler veya hareket halindeki kullanıcılar için zorlu olabilmektedir.

**Ela**, bu süreci doğal bir sohbete dönüştürür:

- *"Yarın Ankara'dan İstanbul'a gitmek istiyorum"* → Sistem uygun seferleri otomatik bulur
- *"5 numaralı koltuğu istiyorum"* → Koltuk uygunluğunu kontrol eder
- *"TC'm 12345678910"* → Algoritmik doğrulamayı anında yapar
- Tüm bilgiler toplandığında özet sunar ve onay sonrası rezervasyonu tamamlar

---

## 🏗️ Sistem Mimarisi

```text
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Vanilla JS)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐│
│  │ Chat Panel   │  │  3D Avatar   │  │  WebSocket İstemcisi   ││
│  │ (Metin/Ses)  │  │  (Three.js + │  │  (Streaming Yanıt)     ││
│  │              │  │   VRM 1.0)   │  │                        ││
│  └──────┬───────┘  └──────┬───────┘  └───────────┬────────────┘│
│         │                 │                      │              │
└─────────┼─────────────────┼──────────────────────┼──────────────┘
          │ REST / WS       │ Emotion Data         │ Audio Stream
          ▼                 ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI + Uvicorn)                  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Chat Router                            │   │
│  │  REST: POST /api/chat    │    WebSocket: /ws/chat         │   │
│  │  (Tek seferlik yanıt)    │    (Streaming yanıt)           │   │
│  └─────────┬────────────────┴──────────────┬─────────────────┘   │
│            │                               │                     │
│  ┌─────────▼───────────────────────────────▼─────────────────┐   │
│  │                    LLM Service (Gemini 2.5 Flash)         │   │
│  │         Konuşma yönetimi + Function Calling               │   │
│  └─────────┬─────────────────────────────────────────────────┘   │
│            │                                                     │
│  ┌─────────▼─────────────────────────────────────────────────┐   │
│  │                      Tool Functions                        │   │
│  │  get_bus_trips │ validate_seat │ validate_tc │ validate_   │   │
│  │                │ _selection    │ _number     │ phone/email │   │
│  │                │               │             │             │   │
│  │  make_reservation                                          │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌───────────────┐ ┌───────────────┐ ┌─────────────────────┐    │
│  │  STT Service  │ │  TTS Service  │ │  Emotion Service    │    │
│  │  (ElevenLabs  │ │  (ElevenLabs  │ │  (XLM-RoBERTa +    │    │
│  │   Scribe v1)  │ │   + Edge-TTS) │ │   ACT Token Parse) │    │
│  └───────────────┘ └───────────────┘ └─────────────────────┘    │
│                                                                  │
│  ┌───────────────┐ ┌───────────────────────────────────────┐    │
│  │Memory Service │ │       Semantic Cache Service           │    │
│  │(Gemini Özet)  │ │  (all-MiniLM-L6-v2 + Cosine Sim.)    │    │
│  └───────────────┘ └───────────────────────────────────────┘    │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │              Veritabanı Katmanı (SQLite)                   │   │
│  │  bilet_sistemi.db (Seferler)  │  rezervasyonlar.db (PNR)  │   │
│  └───────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🤖 Kullanılan Yapay Zekâ Modelleri ve Seçim Gerekçeleri

### 1. Google Gemini 2.5 Flash — Ana Konuşma Motoru (LLM)

| Özellik | Detay |
| --- | --- |
| **Model** | `gemini-2.5-flash` |
| **Kullanım Amacı** | Konuşma yönetimi, doğal dil anlama, araç çağırma (Function Calling) |
| **Erişim** | Google GenAI SDK (`google-genai`) |

**Neden Gemini 2.5 Flash?**

- **Native Function Calling (Araç Çağırma) Desteği:** Gemini, araç tanımlarını doğrudan model konfigürasyonuna alır ve hangi aracı ne zaman çağıracağına kendi karar verir. Bu, GPT tabanlı modellerdeki gibi harici bir orkestrasyon katmanına (LangChain Agent vb.) ihtiyaç duymadan, tek model üzerinden hem doğal dil üretimi hem de iş mantığı yürütmeyi mümkün kılar.  
- **Hız/Maliyet Optimizasyonu:** `Flash` varyantı, `Pro` modeline kıyasla ~5-10x daha düşük gecikme süresi sunar. Rezervasyon gibi çok turlu (multi-turn) bir diyalogda her tur için LLM çağrısı yapıldığından, düşük gecikme doğrudan kullanıcı deneyimini iyileştirir.  
- **Çok Turlu Konuşma (Multi-Turn Chat) Yetkinliği:** Gemini'nin chat API'si, konuşma geçmişini (`history`) doğal olarak alıp bağlamı korumasını sağlar. Bu sayede kullanıcının daha önce verdiği bilgiler (güzergah, tarih vb.) sonraki adımlarda tekrar sorulmaz.  
- **Türkçe Dil Performansı:** Gemini modelleri, Türkçe üzerinde GPT-3.5'e kıyasla daha tutarlı ve dilbilgisi açısından doğru yanıtlar üretmektedir.  
- **Streaming Desteği:** WebSocket üzerinden `send_message_stream` ile token-token yanıt akışı sağlanır, böylece kullanıcı yanıtı beklemeden okumaya başlayabilir.

**Sistemdeki Rolü:**

Gemini, projede **tek LLM** olarak çalışır ve şu görevlerin tamamını üstlenir:

1. Kullanıcının niyetini anlama (NLU)
2. Gerekli bilgiyi adım adım toplama (Slot Filling)
3. Uygun araçları çağırma (`get_bus_trips`, `validate_tc_number`, `make_reservation` vb.)
4. Araç sonuçlarını insani bir dilde kullanıcıya aktarma (NLG)
5. Konuşma özetleme (Memory Service)
6. ACT token üretimi (duygu bilgisi)

---

### 2. XLM-RoBERTa (cardiffnlp/twitter-xlm-roberta-base-sentiment) — Duygu Analizi

| Özellik | Detay |
| --- | --- |
| **Model** | `cardiffnlp/twitter-xlm-roberta-base-sentiment` |
| **Mimari** | XLM-RoBERTa Base (HuggingFace Transformers) |
| **Kullanım Amacı** | Metin tabanlı duygu tespiti (Sentiment Analysis) |
| **Çalışma Ortamı** | Yerel (CPU/GPU), API gerektirmez |

**Neden Bu Model?**

- **Çok Dilli Destek (100+ Dil):** RoBERTa'nın XLM varyantı, Türkçe dahil 100'den fazla dilde eğitilmiştir. Türkçe için ayrı bir model indirmeye gerek kalmaz.  
- **Hafif ve Hızlı:** ~278M parametreli Base boyutu, CPU üzerinde bile <100ms'de sonuç üretir. GPU mevcut olduğunda otomatik olarak GPU'ya geçer (`torch.cuda.is_available()`).  
- **Twitter/Sosyal Medya Verisiyle Eğitim:** Kısa, konuşma dili ağırlıklı metinlerde (ki chatbot diyalogları buna çok yakındır) yüksek doğruluk sağlar.  
- **Offline Çalışma:** Model bir kez indirilir ve tamamen yerel çalışır. Dış API'ye bağımlılık yoktur.

**Hibrit Duygu Tespiti Stratejisi:**

Projede duygu tespiti iki katmanlı bir yaklaşımla yapılır:

1. **ACT Token (Birincil):** Gemini'ye verilen system prompt'ta, her yanıtın başına `<|ACT:"emotion":{"name":"happy","intensity":0.7}|>` formatında bir duygu token'ı eklemesi istenir. Bu, LLM'in kendi bağlam anlayışına dayalı en güvenilir duygu kaynağıdır.
2. **Transformer Fallback (İkincil):** ACT token bulunamazsa XLM-RoBERTa modeli devreye girer ve metnin sentiment sınıfını (positive/negative/neutral) tespit ederek avatar duygu etiketine dönüştürür.

---

### 3. all-MiniLM-L6-v2 (Sentence Transformers) — Semantik Önbellekleme

| Özellik | Detay |
| --- | --- |
| **Model** | `all-MiniLM-L6-v2` |
| **Mimari** | MiniLM (Microsoft, 6 katman, 22M parametre) |
| **Kullanım Amacı** | Sorgu benzerliği hesaplama (Semantic Cache) |
| **Çalışma Ortamı** | Yerel CPU |

**Neden Bu Model?**

- **Ultra Hafif:** Yalnızca 22M parametre ile saniyenin milisaniye mertebesinde vektör üretir. Daha büyük modeller (e.g., `all-mpnet-base-v2`) daha iyi doğruluk sağlar ama chatbot gibi gerçek zamanlı bir uygulamada hız kritiktir.  
- **Sentence Transformers Ekosistemine Uyum:** `sentence-transformers` kütüphanesi ile tek satırda `model.encode(text)` çağrısıyla 384 boyutlu dense vektör üretilebilir.  
- **Yeterli Semantik Kalite:** Aynı anlamlı sorguları (ör. "İstanbul'a bilet" vs "İstanbul'a gitmek istiyorum") yüksek cosine benzerliği ile eşleştirir. 0.90 eşik değeri ile yalnızca gerçekten aynı sorular cache'ten yanıtlanır.

**Semantik Cache Nasıl Çalışır?**

1. Kullanıcının mesajı bir embedding vektörüne dönüştürülür.
2. Daha önce yanıtlanmış ve RAM'de tutulan tüm sorgu vektörleriyle cosine similarity hesaplanır.
3. Benzerlik ≥ 0.90 ise, LLM çağrısı atlanarak önceki yanıt (metin + ses + duygu) doğrudan döndürülür.
4. Sayısal ağırlıklı girdiler (TC, telefon vb.) cache'ten otomatik bypass edilir; çünkü bu tür girdilerde anlamsal benzerlik yanıltıcıdır.

**Kazanç:** Tekrarlı sorularda LLM + TTS maliyeti tamamen ortadan kalkar ve yanıt süresi ~5ms'ye düşer.

---

### 4. ElevenLabs Scribe v1 — Konuşmadan Metne (STT)

| Özellik | Detay |
| --- | --- |
| **Model** | `scribe_v1` (ElevenLabs STT) |
| **Kullanım Amacı** | Kullanıcının sesli girdisini metne dönüştürme |
| **Erişim** | ElevenLabs SDK (API) |

**Neden ElevenLabs Scribe?**

- **Türkçe STT Kalitesi:** Google Cloud STT ve Whisper'a kıyasla Türkçe karşılaştırmalı testlerde yüksek doğruluk sağlamıştır.  
- **Tek SDK ile STT + TTS:** Aynı ElevenLabs SDK üzerinden hem konuşma tanıma hem ses sentezi yapılabilir. Bu, ayrı API hesapları / faturalandırma yönetme karmaşıklığını azaltır.  
- **Entegrasyon Basitliği:** `client.speech_to_text.convert()` ile tek çağrıda transkripsiyon sonucu alınır.

**STT Sonrası Metin Normalizasyonu:**

Türkçe sesli girişlerde STT çıktısı sıklıkla şu sorunları içerir:

- Sayı kelimelerinin karışık formda gelmesi: *"beş yüz otuz yedi"* → `537`
- Onluk-birlik parçalanması: *"altmış 1"* → `61`
- E-posta adreslerinin sesli söylenmesi: *"duygu at gmail nokta com"* → `duygu@gmail.com`

Bu sorunlar `stt_service.py` içindeki çok katmanlı normalizasyon pipeline'ı ile çözülür:

1. **Bağlam Tespiti:** Girdi e-posta mı, sayısal veri mi, yoksa doğal metin mi?
2. **Türkçe Sayı Dönüşümü:** Yazıyla söylenen sayılar hane hane rakamlara çevrilir.
3. **STT Parçalanma Tamiri:** `"60 1"` → `"61"` gibi bitişik olması gereken parçalar birleştirilir.
4. **E-posta Normalizasyonu:** `"at"` → `@`, `"nokta"` → `.`, `"ci mail"` → `"gmail"` gibi sesli kalıplar düzeltilir.

---

### 5. ElevenLabs Multilingual v2 — Metinden Konuşmaya (TTS)

| Özellik | Detay |
| --- | --- |
| **Model** | `eleven_multilingual_v2` |
| **Fallback** | Microsoft Edge-TTS (`tr-TR-EmelNeural`) |
| **Kullanım Amacı** | AI yanıtının sesli olarak okunması |

**Neden ElevenLabs + Edge-TTS Fallback?**

- **ElevenLabs:** Piyasadaki en doğal Türkçe TTS motorlarından biridir. Prozodi, vurgu ve duygu aktarımı açısından güçlüdür. Ancak API kotası sınırlıdır.  
- **Edge-TTS (Fallback):** ElevenLabs kotası dolduğunda veya API hatası oluştuğunda, Microsoft'un ücretsiz Edge-TTS motoru devreye girer. Kalite bir miktar düşer ancak kesintisiz hizmet sağlanır.

**TTS Öncesi Metin Hazırlığı:**

TTS motorlarına gönderilmeden önce metin şu işlemlerden geçer:

- ACT token'ları ve DELAY işaretleri temizlenir
- Sayılar Türkçe okunuşlarına dönüştürülür: `1.191,38 TL` → *"bin yüz doksan bir lira otuz sekiz kuruş"*
- 8+ haneli uzun sayılar (PNR, ID) rakam rakam okunur: `12345678` → *"bir iki üç dört beş altı yedi sekiz"*

---

## 🧩 Modül Açıklamaları

### Backend Servisleri (`backend/services/`)

| Modül | Dosya | Açıklama |
| --- | --- | --- |
| **LLM Service** | `llm_service.py` | Gemini API ile iletişim, system prompt oluşturma, konuşma geçmişi yönetimi, streaming + non-streaming yanıt üretimi |
| **Tools** | `tools.py` | Gemini'nin çağırdığı 6 araç fonksiyonu: sefer arama, koltuk doğrulama, TC doğrulama, telefon doğrulama, e-posta doğrulama, rezervasyon yapma |
| **STT Service** | `stt_service.py` | ElevenLabs Scribe ile ses→metin dönüşümü, Türkçe sayı/e-posta/telefon normalizasyonu |
| **TTS Service** | `tts_service.py` | ElevenLabs veya Edge-TTS ile metin→ses dönüşümü, Türkçe sayı okunuş hazırlığı |
| **Emotion Service** | `emotion_service_v2.py` | ACT token ayrıştırma + XLM-RoBERTa tabanlı duygu analizi |
| **Semantic Cache** | `semantic_cache_service.py` | all-MiniLM-L6-v2 ile vektör tabanlı semantik önbellek, tekrarlı sorgularda LLM bypass |
| **Memory Service** | `memory_service.py` | Her 10 mesajda bir Gemini ile konuşma özetlemesi, uzun konuşmalarda bağlam penceresi yönetimi |

### Backend Router'ları (`backend/routers/`)

| Router | Endpoint | Açıklama |
| --- | --- | --- |
| **Chat** | `POST /api/chat`, `WS /ws/chat` | Ana sohbet endpoint'leri. Deterministik doğrulama kısa yolları + Gemini LLM + TTS + duygu analizi pipeline'ı |
| **STT** | `POST /api/stt` | Ses dosyası alır, transkripsiyon döndürür |
| **TTS** | `POST /api/tts` | Metin alır, base64 kodlanmış ses döndürür |

### Frontend (`index.html`, `main.js`, `style.css`)

| Bileşen | Teknoloji | Açıklama |
| --- | --- | --- |
| **3D Avatar** | Three.js + @pixiv/three-vrm | VRM 1.0 formatında 3D karakter modeli. Göz kırpma, nefes alma, kafa hareketi, lip-sync animasyonları |
| **Lip-Sync** | Web Audio API (FFT) | Ses frekans analizi ile gerçek zamanlı ağız hareketleri (aa, ih, ee, oh, ou morph'ları) |
| **Duygu Sistemi** | Custom Expression Engine | 10 farklı duygu durumu (happy, sad, angry, think, curious vb.) + yumuşak geçiş (lerp) |
| **WebSocket Chat** | Native WebSocket | Streaming metin + ses + duygu güncellemeleri |
| **Ses Kayıt** | MediaRecorder API | Basılı tutarak konuşma (push-to-talk) |

---

## 🔄 Konuşma Akışı (Rezervasyon Pipeline)

```text
Kullanıcı: "Yarın Ankara'dan İstanbul'a gitmek istiyorum"
    │
    ▼
[1] STT Normalizasyonu (sesli giriş ise)
    │
    ▼
[2] Semantic Cache Kontrolü → Cache HIT ise → Önceki yanıtı döndür
    │                                              │
    │ Cache MISS                                   │
    ▼                                              │
[3] Gemini 2.5 Flash                               │
    ├── NLU: Niyet = sefer arama                   │
    ├── Slot: kalkış=Ankara, varış=İstanbul         │
    ├── Function Call: get_bus_trips(...)           │
    ├── Tool Sonucu: "Sefer bulundu, koltuk 3,5,7" │
    └── NLG: "Yarın için şu seferler mevcut..."    │
    │                                              │
    ▼                                              │
[4] TTS: Yanıtı seslendir (ElevenLabs / Edge-TTS) │
    │                                              │
    ▼                                              │
[5] Duygu Analizi: ACT Token → "happy"             │
    │                                              │
    ▼                                              │
[6] Semantic Cache'e Kaydet                        │
    │                                              │
    ▼ ◄──────────────────────────────────────────────
[7] Frontend: Metin + Ses + Avatar Duygu Güncelle
```

### Rezervasyon Adımları

| Adım | Kullanıcıdan Alınan Bilgi | Çağrılan Araç |
| --- | --- | --- |
| 1 | Kalkış ve varış şehri | — |
| 2 | Seyahat tarihi | `get_bus_trips` |
| 3 | Koltuk seçimi | `validate_seat_selection` |
| 4 | Ad soyad | — |
| 5 | T.C. Kimlik No | `validate_tc_number` |
| 6 | Telefon numarası | `validate_phone_number` |
| 7 | E-posta adresi | `validate_email_address` |
| 8 | Bilgi özeti onayı | — |
| 9 | Onay sonrası rezervasyon | `make_reservation` |

---

## 🛡️ Teknik Öne Çıkanlar

### T.C. Kimlik Doğrulama Algoritması

Standart 11 haneli algoritmik doğrulama uygulanır:

- İlk hane 0 olamaz
- Onuncu hane: `((tek_pozisyonlar × 7) - çift_pozisyonlar) mod 10`
- On birinci hane: `(ilk_10_hanenin_toplamı) mod 10`
- On birinci hane çift sayı olmalıdır

Sesli girişlerde STT parçalanmalarını (ör. "beş yüz otuz yedi altmış iki...") doğru şekilde birleştiren özel bir *kayan pencere* (sliding window) algoritması kullanılır.

### Deterministik Doğrulama Kısa Yolları

Chat router'da, LLM'in gereksiz tur kaybetmesini önlemek için belirli bağlamlarda deterministik doğrulama uygulanır:

- Bot telefon numarası sorduysa ve kullanıcı rakam gönderdiyse → `validate_phone_number` LLM'den önce çağrılır
- Bot koltuk sorduysa ve kullanıcı kısa bir sayı gönderdiyse → `validate_seat_selection` doğrudan çağrılır
- Bu sonuçlar, LLM'e `[SİSTEM BİLGİSİ]` formatında fısıldanarak bir sonraki adıma geçişi hızlandırır

### Konuşma Hafızası (Memory Service)

Uzun konuşmalarda Gemini'nin token bağlam penceresi dolabilir. Bu sorunu çözmek için her 10 mesajda bir Gemini ile konuşmanın özeti üretilir. Sonraki mesajlarda bu özet system prompt'a eklenir, böylece "unutkanlık" önlenir.

---

## 🗂️ Proje Yapısı

```text
Bus Ticket Booking Agent/
├── index.html                  # Ana frontend sayfası
├── main.js                     # 3D avatar, WebSocket, UI mantığı
├── style.css                   # Arayüz stilleri
├── ela_avatar.png              # Chat baloncuğu avatar ikonu
├── models/
│   └── character.vrm           # 3D karakter modeli (VRM 1.0)
├── bilet_sistemi.db            # Sefer veritabanı (SQLite)
├── rezervasyonlar.db           # Rezervasyon veritabanı (SQLite)
├── start.bat                   # Tek tıkla başlatma scripti
│
└── backend/
    ├── main.py                 # FastAPI uygulama giriş noktası
    ├── config.py               # Ayarlar, system prompt, API anahtarları
    ├── requirements.txt        # Python bağımlılıkları
    ├── .env                    # Ortam değişkenleri (API anahtarları)
    ├── bilet_sistemi.csv       # Sefer verileri (CSV kaynak)
    ├── rezervasyonlar.csv      # Rezervasyon verileri (CSV kaynak)
    │
    ├── routers/
    │   ├── chat.py             # Sohbet endpoint'leri (REST + WebSocket)
    │   ├── stt.py              # Konuşma tanıma endpoint'i
    │   └── tts.py              # Ses sentezi endpoint'i
    │
    └── services/
        ├── llm_service.py      # Gemini LLM entegrasyonu
        ├── tools.py            # Araç fonksiyonları (sefer, TC, telefon, email, rezervasyon)
        ├── stt_service.py      # ElevenLabs STT + Türkçe normalizasyon
        ├── tts_service.py      # ElevenLabs TTS + Edge-TTS fallback
        ├── emotion_service_v2.py  # Duygu analizi (ACT + XLM-RoBERTa)
        ├── semantic_cache_service.py # Semantik önbellek
        └── memory_service.py   # Konuşma özeti / hafıza yönetimi
```

---

## ⚙️ Kurulum ve Çalıştırma

### Gereksinimler

- Python 3.10+
- Node.js (Live Server için, isteğe bağlı)
- GPU (isteğe bağlı, duygu analizi modelini hızlandırır)

### 1. Backend Kurulumu

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Ortam Değişkenleri

`backend/.env` dosyasını yapılandırın:

```env
GOOGLE_API_KEY=your_google_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
GEMINI_CHAT_MODEL=gemini-2.5-flash
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
DEFAULT_LANG=tr
PORT=8001
```

### 3. Çalıştırma

```bash
# Backend
cd backend
python main.py

# Frontend (ayrı terminalde)
# Proje kök dizininde Live Server ile index.html'yi açın
# veya start.bat dosyasını çalıştırın
```

Backend `http://localhost:8001` adresinde, frontend ise `http://localhost:3000` (veya Live Server portu) üzerinde çalışır.

---

## 📦 Kullanılan Teknolojiler ve Kütüphaneler

| Teknoloji | Versiyon / Detay | Kullanım Alanı |
| --- | --- | --- |
| **Python** | 3.10+ | Backend dili |
| **FastAPI** | — | REST API + WebSocket framework |
| **Uvicorn** | — | ASGI sunucu |
| **google-genai** | — | Google Gemini API SDK |
| **ElevenLabs SDK** | — | STT (Scribe) + TTS |
| **edge-tts** | — | TTS Fallback (Microsoft) |
| **transformers** | HuggingFace | XLM-RoBERTa duygu modeli |
| **sentence-transformers** | — | Semantik cache embedding |
| **torch** | PyTorch | Model inference |
| **SQLite** | Built-in | Veritabanı |
| **Three.js** | r164 | 3D render engine |
| **@pixiv/three-vrm** | 3.0.0 | VRM model yükleme/animasyon |
| **Chart.js** | — | Duygu radar grafiği |
| **Web Audio API** | Native | Lip-sync frekans analizi |

---

## 📊 Performans Metrikleri

| Metrik | Değer |
| --- | --- |
| LLM Yanıt Süresi (ortalama) | ~1.5–3 saniye |
| TTS Üretim Süresi | ~0.5–1.5 saniye |
| Semantik Cache Hit Süresi | ~5ms |
| Duygu Analizi (Transformer) | ~50–100ms (CPU) |
| STT Transkripsiyon | ~1–2 saniye |
| Avatar FPS | 60 FPS (modern tarayıcı) |

---

## 👤 Geliştirici

Bu proje, yapay zekâ destekli konuşma arayüzlerinin gerçek dünya uygulamalarındaki potansiyelini göstermek amacıyla geliştirilmiştir.

---

## 📄 Lisans

Bu proje akademik amaçlı geliştirilmiştir.
