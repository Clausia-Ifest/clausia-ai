import os
import fitz  # PyMuPDF
import io
from typing import Optional, List, Tuple

from PIL import Image
import pytesseract
from dotenv import load_dotenv

# Pastikan variabel lingkungan dari .env ikut terbaca (termasuk TESSERACT_CMD)
load_dotenv()


def _set_tesseract_cmd_from_env() -> None:
    """
    Konfigurasi lokasi executable Tesseract dari env var TESSERACT_CMD jika tersedia.
    Pada Windows, Anda bisa men-set TESSERACT_CMD ke path seperti:
    C:\\Program Files\\Tesseract-OCR\\tesseract.exe
    """
    tesseract_cmd = os.getenv("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> Optional[str]:
    """
    Ekstraksi teks langsung (non-OCR) menggunakan PyMuPDF.
    Mengembalikan string atau None jika tidak ada teks (kemungkinan PDF hasil scan).
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_parts = []
        for page in doc:
            extracted = page.get_text().strip()
            if extracted:
                text_parts.append(extracted)
        combined = "\n\n".join(text_parts).strip()
        return combined if combined else None
    except Exception as e:
        print(f"Error extracting text (non-OCR): {e}")
        return None


def _ocr_image_to_text(image: Image.Image, language: str, oem: int, psm: int) -> str:
    config = f"--oem {oem} --psm {psm}"
    return pytesseract.image_to_string(image, lang=language, config=config)


def _render_page_to_image(page: "fitz.Page", dpi: int) -> Image.Image:
    pix = page.get_pixmap(dpi=dpi)
    png_bytes = pix.tobytes("png")
    return Image.open(io.BytesIO(png_bytes)).convert("L")  # grayscale untuk sedikit percepatan


def extract_text_with_ocr(
    pdf_bytes: bytes,
    language: str = "eng",
    dpi: int = 100,
    oem: int = 1,
    psm: int = 6,
    max_pages: Optional[int] = None,
    parallel: bool = True,
) -> str:
    """
    Ekstraksi teks dari PDF. Coba terlebih dahulu native text extraction.
    Jika tidak ada teks (scan), lakukan OCR per halaman menggunakan Tesseract.

    Param language dapat diubah sesuai model bahasa yang terpasang di Tesseract,
    contoh: "eng" atau "ind" atau gabungan "eng+ind".
    """
    # 1) Coba ekstraksi teks langsung
    direct_text = extract_text_from_pdf_bytes(pdf_bytes)
    if direct_text:
        return direct_text

    # 2) Fallback ke OCR
    _set_tesseract_cmd_from_env()
    text_chunks: List[str] = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = list(doc)
        if isinstance(max_pages, int):
            pages = pages[:max_pages]

        # Fungsi worker per halaman
        def process_page(p: "fitz.Page") -> str:
            try:
                image = _render_page_to_image(p, dpi=dpi)
                return _ocr_image_to_text(image, language=language, oem=oem, psm=psm).strip()
            except Exception as exc:
                print(f"OCR page error: {exc}")
                return ""

        if parallel:
            # Gunakan ThreadPool karena pekerjaan berat ada di native lib (I/O + lib tesseract)
            import concurrent.futures as _fut
            with _fut.ThreadPoolExecutor() as executor:
                for text in executor.map(process_page, pages):
                    if text:
                        text_chunks.append(text)
        else:
            for p in pages:
                text = process_page(p)
                if text:
                    text_chunks.append(text)
        return "\n\n".join(filter(None, text_chunks)).strip()
    except Exception as e:
        print(f"Error performing OCR: {e}")
        return ""

