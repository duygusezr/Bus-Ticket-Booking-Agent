# 🚌 ELA — Otobus Bileti Rezervasyon AI Asistani

**ELA (Electronic Leisure Assistant)**, Google Gemini 2.5 Flash, ElevenLabs TTS/STT ve Three.js VRM teknolojilerini birlestiren yeni nesil bir **yapay zeka destekli otobus bileti asistani**dir. Kullanici, form doldurmak yerine gercek zamanli 3D avatar ile dogal konusarak bilet arayip rezervasyon yapabilir.

> 🎥 **Demo:** [YouTube](https://www.youtube.com/watch?v=adMA9Ky3x6k)

---

## 📖 Proje Hakkinda

### Aciklama

ELA, web tabanli 3D avatar arayuzu uzerinden kullaniciyla gercek zamanli sesli diyalog kuran bir AI asistandir. Projenin temel amaci, otobus bileti arama ve rezervasyon surecini insanla konusur gibi kolaylastirmaktir.

### Cozulen Problemler

- **Karmasik Arayuz Yorgunlugu:** Uzun form ve filtre doldurma ihtiyacini azaltir.
- **Tarih Esnekligi:** "Onumuzdeki cuma bilet var mi?" gibi dogal ifadeleri anlayip tarih hesaplamasi yapar.
- **Eksik Veri Yonetimi:** Istek tarihine uygun sefer yoksa akilli alternatif tarih onerileri sunar.

### Hedef Kitle

- Hizli ve zahmetsiz bilet alma deneyimi isteyen yolcular
- Sesli kullanim tercih eden yasli veya teknolojiye mesafeli kullanicilar
- Portfoy veya ticari projelerine yeni nesil 3D asistan deneyimi eklemek isteyen gelistiriciler

---

## ✨ Ozellikler

- **Gemini Destekli AI:** Google Gemini 2.5 Flash, tool calling ve dogal dil yanitini tek akista yonetir.
- **Akilli Tarih Yonetimi:** Goreli zaman ifadelerini anlar, uygun sefer yoksa en yakin tarihleri onerebilir.
- **Dinamik Sehir Eslesmesi:** Turkce karakter normalizasyonu ile yazim farklarina daha dayaniklidir (`İ/I`, `ı/i`).
- **Deterministik Koltuk Dogrulama:** Son bot mesajinda `Bos koltuklar: ...` varsa, `5` veya `bes` gibi girdiler backend tarafinda dogrudan dogrulanir.
- **Gercek Zamanli 3D Avatar:** Three.js + VRM tabanli karakter, LLM duygu tokenlarina (ACT) gore tepki verir.
- **Uctan Uca Rezervasyon:** Sefer secimi, koltuk secimi, kimlik/iletisim bilgileri ve PNR onayi tek akis.
- **Semantik Onbellek (RAM):** Sik sorulan sorularda milisaniye seviyesinde hizli yanit.
- **Ses Girisi Normalizasyonu (TR):**
  - STT gurultulu metni temizler, rezervasyon acisindan anlamli bolumu secer.
  - Turkce sayi kelimelerini rakama cevirir (`bes` -> `5`, `on dokuz` -> `19`).
- Bolunmus sayi bloklarini uygun oldugunda birlestirir (ornek: `12 34 56 78 90` -> `1234567890`).
- **Turkce TTS Sayi Okuma:** Fiyatlar, uzun sayilar ve rakamlar seslendirme oncesi daha dogal Turkce okunacak sekle cevrilir.
- **TC Kimlik Dogrulama Kurallari:**
  - 11 hane ve sadece rakam
  - Ilk hane `0` olamaz
  - 10. hane checksum kontrolu
  - 11. hane checksum kontrolu
  - Son hane cift olmak zorunda

---

## 💻 Teknoloji Yigini

| Katman | Teknoloji |
| ------- | ----------- |
| **Backend** | Python 3.11+, FastAPI, Uvicorn, SQLite |
| **Frontend** | HTML5, Vanilla CSS (Glassmorphism), JavaScript (ES6+ Modules) |
| **3D Motor** | Three.js, @pixiv/three-vrm |
| **AI Motoru** | Google Gemini 2.5 Flash (Mantik, Tool Calling ve Sohbet) |
| **Ses** | ElevenLabs Scribe (STT), ElevenLabs TTS (Ses Sentezi) |
| **NLP** | Sentence-Transformers (Semantik Arama ve Cache) |

---

## ⚙️ Kurulum

### Gereksinimler

- Python 3.11 veya ustu
- [Google AI Studio](https://aistudio.google.com/) — Gemini API key
- [ElevenLabs](https://elevenlabs.io/) — TTS API key ve Voice ID

### Adim Adim Kurulum

1. **Projeyi klonlayin:**

    ```bash
    git clone https://github.com/duygusezr/Bus-Ticket-Booking-Agent.git
    cd Bus-Ticket-Booking-Agent
    ```

2. **Sanal ortam olusturun ve bagimliliklari yukleyin:**

    ```bash
    cd backend
    python -m venv venv

    # Windows
    .\venv\Scripts\activate

    # macOS / Linux
    source venv/bin/activate

    pip install -r requirements.txt
    ```

3. **`.env` dosyasini ayarlayin:**

    Ornek dosyayi kopyalayip anahtarlari doldurun:

    ```bash
    cp .env.example .env
    ```

    ```env
    GOOGLE_API_KEY=your_google_api_key_here
    ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
    ELEVENLABS_VOICE_ID=your_voice_id_here
    GEMINI_CHAT_MODEL=gemini-2.5-flash
    DEFAULT_LANG=tr
    PORT=8001
    ```

---

## 🚀 Kullanim

Proje kok dizininden `start.bat` ile kolayca baslatilabilir:

```powershell
# Proje kokunden
.\start.bat
```

Bu komut:

1. **Backend** sunucusunu `8001` portunda baslatir.
2. Yerel **Frontend** HTTP sunucusunu `3000` portunda baslatir.
3. Tarayicida otomatik olarak `http://localhost:3000` adresini acar.

### Ornek Diyalog

> **Kullanici:** *"Bursa'dan Istanbul'a uygun tarih var mi?"*
>
> **Ela:** *"En yakin seferleri kontrol ettim. 19 Nisan ve 30 Haziran tarihlerinde secenekler var. Hangisini incelemek istersiniz?"*

### Proje Akis Senaryosu

1. **Karsilama ve Niyet Alma**
   - Ela, kullanicidan kalkis, varis ve tarih bilgisini ister.

2. **Eksik Bilgi Tamamlama**
   - Kullanici kismi bilgi verirse (sadece rota veya sadece tarih), sadece eksik alan sorulur.

3. **Sefer Sorgulama**
   - Backend `get_bus_trips` araci ile seferleri arar.
   - Tam eslesme yoksa en yakin alternatif tarihler sunulur.

4. **Sefer Tarihi Secimi**
   - Kullanici bir tarihi sectiginde koltuk secim adimina gecilir.

5. **Koltuk Dogrulama**
   - Bos koltuklar listelenir.
   - Kullanici `5` veya `bes` gibi bir secim yaptiginda backend deterministik olarak `validate_seat_selection` ile kontrol eder.
   - Uygunsa bot onay sorusu sorar: **"Devam etmek istiyor musunuz?"**

6. **Yolcu Bilgileri Toplama**
   - Ad-soyad, T.C. Kimlik, telefon ve e-posta bilgileri alinir.

7. **TC Kimlik Dogrulama**
   - `validate_tc_number` ve arka planda checksum algoritmasi calisir.
   - 11 hane, ilk hane, 10./11. hane ve cift son hane kurallari kontrol edilir.

8. **Rezervasyon Olusturma**
   - `make_reservation` ile koltuk DB'den dusulur, PNR olusturulur, rezervasyon kaydi yazilir.

9. **Sesli ve Yazili Geri Donus**
   - Metin yaniti TTS ile seslendirilir.
   - Turkce sayilar TTS oncesi daha dogal okunacak sekle cevrilir.

10. **Konusma Bellegi ve Hizli Yanit**
   - Oturum ozeti memory servisine kaydedilir.
   - Benzer sorular semantic cache ile daha hizli cevaplanir.

---

## 🛠️ Konfigurasyon

`.env` icindeki temel degiskenler:

| Degisken | Aciklama |
| ---------- | ------------- |
| `GOOGLE_API_KEY` | Gemini API anahtari |
| `ELEVENLABS_API_KEY` | Ses sentezi ve ses tanima API anahtari |
| `ELEVENLABS_VOICE_ID` | ELA karakterinin ses kimligi |
| `GEMINI_CHAT_MODEL` | Kullanilan model (ornek: `gemini-2.5-flash`) |
| `CORS_ORIGINS` | Izinli frontend origin adresleri (virgulle ayrilmis) |

---

## 📁 Proje Yapisi

```text
Bus-Ticket-Booking-Agent/
├── index.html                  # Frontend (Glassmorphism UI)
├── main.js                     # 3D render, WebSocket ve sohbet mantigi
├── style.css                   # UI stilleri ve animasyonlar
├── ela_avatar.png              # Avatar ikonu
├── house_bg.jpg                # Arka plan gorseli
├── start.bat                   # Otomatik baslatma scripti
├── models/                     # VRM 3D model dosyalari
│
└── backend/
    ├── main.py                 # FastAPI giris noktasi
    ├── config.py               # System prompt ve ayarlar
    ├── requirements.txt        # Python bagimliliklari
    ├── .env.example            # Ortam degiskeni sablonu
    ├── bilet_sistemi.csv       # Sefer veritabani (CSV)
    │
    ├── routers/
    │   ├── chat.py             # Chat WebSocket endpoint
    │   ├── tts.py              # Text-to-Speech endpoint
    │   ├── stt.py              # Speech-to-Text endpoint
    │   └── emotion.py          # Duygu analizi endpoint
    │
    └── services/
        ├── llm_service.py      # Gemini entegrasyonu
        ├── tools.py            # Sefer, koltuk, TC ve rezervasyon mantigi
        ├── tts_service.py      # Ses sentez servisi
        ├── stt_service.py      # Ses tanima servisi
        ├── emotion_service_v2.py   # Metinden duygu analizi
        ├── memory_service.py   # Konusma ozeti/hafiza yonetimi
        └── semantic_cache_service.py # RAM tabanli semantik cache
```

---

## 🧪 Test

Hazir test scriptleri ile temel veritabani ve rezervasyon akislarini test edebilirsiniz:

```bash
cd backend

# Veritabani ve tool testleri
python test_db_tool.py

# Rezervasyon akisi testleri
python test_reservation.py
```

### Manuel Dogrulama Listesi (Onerilir)

1. **Koltuk Secimi Dayanikliligi**
   - `5` ve `bes` ile koltuk secimi deneyin.
   - Beklenen: Koltuk kabul edilir ve bot onay sorusu sorar.

2. **TC Girisi Dayanikliligi**
   - Noktalama/boslukla deneyin (`10000000146.` / `1 0 0 0 0 0 0 0 1 4 6`).
   - Beklenen: Backend normalize eder ve dogru checksum kontrolu yapar.
   - Sonu tek haneli gecersiz denemeler yapin.
   - Beklenen: `T.C. Kimlik numarası çift sayı ile bitmelidir.`

3. **STT Gurultu Filtreleme**
   - Arka plan sesli karisik bir cumle soyleyin.
   - Beklenen: Alakasiz parcaciklar azalir, rezervasyon niyeti korunur.

4. **Turkce TTS Sayi Okuma**
   - Fiyat ve uzun sayi iceren bot yanitlarini tetikleyin.
   - Beklenen: `1.191,38 TL` gibi degerler daha dogal okunur.

---

## 🚢 Dagitim

Proje su an agirlikli olarak lokal gelistirme icin hazirlanmistir. Uretim ortami icin:

1. **Backend:** Docker ile paketleyip Render, Heroku veya VPS'e deploy edin.
2. **Frontend:** Statik site olarak GitHub Pages veya Vercel'e yayinlayin.
3. **Onemli:** `.env` icindeki `CORS_ORIGINS` degerini production domain'inizle guncelleyin.

---

## 🤝 Katki

1. Repoyu fork'layin.
2. Yeni bir branch acin (`git checkout -b feature/yeni-ozellik`).
3. Degisiklikleri commit edin (`git commit -m "Yeni ozellik eklendi"`).
4. Branch'i push edin (`git push origin feature/yeni-ozellik`).
5. Pull Request acin.

---

## 📝 Lisans

Bu proje **MIT Lisansi** ile lisanslanmistir.

---

## ✉️ Iletisim

**Duygu Sezer** — [GitHub](https://github.com/duygusezr)

Portfoy Projesi: **ELA — Voice-Powered Digital Assistant Experience** 🎭