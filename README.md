# Orbit Agent V2

A small conversational AI app powered by local Ollama Gemma 3.

## Requirements

- Python 3.11+
- Node.js 18+
- Ollama with `gemma3:latest`

## Run the backend

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The frontend uses `VITE_API_URL` if set, otherwise `http://localhost:8000`.

Check Ollama first with `ollama list`. Start it with `ollama serve` if needed. Normal messages make one streaming Ollama request. Arithmetic expressions use the safe calculator directly. Web-search requests require `TAVILY_API_KEY` and use live Tavily results followed by one streamed Gemma summary.

To configure search, copy `backend/.env.example` to `backend/.env` and set `TAVILY_API_KEY` to your Tavily key. Never commit that file.
