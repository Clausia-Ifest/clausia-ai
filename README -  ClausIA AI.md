# ClausIA AI 📄🤖

> **AI-Powered Legal Document Management System for IFEST 2025**

An intelligent contract analysis system developed for PT Pelindo's legal document management challenge at IFEST 2025. ClausIA AI leverages advanced AI capabilities including OCR, natural language processing, and Claude AI to automate contract review, risk analysis, and compliance checking.

**Team:** 19° (Sembilan Belas Derajat)  
**Competition:** IFEST 2025 - AI Innovation Challenge  
**Development Period:** September 26-27, 2025 (24-hour Hackathon)

---

## 🌟 Features

### 1. **Intelligent PDF Text Extraction**
- **Hybrid OCR Processing**: Automatic fallback from native text extraction to Tesseract OCR for scanned documents
- **Multi-language Support**: Handles Indonesian and English documents
- **Parallel Processing**: Concurrent page processing for faster OCR operations
- **Noise Handling**: Robust parsing of corrupted OCR text with special character filtering

### 2. **Smart Metadata Extraction**
Automatically extracts critical contract information:
- External company name (counterparty identification)
- Contract start date
- Contract end date
- Formatted contract title

### 3. **AI-Powered Contract Summarization**
- Generates structured HTML summaries with key points
- Focuses on legally relevant aspects: parties, scope, payment terms, duration, penalties, termination clauses
- Context-aware summarization in Indonesian or English
- Maximum 7 bullet points for quick review

### 4. **Risk Analysis Engine**
Identifies and categorizes potential risks in contracts:
- **Risk Types**: Termination rights, liability caps, payment terms, force majeure, governing law, penalties, warranties
- **Severity Levels**: Low, Medium, High
- **Detailed Analysis**: Clause quotations with 3+ risk indicators per finding
- **Actionable Recommendations**: HTML-formatted suggestions for each risk
- **Overall Risk Assessment**: Aggregated risk level calculation

### 5. **Compliance Checker**
Validates contracts against company policies:
- Payment Terms (≤ 30 days)
- Liability Caps (≥ contract value)
- Governing Law (Indonesia)
- Termination Rights
- Confidentiality & Data Privacy

Returns structured compliance status: Compliant / Partial / Non-compliant

### 6. **Intelligent Chatbot (Q&A)**
- Contract-specific question answering
- Session-based conversation history
- Context-aware responses using Claude 3.7 Sonnet
- HTML-formatted answers with blockquotes for contract references
- Database-persisted chat sessions

---

## 🏗️ Architecture

### Technology Stack

**AI & ML:**
- [Anthropic Claude AI](https://www.anthropic.com/) (Claude 3.5 Haiku, Claude 3.7 Sonnet)
- Tesseract OCR for document digitization
- PyMuPDF (fitz) for PDF processing

**Backend:**
- **Python Service**: FastAPI & gRPC server (this repository)
- **Go Backend**: Main API gateway (separate repository)
- **Database**: PostgreSQL
- **Storage**: S3-compatible object storage (CloudHost)

**Communication:**
- gRPC for efficient microservice communication
- Protocol Buffers for structured data exchange

### System Components

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   Go Backend    │─────▶│  Python gRPC     │─────▶│   Claude AI     │
│   (API Gateway) │      │   AI Service     │      │   (Anthropic)   │
└────────┬────────┘      └────────┬─────────┘      └─────────────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐      ┌──────────────────┐
│   PostgreSQL    │      │  S3 Storage      │
│   (Contracts DB)│      │  (PDF Documents) │
└─────────────────┘      └──────────────────┘
```

### Database Schema

**Tables:**
- `documents`: Stores OCR-processed contract text (hash-indexed)
- `contract_documents`: Links contracts to document hashes with metadata
- `chats`: Persists chatbot conversation history per contract

---

## 🚀 Installation & Setup

### Prerequisites

1. **Python 3.11+**
2. **Tesseract OCR** ([Download](https://github.com/tesseract-ocr/tesseract))
   - Windows: Install to `C:\Program Files\Tesseract-OCR\`
   - Linux: `sudo apt-get install tesseract-ocr`
   - macOS: `brew install tesseract`
3. **PostgreSQL Database**
4. **S3-compatible Storage** (AWS S3 or compatible)

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd clausia-ai
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment

Create a `.env` file in the project root:

```env
# Anthropic Claude API
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# PostgreSQL Database
DB_HOST=your_database_host
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_database_password
DB_NAME=ifest

# Tesseract OCR Path (Windows example)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

# S3 Storage Configuration
S3_ACCESS_KEY=your_s3_access_key
S3_SECRET_KEY=your_s3_secret_key
S3_REGION=your_region
S3_ENDPOINT=https://your-s3-endpoint.com
S3_BUCKET_NAME=your_bucket_name
```

### Step 4: Generate gRPC Code

```bash
python -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/clausia.proto
```

This generates:
- `clausia_pb2.py` - Protocol buffer messages
- `clausia_pb2_grpc.py` - gRPC service stubs

### Step 5: Start the Server

**Option A: gRPC Server (Production)**
```bash
python grpc_server.py
```
Default port: `50051`

**Option B: FastAPI Server (Development/Testing)**
```bash
uvicorn app.main:app --reload --port 8000
```

---

## 📡 API Documentation

### gRPC Service API

All services defined in [`proto/clausia.proto`](proto/clausia.proto)

#### 1. Extract Text from PDF

**RPC:** `Extract(ExtractRequest) → ExtractResponse`

Extracts text from PDF using hybrid OCR approach.

**Request:**
```protobuf
message ExtractRequest {
  oneof source {
    FileContent file = 1;      // Direct PDF upload
    S3Reference s3_ref = 3;    // S3 object key
  }
}
```

**Response:**
```protobuf
message ExtractResponse {
  string text = 1;  // HTML-formatted extracted text
}
```

**Features:**
- Automatic OCR fallback for scanned PDFs
- Parallel page processing
- Default: DPI=100, English language

---

#### 2. Extract Metadata

**RPC:** `ExtractMetadata(ExtractRequest) → ExtractMetadataResponse`

Extracts structured metadata using Claude AI.

**Response:**
```protobuf
message ExtractMetadataResponse {
  string metadata = 1;  // JSON string with fields:
                       // - external_company_name
                       // - contract_start_date (ISO-8601)
                       // - contract_end_date (ISO-8601)
                       // - contract_title
  string content = 2;   // Full OCR text in RTF format
}
```

**Example Response:**
```json
{
  "external_company_name": "PT Mitra Sejahtera",
  "contract_start_date": "2025-01-01",
  "contract_end_date": "2025-12-31",
  "contract_title": "Kerja Sama PT Mitra Sejahtera untuk Layanan Logistik Pelabuhan"
}
```

---

#### 3. Summarize Contract

**RPC:** `Summarize(SummarizeRequest) → SummarizeResponse`

Generates intelligent contract summary.

**Request:**
```protobuf
message SummarizeRequest {
  string contract_id = 1;  // Contract ID from database
}
```

**Response:**
```protobuf
message SummarizeResponse {
  string summary = 1;  // HTML-formatted summary with <ul><li> structure
}
```

**Summary Includes:**
- Contracting parties & roles
- Scope of work/services
- Payment terms & values
- Contract duration
- Penalties & sanctions
- Termination conditions
- Dispute resolution
- Force majeure clauses

---

#### 4. Analyze Risks

**RPC:** `AnalyzeRisk(ExtractRequest) → AnalyzeRiskResponse`

Identifies legal and business risks in contracts.

**Request:**
```protobuf
message ExtractRequest {
  S3Reference s3_ref = 3;  // Requires S3 reference (uses cached OCR from DB)
}
```

**Response:**
```protobuf
message AnalyzeRiskResponse {
  repeated RiskFinding findings = 1;
  int32 low = 2;           // Count of low-severity risks
  int32 medium = 3;        // Count of medium-severity risks
  int32 high = 4;          // Count of high-severity risks
  int32 risk_level = 5;    // Overall: 1=Low, 2=Medium, 3=High
}

message RiskFinding {
  string clause_text = 1;   // HTML with clause quote + 3+ risk indicators
  string risk_type = 2;     // e.g., "Unilateral Termination", "Unlimited Liability"
  string severity = 3;      // "Low" | "Medium" | "High"
  string rationale = 4;     // HTML-formatted recommendations
}
```

---

#### 5. Check Compliance

**RPC:** `CheckCompliance(ExtractRequest) → CheckComplianceResponse`

Validates contract against company policies.

**Request:**
```protobuf
message ExtractRequest {
  S3Reference s3_ref = 3;  // Requires S3 reference
}
```

**Response:**
```protobuf
message CheckComplianceResponse {
  repeated ComplianceMatch matches = 1;
  int32 compliant = 2;       // Count of compliant policies
  int32 partial = 3;         // Count of partially compliant policies
  int32 non_compliant = 4;   // Count of non-compliant policies
}

message ComplianceMatch {
  string policy_id = 1;     // e.g., "P-001"
  string policy_name = 2;   // Policy description (HTML result in gRPC version)
  string status = 3;        // "Compliant" | "Partial" | "Non-compliant"
  string evidence = 4;      // Contract clause evidence
  string note = 5;          // Brief explanation
}
```

**Default Policies:**
- **P-001**: Payment Terms ≤ 30 days
- **P-002**: Liability Cap ≥ contract value
- **P-003**: Governing Law = Indonesia
- **P-004**: No unilateral termination by counterparty
- **P-005**: Confidentiality includes personal data protection

---

#### 6. Chat with Contract

**RPC:** `Chat(ChatRequest) → ChatResponse`

Interactive Q&A about contract content.

**Request:**
```protobuf
message ChatRequest {
  string contract_id = 1;   // Contract ID from database
  string question = 2;      // User's question
  string session_id = 3;    // Optional: for conversation continuity
}
```

**Response:**
```protobuf
message ChatResponse {
  string answer = 1;  // HTML-formatted answer with <blockquote> for references
}
```

**Features:**
- Session-based conversation history (stored in database)
- Context-aware responses using previous messages
- Max 10 messages per session (auto-trimmed)
- Uses Claude 3.7 Sonnet for high-quality answers

---

### FastAPI Endpoints

Alternative HTTP REST API (development mode):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/extract` | POST | Extract text from PDF |
| `/extract_metadata` | POST | Extract metadata + full text |
| `/summarize` | POST | Summarize contract |
| `/analyze_risk` | POST | Analyze contract risks |
| `/check_compliance` | POST | Check compliance against policies |
| `/chat` | POST | Ask questions about contract |

**Example: Extract Metadata**
```bash
curl -X POST "http://localhost:8000/extract_metadata" \
  -F "file=@contract.pdf" \
  -F "lang=eng" \
  -F "dpi=100"
```

---

## 🔧 Usage Examples

### Python gRPC Client

```python
import grpc
import clausia_pb2 as pb
import clausia_pb2_grpc as pbs

# Connect to gRPC server
channel = grpc.insecure_channel('localhost:50051')
stub = pbs.ClausIAStub(channel)

# Example 1: Extract text from PDF file
with open('contract.pdf', 'rb') as f:
    pdf_data = f.read()

request = pb.ExtractRequest(
    file=pb.FileContent(data=pdf_data, filename='contract.pdf')
)
response = stub.Extract(request)
print(response.text)  # HTML-formatted text

# Example 2: Extract metadata
metadata_response = stub.ExtractMetadata(request)
import json
metadata = json.loads(metadata_response.metadata)
print(f"Company: {metadata['external_company_name']}")
print(f"Start: {metadata['contract_start_date']}")
print(f"End: {metadata['contract_end_date']}")

# Example 3: Analyze risks (using S3 reference)
risk_request = pb.ExtractRequest(
    s3_ref=pb.S3Reference(object_key='abc123hash')
)
risk_response = stub.AnalyzeRisk(risk_request)
print(f"Risk Level: {risk_response.risk_level}")
print(f"High Risks: {risk_response.high}")
for finding in risk_response.findings:
    print(f"- {finding.risk_type} ({finding.severity})")

# Example 4: Chat about contract
chat_request = pb.ChatRequest(
    contract_id='contract-uuid-123',
    question='Apa saja kewajiban PT Pelindo dalam kontrak ini?',
    session_id='user-session-456'
)
chat_response = stub.Chat(chat_request)
print(chat_response.answer)  # HTML-formatted answer
```

### Database Inspection Tool

Use the included utility to inspect stored contracts:

```bash
python db_inspect.py
```

This tool displays:
- All contracts in the database
- Document hashes and metadata
- Content previews
- Chat history for each contract

---

## 📁 Project Structure

```
clausia-ai/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   └── services/
│       ├── __init__.py
│       ├── claude_service.py      # Claude AI integration
│       ├── pdf_reader_service.py  # OCR & text extraction
│       ├── database_service.py    # PostgreSQL operations
│       └── s3_service.py          # S3 storage operations
├── proto/
│   ├── __init__.py
│   └── clausia.proto              # gRPC service definitions
├── clausia_pb2.py                 # Generated protobuf messages
├── clausia_pb2_grpc.py            # Generated gRPC stubs
├── grpc_server.py                 # gRPC server implementation
├── db_inspect.py                  # Database inspection utility
├── model_list.py                  # Claude model configurations
├── requirements.txt               # Python dependencies
├── .env                           # Environment configuration
├── .gitignore
└── README.md
```

---

## 🧪 Development Notes

### Optimizations for Hackathon Speed

1. **OCR Settings:**
   - Low DPI (100) for faster processing vs. accuracy tradeoff
   - Parallel page processing using ThreadPoolExecutor
   - Limited page processing with `max_pages` parameter

2. **AI Model Selection:**
   - Claude 3.5 Haiku for metadata extraction (fast)
   - Claude 3.7 Sonnet for summarization and chat (balanced)
   - Claude 3.5 Haiku for risk analysis (cost-effective)

3. **Database Caching:**
   - Extracted OCR text stored in PostgreSQL to avoid re-processing
   - Services query database by `object_key` or `contract_id`
   - Chat history persisted for session continuity

### Known Limitations

- **Prototype Status**: Designed for hackathon demonstration, not production deployment
- **OCR Quality**: Low DPI setting may reduce accuracy for complex documents
- **Security**: Credentials in `.env` file (use secrets manager in production)
- **Error Handling**: Basic error handling suitable for controlled environment
- **Scalability**: Single-threaded gRPC server (use production-grade server for scale)

---

## 🔒 Security Considerations

> ⚠️ **Important**: This is a hackathon prototype. For production use:

1. **API Keys**: Use environment-based secret management (AWS Secrets Manager, HashiCorp Vault)
2. **Database**: Enable SSL connections, use connection pooling
3. **S3 Access**: Implement IAM roles and bucket policies
4. **Input Validation**: Add comprehensive input sanitization
5. **Rate Limiting**: Implement rate limiting for API endpoints
6. **Authentication**: Add JWT or OAuth for service-to-service auth

---

## 📊 Performance Metrics

Typical processing times (hackathon environment):

| Operation | Average Time | Notes |
|-----------|--------------|-------|
| OCR (10 pages) | 8-12 seconds | DPI=100, parallel processing |
| Metadata extraction | 2-3 seconds | Claude 3.5 Haiku |
| Summarization | 3-5 seconds | Claude 3.7 Sonnet |
| Risk analysis | 4-6 seconds | Claude 3.5 Haiku |
| Compliance check | 3-5 seconds | Claude 3.5 Haiku |
| Chat query | 2-4 seconds | Claude 3.7 Sonnet |

---

## 🤝 Contributing

This project was developed during IFEST 2025 hackathon. For questions or collaboration:

**Team:** 19° (Sembilan Belas Derajat)

---

## 📄 License

MIT License - see LICENSE file for details

---

## 🙏 Acknowledgments

- **IFEST 2025** for organizing the AI Innovation Challenge
- **PT Pelindo** for providing the legal document management use case
- **Anthropic** for Claude AI API
- **OpenSource Community** for Tesseract OCR, PyMuPDF, and other libraries

---

## 📚 Additional Resources

- [Protocol Buffers Documentation](https://developers.google.com/protocol-buffers)
- [gRPC Python Guide](https://grpc.io/docs/languages/python/)
- [Anthropic Claude API Docs](https://docs.anthropic.com/)
- [Tesseract OCR Documentation](https://tesseract-ocr.github.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

**Built with ❤️ by Team 19° during IFEST 2025**
