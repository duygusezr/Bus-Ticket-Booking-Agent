# 🚌 Müşteri Asistanı — Yapay Zekâ Destekli Otobüs Bileti Rezervasyon Sistemi

> **Sesli ve yazılı etkileşim destekli, 3D avatarlı, uçtan uca akıllı otobüs bileti rezervasyon sistemi.**

---

## 📌 Projenin Amacı

Bu proje, geleneksel web tabanlı otobüs bileti satın alma sürecini **yapay zekâ destekli bir konuşma arayüzüne** dönüştürmeyi amaçlamaktadır. Kullanıcı, ekrandaki 3D avatar ile Türkçe ve İngilizce sesli veya yazılı olarak etkileşime girerek menülere, formlara veya karmaşık filtre panellerine ihtiyaç duymadan bilet rezervasyonu yapabilir.

### Çözmek İstediğimiz Problem

Mevcut otobüs bileti platformlarında kullanıcı, güzergah seçimi → tarih seçimi → koltuk seçimi → yolcu bilgileri → ödeme gibi çok adımlı bir form sürecinden geçmek zorundadır. Bu süreç özellikle yaşlı kullanıcılar, teknolojiye uzak bireyler veya hareket halindeki kullanıcılar için zorlu olabilmektedir.

**Müşteri Asistanı**, bu süreci doğal bir sohbete dönüştürür:

- *"Yarın Ankara'dan İstanbul'a gitmek istiyorum"* → Sistem uygun seferleri otomatik bulur
- *"5 numaralı koltuğu istiyorum"* → Koltuk uygunluğunu kontrol eder (Dilerseniz ekrandaki interaktif koltuk haritası üzerinden de seçim yapabilirsiniz)
- *"TC'm 12345678910"* → Algoritmik doğrulamayı ve gelişmiş sesli sayılarla TC normalizasyonunu anında yapar
- **Görsel Arayüz (Soft UI):** Biletleme ve fatura paneli üzerinden şık ve net bir onay (ticket confirmation) ekranı sunar
- **Kesintisiz İletişim (Barge-in):** Gelişmiş dip gürültü filtreleme teknolojisi sayesinde avatar konuşurken bile sözünü keserek (barge-in) akıcı bir diyalog kurabilirsiniz
- **Çok Dilli Destek:** TR/EN butonları ile anında dil değiştirme (Sistemsel talimatlar ve onay mekanizmaları her iki dil için de tamamen optimize edilmiştir)
- **Toplanmış Responsive Tasarım:** Chat ekranı, 3D avatar ve bilet paneli tüm mobil, tablet ve masaüstü çözünürlükleri için kusursuzca düzenlenir
- **Stabil WebSocket Altyapısı:** Bağlantı kopmalarına ve anlık durumlara karşı bağlantı durumunu doğrulayan ve hata onarımı sağlayan kararlı bir mekanizma barındırır
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

Tarayıcı seviyesinde `echoCancellation`, `noiseSuppression` ve `autoGainControl` etkin tutulur. Buna ek olarak mikrofon `AudioContext` içinde Avatarın ses grafiğine hiç bağlanmaz; yalnızca ölçüm için ayrı bir `micAnalyser` düğümünden geçirilir.

### Frekans Bandına Odaklanma

Ses seviyesi hesaplanırken tüm frekans spektrumu yerine yalnızca **insan konuşma bandı (300 Hz – 3400 Hz)** kullanılır. Bu yaklaşım, Avatarın hoparlörden sızan düşük frekanslı seslerinin ve ortam gürültüsünün yanlış kayıt tetiklemesini azaltır.

### Eşik Değerleri ve Ayarlar

Tüm sabitleri `frontend/js/audio.js` başında değiştirebilirsiniz:

| Sabit | Varsayılan | Açıklama |
| --- | --- | --- |
| `VAD_THRESHOLD` | `15` | Normal sessizlikte kayıt başlatma eşiği (0-255) |
| `BARGE_IN_THRESHOLD` | `12` | Avatar konuşurken barge-in eşiği (daha hassas) |
| `SILENCE_DURATION_MS` | `1000` | Bu kadar sessizlik → kayıt biter, STT'ye gider |
| `MIN_SPEECH_MS` | `300` | Daha kısa ses → gürültü olarak atlanır |

> **İpucu:** Gürültülü bir ortamda kullanıyorsanız `VAD_THRESHOLD` ve `BARGE_IN_THRESHOLD` değerlerini 5-10 puan artırın. Avatar çok erken kesiyorsa `SILENCE_DURATION_MS`'i 1300-1500'e çıkarın.

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
| **3D Avatar** | `js/avatar.js` | Three.js + @pixiv/three-vrm. VRM 1.0 / VRM 0.x formatında 3D karakter modeli. Göz kırpma, nefes alma, kafa hareketi, dudak senkronizasyonu animasyonları. Dinamik VRM yükleme (`loadVRM`) ve otomatik kamera hizalama (`_fitCameraToVRM`) destekli. ARKit blendshape sistemi, Rocketbox AA_VI viseme sistemi, AudioBuffer tabanlı gerçek zamanlı lip-sync. |
| **Ses & VAD** | `js/audio.js` | Web Audio API tabanlı ses çalma, VAD döngüsü, barge-in, eko koruması, MediaRecorder kayıt yönetimi. AudioBuffer genliği analizi ile ses ön-işleme. |
| **Sohbet** | `js/chat.js` | WebSocket bağlantısı, mesaj gönderme, streaming metin render, sohbet geçmişi UI, çok dilli destek. `resetChat()` ile avatar/dil değişiminde sohbet sıfırlama. |
| **Giriş Noktası** | `main.js` | Tüm modülleri birleştirir, UI olay dinleyicilerini bağlar. Mikrofon toggle → `toggleVAD()`. Avatar ayarları modalı (VRM yükleme, cinsiyet/ses seçimi). Cinsiyet seçici butonları (♀/♂). |
| **Stiller** | `style.css` | Responsive tasarım + VAD animasyonları (yeşil nabız: `vad-active`, hızlı nabız: `vad-active.recording`). Cinsiyet seçici buton stilleri. |

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
│   ├── avatar.png              # Chat baloncuğu avatar ikonu
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

### 4. Canlı Sunucu (Deployment)

Projenin canlı ortam dağıtımı (deployment) aktif olarak tamamlanmış olup şu platformlarda çalışmaktadır:

- **Frontend (İstemci / Arayüz):** Cloudflare Pages üzerinde barındırılmaktadır.
- **Backend (API ve WebSocket Servisleri):** Railway sunucuları üzerinde barındırılmaktadır.

#### Frontend Platform Geçişi: Vercel → Cloudflare Pages

Proje başlangıçta frontend katmanı **Vercel** üzerinde barındırılmaktaydı. Ancak **Nisan 2026'da Vercel**, üçüncü taraf bir AI aracı (Context.ai) üzerinden gerçekleştirilen bir **tedarik zinciri saldırısının (supply chain attack)** hedefi oldu. Saldırgan, ele geçirdiği bir Vercel çalışanının Google Workspace hesabı aracılığıyla iç sistemlere sızdı ve sınırlı sayıda müşteriye ait — `sensitive` işareti taşımayan — environment variable değerlerine erişti. Saldırı, Vercel'in deploy altyapısını veya `npm` paketlerini doğrudan etkilememiş olsa da olayın doğası gereği projede aşağıdaki önlemler alınmıştır:

1. **API Anahtar Rotasyonu:** Google Gemini API anahtarı yenilenmiştir.
2. **Backend Secret Rotasyonu:** Railway üzerindeki tüm environment variable'lar güncellenmiş ve eski değerler geçersiz kılınmıştır.
3. **Platform Geçişi:** Frontend, ek bir güvenlik katmanı olarak **Vercel'den Cloudflare Pages'e** taşınmıştır.

**Neden Cloudflare Pages?**

| Kriter | Açıklama |
| --- | --- |
| **Edge Network Avantajı** | Cloudflare'in global CDN altyapısı, özellikle Türkiye'deki son kullanıcıların Railway üzerinde barındırılan backend'e açtığı WebSocket bağlantılarında daha düşük gecikme süresi (latency) sağlar. |
| **Bandwidth Limiti Yok** | Vercel'in ücretsiz (Hobby) planındaki 100 GB/ay bandwidth kısıtlamasına karşılık Cloudflare Pages, kişisel projeler için herhangi bir bandwidth limiti uygulamaz. Bu, sesli etkileşim sırasında oluşan yüksek trafik için kritik bir avantajdır. |
| **Yerleşik DDoS Koruması** | Cloudflare'in standart altyapısının bir parçası olarak frontend katmanına ek bir güvenlik katmanı sağlanır. |
| **Build Performansı** | Statik frontend dağıtımı (Vanilla JS) için optimize edilmiş, hızlı bir build pipeline'ı sunar. |

> **Not:** Proje, Vercel tarafından doğrudan etkilenen müşteriler arasında listelenmemiştir; ancak güvenlik prensibi gereği etkilenmiş varsayılarak önlem alınması tercih edilmiştir.

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
| **Unity 6 LTS** | 6000.x | Karakter düzenleme + VRM export ortamı (geliştirme süreci) |
| **UniVRM** | 0.131.0 (VRM 1.0) | Unity → VRM 1.0 export paketi |
| **Microsoft Rocketbox** | MIT | Gerçekçi insan avatar kütüphanesi (115 karakter) |
| **Cloudflare R2** | Object Storage | VRM dosyalarının barındırılması (egress free, CDN-backed) |

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

## 🎭 3D Avatar Sistemi — Detaylı Açıklama

### Karakter Modelleri

Proje, **anime stilinde stilize avatardan profesyonel ve gerçekçi insan modeline** geçiş yapmıştır. Otobüs şirketi müşteri temsilcisi bağlamına daha uygun, **"insanla konuşuyor" hissi** veren karakterler kullanılmaktadır.

| Model | Dosya | Format | Kaynak | Açıklama |
| --- | --- | --- | --- | --- |
| **Kadın Asistan** | `models/avatar.vrm` | VRM 1.0 | Microsoft Rocketbox (Female_Adult_01) | Varsayılan karakter, kadın TTS sesi |
| **Erkek Asistan** | `models/Male_Adult_11_facial.vrm` | VRM 0.x | Microsoft Rocketbox (Male_Adult_11) | Erkek karakter, erkek TTS sesi |

Kullanıcı, avatar panelinin alt kısmındaki ♀/♂ butonlarıyla karakterler arasında geçiş yapabilir. Geçişte sohbet geçmişi otomatik sıfırlanır.

**VRM 0.x Uyumluluğu:** `VRMUtils.rotateVRM0()` ile VRM 0.x modeller otomatik olarak kameraya dönük hale getirilir. Yükleme sonrasında `vrm.scene.position.set(0,0,0)` ile pozisyon sıfırlanarak `_fitCameraToVRM` doğru hizalamayı yapar.

---

### VRM Modellerinin Barındırılması: Cloudflare R2 Object Storage

Karakter VRM dosyaları (~46 MB her biri) frontend bundle'a dahil edilmek yerine **Cloudflare R2 object storage** üzerinde barındırılmaktadır. Bu mimari karar, deploy sürecini ve son kullanıcı deneyimini optimize etmek amacıyla alınmıştır.

```text
     [Cloudflare Pages]                    [Cloudflare R2 Bucket]
          │                                       │
          │  HTML/CSS/JS bundle                   │  avatar.vrm (46 MB)
          │  (~500 KB)                            │  Male_Adult_11_facial.vrm
          │                                       │
          ▼                                       ▼
     [Browser] ─── fetch('https://pub-xxx.r2.dev/avatar.vrm') ───▶
                        (CORS: AllowedOrigin = Pages domain)
```

**Neden Cloudflare R2?**

| Kriter | Cloudflare R2 | AWS S3 / GCS |
| --- | --- | --- |
| **Egress ücreti** | **Ücretsiz** — limit yok | $0.09/GB (S3 Standard) |
| **Free tier** | 10 GB depolama, 1M Class A op/ay, 10M Class B op/ay | 5 GB / 12 ay |
| **CDN entegrasyonu** | Otomatik (300+ edge node) | CloudFront ayrı yapılandırma |
| **Cloudflare Pages uyumu** | Native (aynı ekosistem) | Cross-cloud tercih edilirse uygundur |
| **Public access** | `pub-xxx.r2.dev` URL'i otomatik | Bucket policy + presigned URL |

**Bu mimarinin avantajları:**

1. **Hızlı Frontend Deploy:** Cloudflare Pages bundle'ı ~500 KB olarak kalır; her commit'te 100 MB'lık VRM dosyaları yeniden yüklenmez. Build süresi <30 saniye.
2. **Edge Cache:** R2 dosyaları Cloudflare'in 300+ edge node'undan servis edilir; Türkiye'deki kullanıcılar için tipik latency <50 ms.
3. **Sıfır Egress Maliyeti:** Avatar her ziyaretçiye 46 MB veri transferi anlamına gelir; R2'de bu maliyet sıfırdır.
4. **Karakter Eklemenin Kolaylığı:** Yeni bir VRM dosyası eklemek için dashboard'dan upload + `AVATAR_URLS` objesine bir satır yeterli; deploy gerekmez.

**CORS Yapılandırması:**

R2 bucketının CORS policy'si, sadece Cloudflare Pages domain'inden ve geliştirme sırasında localhost'tan erişime izin verir:

```json
{
  "AllowedOrigins": [
    "https://<project>.pages.dev",
    "http://localhost:3000"
  ],
  "AllowedMethods": ["GET", "HEAD"],
  "AllowedHeaders": ["*"],
  "MaxAgeSeconds": 3600
}
```

**Frontend Konfigürasyonu:**

Tüm VRM URL'leri `frontend/js/avatar.js` dosyasında **tek bir kaynaktan** yönetilir:

```javascript
export const AVATAR_URLS = {
    female: 'https://pub-xxx.r2.dev/avatar.vrm',
    male:   'https://pub-xxx.r2.dev/Male_Adult_11_facial.vrm',
};
export const DEFAULT_AVATAR = AVATAR_URLS.female;
```

Bu yaklaşım, hard-coded URL'lerin kod tabanında dağılmasını önler ve yeni karakter eklemeyi tek satır değişiklikle mümkün kılar.

---

### Karakter Üretim Pipeline'ı: Microsoft Rocketbox → Unity → VRM

Karakter modelleri **sıfırdan ücretsiz olarak** üretilmiştir. Hazır anime stili VRM modeller (VRoid Studio, Booth.pm vb.) yerine, gerçekçi insan modeli üretmek için aşağıdaki uçtan uca pipeline kurulmuştur:

```text
[1] Microsoft Rocketbox Repository (MIT Lisans)
      │  115 gerçekçi avatar, FBX formatında
      ▼
[2] Unity 6 LTS + UniVRM (VRM 1.0 Paketi)
      │  Avatar projeye import edilir
      ▼
[3] Material → MToon10 Shader Dönüşümü
      │  URP/Lit → VRM10/MToon10 (VRM ile uyumlu)
      ▼
[4] Texture Read/Write Etkinleştirme
      │  PNG'ye encode edilebilmesi için
      ▼
[5] Humanoid Rig + Transform Düzeltme
      │  Rotation reset, +Z eksenine bakış
      ▼
[6] VRM 1.0 Export (Meta + Lisans)
      │  Title, Authors, Permission ayarları
      ▼
[7] frontend/models/ klasörüne taşıma
```

**Neden Microsoft Rocketbox?**

| Kriter | Açıklama |
| --- | --- |
| **Lisans (MIT)** | Akademik ve ticari kullanıma açık, atıf zorunlu değil |
| **Karakter Çeşitliliği** | 115 tam riglenmiş gerçekçi avatar (kadın/erkek, farklı yaş ve etnik köken) |
| **Blendshape Zenginliği** | Modelde **15 viseme + 48 ARKit FACS + 30 Vive Tracker** blendshape hazır gelir; lip-sync ve mimikler için ekstra modelleme gerekmez |
| **Performans** | Düşük poligonlu yapı sayesinde Three.js'te 60 FPS hedefi tüm cihazlarda korunur |
| **Profesyonel Görünüm** | Gerçek insan estetiği, otobüs şirketi müşteri temsilcisi bağlamıyla uyumlu |

**Pipeline Sırasında Karşılaşılan ve Çözülen Teknik Zorluklar:**

1. **"Texture is not readable" hatası:** Unity'nin varsayılan ayarı texture'ları GPU memory'sinde kilitler. UniVRM PNG'ye encode edebilmek için Read/Write Enabled işaretlenmesi gerekir.
2. **"Model needs to face the positive Z-axis" hatası:** Rocketbox FBX'leri 3ds Max kaynaklı olduğu için Unity'ye import edildiğinde rotation farklı eksende kalır; Transform sıfırlanması gerekir.
3. **"Unknown shader: URP/Lit" uyarısı:** URP shader'ları VRM standardına uyumsuzdur; manuel olarak VRM10/MToon10'a dönüştürülmüştür.
4. **Blendshape isimlendirme uyumsuzluğu:** Rocketbox modelinde viseme'ler `blendShape1.AA_VI_10_aa` gibi prefix'li isimlerle gelir; VRM 1.0 standart isimleri (`aa`, `ih` vb.) ile eşleşmez. Frontend'de **Expression Adapter** sistemi yazılarak hem VRM standardı hem de doğrudan blendshape isim alias'ları desteklenmiştir (bkz. `avatar.js` → `EXPRESSION_ALIASES`).
5. **Idle smile blendshape tespiti:** Modelin smile blendshape'leri (`AK_XX_MouthSmile*`) regex pattern (`/mouth.*smile|^smile|_smile/i`) ile dinamik olarak bulunur — model değişse bile çalışır.

Bu pipeline sayesinde, **hiçbir ücretli asset veya hazır VRM modeli kullanılmadan** profesyonel kalitede gerçekçi insan avatarları üretilebilmiştir.

---

### Lip-Sync Sistemi (Dudak Senkronizasyonu)

Sistem, **AudioBuffer tabanlı gerçek zamanlı fonem zamanlama** yöntemi kullanır. Frekans analizi yaklaşımına göre çok daha doğal ve sese tam senkronize dudak hareketleri sağlar.

**Çalışma Prensibi:**

```text
TTS Sesi (Base64 MP3)
    │
    ▼
audioBuffer = decodeAudioData()
    │
    ▼
RMS Genlik Analizi (20ms pencere)
    ├── Genlik < max×0.08 → Sessizlik → Ağız Kapalı (viseme 0)
    └── Genlik ≥ eşik → Konuşma → Fonem Ata
    │
    ▼
textToVisemeIndices(spokenText)
    │  (Her karakter → AA_VI index)
    ▼
speechFrameCount / totalSpeechFrames × phonemes.length
    │  (Sesli bölgelere fonemler eşit dağıtılır)
    ▼
setTimeout() zinciri → applyRocketboxViseme(index)
    │  (Değişim olduğunda timer eklenir — minimum timer sayısı)
    ▼
updateVisemeLerp(dt) → morphTargetInfluences[i]
    (Her frame ~55ms lerp ile yumuşak geçiş)
```

**Rocketbox AA_VI Viseme Seti (15 blendshape):**

| Index | Blendshape | Harfler |
| --- | --- | --- |
| 0 | AA_VI_00_Sil | Sessizlik, boşluk, noktalama |
| 1 | AA_VI_01_PP | b, p, m (dudak kapanır) |
| 2 | AA_VI_02_FF | f, v (diş-dudak) |
| 4 | AA_VI_04_DD | d, t, n, h |
| 5 | AA_VI_05_KK | k, g, ğ, c |
| 6 | AA_VI_06_CH | ş, ç, j |
| 7 | AA_VI_07_SS | s, z |
| 8 | AA_VI_08_nn | l |
| 9 | AA_VI_09_RR | r |
| 10 | AA_VI_10_aa | a, â |
| 11 | AA_VI_11_E | e |
| 12 | AA_VI_12_I | ı, i, y |
| 13 | AA_VI_13_O | o, ö |
| 14 | AA_VI_14_U | u, ü, w |

**Ses Bitiş Senkronizasyonu:** `source.onended` tetiklendiğinde `resetVisemeImmediate()` tüm blendshape değerlerini o frame'de sıfırlar — lerp beklenmez, ağız anında kapanır..

---

### Yüz İfadesi Sistemi (ARKit Blendshape'leri)

Rocketbox modelinin ARKit (AK_ prefix'li) blendshape'leri doğrudan kontrol edilerek dinamik yüz ifadeleri oluşturulur.

**Kaş Hareketleri (`_updateBrow`):**

| Durum | Blendshape | Değer | Frekans |
| --- | --- | --- | --- |
| Nötr | — | 0 | %35 |
| İç kaş kalkışı (düşünme/soru) | BrowInnerUp | 0.25–0.45 | %20 |
| Tam kaş kaldırma (vurgu) | BrowInnerUp + BrowOuterUp | 0.15–0.35 | %15 |
| Kaş çatma (odaklanma) | BrowDownLeft/Right | 0.12–0.22 | %12 |
| Hafif dalga | İç + Dış | 0.08 | %18 |

**Duchenne Gülümseme (`_updateCheekSquint`):**
Idle smile değeriyle orantılı olarak `CheekSquintLeft/Right` blendshape'leri aktif edilir. Gerçek bir gülümsemede göz altı kasları da çalışır — bu detay karakteri yapay görünmekten kurtarır.

**Göz Kırpma (`_startBlinking`):**

- Normal kırpma: ~95ms
- Yavaş kırpma (%20 ihtimalle): ~220ms — uykuluk/düşünceli an hissi
- Çift kırpma (%25 ihtimalle): arka arkaya iki hızlı kırpma

**Idle Gülümseme:** Konuşma yokken hedef değer 0.18 — dudak köşeleri hafifçe kalklar, dişler görünmez.

---

### Göz Bakış Yönü

VRM'in `lookAt` API'si yerine ARKit `EyeLook*` blendshape'leri direkt kontrol edilir. Bu yaklaşım, VRM mapping'i olmayan Rocketbox modellerde de çalışır.

```javascript
// Tüm EyeLookIn/Out/Up/Down blendshape'leri 0 = kameraya düz bakış
_setFace('eyeLookInL',  0); _setFace('eyeLookOutL', 0);
_setFace('eyeLookInR',  0); _setFace('eyeLookOutR', 0);
_setFace('eyeLookDownL', 0); _setFace('eyeLookDownR', 0);
_setFace('eyeLookUpL',  0); _setFace('eyeLookUpR',  0);
```

---

### Kafa Hareketi

Rastgele hedef seçip lerp ile gitme yaklaşımı yerine **üst üste sine dalgaları** kullanılır:

```javascript
_idleHead.y = Math.sin(elapsed * 0.19) * 0.022 + Math.sin(elapsed * 0.07) * 0.014;
_idleHead.x = Math.sin(elapsed * 0.13) * 0.012 + Math.sin(elapsed * 0.31) * 0.006;
```

Farklı frekanslı iki dalga üst üste binince Lissajous benzeri öngörülemeyen ama **tamamen akıcı** bir yol oluşur. Maksimum sapma ±2° — görünmez ama organik hissettirir. Konuşma/dinleme sırasında kafa yavaşça merkeze döner.

---

### Nefes Animasyonu

Sadece göğüs/üst göğüs kemikleri hafifçe öne açılır — vücut öne-geri gitmez:

```javascript
const b = (Math.sin(elapsed * 0.35) + 1) / 2; // 0–1 arası
cachedBones.upperChest.rotation.z = b * 0.012; // Öne şişme
cachedBones.chest.rotation.z      = b * 0.010;
```

Omuzlar hafifçe kalkıp iner, boyun çok minimal hareket eder.

---

### GLTF Animasyon Desteği

VRM dosyası içinde GLTF animasyonu varsa (`idle`, `breathing`, `stand`, `loop` adlarından biri) otomatik olarak `THREE.AnimationMixer` ile oynatılır:

```javascript
const mixer = new THREE.AnimationMixer(vrm.scene);
const clip  = gltf.animations.find(a => /idle|breathing|stand|loop/i.test(a.name));
mixer.clipAction(clip).play();
vrm._mixer = mixer;
```

---

## 🔄 Sohbet Sıfırlama (resetChat)

`chat.js`'deki `resetChat()` fonksiyonu şu durumlarda otomatik çağrılır:

| Tetikleyici | Sonuç |
| --- | --- |
| ♀ → ♂ geçişi | Sohbet temizlenir, yeni karakterle fresh start |
| ♂ → ♀ geçişi | Aynı şekilde |
| TR → EN geçişi | Sohbet temizlenir, İngilizce hoş geldin mesajı gösterilir |
| EN → TR geçişi | Sohbet temizlenir, Türkçe hoş geldin mesajı gösterilir |

`resetChat()` şunları yapar:

- `stopAudio()` → Avatar susturulur
- `isSending = false` → Sıkışmış istek kilidi açılır.
- `chatHistory.length = 0` → Backend geçmişi sıfırlanır
- `historyList.innerHTML = ''` → Ekran temizlenir
- Seçili dilde hoş geldin mesajı yeniden render edilir

---

## 🎨 UI Değişiklikleri

### "Müşteri Asistanı" Başlığı

Avatarın üzerinde görünen başlık, chat panelinin sol üst köşesine (`chat-header`) taşındı. Avatar alanı temiz kaldı.

### Cinsiyet Seçici Butonlar

Avatar panelinin alt ortasında ♀ ve ♂ butonları eklendi:

```html
<div class="gender-switcher">
    <button class="gender-btn active" id="gender-female">♀</button>
    <button class="gender-btn"         id="gender-male">♂</button>
</div>
```

Aktif buton beyaz çerçeve + blur arka plan ile vurgulanır. Geçiş anında sohbet otomatik sıfırlanır ve ilgili TTS sesi (kadın/erkek) yüklenir.

---

## 📦 Güncellenmiş Backend TTS

`tts_service.py`, Edge-TTS `stream()` çıktısındaki `WordBoundary` event'lerini toplar ve frontend'e iletir:

```python
elif ctype == "WordBoundary":
    offset_ms   = int(chunk.get("offset",   0)) // 10_000  # 100ns → ms
    duration_ms = int(chunk.get("duration", 0)) // 10_000
    word_text   = chunk.get("text", "")
    word_boundaries.append([offset_ms, duration_ms, word_text])
```

WordBoundary verisi mevcutsa frontend bunu kullanır; yoksa `AudioBuffer` tabanlı fallback devreye girer. Her iki durumda da lip-sync çalışır.

---

Bu proje, yapay zekâ destekli konuşma arayüzlerinin gerçek dünya uygulamalarındaki potansiyelini göstermek amacıyla geliştirilmiştir.

---

## 📄 Lisans

Bu proje akademik amaçlı geliştirilmiştir.
