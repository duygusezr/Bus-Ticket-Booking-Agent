# 🎭 ELA: 20-Year-Old Virtual AI Companion

Bu proje, gerçek zamanlı konuşma yeteneğine sahip, 3D VRM avatar destekli ve gelişmiş bir duygu sistemine sahip bir yapay zeka asistanıdır. **ELA**, sadece bir asistan değil, Duygu Sezer tarafından geliştirilmiş, dijital bir dünyada yaşayan ama gerçek bir insan gibi tepki veren bir arkadaştır.

---

## ✨ Öne Çıkan Özellikler

- **🤖 Akıllı Beyin:** Google'ın en yeni **Gemini 2.5 Flash** modeli ile yüksek hızda, zeki ve tutarlı sohbet.
- **🎭 Duygu & Hareket Sistemi (ACT):** LLM'den gelen özel `<|ACT:...|>` tokenları sayesinde ELA gerçek zamanlı olarak duygulanır ve hareket eder.
- **🗣️ Doğal Ses:** **ElevenLabs** (Premium) veya **Edge-TTS** (Ücretsiz) seçenekleriyle insan kadar gerçekçi seslendirme.
- **👁️ Canlı Avatar:**
  - **Nefes Alma:** Omuzların ve göğsün hareket ettiği doğal nefes simülasyonu.
  - **Boşta Hareket (Idle):** Karakterin beklerken doğal bakışları ve kafa hareketleri.
  - **Duygusal Tepkiler:** Mutlu, üzgün, düşünceli (`think`), meraklı (`curious`), şaşkın gibi 10'dan fazla ifade.
  - **Dudak Senkronizasyonu:** Sesin frekansına göre milisaniyelik hassasiyette ağız hareketleri.
- **🎙️ STT (Sesten Metne):** Whisper (OpenAI) ile mükemmel ses anlama yeteneği.

---

## 🛠️ Kurulum ve Çalıştırma

Proje iki ana bölümden oluşmaktadır: **Backend (Python)** ve **Frontend (Static HTML/JS)**.

### 1. Backend Kurulumu

1. **Dizine gidin:** `cd backend`
2. **Sanal ortam oluşturun ve aktif edin:**

    ```powershell
    python -m venv venv
    .\venv\Scripts\activate
    ```

3. **Bağımlılıkları yükleyin:**

    ```powershell
    pip install -r requirements.txt
    ```

4. **Yapılandırma (.env):**
    `.env` dosyasını açın ve şu anahtarları girin:

    ```dotenv
    GOOGLE_API_KEY=... (Gemini API Anahtarı)
    ELEVENLABS_API_KEY=... (ElevenLabs API Anahtarı)
    SYSTEM_PROMPT=... (ELA'nın kişiliği ve kuralları)
    GEMINI_CHAT_MODEL=gemini-2.5-flash
    ```

5. **Sunucuyu başlatın:**

    ```powershell
    .\venv\Scripts\python.exe main.py
    ```

### 2. Frontend Çalıştırma

Frontend tarafı herhangi bir derleme gerektirmez, sadece bir HTTP sunucusu ile açılmalıdır.

1. **VS Code:** "Live Server" eklentisini kullanabilirsiniz.
2. **Python ile:**

    ```powershell
    # Proje ana dizininde (avatar/)
    python -m http.server 8000
    ```

3. Tarayıcıda `http://localhost:8000` adresine gidin.

---

## 📂 Proje Yapısı

- `backend/`: FastAPI sunucusu ve AI servisleri.
  - `routers/`: Sohbet, Ses, Metin ve Duygu endpoint'leri.
  - `services/`: Gemini, ElevenLabs ve Whisper entegrasyonları.
- `main.js`: Three.js VRM kontrolü, ACT token işleme ve animasyon motoru.
- `models/`: Karakterin 3D model dosyası (`character.vrm`).
- `style.css`: Glassmorphism ve modern UI tasarımı.

---

## 🚀 Kişilik Kuralları (ELA)

ELA ile konuşurken şunları fark edeceksiniz:

- Kısa ve doğal cümleler kurar.
- Emojileri sese dönüştürürken bir yapay zekanın takılmaması için kullanmaz.
- Konuşmasına `<|ACT:...|>` ifadeleriyle duygu katar.
- Sıcak, meraklı ve sakin bir genç kadın gibi davranır.

Keyifli sohbetler! 🎭✨
