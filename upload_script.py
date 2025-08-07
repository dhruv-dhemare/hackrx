
# """
# Best one so far and i am happy with this and the accuracy is about 85%
# this is the upload function

# """

# import os
# import fitz  # PyMuPDF
# import uuid
# import re
# from dotenv import load_dotenv
# import google.generativeai as genai
# from pinecone import Pinecone, ServerlessSpec

# # === Load Environment Variables ===
# load_dotenv()
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
# INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
# PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
# PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

# print("Loaded INDEX_NAME:", GOOGLE_API_KEY)
# # print("DEBUG ENV:", os.environ)  # See all env vars loaded
# # print("DEBUG PINECONE_INDEX_NAME:", os.getenv("PINECONE_INDEX_NAME"))



# # Normalize index name
# if INDEX_NAME:
#     INDEX_NAME = INDEX_NAME.lower().replace("_", "-")

# # === Configure GOOGLE ===
# genai.configure(api_key=GOOGLE_API_KEY)

# # === Initialize Pinecone Client ===
# pc = Pinecone(api_key=PINECONE_API_KEY)

# if INDEX_NAME not in pc.list_indexes().names():
#     print(f"Index '{INDEX_NAME}' not found. Creating it...")
#     pc.create_index(
#         name=INDEX_NAME,
#         dimension=768,
#         metric="cosine",
#         spec=ServerlessSpec(
#             cloud=PINECONE_CLOUD.strip(),
#             region=PINECONE_REGION.strip()
#         )
#     )

# index = pc.Index(INDEX_NAME)

# # === Step 1: Extract text from PDF ===
# def extract_text_from_pdf(pdf_path):
#     doc = fitz.open(pdf_path)
#     text = ""
#     for page_num, page in enumerate(doc, start=1):
#         page_text = page.get_text("text").strip()
#         if page_text:
#             text += f"\n[Page {page_num}]\n" + page_text + "\n"
#     return text

# # === Step 2: Clause-Aware Chunking with Grouping ===
# def semantic_chunk(text, min_clause_len=80, max_group_size=3):
#     clauses = re.split(r"(?=\n?\s*(\d+(?:\.\d+)*[a-zA-Z]?)\s+)", text)

#     chunks = []
#     buffer = []
#     group_count = 0
#     current_clause_id = None

#     for clause in clauses:
#         if not clause or not clause.strip():
#             continue
#         clause = clause.strip()

#         match = re.match(r"^(\d+(?:\.\d+)*[a-zA-Z]?)\s+", clause)
#         if match:
#             if buffer:
#                 chunks.append((current_clause_id or f"clause_{len(chunks)+1}", " ".join(buffer)))
#                 buffer = []
#                 group_count = 0
#             current_clause_id = match.group(1)

#         buffer.append(clause)
#         group_count += 1

#         if len(" ".join(buffer).split()) > min_clause_len or group_count >= max_group_size:
#             chunks.append((current_clause_id or f"clause_{len(chunks)+1}", " ".join(buffer)))
#             buffer = []
#             group_count = 0

#     if buffer:
#         chunks.append((current_clause_id or f"clause_{len(chunks)+1}", " ".join(buffer)))

#     print(f"✅ Document split into {len(chunks)} grouped clause-chunks.")
#     return chunks

# # === Step 3: Embed and Upload in Batches ===
# def upload_chunks_to_pinecone(chunks, index, batch_size=50):
#     print(f"📤 Uploading {len(chunks)} chunks to Pinecone...")
#     batch = []

#     for i, (clause_id, chunk) in enumerate(chunks):
#         try:
#             embedding = genai.embed_content(
#                 model="models/embedding-001",
#                 content=chunk,
#                 task_type="retrieval_document"
#             )["embedding"]

#             batch.append((
#                 str(uuid.uuid4()),
#                 embedding,
#                 {
#                     "text": chunk,
#                     "clause_id": str(clause_id) if clause_id else f"clause_{i+1}"
#                 }
#             ))

#             if len(batch) >= batch_size:
#                 index.upsert(batch)
#                 batch = []

#         except Exception as e:
#             print(f"⚠️ Error embedding clause {clause_id}: {e}")
#             continue

#     if batch:
#         index.upsert(batch)

#     print("✅ Upload completed.")

# # === Main Program ===
# if __name__ == "__main__":
#     print(f"✅ Connected to Pinecone index: {INDEX_NAME}")

#     pdf_path = input("📂 Enter the full path of your PDF file: ").strip()
#     if not os.path.exists(pdf_path):
#         print(f"❌ File not found: {pdf_path}")
#         exit()

#     pdf_text = extract_text_from_pdf(pdf_path)
#     clause_chunks = semantic_chunk(pdf_text)

#     upload_chunks_to_pinecone(clause_chunks, index)

#     print(f"📌 Document '{pdf_path}' successfully indexed into Pinecone with safe clause IDs.")


import os
import fitz  # PyMuPDF
import uuid
import re
import hashlib
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import google.generativeai as genai
from pinecone import Pinecone, ServerlessSpec

# === Load Environment Variables ===
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
    print(f"Creating Pinecone index: {INDEX_NAME}")
    pc.create_index(
        name=INDEX_NAME,
        dimension=768,
        metric="cosine",
        spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION)
    )

index = pc.Index(INDEX_NAME)

# === Step 1: Extract text from PDF ===
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page_num, page in enumerate(doc, start=1):
        page_text = page.get_text("text").strip()
        if page_text:
            text += f"\n[Page {page_num}]\n{page_text}\n"
    return text

# === Step 2: Improved Semantic Chunking with Overlap ===
def semantic_chunk(text, chunk_size=300, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk.split()) >= 50:  # Minimum chunk length filter
            chunks.append(chunk.strip())
    print(f"✅ Document split into {len(chunks)} semantic chunks.")
    return chunks

# === Step 3: Parallel Embedding + Deduplication ===
def embed_chunk(chunk):
    return genai.embed_content(model="models/embedding-001", content=chunk, task_type="retrieval_document")["embedding"]

def upload_chunks_to_pinecone(chunks, file_id, batch_size=50):
    print(f"📤 Uploading {len(chunks)} chunks to Pinecone namespace: {file_id} ...")
    batch = []

    def process_chunk(chunk):
        chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
        embedding = embed_chunk(chunk)
        return (str(uuid.uuid4()), embedding, {"text": chunk, "hash": chunk_hash})

    with ThreadPoolExecutor(max_workers=5) as executor:
        embedded_chunks = list(executor.map(process_chunk, chunks))

    # Deduplicate (by hash within the namespace)
    existing_hashes = set()
    results = index.query(
        vector=[0.0] * 768,
        top_k=1,
        namespace=file_id,
        include_metadata=True
    )
    if "matches" in results:
        existing_hashes = {match["metadata"].get("hash") for match in results["matches"] if "hash" in match["metadata"]}

    for vec in embedded_chunks:
        if vec[2]["hash"] not in existing_hashes:
            batch.append(vec)
            if len(batch) >= batch_size:
                index.upsert(vectors=batch, namespace=file_id)
                batch = []

    if batch:
        index.upsert(vectors=batch, namespace=file_id)
    print("✅ Upload completed successfully.")

# === Main Upload Program ===
if __name__ == "__main__":
    print(f"✅ Connected to Pinecone index: {INDEX_NAME}")
    pdf_path = input("📂 Enter the full path of your PDF file: ").strip()

    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        exit()

    file_id = os.path.splitext(os.path.basename(pdf_path))[0] + "_" + str(uuid.uuid4())[:6]
    pdf_text = extract_text_from_pdf(pdf_path)
    chunks = semantic_chunk(pdf_text)
    upload_chunks_to_pinecone(chunks, file_id)
    print(f"📌 Document '{pdf_path}' uploaded into Pinecone namespace: {file_id}")
