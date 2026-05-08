# 🚌 Bus Ticket Booking Agent

Sesli ve yazılı etkileşim destekli, gerçek zamanlı çalışan, 3D avatar tabanlı yapay zekâ destekli otobüs bileti rezervasyon sistemi.

Bu proje; doğal dil işleme, konuşma tanıma, metinden sese dönüştürme, WebSocket streaming altyapısı ve VRM tabanlı sanal karakter teknolojilerini bir araya getirerek klasik form tabanlı otobüs bileti rezervasyon deneyimini konuşma tabanlı bir yapay zekâ asistanına dönüştürmeyi amaçlamaktadır.

---

# 🚀 Proje Özeti

Geleneksel otobüs bileti rezervasyon sistemlerinde kullanıcıların:

* kalkış ve varış şehri seçmesi,
* tarih belirlemesi,
* uygun sefer araması,
* koltuk seçmesi,
* yolcu bilgilerini manuel doldurması,
* çok adımlı formlar arasında ilerlemesi

gerekmektedir.

Bu proje, bu süreci doğal bir konuşmaya dönüştürür.

Örneğin kullanıcı:

> “Yarın Ankara’dan İstanbul’a gitmek istiyorum.”

dediğinde sistem:

* kalkış ve varış şehirlerini algılar,
* tarihi işler,
* uygun seferleri arar,
* boş koltukları listeler,
* kullanıcıdan koltuk seçimi alır,
* yolcu bilgilerini toplar,
* gerekli doğrulamaları yapar,
* kullanıcıdan son onay alır,
* rezervasyonu oluşturur.

Tüm süreç sesli veya yazılı şekilde yönetilebilir.

---

# ✨ Temel Özellikler

* Gerçek zamanlı sesli konuşma desteği
* GPT-4o Mini tabanlı konuşma ve karar mekanizması
* ElevenLabs Scribe v2 tabanlı ana STT sistemi
* Gemini 2.5 Flash tabanlı yedek STT sistemi
* Microsoft Edge-TTS tabanlı ücretsiz seslendirme sistemi
* Rolling Summary Memory ile uzun konuşma yönetimi
* Absolute System Truth ile hallucination azaltma
* Deterministik koltuk, telefon, e-posta ve T.C. doğrulama
* Türkçe ve İngilizce çoklu dil desteği
* WebSocket tabanlı streaming iletişim
* VRM tabanlı 3D avatar desteği
* Dudak senkronizasyonu, göz kırpma ve idle animasyonlar
* Cloudflare Pages + Railway + Cloudflare R2 deployment mimarisi
* SQLite + PostgreSQL dual-write veritabanı mimarisi
* Semantic cache ile düşük gecikmeli tekrar yanıt desteği

---

# 🏗️ Sistem Mimarisi

```text
┌──────────────────────────────────────────────────────────────┐
│                         FRONTEND                             │
│                 Cloudflare Pages / Vanilla JS                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────┐     ┌────────────────────────────┐       │
│  │   Chat UI      │     │      3D Avatar System      │       │
│  │                │     │  Three.js + VRM Runtime    │       │
│  │ - Text Chat    │     │ - Lip Sync                 │       │
│  │ - Voice Input  │     │ - Blink                    │       │
│  │ - Streaming    │     │ - Idle Animation           │       │
│  │ - TR / EN      │     │ - ARKit Blendshape         │       │
│  └────────┬───────┘     └────────────┬───────────────┘       │
│           │                           │                       │
│           └──────────────┬────────────┘                       │
│                          │                                    │
│                 WebSocket / REST API                          │
│                          │                                    │
└──────────────────────────┼────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                          BACKEND                             │
│                    FastAPI + Railway                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                  Chat Router                         │    │
│  │                                                      │    │
│  │ - REST API                                           │    │
│  │ - WebSocket Streaming                                │    │
│  │ - Deterministic Validation                           │    │
│  │ - Absolute System Truth Injection                    │    │
│  └──────────────────────┬───────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                 GPT-4o Mini                          │    │
│  │                                                      │    │
│  │ - Conversation Management                            │    │
│  │ - Function Calling                                   │    │
│  │ - Reservation Flow                                   │    │
│  │ - Context Management                                 │    │
│  │ - Rolling Summary Memory                             │    │
│  └──────────────────────┬───────────────────────────────┘    │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                  Tool Functions                      │    │
│  │                                                      │    │
│  │ - get_bus_trips                                      │    │
│  │ - validate_seat_selection                            │    │
│  │ - validate_tc_number                                 │    │
│  │ - validate_phone_number                              │    │
│  │ - validate_email_address                             │    │
│  │ - make_reservation                                   │    │
│  └──────────────────────┬───────────────────────────────┘    │
│                         │                                    │
│        ┌────────────────┼──────────────────┐                 │
│        ▼                ▼                  ▼                 │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  STT       │  │ Memory       │  │ Semantic     │          │
│  │ Services   │  │ Service      │  │ Cache        │          │
│  ├────────────┤  ├──────────────┤  ├──────────────┤          │
│  │ ElevenLabs │  │ Rolling      │  │ MiniLM       │          │
│  │ Gemini     │  │ Summary      │  │ Cosine Sim.  │          │
│  └────────────┘  └──────────────┘  └──────────────┘          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                   TTS Service                        │    │
│  │                                                      │    │
│  │            Microsoft Edge-TTS Neural                 │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                        DATABASE                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  SQLite + PostgreSQL Dual-Write Architecture                 │
│                                                              │
│  - Trips Database                                            │
│  - Reservation Database                                      │
│  - CSV Backup Layer                                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

# 🔄 Veri Akışı

```text
Kullanıcı Konuşur
        │
        ▼
VAD / Ses Algılama
        │
        ▼
STT
ElevenLabs Scribe v2 / Gemini 2.5 Flash
        │
        ▼
Metin Normalizasyonu
number_utils.py
        │
        ▼
GPT-4o Mini
        │
        ▼
Function Calling
        │
        ▼
Rezervasyon Araçları
        │
        ▼
Yanıt Oluşturma
        │
        ▼
TTS
Microsoft Edge-TTS
        │
        ▼
3D Avatar Lip-Sync
        │
        ▼
Kullanıcıya Sesli ve Yazılı Yanıt
```

---

# 📈 Model ve Teknoloji Karşılaştırmaları

Proje geliştirme sürecinde farklı LLM, STT ve TTS sistemleri test edilmiş; maliyet, gecikme süresi, Türkçe doğruluğu ve gerçek zamanlı kullanım performansı karşılaştırılmıştır.

---

# 📊 Model Karşılaştırma Matrisi

| Modül                | Kullanılan Model     | Hız       | Doğruluk   | Tahmini Maliyet (1000 Karşılıklı Mesaj) |
| -------------------- | -------------------- | --------- | ---------- | --------------------------------------- |
| Zekâ / Chat & Bellek | GPT-4o Mini          | Çok hızlı | Çok yüksek | ~$0.01                                  |
| Duyma / Ana STT      | ElevenLabs Scribe v2 | Hızlı     | En yüksek  | ~$1.50                                  |
| Duyma / Yedek STT    | Gemini 2.5 Flash     | Hızlı     | Yüksek     | ~$0.05                                  |
| Konuşma / TTS        | Microsoft Edge-TTS   | Anlık     | Çok doğal  | Ücretsiz                                |

---

# 🤖 LLM Karşılaştırması

| Model            | Ortalama Gecikme | Türkçe Performansı | Tool Calling | Maliyet   | Sonuç                     |
| ---------------- | ---------------- | ------------------ | ------------ | --------- | ------------------------- |
| GPT-4o Mini      | ~1-2s            | Çok yüksek         | Çok iyi      | Çok düşük | Ana model                 |
| Gemini 2.5 Flash | ~1-3s            | Çok yüksek         | İyi          | Düşük     | Alternatif / STT fallback |
| Claude Sonnet    | ~2-4s            | Orta-yüksek        | İyi          | Yüksek    | Test edildi               |
| Gemini 1.5 Flash | ~1-2s            | Orta-yüksek        | İyi          | Düşük     | Önceki test modeli        |

---

# 🤖 Zekâ ve Karar Mekanizması — GPT-4o Mini

## Neden GPT-4o Mini Seçildi?

GPT-4o Mini;

* düşük gecikme süresi,
* güçlü function-calling yeteneği,
* yüksek Türkçe anlama başarısı,
* düşük token maliyeti,
* gerçek zamanlı konuşma akışına uygun yanıt süresi

nedeniyle ana konuşma modeli olarak tercih edilmiştir.

## Sistemdeki Görevleri

GPT-4o Mini sistemde şu görevleri yürütür:

* kullanıcının niyetini anlama,
* rezervasyon akışını yönetme,
* eksik bilgileri sırayla isteme,
* uygun tool/function çağrılarını yapma,
* tool sonuçlarını kullanıcıya doğal dille aktarma,
* konuşma geçmişini ve özet belleği kullanma,
* rezervasyon öncesi özet ve onay adımlarını yönetme.

## Ortalama Performans

| Özellik                 | Sonuç       |
| ----------------------- | ----------- |
| Ortalama Yanıt Süresi   | ~1-3 saniye |
| Function Calling        | Çok güçlü   |
| Türkçe Anlama           | Çok yüksek  |
| Uzun Konuşma Yönetimi   | Başarılı    |
| Gerçek Zamanlı Kullanım | Uygun       |
| Maliyet                 | Çok düşük   |

## Maliyet Değerlendirmesi

GPT-4o Mini, düşük maliyetli profesyonel LLM seçeneklerinden biridir.

Yaklaşık değerlendirme:

* 35.000 token kullanım maliyeti oldukça düşüktür.
* 1000 karşılıklı mesaj için tahmini maliyet yaklaşık ~$0.01 seviyesindedir.
* Rolling Summary Memory sayesinde her mesajda tüm geçmişin gönderilmesi engellenir.
* Semantic cache sayesinde benzer mesajlarda tekrar LLM çağrısı yapılması azaltılır.

---

# 🎙️ STT / Speech-to-Text Karşılaştırması

| Teknoloji              | Türkçe Doğruluğu | Hız   | Gerçek Zamanlı Kullanım | Hallucination Riski | Sonuç       |
| ---------------------- | ---------------- | ----- | ----------------------- | ------------------- | ----------- |
| ElevenLabs Scribe v2   | Çok yüksek       | Hızlı | Çok uygun               | Düşük               | Ana STT     |
| Gemini 2.5 Flash Audio | Yüksek           | Hızlı | Uygun                   | Düşük               | Yedek STT   |
| Whisper API            | Yüksek           | Orta  | Orta                    | Orta-yüksek         | Test edildi |
| Google STT             | Orta             | Hızlı | Uygun                   | Düşük               | Test edildi |

---

# 🎙️ Ana STT — ElevenLabs Scribe v2

ElevenLabs Scribe v2 sistemin ana konuşma tanıma servisidir.

## Avantajları

* Çok yüksek Türkçe doğruluğu
* Gürültülü ortamda daha stabil sonuç
* Düşük hallucination oranı
* Hızlı transkripsiyon
* Gerçek zamanlı konuşma deneyimine uygun performans
* Kullanıcının doğal ve eksik telaffuzlu konuşmalarında daha başarılı sonuç

## Dezavantajı

ElevenLabs Scribe v2, diğer STT alternatiflerine göre daha maliyetlidir. Buna rağmen sistemin en kritik noktası kullanıcının doğru anlaşılması olduğu için ana STT katmanında kullanılmıştır.

---

# 🎙️ Yedek STT — Gemini 2.5 Flash

Sistemde ElevenLabs servisinin başarısız olduğu durumlarda Gemini 2.5 Flash yedek STT olarak kullanılır.

## Kullanım Senaryoları

* ElevenLabs API hatası
* Kota problemi
* Bağlantı sorunu
* Servis kesintisi
* Geçici 401 / 429 / 5xx hataları

Bu sayede sistem tek bir STT servisine bağımlı kalmaz.

---

# 🎙️ STT Değerlendirmesi

Whisper tabanlı sistemlerde test sürecinde şu problemler daha sık gözlemlenmiştir:

* tekrar eden kelimeler,
* sayı bozulmaları,
* e-posta adreslerinde yanlış üretim,
* Türkçe özel isimlerde hata,
* kısa seslerde hallucination,
* kullanıcının söylemediği kelimeleri üretme.

ElevenLabs Scribe v2 ve Gemini 2.5 Flash, bu proje özelindeki konuşma akışında daha stabil sonuç vermiştir.

---

# 🔢 Sayısal Veri Normalizasyonu

Sistemde STT çıktılarının güvenilirliğini artırmak için özel bir sayı normalizasyon sistemi bulunmaktadır.

Örnek:

```text
"beş yüz otuz dört"
↓
534
```

Başka örnekler:

```text
"elli dört sıfır altı yüz yirmi on üç kırk"
↓
5406201340
```

```text
"altmış sekiz altmış üç doksan sekiz doksan altı altmış yedi sekiz"
↓
68639896678
```

Bu sistem sayesinde:

* telefon numaraları,
* T.C. kimlik numaraları,
* koltuk numaraları,
* tarih bilgileri,
* e-posta içindeki sayısal ifadeler

daha düşük hata oranıyla işlenir.

Bu yapı `number_utils.py` üzerinden yönetilir ve STT sonrası deterministik doğrulama katmanına veri sağlar.

---

# 🔊 TTS / Text-to-Speech Karşılaştırması

| Teknoloji                 | Doğallık   | Hız       | Maliyet  | Türkçe Kalitesi | Sonuç       |
| ------------------------- | ---------- | --------- | -------- | --------------- | ----------- |
| Microsoft Edge-TTS Neural | Yüksek     | Çok hızlı | Ücretsiz | Çok iyi         | Kullanıldı  |
| ElevenLabs TTS            | Çok yüksek | Orta      | Yüksek   | Çok iyi         | Test edildi |
| Google TTS                | Orta       | Hızlı     | Orta     | İyi             | Test edildi |

---

# 🔊 TTS Sistemi — Microsoft Edge-TTS

Microsoft Edge-TTS sistemin metinden sese dönüştürme servisidir.

## Neden Edge-TTS?

* Ücretsiz kullanım
* Çok düşük gecikme
* Neural voice desteği
* Doğal Türkçe telaffuz
* Gerçek zamanlı konuşma akışına uygun performans
* Türkçe ve İngilizce ses desteği
* Avatar lip-sync sistemiyle uyumlu ses üretimi

## Ortalama Performans

| Özellik                 | Sonuç      |
| ----------------------- | ---------- |
| İlk Ses Başlatma        | ~300-700ms |
| Doğallık                | Yüksek     |
| Gerçek Zamanlı Kullanım | Çok uygun  |
| Maliyet                 | 0$         |

---

# 💰 Ortalama API Maliyet Analizi

## Ortalama Bir Rezervasyon İşlemi

| Servis | Ortalama Kullanım |
| ------ | ----------------- |
| LLM    | ~3K-8K token      |
| STT    | ~10-30 saniye ses |
| TTS    | ~20-40 saniye ses |

## Tahmini Maliyet

| Teknoloji            | Ortalama İşlem Maliyeti |
| -------------------- | ----------------------- |
| GPT-4o Mini          | Çok düşük               |
| ElevenLabs STT       | Orta                    |
| Gemini 2.5 Flash STT | Çok düşük               |
| Edge-TTS             | Ücretsiz                |

Rolling Summary Memory ve semantic cache sistemi sayesinde token kullanımı önemli ölçüde azaltılmıştır.

---

# ⚡ Gerçek Zamanlı Performans Sonuçları

| Metrik             | Ortalama   |
| ------------------ | ---------- |
| İlk Ses Algılama   | ~16ms      |
| STT Süresi         | ~1-2s      |
| LLM Yanıt Süresi   | ~1-3s      |
| TTS Başlatma       | ~300-700ms |
| Semantic Cache Hit | ~5ms       |
| Avatar Render      | 60 FPS     |

Sistem gerçek zamanlı konuşma deneyimine uygun şekilde optimize edilmiştir.

---

# ☁️ Deployment ve Altyapı Kararları

Sistem; düşük gecikme, düşük maliyet, büyük dosya desteği, WebSocket uyumluluğu ve gerçek zamanlı yapay zekâ servislerini destekleyecek şekilde çok katmanlı bir deployment mimarisiyle tasarlanmıştır.

---

## 🌐 Frontend — Cloudflare Pages

Frontend katmanı Cloudflare Pages üzerinde barındırılmaktadır.

## Cloudflare Üzerinde Çalışan Bileşenler

* HTML dosyaları
* CSS dosyaları
* JavaScript istemcileri
* Chat arayüzü
* WebSocket istemcisi
* Three.js tabanlı 3D avatar render sistemi
* VAD ve ses kayıt istemcisi
* TR / EN dil seçim arayüzü

## Neden Cloudflare Pages?

Cloudflare Pages şu nedenlerle tercih edilmiştir:

* statik frontend dosyalarını hızlı servis etmesi,
* global CDN ağına sahip olması,
* Türkiye dahil farklı bölgelerde düşük gecikme sağlaması,
* ücretsiz static hosting sunması,
* DDoS koruması sağlaması,
* GitHub entegrasyonu ile hızlı deploy süreci sunması,
* Vanilla JS tabanlı frontend için build sürecini basit tutması.

Frontend yalnızca istemci tarafı dosyaları içerdiği için Cloudflare Pages bu katman için uygun bir çözümdür.

---

## 🤖 Backend — Railway

Backend katmanı Railway üzerinde Docker container olarak çalıştırılmaktadır.

## Railway Üzerinde Çalışan Backend Bileşenleri

* FastAPI uygulaması
* REST API endpointleri
* WebSocket `/ws/chat` endpointi
* STT endpointi
* TTS endpointi
* GPT-4o Mini entegrasyonu
* Function calling sistemi
* Rezervasyon araçları
* PostgreSQL bağlantısı
* Memory service
* Semantic cache katmanı
* Veritabanı işlemleri
* Environment variable yönetimi

## Neden Railway?

Backend tarafı yalnızca statik dosya servis etmez; sürekli çalışan bir Python uygulamasına ihtiyaç duyar.

Railway şu nedenlerle tercih edilmiştir:

* Docker desteği,
* FastAPI / Python uygulamaları için uygun runtime,
* WebSocket desteği,
* uzun süreli backend process çalıştırabilme,
* environment variable yönetimi,
* PostgreSQL entegrasyonu,
* hızlı deploy ve log takibi,
* API ve AI servisleri için uygun server ortamı.

Bu sistemde STT, TTS, LLM, tool calling, WebSocket ve veritabanı işlemleri gibi sürekli çalışan servisler bulunduğu için backend katmanı Railway üzerinde konumlandırılmıştır.

---

## 📦 Neden Vercel Kullanılmadı?

Projenin ilk aşamalarında Vercel test edilmiştir.

Ancak bu projenin ihtiyaçları klasik bir statik web sitesinden farklıdır.

Başlıca sebepler:

* uzun yaşayan WebSocket bağlantıları,
* sürekli streaming veri akışı,
* gerçek zamanlı STT / TTS işlemleri,
* Python tabanlı backend servisleri,
* büyük VRM dosyaları,
* environment variable yönetimi,
* backend loglarının detaylı izlenmesi,
* Railway PostgreSQL entegrasyonu ihtiyacı.

Bu nedenle sistem mimarisi şu şekilde ayrılmıştır:

```text
Cloudflare Pages → Frontend
Railway → Backend API / WebSocket
Cloudflare R2 → Büyük VRM dosyaları
```

Bu ayrım hem performans hem de yönetilebilirlik açısından daha stabil sonuç vermiştir.

---

## 🧊 Cloudflare R2 — VRM Dosya Depolama

3D avatar dosyaları Cloudflare R2 Object Storage üzerinde barındırılmaktadır.

## R2 Üzerinde Tutulan Dosyalar

* `.vrm` avatar dosyaları
* büyük binary model dosyaları
* runtime sırasında frontend tarafından fetch edilen 3D karakter assetleri

## Neden Cloudflare R2?

VRM dosyaları frontend bundle içerisine koymak için fazla büyüktür.

VRM dosyaları:

* büyük boyutlu,
* binary formatta,
* sık erişilen,
* CDN gerektiren

assetlerdir.

R2 sayesinde:

* düşük maliyetli object storage,
* CDN üzerinden hızlı erişim,
* global cache,
* düşük bandwidth maliyeti,
* frontend deploy boyutunu küçük tutma

sağlanmıştır.

---

## ⚠️ Cloudflare Pages Asset Limiti

Cloudflare Pages tek dosya için yaklaşık 25MB asset limiti uygulamaktadır.

Bazı VRM karakterleri:

```text
30MB+
```

boyutuna ulaştığı için sistem mimarisi değiştirilmiştir.

## Çözüm

VRM dosyaları frontend içerisine gömülmek yerine:

```text
Cloudflare R2 → CDN → Runtime Fetch
```

mimarisi ile ayrı servis edilmektedir.

Bu yapı sayesinde:

* deploy boyutu küçülmüş,
* yükleme süreleri iyileşmiş,
* CDN cache performansı artmış,
* frontend build limitleri aşılmıştır.

---

# 🗄️ Veritabanı Mimarisi

Sistem dual-write database mimarisi kullanmaktadır.

---

## SQLite

SQLite geliştirme ve lokal test ortamı için kullanılır.

## Avantajları

* hızlı kurulum,
* düşük maliyet,
* kolay debug,
* taşınabilirlik,
* lokal geliştirme için ideal olması.

---

## PostgreSQL

PostgreSQL production ortamında ana veritabanı olarak kullanılmaktadır.

## Avantajları

* eş zamanlı bağlantı desteği,
* daha yüksek güvenilirlik,
* daha iyi ölçeklenebilirlik,
* Railway entegrasyonu,
* production ortamı için daha uygun yapı.

---

## Dual-Write Architecture

Sistem bazı işlemlerde aynı anda:

* SQLite
* PostgreSQL

üzerine yazım yapabilmektedir.

Bu yapı:

* veri kaybı riskini azaltır,
* migration süreçlerini kolaylaştırır,
* fallback database desteği sağlar,
* lokal ve production ortamları arasında geçişi kolaylaştırır.

---

# 🧠 Yapısal Bellek Sistemi

Sistem uzun konuşmalarda bağlam kaybını önlemek için Rolling Summary Memory mimarisi kullanır.

---

## Rolling Summary Nedir?

Rolling Summary, konuşma geçmişinin tamamını her istekte modele göndermek yerine, geçmiş konuşmaları sürekli güncellenen kısa bir özet halinde tutan bellek yaklaşımıdır.

## Çalışma Mantığı

* Son mesajlar kısa süreli hafızada tam metin olarak tutulur.
* Belirli aralıklarla bu mesajlar özetlenir.
* Özet yeni konuşma bağlamına eklenir.
* Kritik rezervasyon bilgileri aynen korunur.
* Gereksiz eski sohbet detayları sadeleştirilir.

## Bellek Katmanları

| Katman                | Görev                               |
| --------------------- | ----------------------------------- |
| Kısa Süreli Hafıza    | Son mesajları tam metin saklar      |
| Rolling Summary       | Konuşmayı yoğun özet halinde taşır  |
| Absolute System Truth | Kritik rezervasyon verilerini korur |

## Korunan Veriler

* Sefer ID
* Tarih
* Kalkış / Varış
* Koltuk Numarası
* Kullanıcı Bilgileri
* Rezervasyon Durumu

Bu yapı sayesinde:

* token kullanımı düşer,
* uzun konuşmalarda bağlam korunur,
* sistem önceki rezervasyon bilgilerini unutmaz,
* hallucination riski azaltılır.

---

# 🧠 Semantic Cache Sistemi

Sistemde semantic cache katmanı bulunmaktadır.

## Kullanım Amacı

Benzer kullanıcı sorularında tekrar LLM çağrısı yapılmasını engellemek.

## Kullanılan Teknoloji

```text
SentenceTransformers MiniLM
+ Cosine Similarity
```

## Avantajları

* Daha düşük token maliyeti
* Daha hızlı yanıt
* Daha düşük API kullanımı
* Daha düşük gecikme

## Ortalama Cache Hit Süresi

```text
~5ms
```

---

# 🛡️ Hallucination Önleme Sistemi

LLM tabanlı sistemlerde modelin olmayan verileri üretme riski bulunmaktadır.

Bu projede bu riski azaltmak için Absolute System Truth yapısı kullanılır.

Her mesajda sistem tarafından doğrulanmış veriler modele tekrar enjekte edilir.

Örnek:

```text
[ABSOLUTE SYSTEM TRUTH]
STRICT_ID=42
STRICT_ROUTE=Ankara to Istanbul
STRICT_DATE=2026-03-22
STRICT_SEAT=5
```

Bu yapı sayesinde model:

* yanlış sefer ID üretmez,
* tarihi değiştirmez,
* güzergahı ters çevirmeye çalışmaz,
* koltuk bilgisini uydurmaz,
* PNR kodunu tool sonucu gelmeden üretmez.

---

# 🧾 Deterministik Doğrulama Katmanı

LLM’in her şeyi tek başına yorumlaması yerine kritik alanlarda deterministik doğrulama yapılır.

Doğrulanan alanlar:

* koltuk seçimi,
* T.C. kimlik numarası,
* telefon numarası,
* e-posta adresi,
* tarih çözümleme,
* sefer uygunluğu.

Bu yaklaşım sayesinde sistem daha güvenilir ve daha kontrollü çalışır.

---

# 👤 3D Avatar Sistemi

Sistem VRM tabanlı 3D avatar kullanır.

## Özellikler

* VRM 1.0 desteği
* Gerçek zamanlı lip-sync
* Göz kırpma sistemi
* Idle animasyon
* Nefes alma animasyonu
* ARKit blendshape desteği
* Viseme tabanlı konuşma senkronizasyonu
* Kadın / erkek avatar geçişi
* TTS sesiyle uyumlu karakter seçimi

---

# 🎭 Avatar Pipeline

```text
Microsoft Rocketbox
        │
        ▼
Unity 6 LTS
        │
        ▼
UniVRM Export
        │
        ▼
VRM 1.0
        │
        ▼
Cloudflare R2
        │
        ▼
Three.js Runtime
```

---

# 🎙️ Sesli Etkileşim ve VAD Sistemi

Sistem yalnızca butona basıp kayıt alma mantığıyla çalışmaz; sesli etkileşimi daha doğal hale getirmek için VAD kullanır.

## VAD Ne Yapar?

VAD, kullanıcının konuşmaya başlayıp başlamadığını ses seviyesine göre algılar.

Akış:

```text
Mikrofon aktif
        │
        ▼
Ses seviyesi ölçülür
        │
        ▼
Eşik aşılırsa kayıt başlar
        │
        ▼
Sessizlik algılanırsa kayıt durur
        │
        ▼
Ses STT servisine gönderilir
```

---

# 🔄 Barge-In Desteği

Avatar konuşurken kullanıcı araya girerse sistem avatarı susturur ve kullanıcının konuşmasını almaya başlar.

Bu yapı sayesinde kullanıcı, klasik IVR sistemlerindeki gibi uzun sesli yanıtların bitmesini beklemek zorunda kalmaz.

---

# 📦 Kullanılan Teknolojiler

| Teknoloji                   | Kullanım              |
| --------------------------- | --------------------- |
| FastAPI                     | Backend API           |
| WebSocket                   | Streaming iletişim    |
| Three.js                    | 3D render             |
| @pixiv/three-vrm            | VRM runtime           |
| OpenAI GPT-4o Mini          | Ana LLM               |
| ElevenLabs Scribe v2        | Ana STT               |
| Gemini 2.5 Flash            | Yedek STT             |
| Microsoft Edge-TTS          | TTS                   |
| SQLite                      | Lokal veritabanı      |
| PostgreSQL                  | Production veritabanı |
| Cloudflare Pages            | Frontend hosting      |
| Cloudflare R2               | VRM depolama          |
| Railway                     | Backend hosting       |
| Unity 6                     | Avatar düzenleme      |
| UniVRM                      | VRM export            |
| SentenceTransformers MiniLM | Semantic cache        |

---

# 📁 Proje Yapısı

```text
frontend/
├── index.html
├── style.css
├── main.js
├── js/
│   ├── avatar.js
│   ├── audio.js
│   └── chat.js
│
├── models/
│   └── *.vrm
│
└── assets/

backend/
├── main.py
├── config.py
├── requirements.txt
├── routers/
│   ├── chat.py
│   ├── stt.py
│   └── tts.py
│
├── services/
│   ├── llm_service.py
│   ├── stt_service.py
│   ├── tts_service.py
│   ├── memory_service.py
│   ├── semantic_cache_service.py
│   ├── number_utils.py
│   └── tools.py
│
└── database/
    ├── bilet_sistemi.db
    ├── rezervasyonlar.db
    ├── bilet_sistemi.csv
    └── rezervasyonlar.csv
```

---

# ⚙️ Kurulum

## Backend Kurulumu

```bash
cd backend

python -m venv venv

venv\Scripts\activate

pip install -r requirements.txt
```

## Ortam Değişkenleri

`.env` dosyası:

```env
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
ELEVENLABS_API_KEY=YOUR_ELEVENLABS_API_KEY
GEMINI_API_KEY=YOUR_GEMINI_API_KEY

OPENAI_CHAT_MODEL=gpt-4o-mini

DATABASE_URL=YOUR_POSTGRESQL_URL

PORT=8001
```

## Backend Çalıştırma

```bash
python main.py
```

## Frontend Çalıştırma

Frontend tarafı Live Server veya herhangi bir static server ile çalıştırılabilir.

---

# 🔐 Güvenlik Yaklaşımları

Sistem production odaklı güvenlik yaklaşımıyla tasarlanmıştır.

## Kullanılan Güvenlik Katmanları

* SHA-256 veri maskeleme
* Deterministik input validation
* Tool-call doğrulama sistemi
* Hallucination prevention injection
* Rolling Summary Memory
* Semantic cache izolasyonu
* Environment variable izolasyonu
* API fallback sistemi
* WebSocket hata toleransı
* Veritabanı bağlantı yönetimi
* PNR kodunu yalnızca başarılı tool sonucundan sonra gösterme

---

# 🎯 Projenin Amacı

Bu proje;

* konuşma tabanlı kullanıcı deneyimleri,
* gerçek zamanlı yapay zekâ sistemleri,
* multimodal insan-bilgisayar etkileşimi,
* sesli rezervasyon sistemleri,
* 3D avatar destekli müşteri asistanları

üzerine araştırma ve geliştirme amacıyla tasarlanmıştır.

---

# 📄 Lisans

Bu proje akademik ve araştırma amaçlı geliştirilmiştir.
