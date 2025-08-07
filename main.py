# #sid code 


# import os
# import re
# import uuid
# import json
# import time
# import fitz  # PyMuPDF
# import requests
# import logging
# from concurrent.futures import ThreadPoolExecutor, as_completed
# from dotenv import load_dotenv
# from fastapi import FastAPI
# from pydantic import BaseModel
# import google.generativeai as genai
# from pinecone import Pinecone, ServerlessSpec
# import asyncio
# from typing import List, Tuple, Dict, Any
# import threading
# import mmap
# import tempfile
# import gc

# # === Setup Logging ===
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(message)s",
#     handlers=[logging.StreamHandler()]
# )

# # === Load Environment ===
# load_dotenv()
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
# INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "hackrx-index").lower().replace("_", "-")
# PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
# PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# # === Configure Clients ===
# genai.configure(api_key=GOOGLE_API_KEY)
# pc = Pinecone(api_key=PINECONE_API_KEY)

# if INDEX_NAME not in pc.list_indexes().names():
#     logging.info(f"Index '{INDEX_NAME}' not found. Creating new one...")
#     pc.create_index(
#         name=INDEX_NAME,
#         dimension=768,
#         metric="cosine",
#         spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION)
#     )
# index = pc.Index(INDEX_NAME)

# app = FastAPI()

# # === Thread-safe clients ===
# thread_local = threading.local()

# def get_genai_client():
#     """Thread-safe GOOGLE client"""
#     if not hasattr(thread_local, 'genai_client'):
#         thread_local.genai_client = genai
#     return thread_local.genai_client

# # === Data Models ===
# class RunRequest(BaseModel):
#     documents: str
#     questions: list[str]

# # === Aggressively Optimized Helpers ===
# def download_pdf_optimized(url: str, save_path: str):
#     """Optimized PDF download with larger chunks and connection pooling"""
#     logging.info("📥 Stage 1: Downloading PDF (optimized)...")
    
#     # Use session for connection pooling
#     session = requests.Session()
#     session.headers.update({
#         'User-Agent': 'Mozilla/5.0 (compatible; HackRx/1.0)'
#     })
    
#     r = session.get(url, stream=True, timeout=30)
#     r.raise_for_status()
    
#     # Use larger chunks for faster download
#     with open(save_path, "wb") as f:
#         for chunk in r.iter_content(chunk_size=65536):  # 64KB chunks
#             f.write(chunk)
    
#     session.close()
#     logging.info("✅ PDF downloaded (optimized)")
#     return save_path

# def extract_text_from_pdf_parallel(pdf_path):
#     """Parallel text extraction using multiple threads"""
#     logging.info("📄 Stage 2: Extracting text from PDF (parallel)...")
    
#     doc = fitz.open(pdf_path)
#     total_pages = len(doc)
    
#     def extract_page_text(page_info):
#         page_num, page = page_info
#         try:
#             page_text = page.get_text("text").strip()
#             return page_num, page_text
#         except Exception as e:
#             logging.warning(f"Error extracting page {page_num}: {e}")
#             return page_num, ""
    
#     # Extract text in parallel
#     page_infos = [(i+1, doc[i]) for i in range(total_pages)]
    
#     with ThreadPoolExecutor(max_workers=min(8, total_pages)) as executor:
#         results = list(executor.map(extract_page_text, page_infos))
    
#     # Combine results in order
#     text_parts = []
#     for page_num, page_text in sorted(results):
#         if page_text:
#             text_parts.append(f"\n[Page {page_num}]\n{page_text}\n")
    
#     doc.close()
#     text = "".join(text_parts)
    
#     logging.info(f"✅ Extracted {len(text.split())} words from {pdf_path} (parallel)")
#     return text

# def chunk_document_optimized(text, min_clause_len=80, max_group_size=3, max_chunk_words=800):
#     """Optimized chunking with larger chunks for better context"""
#     logging.info("✂ Stage 3: Chunking document (optimized)...")
    
#     # Use regex compilation for better performance
#     clause_pattern = re.compile(r"(?=\n?\s*(\d+(?:\.\d+)*[a-zA-Z]?)\s+)")
#     clause_id_pattern = re.compile(r"^(\d+(?:\.\d+)*[a-zA-Z]?)\s+")
    
#     clauses = clause_pattern.split(text)
#     chunks, buffer, group_count, current_clause_id = [], [], 0, None

#     for clause in clauses:
#         if not clause.strip():
#             continue
            
#         match = clause_id_pattern.match(clause)
#         if match:
#             if buffer:
#                 content = " ".join(buffer)
#                 if len(content.split()) > max_chunk_words:
#                     # Split large chunks more efficiently
#                     words = content.split()
#                     for i in range(0, len(words), max_chunk_words):
#                         chunk_words = words[i:i+max_chunk_words]
#                         chunks.append((current_clause_id or f"clause_{len(chunks)+1}", " ".join(chunk_words)))
#                 else:
#                     chunks.append((current_clause_id or f"clause_{len(chunks)+1}", content))
#                 buffer, group_count = [], 0
#             current_clause_id = match.group(1)
            
#         buffer.append(clause.strip())
#         group_count += 1
        
#         if len(" ".join(buffer).split()) > min_clause_len or group_count >= max_group_size:
#             content = " ".join(buffer)
#             if len(content.split()) > max_chunk_words:
#                 words = content.split()
#                 for i in range(0, len(words), max_chunk_words):
#                     chunk_words = words[i:i+max_chunk_words]
#                     chunks.append((current_clause_id or f"clause_{len(chunks)+1}", " ".join(chunk_words)))
#             else:
#                 chunks.append((current_clause_id or f"clause_{len(chunks)+1}", content))
#             buffer, group_count = [], 0
    
#     if buffer:
#         content = " ".join(buffer)
#         if len(content.split()) > max_chunk_words:
#             words = content.split()
#             for i in range(0, len(words), max_chunk_words):
#                 chunk_words = words[i:i+max_chunk_words]
#                 chunks.append((current_clause_id or f"clause_{len(chunks)+1}", " ".join(chunk_words)))
#         else:
#             chunks.append((current_clause_id or f"clause_{len(chunks)+1}", content))

#     logging.info(f"✅ Created {len(chunks)} chunks (optimized)")
#     return chunks

# def embed_batch_parallel_optimized(batch_texts: List[str], batch_id: int) -> Tuple[List[List[float]], int]:
#     """Optimized batch embedding with better error handling and retries"""
#     max_retries = 3
#     for attempt in range(max_retries):
#         try:
#             client = get_genai_client()
#             resp = client.embed_content(
#                 model="models/embedding-001",
#                 content=batch_texts,
#                 task_type="retrieval_document"
#             )
            
#             if isinstance(resp, dict) and "embedding" in resp:
#                 batch_embeddings = resp["embedding"]
#             else:
#                 batch_embeddings = [e["embedding"] for e in resp]
                
#             logging.info(f"✅ Batch {batch_id}: Generated {len(batch_embeddings)} embeddings")
#             return batch_embeddings, batch_id
            
#         except Exception as e:
#             if attempt < max_retries - 1:
#                 logging.warning(f"❌ Batch {batch_id} attempt {attempt + 1} failed: {e}, retrying...")
#                 time.sleep(1)  # Brief delay before retry
#             else:
#                 logging.error(f"❌ Batch {batch_id} failed after {max_retries} attempts: {e}")
#                 return [], batch_id

# def upload_chunks_aggressive_parallel(doc_id: str, chunks: List[Tuple[str, str]], batch_size: int = 200):
#     """Aggressively parallel chunk upload optimized for 16GB RAM"""
#     logging.info("🧠 Stage 4: Checking if doc already exists in Pinecone...")
#     existing = index.query(
#         vector=[0.0]*768,
#         filter={"doc_id": {"$eq": doc_id}},
#         top_k=1
#     )
#     if existing["matches"]:
#         logging.info("⚡ Document already indexed. Skipping upload.")
#         return

#     logging.info("🧠 Uploading new chunks to Pinecone with aggressive parallel processing...")
#     texts = [chunk for _, chunk in chunks]
    
#     # Use larger batches for better throughput
#     batches = []
#     for i in range(0, len(texts), batch_size):
#         batch_texts = texts[i:i+batch_size]
#         batches.append((batch_texts, i // batch_size))
    
#     # Process embeddings with more workers for 16GB RAM
#     all_embeddings = []
#     max_workers = min(16, len(batches))  # Increased workers for 16GB RAM
    
#     with ThreadPoolExecutor(max_workers=max_workers) as executor:
#         future_to_batch = {
#             executor.submit(embed_batch_parallel_optimized, batch_texts, batch_id): batch_id 
#             for batch_texts, batch_id in batches
#         }
        
#         # Collect results in order
#         batch_results = {}
#         for future in as_completed(future_to_batch):
#             embeddings, batch_id = future.result()
#             batch_results[batch_id] = embeddings
        
#         # Reconstruct embeddings in correct order
#         for batch_id in sorted(batch_results.keys()):
#             all_embeddings.extend(batch_results[batch_id])

#     # Create vectors with memory optimization
#     vectors = [
#         (str(uuid.uuid4()), emb, {"text": chunk, "clause_id": cid, "doc_id": doc_id})
#         for (cid, chunk), emb in zip(chunks, all_embeddings)
#     ]

#     # Upload to Pinecone with larger batches and more workers
#     upload_batches = [vectors[i:i+batch_size] for i in range(0, len(vectors), batch_size)]
    
#     def upload_batch_parallel(batch_vectors: List[Tuple], batch_id: int):
#         try:
#             index.upsert(vectors=batch_vectors)
#             logging.info(f"✅ Uploaded batch {batch_id}: {len(batch_vectors)} vectors")
#             return batch_id
#         except Exception as e:
#             logging.error(f"❌ Upload batch {batch_id} failed: {e}")
#             return None

#     # Use more workers for uploads as well
#     with ThreadPoolExecutor(max_workers=8) as executor:
#         upload_futures = [
#             executor.submit(upload_batch_parallel, batch, i) 
#             for i, batch in enumerate(upload_batches)
#         ]
        
#         for future in as_completed(upload_futures):
#             result = future.result()
#             if result is not None:
#                 logging.info(f"✅ Upload batch {result} completed")

#     logging.info(f"✅ Uploaded {len(vectors)} vectors using aggressive parallel processing")
    
#     # Force garbage collection to free memory
#     gc.collect()

# def embed_query_parallel(query: str) -> List[float]:
#     """Thread-safe query embedding with retry logic"""
#     max_retries = 3
#     for attempt in range(max_retries):
#         try:
#             client = get_genai_client()
#             return client.embed_content(
#                 model="models/embedding-001",
#                 content="Find insurance coverage details: " + query,
#                 task_type="retrieval_query"
#             )["embedding"]
#         except Exception as e:
#             if attempt < max_retries - 1:
#                 logging.warning(f"Query embedding attempt {attempt + 1} failed: {e}, retrying...")
#                 time.sleep(0.5)
#             else:
#                 logging.error(f"Query embedding failed after {max_retries} attempts: {e}")
#                 raise

# def retrieve_chunks_contextual(query: str, top_k: int = 15) -> List[str]:
#     """Enhanced contextual retrieval with better chunk selection"""
#     logging.info(f"🔍 Retrieving relevant chunks for query: {query}")
    
#     # Get query embedding
#     query_vec = embed_query_parallel(query)
    
#     # Retrieve more chunks initially for better context
#     results = index.query(
#         vector=query_vec, 
#         top_k=top_k, 
#         include_metadata=True,
#         include_values=False
#     )
    
#     # Enhanced chunk selection based on relevance score
#     matches = []
#     for match in results["matches"]:
#         if match["score"] > 0.3:  # Filter by relevance threshold
#             matches.append(match["metadata"]["text"])
    
#     # If we don't have enough high-quality matches, include lower scoring ones
#     if len(matches) < 5:
#         for match in results["matches"]:
#             if match["metadata"]["text"] not in matches:
#                 matches.append(match["metadata"]["text"])
#                 if len(matches) >= 8:  # Ensure minimum context
#                     break
    
#     logging.info(f"✅ Retrieved {len(matches)} contextual chunks (score threshold: 0.3)")
#     return matches

# async def ask_GOOGLE_parallel(query: str, context_chunks: List[str]) -> Dict[str, Any]:
#     """Optimized GOOGLE query with parallel processing"""
#     logging.info("🤖 Stage 5: Generating answer with GOOGLE...")
    
#     # Truncate context if too long to avoid token limits
#     context = "\n---\n".join(context_chunks[:10])  # Limit to top 10 chunks
    
#     prompt = f"""
# You are a health insurance policy analysis assistant.
# Answer strictly using the clauses below.

# Query: {query}

# Policy Clauses:
# {context}

# Instructions:
# - ONLY use given clauses.
# - Extract exact numbers/limits.
# - If missing, say "Cannot determine".
# - Output strictly JSON:

# {{
#   "decision": "Yes / No / Cannot determine",
#   "amount": "Coverage limit or Unknown",
#   "justification": "Cite exact clauses",
#   "clause_ids": ["C1", "C2"],
#   "risk_level": "Red / Orange / Yellow / Black",
#   "answers": ["Extracted factual statements"]
# }}
# """
#     try:
#         model = genai.GenerativeModel("GOOGLE-1.5-flash")
#         resp = await asyncio.to_thread(model.generate_content, prompt)
#         txt = resp.text.strip()
#         if txt.startswith("json"):
#             txt = txt[7:]
#         if txt.endswith(""):
#             txt = txt[:-3]
#         result = json.loads(txt)
#         logging.info("✅ GOOGLE response generated")
#         return result
#     except Exception as e:
#         logging.error(f"❌ GOOGLE error: {str(e)}")
#         return {
#             "decision": "Cannot determine",
#             "amount": "Unknown",
#             "justification": f"Error: {str(e)}",
#             "clause_ids": [],
#             "risk_level": "Yellow",
#             "answers": []
#         }

# async def process_question_parallel(query: str) -> Dict[str, Any]:
#     """Process a single question with parallel retrieval and generation"""
#     # Retrieve chunks and generate answer concurrently
#     retrieved_chunks = retrieve_chunks_contextual(query)
#     answer = await ask_GOOGLE_parallel(query, retrieved_chunks)
#     return answer

# # === API Endpoints ===
# @app.get("/health")
# async def health_check():
#     """Health check endpoint to verify server is running"""
#     return {"status": "healthy", "service": "HackRx Webhook API (Aggressively Optimized for 16GB RAM)"}

# @app.post("/hackrx/run")
# async def run_submission(req: RunRequest):
#     logging.info("📩 POST request received")
#     logging.info(f"➡ Document: {req.documents}")
#     logging.info(f"➡ Questions: {len(req.questions)}")

#     start_time = time.time()
#     pdf_path = "temp.pdf"
#     doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, req.documents))

#     # Stage 1-4: Optimized ingestion pipeline
#     ingestion_start = time.time()
#     download_pdf_optimized(req.documents, pdf_path)
#     text = extract_text_from_pdf_parallel(pdf_path)
#     chunks = chunk_document_optimized(text)
#     upload_chunks_aggressive_parallel(doc_id, chunks)
#     ingestion_time = time.time() - ingestion_start
#     logging.info(f"⏱ Ingestion completed in {ingestion_time:.2f}s")

#     # Stage 5: Parallel question processing
#     processing_start = time.time()
    
#     # Process all questions concurrently
#     tasks = [process_question_parallel(q) for q in req.questions]
#     answers = await asyncio.gather(*tasks)
    
#     processing_time = time.time() - processing_start
#     total_time = round(time.time() - start_time, 2)
    
#     logging.info(f"⏱ Processing completed in {processing_time:.2f}s")
#     logging.info(f"✅ Total time: {total_time}s (Ingestion: {ingestion_time:.2f}s, Processing: {processing_time:.2f}s)")

#     # Clean up temp file
#     try:
#         os.remove(pdf_path)
#     except:
#         pass

#     return {
#         "answers": answers,
#         "performance": {
#             "total_time": total_time,
#             "ingestion_time": round(ingestion_time, 2),
#             "processing_time": round(processing_time, 2),
#             "questions_processed": len(req.questions),
#             "optimization": "16GB RAM aggressive parallel processing"
#         }
#     }

"""
HackRx Webhook API (Enhanced for Accuracy & Speed)

Key Improvements:
- Better chunking strategy for insurance documents
- Enhanced context retrieval with semantic filtering
- Improved prompt engineering for policy Q&A
- Memory-efficient processing
- Better error handling and retry logic
"""

import os
import re
import uuid
import json
import time
import fitz  # PyMuPDF
import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
from pinecone import Pinecone, ServerlessSpec
import asyncio
from typing import List, Tuple, Dict, Any
import threading
import gc
from collections import defaultdict

# === Setup Logging ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# === Load Environment ===
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "hackrx-index").lower().replace("_", "-")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# === Configure Clients ===
genai.configure(api_key=GOOGLE_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

if INDEX_NAME not in pc.list_indexes().names():
    logging.info(f"Index '{INDEX_NAME}' not found. Creating new one...")
    pc.create_index(
        name=INDEX_NAME,
        dimension=768,
        metric="cosine",
        spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION)
    )
index = pc.Index(INDEX_NAME)

app = FastAPI()

# === Thread-safe clients ===
thread_local = threading.local()

def get_genai_client():
    """Thread-safe GOOGLE client"""
    if not hasattr(thread_local, 'genai_client'):
        thread_local.genai_client = genai
    return thread_local.genai_client

# === Data Models ===
class RunRequest(BaseModel):
    documents: str
    questions: list[str]

# === Additional imports for form-data support ===
from fastapi import Form, File, UploadFile
import json

# === Enhanced PDF Processing ===
def download_pdf_optimized(url: str, save_path: str):
    """Optimized PDF download with better error handling"""
    logging.info("📥 Stage 1: Downloading PDF...")
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (compatible; HackRx/1.0)'
    })
    
    try:
        r = session.get(url, stream=True, timeout=30)
        r.raise_for_status()
        
        with open(save_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        
        session.close()
        logging.info("✅ PDF downloaded successfully")
        return save_path
    except Exception as e:
        session.close()
        logging.error(f"❌ PDF download failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to download PDF: {e}")

def extract_text_with_structure(pdf_path):
    """Enhanced text extraction preserving document structure"""
    logging.info("📄 Stage 2: Extracting structured text from PDF...")
    
    doc = fitz.open(pdf_path)
    structured_text = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Extract text with position information
        text_dict = page.get_text("dict")
        page_text = []
        
        for block in text_dict["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    line_text = ""
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if text:
                            # Check if it's a heading/section (larger font or bold)
                            font_size = span["size"]
                            font_flags = span["flags"]
                            
                            if font_size > 12 or font_flags & 2**4:  # Bold text or large font
                                text = f"\n=== {text} ===\n"
                            
                            line_text += text + " "
                    
                    if line_text.strip():
                        page_text.append(line_text.strip())
        
        if page_text:
            structured_text.append(f"\n[Page {page_num + 1}]\n")
            structured_text.extend(page_text)
    
    doc.close()
    full_text = "\n".join(structured_text)
    
    logging.info(f"✅ Extracted {len(full_text.split())} words with structure preserved")
    return full_text

def chunk_insurance_document_enhanced(text, chunk_size=600, overlap=100):
    """Enhanced chunking specifically designed for insurance documents"""
    logging.info("✂ Stage 3: Enhanced insurance document chunking...")
    
    # Insurance-specific section patterns
    section_patterns = [
        r'(?i)\b(?:section|clause|article|part|chapter)\s+\d+',
        r'(?i)\b(?:coverage|benefit|exclusion|condition|definition)',
        r'(?i)\b(?:\d+\.?\d*)\s+[A-Z][a-z]+',  # Numbered sections
        r'(?i)(?:waiting period|grace period|premium|deductible|co-payment)',
        r'(?i)(?:maternity|pre-existing|ayush|hospital|treatment)'
    ]
    
    # Split text into paragraphs
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    
    chunks = []
    current_chunk = []
    current_size = 0
    
    for para in paragraphs:
        para_words = len(para.split())
        
        # Check if this paragraph starts a new important section
        is_section_start = any(re.search(pattern, para) for pattern in section_patterns)
        
        # If adding this paragraph would exceed chunk size, finalize current chunk
        if current_size + para_words > chunk_size and current_chunk:
            chunk_text = '\n'.join(current_chunk)
            chunks.append(chunk_text)
            
            # Overlap: keep last few sentences for context
            if overlap > 0:
                sentences = chunk_text.split('. ')
                overlap_sentences = sentences[-2:] if len(sentences) > 2 else sentences
                current_chunk = ['. '.join(overlap_sentences)]
                current_size = len(' '.join(current_chunk).split())
            else:
                current_chunk = []
                current_size = 0
        
        # Add paragraph to current chunk
        current_chunk.append(para)
        current_size += para_words
        
        # If this is a major section start and chunk is getting large, consider breaking
        if is_section_start and current_size > chunk_size * 0.7:
            chunk_text = '\n'.join(current_chunk)
            chunks.append(chunk_text)
            current_chunk = []
            current_size = 0
    
    # Add final chunk
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    # Create chunk metadata
    structured_chunks = []
    for i, chunk in enumerate(chunks):
        # Extract potential clause/section identifiers
        clause_match = re.search(r'(?i)(?:section|clause|article)\s+(\d+(?:\.\d+)*)', chunk)
        clause_id = clause_match.group(1) if clause_match else f"chunk_{i+1}"
        
        structured_chunks.append((clause_id, chunk))
    
    logging.info(f"✅ Created {len(structured_chunks)} enhanced insurance chunks")
    return structured_chunks

def embed_batch_with_retry(batch_texts: List[str], batch_id: int, max_retries: int = 3) -> Tuple[List[List[float]], int]:
    """Enhanced batch embedding with rate limit handling"""
    for attempt in range(max_retries):
        try:
            client = get_genai_client()
            
            # Handle single text vs batch differently
            if len(batch_texts) == 1:
                resp = client.embed_content(
                    model="models/embedding-001",
                    content=batch_texts[0],
                    task_type="retrieval_document"
                )
                # Debug logging
                logging.info(f"Debug - Single embedding response type: {type(resp)}")
                if isinstance(resp, dict):
                    logging.info(f"Debug - Response keys: {resp.keys()}")
                
                # Single embedding response
                if isinstance(resp, dict) and "embedding" in resp:
                    batch_embeddings = [resp["embedding"]]
                else:
                    batch_embeddings = [resp]
            else:
                # Batch embedding - process one by one to avoid API issues
                batch_embeddings = []
                for text in batch_texts:
                    resp = client.embed_content(
                        model="models/embedding-001",
                        content=text,
                        task_type="retrieval_document"
                    )
                    if isinstance(resp, dict) and "embedding" in resp:
                        batch_embeddings.append(resp["embedding"])
                    else:
                        batch_embeddings.append(resp)
                    
                    # Small delay to avoid rate limits
                    time.sleep(0.1)
                
            logging.info(f"✅ Batch {batch_id}: Generated {len(batch_embeddings)} embeddings")
            return batch_embeddings, batch_id
            
        except Exception as e:
            error_str = str(e)
            
            # Handle rate limiting specifically
            if "429" in error_str or "quota" in error_str.lower():
                if "retry_delay" in error_str:
                    # Extract retry delay from error message
                    import re
                    delay_match = re.search(r'retry_delay.*?seconds: (\d+)', error_str)
                    wait_time = int(delay_match.group(1)) + 2 if delay_match else 60
                else:
                    wait_time = 60  # Default wait for rate limit
                
                logging.warning(f"🚫 Rate limit hit for batch {batch_id}. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            # Regular exponential backoff for other errors
            wait_time = (2 ** attempt) * 0.5
            if attempt < max_retries - 1:
                logging.warning(f"❌ Batch {batch_id} attempt {attempt + 1} failed: {e}, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logging.error(f"❌ Batch {batch_id} failed after {max_retries} attempts: {e}")
                return [], batch_id

def upload_chunks_memory_efficient(doc_id: str, chunks: List[Tuple[str, str]], batch_size: int = 100):
    """Memory-efficient chunk upload with better error handling"""
    logging.info("🧠 Stage 4: Checking existing document...")
    
    # Check if document already exists
    try:
        existing = index.query(
            vector=[0.0]*768,
            filter={"doc_id": {"$eq": doc_id}},
            top_k=1
        )
        if existing["matches"]:
            logging.info("⚡ Document already indexed. Skipping upload.")
            return
    except Exception as e:
        logging.warning(f"Could not check existing document: {e}. Proceeding with upload...")

    logging.info("🧠 Uploading chunks with memory-efficient processing...")
    
    # Process in much smaller batches to avoid rate limits
    total_chunks = len(chunks)
    upload_batch_size = min(batch_size, 10)  # Much smaller batches for rate limit management
    
    successful_uploads = 0
    
    for batch_start in range(0, total_chunks, upload_batch_size):
        batch_end = min(batch_start + upload_batch_size, total_chunks)
        batch_chunks = chunks[batch_start:batch_end]
        
        batch_num = batch_start//upload_batch_size + 1
        total_batches = (total_chunks-1)//upload_batch_size + 1
        
        logging.info(f"Processing batch {batch_num}/{total_batches} ({len(batch_chunks)} chunks)")
        
        # Extract texts for embedding
        texts = [chunk for _, chunk in batch_chunks]
        
        # Get embeddings for this batch with rate limit handling
        embeddings, _ = embed_batch_with_retry(texts, batch_start//upload_batch_size)
        
        if not embeddings:
            logging.warning(f"Skipping batch {batch_num} due to embedding failure")
            continue
        
        # Create vectors with proper validation
        vectors = []
        for i, ((clause_id, chunk), emb) in enumerate(zip(batch_chunks, embeddings)):
            vector_id = str(uuid.uuid4())
            
            # Ensure embedding is a flat list of floats
            if isinstance(emb, list) and len(emb) > 0:
                if isinstance(emb[0], list):
                    # If nested list, flatten it
                    flat_emb = emb[0] if len(emb) == 1 else [item for sublist in emb for item in sublist]
                else:
                    flat_emb = emb
            else:
                logging.error(f"Invalid embedding format for chunk {i}: {type(emb)}")
                continue
            
            # Validate embedding dimensions (should be 768 for embedding-001)
            if len(flat_emb) != 768:
                logging.error(f"Invalid embedding dimension for chunk {i}: {len(flat_emb)} (expected 768)")
                continue
            
            # Validate all elements are floats
            try:
                flat_emb = [float(x) for x in flat_emb]
            except (ValueError, TypeError) as e:
                logging.error(f"Invalid embedding values for chunk {i}: {e}")
                continue
            
            metadata = {
                "text": chunk[:40000],  # Limit metadata size
                "clause_id": clause_id,
                "doc_id": doc_id,
                "chunk_index": batch_start + i
            }
            vectors.append((vector_id, flat_emb, metadata))
        
        if not vectors:
            logging.warning(f"No valid vectors in batch {batch_num}")
            continue
        
        # Upload to Pinecone with retry logic
        max_upload_retries = 3
        for upload_attempt in range(max_upload_retries):
            try:
                index.upsert(vectors=vectors)
                logging.info(f"✅ Uploaded {len(vectors)} vectors from batch {batch_num}")
                successful_uploads += len(vectors)
                break
            except Exception as e:
                if upload_attempt < max_upload_retries - 1:
                    wait_time = (2 ** upload_attempt) * 2
                    logging.warning(f"Upload attempt {upload_attempt + 1} failed: {e}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logging.error(f"❌ Failed to upload batch {batch_num} after {max_upload_retries} attempts: {e}")
        
        # Add delay between batches to manage rate limits
        if batch_num < total_batches:
            time.sleep(2)  # 2 second delay between batches
        
        # Force garbage collection between batches
        gc.collect()
    
    logging.info(f"✅ Completed upload: {successful_uploads}/{total_chunks} chunks successfully uploaded")
    
    if successful_uploads == 0:
        raise Exception("Failed to upload any chunks to Pinecone")

def retrieve_relevant_context(query: str, top_k: int = 12) -> List[str]:
    """Enhanced context retrieval with better fallback strategies"""
    logging.info(f"🔍 Retrieving context for: {query[:100]}...")
    
    try:
        # Enhanced query embedding with context
        client = get_genai_client()
        query_embedding = client.embed_content(
            model="models/embedding-001",
            content=f"Insurance policy question: {query}",
            task_type="retrieval_query"
        )["embedding"]
        
        # First attempt: Higher top_k with lower threshold
        results = index.query(
            vector=query_embedding,
            top_k=min(top_k * 3, 50),  # Get more results initially
            include_metadata=True,
            include_values=False
        )
        
        logging.info(f"Debug - Pinecone returned {len(results['matches'])} matches")
        if results['matches']:
            logging.info(f"Debug - Top match score: {results['matches'][0]['score']:.3f}")
        
        # Enhanced filtering with multiple fallback thresholds
        relevant_chunks = []
        seen_content = set()
        
        # Try different relevance thresholds
        thresholds = [0.25, 0.15, 0.05, 0.0]  # Progressively lower thresholds
        
        for threshold in thresholds:
            relevant_chunks = []
            seen_content = set()
            
            for match in results["matches"]:
                score = match["score"]
                text = match["metadata"]["text"]
                
                # Skip if below current threshold
                if score < threshold:
                    continue
                
                # Skip duplicate content
                text_hash = hash(text[:200])
                if text_hash in seen_content:
                    continue
                seen_content.add(text_hash)
                
                # Calculate keyword overlap
                query_words = set(query.lower().split())
                text_words = set(text.lower().split())
                keyword_overlap = len(query_words.intersection(text_words))
                
                relevant_chunks.append({
                    'text': text,
                    'score': score,
                    'keyword_overlap': keyword_overlap,
                    'clause_id': match["metadata"].get("clause_id", "unknown")
                })
            
            # If we found enough chunks, break
            if len(relevant_chunks) >= 5:
                logging.info(f"Found {len(relevant_chunks)} chunks with threshold {threshold}")
                break
        
        if not relevant_chunks:
            # Final fallback: try broader keyword search
            logging.warning("No chunks found with semantic search, trying keyword fallback...")
            
            # Extract key terms from query for broader search
            key_terms = []
            insurance_terms = {
                'grace period': 'grace',
                'waiting period': 'waiting',
                'pre-existing': 'pre-existing',
                'maternity': 'maternity',
                'cataract': 'cataract',
                'organ donor': 'organ',
                'no claim discount': 'discount',
                'preventive': 'preventive',
                'hospital': 'hospital',
                'ayush': 'ayush',
                'room rent': 'room',
                'icu': 'icu'
            }
            
            query_lower = query.lower()
            for term, keyword in insurance_terms.items():
                if term in query_lower:
                    key_terms.append(keyword)
            
            # If we have key terms, do a broader search
            if key_terms:
                broader_query = f"Insurance policy {' '.join(key_terms)}"
                broader_embedding = client.embed_content(
                    model="models/embedding-001",
                    content=broader_query,
                    task_type="retrieval_query"
                )["embedding"]
                
                broader_results = index.query(
                    vector=broader_embedding,
                    top_k=20,
                    include_metadata=True,
                    include_values=False
                )
                
                # Take any matches with score > 0
                for match in broader_results["matches"]:
                    if match["score"] > 0:
                        text = match["metadata"]["text"]
                        text_hash = hash(text[:200])
                        if text_hash not in seen_content:
                            relevant_chunks.append({
                                'text': text,
                                'score': match["score"],
                                'keyword_overlap': 0,
                                'clause_id': match["metadata"].get("clause_id", "unknown")
                            })
                            seen_content.add(text_hash)
                            if len(relevant_chunks) >= 8:
                                break
        
        # Sort by relevance
        relevant_chunks.sort(key=lambda x: (x['score'], x['keyword_overlap']), reverse=True)
        
        # Return top chunks
        final_chunks = [chunk['text'] for chunk in relevant_chunks[:top_k]]
        
        if final_chunks:
            avg_score = sum(c['score'] for c in relevant_chunks[:len(final_chunks)]) / len(final_chunks)
            logging.info(f"✅ Retrieved {len(final_chunks)} relevant chunks (avg score: {avg_score:.3f})")
        else:
            logging.error("❌ No relevant chunks found even with fallback strategies")
            
            # Final debug: show what's in the index
            sample_results = index.query(
                vector=[0.0] * 768,  # Zero vector to get random samples
                top_k=3,
                include_metadata=True
            )
            logging.info(f"Debug - Sample docs in index: {len(sample_results['matches'])}")
            for i, match in enumerate(sample_results['matches'][:2]):
                text_preview = match['metadata']['text'][:200] + "..."
                logging.info(f"Debug - Sample {i}: {text_preview}")
        
        return final_chunks
        
    except Exception as e:
        logging.error(f"❌ Context retrieval failed: {e}")
        return []

async def generate_insurance_answer(query: str, context_chunks: List[str]) -> str:
    """Enhanced answer generation with rate limit handling"""
    logging.info("🤖 Stage 5: Generating insurance-specific answer...")
    
    # Limit context to prevent token overflow
    context = "\n\n---CONTEXT SECTION---\n".join(context_chunks[:8])
    
    # Enhanced prompt for insurance policy Q&A
    prompt = f"""You are an expert insurance policy analyst. Answer the question using ONLY the provided policy document sections.

QUESTION: {query}

POLICY DOCUMENT SECTIONS:
{context}

INSTRUCTIONS:
1. Answer ONLY based on the provided policy sections
2. Extract specific numbers, periods, percentages, and limits mentioned
3. Quote exact policy language when relevant
4. If information is not found in the provided sections, state "The provided policy sections do not contain information about [specific aspect]"
5. For waiting periods, grace periods, coverage limits - provide exact values
6. For yes/no questions, give clear answers with supporting details
7. Be precise and factual - avoid interpretations

ANSWER FORMAT:
- Direct answer to the question
- Supporting details from policy sections
- Exact quotes when relevant (in quotation marks)
- If incomplete information, specify what's missing

Answer:"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel("GOOGLE-1.5-flash")
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Lower temperature for factual accuracy
                    max_output_tokens=500,
                    top_p=0.8
                )
            )
            
            answer = response.text.strip()
            logging.info("✅ Insurance answer generated")
            return answer
            
        except Exception as e:
            error_str = str(e)
            
            # Handle rate limiting
            if "429" in error_str or "quota" in error_str.lower():
                if "retry_delay" in error_str:
                    import re
                    delay_match = re.search(r'retry_delay.*?seconds: (\d+)', error_str)
                    wait_time = int(delay_match.group(1)) + 2 if delay_match else 60
                else:
                    wait_time = 60
                
                if attempt < max_retries - 1:
                    logging.warning(f"🚫 Rate limit hit. Waiting {wait_time}s before retry {attempt + 2}...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logging.error(f"❌ Rate limit exceeded after {max_retries} attempts")
                    return f"Rate limit exceeded. Please upgrade to GOOGLE Pro API or wait for quota reset."
            
            # Other errors
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 1.0
                logging.warning(f"❌ Generation attempt {attempt + 1} failed: {e}, retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logging.error(f"❌ Answer generation failed after {max_retries} attempts: {e}")
                return f"Error generating answer: {str(e)}"

async def process_insurance_question(query: str) -> str:
    """Process insurance question with enhanced retrieval and generation"""
    try:
        # Retrieve relevant context
        context_chunks = retrieve_relevant_context(query, top_k=10)
        
        if not context_chunks:
            return "No relevant information found in the policy document for this question. The document may not contain details about this specific topic, or the content may not have been properly indexed."
        
        # Generate answer
        answer = await generate_insurance_answer(query, context_chunks)
        return answer
        
    except Exception as e:
        logging.error(f"❌ Question processing failed: {e}")
        return f"Error processing question: {str(e)}"

# === API Endpoints ===
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "HackRx Webhook API (Enhanced for Accuracy & Speed)",
        "version": "2.0"
    }

@app.post("/hackrx/run")
async def run_enhanced_submission(req: RunRequest = None, pdf_url: str = Form(None), questions: str = Form(None)):
    """Enhanced submission processing - supports both JSON and form-data"""
    
    # Handle form-data input
    if pdf_url and questions:
        try:
            questions_list = json.loads(questions)
            req = RunRequest(documents=pdf_url, questions=questions_list)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid questions JSON format: {e}")
    elif not req:
        raise HTTPException(status_code=400, detail="Either JSON body or form-data (pdf_url + questions) required")
    """Enhanced submission processing with better accuracy"""
    logging.info("📩 Enhanced POST request received")
    logging.info(f"➡ Document: {req.documents}")
    logging.info(f"➡ Questions: {len(req.questions)}")

    start_time = time.time()
    pdf_path = "temp_enhanced.pdf"
    doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, req.documents))

    try:
        # Enhanced ingestion pipeline
        ingestion_start = time.time()
        
        download_pdf_optimized(req.documents, pdf_path)
        text = extract_text_with_structure(pdf_path)
        chunks = chunk_insurance_document_enhanced(text)
        upload_chunks_memory_efficient(doc_id, chunks)
        
        ingestion_time = time.time() - ingestion_start
        logging.info(f"⏱ Enhanced ingestion completed in {ingestion_time:.2f}s")

        # Enhanced question processing with rate limit management
        processing_start = time.time()
        
        # Implement sequential processing with delays to manage rate limits
        final_answers = []
        
        for i, question in enumerate(req.questions):
            logging.info(f"Processing question {i+1}/{len(req.questions)}: {question[:50]}...")
            
            try:
                answer = await process_insurance_question(question)
                final_answers.append(answer)
                
                # Add delay between questions to manage rate limits
                if i < len(req.questions) - 1:  # Don't delay after last question
                    await asyncio.sleep(1)  # 1 second delay between questions
                    
            except Exception as e:
                logging.error(f"Question {i+1} failed: {e}")
                final_answers.append(f"Error processing question: {str(e)}")
        
        processing_time = time.time() - processing_start
        total_time = round(time.time() - start_time, 2)
        
        logging.info(f"⏱ Enhanced processing completed in {processing_time:.2f}s")
        logging.info(f"✅ Total time: {total_time}s")

        return {
            "answers": final_answers,
            "performance": {
                "total_time": total_time,
                "ingestion_time": round(ingestion_time, 2),
                "processing_time": round(processing_time, 2),
                "questions_processed": len(req.questions),
                "enhancement": "accuracy_and_speed_optimized"
            }
        }
        
    except Exception as e:
        logging.error(f"❌ Request processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
        
    finally:
        # Clean up
        try:
            os.remove(pdf_path)
        except:
            pass
        gc.collect()