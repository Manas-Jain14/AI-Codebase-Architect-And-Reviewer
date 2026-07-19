# AI Codebase Architect & Engineering Reviewer

## PostgreSQL Setup

Use the existing database named `codebase_analyzer`. The application expects the following tables to already exist exactly as provided: `projects`, `analysis_reports`, `chat_sessions`, and `chat_messages`.

## Environment Variables

Create a local `.env` file from `.env.example` and set:

- `DATABASE_URL`
- `GEMINI_API_KEY`
- `BACKEND_URL`
- `UPLOAD_DIR`
- `EXTRACT_DIR`

## Start FastAPI

Run:

```bash
uvicorn app.main:app --reload
```

The backend runs at `http://localhost:8000` by default.

## Start Streamlit

Run:

```bash
streamlit run frontend/streamlit_app.py
```

The frontend runs at `http://localhost:8501` by default.

## Start ngrok

Run:

```bash
ngrok http 8501
```

Share the generated public URL with users.

## Typical Workflow

1. Start the FastAPI backend.
2. Start the Streamlit frontend.
3. Start ngrok for the Streamlit port.
4. Upload a ZIP file in the frontend.
5. Run analysis or chat with the codebase from the UI.
