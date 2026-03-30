# 🚌 ELA — Bus Ticket Booking AI Agent

**ELA (Electronic Leisure Assistant)** is a next-generation **AI-powered Bus Ticket Booking Agent** that combines Google Gemini 2.5 Flash, ElevenLabs TTS/STT, and Three.js VRM technologies. Instead of filling out complex forms, users can book tickets through natural voice conversations with a real-time 3D avatar.

> 🎥 **Demo:** [YouTube](https://www.youtube.com/watch?v=adMA9Ky3x6k)

---

## 📖 About

### Description

ELA is an AI assistant that engages in real-time voice conversations with users through a web-based 3D avatar interface. The project's core goal is to make bus ticket search and reservation as easy and seamless as talking to a human.

### Problems Solved

- **Complex UI Fatigue:** Eliminates the need for users to fill in dozens of filters and forms.
- **Date Flexibility:** Understands natural expressions like *"Are there tickets for next Friday?"* and performs calendar calculations at the AI level.
- **Missing Data Management:** Instead of rejecting users when no trips are found for a given date, it suggests intelligent alternative dates.

### Target Users

- Passengers who want a fast, effortless ticket booking experience.
- Elderly or non-tech-savvy users who prefer voice commands.
- Developers looking to integrate a next-gen 3D assistant experience into their portfolio or commercial projects.

---

## ✨ Features

- **Gemini-Powered AI:** Google Gemini 2.5 Flash handles both intelligent tool calling and natural conversational responses in a single pass.
- **Smart Date Management:** Understands relative time expressions (tomorrow, next week, etc.) and automatically suggests future dates when no trips are available.
- **Dynamic City Matching:** Correctly matches routes even with misspellings via Turkish character normalization (İ/I, ı/i).
- **Real-Time 3D Avatar:** Three.js + VRM-based animated character that reacts to LLM emotions (ACT tokens).
- **End-to-End Reservation:** Complete ticketing flow — trip selection, seat assignment, ID & contact info collection, and PNR confirmation.
- **Semantic Cache (RAM):** Vector-based cache providing millisecond-level response times for frequently asked questions.

---

## 💻 Tech Stack

| Layer | Technology |
| ------- | ----------- |
| **Backend** | Python 3.11+, FastAPI, Uvicorn, SQLite |
| **Frontend** | HTML5, Vanilla CSS (Glassmorphism), JavaScript (ES6+ Modules) |
| **3D Engine** | Three.js, @pixiv/three-vrm |
| **AI Engine** | Google Gemini 2.5 Flash (Logic, Tool Calling & Conversation) |
| **Audio** | ElevenLabs Scribe (STT), ElevenLabs TTS (Voice Synthesis) |
| **NLP** | Sentence-Transformers (Semantic Search & Cache) |

---

## ⚙️ Setup

### Prerequisites

- Python 3.11 or higher
- [Google AI Studio](https://aistudio.google.com/) — a Gemini API Key
- [ElevenLabs](https://elevenlabs.io/) — TTS API Key and Voice ID

### Step-by-Step Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/duygusezr/Bus-Ticket-Booking-Agent.git
    cd Bus-Ticket-Booking-Agent
    ```

2. **Create a virtual environment and install dependencies:**

    ```bash
    cd backend
    python -m venv venv

    # Windows
    .\venv\Scripts\activate

    # macOS / Linux
    source venv/bin/activate

    pip install -r requirements.txt
    ```

3. **Configure the `.env` file:**

    Copy the example and fill in your API keys:

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

## 🚀 Usage

Start the project easily using the batch script in the root directory:

```powershell
# From the project root
.\start.bat
```

This will:

1. Start the **Backend** server on port `8001`.
2. Start a local **Frontend** HTTP server on port `3000`.
3. Automatically open your browser at `http://localhost:3000`.

### Example Dialogue

> **User:** *"Are there any available dates from Bursa to Istanbul?"*
>
> **Ela:** *"I checked the upcoming dates. There are trips available on April 19th and April 26th. Would you like me to look into one of them?"*

---

## 🛠️ Configuration

Key environment variables in `.env`:

| Variable | Description |
| ---------- | ------------- |
| `GOOGLE_API_KEY` | Gemini API key. |
| `ELEVENLABS_API_KEY` | API key for voice synthesis and speech recognition. |
| `ELEVENLABS_VOICE_ID` | Voice ID used for the ELA character. |
| `GEMINI_CHAT_MODEL` | AI model (e.g., `gemini-2.5-flash`). |
| `CORS_ORIGINS` | Allowed frontend origins (comma-separated). |

---

## 📁 Project Structure

```text
Bus-Ticket-Booking-Agent/
├── index.html                  # Frontend (Glassmorphism UI)
├── main.js                     # 3D Render, WebSocket & Chat Logic
├── style.css                   # Modern UI styles & animations
├── ela_avatar.png              # Avatar icon
├── house_bg.jpg                # Background image
├── start.bat                   # Auto-start script
├── models/                     # VRM 3D model files
│
└── backend/
    ├── main.py                 # FastAPI application entry point
    ├── config.py               # System prompts & settings
    ├── requirements.txt        # Python dependencies
    ├── .env.example            # Environment variable template
    ├── bilet_sistemi.csv       # Trip database (CSV)
    │
    ├── routers/
    │   ├── chat.py             # Chat WebSocket endpoint
    │   ├── tts.py              # Text-to-Speech endpoint
    │   ├── stt.py              # Speech-to-Text endpoint
    │   └── emotion.py          # Emotion analysis endpoint
    │
    └── services/
        ├── llm_service.py      # Gemini AI integration (Logic + Conversation)
        ├── tools.py            # Smart date & ticketing logic (Core)
        ├── tts_service.py      # Voice synthesis service
        ├── stt_service.py      # Speech recognition service
        ├── emotion_service_v2.py   # Emotion detection from text
        ├── memory_service.py   # Conversation memory management
        └── semantic_cache_service.py # RAM-based vector cache
```

---

## 🧪 Testing

Run the pre-built test scripts to validate the ticketing and date logic:

```bash
cd backend

# Database & Tool tests
python test_db_tool.py

# Reservation flow tests
python test_reservation.py
```

---

## 🚢 Deployment

The project is currently designed for local development. To deploy to production:

1. **Backend:** Dockerize and deploy on Render, Heroku, or a VPS.
2. **Frontend:** Serve as a static site via GitHub Pages or Vercel.
3. **Important:** Update `CORS_ORIGINS` in `.env` with your production domain.

---

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## 📝 License

This project is licensed under the **MIT License**.

---

## ✉️ Contact

**Duygu Sezer** — [GitHub](https://github.com/duygusezr)

Portfolio Project: **ELA — Voice-Powered Digital Assistant Experience** 🎭