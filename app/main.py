import fitz  # PyMuPDF
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, Response
from app.services.pdf_reader_service import extract_text_with_ocr
from app.services.claude_service import extract_target_metadata, summarize_text, analyze_risks_pure_llm, handle_chatbot_query, check_compliance_pure_llm

# Inisialisasi aplikasi FastAPI agar dapat dideteksi oleh Uvicorn
app = FastAPI()


def _rtf_escape(text: str) -> str:
    # Escapes RTF special characters and normalizes newlines to \par
    if text is None:
        return ""
    escaped = (
        text.replace("\\", r"\\\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )
    escaped = escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\par ")
    return escaped

def extract_text_from_pdf(pdf_bytes: bytes) -> Optional[str]:
    """
    Menggunakan PyMuPDF untuk mengekstrak teks dari bytes PDF.
    """
    try:
        # Buka dokumen dari bytes
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            # Mengekstrak teks dari setiap halaman
            text += page.get_text()
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        # Jika PyMuPDF gagal, itu mungkin PDF yang di-scan dan perlu OCR (sebaiknya diatasi di luar hackathon)
        return None


# Endpoint sederhana untuk memastikan aplikasi berjalan
@app.get("/")
def read_root():
    rtf = r"{\rtf1\ansi \b ClausIA API\b0\par Status: ok}"
    return Response(content=rtf, media_type="text/rtf")


@app.post("/extract")
async def extract_pdf_text(
    request: Request,
    file: UploadFile | None = File(None),
    lang: str = "eng",           # default single language untuk kecepatan
    dpi: int = 100,               # render lebih rendah untuk kecepatan
    oem: int = 1,                 # LSTM only
    psm: int = 6,                 # assume a single uniform block of text
    max_pages: int | None = None, # batasi halaman jika diinginkan
    parallel: bool = True,        # proses paralel
):
    # Jika field "file" tidak terdeteksi oleh FastAPI (beberapa klien salah format),
    # coba ambil file pertama secara manual dari form-data.
    if file is None:
        form = await request.form()
        for key, value in form.multi_items():
            if hasattr(value, "filename") and value.filename:
                file = value  # type: ignore
                break

    if file is None:
        raise HTTPException(status_code=422, detail="Form-data must include a file field")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    text = extract_text_with_ocr(
        pdf_bytes,
        language=lang,
        dpi=dpi,
        oem=oem,
        psm=psm,
        max_pages=max_pages,
        parallel=parallel,
    )
    rtf = r"{\rtf1\ansi " + r"\b Extracted Text\b0\par " + _rtf_escape(text) + "}"
    return Response(content=rtf, media_type="text/rtf")


@app.post("/extract_metadata")
async def extract_metadata(
    request: Request,
    file: UploadFile | None = File(None),
    lang: str = "eng",
    dpi: int = 100,
    oem: int = 1,
    psm: int = 6,
    max_pages: int | None = None,
    parallel: bool = True,
):
    # Ambil file dari form-data (fallback manual bila perlu)
    if file is None:
        form = await request.form()
        for key, value in form.multi_items():
            if hasattr(value, "filename") and value.filename:
                file = value  # type: ignore
                break
    if file is None:
        raise HTTPException(status_code=422, detail="Form-data must include a file field")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    # 1) Ambil teks via OCR cepat
    text = extract_text_with_ocr(
        pdf_bytes,
        language=lang,
        dpi=dpi,
        oem=oem,
        psm=psm,
        max_pages=max_pages,
        parallel=parallel,
    )

    # 2) Kirim ke Claude untuk ekstraksi metadata terarah
    metadata = extract_target_metadata(text)
    import json as _json
    meta_json = _json.dumps({
        "external_company_name": metadata.get("external_company_name") or "",
        "contract_start_date": metadata.get("contract_start_date") or "",
        "contract_end_date": metadata.get("contract_end_date") or "",
        "contract_title": metadata.get("contract_title") or "",
    }, ensure_ascii=False)

    content_rtf = r"{\rtf1\ansi " + r"\b Extracted Text\b0\par " + _rtf_escape(text) + "}"
    return JSONResponse({"metadata": meta_json, "content": content_rtf})


@app.post("/summarize")
async def summarize(
    request: Request,
    file: UploadFile | None = File(None),
    lang: str = "eng",
    dpi: int = 100,
    oem: int = 1,
    psm: int = 6,
    max_pages: int | None = None,
    parallel: bool = True,
):
    # Ambil file dari form-data (fallback manual bila perlu)
    if file is None:
        form = await request.form()
        for key, value in form.multi_items():
            if hasattr(value, "filename") and value.filename:
                file = value  # type: ignore
                break
    if file is None:
        raise HTTPException(status_code=422, detail="Form-data must include a file field")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    # 1) OCR cepat
    text = extract_text_with_ocr(
        pdf_bytes,
        language=lang,
        dpi=dpi,
        oem=oem,
        psm=psm,
        max_pages=max_pages,
        parallel=parallel,
    )

    # 2) Ringkasan maksimal 5 kalimat
    summary = summarize_text(text, language_hint="id" if lang.startswith("ind") else "en")
    rtf = r"{\rtf1\ansi " + r"\b Summary\b0\par " + _rtf_escape(summary) + "}"
    return Response(content=rtf, media_type="text/rtf")


@app.post("/analyze_risk")
async def analyze_risk(
    request: Request,
    file: UploadFile | None = File(None),
    lang: str = "eng",
    dpi: int = 100,
    oem: int = 1,
    psm: int = 6,
    max_pages: int | None = None,
    parallel: bool = True,
):
    # Ambil file dari form-data (fallback manual bila perlu)
    if file is None:
        form = await request.form()
        for key, value in form.multi_items():
            if hasattr(value, "filename") and value.filename:
                file = value  # type: ignore
                break
    if file is None:
        raise HTTPException(status_code=422, detail="Form-data must include a file field")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    text = extract_text_with_ocr(
        pdf_bytes,
        language=lang,
        dpi=dpi,
        oem=oem,
        psm=psm,
        max_pages=max_pages,
        parallel=parallel,
    )

    result = analyze_risks_pure_llm(text)
    counts = result.get("summary_counts", {})
    header = rf"\b Risk Analysis\b0\par Counts — Low: {counts.get('Low',0)}, Medium: {counts.get('Medium',0)}, High: {counts.get('High',0)}\par "
    items = []
    for f in result.get("findings", []):
        line = (
            r"\par \b " + _rtf_escape(f.get("risk_type", "")) + r"\b0  - " + _rtf_escape(f.get("severity", "")) +
            r"\par \tab \b Kutipan:\b0 " + _rtf_escape(f.get("clause_text", "")) +
            r"\par \tab \b Alasan:\b0 " + _rtf_escape(f.get("rationale", "")) + r"\par "
        )
        items.append(line)
    rtf = r"{\rtf1\ansi " + header + "".join(items) + "}"
    return Response(content=rtf, media_type="text/rtf")


@app.post("/check_compliance")
async def check_compliance(
    request: Request,
    file: UploadFile | None = File(None),
    lang: str = "eng",
    dpi: int = 100,
    oem: int = 1,
    psm: int = 6,
    max_pages: int | None = None,
    parallel: bool = True,
):
    # Ambil file dari form-data (fallback manual bila perlu)
    if file is None:
        form = await request.form()
        for key, value in form.multi_items():
            if hasattr(value, "filename") and value.filename:
                file = value  # type: ignore
                break
    if file is None:
        raise HTTPException(status_code=422, detail="Form-data must include a file field")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    text = extract_text_with_ocr(
        pdf_bytes,
        language=lang,
        dpi=dpi,
        oem=oem,
        psm=psm,
        max_pages=max_pages,
        parallel=parallel,
    )

    result = check_compliance_pure_llm(text)
    summary = result.get("summary", {})
    header = rf"\b Compliance Check\b0\par Compliant: {summary.get('Compliant',0)} | Partial: {summary.get('Partial',0)} | Non-compliant: {summary.get('Non-compliant',0)}\par "
    lines = []
    for m in result.get("matches", []):
        line = (
            r"\par \b [" + _rtf_escape(m.get("policy_id", "")) + r"] " + _rtf_escape(m.get("policy_name", "")) + r"\b0" +
            r"\par \tab Status: " + _rtf_escape(m.get("status", "")) +
            r"\par \tab Evidence: " + _rtf_escape(m.get("evidence", "")) +
            r"\par \tab Note: " + _rtf_escape(m.get("note", "")) + r"\par "
        )
        lines.append(line)
    rtf = r"{\rtf1\ansi " + header + "".join(lines) + "}"
    return Response(content=rtf, media_type="text/rtf")


@app.post("/chat")
async def chat_about_document(
    request: Request,
    file: UploadFile | None = File(None),
    question: str = Form(...),
    lang: str = "eng",
    dpi: int = 100,
    oem: int = 1,
    psm: int = 6,
    max_pages: int | None = None,
    parallel: bool = True,
):
    # Ambil file dari form-data (fallback manual bila perlu)
    if file is None:
        form = await request.form()
        for key, value in form.multi_items():
            if hasattr(value, "filename") and value.filename:
                file = value  # type: ignore
                break
    if file is None:
        raise HTTPException(status_code=422, detail="Form-data must include a file field")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    # 1) OCR teks
    text = extract_text_with_ocr(
        pdf_bytes,
        language=lang,
        dpi=dpi,
        oem=oem,
        psm=psm,
        max_pages=max_pages,
        parallel=parallel,
    )

    # 2) Q&A berbasis teks kontrak
    answer = handle_chatbot_query(text, question)
    rtf = r"{\rtf1\ansi " + r"\b Q&A\b0\par " + r"\b Question:\b0 " + _rtf_escape(question) + r"\par " + r"\b Answer:\b0 " + _rtf_escape(answer) + "}"
    return Response(content=rtf, media_type="text/rtf")