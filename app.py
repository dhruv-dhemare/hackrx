
# import os
# import json
# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from dotenv import load_dotenv
# import google.generativeai as genai
# from pinecone import Pinecone
# import uuid

# # Import from your upload script
# from upload_script import extract_text_from_pdf, semantic_chunk, upload_chunks_to_pinecone

# # === Load Environment Variables ===
# load_dotenv()
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
# INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# # === Configure Gemini & Pinecone ===
# genai.configure(api_key=GOOGLE_API_KEY)
# pc = Pinecone(api_key=PINECONE_API_KEY)
# index = pc.Index(INDEX_NAME)

# # === FastAPI App Initialization ===
# app = FastAPI(
#     title="HackRx LLM Backend",
#     description="Upload policy PDFs and query them using LLM",
#     version="1.0"
# )

# # Enable CORS (Optional if frontend integration is required)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # === Request Models ===
# class QueryRequest(BaseModel):
#     file_id: str
#     query: str

# # === Health Check Endpoint ===
# @app.get("/health")
# def health_check():
#     return {"status": "ok", "pinecone_index": INDEX_NAME}

# # === Upload PDF Endpoint ===
# @app.post("/upload")
# async def upload_policy(file: UploadFile = File(...)):
#     try:
#         # Save file temporarily
#         file_path = f"temp_{file.filename}"
#         with open(file_path, "wb") as buffer:
#             buffer.write(await file.read())

#         # Extract & chunk text
#         pdf_text = extract_text_from_pdf(file_path)
#         chunks = semantic_chunk(pdf_text)

#         # Generate unique file_id (namespace in Pinecone)
#         file_id = os.path.splitext(file.filename)[0].replace(" ", "_").lower() + "_" + str(uuid.uuid4())[:6]

#         # Upload chunks to Pinecone under this namespace
#         upload_chunks_to_pinecone(chunks, file_id)

#         # Remove temp file
#         os.remove(file_path)

#         return {"message": "File uploaded and indexed successfully", "file_id": file_id}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # === Query Endpoint ===
# @app.post("/query")
# async def query_policy(request: QueryRequest):
#     try:
#         # Embed query
#         query_embedding = genai.embed_content(
#             model="models/embedding-001",
#             content=request.query,
#             task_type="retrieval_query"
#         )["embedding"]

#         # Search within namespace (file-specific chunks)
#         results = index.query(
#             vector=query_embedding,
#             namespace=request.file_id,
#             top_k=8,
#             include_metadata=True
#         )

#         if not results or "matches" not in results or len(results["matches"]) == 0:
#             return {"decision": "Cannot determine", "amount": "Unknown", "justification": "No relevant info found.", "clause_ids": [], "risk_level": "Yellow", "answers": []}

#         # Collect retrieved chunks
#         context_chunks = [match["metadata"]["text"] for match in results["matches"]]

#         # Prepare prompt for Gemini
#         prompt = f"""
#         You are an insurance policy assistant.
#         Answer the following query strictly using these clauses:
#         {'\n---\n'.join(context_chunks)}

#         Query:
#         {request.query}

#         Respond strictly in JSON:
#         {{
#             "decision": "Yes / No / Cannot determine",
#             "amount": "Coverage limit, percentage, or Unknown",
#             "justification": "Explain using exact clauses",
#             "clause_ids": ["..."],
#             "risk_level": "Red / Orange / Yellow / Black",
#             "answers": ["Direct factual answers"]
#         }}
#         """

#         model = genai.GenerativeModel("gemini-1.5-flash")
#         response = model.generate_content(prompt)
#         response_text = response.text.strip()

#         # Clean JSON if wrapped in code fences
#         if response_text.startswith("```json"):
#             response_text = response_text[7:]
#         if response_text.endswith("```"):
#             response_text = response_text[:-3]

#         return json.loads(response_text)

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

import os
import json
import uuid
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai
from pinecone import Pinecone
from upload_script import extract_text_from_pdf, semantic_chunk, upload_chunks_to_pinecone

# === Load Env Vars ===
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# === Initialize Clients ===
genai.configure(api_key=GOOGLE_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

# === FastAPI App ===
app = FastAPI(title="HackRx Policy LLM Backend")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# === Request Schema ===
class QueryRequest(BaseModel):
    file_id: str
    queries: List[str]  # ⬅️ Only an array of queries now

# === Health Check ===
@app.get("/health")
async def health_check():
    return {"status": "ok", "pinecone_index": INDEX_NAME}

# === Upload PDF (Single PDF Upload) ===
@app.post("/upload")
async def upload_policy(file: UploadFile = File(...)):
    try:
        # Save temp file
        file_path = f"./temp_{file.filename}"
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Extract text & chunk
        pdf_text = extract_text_from_pdf(file_path)
        chunks = semantic_chunk(pdf_text)

        # Generate unique file_id (namespace)
        file_id = os.path.splitext(file.filename)[0] + "_" + str(uuid.uuid4())[:6]

        # Upload chunks to Pinecone
        upload_chunks_to_pinecone(chunks, file_id)

        os.remove(file_path)  # Cleanup temp file

        return {"message": "File uploaded and indexed successfully", "file_id": file_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

# === Query PDF (Array of Queries) ===
@app.post("/query")
async def query_policy(request: QueryRequest):
    responses = []

    for query_text in request.queries:
        try:
            # Embed Query
            query_embedding = genai.embed_content(
                model="models/embedding-001",
                content=query_text,
                task_type="retrieval_query"
            )["embedding"]

            # Retrieve chunks from Pinecone (specific file namespace)
            pinecone_results = index.query(
                vector=query_embedding,
                namespace=request.file_id,
                top_k=8,
                include_metadata=True
            )

            if not pinecone_results.get("matches"):
                responses.append({
                    "decision": "Cannot determine",
                    "amount": "Unknown",
                    "justification": "No relevant info found.",
                    "clause_ids": [],
                    "risk_level": "Yellow",
                    "answers": []
                })
                continue

            context_chunks = [match["metadata"]["text"] for match in pinecone_results["matches"]]

            # Build Gemini Prompt
            prompt = f"""
            You are an insurance policy assistant.
            Use ONLY the clauses below to answer the query.

            Clauses:
            {'\n---\n'.join(context_chunks)}

            Query:
            {query_text}

            Respond strictly in JSON:
            {{
                "decision": "Yes / No / Cannot determine",
                "amount": "Coverage limit, percentage, or Unknown",
                "justification": "Explain using exact clauses",
                "clause_ids": ["..."],
                "risk_level": "Red / Orange / Yellow / Black",
                "answers": ["Direct factual answers"]
            }}
            """

            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            response_text = response.text.strip()

            # Clean fenced JSON
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            try:
                responses.append(json.loads(response_text))
            except:
                responses.append({
                    "decision": "Cannot determine",
                    "amount": "Unknown",
                    "justification": "Parsing error.",
                    "clause_ids": [],
                    "risk_level": "Yellow",
                    "answers": []
                })

        except Exception as e:
            responses.append({
                "decision": "Cannot determine",
                "amount": "Unknown",
                "justification": f"Error: {str(e)}",
                "clause_ids": [],
                "risk_level": "Yellow",
                "answers": []
            })

    return responses
