import os, re
from datetime import datetime, timezone
from io import BytesIO
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, desc
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from .database import Base, engine, get_db
from .models import Document, Analysis, Finding
from .schemas import AnalysisStart, GuidanceRequest, NegotiationRequest
from .services import extract_pdf, extract_docx, analyze_contract, LEGAL_SOURCES

Base.metadata.create_all(bind=engine)
app = FastAPI(title="ClauseLens API", version="1.0.0", description="Contract review prototype. Heuristic findings are not legal advice.")
origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(CORSMiddleware, allow_origins=[origin, "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "15"))

def analysis_payload(a: Analysis):
    return {
        "id": a.id, "document_id": a.document_id, "filename": a.document.filename,
        "requirements": a.requirements, "overall_risk": a.overall_risk, "summary": a.summary,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "findings": [{
            "id": f.id, "category": f.category, "severity": f.severity, "title": f.title,
            "explanation": f.explanation, "excerpt": f.excerpt, "page": f.page,
            "evidence_status": f.evidence_status, "recommendation": f.recommendation
        } for f in a.findings]
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ClauseLens API", "time": datetime.now(timezone.utc).isoformat()}

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = (file.filename or "").replace("\\", "/").split("/")[-1]
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in {"pdf", "docx"}:
        raise HTTPException(400, "Only PDF and DOCX files are supported.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_MB} MB upload limit.")
    try:
        text, pages = extract_pdf(data) if ext == "pdf" else extract_docx(data)
    except Exception as exc:
        raise HTTPException(422, str(exc))
    doc = Document(filename=filename[:255], file_type=ext, extracted_text=text, page_text={str(k): v for k, v in pages.items()})
    db.add(doc); db.commit(); db.refresh(doc)
    return {"document_id": doc.id, "filename": doc.filename, "file_type": ext, "characters_extracted": len(text), "page_references_available": bool(pages)}

@app.post("/api/analysis/start")
def start_analysis(payload: AnalysisStart, db: Session = Depends(get_db)):
    doc = db.get(Document, payload.document_id)
    if not doc:
        raise HTTPException(404, "Document not found. Upload the contract first.")
    requirements = [r.strip() for r in payload.requirements if r and r.strip()]
    page_text = {int(k): v for k, v in (doc.page_text or {}).items()}
    findings, overall, summary = analyze_contract(doc.extracted_text, page_text, requirements)
    analysis = Analysis(document_id=doc.id, requirements=requirements, overall_risk=overall, summary=summary)
    db.add(analysis); db.flush()
    for f in findings:
        db.add(Finding(analysis_id=analysis.id, **f))
    db.commit()
    saved = db.scalar(select(Analysis).options(joinedload(Analysis.document), joinedload(Analysis.findings)).where(Analysis.id == analysis.id))
    return analysis_payload(saved)

@app.get("/api/analysis/history")
def history(db: Session = Depends(get_db)):
    rows = db.scalars(select(Analysis).options(joinedload(Analysis.document), joinedload(Analysis.findings)).order_by(desc(Analysis.id)).limit(100)).unique().all()
    return [{"id": a.id, "filename": a.document.filename, "overall_risk": a.overall_risk, "created_at": a.created_at.isoformat() if a.created_at else None, "finding_count": len(a.findings)} for a in rows]

@app.get("/api/analysis/{analysis_id}")
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    a = db.scalar(select(Analysis).options(joinedload(Analysis.document), joinedload(Analysis.findings)).where(Analysis.id == analysis_id))
    if not a: raise HTTPException(404, "Analysis not found.")
    return analysis_payload(a)

@app.get("/api/analysis/{analysis_id}/findings")
def get_findings(analysis_id: int, db: Session = Depends(get_db)):
    a = db.get(Analysis, analysis_id)
    if not a: raise HTTPException(404, "Analysis not found.")
    return [{"id": f.id, "category": f.category, "severity": f.severity, "title": f.title, "explanation": f.explanation, "excerpt": f.excerpt, "page": f.page, "evidence_status": f.evidence_status, "recommendation": f.recommendation} for f in a.findings]

@app.post("/api/guidance/ask")
def guidance(payload: GuidanceRequest):
    q = payload.question.lower()
    relevant = [s for s in LEGAL_SOURCES if any(word in (s["name"] + " " + s["topic"]).lower() for word in re.findall(r"[a-z]{4,}", q))]
    if not relevant:
        relevant = LEGAL_SOURCES[:3]
    return {
        "answer": f"General information for {payload.jurisdiction}: the answer depends on the contract type, facts, applicable state rules, and current law. I can provide a starting point, but this prototype does not verify the latest legal text or provide a legal opinion. Identify the exact clause, parties, transaction, and requested outcome before drawing a conclusion. For important rights or financial exposure, consult a qualified lawyer.",
        "language": payload.language,
        "sources": relevant[:4],
        "disclaimer": "Educational information only; not legal advice. Sources are discovery starting points, not confirmation that a provision applies."
    }

@app.post("/api/clauses/negotiation")
def negotiation(payload: NegotiationRequest):
    draft = (
        f"**Negotiation objective:** {payload.goal.strip()}\n\n"
        "Suggested discussion wording (adapt to the transaction and obtain legal review):\n\n"
        f"“The parties will discuss revising the clause as follows: {payload.goal.strip()}. "
        "Any revised obligation should specify its scope, applicable time period, notice requirements, "
        "exceptions, and a practical process for resolving disagreements. The final wording will be agreed "
        "in writing by both parties.”\n\n"
        f"Tone requested: {payload.tone}. This is a negotiation starting point, not a substitute for tailored drafting."
    )
    return {"draft": draft, "disclaimer": "Have a lawyer adapt and review before signing."}

@app.get("/api/legal-sources/search")
def legal_sources_search(q: str = ""):
    query = q.strip().lower()
    results = [s for s in LEGAL_SOURCES if not query or query in (s["name"] + " " + s["topic"]).lower()]
    return {"results": results, "note": "Starter catalogue only. Check the current official text and commencement/applicability."}

@app.post("/api/legal-sources/verify")
def legal_sources_verify(payload: dict):
    # Intentionally never claims that a clause is illegal based only on keywords.
    clause = str(payload.get("clause_text", ""))[:8000]
    question = str(payload.get("legal_question", ""))[:2000]
    if not clause.strip() and not question.strip():
        raise HTTPException(400, "Provide clause_text or legal_question.")
    return {
        "status": "not_verified",
        "result": "This starter version cannot confirm legal validity or illegality. It has no live statute/case-law retrieval or legal review engine.",
        "next_steps": ["Identify the contract type and jurisdiction.", "Check the current official statute and relevant rules/case law.", "Confirm commencement and factual applicability.", "Ask a qualified lawyer to review the clause."],
        "candidate_sources": LEGAL_SOURCES[:4],
        "disclaimer": "Do not treat this result as a legal conclusion."
    }

@app.get("/api/reports/{analysis_id}/pdf")
def report_pdf(analysis_id: int, db: Session = Depends(get_db)):
    a = db.scalar(select(Analysis).options(joinedload(Analysis.document), joinedload(Analysis.findings)).where(Analysis.id == analysis_id))
    if not a: raise HTTPException(404, "Analysis not found.")
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    story = [Paragraph("ClauseLens — Contract Review Report", styles["Title"]), Spacer(1, 10)]
    story.append(Paragraph(f"Document: {a.document.filename}", styles["Normal"]))
    story.append(Paragraph(f"Overall heuristic flag: {a.overall_risk}", styles["Normal"]))
    story.append(Paragraph(a.summary, styles["BodyText"])); story.append(Spacer(1, 12))
    for i, f in enumerate(a.findings, 1):
        story.append(Paragraph(f"{i}. [{f.severity}] {f.title}", styles["Heading3"]))
        story.append(Paragraph(f"Category: {f.category} | Evidence status: {f.evidence_status} | Page: {f.page if f.page else 'Not available'}", styles["Normal"]))
        story.append(Paragraph(f.explanation.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), styles["BodyText"]))
        if f.excerpt:
            excerpt = f.excerpt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(f"Excerpt: {excerpt}", styles["BodyText"]))
        story.append(Paragraph(f"Suggested next step: {f.recommendation.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}", styles["BodyText"]))
        story.append(Spacer(1, 8))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Important: This report is generated by keyword heuristics. It is not a legal opinion, legal compliance certificate, or substitute for qualified legal advice. A missing finding does not mean a clause is safe.", styles["Italic"]))
    doc.build(story); buffer.seek(0)
    safe_name = f"clauselens_report_{analysis_id}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe_name}"'})
