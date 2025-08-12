"""
Final Upload & Indexing Script (chatbot_doc_5.py)

- Extracts text from PDF
- Splits into clause-aware chunks
- Embeds with Gemini embeddings
- Uploads to Pinecone
"""

import os
import fitz  # PyMuPDF
import uuid
import re
from dotenv import load_dotenv
import google.generativeai as genai
from pinecone import Pinecone, ServerlessSpec
import sys

# === Load Environment Variables ===
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

if not GEMINI_API_KEY or not PINECONE_API_KEY or not INDEX_NAME:
    print("[ERROR] Missing required environment variables.")
    exit(1)

# Normalize index name
INDEX_NAME = INDEX_NAME.lower().replace("_", "-")

# === Configure Gemini ===
genai.configure(api_key=GEMINI_API_KEY)

# === Initialize Pinecone Client ===
pc = Pinecone(api_key=PINECONE_API_KEY)

if INDEX_NAME not in pc.list_indexes().names():
    print(f"[WARN] Index '{INDEX_NAME}' not found. Creating it...")
    pc.create_index(
        name=INDEX_NAME,
        dimension=768,
        metric="cosine",
        spec=ServerlessSpec(
            cloud=PINECONE_CLOUD.strip(),
            region=PINECONE_REGION.strip()
        )
    )

index = pc.Index(INDEX_NAME)

# === Step 1: Extract text from PDF ===
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page_num, page in enumerate(doc, start=1):
        page_text = page.get_text("text").strip()
        if page_text:
            text += f"\n[Page {page_num}]\n" + page_text + "\n"
    return text

# === Step 2: Clause-Aware Chunking with Grouping ===
def chunk_document(text, min_clause_len=80, max_group_size=3):
    clauses = re.split(r"(?=\n?\s*(\d+(?:\.\d+)*[a-zA-Z]?)\s+)", text)

    chunks = []
    buffer = []
    group_count = 0
    current_clause_id = None

    for clause in clauses:
        if not clause or not clause.strip():
            continue
        clause = clause.strip()

        match = re.match(r"^(\d+(?:\.\d+)*[a-zA-Z]?)\s+", clause)
        if match:
            if buffer:
                chunks.append((current_clause_id or f"clause_{len(chunks)+1}", " ".join(buffer)))
                buffer = []
                group_count = 0
            current_clause_id = match.group(1)

        buffer.append(clause)
        group_count += 1

        if len(" ".join(buffer).split()) > min_clause_len or group_count >= max_group_size:
            chunks.append((current_clause_id or f"clause_{len(chunks)+1}", " ".join(buffer)))
            buffer = []
            group_count = 0

    if buffer:
        chunks.append((current_clause_id or f"clause_{len(chunks)+1}", " ".join(buffer)))

    print(f"[INFO] Document split into {len(chunks)} grouped clause-chunks.")
    return chunks

# === Step 3: Embed and Upload in Batches ===
def upload_chunks_to_pinecone(chunks, index, batch_size=50):
    print(f"[INFO] Uploading {len(chunks)} chunks to Pinecone...")
    batch = []

    for i, (clause_id, chunk) in enumerate(chunks):
        try:
            embedding = genai.embed_content(
                model="models/embedding-001",
                content=chunk,
                task_type="retrieval_document"
            )["embedding"]

            batch.append((
                str(uuid.uuid4()),
                embedding,
                {
                    "text": chunk,
                    "clause_id": str(clause_id) if clause_id else f"clause_{i+1}"
                }
            ))

            if len(batch) >= batch_size:
                index.upsert(batch)
                batch = []

        except Exception as e:
            print(f"[ERROR] Error embedding clause {clause_id}: {e}")
            continue

    if batch:
        index.upsert(batch)

    print("[INFO] Upload completed.")

# === Main Program ===
if __name__ == "__main__":
    print(f"[INFO] Connected to Pinecone index: {INDEX_NAME}")

    if len(sys.argv) < 2:
        print("[ERROR] No PDF path provided.")
        exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"[ERROR] File not found: {pdf_path}")
        exit(1)

    print(f"[INFO] Processing document: {pdf_path}")

    pdf_text = extract_text_from_pdf(pdf_path)
    clause_chunks = chunk_document(pdf_text)
    upload_chunks_to_pinecone(clause_chunks, index)

    print(f"[INFO] Document '{pdf_path}' successfully indexed into Pinecone with safe clause IDs.")
