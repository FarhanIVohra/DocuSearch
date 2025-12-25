import os
import re
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .index.indexer import build_index, extract_text_from_docx
from .index.preprocess import preprocess
from .index.pdf_reader import extract_text_from_pdf_with_status, PDFExtractionError
from .service.search_service import SearchService

DOCS_DIR_DEFAULT = os.path.join(os.path.dirname(__file__), "data", "documents")
CACHE_CAPACITY_DEFAULT = int(os.environ.get("CACHE_CAPACITY", "256"))

app = FastAPI(title="Interactive Document Search Engine API", version="0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INDEX: Dict[str, Any] = build_index(os.environ.get("DOCS_DIR", DOCS_DIR_DEFAULT))
SERVICE = SearchService(INDEX, cache_capacity=CACHE_CAPACITY_DEFAULT)

UPLOADED_DOCUMENT: Optional[str] = None
UPLOADED_DOCUMENT_CACHE: Dict[str, List[int]] = {}


def extract_snippet(text: str, query: str, max_length: int = 200) -> str:
    """Extract a relevant snippet from text containing query terms."""
    text_lower = text.lower()
    query_terms = [q.lower().strip() for q in query.split() if q.strip()]
    
    if not query_terms:
        return text[:max_length] + "..." if len(text) > max_length else text
    
    best_pos = len(text)
    for term in query_terms:
        pos = text_lower.find(term)
        if pos != -1 and pos < best_pos:
            best_pos = pos
    
    start = max(0, best_pos - 50)
    end = min(len(text), best_pos + max_length - 50)
    snippet = text[start:end]
    
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    
    return snippet


def highlight_terms(text: str, query: str) -> str:
    """Highlight query terms in text (simple version, frontend will handle actual highlighting)."""
    return text


class SearchResultItem(BaseModel):
    id: str
    title: str
    url: str
    snippet: str
    score: float
    type: str = "article"
    year: Optional[int] = None


class FrontendSearchResponse(BaseModel):
    results: List[SearchResultItem]
    totalResults: int
    page: int
    executionTime: float


class SearchResponse(BaseModel):
    results: List[List[float]] | List[List[int]] | List  # (doc_id, score) tuples serialized as lists
    elapsed_ms: float
    cached: bool


@app.get("/api/search", response_model=FrontendSearchResponse)
async def api_search(
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Results per page"),
    filter: Optional[str] = Query(None, description="Filter type: article, pdf, recent")
):
    """Frontend-compatible search endpoint with pagination and result transformation."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query 'q' must be non-empty")
    
    search_result = SERVICE.search(q)
    
    all_results: List[tuple] = [(int(r[0]), float(r[1])) for r in search_result["results"]]
    
    total_results = len(all_results)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_results = all_results[start_idx:end_idx]
    
    transformed_results = []
    doc_id_map = INDEX["doc_id_map"]
    forward_index = INDEX["forward_index"]
    
    for doc_id, score in paginated_results:
        doc_text = forward_index.get(doc_id, "")
        file_path = doc_id_map.get(doc_id, "")
        
        lines = doc_text.split("\n")
        title = lines[0].strip() if lines else os.path.basename(file_path)
        if not title:
            title = f"Document {doc_id}"
        
        url = f"/document/{doc_id}" if file_path else f"#doc-{doc_id}"
        
        snippet = extract_snippet(doc_text, q)
        
        if file_path.endswith(".pdf"):
            doc_type = "pdf"
        elif file_path.endswith(".docx") or file_path.endswith(".doc"):
            doc_type = "doc"
        else:
            doc_type = "article"
        
        transformed_results.append(SearchResultItem(
            id=str(doc_id),
            title=title,
            url=url,
            snippet=snippet,
            score=score,
            type=doc_type,
            year=None
        ))
    
    return FrontendSearchResponse(
        results=transformed_results,
        totalResults=total_results,
        page=page,
        executionTime=search_result["elapsed_ms"]
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "index_size": INDEX.get("N", 0)}


@app.get("/api/suggest")
async def api_suggest(q: str = Query("", min_length=0)):
    """Autocomplete suggestions endpoint (placeholder for now)."""
    return {"suggestions": []}


@app.get("/stats")
async def http_stats():
    """Service statistics endpoint."""
    return SERVICE.stats()


class UploadResponse(BaseModel):
    status: str
    doc_length: int
    unique_terms: int
    text: Optional[str] = None
    extraction_status: Optional[str] = None


class MatchItem(BaseModel):
    term: str
    positions: List[int]


class SearchResponseModel(BaseModel):
    query: str
    matches: List[MatchItem]
    total_matches: int
    time_ms: float
    cache: str


@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a .txt, .pdf or .docx document for interactive search.

    Supported formats:
      - .txt: Plain text files (UTF-8 preferred; attempts common fallbacks)
      - .pdf: Simple text-based PDFs only (no scanned/image PDFs)
      - .docx: Microsoft Word documents (OpenXML)
      - .doc: Legacy Word; may fail (suggest converting to .docx if it does)

    The document is stored in memory and can be searched via /search endpoint.
    All formats go through the SAME indexing pipeline (preprocess → tokenize → index).
    """
    global UPLOADED_DOCUMENT, UPLOADED_DOCUMENT_CACHE
    
    filename = file.filename or "unknown"
    file_ext = filename.lower().split('.')[-1]
    
    if file_ext not in ['txt', 'pdf', 'docx', 'doc']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{file_ext}. Supported: .txt, .pdf, .docx, .doc"
        )
    
    try:
        content = await file.read()
        
        if file_ext == 'txt':
            text = None
            for enc in ('utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin-1'):
                try:
                    text = content.decode(enc)
                    break
                except Exception:
                    continue
            if text is None:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to decode text file. Please ensure it is saved with UTF-8 encoding."
                )
            extraction_status = "Plain text detected — loaded"
        elif file_ext == 'pdf':
            try:
                text, extraction_status = extract_text_from_pdf_with_status(content)
            except PDFExtractionError as e:
                error_msg = str(e)
                error_msg += "\n\nTip: If this PDF is scanned, OCR is required (install Tesseract). If it uses embedded fonts, OCR may still be required."
                raise HTTPException(
                    status_code=400,
                    detail=error_msg
                )
        else:
            try:
                text = extract_text_from_docx(content)
                extraction_status = "Text-based document detected — extracted text"
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to extract text from this Word file. Please upload a .docx (not legacy .doc) or export to PDF."
                )
        
        if not text.strip():
            raise HTTPException(
                status_code=400,
                detail="Document is empty or contains no extractable text."
            )
        
        UPLOADED_DOCUMENT = text
        UPLOADED_DOCUMENT_CACHE = {}
        
        tokens = preprocess(text)
        unique_terms = len(set(tokens))
        
        return UploadResponse(
            status="loaded",
            doc_length=len(text),
            unique_terms=unique_terms,
            text=text,
            extraction_status=extraction_status
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )



def find_term_positions(text: str, term: str) -> List[int]:
    """
    Find all character positions where a term appears in text.
    Case-insensitive substring search.
    """
    positions = []
    
    if not term:
        return positions

    pattern = re.escape(term)
    for match in re.finditer(pattern, text, re.IGNORECASE):
        positions.append(match.start())
    
    return positions


@app.get("/search", response_model=SearchResponseModel)
async def search_document(q: str = Query(..., min_length=1)):
    """
    Search within the uploaded document.
    Returns matches with character positions for highlighting.
    Searches for exact query terms (not preprocessed) to find all occurrences.
    """
    global UPLOADED_DOCUMENT, UPLOADED_DOCUMENT_CACHE
    
    if UPLOADED_DOCUMENT is None:
        raise HTTPException(status_code=400, detail="No document uploaded. Please upload a document first.")
    
    start_time = time.perf_counter()
    
    cache_key = q.lower().strip()
    if cache_key in UPLOADED_DOCUMENT_CACHE:
        cached_matches = UPLOADED_DOCUMENT_CACHE[cache_key]
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        return SearchResponseModel(
            query=q,
            matches=cached_matches,
            total_matches=sum(len(m.positions) for m in cached_matches),
            time_ms=elapsed_ms,
            cache="HIT"
        )
    
    query_words = q.strip().split()
    matches = []
    seen_terms = set()
    
    for word in query_words:
        if len(word) > 0 and word.lower() not in seen_terms:
            seen_terms.add(word.lower())
            positions = find_term_positions(UPLOADED_DOCUMENT, word)
            if positions:
                matches.append(MatchItem(term=word, positions=positions))
    
    UPLOADED_DOCUMENT_CACHE[cache_key] = matches
    
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    
    return SearchResponseModel(
        query=q,
        matches=matches,
        total_matches=sum(len(m.positions) for m in matches),
        time_ms=elapsed_ms,
        cache="MISS"
    )
