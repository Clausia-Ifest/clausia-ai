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
        "Anda adalah asisten tanya jawab kontrak yang memberikan jawaban dalam format HTML. "
        "Jawab pertanyaan secara ringkas, profesional, dan HANYA berdasarkan konten kontrak. "
        "Format jawaban: <div><h4>Jawaban</h4><p>Isi jawaban...</p></div> "
        "Jika merujuk bagian kontrak, gunakan <blockquote>kutipan</blockquote>. "
        "Pertimbangkan riwayat percakapan untuk konteks.\n\n"
        + f"Teks Kontrak: {contract_text[:6000]}\n"
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

    # HTML summary dengan poin-poin penting untuk legal review
    system_prompt = (
        "Anda adalah legal counsel yang membuat ringkasan HTML untuk tim legal. "
        "Buat ringkasan dalam format HTML dengan poin-poin penting untuk mempercepat review kontrak. "
        "Gunakan struktur: <h3>Ringkasan Kontrak</h3><ul><li>Poin 1</li><li>Poin 2</li>...</ul> "
        "Fokus pada: para pihak & peran, ruang lingkup/layanan, nilai & pembayaran, jangka waktu, "
        "penalti/sanksi, pemutusan kontrak, penyelesaian sengketa, force majeure, kewajiban kunci. "
        "Maksimal 7 poin, setiap poin 1-2 kalimat ringkas. TANPA frasa pembuka. "
        "Langsung kembalikan HTML tanpa teks lain."
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


def analyze_risks(text: str) -> dict:
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
        "Untuk setiap temuan berikan: "
        "- clause_text: HTML dengan kutipan klausa + minimal 3 poin kenapa ini risiko (gunakan <ul><li>) "
        "- risk_type: jenis risiko "
        "- severity: Low/Medium/High "
        "- rationale: rekomendasi dalam format HTML <div><h5>Rekomendasi</h5><p>langkah selanjutnya 2-3 kalimat</p></div> "
        "Kembalikan JSON: findings (list) dan summary_counts (jumlah per severity). "
        "Jika tidak ada risiko jelas, tetap cari potensi risiko kecil (Low severity)."
    )

    user_prompt = (
        "Analisis risiko untuk teks kontrak berikut. Kembalikan JSON dengan format:\n"
        '{"findings": [{"clause_text": "<p>Kutipan klausa</p><ul><li>Poin risiko 1</li><li>Poin risiko 2</li><li>Poin risiko 3</li></ul>", "risk_type": "jenis", "severity": "Low/Medium/High", "rationale": "<div><h5>Rekomendasi</h5><p>langkah selanjutnya 2-3 kalimat</p></div>"}], "summary_counts": {"Low": 0, "Medium": 0, "High": 0}}\n\n'
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
            
            # Tentukan overall risk level berdasarkan findings
            if counts["High"] > 0:
                data["overall_risk_level"] = 3  # High
            elif counts["Medium"] > 0:
                data["overall_risk_level"] = 2  # Medium
            elif counts["Low"] > 0:
                data["overall_risk_level"] = 1  # Low
            else:
                data["overall_risk_level"] = 1  # Default Low jika tidak ada findings
            
            return data
        except Exception as e:
            print(f"Error parsing Claude response: {e}")
            last_error = e
            continue

    return {"findings": [], "summary_counts": {"Low": 0, "Medium": 0, "High": 0}, "error": str(last_error) if last_error else "model_unavailable"}


def check_compliance_pure_llm(text: str) -> str:
    """
    Compliance checker berbasis LLM dengan kebijakan perusahaan mock.
    Mengembalikan HTML string dengan hasil compliance check.
    """
    if not client:
        return "<h3>Compliance Check</h3><p>Error: Claude API tidak terhubung</p>"

    mock_policies = [
        {"id": "P-001", "name": "Payment Terms ≤ 30 hari", "rule": "Pembayaran harus net 30 hari atau lebih cepat."},
        {"id": "P-002", "name": "Cap on Liability ≥ nilai kontrak", "rule": "Harus ada batas maksimal tanggung jawab setidaknya setara nilai kontrak."},
        {"id": "P-003", "name": "Governing Law Indonesia", "rule": "Hukum yang berlaku harus Indonesia."},
        {"id": "P-004", "name": "No Termination for Convenience oleh counterparty", "rule": "Pihak lawan tidak boleh memutuskan perjanjian secara sepihak tanpa sebab."},
        {"id": "P-005", "name": "Confidentiality mencakup data pribadi", "rule": "Klausul kerahasiaan wajib mencakup data pribadi dan mekanisme perlindungan."},
    ]

    system_prompt = (
        "Anda adalah compliance officer. Evaluasi kesesuaian kontrak terhadap daftar kebijakan. "
        "Kembalikan hasil dalam format HTML dengan struktur: "
        "<h3>Compliance Check</h3><ul><li><strong>[Policy ID] Policy Name</strong> - Status: [status]<br/>Evidence: [kutipan]<br/>Note: [catatan]</li></ul> "
        "Untuk setiap kebijakan, tentukan status: Compliant / Partial / Non-compliant. "
        "Evidence: kutipan teks singkat. Note: catatan ringkas maksimal 2 kalimat. "
        "Langsung kembalikan HTML tanpa teks lain."
    )

    user_prompt = {
        "text": text,
        "policies": mock_policies,
        "instruction": "Nilai tiap kebijakan. Jika tak ada bukti, Non-compliant."
    }

    user_prompt = f"""
Evaluasi kontrak berikut terhadap kebijakan perusahaan:

Kebijakan:
{json.dumps(mock_policies, indent=2, ensure_ascii=False)}

Teks kontrak:
{text[:6000]}

Kembalikan HTML compliance check sesuai format yang diminta.
"""

    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        html_result = response.content[0].text.strip()
        
        # Bersihkan markdown code blocks jika ada
        if html_result.startswith("```html"):
            html_result = html_result.strip("```html").strip("```")
        elif html_result.startswith("```"):
            html_result = html_result.strip("```")
        
        return html_result
    except Exception as e:
        print(f"Error in compliance check: {e}")
        return f"<h3>Compliance Check</h3><p>Error: {str(e)}</p>"