import os
import sys
import json
from dotenv import load_dotenv
import google.generativeai as genai
from pinecone import Pinecone

# === Load Environment Variables ===
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

if not GEMINI_API_KEY or not PINECONE_API_KEY or not INDEX_NAME:
    print(json.dumps({
        "decision": "Cannot determine",
        "amount": "Unknown",
        "justification": "Missing API keys or index name.",
        "clause_ids": [],
        "risk_level": "Yellow",
        "answers": []
    }))
    sys.exit(1)

# === Configure Gemini & Pinecone ===
genai.configure(api_key=GEMINI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)

if INDEX_NAME not in pc.list_indexes().names():
    print(json.dumps({
        "decision": "Cannot determine",
        "amount": "Unknown",
        "justification": f"Index {INDEX_NAME} not found.",
        "clause_ids": [],
        "risk_level": "Yellow",
        "answers": []
    }))
    sys.exit(1)

index = pc.Index(INDEX_NAME)

# === Helper Functions ===
def embed_text_for_query(text: str):
    response = genai.embed_content(
        model="models/embedding-001",
        content="Find insurance coverage details: " + text,
        task_type="retrieval_query"
    )
    return response["embedding"]

def retrieve_similar_chunks(query: str, top_k: int = 10):
    query_embedding = embed_text_for_query(query)
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )
    return [match["metadata"]["text"] for match in results["matches"]]

def ask_gemini(query: str, context_chunks: list):
    context = "\n---\n".join(context_chunks)
    prompt = f"""
You are a health insurance policy analysis assistant.
Answer the query strictly using the policy clauses below.

Query:
{query}

Policy Clauses:
{context}

Instructions:
- ONLY use the given clauses, do not invent.
- If any numeric value, percentage, or monetary amount is in the text, extract it exactly.
- If multiple waiting periods are given, report all and highlight the general Pre-existing Disease waiting period separately.
- If the clause mentions 'as per schedule', say 'Specified in Policy Schedule (not in text)' instead of 'Cannot determine'.
- If truly missing, then use 'Cannot determine'.
- Output strictly JSON:

{{
  "decision": "Yes / No / Cannot determine",
  "amount": "Coverage limit, percentage, or Unknown",
  "justification": "Explanation citing exact clauses provided",
  "clause_ids": ["C1", "C2"],
  "risk_level": "Red / Orange / Yellow / Black",
  "answers": [
    "Direct factual statements extracted from clauses"
  ]
}}
"""
    model = genai.GenerativeModel("gemini-1.5-pro")
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean ```json ``` wrappers if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        return json.loads(response_text)
    except Exception as e:
        return {
            "decision": "Cannot determine",
            "amount": "Unknown",
            "justification": f"Parsing/Generation error: {str(e)}",
            "clause_ids": [],
            "risk_level": "Yellow",
            "answers": []
        }

# === Entry Point ===
if __name__ == "__main__":
    import sys
    query = sys.argv[1]
    retrieved = retrieve_similar_chunks(query)
    if not retrieved:
        result = {
            "decision": "Cannot determine",
            "amount": "Unknown",
            "justification": "No relevant info found.",
            "clause_ids": [],
            "risk_level": "Yellow",
            "answers": []
        }
        print(json.dumps(result))  # ✅ only JSON
        sys.exit(0)

    answer = ask_gemini(query, retrieved)
    if not answer:
        answer = {
            "decision": "Cannot determine",
            "amount": "Unknown",
            "justification": "Parsing error.",
            "clause_ids": [],
            "risk_level": "Yellow",
            "answers": []
        }
    print(json.dumps(answer))  # ✅ only JSON
