import grpc
from concurrent import futures
from typing import Optional

from app.services.pdf_reader_service import extract_text_with_ocr
from app.services.claude_service import (
    extract_target_metadata,
    summarize_text,
    analyze_risks,
    check_compliance_pure_llm,
    handle_chatbot_query,
    handle_chatbot_query_with_db,
)
from app.services.s3_service import download_pdf_from_s3
from app.services.database_service import get_contract_text_by_object_key, get_contract_text_by_id

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

    def Summarize(self, request: pb.SummarizeRequest, context):
        # Ambil teks dari database berdasarkan contract_id
        contract_id = request.contract_id
        if not contract_id:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Summarize requires contract_id")
            return pb.SummarizeResponse()
        
        print(f"Retrieving contract text for summarize, contract_id: {contract_id}")
        
        try:
            # Ambil teks dari database berdasarkan contract_id
            text = get_contract_text_by_id(contract_id)
            if not text:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Contract text not found in database for contract_id: {contract_id}")
                return pb.SummarizeResponse()
        except Exception as e:
            print(f"Error in Summarize: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")
            return pb.SummarizeResponse()
        
        print(f"Retrieved text length for summarize: {len(text)} chars")
        html_summary = summarize_text(text, language_hint="id")
        
        # Bersihkan HTML code blocks jika ada
        if html_summary.startswith("```html"):
            html_summary = html_summary.strip("```html").strip("```")
        elif html_summary.startswith("```"):
            html_summary = html_summary.strip("```")
        
        return pb.SummarizeResponse(summary=html_summary)

    def AnalyzeRisk(self, request: pb.ExtractRequest, context):
        # Skip OCR, ambil teks dari database berdasarkan object_key
        try:
            source_type = request.WhichOneof('source')
            if source_type != 's3_ref':
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
        except Exception as e:
            print(f"Error in AnalyzeRisk: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")
            return pb.AnalyzeRiskResponse()
        
        print(f"Retrieved text length: {len(text)} chars")
        print(f"Text preview: {text[:200]}...")
        
        result = analyze_risks(text)
        print(f"Risk analysis result: {len(result.get('findings', []))} findings")
        findings = []
        for f in result.get("findings", []):
            # clause_text sudah dalam format HTML, kirim apa adanya
            findings.append(pb.RiskFinding(
                clause_text=f.get("clause_text", ""),
                risk_type=f.get("risk_type", ""),
                severity=f.get("severity", ""),
                rationale=f.get("rationale", ""),  # rationale sekarang berisi rekomendasi
            ))
        return pb.AnalyzeRiskResponse(
            findings=findings,
            low=result.get("summary_counts", {}).get("Low", 0),
            medium=result.get("summary_counts", {}).get("Medium", 0),
            high=result.get("summary_counts", {}).get("High", 0),
            risk_level=result.get("overall_risk_level", 1),
        )

    def CheckCompliance(self, request: pb.ExtractRequest, context):
        # Skip OCR, ambil teks dari database berdasarkan object_key
        try:
            source_type = request.WhichOneof('source')
            if source_type != 's3_ref':
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("CheckCompliance requires s3_ref.object_key (no file upload support)")
                return pb.CheckComplianceResponse()
            
            object_key = request.s3_ref.object_key
            print(f"Retrieving contract text for compliance check, object_key: {object_key}")
            
            # Ambil teks dari database (sudah di-OCR sebelumnya)
            text = get_contract_text_by_object_key(object_key)
            if not text:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Contract text not found in database for object_key: {object_key}")
                return pb.CheckComplianceResponse()
        except Exception as e:
            print(f"Error in CheckCompliance: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")
            return pb.CheckComplianceResponse()
        
        print(f"Retrieved text length for compliance: {len(text)} chars")
        html_result = check_compliance_pure_llm(text)
        
        # Kembalikan HTML sebagai single string di field pertama
        return pb.CheckComplianceResponse(
            matches=[pb.ComplianceMatch(
                policy_id="html_result",
                policy_name=html_result,  # HTML result dalam field policy_name
                status="",
                evidence="",
                note="",
            )],
            compliant=0,
            partial=0,
            non_compliant=0,
        )

    def Chat(self, request: pb.ChatRequest, context):
        # Gunakan database session management dengan contract_id
        contract_id = request.contract_id
        if not contract_id:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Chat requires contract_id")
            return pb.ChatResponse()
        
        question = request.question
        session_id = request.session_id or None
        
        print(f"Chat request - contract_id: {contract_id}, question: {question[:50]}...")
        
        try:
            # Gunakan database session management
            html_answer, confirmed_session_id = handle_chatbot_query_with_db(
                contract_id, question, session_id
            )
            
            # Bersihkan HTML code blocks jika ada
            if html_answer.startswith("```html"):
                html_answer = html_answer.strip("```html").strip("```")
            elif html_answer.startswith("```"):
                html_answer = html_answer.strip("```")
            
            print(f"Chat response generated, session_id: {confirmed_session_id}")
            return pb.ChatResponse(answer=html_answer)
            
        except Exception as e:
            print(f"Error in Chat: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {str(e)}")
            return pb.ChatResponse()


def serve(port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pbs.add_ClausIAServicer_to_server(ClausIAServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"gRPC server running on port {port}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()


