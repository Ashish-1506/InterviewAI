# InterviewAI

InterviewAI is an AI-assisted interview preparation platform. Users can create
an account, upload a resume, choose an HR or technical interview, answer
questions in text or by voice, and review a generated performance report.

## Features

- JWT-based signup, login, and protected user workflows
- PDF and DOCX resume upload and parsing
- Resume-aware HR and technical interview question generation
- Real-time browser interviews over WebSockets
- Text answers and voice answers with speech-to-text transcription
- Optional text-to-speech playback for interviewer questions
- Candidate emotion and speech analysis
- AI code evaluation in an isolated local runner
- Interview scoring, conversation persistence, and performance reports
- Responsive React interface with validation, loading states, and accessibility

## Architecture

| Service | Technology | Responsibility | Local address |
| --- | --- | --- | --- |
| Frontend | React 18, Vite, React Router, Monaco Editor | Browser application and interview UI | `http://localhost:5173` |
| Node API | Node.js, Express, Mongoose, JWT | Authentication, users, resumes, and interview sessions | `http://localhost:4000` |
| AI service | Python, FastAPI, Pydantic | Resume parsing, interviewer engine, voice, emotion, scoring, reports, and code evaluation | `http://localhost:8000` |
| Database | MongoDB 7 | Users, interview sessions, conversations, and reports | `mongodb://localhost:27017` |

The AI service uses LangChain with OpenAI or Google Gemini, FAISS for the
question-bank index, Whisper for speech-to-text, and Coqui TTS when server-side
voice playback is enabled. Uploaded resumes are stored locally in development.

## Requirements

- Docker Desktop with the Linux engine enabled
- Git
- An OpenAI key or Gemini key for AI features

Node.js and Python are only required when running services outside Docker.

## Quick Start With Docker

From the repository root:

```powershell
Copy-Item .env.example .env
New-Item fastapi/.env -ItemType File -Force
```

Edit `.env` and set a strong `JWT_SECRET`, plus `OPENAI_API_KEY` or
`GEMINI_API_KEY`. The root `.env` and `fastapi/.env` are intentionally ignored
by Git. The Compose file supplies development defaults for the remaining
settings.

Start all services:

```powershell
docker compose up --build
```

Open `http://localhost:5173`, create an account, upload a PDF or DOCX resume,
and start an HR or technical interview. Stop the stack with:

```powershell
docker compose down
```

Use `docker compose down -v` only when you intentionally want to delete the
MongoDB volume and stored development data.

## Run Services Without Docker

Install dependencies in each service, then run them in separate terminals.

```powershell
cd frontend
npm install
npm run dev
```

```powershell
cd backend
npm install
npm run dev
```

```powershell
cd fastapi
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

For direct frontend development, copy `frontend/.env.example` to
`frontend/.env.local`. For direct backend development, copy
`backend/.env.example` to `backend/.env` and ensure MongoDB is running.

## Configuration

Important variables include:

- `JWT_SECRET`: signing key for authentication tokens; use a long random value
- `MONGODB_URI` and `MONGODB_DB`: database connection settings
- `OPENAI_API_KEY`, `OPENAI_MODEL`: OpenAI provider configuration
- `GEMINI_API_KEY`, `GEMINI_MODEL`: optional Gemini provider configuration
- `LLM_PROVIDER`: `openai` or `gemini`
- `STT_PROVIDER`, `WHISPER_MODEL`: speech-to-text configuration
- `TTS_PROVIDER`, `COQUI_MODEL`, `COQUI_GPU`: text-to-speech configuration
- `CORS_ORIGIN` and `CORS_ORIGINS`: allowed browser origins
- `VITE_API_BASE_URL`, `VITE_FASTAPI_BASE_URL`, `VITE_FASTAPI_WS_BASE_URL`: frontend service URLs

## Verification

Build the frontend before publishing changes:

```powershell
cd frontend
npm run build
```

Start the backend directly with:

```powershell
cd backend
npm run start
```

The backend currently exposes `dev` and `start` scripts; controller tests can
be run with the project's configured Node test runner when available. Python
tests can be run from the `fastapi` directory with `pytest` after the
requirements are installed.

## Production Notes

The production Compose file builds optimized images and serves the frontend on
port `8080`. Set production values for `MONGODB_URI`, `JWT_SECRET`,
`APP_ORIGIN`, `PUBLIC_BASE_URL`, and the selected LLM credentials through a
secret manager or deployment environment.

Do not expose the development FastAPI container publicly: local Compose mounts
the Docker socket to support isolated code evaluation. A production deployment
must use a separate authenticated code-runner service, private resume storage,
HTTPS, health checks, centralized logs, and monitoring.

## Repository Layout

```text
frontend/   React/Vite client
backend/    Express API and MongoDB models
fastapi/    FastAPI AI and analysis services
data/       Question bank and FAISS index under fastapi/
docker-compose.yml       Local development stack
docker-compose.prod.yml  Production-oriented container stack
```

## Author

InterviewAI was designed and developed by **Ashish**.
