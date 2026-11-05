import csv
import json
import os
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from threading import Lock

import faiss
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/literature", tags=["Literature"])

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = Path(os.getenv(
    "MAIZE_LITERATURE_INDEX",
    str(ROOT / "embeddings/literature-full-v1/faiss")
))
PAPERS_CSV = Path(os.getenv(
    "MAIZE_LITERATURE_CSV",
    str(ROOT / "maize_literature/01_数据/02_清洗数据/delivery_v1_0/papers_master.csv")
))
EMBEDDING_URL = os.getenv(
    "MAIZE_EMBEDDING_URL",
    "http://127.0.0.1:18084/v1/embeddings"
)
EMBEDDING_MODEL = os.getenv(
    "MAIZE_EMBEDDING_MODEL",
    "embeddinggemma-300m"
)
_metadata_lock = Lock()


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=50)


@lru_cache(maxsize=1)
def _load_paper_metadata():
    with (INDEX_DIR / "papers_index.csv").open(
        encoding="utf-8-sig", newline=""
    ) as f:
        reader = csv.DictReader(f)
        required = {"row_id", "source_record_key", "title", "doi", "pmid"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError("Invalid literature index metadata columns")
        papers = list(reader)

    abstracts = {}
    with PAPERS_CSV.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"source_record_key", "abstract", "screen_decision", "is_duplicate_representative"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError("Invalid literature master CSV columns")
        for paper in reader:
            if paper["is_duplicate_representative"].strip() != "1":
                continue
            if paper["screen_decision"].strip() != "\u4fdd\u7559":
                continue
            abstracts[paper["source_record_key"]] = paper["abstract"]

    return papers, abstracts


def load_paper_metadata():
    # Share one metadata snapshot across both APIs, including on a cold start.
    with _metadata_lock:
        return _load_paper_metadata()


@lru_cache(maxsize=1)
def load_resources():
    papers, abstracts = load_paper_metadata()
    index = faiss.read_index(str(INDEX_DIR / "index.faiss"))
    if index.ntotal != len(papers) or index.d != 768:
        raise RuntimeError("FAISS index and metadata mismatch")
    return index, papers, abstracts


def encode_query(query, *, timeout=60):
    payload = json.dumps({
        "model": EMBEDDING_MODEL,
        "input": query
    }).encode("utf-8")

    request = urllib.request.Request(
        EMBEDDING_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable"
        ) from exc

    try:
        vector = np.asarray(
            data["data"][0]["embedding"], dtype=np.float32
        ).reshape(1, -1)
        if vector.shape != (1, 768) or not np.isfinite(vector).all():
            raise ValueError("Invalid embedding")
        if np.linalg.norm(vector) == 0:
            raise ValueError("Zero embedding")
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Invalid embedding response"
        ) from exc

    faiss.normalize_L2(vector)
    return vector


@router.post("/search")
def search_literature(request: SearchRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Empty query")

    results = find_similar_papers(query, request.top_k)
    return {
        "query": query,
        "total": len(results),
        "papers": results
    }


def find_similar_papers(query, top_k, *, timeout=60):
    try:
        index, papers, abstracts = load_resources()
    except (OSError, RuntimeError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Literature index unavailable"
        ) from exc

    vector = encode_query(query, timeout=timeout)
    scores, indices = index.search(vector, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue

        paper = papers[int(idx)]
        if int(paper["row_id"]) != int(idx):
            raise HTTPException(
                status_code=500,
                detail="Literature index mapping error"
            )

        results.append({
            "source_record_key": paper["source_record_key"],
            "title": paper["title"],
            "abstract": abstracts.get(paper["source_record_key"], ""),
            "doi": paper["doi"],
            "pmid": paper["pmid"],
            "score": float(score)
        })

    return results
