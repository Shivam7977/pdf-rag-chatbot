# PrivateDoc — Intelligent PDF Research Assistant

> Ask questions about your documents and get grounded answers with relevant source references.

PrivateDoc is a document question-answering system built around Retrieval-Augmented Generation (RAG).

Instead of sending an entire document to an LLM and hoping it finds the right information, PrivateDoc retrieves the most relevant sections from the uploaded PDFs, reranks them, and uses only that retrieved context to generate the final answer.

The system is designed with a production-oriented architecture, measurable retrieval quality, source attribution, and a mobile-first interface.

---

## ✨ What Makes PrivateDoc Different?

This project is not just a wrapper around an LLM.

The main focus is on building and evaluating the **retrieval pipeline** that determines what information the AI sees before generating an answer.

The retrieval pipeline evolved through multiple stages:

```text
PDF
 │
 ▼
Text Extraction
 │
 ▼
Chunking
 │
 ▼
Embeddings
 │
 ▼
Dense Retrieval
 │
 ▼
BM25 Keyword Retrieval
 │
 ▼
Reciprocal Rank Fusion (RRF)
 │
 ▼
Cross-Encoder Reranking
 │
 ▼
Top Relevant Context
 │
 ▼
LLM Generation
 │
 ▼
Grounded Answer + Sources

This allows the system to combine:

Semantic similarity
Exact keyword matching
Reciprocal Rank Fusion
Cross-encoder reranking
Context-grounded generation
Source/page attribution
Retrieval evaluation
🚀 Features
📄 PDF Question Answering

Upload a PDF and ask natural-language questions about its contents.

The system retrieves relevant passages instead of passing the entire document to the language model.

🔎 Hybrid Retrieval

Combines two different retrieval strategies:

Dense retrieval

Finds passages based on semantic meaning.

BM25

Finds passages based on lexical/keyword matching.

These results are combined using Reciprocal Rank Fusion (RRF).

🧠 Cross-Encoder Reranking

The initial retrieval stage intentionally retrieves a larger candidate set.

For example:

Hybrid Retrieval
      ↓
Top 20 candidates
      ↓
Cross-Encoder
      ↓
Top 5 most relevant chunks

This allows a more expensive relevance model to focus only on a small candidate set.

📊 Retrieval Evaluation

The retrieval pipeline is evaluated using a manually created question dataset.

The primary metric is:

Strict Recall@K

A retrieved result counts as correct only when the expected source document and page are matched.

This provides a more meaningful measure of whether the system actually finds the required evidence.

📚 Source Attribution

Answers are accompanied by the document and page information used during retrieval.

Example:

Answer
│
├── Source: report.pdf
│   Page: 4
│
├── Source: report.pdf
│   Page: 7
│
└── Source: report.pdf
    Page: 12
🛡️ Grounded Generation

The generation layer is instructed to answer using the retrieved context.

If the retrieved context does not contain the answer, the system can respond:

"I couldn't find this in the uploaded documents."

This reduces the risk of generating unsupported answers.

⚡ Streaming Responses

The application supports streaming responses so generated answers appear progressively rather than waiting for the complete response.

🌐 Mobile-First UI

The frontend is designed from the beginning to work across:

Desktop
Tablet
Mobile
📈 Retrieval Performance

The retrieval system was evaluated on a dataset of 30 questions.

Retrieval Method	Strict Recall@5	Strict Recall@10
Dense	76.7%	86.7%
Dense + Reranker	86.7%	90.0%
Hybrid (BM25 + Dense)	76.7%	90.0%
Hybrid + Reranker	90.0%	96.7%
Best configuration

Hybrid Retrieval + Cross-Encoder Reranking

achieved:

Recall@5  → 90.0%
Recall@10 → 96.7%

At Recall@10, the system retrieved the expected source/page for 29 out of 30 evaluation questions.

This evaluation was important because retrieval quality is one of the most critical components of a RAG system.

🏗️ Architecture
                         ┌─────────────────┐
                         │    PDF Upload   │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  PDF Parser     │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │     Chunker     │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   Embeddings    │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │    ChromaDB     │
                         └────────┬────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
             Dense Retrieval               BM25 Search
                    │                           │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                           RRF Fusion
                                  │
                                  ▼
                         Candidate Retrieval
                                  │
                                  ▼
                        Cross-Encoder Reranker
                                  │
                                  ▼
                         Top Relevant Chunks
                                  │
                                  ▼
                           LLM Generation
                                  │
                                  ▼
                    ┌────────────────────────┐
                    │ Answer + Source Pages │
                    └────────────────────────┘
🧩 Project Structure
pdf-rag-chatbot/
│
├── app/
│   ├── api/
│   │   └── chat.py
│   │
│   ├── db/
│   │   └── chroma.py
│   │
│   ├── schemas/
│   │   └── chat.py
│   │
│   ├── services/
│   │   ├── pdf_parser.py
│   │   ├── chunker.py
│   │   ├── embeddings.py
│   │   ├── retriever.py
│   │   ├── reranker.py
│   │   ├── hybrid_search.py
│   │   └── llm.py
│   │
│   └── main.py
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── evaluation/
│   └── ...
│
├── tests/
│   └── ...
│
├── data/
│   ├── uploads/
│   └── chroma/
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
🔄 How It Works
1. Upload

The user uploads a PDF document.

The backend receives and processes the document.

2. Parse

The PDF is converted into structured text while preserving page information.

Each page remains associated with its original source.

PDF
 ↓
Page 1 → text
Page 2 → text
Page 3 → text
...
3. Chunk

Long pages are divided into smaller overlapping chunks.

For example:

Page
 │
 ├── Chunk 1
 ├── Chunk 2
 ├── Chunk 3
 └── Chunk 4

Each chunk retains metadata such as:

{
  "page": 4,
  "source": "report.pdf"
}
4. Embed

Each chunk is converted into a numerical vector representing its semantic meaning.

These vectors allow semantically similar questions and document passages to be compared.

5. Store

The embeddings, original text, metadata, and chunk identifiers are stored in ChromaDB.

Conceptually:

Chunk
  ↓
Embedding
  ↓
Vector Database

+ original text
+ source
+ page
+ metadata
6. Retrieve

When a user asks a question, the question is embedded and compared against stored document vectors.

Dense retrieval finds semantically similar chunks.

BM25 independently searches for important lexical matches.

7. Fuse

The two retrieval result lists are combined using Reciprocal Rank Fusion.

This gives the system both:

Meaning-based retrieval
        +
Keyword-based retrieval
8. Rerank

The fused candidate set is passed through a cross-encoder reranker.

Instead of relying only on vector similarity, the reranker directly evaluates the relationship between:

Question ↔ Candidate Chunk

The strongest candidates are selected for generation.

9. Generate

The selected chunks are provided to the LLM as context.

The model is instructed to answer using the retrieved evidence rather than relying on unrelated knowledge.

10. Return Sources

The response includes the answer along with source/page references.

🧪 Evaluation Methodology

The retrieval system was evaluated using 30 manually created questions.

The evaluation focuses primarily on retrieval rather than judging whether an LLM's prose "sounds correct."

Primary Metric

Strict Recall@K

A question is counted as successfully retrieved only if the expected:

source document + page

appears in the top-K retrieved results.

Why strict evaluation?

A RAG system can produce a convincing answer even when the retrieval system selected the wrong evidence.

Strict source/page evaluation makes it possible to measure the retrieval layer independently.

Secondary diagnostics

Keyword-based matching is used only as a diagnostic signal and is not treated as the primary retrieval metric.

🤖 LLM Layer

The LLM is responsible for generation, not document retrieval.

The retrieval pipeline determines:

"Which pieces of the document are relevant?"

The LLM determines:

"How should I explain those pieces to the user?"

This separation is intentional.

The LLM layer is designed so the inference provider can be changed without rewriting the retrieval pipeline.

Local development

The project can run with a local Ollama model during development.

Deployment

The inference layer can be configured to use a hosted provider when deploying to infrastructure that does not have sufficient resources for local model inference.

This keeps the application architecture provider-agnostic.

🔐 Privacy & Deployment Model

PrivateDoc can be run locally with a local LLM for development and private document processing.

For the deployed portfolio version, the application can use a hosted inference provider.

Therefore:

Local Development
PDF → RAG Pipeline → Local LLM

Deployment
PDF → RAG Pipeline → Hosted LLM

The retrieval architecture remains the same.

🛠️ Tech Stack
Backend
Python
FastAPI
Retrieval
Sentence Transformers
BM25
Reciprocal Rank Fusion
Cross-Encoder Reranking
Vector Database
ChromaDB
LLM
Ollama / configurable hosted inference provider
Frontend
HTML
CSS
JavaScript
Tailwind CSS
Document Processing
PyMuPDF
📱 Frontend

The interface is being designed with a mobile-first approach.

Core interaction:

Upload Document
       ↓
Ask Question
       ↓
Streaming Answer
       ↓
View Sources

The UI is intentionally designed around the document-question-answering workflow rather than exposing implementation details to the user.

⚠️ Current Scope & Limitations

The current version deliberately focuses on reliable retrieval from typed/printed text PDFs.

The following are currently outside the primary scope:

OCR for scanned documents
Handwritten documents
Advanced table extraction
Complex image/figure understanding
Large-scale multilingual optimization
Chunk-level ground-truth evaluation
Precision@5 evaluation
Large evaluation datasets

These are potential future improvements rather than unfinished core requirements.

🔮 Future Improvements

Potential extensions include:

OCR fallback for scanned PDFs
Table-aware document parsing
Figure/image understanding
Multilingual generation and translation
Larger evaluation datasets
Additional retrieval metrics
Query rewriting
Better conversational memory
Multiple document collections
User authentication
Persistent chat history
🎯 Engineering Goals

The project was built with a few principles in mind:

1. Retrieval before generation

A powerful LLM cannot compensate for consistently poor retrieval.

2. Measure instead of assuming

Retrieval strategies are compared using a fixed evaluation dataset.

3. Modular architecture

Parsing, chunking, embedding, retrieval, reranking, generation, and API layers are separated.

4. Provider independence

The LLM inference layer is isolated from the core RAG pipeline.

5. Production-oriented design

The application is designed with:

API separation
Configuration management
Health checks
Streaming responses
Source attribution
Evaluation
Deployment considerations
🚀 Running Locally
Clone the repository
git clone <YOUR_REPOSITORY_URL>
cd pdf-rag-chatbot
Create virtual environment
python -m venv venv

Activate it on Windows:

venv\Scripts\Activate.ps1
Install dependencies
pip install -r requirements.txt
Configure environment variables

Create a .env file based on:

.env.example
Start the API
uvicorn app.main:app --reload

The API will be available at:

http://localhost:8000

FastAPI documentation:

http://localhost:8000/docs
📡 API
Health Check
GET /health
Chat
POST /chat

Example:

{
  "question": "What are global South funds?"
}

Example response:

{
  "answer": "Global South funds ...",
  "sources": [
    {
      "page": 1,
      "source": "report.pdf",
      "text": "..."
    }
  ]
}
📊 Project Progress
Component	Status
PDF parsing	✅
Chunking	✅
Embeddings	✅
Vector storage	✅
Dense retrieval	✅
Cross-encoder reranking	✅
Retrieval evaluation	✅
Hybrid BM25 + Dense search	✅
RRF fusion	✅
Source attribution	✅
Grounded generation	✅
SSE streaming	✅
Mobile-first frontend	🚧
File upload UI	🚧
Cloud deployment	🚧
Persistent chat history	🔜
📜 License

This project is intended as a portfolio and learning project.

Add your preferred license here.

👨‍💻 Why I Built This

The goal of this project was not simply to connect a PDF to an LLM.

The goal was to understand what happens before the LLM generates an answer:

How do we find the right information from a document?

By progressively comparing dense retrieval, reranking, hybrid search, and fusion techniques, the project turns that question into something measurable rather than relying on subjective answer quality.

The final retrieval pipeline achieved:

90.0% strict Recall@5
96.7% strict Recall@10

on the current 30-question evaluation set.

flagships

1. Conversational follow-up questions (mera top recommendation)
2. Answer confidence score dikhana
3. Auto-generated document summary on upload
4. Multi-document comparison mode

per pdf limit 20 mb and complete chat limit  50 mb.
