# ClauseLens — Contract Risk Flagger

A hackathon-ready full-stack starter for reviewing contracts against user requirements and flagging potential risks. It includes a React + TypeScript frontend and a FastAPI + SQLite backend.

> **Important:** ClauseLens is an informational review aid, not a law firm or a substitute for legal advice. Its initial risk checks are rule-based heuristics, not a comprehensive legal opinion. Legal applicability depends on facts, contract type, jurisdiction, and current law. Have a qualified lawyer review consequential decisions.

## Features
- Upload PDF and DOCX contracts.
- Extract text with page references for PDFs; DOCX page references are intentionally not guessed.
- Compare contract text with user-defined requirements.
- Heuristic clause-risk checks for termination, liability, indemnity, payment, confidentiality, renewal, and dispute resolution.
- Persist uploaded document metadata and analysis findings in SQLite.
- View analysis history and download a PDF report.
- FastAPI interactive docs for live API testing.
- Input validation, upload size limit, and basic tests.

## Requirements
- Python 3.10+
- Node.js 18+

## Run locally

### 1. Backend
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Backend: http://127.0.0.1:8000  
Swagger UI: http://127.0.0.1:8000/docs

### 2. Frontend (new terminal)
```bash
cd frontend
npm install
npm run dev
```
Frontend: http://localhost:5173

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

## Test backend
```bash
cd backend
pytest -q
```
Use Swagger UI `/docs` to demonstrate the API to hackathon judges:
1. `GET /api/health`
2. `POST /api/documents/upload` with a PDF/DOCX
3. `POST /api/analysis/start` with the returned `document_id` and your requirements
4. `GET /api/analysis/{analysis_id}`
5. `GET /api/analysis/history`
6. `GET /api/reports/{analysis_id}/pdf`

## API endpoints
- `GET /api/health`
- `POST /api/documents/upload`
- `POST /api/analysis/start`
- `GET /api/analysis/{analysis_id}`
- `GET /api/analysis/{analysis_id}/findings`
- `GET /api/analysis/history`
- `POST /api/guidance/ask`
- `POST /api/clauses/negotiation`
- `GET /api/legal-sources/search`
- `POST /api/legal-sources/verify`
- `GET /api/reports/{analysis_id}/pdf`

## Configuration
Copy `.env.example` to `.env` if you want to configure settings. Never commit real API keys or confidential contracts. The current version works without an external LLM/API key; analysis is deliberately heuristic and transparent.

## Limitations
- Scanned/image-only PDFs need OCR; this starter reports when little/no text can be extracted.
- PDF page references are based on extracted PDF pages. DOCX has no reliable page numbers without a rendering engine, so findings use `page: null`.
- Legal-source catalogue is a small starter catalogue, not a live legal database. The app must not claim a clause is illegal solely from keyword matches.
- The guidance endpoint gives general educational information and asks users to verify current law and consult counsel.
- Authentication, multi-user access controls, malware scanning, production object storage, and comprehensive legal-source retrieval are not included. Do not deploy with sensitive documents without adding them.
