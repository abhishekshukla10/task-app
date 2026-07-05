# A2A Task App — Voice-Enabled Multilingual Task Manager

🔗 **Live Demo:** [task-app-ghfx.onrender.com](https://task-app-ghfx.onrender.com)

Speak your tasks in **Hindi or English** — fully hands-free task management with AI-powered intent extraction.

---

## Business Problem

Task tools require typing — slow, friction-heavy, and unusable while hands are occupied. Hindi-speaking teams face additional adoption barriers with English-only enterprise tools.

## Solution

A voice-first task manager: speak in Hindi or English, the browser transcribes, an LLM extracts the task structure (title, date, priority), and it's saved and displayed instantly.

## How It Works

```
Voice Input — Hindi/English via browser
        ↓
Web Speech API — speech → text in real time
        ↓
Groq AI (LLaMA) — extracts title, date, priority → structured JSON
        ↓
PostgreSQL — task persisted via SQLAlchemy
        ↓
Live UI — instant update with toast notification
```

## Key Technical Decisions

- **Web Speech API over server-side STT** — zero-latency browser-native transcription, no audio upload, no STT API cost
- **LLM as intent extractor, not chatbot** — Groq returns strict JSON (title/date/priority), keeping the voice-to-database path deterministic
- **Natural date parsing** — "kal" / "tomorrow" / "+2d" all resolve to dates through the LLM extraction layer
- **Render deployment with PostgreSQL** — full production-style stack: Flask app server, managed database, live URL

## Business Impact

- Zero-typing task capture · bilingual native support
- Full-stack AI delivery — voice input → AI extraction → database → live UI
- Accessible on mobile, no app install

## Stack

`Flask` `PostgreSQL` `Web Speech API` `Groq AI` `SQLAlchemy` `Python` `Render`

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add keys
flask run
```

**.env.example**
```
GROQ_API_KEY=
DATABASE_URL=
```

## Roadmap

→ Operations AI Assistant — team collaboration, project tracking, AI-powered daily standups, gamification
