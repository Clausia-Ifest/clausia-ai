import grpc
from concurrent import futures
from typing import Optional

from app.services.pdf_reader_service import extract_text_with_ocr
from app.services.claude_service import (
    extract_target_metadata,
    summarize_text,
    analyze_risks_pure_llm,
    check_compliance_pure_llm,
    handle_chatbot_query,
)
from app.services.s3_service import download_pdf_from_s3
from app.services.database_service import get_contract_text_by_object_key

# Support both layouts: generated files inside package 'proto/' or at project root
try:
    import proto.clausia_pb2 as pb
    import proto.clausia_pb2_grpc as pbs
except ImportError:  # fallback if generated at project root
    import clausia_pb2 as pb
    import clausia_pb2_grpc as pbs


def _rtf_escape(text: str) -> str:
    if text is None:
        return ""
    escaped = (
        text.replace("\\", r"\\\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )
    escaped = escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\par ")
    return escaped


def _ocr_params(ocr: Optional[pb.OCRParams]):
    if not ocr:
        return {"language": "eng", "dpi": 300, "oem": 1, "psm": 6, "max_pages": None, "parallel": True}
    return {
        "language": ocr.lang or "eng",
        "dpi": ocr.dpi or 300,
        "oem": ocr.oem or 1,
        "psm": ocr.psm or 6,
        "max_pages": (ocr.max_pages if ocr.max_pages > 0 else None),
        "parallel": ocr.parallel,
    }


def _get_pdf_bytes(request) -> bytes | None:
    """Extract PDF bytes dari request, baik dari file upload atau S3 reference"""
    if hasattr(request, 'file') and request.HasField('file'):
        # Direct file upload
        return bytes(request.file.data)
    elif hasattr(request, 's3_ref') and request.HasField('s3_ref'):
        # S3 reference
        return download_pdf_from_s3(request.s3_ref.object_key)
    elif hasattr(request, 'source'):
        # Handle oneof field properly
        if request.WhichOneof('source') == 'file':
            return bytes(request.file.data)
        elif request.WhichOneof('source') == 's3_ref':
            return download_pdf_from_s3(request.s3_ref.object_key)
    return None


class ClausIAServicer(pbs.ClausIAServicer):
    def Extract(self, request: pb.ExtractRequest, context):
        # Gunakan default OCR params
        params = {"language": "eng", "dpi": 100, "oem": 1, "psm": 6, "max_pages": None, "parallel": True}
        pdf_bytes = _get_pdf_bytes(request)
        if not pdf_bytes:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("No valid file source provided (file or s3_ref)")
            return pb.ExtractResponse()
        
        text = extract_text_with_ocr(pdf_bytes, **params)
        rtf = r"{\rtf1\ansi " + r"\b Extracted Text\b0\par " + _rtf_escape(text) + "}"
        return pb.ExtractResponse(text=rtf)

    def ExtractMetadata(self, request: pb.ExtractRequest, context):
        # Gunakan default OCR params
        params = {"language": "eng", "dpi": 100, "oem": 1, "psm": 6, "max_pages": None, "parallel": True}
        pdf_bytes = _get_pdf_bytes(request)
        if not pdf_bytes:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("No valid file source provided (file or s3_ref)")
            return pb.ExtractMetadataResponse()
        
        text = extract_text_with_ocr(pdf_bytes, **params)
        meta = extract_target_metadata(text)
        import json as _json
        meta_json = _json.dumps({
            "external_company_name": meta.get("external_company_name") or "",
            "contract_start_date": meta.get("contract_start_date") or "",
            "contract_end_date": meta.get("contract_end_date") or "",
            "contract_title": meta.get("contract_title") or "",
        }, ensure_ascii=False)
        return pb.ExtractMetadataResponse(
            metadata=meta_json,
            content=(r"{\\rtf1\\ansi " + r"\\b Extracted Text\\b0\\par " + _rtf_escape(text) + "}"),
        )

    def Summarize(self, request: pb.ExtractRequest, context):
        # Gunakan default OCR params
        params = {"language": "eng", "dpi": 100, "oem": 1, "psm": 6, "max_pages": None, "parallel": True}
        pdf_bytes = _get_pdf_bytes(request)
        if not pdf_bytes:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("No valid file source provided (file or s3_ref)")
            return pb.SummarizeResponse()
        
        text = extract_text_with_ocr(pdf_bytes, **params)
        summary = summarize_text(text, language_hint="id")
        rtf = r"{\rtf1\ansi " + r"\b Summary\b0\par " + _rtf_escape(summary) + "}"
        return pb.SummarizeResponse(summary=rtf)

    def AnalyzeRisk(self, request: pb.ExtractRequest, context):
        # Skip OCR, ambil teks dari database berdasarkan object_key
        if not (hasattr(request, 's3_ref') and request.HasField('s3_ref')):
            if request.WhichOneof('source') != 's3_ref':
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("AnalyzeRisk requires s3_ref.object_key (no file upload support)")
                return pb.AnalyzeRiskResponse()
        
        object_key = request.s3_ref.object_key
        print(f"Retrieving contract text for object_key: {object_key}")
        
        # Ambil teks dari database (sudah di-OCR sebelumnya)
        text = get_contract_text_by_object_key(object_key)
        if not text:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(f"Contract text not found in database for object_key: {object_key}")
            return pb.AnalyzeRiskResponse()
        
        print(f"Retrieved text length: {len(text)} chars")
        print(f"Text preview: {text[:200]}...")
        
        result = analyze_risks_pure_llm(text)
        print(f"Risk analysis result: {len(result.get('findings', []))} findings")
        findings = []
        for f in result.get("findings", []):
            r_clause = r"{\rtf1\ansi " + _rtf_escape(f.get("clause_text", "")) + "}"
            r_rationale = r"{\rtf1\ansi " + _rtf_escape(f.get("rationale", "")) + "}"
            findings.append(pb.RiskFinding(
                clause_text=r_clause,
                risk_type=f.get("risk_type", ""),
                severity=f.get("severity", ""),
                rationale=r_rationale,
            ))
        return pb.AnalyzeRiskResponse(
            findings=findings,
            low=result.get("summary_counts", {}).get("Low", 0),
            medium=result.get("summary_counts", {}).get("Medium", 0),
            high=result.get("summary_counts", {}).get("High", 0),
        )

    def CheckCompliance(self, request: pb.ExtractRequest, context):
        # Gunakan default OCR params
        params = {"language": "eng", "dpi": 100, "oem": 1, "psm": 6, "max_pages": None, "parallel": True}
        pdf_bytes = _get_pdf_bytes(request)
        if not pdf_bytes:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("No valid file source provided (file or s3_ref)")
            return pb.CheckComplianceResponse()
        
        text = extract_text_with_ocr(pdf_bytes, **params)
        result = check_compliance_pure_llm(text)
        matches = []
        for m in result.get("matches", []):
            matches.append(pb.ComplianceMatch(
                policy_id=m.get("policy_id", ""),
                policy_name=m.get("policy_name", ""),
                status=m.get("status", ""),
                evidence=r"{\rtf1\ansi " + _rtf_escape(m.get("evidence", "")) + "}",
                note=r"{\rtf1\ansi " + _rtf_escape(m.get("note", "")) + "}",
            ))
        return pb.CheckComplianceResponse(
            matches=matches,
            compliant=result.get("summary", {}).get("Compliant", 0),
            partial=result.get("summary", {}).get("Partial", 0),
            non_compliant=result.get("summary", {}).get("Non-compliant", 0),
        )

    def Chat(self, request: pb.ChatRequest, context):
        # Gunakan default OCR params
        params = {"language": "eng", "dpi": 100, "oem": 1, "psm": 6, "max_pages": None, "parallel": True}
        pdf_bytes = _get_pdf_bytes(request)
        if not pdf_bytes:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("No valid file source provided (file or s3_ref)")
            return pb.ChatResponse()
        
        text = extract_text_with_ocr(pdf_bytes, **params)
        answer = handle_chatbot_query(text, request.question, session_id=(request.session_id or None))
        rtf = r"{\rtf1\ansi " + r"\b Q&A\b0\par " + r"\b Question:\b0 " + _rtf_escape(request.question) + r"\par " + r"\b Answer:\b0 " + _rtf_escape(answer) + "}"
        return pb.ChatResponse(answer=rtf)


def serve(port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pbs.add_ClausIAServicer_to_server(ClausIAServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"gRPC server running on port {port}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()


