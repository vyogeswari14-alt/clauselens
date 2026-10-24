import re
from pathlib import Path
import fitz
from docx import Document as DocxDocument

MAX_TEXT_CHARS = 2_000_000

def extract_pdf(data: bytes):
    pages = {}
    with fitz.open(stream=data, filetype="pdf") as pdf:
        for idx, page in enumerate(pdf, start=1):
            pages[idx] = page.get_text("text").strip()
    text = "\n\n".join(f"[Page {n}]\n{body}" for n, body in pages.items() if body)
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("Extracted document text is too large.")
    if len(text.strip()) < 20:
        raise ValueError("No usable text found. This may be a scanned PDF; OCR is not enabled in this starter.")
    return text, pages

def extract_docx(data: bytes):
    import io
    doc = DocxDocument(io.BytesIO(data))
    chunks = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            chunks.append(" | ".join(cell.text.strip() for cell in row.cells))
    text = "\n".join(chunks)
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("Extracted document text is too large.")
    if len(text.strip()) < 20:
        raise ValueError("No usable text found in this DOCX.")
    return text, {}

def split_sentences(text: str):
    # Preserve paragraph/heading-sized chunks so excerpts remain readable.
    chunks = []
    for part in re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z0-9])", text):
        clean = re.sub(r"\s+", " ", part).strip()
        if len(clean) >= 8:
            chunks.append(clean)
    return chunks

def find_page(excerpt: str, page_text: dict):
    if not page_text:
        return None
    for page_num, content in page_text.items():
        if excerpt and excerpt[:45].lower() in content.lower():
            return int(page_num)
    return None

def analyze_contract(text: str, page_text: dict, requirements: list[str]):
    findings = []
    sentences = split_sentences(text)
    normalized = text.lower()

    # Requirements are matched by a transparent keyword overlap heuristic.
    for requirement in requirements:
        words = {w.lower() for w in re.findall(r"[a-zA-Z0-9]{4,}", requirement)}
        words -= {"must", "shall", "should", "with", "from", "that", "this", "have", "will", "contract"}
        matches = []
        if words:
            for sentence in sentences:
                overlap = words & set(re.findall(r"[a-zA-Z0-9]{4,}", sentence.lower()))
                if len(overlap) >= max(1, min(2, len(words))):
                    matches.append((sentence, len(overlap)))
        if not matches:
            findings.append({
                "category": "Requirement mismatch", "severity": "High",
                "title": f"Requirement not clearly found: {requirement[:90]}",
                "explanation": "A keyword-based scan did not find a clear matching passage. This is not proof that the requirement is absent; review the contract manually.",
                "excerpt": "", "page": None, "evidence_status": "needs_manual_review",
                "recommendation": "Locate the relevant clause and confirm the requirement is stated explicitly. If absent, request suitable wording."
            })
        else:
            best = sorted(matches, key=lambda x: x[1], reverse=True)[0][0]
            findings.append({
                "category": "Requirement match", "severity": "Low",
                "title": f"Possible match: {requirement[:90]}",
                "explanation": "A passage shares keywords with your requirement. Semantic equivalence and enforceability have not been verified.",
                "excerpt": best[:1200], "page": find_page(best, page_text),
                "evidence_status": "keyword_match",
                "recommendation": "Check the full clause and confirm it meets the intended commercial outcome."
            })

    rules = [
        ("liability", ["unlimited liability", "without limitation", "no limit on liability"], "High",
         "Potentially broad liability exposure",
         "The text contains wording that may create broad or uncapped liability. Context, carve-outs, and enforceability need review.",
         "Consider a negotiated liability cap, clearly defined exclusions, and proportionate carve-outs."),
        ("indemnity", ["indemnify", "indemnification", "hold harmless"], "Medium",
         "Indemnity obligation detected",
         "An indemnity clause can allocate substantial risk. This keyword flag does not determine whether the clause is unfair or unlawful.",
         "Review covered losses, third-party claims, causation, notice, defence control, caps, and exclusions."),
        ("termination", ["terminate at any time", "termination for convenience", "without cause"], "Medium",
         "Broad termination language detected",
         "The contract may permit termination without cause or on broad terms. Check whether notice and transition duties are balanced.",
         "Clarify notice period, accrued payments, cure rights, and transition obligations."),
        ("payment", ["late fee", "penalty", "interest at", "payment within"], "Low",
         "Payment terms detected",
         "Payment-related wording was found. Amounts, due dates, taxes, acceptance criteria, and late-payment consequences should be checked.",
         "Confirm invoice triggers, payment period, dispute procedure, tax treatment, and applicable statutory requirements."),
        ("confidentiality", ["confidential information", "non-disclosure", "confidentiality"], "Low",
         "Confidentiality clause detected",
         "Confidentiality language was found. Scope, exclusions, duration, permitted disclosures, and data handling need review.",
         "Define exclusions, permitted use, security safeguards, disclosure exceptions, and survival period."),
        ("renewal", ["automatically renew", "auto-renew", "automatic renewal"], "Medium",
         "Automatic renewal language detected",
         "An automatic-renewal mechanism may create unwanted continuation if notice windows are missed.",
         "Confirm renewal period, reminder/notice mechanics, deadline, and termination route."),
        ("dispute resolution", ["arbitration", "exclusive jurisdiction", "courts at"], "Low",
         "Dispute-resolution language detected",
         "A dispute-resolution clause was found. Seat/venue, governing law, procedure, costs, and court jurisdiction may matter.",
         "Confirm governing law, arbitration seat and venue where applicable, appointment procedure, and interim-relief rights."),
    ]
    for category, terms, severity, title, explanation, recommendation in rules:
        hits = [s for s in sentences if any(term in s.lower() for term in terms)]
        if hits:
            excerpt = hits[0][:1200]
            findings.append({
                "category": category.title(), "severity": severity, "title": title,
                "explanation": explanation, "excerpt": excerpt,
                "page": find_page(hits[0], page_text), "evidence_status": "heuristic_flag",
                "recommendation": recommendation
            })
    if not findings:
        findings.append({
            "category": "Review coverage", "severity": "Low",
            "title": "No configured heuristic triggers found",
            "explanation": "The starter checks did not detect configured keyword patterns. This does not establish that the contract is safe or legally compliant.",
            "excerpt": "", "page": None, "evidence_status": "limited_scan",
            "recommendation": "Review the full contract, verify legal requirements for the transaction, and seek legal advice for material commitments."
        })

    severity_rank = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    overall = max((f["severity"] for f in findings), key=lambda s: severity_rank.get(s, 0))
    summary = f"Generated {len(findings)} finding(s) using transparent keyword heuristics. Highest flagged severity: {overall}. This is not a legal compliance certification."
    return findings, overall, summary

LEGAL_SOURCES = [
    {"name": "Indian Contract Act, 1872", "topic": "contract formation, consent, consideration, breach and damages", "official_url": "https://www.indiacode.nic.in/"},
    {"name": "Arbitration and Conciliation Act, 1996", "topic": "arbitration agreements and dispute resolution", "official_url": "https://www.indiacode.nic.in/"},
    {"name": "Specific Relief Act, 1963", "topic": "specific performance and civil remedies", "official_url": "https://www.indiacode.nic.in/"},
    {"name": "Sale of Goods Act, 1930", "topic": "sale of goods and related contractual obligations", "official_url": "https://www.indiacode.nic.in/"},
    {"name": "Information Technology Act, 2000", "topic": "electronic records and electronic transactions", "official_url": "https://www.indiacode.nic.in/"},
    {"name": "Consumer Protection Act, 2019", "topic": "consumer protection where the relationship falls within the Act", "official_url": "https://www.indiacode.nic.in/"},
    {"name": "Micro, Small and Medium Enterprises Development Act, 2006", "topic": "certain payment protections for eligible micro and small enterprises", "official_url": "https://www.indiacode.nic.in/"},
]
