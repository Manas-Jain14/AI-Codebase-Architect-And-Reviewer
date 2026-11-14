# 🏗️ AI Codebase Architect & Engineering Reviewer

An AI-powered codebase analysis platform that helps developers understand unfamiliar software projects, explore their architecture, identify important code structures, and interact with their codebase using natural language.

Upload a ZIP of a software project and get an AI-generated architecture review, interactive architecture visualizations, persistent reports, and contextual AI-powered conversations about the uploaded codebase.

---

## 📌 Overview

Understanding a large or unfamiliar codebase can be time-consuming, especially when developers need to identify entry points, understand dependencies, trace execution flows, or evaluate architectural decisions.

**AI Codebase Architect & Engineering Reviewer** addresses this problem by combining static code analysis with Large Language Models (LLMs).

The application extracts useful structural information from uploaded repositories, builds a structured project context, and uses Google's Gemini models through PydanticAI to generate architecture reviews and answer questions about the codebase.

It also provides interactive architecture visualizations and persistent project history.

## ✨ Key Features

### 1. 📦 ZIP-Based Project Upload
- Upload software projects as ZIP files.
- Safely extract uploaded repositories.
- Store project archives in Supabase Storage.
- Maintain project metadata in PostgreSQL.
- Select, refresh, and delete previously uploaded projects.

### 2. 🤖 AI-Powered Architecture Analysis
- Analyze uploaded codebases using Gemini.
- Generate structured architecture reviews.
- Understand the overall project structure.
- Identify architectural strengths and weaknesses.
- Generate actionable improvement recommendations and development roadmaps.
- Provide recruiter-oriented project evaluation insights.

### 3. 🏗️ Interactive Architecture Explorer
Explore the internal structure of an uploaded project through visual representations.

Includes:
- Project overview and structural metrics.
- File dependency visualization.
- Function call relationships.
- Database usage flow.
- Step-by-step execution flow.
- Mermaid-based architecture diagrams.
- Interactive diagram zooming, panning, and fit-to-screen controls.

### 4. 📋 Persistent Analysis Reports
- Store generated architecture reviews in PostgreSQL.
- Retrieve previously generated reports.
- View summaries, architecture descriptions, strengths, weaknesses, and recommended roadmaps.
- Keep analysis results associated with their respective projects.

### 5. 💬 Chat With Your Codebase
- Ask natural-language questions about uploaded projects.
- Generate contextual answers using Gemini.
- Use project structure and code context to support responses.
- Stream responses through Server-Sent Events (SSE).
- Maintain chat history in PostgreSQL.
- Identify files referenced in responses.
- Provide fallback responses when Gemini is temporarily unavailable.

### 6. ⚡ Optimized Frontend Requests
- Cache project lists during a Streamlit session.
- Cache architecture and report responses.
- Avoid unnecessary requests when switching between sections.
- Implement bounded retries for safe GET requests.
- Prevent duplicate ZIP upload submissions.
- Display clearer request and backend error messages.

---
🌐 Live Demo
https://ai-codebase-architect-frontend.onrender.com/

Note: The application is hosted on free-tier infrastructure. Initial loading may take some time while the services wake up. Availability is not guaranteed.

## 🧰 Tech Stack

| Component | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | Python, FastAPI |
| AI Framework | PydanticAI |
| LLM Provider | Google Gemini |
| AI Integration | Google GenAI SDK |
| Database | PostgreSQL |
| ORM | SQLAlchemy (Async) |
| Database Driver | asyncpg |
| File Storage | Supabase Storage |
| Architecture Visualization | Mermaid.js |
| API Communication | REST APIs |
| Chat Streaming | Server-Sent Events (SSE) |
| Deployment | Render |
| Version Control | Git & GitHub |

---

## 🏛️ System Architecture

The application follows a modular architecture with separate frontend, backend, database, AI, and file-storage responsibilities.

```mermaid
flowchart TD
    A[Developer] --> B[Streamlit Frontend]
    B -->|REST API Requests| C[FastAPI Backend]

    C --> D[Project Processing]
    D --> E[ZIP Extraction]
    E --> F[Static Code Analysis]
    F --> G[Project Context]

    G --> H[PydanticAI Agents]
    H --> I[Google Gemini]

    C --> J[SQLAlchemy Async ORM]
    J --> K[(PostgreSQL)]

    C --> L[Supabase Storage]
    L --> M[Project ZIP Archives]

    H --> N[Architecture Review]
    N --> K

    C --> O[Architecture Explorer Data]
    O --> B

    C --> P[Streaming Codebase Chat]
    P --> B

    K --> Q[Stored Reports and Chat History]
```

### Architecture Workflow

1. A developer uploads a ZIP archive through the Streamlit interface.
2. The frontend sends the archive to the FastAPI backend.
3. The backend processes and safely extracts the uploaded project.
4. The original ZIP archive is stored in Supabase Storage.
5. Project metadata is persisted in PostgreSQL.
6. Static analysis extracts useful code structure and builds a structured `ProjectContext`.
7. PydanticAI agents use the project context to interact with Gemini.
8. Architecture reviews are generated and stored in PostgreSQL.
9. Architecture data is exposed through backend APIs and visualized in the frontend.
10. Developers can retrieve reports and ask contextual questions through the chat interface.

---

## 🧠 AI and Analysis Design

The project combines deterministic code analysis with LLM-based reasoning.

**Static Analysis**

The backend examines the uploaded project and builds structured context containing information such as:

- Project files and folders.
- Python files.
- Imports and dependencies.
- Functions and classes.
- API routes.
- Database-related structures.
- File relationships and execution information.

**AI-Based Analysis**

The structured project context is passed to PydanticAI agents, which use Google Gemini to:

- Generate architecture reviews.
- Explain architectural decisions.
- Identify strengths and weaknesses.
- Recommend improvements.
- Answer contextual questions about the project.

Keeping structural analysis separate from LLM reasoning helps provide the AI with more organized and relevant information.

---

## 📁 Project Structure

The following shows the main application modules:

```text
AI-Codebase-Architect-And-Reviewer/
│
├── app/
│   ├── main.py
│   ├── routes.py
│   ├── database.py
│   ├── config.py
│   ├── storage.py
│   ├── agent.py
│   ├── architecture.py
│   ├── diagrams.py
│   ├── schemas.py
│   └── utils.py
│
├── frontend/
│   ├── streamlit_app.py
│   └── http_client.py
│
├── tests/
│   └── test_frontend_requests.py
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

### Important Modules

| Module | Responsibility |
|---|---|
| `app/main.py` | FastAPI application initialization and startup validation |
| `app/routes.py` | API endpoints, project processing, analysis, and chat |
| `app/database.py` | SQLAlchemy models, async database engine, and sessions |
| `app/config.py` | Application configuration and environment variables |
| `app/storage.py` | Supabase Storage integration |
| `app/agent.py` | PydanticAI agent integration |
| `app/architecture.py` | Architecture and code relationship analysis |
| `app/diagrams.py` | Mermaid diagram generation |
| `app/schemas.py` | Structured Pydantic data models |
| `app/utils.py` | ZIP extraction, project context building, and utilities |
| `frontend/streamlit_app.py` | Streamlit user interface |
| `frontend/http_client.py` | Frontend HTTP handling and request retries |

---

## ⚙️ Installation and Setup

Follow these steps to run the project locally.

### Prerequisites

Make sure you have:

- Python installed.
- Git installed.
- A Google Gemini API key.
- A Supabase project with a Storage bucket.
- A PostgreSQL database.

### 1. Clone the Repository

```bash
git clone https://github.com/Manas-Jain14/AI-Codebase-Architect-And-Reviewer.git
```

Navigate into the project:

```bash
cd AI-Codebase-Architect-And-Reviewer
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate it.

**Windows:**

```powershell
.venv\Scripts\activate
```

**Linux / macOS:**

```bash
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the repository root.

Use the following configuration:

```env
# PostgreSQL Database
DATABASE_URL=postgresql+asyncpg://username:password@host:5432/database_name

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key
MODEL_NAME=gemini-3.1-flash-lite

# Supabase Storage
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=your_supabase_secret_key
SUPABASE_BUCKET=project-files

# Backend Configuration
BACKEND_URL=http://localhost:8000

# Local File Directories (optional)
UPLOAD_DIR=uploads
EXTRACT_DIR=extracted_projects
```

**Environment Variable Description**

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `GEMINI_API_KEY` | Google Gemini API key |
| `MODEL_NAME` | Gemini model identifier |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SECRET_KEY` | Supabase secret key used by the backend |
| `SUPABASE_BUCKET` | Supabase Storage bucket name |
| `BACKEND_URL` | FastAPI backend URL used by Streamlit |
| `UPLOAD_DIR` | Temporary local ZIP upload directory |
| `EXTRACT_DIR` | Local extracted project directory |

**Important:**
- Create the Supabase Storage bucket before uploading projects.
- Use valid PostgreSQL connection credentials.
- Configure all required environment variables before starting the backend.
- Never commit your actual `.env` file, API keys, database passwords, or Supabase secret keys to GitHub.

### 5. Start the FastAPI Backend

Run the following command from the repository root:

```bash
uvicorn app.main:app --reload
```

The backend will be available at:

```text
http://localhost:8000
```

FastAPI documentation:

```text
http://localhost:8000/docs
```

The backend initializes its SQLAlchemy database tables during application startup.

### 6. Start the Streamlit Frontend

Open a second terminal, activate the virtual environment, and navigate to the repository root.

Run:

```bash
streamlit run frontend/streamlit_app.py
```

The frontend will be available at:

```text
http://localhost:8501
```

Make sure `BACKEND_URL` in your `.env` points to the running FastAPI backend.

---

## 🔌 API Endpoints

The FastAPI backend exposes REST endpoints for project management, analysis, architecture exploration, and chat.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload-project` | Upload and process a project ZIP |
| `GET` | `/projects` | Retrieve uploaded projects |
| `DELETE` | `/projects/{project_id}` | Delete a project and associated data |
| `GET` | `/analysis/{project_id}` | Generate an AI architecture review |
| `GET` | `/report/{project_id}` | Retrieve the latest stored report |
| `GET` | `/architecture/{project_id}` | Retrieve architecture analysis data |
| `GET` | `/architecture/{project_id}/file/{file_path}` | Retrieve file-level details |
| `GET` | `/architecture/{project_id}/function/{function_name}` | Retrieve function-level details |
| `POST` | `/chat/{project_id}` | Chat with a codebase |
| `POST` | `/chat/{project_id}/stream` | Stream contextual chat responses |

For interactive API exploration, start the backend and visit:

```text
http://localhost:8000/docs
```

---

## 🗄️ Database Design

The application uses PostgreSQL with SQLAlchemy's asynchronous ORM.

The primary database models are:

### Projects
Stores uploaded project metadata and references to ZIP archives.

### Analysis Reports
Stores AI-generated architecture reviews, including:

- Summary.
- Architecture description.
- Strengths.
- Weaknesses.
- Score field.
- Recommended roadmap.

### Chat Sessions
Maintains chat sessions associated with uploaded projects.

### Chat Messages
Stores user questions and corresponding assistant responses.

The application initializes its SQLAlchemy tables through `Base.metadata.create_all()` during backend startup.

---

## ☁️ Deployment Architecture

The application is designed with separately deployed frontend and backend services.

| Component | Deployment |
|---|---|
| Streamlit Frontend | Render |
| FastAPI Backend | Render |
| PostgreSQL Database | Neon |
| Project File Storage | Supabase |

The frontend communicates with the backend through HTTP requests.

The backend manages database operations, project processing, Gemini integration, and file-storage operations.

Deployment requires the corresponding environment variables to be configured in each service.

---

## 🧪 Testing

The repository includes automated tests for frontend request handling.

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

Run Python compilation checks:

```bash
python -m compileall -q frontend tests
```

Check Git whitespace errors:

```bash
git diff --check
```

---

## 🔐 Security Considerations

- API keys and database credentials are stored in environment variables.
- Secret configuration files should not be committed to version control.
- ZIP extraction uses a safe extraction utility to reduce archive path traversal risks.
- Project archives are stored separately from relational project metadata.
- Uploaded repositories should be treated as untrusted input.
- Production deployments should restrict access to secret credentials and database services.

---

## 🚀 Future Improvements

Potential areas for further development include:

- Support for additional programming languages.
- Deeper cross-language dependency analysis.
- More detailed code quality and maintainability insights.
- Improved architecture exploration and filtering.
- Background processing for large repository analysis.
- User authentication and project ownership.
- More comprehensive automated backend and integration tests.
- Improved observability and request monitoring.
- More advanced codebase navigation and contextual retrieval.

---

## 🎯 Project Goals

This project explores the practical integration of:

- Generative AI and LLM-powered agents.
- Static code analysis.
- Structured AI outputs using PydanticAI.
- Asynchronous backend development with FastAPI.
- Relational database design and persistence.
- Cloud-based file storage.
- Interactive software architecture visualization.
- Contextual AI-powered developer tools.

The goal is to make understanding unfamiliar codebases faster, more accessible, and more interactive.

---

## 👨‍💻 Author

**Manas Jain**

B.Tech — Computer Science and Engineering

Swami Keshwanand Institute of Technology, Jaipur

### GitHub Repository

[AI Codebase Architect & Engineering Reviewer](https://github.com/Manas-Jain14/AI-Codebase-Architect-And-Reviewer)

---


*Built to explore the intersection of software architecture, static analysis, and Generative AI.*