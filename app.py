import os
import uuid
import fitz
import re
import json
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
import google.generativeai as genai
from pinecone import Pinecone
from pydantic import BaseModel
from typing import List

# === Load environment variables ===
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# === Configure Gemini & Pinecone ===
genai.configure(api_key=GEMINI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

app = FastAPI()

# === PDF Text Extraction ===
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page_num, page in enumerate(doc, start=1):
        page_text = page.get_text("text").strip()
        if page_text:
            text += f"\n[Page {page_num}]\n" + page_text + "\n"
    return text

# === Chunking ===
def chunk_document(text, min_clause_len=80, max_group_size=3):
    clauses = re.split(r"(?=\n?\s*(\d+(?:\.\d+)*[a-zA-Z]?)\s+)", text)
    chunks, buffer, group_count, current_clause_id = [], [], 0, None

    for clause in clauses:
        if not clause or not clause.strip():
            continue
        clause = clause.strip()
        match = re.match(r"^(\d+(?:\.\d+)*[a-zA-Z]?)\s+", clause)
        if match:
            if buffer:
                chunks.append((current_clause_id or f"clause_{len(chunks)+1}", " ".join(buffer)))
                buffer, group_count = [], 0
            current_clause_id = match.group(1)
        buffer.append(clause)
        group_count += 1
        if len(" ".join(buffer).split()) > min_clause_len or group_count >= max_group_size:
            chunks.append((current_clause_id or f"clause_{len(chunks)+1}", " ".join(buffer)))
            buffer, group_count = [], 0
    if buffer:
        chunks.append((current_clause_id or f"clause_{len(chunks)+1}", " ".join(buffer)))
    return chunks

# === Upload Chunks to Pinecone ===
def upload_chunks_to_pinecone(chunks):
    for clause_id, chunk in chunks:
        embedding = genai.embed_content(model="models/embedding-001", content=chunk, task_type="retrieval_document")["embedding"]
        index.upsert([(str(uuid.uuid4()), embedding, {"text": chunk, "clause_id": clause_id})])

# === Query Embedding & Retrieval ===
def embed_text_for_query(query):
    return genai.embed_content(model="models/embedding-001", content=query, task_type="retrieval_query")["embedding"]

def retrieve_chunks(query):
    query_emb = embed_text_for_query(query)
    results = index.query(vector=query_emb, top_k=8, include_metadata=True)
    return [match["metadata"]["text"] for match in results["matches"]]

# === Gemini Answer Generation ===
def ask_gemini(query, context_chunks):
    context = "\n---\n".join(context_chunks)
    prompt = f"""
You are a health insurance policy analysis assistant.
Answer using ONLY the clauses below.

Query:
{query}

Policy Clauses:
{context}

Output strictly in JSON:
{{
  "decision": "Yes / No / Cannot determine",
  "amount": "Coverage limit or Unknown",
  "justification": "Cite exact clauses",
  "clause_ids": ["C1", "C2"],
  "risk_level": "Red / Orange / Yellow / Black",
  "answers": ["Extracted statements"]
}}
"""
    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content(prompt).text.strip()
    if response.startswith("```json"):
        response = response[7:-3]
    return json.loads(response)

# === FastAPI Endpoints ===
@app.post("/upload")
async def upload_policy(file: UploadFile):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    text = extract_text_from_pdf(temp_path)
    chunks = chunk_document(text)
    upload_chunks_to_pinecone(chunks)
    return {"message": f"Policy '{file.filename}' indexed successfully!"}

class QueryRequest(BaseModel):
    queries: List[str]

@app.post("/query")
async def query_policy(req: QueryRequest):
    answers = []
    for q in req.queries:
        retrieved = retrieve_chunks(q)
        if not retrieved:
            answers.append({"decision": "Cannot determine", "amount": "Unknown", "justification": "No relevant info", "clause_ids": [], "risk_level": "Yellow", "answers": []})
        else:
            answers.append(ask_gemini(q, retrieved))
    return JSONResponse(content={"results": answers})
