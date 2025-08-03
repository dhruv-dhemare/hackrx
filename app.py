

# import os
# import json
# import uuid
# from typing import List
# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from dotenv import load_dotenv
# import google.generativeai as genai
# from pinecone import Pinecone
# from upload_script import extract_text_from_pdf, semantic_chunk, upload_chunks_to_pinecone

# # === Load Env Vars ===
# load_dotenv()
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
# INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# # === Initialize Clients ===
# genai.configure(api_key=GOOGLE_API_KEY)
# pc = Pinecone(api_key=PINECONE_API_KEY)
# index = pc.Index(INDEX_NAME)

# # === FastAPI App ===
# app = FastAPI(title="HackRx Policy LLM Backend")

# # CORS Middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"]
# )

# # === Request Schema ===
# class QueryRequest(BaseModel):
#     file_id: str
#     queries: List[str]  # ⬅️ Only an array of queries now

# # === Health Check ===
# @app.get("/health")
# async def health_check():
#     return {"status": "ok", "pinecone_index": INDEX_NAME}

# # === Upload PDF (Single PDF Upload) ===
# @app.post("/upload")
# async def upload_policy(file: UploadFile = File(...)):
#     try:
#         # Save temp file
#         file_path = f"./temp_{file.filename}"
#         with open(file_path, "wb") as f:
#             f.write(await file.read())

#         # Extract text & chunk
#         pdf_text = extract_text_from_pdf(file_path)
#         chunks = semantic_chunk(pdf_text)

#         # Generate unique file_id (namespace)
#         file_id = os.path.splitext(file.filename)[0] + "_" + str(uuid.uuid4())[:6]

#         # Upload chunks to Pinecone
#         upload_chunks_to_pinecone(chunks, file_id)

#         os.remove(file_path)  # Cleanup temp file

#         return {"message": "File uploaded and indexed successfully", "file_id": file_id}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

# # === Query PDF (Array of Queries) ===
# @app.post("/query")
# async def query_policy(request: QueryRequest):
#     responses = []

#     for query_text in request.queries:
#         try:
#             # Embed Query
#             query_embedding = genai.embed_content(
#                 model="models/embedding-001",
#                 content=query_text,
#                 task_type="retrieval_query"
#             )["embedding"]

#             # Retrieve chunks from Pinecone (specific file namespace)
#             pinecone_results = index.query(
#                 vector=query_embedding,
#                 namespace=request.file_id,
#                 top_k=8,
#                 include_metadata=True
#             )

#             if not pinecone_results.get("matches"):
#                 responses.append({
#                     "decision": "Cannot determine",
#                     "amount": "Unknown",
#                     "justification": "No relevant info found.",
#                     "clause_ids": [],
#                     "risk_level": "Yellow",
#                     "answers": []
#                 })
#                 continue

#             context_chunks = [match["metadata"]["text"] for match in pinecone_results["matches"]]

#             # Build Gemini Prompt
#             prompt = f"""
#             You are an insurance policy assistant.
#             Use ONLY the clauses below to answer the query.

#             Clauses:
#             {'\n---\n'.join(context_chunks)}

#             Query:
#             {query_text}

#             Respond strictly in JSON:
#             {{
#                 "decision": "Yes / No / Cannot determine",
#                 "amount": "Coverage limit, percentage, or Unknown",
#                 "justification": "Explain using exact clauses",
#                 "clause_ids": ["..."],
#                 "risk_level": "Red / Orange / Yellow / Black",
#                 "answers": ["Direct factual answers"]
#             }}
#             """

#             model = genai.GenerativeModel("gemini-1.5-flash")
#             response = model.generate_content(prompt)
#             response_text = response.text.strip()

#             # Clean fenced JSON
#             if response_text.startswith("```json"):
#                 response_text = response_text[7:]
#             if response_text.endswith("```"):
#                 response_text = response_text[:-3]

#             try:
#                 responses.append(json.loads(response_text))
#             except:
#                 responses.append({
#                     "decision": "Cannot determine",
#                     "amount": "Unknown",
#                     "justification": "Parsing error.",
#                     "clause_ids": [],
#                     "risk_level": "Yellow",
#                     "answers": []
#                 })

#         except Exception as e:
#             responses.append({
#                 "decision": "Cannot determine",
#                 "amount": "Unknown",
#                 "justification": f"Error: {str(e)}",
#                 "clause_ids": [],
#                 "risk_level": "Yellow",
#                 "answers": []
#             })

#     return responses
       #raise HTTPException(status_code=500, detail=f"Webhook error: {str(e)}")

# import os
# import uuid
# import requests
# import tempfile
# from fastapi import FastAPI, HTTPException, Header
# from upload_script import extract_text_from_pdf, semantic_chunk, upload_chunks_to_pinecone
# from query_input import retrieve_chunks, ask_gemini

# app = FastAPI()
# @app.get("/")
# def root():
#     return {"status": "Server is running successfully!"}

# def download_pdf(pdf_input: str) -> str:
#     """Handles Google Drive, Direct PDF, and Base64 PDF download safely."""
#     tmp_dir = tempfile.gettempdir()
#     save_path = os.path.join(tmp_dir, "policy.pdf")

#     try:
#         # ✅ Case 1: Base64 PDF string
#         if pdf_input.startswith("data:application/pdf;base64,"):
#             import base64
#             pdf_data = base64.b64decode(pdf_input.split(",")[1])
#             with open(save_path, "wb") as f:
#                 f.write(pdf_data)
#             return save_path

#         # ✅ Case 2: Google Drive Links
#         if "drive.google.com" in pdf_input:
#             file_id = None
#             if "file/d/" in pdf_input:
#                 parts = pdf_input.split("/file/d/")
#                 if len(parts) > 1:
#                     file_id = parts[1].split("/")[0]
#             elif "id=" in pdf_input:
#                 parts = pdf_input.split("id=")
#                 if len(parts) > 1:
#                     file_id = parts[1].split("&")[0]

#             if not file_id:
#                 raise HTTPException(status_code=400, detail="Invalid Google Drive link format.")
            
#             pdf_url = f"https://drive.google.com/uc?export=download&id={file_id}"
#             session = requests.Session()
#             response = session.get(pdf_url, stream=True)

#             # Handle Google Drive virus scan confirmation pages
#             if "text/html" in response.headers.get("Content-Type", ""):
#                 for k, v in response.cookies.items():
#                     if k.startswith("download_warning"):
#                         confirm_url = f"{pdf_url}&confirm={v}"
#                         response = session.get(confirm_url, stream=True)
#                         break

#         else:
#             # ✅ Case 3: Direct PDF URLs
#             response = requests.get(pdf_input, stream=True, allow_redirects=True)

#         # ✅ Verify PDF signature (even if Content-Type header is missing)
#         content = response.content
#         if not content.startswith(b"%PDF"):
#             raise HTTPException(status_code=400, detail="Failed to download a valid PDF file.")

#         with open(save_path, "wb") as f:
#             f.write(content)

#         return save_path

#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Failed to process PDF URL: {str(e)}")


# @app.post("/hackrx/run")
# async def hackrx_run(payload: dict, authorization: str = Header(None)):
#     try:
#         pdf_url = payload.get("documents")
#         questions = payload.get("questions")

#         if not pdf_url or not questions or not isinstance(questions, list) or len(questions) == 0:
#             raise HTTPException(status_code=400, detail="Missing or invalid 'documents' or 'questions'.")

#         # ✅ Step 1: Download PDF
#         pdf_path = download_pdf(pdf_url)

#         # ✅ Step 2: Extract text & Chunk
#         file_id = f"file_{uuid.uuid4().hex[:6]}"
#         pdf_text = extract_text_from_pdf(pdf_path)
#         if not pdf_text.strip():
#             raise HTTPException(status_code=400, detail="Extracted PDF text is empty.")
#         chunks = semantic_chunk(pdf_text)
#         upload_chunks_to_pinecone(chunks, file_id)
#         print("Chunks uploaded:", len(chunks))


#         # ✅ Step 3: Answer each question
#         answers = []
#         for q in questions:
#             try:
#                 retrieved_chunks = retrieve_chunks(q, file_id,top_k=8)
#                 print("\n--- Question:", q)
#                 print("Retrieved Chunks:\n", retrieved_chunks)

#                 result = ask_gemini(q, retrieved_chunks)
#                 answer_text = result["answers"][0] if result and "answers" in result and result["answers"] else "Cannot determine"
#                 answers.append(answer_text)
#             except Exception:
#                 answers.append("Cannot determine")

#         return {"answers": answers}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Webhook error: {str(e)}")

#nicely working code 
import os
import fitz  # PyMuPDF
import uuid
import re
import hashlib
import json
import asyncio
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from dataclasses import dataclass
from pdf2image import convert_from_path
import pytesseract
import tempfile
import time
from rank_bm25 import BM25Okapi
import google.generativeai as genai
import email
from email import policy
from bs4 import BeautifulSoup
from docx import Document

# === Load Env Variables ===
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# === Configure Gemini & Pinecone ===
genai.configure(api_key=GOOGLE_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX_NAME,
        dimension=768,
        metric="cosine",
        spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION)
    )
index = pc.Index(INDEX_NAME)

app = FastAPI()

@dataclass
class DocumentChunk:
    text: str
    chunk_id: str
    page_num: int
    chunk_type: str
    metadata: Dict

# === PDF Download (URL Support) ===
def download_pdf(pdf_url: str) -> str:
    tmp_path = os.path.join(tempfile.gettempdir(), "policy.pdf")
    r = requests.get(pdf_url, stream=True)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to download PDF.")
    with open(tmp_path, "wb") as f:
        f.write(r.content)
    return tmp_path

# === OCR Fallback ===
def ocr_pdf(pdf_path: str) -> str:
    pages = convert_from_path(pdf_path)
    text = ""
    for page in pages:
        text += pytesseract.image_to_string(page)
    return text

# === PDF Text Extraction ===
def extract_text_from_pdf_enhanced(pdf_path: str) -> Tuple[str, Dict]:
    doc = fitz.open(pdf_path)
    full_text = ""
    structured_content = {'definitions': {}, 'clauses': {}, 'tables': [], 'key_terms': set()}
    for page_num, page in enumerate(doc, start=1):
        page_text = page.get_text("text").strip()
        if page_text:
            full_text += f"\n[Page {page_num}]\n{page_text}\n"
            definition_matches = re.findall(r'([A-Z][a-z\s]+)\s*means\s+([^.]+\.)', page_text)
            for term, definition in definition_matches:
                structured_content['definitions'][term.strip()] = definition.strip()
                structured_content['key_terms'].add(term.strip().lower())
            clause_matches = re.findall(r'(\d+(?:\.\d+)*)\s+([^\n]+)', page_text)
            for clause_num, clause_text in clause_matches:
                structured_content['clauses'][clause_num] = clause_text.strip()
    return full_text, structured_content

# === DOCX Extraction ===
def extract_text_from_docx(file_path: str) -> Tuple[str, Dict]:
    doc = Document(file_path)
    full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    structured_content = {"headings": [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]}
    return full_text, structured_content

# === Email Extraction ===
def extract_text_from_email(file_path: str) -> Tuple[str, Dict]:
    with open(file_path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)

    email_text = ""
    structured_content = {"subject": msg["subject"], "from": msg["from"], "to": msg["to"], "body": ""}

    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            email_text += part.get_content()
        elif part.get_content_type() == "text/html":
            soup = BeautifulSoup(part.get_content(), "html.parser")
            email_text += soup.get_text()

    structured_content["body"] = email_text.strip()
    return email_text, structured_content

# === Smart Chunking ===
def smart_semantic_chunk(text: str, structured_content: Dict, chunk_size: int = 400, overlap: int = 80) -> List[DocumentChunk]:
    words = text.split()
    chunks = []
    for term, definition in structured_content.get('definitions', {}).items():
        chunks.append(DocumentChunk(
            text=f"{term} means {definition}",
            chunk_id=f"def_{len(chunks)}",
            page_num=0,
            chunk_type='definition',
            metadata={'term': term, 'importance': 'high'}
        ))
    for i in range(0, len(words), chunk_size - overlap):
        chunk_text = " ".join(words[i:i + chunk_size])
        if len(chunk_text.split()) >= 30:
            chunk_type = 'general'
            importance = 'medium'
            if any(term in chunk_text.lower() for term in structured_content.get('key_terms', set())):
                chunk_type, importance = 'key_term', 'high'
            elif re.search(r'\d+(?:\.\d+)*\s', chunk_text):
                chunk_type, importance = 'clause', 'high'
            elif any(keyword in chunk_text.lower() for keyword in ['waiting period', 'coverage', 'premium', 'deductible']):
                chunk_type, importance = 'policy_term', 'high'
            chunks.append(DocumentChunk(
                text=chunk_text.strip(),
                chunk_id=f"chunk_{len(chunks)}",
                page_num=i // 200 + 1,
                chunk_type=chunk_type,
                metadata={'importance': importance, 'word_count': len(chunk_text.split())}
            ))
    return chunks

# === Embeddings (Gemini) ===
def embed_text(text: str):
    embedding = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="retrieval_document"
    )["embedding"]
    return embedding

def embed_text_for_query(text: str):
    embedding = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="retrieval_query"
    )["embedding"]
    return embedding

# === Parallel Chunk Embedding ===
async def embed_chunks_parallel(chunks: List[DocumentChunk], max_workers: int = 8) -> List[Tuple]:
    def embed_single_chunk(chunk: DocumentChunk):
        embedding = embed_text(chunk.text)
        chunk_hash = hashlib.md5(chunk.text.encode()).hexdigest()
        return (str(uuid.uuid4()), embedding, {
            "text": chunk.text,
            "hash": chunk_hash,
            "chunk_type": chunk.chunk_type,
            "importance": chunk.metadata.get('importance', 'medium'),
            "page_num": chunk.page_num
        })
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(embed_single_chunk, chunks))

async def upload_chunks(chunks: List[DocumentChunk], file_id: str):
    embedded = await embed_chunks_parallel(chunks)
    index.upsert(vectors=embedded, namespace=file_id)

# === Hybrid Search (BM25 + Vector) ===
async def hybrid_search(query: str, file_id: str, bm25: BM25Okapi, chunks: List[str], top_k: int = 10):
    async def bm25_search():
        scores = bm25.get_scores(query.split())
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [chunks[i] for i in top_indices]

    async def pinecone_search():
        query_embedding = embed_text_for_query(query)
        res = index.query(namespace=file_id, vector=query_embedding, top_k=top_k, include_metadata=True)
        return [m["metadata"]["text"] for m in res["matches"]]

    bm25_results, pinecone_results = await asyncio.gather(bm25_search(), pinecone_search())
    seen, combined = set(), []
    for c in bm25_results + pinecone_results:
        if c not in seen:
            seen.add(c)
            combined.append(c)
    return combined[:top_k]

# === Batched Gemini QA ===
# === Batched Gemini QA (Improved) ===
# === Enhanced Batched Gemini QA ===
async def ask_gemini_batch(questions: List[str], context_chunks: List[str], structured_content: Dict = None, retries: int = 3):
    """
    Ask Gemini model a batch of questions using provided context chunks.
    Ensures detailed, clause-backed answers and avoids hallucination.
    """
    combined_context = "\n\n--- CHUNK ---\n".join(context_chunks)
    question_list = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
    
    # Optional: include definitions/clauses if available for more grounded answers
    definitions_section = ""
    if structured_content and structured_content.get("definitions"):
        definitions_section = f"""
DEFINITIONS & KEY TERMS:
{json.dumps(structured_content.get("definitions", {}), indent=2)}
"""

    prompt = f"""
You are an expert insurance analyst.
Your job is to extract **accurate answers strictly from the document text provided**. 
Do not infer or hallucinate any information not present in the text.

DOCUMENT TEXT:
{combined_context}

{definitions_section}

QUESTIONS:
{question_list}

Answer each question in **clear, complete sentences** with specific clause references or supporting context from the document where possible.
If the answer is not explicitly stated in the text, respond with: "Not specified in the policy text."

Output strictly in this JSON format:
{{
  "answers": [
    "Answer 1 with full context and clause references if present",
    "Answer 2 ...",
    "Answer 3 ..."
  ]
}}
"""
    
    for attempt in range(retries):
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.0,  # strictly factual
                    "max_output_tokens": 1400
                }
            )
            
            parsed = json.loads(response.text)
            if "answers" in parsed and isinstance(parsed["answers"], list):
                return parsed["answers"]
            else:
                raise ValueError("Invalid response format from Gemini.")
        
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise e



# === API Endpoint ===
@app.post("/hackrx/run")
async def hackrx_run(file: UploadFile = File(None), pdf_url: str = Form(None), questions: str = Form(...)):
    start_time = time.time()

    try:
        questions_list = json.loads(questions)
    except:
        raise HTTPException(status_code=400, detail="Invalid questions format. Must be a JSON list.")

    if not file and not pdf_url:
        raise HTTPException(status_code=400, detail="Provide either a file or pdf_url.")

    # === File Handling ===
    if pdf_url:
        file_path = download_pdf(pdf_url)
        file_type = "pdf"
    else:
        file_ext = file.filename.split(".")[-1].lower()
        file_path = os.path.join(tempfile.gettempdir(), file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        file_type = file_ext

    # === Extract Content Based on Type ===
    if file_type == "pdf":
        text, structured_content = extract_text_from_pdf_enhanced(file_path)
        if not text.strip():
            text = ocr_pdf(file_path)
    elif file_type == "docx":
        text, structured_content = extract_text_from_docx(file_path)
    elif file_type in ["eml", "email"]:
        text, structured_content = extract_text_from_email(file_path)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF, DOCX, and EML are allowed.")

    # === Hash File & Handle Indexing ===
    file_hash = hashlib.md5(text.encode()).hexdigest()
    stats = index.describe_index_stats()

    if file_hash not in stats.get("namespaces", {}):
        chunks = smart_semantic_chunk(text, structured_content)
        await upload_chunks(chunks, file_hash)
        chunk_texts = [c.text for c in chunks]
    else:
        res = index.query(vector=[0.0]*768, namespace=file_hash, top_k=50, include_metadata=True)
        chunk_texts = [m["metadata"]["text"] for m in res["matches"]]

    # === Hybrid Search & QA ===
    bm25 = BM25Okapi([chunk.split() for chunk in chunk_texts])
    context_chunks = await hybrid_search(" ".join(questions_list), file_hash, bm25, chunk_texts)
    answers = await ask_gemini_batch(questions_list, context_chunks,structured_content)

    return {
        "file_id": file_hash,
        "file_type": file_type,
        "answers": answers,
        "processing_time": f"{time.time()-start_time:.2f}s"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)



# import os
# import fitz  # PyMuPDF
# import uuid
# import re
# import hashlib
# import json
# import asyncio
# import aiofiles
# import aiohttp
# from concurrent.futures import ThreadPoolExecutor, as_completed
# from typing import List, Dict, Tuple, Optional, Union
# from fastapi import FastAPI, UploadFile, File, Form, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from dotenv import load_dotenv
# from pinecone import Pinecone, ServerlessSpec
# from dataclasses import dataclass, asdict
# from pdf2image import convert_from_path
# import pytesseract
# import tempfile
# import time
# from rank_bm25 import BM25Okapi
# import google.generativeai as genai
# from email.message import EmailMessage
# import email
# from docx import Document
# import mammoth
# from pathlib import Path
# import logging
# from functools import lru_cache
# import numpy as np
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.metrics.pairwise import cosine_similarity
# import asyncpg
# from asyncpg.pool import Pool
# import psycopg2
# from datetime import datetime, timedelta
# from sqlalchemy import create_engine, text
# from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
# from sqlalchemy.orm import sessionmaker
# import pickle
# from cachetools import TTLCache

# # === Setup Logging ===
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # === Load Env Variables ===
# load_dotenv()

# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
# INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
# PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
# PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")
# DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/document_qa")

# # === Configure Gemini & Pinecone ===
# genai.configure(api_key=GOOGLE_API_KEY)
# pc = Pinecone(api_key=PINECONE_API_KEY)

# # === PostgreSQL Database Schema and Connection ===
# class DatabaseManager:
#     def __init__(self):
#         self.pool: Optional[Pool] = None
#         self.engine = create_async_engine(DATABASE_URL, echo=False, pool_size=20, max_overflow=30)
    
#     async def initialize(self):
#         """Initialize database connection pool and create tables"""
#         self.pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
#         await self.create_tables()
    
#     async def create_tables(self):
#         """Create optimized database schema for document QA"""
#         create_tables_sql = """
#         -- Enable extensions
#         CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
#         CREATE EXTENSION IF NOT EXISTS "pg_trgm";
#         CREATE EXTENSION IF NOT EXISTS "btree_gin";
#         CREATE EXTENSION IF NOT EXISTS "vector";  -- For pgvector if available
        
#         -- Documents table with metadata and full-text search
#         CREATE TABLE IF NOT EXISTS documents (
#             id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
#             file_hash VARCHAR(64) UNIQUE NOT NULL,
#             filename VARCHAR(255),
#             file_type VARCHAR(20) NOT NULL,
#             content_size INTEGER,
#             upload_timestamp TIMESTAMP DEFAULT NOW(),
#             last_accessed TIMESTAMP DEFAULT NOW(),
#             processing_status VARCHAR(20) DEFAULT 'pending',
#             structured_data JSONB,
#             search_vector tsvector,
#             metadata JSONB DEFAULT '{}'::jsonb
#         );
        
#         -- Document chunks with enhanced indexing
#         CREATE TABLE IF NOT EXISTS document_chunks (
#             id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
#             document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
#             chunk_text TEXT NOT NULL,
#             chunk_hash VARCHAR(64) UNIQUE NOT NULL,
#             chunk_type VARCHAR(50) DEFAULT 'general',
#             page_number INTEGER DEFAULT 0,
#             importance_score FLOAT DEFAULT 0.5,
#             word_count INTEGER,
#             chunk_metadata JSONB DEFAULT '{}'::jsonb,
#             search_vector tsvector,
#             created_at TIMESTAMP DEFAULT NOW()
#         );
        
#         -- Key-value cache for embeddings and results
#         CREATE TABLE IF NOT EXISTS embeddings_cache (
#             id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
#             content_hash VARCHAR(64) UNIQUE NOT NULL,
#             embedding_vector FLOAT[] NOT NULL,
#             embedding_type VARCHAR(20) DEFAULT 'document',
#             created_at TIMESTAMP DEFAULT NOW(),
#             last_used TIMESTAMP DEFAULT NOW(),
#             use_count INTEGER DEFAULT 1
#         );
        
#         -- Query results cache with analytics
#         CREATE TABLE IF NOT EXISTS query_cache (
#             id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
#             query_hash VARCHAR(64) NOT NULL,
#             document_hash VARCHAR(64) NOT NULL,
#             questions JSONB NOT NULL,
#             answers JSONB NOT NULL,
#             processing_time FLOAT,
#             accuracy_score FLOAT,
#             created_at TIMESTAMP DEFAULT NOW(),
#             last_used TIMESTAMP DEFAULT NOW(),
#             use_count INTEGER DEFAULT 1,
#             UNIQUE(query_hash, document_hash)
#         );
        
#         -- Document definitions for quick lookup
#         CREATE TABLE IF NOT EXISTS document_definitions (
#             id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
#             document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
#             term VARCHAR(255) NOT NULL,
#             definition TEXT NOT NULL,
#             confidence_score FLOAT DEFAULT 0.5,
#             search_vector tsvector,
#             created_at TIMESTAMP DEFAULT NOW(),
#             UNIQUE(document_id, term)
#         );
        
#         -- Question patterns for smart routing
#         CREATE TABLE IF NOT EXISTS question_patterns (
#             id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
#             pattern_type VARCHAR(50) NOT NULL,
#             keywords TEXT[] NOT NULL,
#             regex_pattern TEXT,
#             priority_score FLOAT DEFAULT 0.5,
#             chunk_types TEXT[] DEFAULT ARRAY['general'],
#             created_at TIMESTAMP DEFAULT NOW()
#         );
        
#         -- Performance analytics
#         CREATE TABLE IF NOT EXISTS query_analytics (
#             id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
#             document_type VARCHAR(20),
#             question_types TEXT[],
#             processing_time FLOAT,
#             cache_hit BOOLEAN DEFAULT FALSE,
#             accuracy_feedback FLOAT,
#             timestamp TIMESTAMP DEFAULT NOW()
#         );
        
#         -- Create optimized indexes
#         CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);
#         CREATE INDEX IF NOT EXISTS idx_documents_file_type ON documents(file_type);
#         CREATE INDEX IF NOT EXISTS idx_documents_search_vector ON documents USING GIN(search_vector);
#         CREATE INDEX IF NOT EXISTS idx_documents_structured_data ON documents USING GIN(structured_data);
#         CREATE INDEX IF NOT EXISTS idx_documents_last_accessed ON documents(last_accessed);
        
#         CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id);
#         CREATE INDEX IF NOT EXISTS idx_chunks_type ON document_chunks(chunk_type);
#         CREATE INDEX IF NOT EXISTS idx_chunks_importance ON document_chunks(importance_score DESC);
#         CREATE INDEX IF NOT EXISTS idx_chunks_search_vector ON document_chunks USING GIN(search_vector);
#         CREATE INDEX IF NOT EXISTS idx_chunks_hash ON document_chunks(chunk_hash);
#         CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON document_chunks USING GIN(chunk_metadata);
        
#         CREATE INDEX IF NOT EXISTS idx_embeddings_hash ON embeddings_cache(content_hash);
#         CREATE INDEX IF NOT EXISTS idx_embeddings_type ON embeddings_cache(embedding_type);
#         CREATE INDEX IF NOT EXISTS idx_embeddings_last_used ON embeddings_cache(last_used);
        
#         CREATE INDEX IF NOT EXISTS idx_query_cache_hashes ON query_cache(query_hash, document_hash);
#         CREATE INDEX IF NOT EXISTS idx_query_cache_created ON query_cache(created_at);
#         CREATE INDEX IF NOT EXISTS idx_query_cache_use_count ON query_cache(use_count DESC);
        
#         CREATE INDEX IF NOT EXISTS idx_definitions_document_id ON document_definitions(document_id);
#         CREATE INDEX IF NOT EXISTS idx_definitions_term ON document_definitions(term);
#         CREATE INDEX IF NOT EXISTS idx_definitions_search_vector ON document_definitions USING GIN(search_vector);
        
#         CREATE INDEX IF NOT EXISTS idx_patterns_type ON question_patterns(pattern_type);
#         CREATE INDEX IF NOT EXISTS idx_patterns_keywords ON question_patterns USING GIN(keywords);
        
#         CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON query_analytics(timestamp);
#         CREATE INDEX IF NOT EXISTS idx_analytics_document_type ON query_analytics(document_type);
        
#         -- Insert default question patterns
#         INSERT INTO question_patterns (pattern_type, keywords, regex_pattern, priority_score, chunk_types) 
#         VALUES 
#             ('definition', ARRAY['what is', 'define', 'definition', 'meaning', 'means'], 
#              '\\b(what is|define|definition|meaning|means)\\b', 0.9, ARRAY['definition', 'clause']),
#             ('waiting_period', ARRAY['waiting period', 'wait time', 'how long wait'], 
#              '\\b(waiting period|wait time|how long)\\b', 0.8, ARRAY['policy_term', 'clause']),
#             ('coverage', ARRAY['cover', 'coverage', 'covered', 'include', 'benefit'], 
#              '\\b(cover|coverage|covered|include|benefit)\\b', 0.7, ARRAY['policy_term', 'general']),
#             ('exclusion', ARRAY['exclude', 'excluded', 'not cover', 'exception'], 
#              '\\b(exclude|excluded|not cover|exception)\\b', 0.8, ARRAY['exclusion', 'clause']),
#             ('amount', ARRAY['amount', 'cost', 'price', 'premium', 'sum insured', 'limit'], 
#              '\\b(amount|cost|price|premium|sum insured|limit)\\b', 0.7, ARRAY['policy_term', 'clause'])
#         ON CONFLICT DO NOTHING;
#         """
        
#         async with self.pool.acquire() as conn:
#             await conn.execute(create_tables_sql)
    
#     async def close(self):
#         """Close database connections"""
#         if self.pool:
#             await self.pool.close()
#         await self.engine.dispose()

# # Global database manager
# db_manager = DatabaseManager()

# # === Enhanced Document Storage with PostgreSQL ===
# class PostgreSQLDocumentStore:
    
#     @staticmethod
#     async def store_document(doc_info: 'DocumentInfo', file_hash: str, filename: str = None) -> str:
#         """Store document with full-text search optimization"""
#         async with db_manager.pool.acquire() as conn:
#             # Check if document already exists
#             existing = await conn.fetchrow(
#                 "SELECT id FROM documents WHERE file_hash = $1", file_hash
#             )
            
#             if existing:
#                 # Update last accessed
#                 await conn.execute(
#                     "UPDATE documents SET last_accessed = NOW() WHERE file_hash = $1", 
#                     file_hash
#                 )
#                 return str(existing['id'])
            
#             # Create search vector for full-text search
#             search_text = f"{doc_info.content} {json.dumps(doc_info.structured_data)}"
            
#             # Insert new document
#             doc_id = await conn.fetchval("""
#                 INSERT INTO documents (
#                     file_hash, filename, file_type, content_size, 
#                     structured_data, search_vector, metadata
#                 ) VALUES (
#                     $1, $2, $3, $4, $5, to_tsvector('english', $6), $7
#                 ) RETURNING id
#             """, file_hash, filename, doc_info.file_type, len(doc_info.content),
#                 json.dumps(doc_info.structured_data), search_text, 
#                 json.dumps(doc_info.metadata))
            
#             return str(doc_id)
    
#     @staticmethod
#     async def store_chunks_batch(chunks: List['DocumentChunk'], document_id: str):
#         """Efficiently store document chunks with batch insert"""
#         async with db_manager.pool.acquire() as conn:
#             # Prepare batch data
#             chunk_data = []
#             for chunk in chunks:
#                 chunk_hash = hashlib.md5(chunk.text.encode()).hexdigest()
#                 chunk_data.append((
#                     document_id, chunk.text, chunk_hash, chunk.chunk_type,
#                     chunk.page_num, chunk.importance_score, len(chunk.text.split()),
#                     json.dumps(chunk.metadata), chunk.text  # Last for tsvector
#                 ))
            
#             # Batch insert with conflict handling
#             await conn.executemany("""
#                 INSERT INTO document_chunks (
#                     document_id, chunk_text, chunk_hash, chunk_type, page_number,
#                     importance_score, word_count, chunk_metadata, search_vector
#                 ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, to_tsvector('english', $9))
#                 ON CONFLICT (chunk_hash) DO NOTHING
#             """, chunk_data)
    
#     @staticmethod
#     async def store_definitions(document_id: str, definitions: Dict[str, str]):
#         """Store document definitions for quick lookup"""
#         async with db_manager.pool.acquire() as conn:
#             definition_data = []
#             for term, definition in definitions.items():
#                 definition_data.append((
#                     document_id, term, definition, 
#                     f"{term} {definition}"  # For search vector
#                 ))
            
#             if definition_data:
#                 await conn.executemany("""
#                     INSERT INTO document_definitions (
#                         document_id, term, definition, search_vector
#                     ) VALUES ($1, $2, $3, to_tsvector('english', $4))
#                     ON CONFLICT (document_id, term) DO UPDATE SET
#                         definition = EXCLUDED.definition,
#                         search_vector = EXCLUDED.search_vector
#                 """, definition_data)

# # === Intelligent Query Cache with PostgreSQL ===
# class PostgreSQLQueryCache:
    
#     @staticmethod
#     async def get_cached_result(questions: List[str], document_hash: str) -> Optional[List[str]]:
#         """Get cached query result with intelligent matching"""
#         query_hash = hashlib.md5(json.dumps(sorted(questions)).encode()).hexdigest()
        
#         async with db_manager.pool.acquire() as conn:
#             # Try exact match first
#             result = await conn.fetchrow("""
#                 SELECT answers, use_count FROM query_cache 
#                 WHERE query_hash = $1 AND document_hash = $2
#                 AND created_at > NOW() - INTERVAL '24 hours'
#             """, query_hash, document_hash)
            
#             if result:
#                 # Update usage stats
#                 await conn.execute("""
#                     UPDATE query_cache SET 
#                         last_used = NOW(), 
#                         use_count = use_count + 1 
#                     WHERE query_hash = $1 AND document_hash = $2
#                 """, query_hash, document_hash)
                
#                 return result['answers']
            
#             # Try similarity matching for partial cache hits
#             similar_results = await conn.fetch("""
#                 SELECT questions, answers, 
#                        similarity(questions::text, $1) as sim_score
#                 FROM query_cache 
#                 WHERE document_hash = $2 
#                   AND created_at > NOW() - INTERVAL '7 days'
#                   AND similarity(questions::text, $1) > 0.7
#                 ORDER BY sim_score DESC, use_count DESC
#                 LIMIT 3
#             """, json.dumps(questions), document_hash)
            
#             if similar_results:
#                 # Log potential cache optimization
#                 logger.info(f"Found {len(similar_results)} similar cached queries")
            
#             return None
    
#     @staticmethod
#     async def cache_result(questions: List[str], document_hash: str, answers: List[str], 
#                           processing_time: float, accuracy_score: float = None):
#         """Cache query result with analytics"""
#         query_hash = hashlib.md5(json.dumps(sorted(questions)).encode()).hexdigest()
        
#         async with db_manager.pool.acquire() as conn:
#             await conn.execute("""
#                 INSERT INTO query_cache (
#                     query_hash, document_hash, questions, answers, 
#                     processing_time, accuracy_score
#                 ) VALUES ($1, $2, $3, $4, $5, $6)
#                 ON CONFLICT (query_hash, document_hash) DO UPDATE SET
#                     answers = EXCLUDED.answers,
#                     processing_time = EXCLUDED.processing_time,
#                     accuracy_score = EXCLUDED.accuracy_score,
#                     last_used = NOW(),
#                     use_count = query_cache.use_count + 1
#             """, query_hash, document_hash, json.dumps(questions), 
#                 json.dumps(answers), processing_time, accuracy_score)

# # === Smart Search with PostgreSQL Full-Text Search ===
# class PostgreSQLSmartSearch:
    
#     @staticmethod
#     async def hybrid_search(questions: List[str], document_hash: str, limit: int = 15) -> List[Dict]:
#         """Perform hybrid search combining PostgreSQL FTS and vector similarity"""
#         combined_query = " ".join(questions)
        
#         async with db_manager.pool.acquire() as conn:
#             # Get document ID
#             doc_result = await conn.fetchrow(
#                 "SELECT id FROM documents WHERE file_hash = $1", document_hash
#             )
            
#             if not doc_result:
#                 return []
            
#             document_id = doc_result['id']
            
#             # PostgreSQL full-text search with ranking
#             fts_results = await conn.fetch("""
#                 SELECT 
#                     chunk_text,
#                     chunk_type,
#                     importance_score,
#                     page_number,
#                     chunk_metadata,
#                     ts_rank(search_vector, plainto_tsquery('english', $1)) as fts_score,
#                     'fts' as search_type
#                 FROM document_chunks 
#                 WHERE document_id = $2 
#                   AND search_vector @@ plainto_tsquery('english', $1)
#                 ORDER BY 
#                     ts_rank(search_vector, plainto_tsquery('english', $1)) DESC,
#                     importance_score DESC
#                 LIMIT $3
#             """, combined_query, document_id, limit)
            
#             # Get high-importance chunks even if not matching FTS
#             importance_results = await conn.fetch("""
#                 SELECT 
#                     chunk_text,
#                     chunk_type,
#                     importance_score,
#                     page_number,
#                     chunk_metadata,
#                     importance_score as fts_score,
#                     'importance' as search_type
#                 FROM document_chunks 
#                 WHERE document_id = $1 
#                   AND importance_score > 0.7
#                   AND chunk_type IN ('definition', 'policy_term', 'clause')
#                 ORDER BY importance_score DESC
#                 LIMIT $2
#             """, document_id, max(5, limit // 3))
            
#             # Search definitions separately
#             definition_results = await conn.fetch("""
#                 SELECT 
#                     CONCAT('DEFINITION: ', term, ' means ', definition) as chunk_text,
#                     'definition' as chunk_type,
#                     0.9 as importance_score,
#                     0 as page_number,
#                     '{}' as chunk_metadata,
#                     ts_rank(search_vector, plainto_tsquery('english', $1)) as fts_score,
#                     'definition' as search_type
#                 FROM document_definitions 
#                 WHERE document_id = $2 
#                   AND search_vector @@ plainto_tsquery('english', $1)
#                 ORDER BY ts_rank(search_vector, plainto_tsquery('english', $1)) DESC
#                 LIMIT 5
#             """, combined_query, document_id)
            
#             # Combine and deduplicate results
#             all_results = list(fts_results) + list(importance_results) + list(definition_results)
            
#             # Deduplicate by text content
#             seen_texts = set()
#             unique_results = []
#             for result in all_results:
#                 text_hash = hashlib.md5(result['chunk_text'].encode()).hexdigest()
#                 if text_hash not in seen_texts:
#                     seen_texts.add(text_hash)
#                     unique_results.append(dict(result))
            
#             # Sort by combined score
#             unique_results.sort(
#                 key=lambda x: (x['fts_score'] * 0.6 + x['importance_score'] * 0.4), 
#                 reverse=True
#             )
            
#             return unique_results[:limit]
    
#     @staticmethod
#     async def get_question_patterns(questions: List[str]) -> List[Dict]:
#         """Get matching question patterns for optimization"""
#         async with db_manager.pool.acquire() as conn:
#             combined_text = " ".join(questions).lower()
            
#             patterns = await conn.fetch("""
#                 SELECT pattern_type, keywords, chunk_types, priority_score
#                 FROM question_patterns
#                 WHERE $1 ~ regex_pattern
#                 ORDER BY priority_score DESC
#             """, combined_text)
            
#             return [dict(p) for p in patterns]

# # === Enhanced Embedding Cache ===
# class PostgreSQLEmbeddingCache:
    
#     @staticmethod
#     async def get_embedding(text: str, embedding_type: str = 'document') -> Optional[List[float]]:
#         """Get cached embedding with usage tracking"""
#         content_hash = hashlib.md5(text.encode()).hexdigest()
        
#         async with db_manager.pool.acquire() as conn:
#             result = await conn.fetchrow("""
#                 SELECT embedding_vector FROM embeddings_cache 
#                 WHERE content_hash = $1 AND embedding_type = $2
#             """, content_hash, embedding_type)
            
#             if result:
#                 # Update usage stats
#                 await conn.execute("""
#                     UPDATE embeddings_cache SET 
#                         last_used = NOW(), 
#                         use_count = use_count + 1 
#                     WHERE content_hash = $1 AND embedding_type = $2
#                 """, content_hash, embedding_type)
                
#                 return result['embedding_vector']
            
#             return None
    
#     @staticmethod
#     async def cache_embedding(text: str, embedding: List[float], embedding_type: str = 'document'):
#         """Cache embedding with deduplication"""
#         content_hash = hashlib.md5(text.encode()).hexdigest()
        
#         async with db_manager.pool.acquire() as conn:
#             await conn.execute("""
#                 INSERT INTO embeddings_cache (content_hash, embedding_vector, embedding_type)
#                 VALUES ($1, $2, $3)
#                 ON CONFLICT (content_hash) DO UPDATE SET
#                     last_used = NOW(),
#                     use_count = embeddings_cache.use_count + 1
#             """, content_hash, embedding, embedding_type)
    
#     @staticmethod
#     async def cleanup_old_embeddings(days: int = 30):
#         """Clean up old unused embeddings"""
#         async with db_manager.pool.acquire() as conn:
#             deleted = await conn.fetchval("""
#                 DELETE FROM embeddings_cache 
#                 WHERE last_used < NOW() - INTERVAL '%s days' 
#                   AND use_count < 3
#                 RETURNING COUNT(*)
#             """, days)
            
#             logger.info(f"Cleaned up {deleted} old embeddings")

# # === Enhanced QA Processor with PostgreSQL ===
# class PostgreSQLOptimizedQAProcessor:
    
#     def __init__(self):
#         self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
    
#     async def process_questions_batch(
#         self, 
#         doc_info: 'DocumentInfo', 
#         questions: List[str], 
#         file_hash: str,
#         filename: str = None
#     ) -> List[str]:
#         """Process multiple questions with PostgreSQL optimization"""
        
#         start_time = time.time()
#         cache_hit = False
        
#         # Check cache first
#         cached_result = await PostgreSQLQueryCache.get_cached_result(questions, file_hash)
#         if cached_result:
#             cache_hit = True
#             await self._log_analytics(doc_info.file_type, questions, time.time() - start_time, cache_hit)
#             return cached_result
        
#         # Store document if not exists
#         document_id = await PostgreSQLDocumentStore.store_document(doc_info, file_hash, filename)
        
#         # Store chunks and definitions
#         await self._ensure_document_processed(doc_info, document_id)
        
#         # Get optimized context using hybrid search
#         context_chunks = await PostgreSQLSmartSearch.hybrid_search(questions, file_hash, limit=15)
        
#         # Get question patterns for optimization
#         patterns = await PostgreSQLSmartSearch.get_question_patterns(questions)
        
#         # Generate answers
#         answers = await self._generate_answers_with_context(
#             questions, context_chunks, patterns
#         )
        
#         processing_time = time.time() - start_time
        
#         # Cache results
#         await PostgreSQLQueryCache.cache_result(
#             questions, file_hash, answers, processing_time
#         )
        
#         # Log analytics
#         await self._log_analytics(doc_info.file_type, questions, processing_time, cache_hit)
        
#         return answers
    
#     async def _ensure_document_processed(self, doc_info: 'DocumentInfo', document_id: str):
#         """Ensure document chunks and definitions are stored"""
#         async with db_manager.pool.acquire() as conn:
#             # Check if chunks already exist
#             chunk_count = await conn.fetchval(
#                 "SELECT COUNT(*) FROM document_chunks WHERE document_id = $1", document_id
#             )
            
#             if chunk_count == 0:
#                 # Process and store chunks
#                 chunks = SmartChunker.semantic_chunking(doc_info)
#                 await PostgreSQLDocumentStore.store_chunks_batch(chunks, document_id)
                
#                 # Store definitions
#                 definitions = doc_info.structured_data.get('definitions', {})
#                 if definitions:
#                     await PostgreSQLDocumentStore.store_definitions(document_id, definitions)
    
#     async def _generate_answers_with_context(
#         self, 
#         questions: List[str], 
#         context_chunks: List[Dict],
#         patterns: List[Dict],
#         retries: int = 3
#     ) -> List[str]:
#         """Generate answers with enhanced context and patterns"""
        
#         # Prepare context with source information
#         context_text = ""
#         for i, chunk in enumerate(context_chunks):
#             context_text += f"\n--- SECTION {i+1} ({chunk['chunk_type']}) ---\n"
#             context_text += chunk['chunk_text']
#             context_text += f"\n[Importance: {chunk['importance_score']:.2f}]"
        
#         # Build pattern-aware prompt
#         pattern_info = ""
#         if patterns:
#             pattern_types = [p['pattern_type'] for p in patterns]
#             pattern_info = f"\nDetected question types: {', '.join(pattern_types)}"
        
#         prompt = f"""
# You are an expert insurance policy analyst. Answer the following questions based STRICTLY on the provided policy document sections.

# {pattern_info}

# IMPORTANT GUIDELINES:
# 1. Answer ONLY based on the provided document sections
# 2. If information is not found, state "Information not available in the provided document"
# 3. For numerical values (periods, percentages, amounts), be precise and include units
# 4. For coverage questions, specify conditions and limitations
# 5. For definitions, provide complete explanations from the DEFINITION sections
# 6. Prioritize information from higher importance sections
# 7. Keep answers concise but comprehensive

# POLICY DOCUMENT SECTIONS:
# {context_text}

# QUESTIONS TO ANSWER:
# {chr(10).join([f"{i+1}. {q}" for i, q in enumerate(questions)])}

# Respond in JSON format with exactly {len(questions)} answers:
# {{"answers": ["Answer 1", "Answer 2", "Answer 3", ...]}}
# """
        
#         for attempt in range(retries):
#             try:
#                 model = genai.GenerativeModel("gemini-1.5-flash")
#                 response = model.generate_content(
#                     prompt,
#                     generation_config={
#                         "response_mime_type": "application/json",
#                         "temperature": 0.05,
#                         "max_output_tokens": 2000,
#                         "top_p": 0.1,
#                         "top_k": 1
#                     }
#                 )
                
#                 result = json.loads(response.text)
#                 answers = result.get("answers", [])
                
#                 # Validate and pad answers
#                 while len(answers) < len(questions):
#                     answers.append("Information not available in the provided document")
                
#                 return answers[:len(questions)]
                
#             except Exception as e:
#                 logger.error(f"Answer generation failed on attempt {attempt + 1}: {e}")
#                 if attempt == retries - 1:
#                     return ["Unable to process document content"] * len(questions)
#                 await asyncio.sleep(1)
    
#     async def _log_analytics(self, document_type: str, questions: List[str], 
#                            processing_time: float, cache_hit: bool):
#         """Log performance analytics"""
#         async with db_manager.pool.acquire() as conn:
#             # Analyze question types
#             question_types = []
#             for question in questions:
#                 q_lower = question.lower()
#                 if any(kw in q_lower for kw in ['what is', 'define', 'definition']):
#                     question_types.append('definition')
#                 elif any(kw in q_lower for kw in ['waiting period', 'wait']):
#                     question_types.append('waiting_period')
#                 elif any(kw in q_lower for kw in ['cover', 'coverage', 'benefit']):
#                     question_types.append('coverage')
#                 else:
#                     question_types.append('general')
            
#             await conn.execute("""
#                 INSERT INTO query_analytics (
#                     document_type, question_types, processing_time, cache_hit
#                 ) VALUES ($1, $2, $3, $4)
#             """, document_type, question_types, processing_time, cache_hit)

# # Keep your existing classes but enhance them
# @dataclass
# class DocumentChunk:
#     text: str
#     chunk_id: str
#     page_num: int
#     chunk_type: str
#     metadata: Dict
#     importance_score: float = 0.5
    
#     def to_dict(self):
#         return asdict(self)

# @dataclass 
# class DocumentInfo:
#     file_type: str
#     content: str
#     structured_data: Dict
#     metadata: Dict

# # Your existing classes (ContentExtractor, SmartChunker, etc.) remain the same
# # but now they integrate with PostgreSQL for enhanced performance

# # === Enhanced FastAPI App with PostgreSQL ===
# app = FastAPI(title="PostgreSQL-Enhanced Document QA System", version="3.0.0")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Initialize database on startup
# @app.on_event("startup")
# async def startup_event():
#     """Initialize database connections and cache cleanup"""
#     await db_manager.initialize()
#     logger.info("Database initialized successfully")
    
#     # Start background cleanup task
#     asyncio.create_task(periodic_cleanup())

# @app.on_event("shutdown")
# async def shutdown_event():
#     """Clean shutdown"""
#     await db_manager.close()
#     logger.info("Database connections closed")

# # Background cleanup task
# async def periodic_cleanup():
#     """Periodic cleanup of old cache entries"""
#     while True:
#         try:
#             await asyncio.sleep(3600)  # Run every hour
#             await PostgreSQLEmbeddingCache.cleanup_old_embeddings(days=7)
            
#             # Clean old query cache entries
#             async with db_manager.pool.acquire() as conn:
#                 deleted = await conn.fetchval("""
#                     DELETE FROM query_cache 
#                     WHERE created_at < NOW() - INTERVAL '7 days' 
#                       AND use_count < 2
#                     RETURNING COUNT(*)
#                 """)
#                 logger.info(f"Cleaned up {deleted} old query cache entries")
                
#         except Exception as e:
#             logger.error(f"Cleanup task failed: {e}")

# # Global QA processor
# qa_processor = PostgreSQLOptimizedQAProcessor()

# # Enhanced utility functions with caching
# async def embed_text_cached(text: str, embedding_type: str = 'document') -> List[float]:
#     """Get embedding with PostgreSQL caching"""
#     # Check cache first
#     cached_embedding = await PostgreSQLEmbeddingCache.get_embedding(text, embedding_type)
#     if cached_embedding:
#         return cached_embedding
    
#     # Generate new embedding
#     try:
#         embedding = genai.embed_content(
#             model="models/embedding-001",
#             content=text[:8000],  # Limit text length
#             task_type="retrieval_document" if embedding_type == 'document' else "retrieval_query"
#         )["embedding"]
        
#         # Cache the result
#         await PostgreSQLEmbeddingCache.cache_embedding(text, embedding, embedding_type)
        
#         return embedding
#     except Exception as e:
#         logger.error(f"Embedding failed: {e}")
#         return [0.0] * 768

# # Keep your existing ContentExtractor class but add this optimization
# class ContentExtractor:
    
#     @staticmethod
#     async def extract_pdf(file_path: str) -> DocumentInfo:
#         """Extract content from PDF with OCR fallback"""
#         try:
#             doc = fitz.open(file_path)
#             full_text = ""
#             structured_content = {
#                 'definitions': {},
#                 'clauses': {},
#                 'tables': [],
#                 'key_terms': set(),
#                 'sections': {}
#             }
            
#             for page_num, page in enumerate(doc, start=1):
#                 page_text = page.get_text("text").strip()
                
#                 if not page_text:  # OCR fallback for scanned PDFs
#                     try:
#                         pix = page.get_pixmap()
#                         img_data = pix.tobytes("png")
#                         page_text = pytesseract.image_to_string(img_data)
#                     except Exception as e:
#                         logger.warning(f"OCR failed for page {page_num}: {e}")
#                         continue
                
#                 if page_text:
#                     full_text += f"\n[Page {page_num}]\n{page_text}\n"
                    
#                     # Extract structured information
#                     ContentExtractor._extract_policy_structures(page_text, structured_content)
            
#             doc.close()
            
#             return DocumentInfo(
#                 file_type='pdf',
#                 content=full_text,
#                 structured_data=structured_content,
#                 metadata={'total_pages': page_num, 'extraction_method': 'PyMuPDF+OCR'}
#             )
            
#         except Exception as e:
#             logger.error(f"PDF extraction failed: {e}")
#             raise HTTPException(status_code=500, detail=f"PDF processing failed: {str(e)}")
    
#     @staticmethod
#     async def extract_docx(file_path: str) -> DocumentInfo:
#         """Extract content from DOCX file"""
#         try:
#             doc = Document(file_path)
#             full_text = ""
#             structured_content = {
#                 'paragraphs': [],
#                 'tables': [],
#                 'headers': [],
#                 'definitions': {},
#                 'key_terms': set()
#             }
            
#             # Extract paragraphs
#             for para in doc.paragraphs:
#                 if para.text.strip():
#                     full_text += para.text + "\n"
#                     structured_content['paragraphs'].append({
#                         'text': para.text,
#                         'style': para.style.name if para.style else 'Normal'
#                     })
            
#             # Extract tables
#             for table in doc.tables:
#                 table_data = []
#                 for row in table.rows:
#                     row_data = [cell.text.strip() for cell in row.cells]
#                     table_data.append(row_data)
#                     full_text += " | ".join(row_data) + "\n"
#                 structured_content['tables'].append(table_data)
            
#             # Method 2: mammoth (better for complex formatting)
#             try:
#                 with open(file_path, "rb") as docx_file:
#                     result = mammoth.extract_raw_text(docx_file)
#                     mammoth_text = result.value
#                     if len(mammoth_text) > len(full_text):
#                         full_text = mammoth_text
#             except Exception as e:
#                 logger.warning(f"Mammoth extraction failed: {e}")
            
#             ContentExtractor._extract_policy_structures(full_text, structured_content)
            
#             return DocumentInfo(
#                 file_type='docx',
#                 content=full_text,
#                 structured_data=structured_content,
#                 metadata={'extraction_method': 'python-docx+mammoth'}
#             )
            
#         except Exception as e:
#             logger.error(f"DOCX extraction failed: {e}")
#             raise HTTPException(status_code=500, detail=f"DOCX processing failed: {str(e)}")
    
#     @staticmethod
#     async def extract_email(file_path: str) -> DocumentInfo:
#         """Extract content from email file"""
#         try:
#             with open(file_path, 'rb') as f:
#                 msg = email.message_from_bytes(f.read())
            
#             structured_content = {
#                 'headers': {},
#                 'body': '',
#                 'attachments': [],
#                 'definitions': {},
#                 'key_terms': set()
#             }
            
#             # Extract headers
#             headers = ['From', 'To', 'Subject', 'Date', 'Cc', 'Bcc']
#             for header in headers:
#                 if msg.get(header):
#                     structured_content['headers'][header] = msg.get(header)
            
#             # Extract body
#             body_text = ""
#             if msg.is_multipart():
#                 for part in msg.walk():
#                     if part.get_content_type() == "text/plain":
#                         body_text += part.get_payload(decode=True).decode('utf-8', errors='ignore')
#                     elif part.get_content_type() == "text/html":
#                         html_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
#                         body_text += re.sub('<[^<]+?>', '', html_content)
#             else:
#                 body_text = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            
#             structured_content['body'] = body_text
            
#             # Combine all content
#             full_text = f"""
#             From: {structured_content['headers'].get('From', '')}
#             To: {structured_content['headers'].get('To', '')}
#             Subject: {structured_content['headers'].get('Subject', '')}
#             Date: {structured_content['headers'].get('Date', '')}
            
#             {body_text}
#             """
            
#             ContentExtractor._extract_policy_structures(full_text, structured_content)
            
#             return DocumentInfo(
#                 file_type='email',
#                 content=full_text,
#                 structured_data=structured_content,
#                 metadata={'has_attachments': len(structured_content['attachments']) > 0}
#             )
            
#         except Exception as e:
#             logger.error(f"Email extraction failed: {e}")
#             raise HTTPException(status_code=500, detail=f"Email processing failed: {str(e)}")
    
#     @staticmethod
#     def _extract_policy_structures(text: str, structured_content: Dict):
#         """Extract insurance policy specific structures"""
#         patterns = {
#             'definitions': r'([A-Z][a-z\s]+(?:[A-Z][a-z\s]*)*)\s*(?:means?|is defined as|shall mean)\s+([^.!?]+[.!?])',
#             'waiting_periods': r'waiting period[s]?\s+(?:of\s+)?(\d+)\s+(days?|months?|years?)',
#             'coverage_amounts': r'(?:coverage|sum insured|limit).*?(?:rs\.?\s*|inr\s*|₹\s*)?(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:lakhs?|crores?)?',
#             'percentages': r'(\d+(?:\.\d+)?)\s*%',
#             'clauses': r'(\d+(?:\.\d+)*)\s+([^\n]+)',
#             'benefits': r'(benefit|discount|bonus|reimbursement).*?(\d+(?:\.\d+)?(?:\s*%|\s*rs\.?\s*\d+))',
#         }
        
#         for pattern_type, pattern in patterns.items():
#             matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
#             if pattern_type == 'definitions':
#                 for term, definition in matches:
#                     structured_content.setdefault('definitions', {})[term.strip()] = definition.strip()
#                     structured_content.setdefault('key_terms', set()).add(term.strip().lower())
#             elif pattern_type == 'clauses':
#                 for clause_num, clause_text in matches:
#                     structured_content.setdefault('clauses', {})[clause_num] = clause_text.strip()
#             else:
#                 structured_content.setdefault(pattern_type, []).extend(matches)

# # Keep your SmartChunker class as is
# class SmartChunker:
#     @staticmethod
#     def adaptive_chunk_size(text: str, doc_type: str) -> int:
#         """Determine optimal chunk size based on document characteristics"""
#         text_length = len(text.split())
        
#         if doc_type == 'email':
#             return min(300, text_length // 3)
#         elif doc_type == 'pdf' and text_length > 10000:
#             return 500
#         elif doc_type == 'docx':
#             return 400
#         else:
#             return 350
    
#     @staticmethod
#     def semantic_chunking(doc_info: DocumentInfo, chunk_size: int = None, overlap: int = 100) -> List[DocumentChunk]:
#         """Advanced semantic chunking with importance scoring"""
#         if not chunk_size:
#             chunk_size = SmartChunker.adaptive_chunk_size(doc_info.content, doc_info.file_type)
        
#         chunks = []
        
#         # Priority chunks from structured data
#         for term, definition in doc_info.structured_data.get('definitions', {}).items():
#             chunks.append(DocumentChunk(
#                 text=f"DEFINITION: {term} means {definition}",
#                 chunk_id=f"def_{len(chunks)}",
#                 page_num=0,
#                 chunk_type='definition',
#                 metadata={'term': term, 'source': 'structured'},
#                 importance_score=0.9
#             ))
        
#         # Clause-based chunks
#         for clause_num, clause_text in doc_info.structured_data.get('clauses', {}).items():
#             if len(clause_text.split()) >= 10:
#                 chunks.append(DocumentChunk(
#                     text=f"CLAUSE {clause_num}: {clause_text}",
#                     chunk_id=f"clause_{clause_num}",
#                     page_num=0,
#                     chunk_type='clause',
#                     metadata={'clause_number': clause_num, 'source': 'structured'},
#                     importance_score=0.8
#                 ))
        
#         # Content-based chunking
#         words = doc_info.content.split()
#         for i in range(0, len(words), chunk_size - overlap):
#             chunk_text = " ".join(words[i:i + chunk_size])
            
#             if len(chunk_text.split()) < 30:
#                 continue
            
#             importance_score = SmartChunker._calculate_importance(
#                 chunk_text, doc_info.structured_data
#             )
            
#             chunk_type = SmartChunker._classify_chunk(chunk_text)
            
#             chunks.append(DocumentChunk(
#                 text=chunk_text.strip(),
#                 chunk_id=f"chunk_{len(chunks)}",
#                 page_num=i // (chunk_size * 2) + 1,
#                 chunk_type=chunk_type,
#                 metadata={
#                     'word_count': len(chunk_text.split()),
#                     'start_index': i,
#                     'source': 'content'
#                 },
#                 importance_score=importance_score
#             ))
        
#         chunks.sort(key=lambda x: x.importance_score, reverse=True)
#         return chunks
    
#     @staticmethod
#     def _calculate_importance(text: str, structured_data: Dict) -> float:
#         """Calculate importance score for a text chunk"""
#         score = 0.5
        
#         key_terms = structured_data.get('key_terms', set())
#         text_lower = text.lower()
        
#         for term in key_terms:
#             if term in text_lower:
#                 score += 0.1
        
#         important_keywords = [
#             'waiting period', 'coverage', 'premium', 'deductible', 'benefit',
#             'exclusion', 'limit', 'policy', 'claim', 'insured', 'maternity',
#             'pre-existing', 'hospital', 'treatment', 'surgery'
#         ]
        
#         for keyword in important_keywords:
#             if keyword in text_lower:
#                 score += 0.05
        
#         if re.search(r'\d+\s*(?:days?|months?|years?|%|rs\.?|inr)', text_lower):
#             score += 0.15
        
#         if any(pattern in text_lower for pattern in ['means', 'defined as', 'shall mean']):
#             score += 0.2
        
#         return min(score, 1.0)
    
#     @staticmethod
#     def _classify_chunk(text: str) -> str:
#         """Classify chunk type based on content"""
#         text_lower = text.lower()
        
#         if any(pattern in text_lower for pattern in ['means', 'defined as', 'definition']):
#             return 'definition'
#         elif re.search(r'\d+(?:\.\d+)*\s', text):
#             return 'clause'
#         elif any(keyword in text_lower for keyword in ['waiting period', 'coverage', 'benefit']):
#             return 'policy_term'
#         elif any(keyword in text_lower for keyword in ['exclusion', 'not covered', 'except']):
#             return 'exclusion'
#         else:
#             return 'general'

# # File processing functions
# def detect_file_type(content: bytes, filename: str = None) -> str:
#     """Detect file type from content and filename"""
#     if content.startswith(b'%PDF'):
#         return 'pdf'
#     elif content.startswith(b'PK\x03\x04') and filename and filename.endswith('.docx'):
#         return 'docx'
#     elif b'Content-Type: ' in content[:1000] or b'From: ' in content[:1000]:
#         return 'email'
#     elif filename:
#         ext = Path(filename).suffix.lower()
#         if ext == '.pdf':
#             return 'pdf'
#         elif ext == '.docx':
#             return 'docx'
#         elif ext in ['.eml', '.msg']:
#             return 'email'
    
#     try:
#         text_content = content.decode('utf-8')
#         if 'From:' in text_content[:1000] and 'Subject:' in text_content[:1000]:
#             return 'email'
#     except:
#         pass
    
#     return 'unknown'

# async def download_file(url: str) -> Tuple[str, bytes]:
#     """Download file from URL and return path and content"""
#     try:
#         async with aiohttp.ClientSession() as session:
#             async with session.get(url) as response:
#                 if response.status != 200:
#                     raise HTTPException(status_code=400, detail=f"Failed to download file: {response.status}")
                
#                 content = await response.read()
                
#                 content_type = response.headers.get('content-type', '')
#                 if 'pdf' in content_type:
#                     ext = '.pdf'
#                 elif 'officedocument' in content_type:
#                     ext = '.docx'
#                 else:
#                     ext = '.pdf'
                
#                 tmp_path = os.path.join(tempfile.gettempdir(), f"document_{uuid.uuid4()}{ext}")
                
#                 async with aiofiles.open(tmp_path, 'wb') as f:
#                     await f.write(content)
                
#                 return tmp_path, content
#     except Exception as e:
#         logger.error(f"File download failed: {e}")
#         raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

# async def process_document(file_path: str, content: bytes = None) -> DocumentInfo:
#     """Process document based on its type"""
#     if not content:
#         async with aiofiles.open(file_path, 'rb') as f:
#             content = await f.read()
    
#     file_type = detect_file_type(content, file_path)
    
#     if file_type == 'pdf':
#         return await ContentExtractor.extract_pdf(file_path)
#     elif file_type == 'docx':
#         return await ContentExtractor.extract_docx(file_path)
#     elif file_type == 'email':
#         return await ContentExtractor.extract_email(file_path)
#     else:
#         raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")

# # === MAIN API ENDPOINTS ===

# @app.post("/hackrx/run")
# async def hackrx_run(
#     file: UploadFile = File(None), 
#     documents: str = Form(None),
#     questions: str = Form(...)
# ):
#     """
#     PostgreSQL-Enhanced endpoint with superior caching and search capabilities
#     """
#     start_time = time.time()
    
#     try:
#         # Parse questions
#         try:
#             if isinstance(questions, str):
#                 questions_list = json.loads(questions)
#             else:
#                 questions_list = questions
                
#             if not isinstance(questions_list, list):
#                 raise ValueError("Questions must be a list")
                
#         except (json.JSONDecodeError, ValueError) as e:
#             raise HTTPException(status_code=400, detail=f"Invalid questions format: {str(e)}")

#         # Validate input
#         if not file and not documents:
#             raise HTTPException(status_code=400, detail="Provide either a file upload or document URL")

#         # Process file
#         filename = None
#         if documents:  # URL provided
#             file_path, content = await download_file(documents)
#             filename = Path(documents).name
#         else:  # File upload
#             content = await file.read()
#             filename = file.filename
#             file_extension = Path(filename).suffix if filename else '.pdf'
#             file_path = os.path.join(tempfile.gettempdir(), f"upload_{uuid.uuid4()}{file_extension}")
            
#             async with aiofiles.open(file_path, 'wb') as f:
#                 await f.write(content)

#         # Extract document content
#         doc_info = await process_document(file_path, content)
        
#         if not doc_info.content.strip():
#             raise HTTPException(status_code=400, detail="No extractable content found in document")

#         # Generate file hash for caching/indexing
#         file_hash = hashlib.md5(doc_info.content.encode()).hexdigest()
        
#         # Process questions with PostgreSQL optimization
#         answers = await qa_processor.process_questions_batch(
#             doc_info, questions_list, file_hash, filename
#         )
        
#         # Cleanup temporary file
#         try:
#             if os.path.exists(file_path):
#                 os.unlink(file_path)
#         except Exception as e:
#             logger.warning(f"Cleanup failed: {e}")
        
#         processing_time = time.time() - start_time
        
#         return {
#             "file_id": file_hash,
#             "file_type": doc_info.file_type,
#             "answers": answers,
#             "processing_time": f"{processing_time:.2f}s",
#             "metadata": {
#                 "document_type": doc_info.file_type,
#                 "content_length": len(doc_info.content),
#                 "structured_elements": len(doc_info.structured_data.get('definitions', {})),
#                 "total_questions": len(questions_list),
#                 "filename": filename
#             }
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Unexpected error: {e}")
#         raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

# @app.get("/health")
# async def health_check():
#     """Enhanced health check with PostgreSQL status"""
#     try:
#         # Test PostgreSQL connection
#         async with db_manager.pool.acquire() as conn:
#             db_version = await conn.fetchval("SELECT version()")
        
#         # Test Gemini API
#         test_embedding = await embed_text_cached("test")
        
#         return {
#             "status": "healthy",
#             "timestamp": time.time(),
#             "services": {
#                 "postgresql": "connected",
#                 "gemini": "connected" if len(test_embedding) == 768 else "error",
#                 "database_version": db_version.split()[1] if db_version else "unknown"
#             },
#             "version": "3.0.0"
#         }
#     except Exception as e:
#         return {
#             "status": "unhealthy",
#             "error": str(e),
#             "timestamp": time.time()
#         }

# @app.get("/analytics")
# async def get_analytics(days: int = 7):
#     """Get query analytics and performance metrics"""
#     try:
#         async with db_manager.pool.acquire() as conn:
#             # Query performance metrics
#             perf_stats = await conn.fetchrow("""
#                 SELECT 
#                     COUNT(*) as total_queries,
#                     AVG(processing_time) as avg_processing_time,
#                     COUNT(*) FILTER (WHERE cache_hit = true) as cache_hits,
#                     COUNT(DISTINCT document_type) as document_types_processed
#                 FROM query_analytics 
#                 WHERE timestamp > NOW() - INTERVAL '%s days'
#             """, days)
            
#             # Question type distribution
#             question_types = await conn.fetch("""
#                 SELECT 
#                     unnest(question_types) as question_type,
#                     COUNT(*) as frequency
#                 FROM query_analytics 
#                 WHERE timestamp > NOW() - INTERVAL '%s days'
#                 GROUP BY question_type
#                 ORDER BY frequency DESC
#             """, days)
            
#             # Document type performance
#             doc_performance = await conn.fetch("""
#                 SELECT 
#                     document_type,
#                     COUNT(*) as query_count,
#                     AVG(processing_time) as avg_time,
#                     AVG(CASE WHEN cache_hit THEN 1.0 ELSE 0.0 END) as cache_hit_rate
#                 FROM query_analytics 
#                 WHERE timestamp > NOW() - INTERVAL '%s days'
#                   AND document_type IS NOT NULL
#                 GROUP BY document_type
#                 ORDER BY query_count DESC
#             """, days)
            
#             return {
#                 "period_days": days,
#                 "performance": dict(perf_stats) if perf_stats else {},
#                 "question_types": [dict(row) for row in question_types],
#                 "document_performance": [dict(row) for row in doc_performance],
#                 "cache_hit_rate": perf_stats['cache_hits'] / max(perf_stats['total_queries'], 1) if perf_stats else 0
#             }
            
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Analytics unavailable: {str(e)}")

# @app.post("/optimize-cache")
# async def optimize_cache():
#     """Optimize cache by removing unused entries and updating patterns"""
#     try:
#         async with db_manager.pool.acquire() as conn:
#             # Clean old embeddings
#             deleted_embeddings = await conn.fetchval("""
#                 DELETE FROM embeddings_cache 
#                 WHERE last_used < NOW() - INTERVAL '30 days' 
#                   AND use_count < 2
#                 RETURNING COUNT(*)
#             """)
            
#             # Clean old query cache
#             deleted_queries = await conn.fetchval("""
#                 DELETE FROM query_cache 
#                 WHERE created_at < NOW() - INTERVAL '14 days' 
#                   AND use_count < 3
#                 RETURNING COUNT(*)
#             """)
            
#             # Update question patterns based on usage
#             await conn.execute("""
#                 UPDATE question_patterns 
#                 SET priority_score = LEAST(1.0, priority_score + 0.1)
#                 WHERE pattern_type IN (
#                     SELECT unnest(question_types) 
#                     FROM query_analytics 
#                     WHERE timestamp > NOW() - INTERVAL '7 days'
#                     GROUP BY unnest(question_types)
#                     HAVING COUNT(*) > 10
#                 )
#             """)
            
#             return {
#                 "message": "Cache optimization completed",
#                 "deleted_embeddings": deleted_embeddings or 0,
#                 "deleted_queries": deleted_queries or 0,
#                 "timestamp": time.time()
#             }
            
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Cache optimization failed: {str(e)}")

# @app.get("/stats")
# async def get_stats():
#     """Get comprehensive system statistics"""
#     try:
#         async with db_manager.pool.acquire() as conn:
#             # Database stats
#             db_stats = await conn.fetchrow("""
#                 SELECT 
#                     (SELECT COUNT(*) FROM documents) as total_documents,
#                     (SELECT COUNT(*) FROM document_chunks) as total_chunks,
#                     (SELECT COUNT(*) FROM embeddings_cache) as cached_embeddings,
#                     (SELECT COUNT(*) FROM query_cache) as cached_queries,
#                     (SELECT COUNT(*) FROM document_definitions) as total_definitions
#             """)
            
#             # Storage usage
#             storage_stats = await conn.fetchrow("""
#                 SELECT 
#                     pg_size_pretty(pg_database_size(current_database())) as database_size,
#                     pg_size_pretty(pg_total_relation_size('documents')) as documents_size,
#                     pg_size_pretty(pg_total_relation_size('document_chunks')) as chunks_size,
#                     pg_size_pretty(pg_total_relation_size('embeddings_cache')) as embeddings_size,
#                     pg_size_pretty(pg_total_relation_size('query_cache')) as cache_size
#             """)
            
#             return {
#                 "database": dict(db_stats) if db_stats else {},
#                 "storage": dict(storage_stats) if storage_stats else {},
#                 "supported_formats": ["pdf", "docx", "email"],
#                 "features": [
#                     "PostgreSQL Full-Text Search",
#                     "Intelligent Caching",
#                     "Question Pattern Matching",
#                     "Performance Analytics",
#                     "Hybrid Search (FTS + Vector)",
#                     "Automatic Cache Optimization"
#                 ],
#                 "version": "3.0.0"
#             }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Stats unavailable: {str(e)}")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(
#         app, 
#         host="0.0.0.0", 
#         port=8000,
#         workers=1,
#         log_level="info"
#     )