import os
import fitz  # PyMuPDF
import uuid
import re
import hashlib
import json
import asyncio
import aiofiles
import aiohttp
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional, Union
from datetime import datetime, timedelta
import logging
from pathlib import Path
import tempfile
import time

# FastAPI imports
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse


# Database imports
import asyncpg
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from databases import Database

# Vector DB
from pinecone import Pinecone, ServerlessSpec
import openai

# ML/NLP imports
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from rank_bm25 import BM25Okapi

# Document processing
from docx import Document
import mammoth
import email
from pdf2image import convert_from_path
import pytesseract

# Other imports
from dataclasses import dataclass, asdict
from dotenv import load_dotenv
import redis
from cachetools import TTLCache
from pydantic import BaseModel, Field
from functools import lru_cache

# === Configuration ===
load_dotenv()

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/hackrx_db")
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "hackrx-documents")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Initialize services
openai.api_key = OPENAI_API_KEY
pc = Pinecone(api_key=PINECONE_API_KEY)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Database Models ===
Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    content_hash = Column(String, unique=True, nullable=False)
    file_size = Column(Integer)
    upload_time = Column(DateTime, default=datetime.utcnow)
    processing_status = Column(String, default="pending")  # pending, processing, completed, failed
    content_preview = Column(Text)
    metadata = Column(JSON)
    vector_count = Column(Integer, default=0)
    
class Query(Base):
    __tablename__ = "queries"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, nullable=False)
    questions = Column(JSON, nullable=False)
    answers = Column(JSON)
    processing_time = Column(Float)
    accuracy_score = Column(Float)
    query_time = Column(DateTime, default=datetime.utcnow)
    user_feedback = Column(JSON)  # For storing user ratings/corrections
    
class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_type = Column(String)  # definition, clause, general, etc.
    page_number = Column(Integer)
    importance_score = Column(Float, default=0.5)
    metadata = Column(JSON)
    vector_id = Column(String)  # Pinecone vector ID

# === Pydantic Models ===
class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    processing_status: str
    upload_time: datetime
    metadata: dict

class QueryRequest(BaseModel):
    questions: List[str]
    document_url: Optional[str] = None
    file_id: Optional[str] = None

class QueryResponse(BaseModel):
    file_id: str
    answers: List[str]
    processing_time: str
    accuracy_indicators: Dict
    metadata: Dict

# === FastAPI App Setup ===
app = FastAPI(
    title="HackRX Document QA System",
    version="3.0.0",
    description="Production-grade document QA with GPT-4, Pinecone, and PostgreSQL"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Database Setup ===
engine = create_async_engine(ASYNC_DATABASE_URL)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
database = Database(ASYNC_DATABASE_URL)

async def get_database():
    async with SessionLocal() as session:
        yield session

# === Initialize Services ===
@app.on_event("startup")
async def startup():
    await database.connect()
    
    # Create Pinecone index if not exists
    if INDEX_NAME not in pc.list_indexes().names():
        pc.create_index(
            name=INDEX_NAME,
            dimension=1536,  # OpenAI text-embedding-ada-002 dimension
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
    
    global pinecone_index
    pinecone_index = pc.Index(INDEX_NAME)
    
    # Initialize Redis
    global redis_client
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
    except:
        redis_client = None
        logger.warning("Redis not available")

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# === Enhanced Document Processing ===
class AdvancedDocumentProcessor:
    def __init__(self):
        # Use sentence-transformers for better semantic understanding
        self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
    
    async def process_document(self, file_path: str, filename: str) -> Tuple[str, Dict]:
        """Enhanced document processing with better structure extraction"""
        
        file_type = self._detect_file_type(file_path, filename)
        
        if file_type == 'pdf':
            content, structured_data = await self._process_pdf(file_path)
        elif file_type == 'docx':
            content, structured_data = await self._process_docx(file_path)
        elif file_type == 'email':
            content, structured_data = await self._process_email(file_path)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")
        
        return content, {
            **structured_data,
            'file_type': file_type,
            'processing_method': 'advanced_extraction'
        }
    
    def _detect_file_type(self, file_path: str, filename: str) -> str:
        """Improved file type detection"""
        with open(file_path, 'rb') as f:
            header = f.read(1024)
        
        if header.startswith(b'%PDF'):
            return 'pdf'
        elif header.startswith(b'PK\x03\x04') and filename.endswith('.docx'):
            return 'docx'
        elif b'From:' in header or b'Subject:' in header:
            return 'email'
        else:
            # Fallback to extension
            ext = Path(filename).suffix.lower()
            return ext[1:] if ext in ['.pdf', '.docx', '.eml'] else 'unknown'
    
    async def _process_pdf(self, file_path: str) -> Tuple[str, Dict]:
        """Advanced PDF processing with insurance-specific extraction"""
        doc = fitz.open(file_path)
        full_text = ""
        structured_data = {
            'definitions': {},
            'waiting_periods': {},
            'coverage_details': {},
            'exclusions': [],
            'tables': [],
            'numerical_data': {},
            'sections': {}
        }
        
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text").strip()
            
            # OCR fallback for image-based PDFs
            if not page_text:
                try:
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("png")
                    page_text = pytesseract.image_to_string(img_data)
                except Exception as e:
                    logger.warning(f"OCR failed for page {page_num}: {e}")
                    continue
            
            full_text += f"\n[Page {page_num}]\n{page_text}\n"
            
            # Extract insurance-specific patterns
            self._extract_insurance_patterns(page_text, structured_data)
            
            # Extract tables
            tables = page.find_tables()
            for table in tables:
                try:
                    table_data = table.extract()
                    structured_data['tables'].append({
                        'page': page_num,
                        'data': table_data
                    })
                except:
                    pass
        
        doc.close()
        return full_text, structured_data
    
    async def _process_docx(self, file_path: str) -> Tuple[str, Dict]:
        """Enhanced DOCX processing"""
        doc = Document(file_path)
        full_text = ""
        structured_data = {
            'paragraphs': [],
            'tables': [],
            'headers': [],
            'definitions': {},
            'key_sections': {}
        }
        
        # Extract paragraphs with styles
        for para in doc.paragraphs:
            if para.text.strip():
                full_text += para.text + "\n"
                structured_data['paragraphs'].append({
                    'text': para.text,
                    'style': para.style.name if para.style else 'Normal'
                })
        
        # Extract tables
        for table in doc.tables:
            table_data = []
            for row in table.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                table_data.append(row_data)
            structured_data['tables'].append(table_data)
            full_text += "\n" + "\n".join([" | ".join(row) for row in table_data]) + "\n"
        
        # Extract patterns
        self._extract_insurance_patterns(full_text, structured_data)
        
        return full_text, structured_data
    
    async def _process_email(self, file_path: str) -> Tuple[str, Dict]:
        """Email processing"""
        with open(file_path, 'rb') as f:
            msg = email.message_from_bytes(f.read())
        
        structured_data = {'headers': {}, 'body': '', 'attachments': []}
        
        # Extract headers
        for header in ['From', 'To', 'Subject', 'Date']:
            if msg.get(header):
                structured_data['headers'][header] = msg.get(header)
        
        # Extract body
        body_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body_text += part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            body_text = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        structured_data['body'] = body_text
        full_text = f"Subject: {structured_data['headers'].get('Subject', '')}\n{body_text}"
        
        return full_text, structured_data
    
    def _extract_insurance_patterns(self, text: str, structured_data: Dict):
        """Extract insurance-specific patterns with high accuracy"""
        
        # Enhanced patterns for insurance documents
        patterns = {
            'waiting_periods': [
                r'waiting period[s]?\s+(?:of\s+)?(\d+)\s+(days?|months?|years?)',
                r'(?:wait|waiting)\s+(?:time|period).*?(\d+)\s+(days?|months?|years?)',
                r'(\d+)\s+(days?|months?|years?)\s+waiting\s+period'
            ],
            'grace_periods': [
                r'grace period[s]?\s+(?:of\s+)?(\d+)\s+(days?|months?|years?)',
                r'(\d+)\s+(days?|months?|years?)\s+grace\s+period'
            ],
            'coverage_amounts': [
                r'sum insured.*?(?:rs\.?\s*|inr\s*|₹\s*)?(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:lakhs?|crores?|/-)?',
                r'coverage.*?(?:rs\.?\s*|inr\s*|₹\s*)?(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:lakhs?|crores?|/-)?',
                r'(?:limit|maximum).*?(?:rs\.?\s*|inr\s*|₹\s*)?(\d+(?:,\d+)*(?:\.\d+)?)'
            ],
            'percentages': [
                r'(\d+(?:\.\d+)?)\s*%',
                r'(\d+(?:\.\d+)?)\s*percent'
            ],
            'definitions': [
                r'([A-Z][a-zA-Z\s]+(?:[A-Z][a-zA-Z\s]*)*)\s*(?:means?|is defined as|shall mean)\s+([^.!?]+[.!?])',
                r'"([^"]+)"\s+means\s+([^.!?]+[.!?])'
            ]
        }
        
        for pattern_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    if pattern_type == 'definitions':
                        for term, definition in matches:
                            structured_data.setdefault('definitions', {})[term.strip()] = definition.strip()
                    else:
                        structured_data.setdefault(pattern_type, []).extend(matches)

# === GPT-4 Enhanced QA System ===
class GPT4QASystem:
    def __init__(self):
        self.model = "gpt-4"  # Use GPT-4 instead of Gemini
        self.embedding_model = "text-embedding-ada-002"
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get OpenAI embeddings for texts"""
        try:
            response = await openai.Embedding.acreate(
                model=self.embedding_model,
                input=texts
            )
            return [item['embedding'] for item in response['data']]
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise
    
    async def generate_answers(
        self, 
        questions: List[str], 
        context_chunks: List[str],
        structured_data: Dict
    ) -> Tuple[List[str], Dict]:
        """Generate answers using GPT-4 with enhanced prompting"""
        
        # Create enhanced context
        enhanced_context = self._create_enhanced_context(context_chunks, structured_data)
        
        # Analyze questions for better prompting
        question_analysis = [self._analyze_question(q) for q in questions]
        
        # Create sophisticated prompt
        prompt = self._create_advanced_prompt(questions, question_analysis, enhanced_context)
        
        try:
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert insurance policy analyst with deep knowledge of policy terms, coverage details, and regulatory requirements. Provide accurate, specific answers based strictly on the provided policy document."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistency
                max_tokens=2000,
                top_p=0.1
            )
            
            # Parse response
            response_content = response.choices[0].message.content
            answers, confidence_scores = self._parse_gpt4_response(response_content, questions)
            
            accuracy_indicators = {
                'confidence_scores': confidence_scores,
                'context_relevance': self._calculate_context_relevance(questions, context_chunks),
                'structured_data_usage': self._calculate_structured_usage(questions, structured_data)
            }
            
            return answers, accuracy_indicators
            
        except Exception as e:
            logger.error(f"GPT-4 generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Answer generation failed: {str(e)}")
    
    def _create_enhanced_context(self, chunks: List[str], structured_data: Dict) -> str:
        """Create enhanced context combining chunks and structured data"""
        context_parts = []
        
        # Add structured definitions
        if structured_data.get('definitions'):
            context_parts.append("=== POLICY DEFINITIONS ===")
            for term, definition in structured_data['definitions'].items():
                context_parts.append(f"{term}: {definition}")
        
        # Add waiting periods
        if structured_data.get('waiting_periods'):
            context_parts.append("\n=== WAITING PERIODS ===")
            for period in structured_data['waiting_periods']:
                context_parts.append(f"Waiting Period: {period}")
        
        # Add main content chunks
        context_parts.append("\n=== POLICY CONTENT ===")
        context_parts.extend(chunks[:10])  # Limit chunks to avoid token limits
        
        return "\n".join(context_parts)
    
    def _analyze_question(self, question: str) -> Dict:
        """Analyze question type and requirements"""
        question_lower = question.lower()
        
        analysis = {
            'type': 'general',
            'requires_numbers': bool(re.search(r'how much|amount|percentage|cost|fee', question_lower)),
            'requires_time': bool(re.search(r'when|period|time|duration|wait', question_lower)),
            'requires_definition': bool(re.search(r'what is|define|meaning', question_lower)),
            'requires_coverage': bool(re.search(r'cover|include|benefit|eligible', question_lower)),
            'keywords': re.findall(r'\b\w+\b', question_lower)
        }
        
        # Determine specific type
        if analysis['requires_definition']:
            analysis['type'] = 'definition'
        elif analysis['requires_time']:
            analysis['type'] = 'waiting_period'
        elif analysis['requires_coverage']:
            analysis['type'] = 'coverage'
        elif analysis['requires_numbers']:
            analysis['type'] = 'numerical'
        
        return analysis
    
    def _create_advanced_prompt(self, questions: List[str], analyses: List[Dict], context: str) -> str:
        """Create advanced prompt with question-specific instructions"""
        
        prompt = f"""
Based on the following insurance policy document, answer the questions with high accuracy and specificity.

POLICY DOCUMENT:
{context}

INSTRUCTIONS:
1. Answer ONLY based on the provided policy document
2. For numerical values (amounts, percentages, periods), provide exact figures with units
3. For coverage questions, specify conditions, limitations, and eligibility criteria
4. For definitions, provide complete explanations as stated in the policy
5. If information is not found, state "Information not available in the provided policy document"
6. Maintain consistency with policy terminology

QUESTIONS:
"""
        
        for i, (question, analysis) in enumerate(zip(questions, analyses), 1):
            prompt += f"\n{i}. {question}"
            
            # Add specific instructions based on question type
            if analysis['type'] == 'waiting_period':
                prompt += " (Provide exact duration in days/months/years)"
            elif analysis['type'] == 'coverage':
                prompt += " (Include conditions and limitations)"
            elif analysis['type'] == 'numerical':
                prompt += " (Provide exact figures with currency/percentage)"
            elif analysis['type'] == 'definition':
                prompt += " (Provide complete policy definition)"
        
        prompt += f"""

Respond in JSON format:
{{
    "answers": [
        {{"answer": "Answer 1", "confidence": 0.95, "sources": ["relevant section"]}},
        {{"answer": "Answer 2", "confidence": 0.88, "sources": ["relevant section"]}},
        ...
    ]
}}
"""
        
        return prompt
    
    def _parse_gpt4_response(self, response: str, questions: List[str]) -> Tuple[List[str], List[float]]:
        """Parse GPT-4 response and extract confidence scores"""
        try:
            parsed = json.loads(response)
            answers = []
            confidence_scores = []
            
            for item in parsed.get('answers', []):
                if isinstance(item, dict):
                    answers.append(item.get('answer', 'No answer provided'))
                    confidence_scores.append(item.get('confidence', 0.5))
                else:
                    answers.append(str(item))
                    confidence_scores.append(0.5)
            
            # Ensure we have the right number of answers
            while len(answers) < len(questions):
                answers.append("Information not available in the provided policy document")
                confidence_scores.append(0.0)
            
            return answers[:len(questions)], confidence_scores[:len(questions)]
            
        except json.JSONDecodeError:
            # Fallback: split by lines and extract answers
            lines = response.strip().split('\n')
            answers = []
            for line in lines:
                if line.strip() and not line.startswith(('Based on', 'According to')):
                    answers.append(line.strip())
            
            while len(answers) < len(questions):
                answers.append("Information not available in the provided policy document")
            
            return answers[:len(questions)], [0.5] * len(questions)
    
    def _calculate_context_relevance(self, questions: List[str], chunks: List[str]) -> float:
        """Calculate how relevant the context is to the questions"""
        question_text = " ".join(questions).lower()
        context_text = " ".join(chunks).lower()
        
        # Simple keyword overlap calculation
        question_words = set(re.findall(r'\b\w+\b', question_text))
        context_words = set(re.findall(r'\b\w+\b', context_text))
        
        if not question_words:
            return 0.0
        
        overlap = len(question_words.intersection(context_words))
        return min(overlap / len(question_words), 1.0)
    
    def _calculate_structured_usage(self, questions: List[str], structured_data: Dict) -> float:
        """Calculate how much structured data can help answer questions"""
        score = 0.0
        total_questions = len(questions)
        
        for question in questions:
            question_lower = question.lower()
            
            # Check if structured data can help
            if any(keyword in question_lower for keyword in ['definition', 'define', 'what is']):
                if structured_data.get('definitions'):
                    score += 1.0
            elif any(keyword in question_lower for keyword in ['waiting', 'period', 'grace']):
                if structured_data.get('waiting_periods') or structured_data.get('grace_periods'):
                    score += 1.0
            else:
                score += 0.5  # General structured data relevance
        
        return score / total_questions if total_questions > 0 else 0.0

# === Enhanced Vector Search ===
class AdvancedVectorSearch:
    def __init__(self):
        self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    async def hybrid_search(
        self, 
        query: str, 
        namespace: str, 
        structured_data: Dict,
        top_k: int = 15
    ) -> List[str]:
        """Advanced hybrid search combining multiple techniques"""
        
        # 1. Vector similarity search
        query_embedding = await self._get_query_embedding(query)
        vector_results = pinecone_index.query(
            namespace=namespace,
            vector=query_embedding,
            top_k=top_k * 2,  # Get more for filtering
            include_metadata=True,
            filter={"importance_score": {"$gte": 0.3}}
        )
        
        vector_chunks = [match["metadata"]["text"] for match in vector_results["matches"]]
        
        # 2. Add relevant structured data
        structured_chunks = self._get_relevant_structured_data(query, structured_data)
        
        # 3. Combine and deduplicate
        all_chunks = structured_chunks + vector_chunks
        unique_chunks = list(dict.fromkeys(all_chunks))  # Remove duplicates
        
        # 4. Re-rank using semantic similarity
        reranked_chunks = await self._rerank_chunks(query, unique_chunks)
        
        return reranked_chunks[:top_k]
    
    async def _get_query_embedding(self, query: str) -> List[float]:
        """Get embedding for query"""
        try:
            response = await openai.Embedding.acreate(
                model="text-embedding-ada-002",
                input=query
            )
            return response['data'][0]['embedding']
        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            # Fallback to sentence transformer
            return self.sentence_model.encode(query).tolist()
    
    def _get_relevant_structured_data(self, query: str, structured_data: Dict) -> List[str]:
        """Extract relevant structured data based on query"""
        relevant_chunks = []
        query_lower = query.lower()
        
        # Check definitions
        if any(keyword in query_lower for keyword in ['definition', 'define', 'what is', 'means']):
            for term, definition in structured_data.get('definitions', {}).items():
                if any(word in term.lower() for word in query_lower.split()):
                    relevant_chunks.append(f"DEFINITION: {term} means {definition}")
        
        # Check waiting periods
        if any(keyword in query_lower for keyword in ['waiting', 'period', 'wait', 'grace']):
            for period in structured_data.get('waiting_periods', []):
                relevant_chunks.append(f"WAITING PERIOD: {period}")
        
        # Check coverage details
        if any(keyword in query_lower for keyword in ['cover', 'coverage', 'benefit', 'include']):
            for detail in structured_data.get('coverage_details', {}).values():
                relevant_chunks.append(f"COVERAGE: {detail}")
        
        return relevant_chunks
    
    async def _rerank_chunks(self, query: str, chunks: List[str]) -> List[str]:
        """Re-rank chunks using semantic similarity"""
        if not chunks:
            return []
        
        try:
            # Use sentence transformer for re-ranking
            query_embedding = self.sentence_model.encode([query])
            chunk_embeddings = self.sentence_model.encode(chunks)
            
            similarities = cosine_similarity(query_embedding, chunk_embeddings)[0]
            
            # Sort by similarity
            ranked_indices = np.argsort(similarities)[::-1]
            return [chunks[i] for i in ranked_indices]
            
        except Exception as e:
            logger.error(f"Re-ranking failed: {e}")
            return chunks

# === Global Instances ===
doc_processor = AdvancedDocumentProcessor()
gpt4_qa = GPT4QASystem()
vector_search = AdvancedVectorSearch()

# === Main API Endpoints ===
@app.post("/hackrx/run", response_model=QueryResponse)
async def hackrx_run(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(None),
    documents: str = Form(None),
    questions: str = Form(...),
    db: AsyncSession = Depends(get_database)
):
    """Enhanced main endpoint with full tech stack integration"""
    start_time = time.time()
    
    try:
        # Parse questions
        questions_list = json.loads(questions) if isinstance(questions, str) else questions
        
        # Validate input
        if not file and not documents:
            raise HTTPException(status_code=400, detail="Provide either file upload or document URL")
        
        # Process file
        if documents:
            file_path, content = await download_file(documents)
        else:
            content = await file.read()
            file_path = await save_uploaded_file(file, content)
        
        # Extract document content
        content_text, structured_data = await doc_processor.process_document(
            file_path, file.filename if file else "document"
        )
        
        if not content_text.strip():
            raise HTTPException(status_code=400, detail="No extractable content found")
        
        # Generate content hash
        content_hash = hashlib.md5(content_text.encode()).hexdigest()
        
        # Store in PostgreSQL
        doc_record = await store_document(
            db, file.filename if file else "url_document", 
            content_text, content_hash, structured_data
        )
        
        # Process document chunks and store in Pinecone
        await process_and_store_chunks(
            content_text, structured_data, content_hash, doc_record.id
        )
        
        # Perform advanced search
        combined_query = " ".join(questions_list)
        context_chunks = await vector_search.hybrid_search(
            combined_query, content_hash, structured_data
        )
        
        # Generate answers using GPT-4
        return JSONResponse(content={"error": "message"}, status_code=400)  # ✅ Correct
