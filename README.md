# 🚌 Müşteri Asistanı — Yapay Zekâ Destekli Otobüs Bileti Rezervasyon Sistemi

> **Sesli ve yazılı etkileşim destekli, 3D avatarlı, uçtan uca akıllı otobüs bileti rezervasyon sistemi.**

---

## 📌 Projenin Amacı

Bu proje, geleneksel web tabanlı otobüs bileti satın alma sürecini **yapay zekâ destekli bir konuşma arayüzüne** dönüştürmeyi amaçlamaktadır. Kullanıcı, ekrandaki 3D avatar ile Türkçe ve İngilizce sesli veya yazılı olarak etkileşime girerek menülere, formlara veya karmaşık filtre panellerine ihtiyaç duymadan bilet rezervasyonu yapabilir.

### Çözmek İstediğimiz Problem

Mevcut otobüs bileti platformlarında kullanıcı, güzergah seçimi → tarih seçimi → koltuk seçimi → yolcu bilgileri → ödeme gibi çok adımlı bir form sürecinden geçmek zorundadır. Bu süreç özellikle yaşlı kullanıcılar, teknolojiye uzak bireyler veya hareket halindeki kullanıcılar için zorlu olabilmektedir.

**Müşteri Asistanı**, bu süreci doğal bir sohbete dönüştürür:

- *"Yarın Ankara'dan İstanbul'a gitmek istiyorum"* → Sistem uygun seferleri otomatik bulur
- *"5 numaralı koltuğu istiyorum"* → Koltuk uygunluğunu kontrol eder
- *"TC'm 12345678910"* → Algoritmik doğrulamayı anında yapar
- **Çok Dilli Destek:** TR/EN butonları ile anında dil değiştirme (Sistemsel talimatlar ve onay mekanizmaları her iki dil için de tamamen optimize edilmiştir)
- **Mobil Uyumlu:** Telefon ve tabletler için optimize edilmiş özel dikey görünüm ve akıllı klavye yönetimi
- Tüm bilgiler toplandığında özet sunar ve onay sonrası rezervasyonu tamamlar

---

## 🏗️ Sistem Mimarisi

```text
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Vanilla JS)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐│
│  │ Chat Panel   │  │  3D Avatar   │  │  WebSocket İstemcisi   ││
│  │ (Metin/Ses)  │  │  (Three.js + │  │  (Streaming Yanıt)     ││
│  │  VAD Sistemi │  │   VRM 1.0)   │  │                        ││
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
│  │  _preprocess_request() — ortak deterministik doğrulama    │   │
│  └─────────┬────────────────┴──────────────┬─────────────────┘   │
│            │                               │                     │
│  ┌─────────▼───────────────────────────────▼─────────────────┐   │
│  │           LLM Service (Gemini 2.5 Flash)                  │   │
│  │   Konuşma yönetimi + Function Calling                     │   │
│  │   Manuel tool-call döngüsü (max 10 tur, IndexError-safe)  │   │
│  └─────────┬─────────────────────────────────────────────────┘   │
│            │                                                     │
│  ┌─────────▼─────────────────────────────────────────────────┐   │
│  │              Tool Functions  +  number_utils              │   │
│  │  get_bus_trips │ validate_seat │ validate_tc │ validate_   │   │
│  │                │ _selection    │ _number     │ phone/email │   │
│  │  make_reservation  (contextmanager DB, _sync_csv)         │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌───────────────┐ ┌───────────────┐ ┌─────────────────────┐    │
│  │  STT Service  │ │  TTS Service  │ │  Memory Service     │    │
│  │  (Google      │ │  (Microsoft   │ │  (Gemini özetleme   │    │
│  │   Gemini)     │ │   Edge-TTS)   │ │  + buffer snapshot) │    │
│  └───────────────┘ └───────────────┘ └─────────────────────┘    │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │       Semantic Cache  (varsayılan: KAPALI)                 │   │
│  │  all-MiniLM-L6-v2 + Cosine Sim.                           │   │
│  │  ENABLED=False → model yüklenmez, ~200 MB RAM tasarrufu   │   │
│  └───────────────────────────────────────────────────────────┘   │
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
6. **Çok Dilli (Multilingual) Destek:** Seçilen dile göre dinamik `SYSTEM_PROMPT` ve teknik yönlendirme (whisper) yönetimi.

**Tool-Call Döngüsü Güvenliği:**

`automatic_function_calling=False` ile döngü `llm_service.py` içinde manuel yönetilir. `_has_function_call()` guard fonksiyonu boş `candidates` veya eksik `parts` durumlarında `IndexError` üretmesini engeller. Sonsuz döngü önlemek için maksimum **10 iterasyon** limiti uygulanır.

---

### 2. all-MiniLM-L6-v2 (Sentence Transformers) — Semantik Önbellekleme

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

**Kazanım:** Tekrarlı sorularda LLM + TTS maliyeti tamamen ortadan kalkar ve yanıt süresi ~5ms'ye düşer.

---

### 3. Google Gemini — Konuşmadan Metne (STT)

| Özellik | Detay |
| --- | --- |
| **Model** | `gemini-2.5-flash` (Audio-to-Text, aynı model) |
| **Kullanım Amacı** | Kullanıcının sesli girdisini metne dönüştürme |
| **Erişim** | Google GenAI SDK (API) |

**Neden Gemini STT?**

- **Native Multimodal Desteği:** Gemini 1.5/2.0+ modelleri ses verisini doğrudan (native) işleyebilir. Bu, üçüncü parti STT servislerine olan bağımlılığı azaltır ve gecikmeyi (latency) minimize eder.
- **Doğal Dil Bağlamı:** Gemini, sadece sesi metne çevirmekle kalmaz, cümlenin gelişinden hangi kelimenin kullanılmış olabileceğini anlama yeteneğine sahiptir (Örn: özel isimlerde daha başarılıdır).
- **Tek SDK:** LLM ve STT işlemleri aynı Google API anahtarı ve SDK üzerinden yürütülür.

**STT Sonrası Metin Normalizasyonu:**

Türkçe sesli girişlerde STT çıktısı sıklıkla şu sorunları içerir:

- Sayı kelimelerinin karışık formda gelmesi: *"beş yüz otuz dokuz"* → `539`
- Onluk-birlik parçalanması: *"elli 1"* → `51`
- E-posta adreslerinin sesli söylenmesi: *"fatma at gmail nokta com"* → `fatma@gmail.com`

Bu sorunlar `stt_service.py` içindeki çok katmanlı normalizasyon pipeline'ı ile çözülür; sayı dönüşüm mantığı `number_utils.py`'dan import edilir:

1. **Bağlam Tespiti:** Girdi e-posta mı, sayısal veri mi, yoksa doğal metin mi?
2. **Türkçe Sayı Dönüşümü:** Yazıyla söylenen sayılar hane hane rakamlara çevrilir.
3. **STT Parçalanma Tamiri:** `"50 1"` → `"51"` gibi bitişik olması gereken parçalar birleştirilir.
4. **E-posta Normalizasyonu:** `"at"` → `@`, `"nokta"` → `.`, `"ci mail"` → `"gmail"` gibi sesli kalıplar düzeltilir.

---

### 4. Microsoft Edge-TTS — Metinden Konuşmaya (TTS)

| Özellik | Detay |
| --- | --- |
| **Model** | `tr-TR-EmelNeural` (Türkçe) / `en-US-AriaNeural` (İngilizce) |
| **Kullanım Amacı** | AI yanıtının sesli olarak okunması |

**Neden Edge-TTS?**

- **Hız ve Lisans:** Microsoft'un Edge tarayıcısı için kullandığı bu motor, gerçek zamanlı yanıtlar için optimize edilmiştir.
- **Maliyet:** Ücretsiz ve sınırsız bir şekilde kullanılabilmesi projenin sürdürülebilirliğini sağlar.
- **Kalite:** Nöral ses teknolojisi sayesinde doğal vurgular ve akıcı bir okuma sunar.

**TTS Öncesi Metin Hazırlığı:**

TTS motorlarına gönderilmeden önce metin şu işlemlerden geçer:

- ACT token'ları ve DELAY işaretleri temizlenir
- Sayılar Türkçe okunuşlarına dönüştürülür: `1.191,38 TL` → *"bin yüz doksan bir lira otuz sekiz kuruş"*
- 8+ haneli uzun sayılar (PNR, ID) rakam rakam okunur: `12345678` → *"bir iki üç dört beş altı yedi sekiz"*
- Geçici ağ hataları (503) için otomatik **1 yeniden deneme** uygulanır

---

## 🎙️ Sesli Etkileşim Sistemi — VAD (Voice Activity Detection)

Sistem, "basılı tut" (push-to-talk) yaklaşımı yerine **sürekli dinleme ve otomatik konuşma algılama** modeli üzerine inşa edilmiştir. Kullanıcı deneyimi, bir insan ile karşılıklı konuşmaya mümkün olduğunca yaklaştırılmıştır.

### Temel Davranış

| Durum | Ne Olur |
| --- | --- |
| Mikrofon butonu tıklandı | Mikrofon açılır, sürekli dinleme başlar (yeşil nabız animasyonu) |
| Kullanıcı konuşmaya başladı | Ses seviyesi eşiği aşıldığında kayıt otomatik başlar |
| Kullanıcı sustu (≥1000ms) | Kayıt durur, ses STT'ye gönderilir, asistan cevap verir |
| Avatar konuşurken kullanıcı konuştu | **Avatar anında susar**, kayıt hemen başlar (barge-in) |
| Mikrofon butonu tekrar tıklandı | Mikrofon kapanır |

### Barge-In (Araya Girme)

Avatar konuşurken kullanıcı söz almak istediğinde sistem şu adımları izler:

1. `micAnalyser`, avatarın hoparlör sesinden **bağımsız** olarak yalnızca mikrofon girdisini ölçer — `destination`'a bağlanmadığı için hoparlörden geri besleme olmaz.
2. Ses seviyesi `BARGE_IN_THRESHOLD` değerini aşarsa `stopAudio()` çağrılır → Avatar anında durur.
3. Kayıt **aynı anda** başlatılır → kullanıcının ilk hecesi kaybolmaz.

### Eko Koruması

Tarayıcı seviyesinde `echoCancellation`, `noiseSuppression` ve `autoGainControl` etkin tutulur. Buna ek olarak mikrofon `AudioContext` içinde Ela'nın ses grafiğine hiç bağlanmaz; yalnızca ölçüm için ayrı bir `micAnalyser` düğümünden geçirilir.

### Frekans Bandına Odaklanma

Ses seviyesi hesaplanırken tüm frekans spektrumu yerine yalnızca **insan konuşma bandı (300 Hz – 3400 Hz)** kullanılır. Bu yaklaşım, Ela'nın hoparlörden sızan düşük frekanslı seslerinin ve ortam gürültüsünün yanlış kayıt tetiklemesini azaltır.

### Eşik Değerleri ve Ayarlar

Tüm sabitleri `frontend/js/audio.js` başında değiştirebilirsiniz:

| Sabit | Varsayılan | Açıklama |
| --- | --- | --- |
| `VAD_THRESHOLD` | `15` | Normal sessizlikte kayıt başlatma eşiği (0-255) |
| `BARGE_IN_THRESHOLD` | `12` | Ela konuşurken barge-in eşiği (daha hassas) |
| `SILENCE_DURATION_MS` | `1000` | Bu kadar sessizlik → kayıt biter, STT'ye gider |
| `MIN_SPEECH_MS` | `300` | Daha kısa ses → gürültü olarak atlanır |

> **İpucu:** Gürültülü bir ortamda kullanıyorsanız `VAD_THRESHOLD` ve `BARGE_IN_THRESHOLD` değerlerini 5-10 puan artırın. Ela çok erken kesiyorsa `SILENCE_DURATION_MS`'i 1300-1500'e çıkarın.

---

## 🧩 Modül Açıklamaları

### Backend Servisleri (`backend/services/`)

| Modül | Dosya | Açıklama |
| --- | --- | --- |
| **Number Utils** | `number_utils.py` | ★ **Yeni.** Türkçe/İngilizce sayı kelimesi→rakam dönüşümünün tek kaynağı. `tools.py` ve `stt_service.py` buradan import eder; ~600 satır tekrar kod elimine edildi. |
| **LLM Service** | `llm_service.py` | Gemini API ile iletişim, system prompt oluşturma, konuşma geçmişi yönetimi. Güvenli tool-call döngüsü: `_has_function_call()` guard + max 10 iterasyon limiti. |
| **Tools** | `tools.py` | Gemini'nin çağırdığı 6 araç fonksiyonu. `contextmanager` ile garantili DB bağlantısı (hata → rollback → close). `_sync_csv` yardımcısı ile CSV yedekleme. |
| **STT Service** | `stt_service.py` | Google Gemini ile ses→metin dönüşümü. Bağlam tespiti + `number_utils` tabanlı Türkçe/İngilizce normalizasyon pipeline'ı. |
| **TTS Service** | `tts_service.py` | Microsoft Edge-TTS ile metin→ses dönüşümü, Türkçe sayı okunuş hazırlığı, otomatik retry. |
| **Semantic Cache** | `semantic_cache_service.py` | all-MiniLM-L6-v2 ile vektör tabanlı semantik önbellek. Varsayılan olarak kapalıdır (`_ENABLED = False`); kapalıyken model yüklenmez. |
| **Memory Service** | `memory_service.py` | Her `SUMMARIZE_EVERY` mesajda bir Gemini ile konuşma özetlemesi. `await` öncesi buffer snapshot alınır; hata durumunda mesajlar kaybolmaz. |

### Backend Router'ları (`backend/routers/`)

| Router | Endpoint | Açıklama |
| --- | --- | --- |
| **Chat** | `POST /api/chat`, `WS /ws/chat` | Ortak `_preprocess_request()` fonksiyonu: deterministik doğrulama kısa yolları + `[SİSTEM BİLGİSİ]` injection + `[ABSOLUTE SYSTEM TRUTH]` injection. REST ve WS'de aynı kod tekrarlanmıyor. |
| **STT** | `POST /api/stt` | Ses dosyası alır, transkripsiyon döndürür |
| **TTS** | `POST /api/tts` | Metin alır, base64 kodlanmış ses döndürür |

### Frontend (`frontend/`)

| Bileşen | Dosya | Açıklama |
| --- | --- | --- |
| **3D Avatar** | `js/avatar.js` | Three.js + @pixiv/three-vrm. VRM 1.0 formatında 3D karakter modeli. Göz kırpma, nefes alma, kafa hareketi, lip-sync animasyonları. Dinamik VRM yükleme (`loadVRM`) ve otomatik kamera hizalama (`_fitCameraToVRM`) destekli. |
| **Ses & VAD** | `js/audio.js` | Web Audio API tabanlı ses çalma, VAD döngüsü, barge-in, eko koruması, MediaRecorder kayıt yönetimi. |
| **Sohbet** | `js/chat.js` | WebSocket bağlantısı, mesaj gönderme, streaming metin render, sohbet geçmişi UI, çok dilli destek. |
| **Giriş Noktası** | `main.js` | Tüm modülleri birleştirir, UI olay dinleyicilerini bağlar. Mikrofon toggle → `toggleVAD()`. Avatar ayarları modal'ı (VRM yükleme, cinsiyet/ses seçimi). |
| **Stiller** | `style.css` | Responsive tasarım + VAD animasyonları (yeşil nabız: `vad-active`, hızlı nabız: `vad-active.recording`). |

---

## 🌐 Çok Dilli Destek (TR / EN)

Sistem, Türkçe ve İngilizce olmak üzere iki dili tam olarak destekler. Dil seçimi frontend'deki TR/EN butonları aracılığıyla yapılır ve seçilen dil her istekte backend'e iletilir.

**Dil bazlı farklılaşma şu katmanlarda uygulanır:**

| Katman | Türkçe | İngilizce |
| --- | --- | --- |
| **System Prompt** | `SYSTEM_PROMPT` (`config.py`) | `SYSTEM_PROMPT_EN` (`config.py`) |
| **Dil kuralı** | `SADECE Türkçe cevap ver` | `Reply ONLY in English` |
| **TTS sesi** | `tr-TR-EmelNeural` (Kadın) / `tr-TR-AhmetNeural` (Erkek) | `en-US-AriaNeural` (Kadın) / `en-US-GuyNeural` (Erkek) |
| **STT talimatı** | Türkçe transkripsiyon yönergesi | İngilizce transkripsiyon yönergesi |
| **Sistem enjeksiyonu** | `[SİSTEM BİLGİSİ: ...]` | `[SYSTEM INFORMATION: ...]` |
| **Özet dili** | Türkçe | İngilizce (buffer'daki İngilizce kelimelerle otomatik tespit) |

**`SYSTEM_PROMPT_EN` Gerekçesi:**

Yalnızca dil kuralı eklemek yetmez; rezervasyon akışının doğru çalışması için tüm adım tanımları, veri bütünlüğü uyarıları ve whisper formatları İngilizce olarak ayrıca yazılmıştır. Örneğin:

- `[SYSTEM INFORMATION: Tool result: ...]` — doğrulama sonuçları İngilizce enjekte edilir
- `STRICT_LANGUAGE RULE: Reply ONLY in English` — sistem prompt sonuna eklenir
- Özet adımında `--- SUMMARY OF PREVIOUS CONVERSATION ---` başlığı kullanılır

Bu sayede kullanıcı EN moduna geçtiğinde tüm konuşma akışı, hata mesajları ve özetler tutarlı biçimde İngilizce kalır.

---

## 🔄 Konuşma Akışı (Rezervasyon Pipeline)

```text
Kullanıcı konuşur (VAD otomatik algılar)
    │
    ▼
[0] VAD Döngüsü (requestAnimationFrame)
    ├── Ses seviyesi > eşik → kayıt başlar
    ├── Avatar konuşuyorsa → eşik düşürülür (barge-in modu)
    │   └── Kullanıcı ses çıkarırsa → Avatar durur, kayıt anında başlar
    └── Sessizlik ≥ 1000ms → kayıt biter, STT'ye gider
    │
    ▼
[1] STT Normalizasyonu
    │
    ▼
[2] _preprocess_request()
    ├── Deterministik koltuk / telefon / e-posta doğrulaması
    ├── [SİSTEM BİLGİSİ] injection (doğrulama sonuçları)
    └── [ABSOLUTE SYSTEM TRUTH] injection (halüsinasyon önleme)
    │
    ▼
[3] Semantic Cache Kontrolü → Cache HIT ise → Önceki yanıtı döndür
    │                                              │
    │ Cache MISS                                   │
    ▼                                              │
[4] Gemini 2.5 Flash (tool-call döngüsü, max 10 tur)
    ├── NLU: Niyet = sefer arama                   │
    ├── Slot: kalkış=Ankara, varış=İstanbul         │
    ├── Function Call: get_bus_trips(...)           │
    ├── Tool Sonucu: "Sefer bulundu, koltuk 3,5,7" │
    └── NLG: "Yarın için şu seferler mevcut..."    │
    │                                              │
    ▼                                              │
[5] TTS: Yanıtı seslendir (Microsoft Edge-TTS)     │
    │                                              │
    ▼ ◄──────────────────────────────────────────────
[6] Frontend: Metin + Ses Güncelle
    └── avatarIsSpeaking = true → VAD barge-in moduna girer
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

### number_utils.py — Tek Kaynak Prensibi

Daha önce `tools.py`, `stt_service.py` ve `routers/chat.py` içinde yaklaşık **600 satır** olarak üç kez tekrarlanan Türkçe/İngilizce sayı kelimesi→rakam dönüşüm mantığı `services/number_utils.py` modülüne taşındı. Tüm modüller bu tek kaynaktan import eder.

Sağlanan temel fonksiyonlar:

- `extract_digit_stream(text)` — karışık kelime+rakam girdisini saf rakam dizisine çevirir (yüzler, onluklar, bileşikler, STT parçalanma tamiri dahil)
- `normalize_phone_digits(text)` — telefon normalizasyonu (ülke kodu stripping dahil)
- `normalize_text(text)` — Türkçe karakter normalizasyonu + boşluk temizliği

### T.C. Kimlik Doğrulama Algoritması

Standart 11 haneli algoritmik doğrulama uygulanır:

- İlk hane 0 olamaz
- Onuncu hane: `((tek_pozisyonlar × 7) - çift_pozisyonlar) mod 10`
- On birinci hane: `(ilk_10_hanenin_toplamı) mod 10`
- On birinci hane çift sayı olmalıdır

Sesli girişlerde STT parçalanmalarını (ör. "beş yüz otuz yedi altmış iki...") doğru şekilde birleştiren özel bir *kayan pencere* (sliding window) algoritması kullanılır.

### Deterministik Doğrulama Kısa Yolları

Chat router'da, LLM'in gereksiz tur kaybetmesini önlemek için belirli bağlamlarda deterministik doğrulama uygulanır. Bu mantık REST ve WebSocket endpoint'lerinde daha önce **tamamen tekrarlanıyordu**; artık tek `_preprocess_request()` fonksiyonunda toplanmıştır:

- Bot telefon numarası sorduysa ve kullanıcı rakam gönderdiyse → `validate_phone_number` LLM'den önce çağrılır
- Bot koltuk sorduysa ve kullanıcı kısa bir sayı gönderdiyse → `validate_seat_selection` doğrudan çağrılır
- Bot e-posta sorduysa → `validate_email_address` direkt çağrılır
- Bu sonuçlar, LLM'e `[SİSTEM BİLGİSİ]` formatında fısıldanarak bir sonraki adıma geçişi hızlandırır

### Halüsinasyon Önleme — ABSOLUTE SYSTEM TRUTH

`_inject_ground_truth()`, konuşma geçmişinden onaylanmış Sefer ID, güzergah, tarih ve koltuk bilgilerini çekerek her mesaja şu formatı ekler:

```
[ABSOLUTE SYSTEM TRUTH (NEVER HALLUCINATE): STRICT_ID=42 | STRICT_ROUTE=Ankara to Istanbul | STRICT_DATE=2026-03-22 | STRICT_SEAT=5]
```

Bu sayede LLM'in kendi eğitim verisinden (`"12345"`, `"İstanbul-Ankara"` vb.) uydurmaya çalışması engellenir.

### Güvenli Veritabanı Bağlantısı

`tools.py`'daki tüm DB işlemleri `contextmanager` ile sarılmıştır:

```python
with _db(DB_PATH) as conn:
    ...  # commit otomatik; hata → rollback otomatik; finally → close garantili
```

Daha önce hata senaryolarında bağlantı açık kalabiliyordu.

### Konuşma Hafızası (Memory Service)

Uzun konuşmalarda Gemini'nin token bağlam penceresi dolabilir. Bu sorunu çözmek için her `SUMMARIZE_EVERY` mesajda bir Gemini ile konuşmanın özeti üretilir. Sonraki mesajlarda bu özet system prompt'a eklenir, böylece "unutkanlık" önlenir.

**Race Condition Düzeltmesi:** `_summarize()` fonksiyonu `await` öncesinde buffer'ın snapshot'ını alır. Özetleme başarısız olursa mesajlar kaybolmaz; buffer eski hâline restore edilir.

### WebSocket Sağlık ve Hata Yönetimi

- **Railway Healthcheck & HMR:** Geliştirme araçlarının (Vite HMR) ve Railway sağlık kontrollerinin log spam'ini önlemek için `/ws` altında bir dummy endpoint bulunur.
- **JSON Fallback:** WebSocket üzerinden gelen bozuk veya JSON olmayan veriler sistemin çökmesini engellemek için try-except bloklarıyla yakalanır.

---

## 🗂️ Proje Yapısı

```text
Bus Ticket Booking Agent/
├── frontend/                   # Ön yüz klasörü
│   ├── index.html              # Ana frontend sayfası
│   ├── main.js                 # Giriş noktası; UI olayları, VAD toggle bağlantısı
│   ├── style.css               # Arayüz stilleri (VAD animasyonları dahil)
│   ├── ela_avatar.png          # Chat baloncuğu avatar ikonu
│   ├── arkaplan.jpeg           # Arka plan resmi
│   ├── js/
│   │   ├── audio.js            # VAD, barge-in, eko koruması, ses çalma
│   │   ├── avatar.js           # 3D avatar render, lip-sync, duygu sistemi
│   │   └── chat.js             # WebSocket, mesaj gönderme, sohbet geçmişi UI
│   └── models/
│       └── character.vrm       # 3D karakter modeli (VRM 1.0)
├── start.bat                   # Tek tıkla başlatma scripti
│
└── backend/
    ├── database/               # Veritabanı ve CSV dosyaları
    │   ├── bilet_sistemi.db    # Sefer veritabanı (SQLite)
    │   ├── rezervasyonlar.db   # Rezervasyon veritabanı (SQLite)
    │   ├── bilet_sistemi.csv   # Sefer yedek dosyası (CSV)
    │   └── rezervasyonlar.csv  # Rezervasyon yedek dosyası (CSV)
    ├── main.py                 # FastAPI giriş noktası; logging config
    ├── config.py               # Ayarlar, system prompt, type-safe env parsing
    ├── requirements.txt        # Python bağımlılıkları (sadece aktif paketler)
    ├── .env                    # Ortam değişkenleri (API anahtarları)
    │
    ├── routers/
    │   ├── chat.py             # REST + WebSocket; ortak _preprocess_request()
    │   ├── stt.py              # Konuşma tanıma endpoint'i
    │   └── tts.py              # Ses sentezi endpoint'i
    │
    └── services/
        ├── number_utils.py         # ★ Yeni: paylaşımlı sayı parse utility
        ├── llm_service.py          # Gemini LLM + güvenli tool-call döngüsü
        ├── tools.py                # 6 araç; contextmanager DB; _sync_csv
        ├── stt_service.py          # Gemini STT + bağlam tespiti + normalize
        ├── tts_service.py          # Edge-TTS + Türkçe sayı okunuşu + retry
        ├── semantic_cache_service.py  # MiniLM cache (varsayılan: kapalı)
        └── memory_service.py       # Gemini özetleme + buffer snapshot fix
```

---

## ⚙️ Kurulum ve Çalıştırma

### Gereksinimler

- Python 3.10+
- Node.js (Live Server için, isteğe bağlı)

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
GEMINI_CHAT_MODEL=gemini-2.5-flash
DEFAULT_LANG=tr
PORT=8001
CORS_ORIGINS=*
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
| **google-genai** | — | Google Gemini API SDK (LLM + STT) |
| **edge-tts** | — | TTS Motoru (Microsoft) |
| **SQLite** | Built-in | Veritabanı |
| **Three.js** | r164 | 3D render engine |
| **@pixiv/three-vrm** | 3.0.0 | VRM model yükleme/animasyon |
| **Chart.js** | — | Duygu radar grafiği |
| **Web Audio API** | Native | Lip-sync frekans analizi + VAD ses ölçümü |
| **MediaRecorder API** | Native | VAD tabanlı ses kaydı (80ms chunk) |

---

## 📊 Performans Metrikleri

| Metrik | Değer |
| --- | --- |
| LLM Yanıt Süresi (ortalama) | ~1.5–3 saniye |
| TTS Üretim Süresi | ~0.5–1.5 saniye |
| Semantik Cache Hit Süresi | ~5ms |
| STT Transkripsiyon | ~1–2 saniye |
| Avatar FPS | 60 FPS (modern tarayıcı) |
| VAD Tepki Süresi | ~16ms (1 frame, requestAnimationFrame) |
| Barge-in Gecikme | <100ms (kayıt chunk aralığı) |

---

## 👤 Geliştirici

Bu proje, yapay zekâ destekli konuşma arayüzlerinin gerçek dünya uygulamalarındaki potansiyelini göstermek amacıyla geliştirilmiştir.

---

## 📄 Lisans

Bu proje akademik amaçlı geliştirilmiştir.
