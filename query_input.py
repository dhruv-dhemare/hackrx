
# """
# Best one so far and i am happy with this and the accuracy is about 85%
# this is the query function

# """

# import os
# import json
# from dotenv import load_dotenv
# import google.generativeai as genai
# from pinecone import Pinecone

# # === Load Environment Variables ===
# load_dotenv()
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
# INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# if not GOOGLE_API_KEY or not PINECONE_API_KEY or not INDEX_NAME:
#     print("❌ Missing env vars. Check your .env file.")
#     exit()

# # === Configure GOOGLE & Pinecone ===
# genai.configure(api_key=GOOGLE_API_KEY)
# pc = Pinecone(api_key=PINECONE_API_KEY)

# if INDEX_NAME not in pc.list_indexes().names():
#     print(f"❌ Index {INDEX_NAME} not found.")
#     exit()

# index = pc.Index(INDEX_NAME)

# # === Helper Functions ===
# def embed_text_for_query(text):
#     response = genai.embed_content(
#         model="models/embedding-001",
#         content="Find insurance coverage details: " + text,  # 👈 Add directive
#         task_type="retrieval_query"
#     )
#     return response["embedding"]

# def retrieve_similar_chunks(query, top_k=7):  # 👈 Increased top_k
#     query_embedding = embed_text_for_query(query)
#     results = index.query(
#         vector=query_embedding,
#         top_k=top_k,
#         include_metadata=True
#     )
#     return [match["metadata"]["text"] for match in results["matches"]]

# def ask_GOOGLE(query, context_chunks):
#     context = "\n---\n".join(context_chunks)
#     prompt = f"""
# You are a health insurance policy analysis assistant.
# Answer the query strictly using the policy clauses below.

# Query:
# {query}

# Policy Clauses:
# {context}

# Instructions:
# - ONLY use the given clauses, do not invent.
# - If any numeric value, percentage, or monetary amount is in the text, extract it exactly.
# - If multiple waiting periods are given, report all and highlight the general Pre-existing Disease waiting period separately.
# - If the clause mentions 'as per schedule', say 'Specified in Policy Schedule (not in text)' instead of 'Cannot determine'.
# - If truly missing, then use 'Cannot determine'.
# - Output strictly JSON:

# {{
#   "decision": "Yes / No / Cannot determine",
#   "amount": "Coverage limit, percentage, or Unknown",
#   "justification": "Explanation citing exact clauses provided",
#   "clause_ids": ["C1", "C2"],
#   "risk_level": "Red / Orange / Yellow / Black",
#   "answers": [
#     "Direct factual statements extracted from clauses"
#   ]
# }}
# """
#     model = genai.GenerativeModel("GOOGLE-1.5-flash")
#     try:
#         response = model.generate_content(prompt)
#         response_text = response.text.strip()
#         if response_text.startswith("```json"):
#             response_text = response_text[7:]
#         if response_text.endswith("```"):
#             response_text = response_text[:-3]
#         return json.loads(response_text)
#     except Exception as e:
#         print(f"❌ Error parsing response: {e}")
#         return None

# # === Main Program ===
# if __name__ == "__main__":
#     print(f"✅ Connected to Pinecone index: {INDEX_NAME}")
#     while True:
#         query = input("\n🔍 Ask something (or 'exit'): ")
#         if query.lower() == "exit":
#             break
#         print("🔎 Retrieving relevant chunks...")
#         retrieved = retrieve_similar_chunks(query)
#         if not retrieved:
#             print(json.dumps({
#                 "decision": "Cannot determine",
#                 "amount": "Unknown",
#                 "justification": "No relevant info found.",
#                 "clause_ids": [],
#                 "risk_level": "Yellow",
#                 "answers": []
#             }, indent=4))
#             continue
#         print("💬 Generating GOOGLE response...")
#         answer = ask_GOOGLE(query, retrieved)
#         print(json.dumps(answer if answer else {
#             "decision": "Cannot determine",
#             "amount": "Unknown",
#             "justification": "Parsing error.",
#             "clause_ids": [],
#             "risk_level": "Yellow",
#             "answers": []
#         }, indent=4))

import os
import fitz  # PyMuPDF
import uuid
import re
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from dotenv import load_dotenv
import google.generativeai as genai
from pinecone import Pinecone, ServerlessSpec

# === Load Env Variables ===
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# === Configure GOOGLE & Pinecone ===
genai.configure(api_key=GOOGLE_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

# Ensure Pinecone Index Exists
if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX_NAME,
        dimension=768,
        metric="cosine",
        spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION)
    )
index = pc.Index(INDEX_NAME)

app = FastAPI()

# === PDF Text Extraction ===
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page_num, page in enumerate(doc, start=1):
        page_text = page.get_text("text").strip()
        if page_text:
            text += f"\n[Page {page_num}]\n{page_text}\n"
    return text

# === Chunking ===
def semantic_chunk(text, chunk_size=300, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk.split()) >= 50:
            chunks.append(chunk.strip())
    return chunks

# === Embedding ===
def embed_chunk(chunk):
    return genai.embed_content(model="models/embedding-001", content=chunk, task_type="retrieval_document")["embedding"]

# === Upload Chunks to Pinecone ===
def upload_chunks_to_pinecone(chunks, file_id, batch_size=50):
    batch = []
    def process_chunk(chunk):
        chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
        embedding = embed_chunk(chunk)
        return (str(uuid.uuid4()), embedding, {"text": chunk, "hash": chunk_hash})

    with ThreadPoolExecutor(max_workers=5) as executor:
        embedded_chunks = list(executor.map(process_chunk, chunks))

    for vec in embedded_chunks:
        batch.append(vec)
        if len(batch) >= batch_size:
            index.upsert(vectors=batch, namespace=file_id)
            batch = []
    if batch:
        index.upsert(vectors=batch, namespace=file_id)

# === Query Retrieval ===
def embed_text_for_query(text):
    return genai.embed_content(model="models/embedding-001", content=text, task_type="retrieval_query")["embedding"]

def retrieve_chunks(query, file_id, top_k=8):
    query_embedding = embed_text_for_query(query)
    results = index.query(vector=query_embedding, top_k=top_k, namespace=file_id, include_metadata=True)
    return [m["metadata"]["text"] for m in results["matches"]]

# === GOOGLE Answer Generation ===
def ask_GOOGLE(query, context_chunks):
    context = "\n---\n".join(context_chunks)
    prompt = f"""
You are a health insurance policy assistant. Answer based only on the clauses:

Query:
{query}

Clauses:
{context}

Output strictly JSON:
{{
  "decision": "Yes/No/Cannot determine",
  "amount": "Coverage limit or Unknown",
  "justification": "Explain with cited clauses",
  "answers": ["Direct factual extractions"]
}}
"""
    model = genai.GenerativeModel("GOOGLE-1.5-flash")
    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    return json.loads(response.text)

# === SINGLE ROUTE: UPLOAD PDF + ANSWER QUERIES ===
@app.post("/hackrx/run")
async def hackrx_run(file: UploadFile = File(...), questions: str = Form(...)):
    try:
        # Convert questions string into list
        questions_list = json.loads(questions)

        # Save PDF temporarily
        pdf_path = f"/tmp/{file.filename}"
        with open(pdf_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Extract & Embed PDF
        pdf_text = extract_text_from_pdf(pdf_path)
        if not pdf_text.strip():
            raise HTTPException(status_code=400, detail="Empty or scanned PDF (no text extracted).")

        file_id = os.path.splitext(file.filename)[0] + "_" + str(uuid.uuid4())[:6]
        chunks = semantic_chunk(pdf_text)
        upload_chunks_to_pinecone(chunks, file_id)

        # Process Queries
        answers = []
        for q in questions_list:
            retrieved = retrieve_chunks(q, file_id)
            if not retrieved:
                answers.append("Cannot determine")
            else:
                GOOGLE_output = ask_GOOGLE(q, retrieved)
                answers.append(GOOGLE_output["answers"][0] if "answers" in GOOGLE_output else "Cannot determine")

        return {"file_id": file_id, "answers": answers}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook error: {str(e)}")
