import os
from anthropic import Anthropic
import json
from dotenv import load_dotenv

load_dotenv()

# Inisialisasi Klien Claude
try:
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
except Exception as e:
    # Ini akan mencegah aplikasi berjalan jika kunci API tidak ada
    print(f"Gagal menginisialisasi Claude API: {e}")
    client = None

def analyze_and_extract_contract(text: str) -> dict:
    """
    Menggunakan Claude untuk Ekstraksi Metadata, Deteksi Risiko, dan Rekomendasi.
    """
    if not client:
        return {"metadata": {}, "risks": [{"summary": "API Claude tidak terhubung.", "severity": "High"}], "recommendations": []}

    # Prompt Engineering: Instruksi yang sangat jelas untuk Claude
    system_prompt = (
        "Anda adalah asisten legal AI yang sangat akurat. Analisis kontrak yang diberikan. "
        "Output Anda HARUS berupa objek JSON dengan tiga kunci utama: 'metadata', 'risks', dan 'recommendations'. "
        "Kunci 'metadata' harus berisi 'parties' (list), 'date' (string), dan 'title' (string). "
        "Kunci 'risks' adalah list objek. Setiap risiko harus mencakup 'clause_text' (teks klausa bermasalah), 'risk_type', dan 'severity' (Low, Medium, High)."
        "Kunci 'recommendations' adalah list dari string yang berisi saran mitigasi hukum."
    )

    prompt = f"Lakukan analisis terhadap teks kontrak berikut dan kembalikan output dalam format JSON sesuai instruksi:\n---\n{text}"

    # Gunakan Claude Opus untuk akurasi analisis terbaik
    response = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    
    try:
        json_string = response.content[0].text.strip()
        # Perbaiki Claude yang terkadang menambahkan teks di luar blok JSON
        if json_string.startswith("```json"):
            json_string = json_string.strip("```json").strip("```")
            
        return json.loads(json_string)
    except Exception as e:
        print(f"Gagal memparsing respons Claude: {e}")
        return {}


_SESSION_HISTORY: dict[str, list[dict[str, str]]] = {}


def handle_chatbot_query(contract_text: str, question: str, session_id: str | None = None) -> str:
    """
    Fungsi untuk menjawab pertanyaan chatbot berdasarkan teks kontrak.
    """
    if not client:
        return "Chatbot tidak dapat terhubung ke API Claude."
        
    # Gunakan Haiku untuk kecepatan respons chatbot
    # Kelola riwayat per sesi
    history = []
    if session_id:
        history = _SESSION_HISTORY.get(session_id, [])

    prompt = (
        "Anda adalah asisten tanya jawab kontrak. Jawablah pertanyaan pengguna secara ringkas, profesional, dan HANYA berdasarkan KONTEN yang ada dalam 'Teks Kontrak' yang diberikan.\n\n"
        + f"Teks Kontrak: {contract_text}\n"
        + ("\n".join([f"Turn {i+1} Q: {h['q']}\nTurn {i+1} A: {h['a']}" for i, h in enumerate(history)]) + "\n" if history else "")
        + f"Pertanyaan: {question}"
    )
    
    response = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    answer = response.content[0].text.strip()

    # Simpan riwayat sesi
    if session_id:
        history = _SESSION_HISTORY.get(session_id, [])
        history.append({"q": question, "a": answer})
        # batasi panjang riwayat sederhana
        if len(history) > 10:
            history = history[-10:]
        _SESSION_HISTORY[session_id] = history

    return answer


def extract_target_metadata(text: str) -> dict:
    """
    Ekstraksi metadata terarah: nama PT luar (pihak kedua), tanggal mulai, tanggal selesai,
    dan judul kontrak terformat.
    Mengembalikan dict: { external_company_name, contract_start_date, contract_end_date, contract_title }
    """
    if not client:
        return {
            "external_company_name": None,
            "contract_start_date": None,
            "contract_end_date": None,
            "contract_title": None,
            "note": "API Claude tidak terhubung",
        }

    system_prompt = (
        "Anda adalah asisten legal yang sangat teliti dalam membaca teks OCR yang mungkin rusak. "
        "Ekstrak empat informasi dari teks kontrak berikut: "
        "(1) external_company_name: nama perusahaan lawan/pihak kedua (bukan PT Pelabuhan Indonesia/Pelindo), "
        "(2) contract_start_date: tanggal kontrak dimulai/ditandatangani, "
        "(3) contract_end_date: tanggal kontrak berakhir/masa berlaku selesai, "
        "(4) contract_title: judul terformat 'Kerja Sama PT [nama pt luar] [tentang apa]'. "
        "PENTING: Abaikan karakter rusak OCR seperti '———', '[', ']', 'reper'. "
        "Cari pola nama PT, tanggal (format apa saja), dan topik kontrak. "
        "Jika tidak ditemukan, isi null. Format tanggal ISO-8601 (YYYY-MM-DD) bila bisa. "
        "Hanya kembalikan JSON tanpa teks lain."
    )

    user_prompt = (
        "Teks kontrak:\n" + text + "\n" +
        "Kembalikan JSON dengan kunci: external_company_name, contract_start_date, contract_end_date, contract_title."
    )

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=512,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    try:
        json_string = response.content[0].text.strip()
        if json_string.startswith("```json"):
            json_string = json_string.strip("```json").strip("```")
        return json.loads(json_string)
    except Exception:
        return {
            "external_company_name": None,
            "contract_start_date": None,
            "contract_end_date": None,
            "contract_title": None,
        }


def summarize_text(text: str, language_hint: str = "id") -> str:
    """
    Ringkas teks maksimal 5 kalimat, keluaran plain text satu paragraf TANPA preface/bullet.
    Default bahasa Indonesia.
    """
    if not client:
        return "Ringkasan tidak tersedia: API Claude tidak terhubung."

    # Instruksi: Indonesia, max 5 kalimat, tanpa preface/bullet, fokus pasal kunci untuk legal review.
    system_prompt = (
        "generate text nya seperti anda adalah seorang legal dari perusahaan pihak pertama. Buat ringkasan SANGAT PADAT dalam bahasa Indonesia, MAKSIMAL 5 kalimat. "
        "TANPA frasa pembuka/penutup, TANPA bullet/penomoran, HANYA isi ringkasan sebagai teks polos satu paragraf. Tanpa kalimat seperti berikut adalah ringkasan dari... atau semacamnya"
        "Prioritaskan butir yang membantu legal review cepat: para pihak & peran, ruang lingkup/layanan, nilai & skema pembayaran, jangka waktu/masa berlaku, penalti/denda, perubahan kontrak, force majeure, pemutusan kontrak, sengketa (hukum/forumnya), kerahasiaan & data, hak kekayaan intelektual, SLA/deliverables, kewajiban utama masing-masing pihak. "
        "Gunakan istilah kontraktual yang ringkas. Jangan menambahkan kalimat pembuka seperti 'Berikut adalah...'."
        "Jangan menambahkan kalimat pembuka satupun seperti 'Berikut adalah ringkasan dari...' atau sebagainya."
    )

    user_prompt = text

    response = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=512,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    # Normalisasi: hapus codefence, preface umum, dan rapikan whitespace menjadi satu baris
    if raw.startswith("```json") or raw.startswith("```"):
        raw = raw.strip("` ")
    prefixes = [
        "Berikut adalah ringkasan dalam bahasa Indonesia:",
        "Berikut adalah ringkasan dalam bahasa Inggris:",
        "Berikut adalah ringkasan:",
        "Ringkasan:",
        "Rangkuman:",
        "Summary:",
        "Ringkasan kontrak:",
        "Ringkasan kontrak ini:",
    ]
    for p in prefixes:
        if raw.lower().startswith(p.lower()):
            raw = raw[len(p):].lstrip()
            break

    import re
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def analyze_risks_pure_llm(text: str) -> dict:
    """
    Analisis risiko berbasis LLM murni (tanpa RAG). Mengembalikan dict:
    { findings: [{clause_text, risk_type, severity, rationale}], summary_counts: {...} }
    """
    if not client:
        return {"findings": [], "summary_counts": {"Low": 0, "Medium": 0, "High": 0}, "note": "Claude API tidak terhubung"}

    system_prompt = (
        "Anda adalah counsel kontrak senior yang ahli membaca teks OCR rusak. Tugas: temukan klausa berisiko. "
        "PENTING: Teks ini hasil OCR dengan banyak karakter rusak (———, [, ], reper, dll). Abaikan noise tersebut. "
        "Cari pola risiko seperti: pemutusan sepihak, liability tidak terbatas, sanksi berat, force majeure, "
        "governing law luar negeri, pembayaran terlambat, garansi panjang, denda tinggi, dll. "
        "Untuk setiap temuan: clause_text (kutipan singkat), risk_type, severity (Low/Medium/High), rationale. "
        "Kembalikan JSON: findings (list) dan summary_counts (jumlah per severity). "
        "Jika tidak ada risiko jelas, tetap cari potensi risiko kecil (Low severity)."
    )

    user_prompt = (
        "Analisis risiko untuk teks kontrak berikut. Kembalikan JSON dengan format:\n"
        '{"findings": [{"clause_text": "kutipan", "risk_type": "jenis", "severity": "Low/Medium/High", "rationale": "alasan"}], "summary_counts": {"Low": 0, "Medium": 0, "High": 0}}\n\n'
        "Teks kontrak:\n" + text[:8000]  # Batasi panjang untuk menghindari token limit
    )

    model_candidates = [
        "claude-3-5-haiku-20241022"
    ]

    last_error = None
    for model in model_candidates:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            payload = response.content[0].text.strip()
            print(f"Claude response for risk analysis: {payload[:500]}...")
            
            # Ekstrak JSON dari response yang mungkin berisi teks tambahan
            if "```json" in payload:
                start = payload.find("```json") + 7
                end = payload.find("```", start)
                if end > start:
                    payload = payload[start:end].strip()
            elif "{" in payload and "}" in payload:
                # Cari JSON object pertama
                start = payload.find("{")
                # Cari closing brace yang matching
                brace_count = 0
                end = start
                for i, char in enumerate(payload[start:], start):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break
                payload = payload[start:end]
            
            print(f"Extracted JSON: {payload[:300]}...")
            data = json.loads(payload)
            print(f"Parsed risk data: {data}")
            
            # normalisasi summary_counts
            counts = {"Low": 0, "Medium": 0, "High": 0}
            for f in data.get("findings", []):
                sev = (f.get("severity") or "").capitalize()
                if sev in counts:
                    counts[sev] += 1
            data["summary_counts"] = counts
            return data
        except Exception as e:
            print(f"Error parsing Claude response: {e}")
            last_error = e
            continue

    return {"findings": [], "summary_counts": {"Low": 0, "Medium": 0, "High": 0}, "error": str(last_error) if last_error else "model_unavailable"}


def check_compliance_pure_llm(text: str) -> dict:
    """
    Compliance checker berbasis LLM dengan kebijakan perusahaan mock. Mengembalikan:
    { matches: [{policy_id, policy_name, status, evidence, note}], summary: {...} }
    status: Compliant / Partial / Non-compliant
    """
    if not client:
        return {"matches": [], "summary": {}, "note": "Claude API tidak terhubung"}

    mock_policies = [
        {"id": "P-001", "name": "Payment Terms ≤ 30 hari", "rule": "Pembayaran harus net 30 hari atau lebih cepat."},
        {"id": "P-002", "name": "Cap on Liability ≥ nilai kontrak", "rule": "Harus ada batas maksimal tanggung jawab setidaknya setara nilai kontrak."},
        {"id": "P-003", "name": "Governing Law Indonesia", "rule": "Hukum yang berlaku harus Indonesia."},
        {"id": "P-004", "name": "No Termination for Convenience oleh counterparty", "rule": "Pihak lawan tidak boleh memutuskan perjanjian secara sepihak tanpa sebab."},
        {"id": "P-005", "name": "Confidentiality mencakup data pribadi", "rule": "Klausul kerahasiaan wajib mencakup data pribadi dan mekanisme perlindungan."},
    ]

    system_prompt = (
        "Anda adalah compliance officer. Evaluasi kesesuaian kontrak terhadap daftar kebijakan. "
        "Untuk setiap kebijakan, tentukan status: Compliant / Partial / Non-compliant, kutip evidence (teks singkat), dan berikan catatan ringkas. "
        "Kembalikan JSON dengan kunci: matches (list objek policy) dan summary (jumlah per status)."
    )

    user_prompt = {
        "text": text,
        "policies": mock_policies,
        "instruction": "Nilai tiap kebijakan. Jika tak ada bukti, Non-compliant."
    }

    model_candidates = [
        "claude-3-7-sonnet-20250219"
    ]

    last_error = None
    for model in model_candidates:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": json.dumps(user_prompt)}],
            )
            payload = response.content[0].text.strip()
            if payload.startswith("```json"):
                payload = payload.strip("```json").strip("```")
            data = json.loads(payload)
            # Ringkas summary
            summary = {"Compliant": 0, "Partial": 0, "Non-compliant": 0}
            for m in data.get("matches", []):
                s = (m.get("status") or "").title()
                if s in summary:
                    summary[s] += 1
            data["summary"] = summary
            return data
        except Exception as e:
            last_error = e
            continue

    return {"matches": [], "summary": {}, "error": str(last_error) if last_error else "model_unavailable"}