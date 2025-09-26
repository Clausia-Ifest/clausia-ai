from pydantic import BaseModel
from typing import Dict, List, Any

# Model untuk detail risiko
class RiskDetail(BaseModel):
    clause_text: str
    risk_type: str
    severity: str # Contoh: "Low", "Medium", "High"

# Model untuk respons analisis kontrak
class ContractAnalysisResponse(BaseModel):
    contract_id: str
    extracted_text: str
    metadata: Dict[str, Any] # Akan berisi keys: parties, date, title, dll.
    risks: List[RiskDetail]
    recommendations: List[str]

# Model untuk respons chatbot
class ChatbotResponse(BaseModel):
    answer: str