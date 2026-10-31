import json
import os
import urllib.request
from pathlib import Path

from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any
import logging

from dotenv import load_dotenv
from neo4j import GraphDatabase, READ_ACCESS, unit_of_work
from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable, SessionExpired
from fastapi import FastAPI, HTTPException, Path as ApiPath, Request
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.neo4j_driver = None
    app.state.neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")
    app.state.neo4j_error = "缺少 Neo4j 凭据：请在项目 .env 设置 NEO4J_AUTH=用户名/密码"
    auth = os.getenv("NEO4J_AUTH", "")
    username, _, password = auth.partition("/")
    username = os.getenv("NEO4J_USER", username or "neo4j")
    password = os.getenv("NEO4J_PASSWORD", password)
    if username and password:
        try:
            app.state.neo4j_driver = GraphDatabase.driver(
                os.getenv("NEO4J_URI", "bolt://127.0.0.1:7688"),
                auth=(username, password),
                connection_timeout=5,
                connection_acquisition_timeout=10,
                max_transaction_retry_time=5,
                max_connection_pool_size=5,
            )
        except (ValueError, Neo4jError):
            app.state.neo4j_error = "Neo4j 连接配置无效，请检查 NEO4J_URI 和认证设置"
    try:
        yield
    finally:
        if app.state.neo4j_driver is not None:
            app.state.neo4j_driver.close()


app = FastAPI(title="MaizeGene API", lifespan=lifespan)


class GeneDetail(BaseModel):
    gene: dict[str, Any]
    go: list[dict[str, Any]]
    protein_domains: list[dict[str, Any]]
    transcripts: list[dict[str, Any]]
    counts: dict[str, int]


# 分别聚合三类关联，避免 GO × Domain × Transcript 造成笛卡尔积。
GENE_DETAIL_QUERY = """
MATCH (g:Gene {gene_id: $gene_id})
CALL (g) {
    OPTIONAL MATCH (g)-[r:HAS_FUNCTION]->(n:GO)
    WITH n, r ORDER BY n.go_id
    RETURN collect(DISTINCT n{.*, relationship: {
        type: type(r), properties: properties(r)
    }}) AS go
}
CALL (g) {
    OPTIONAL MATCH (g)-[r:HAS_DOMAIN]->(n:ProteinDomain)
    WITH n, r ORDER BY n.domain_id
    RETURN collect(DISTINCT n{.*, relationship: {
        type: type(r), properties: properties(r)
    }}) AS protein_domains
}
CALL (g) {
    OPTIONAL MATCH (g)-[r:HAS_TRANSCRIPT]->(n:Transcript)
    WITH n, r ORDER BY n.transcript_id
    RETURN collect(DISTINCT n{.*, relationship: {
        type: type(r), properties: properties(r)
    }}) AS transcripts
}
RETURN properties(g) AS gene, go, protein_domains, transcripts
"""


def read_neo4j(request: Request, operation, *args):
    driver = request.app.state.neo4j_driver
    if driver is None:
        raise HTTPException(503, request.app.state.neo4j_error)
    try:
        with driver.session(
            database=request.app.state.neo4j_database,
            default_access_mode=READ_ACCESS,
        ) as session:
            return session.execute_read(operation, *args)
    except AuthError as exc:
        raise HTTPException(503, "Neo4j 认证失败，请检查项目 .env 中的凭据") from exc
    except (ServiceUnavailable, SessionExpired, OSError) as exc:
        raise HTTPException(503, "Neo4j 暂时不可用，请检查 127.0.0.1:7688 的数据库服务") from exc
    except Neo4jError as exc:
        logger.error("Neo4j read failed: %s", type(exc).__name__)
        raise HTTPException(503, "Neo4j 查询失败，请检查数据库名称及服务日志") from exc


@unit_of_work(timeout=10)
def check_database(tx):
    return tx.run("RETURN 1 AS ok").single()["ok"] == 1


@app.get("/health", tags=["Gene details"])
def health(request: Request):
    read_neo4j(request, check_database)
    return {"status": "ok", "neo4j": "connected"}


@unit_of_work(timeout=10)
def fetch_gene(tx, gene_id):
    record = tx.run(GENE_DETAIL_QUERY, gene_id=gene_id).single()
    return record.data() if record is not None else None


@app.get(
    "/genes/{gene_id}",
    response_model=GeneDetail,
    tags=["Gene details"],
    summary="按基因 ID 查询 Gene、GO、ProteinDomain 和 Transcript",
    responses={404: {"description": "基因不存在"}, 503: {"description": "数据库不可用"}},
)
def gene_detail(
    request: Request,
    gene_id: str = ApiPath(
        ..., min_length=1, max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$",
        examples=["Zm00001eb081920"],
    ),
):
    result = read_neo4j(request, fetch_gene, gene_id)
    if result is None:
        raise HTTPException(404, "未找到该基因 ID")
    result["counts"] = {
        key: len(result[key]) for key in ("go", "protein_domains", "transcripts")
    }
    return result


DATA_DIR = (
    Path(__file__).resolve().parents[1]
    / "embeddings"
    / "maize-gene-emb-768-full"
)
EMBEDDING_API_URL = os.getenv(
    "EMBEDDING_API_URL",
    "http://127.0.0.1:18084/v1/embeddings",
)

# ID 列表很小；向量和 numpy 仅在调用 /search 时加载。
gene_ids = (DATA_DIR / "maize_gene_ids.txt").read_text(
    encoding="utf-8"
).splitlines() if (DATA_DIR / "maize_gene_ids.txt").exists() else []


@lru_cache(maxsize=1)
def load_gene_vectors():
    import numpy as np

    try:
        vectors = np.load(DATA_DIR / "maize_gene_emb.npy").astype(np.float32)
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "基因向量文件不可用") from exc
    if vectors.ndim != 2 or len(gene_ids) != vectors.shape[0]:
        raise HTTPException(503, "基因 ID 与向量数据不一致")
    vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)
    return vectors


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


@app.get("/")
def home():
    return {
        "project": "MaizeGene",
        "status": "running",
        "gene_count": len(gene_ids),
    }


@app.post("/search")
def search_genes(request: SearchRequest):
    import numpy as np

    gene_vectors = load_gene_vectors()
    # 请求本地Embedding服务生成查询向量
    payload = json.dumps({
        "input": request.query,
        "model": "embeddinggemma-300m",
    }).encode("utf-8")

    embedding_request = urllib.request.Request(
        EMBEDDING_API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            embedding_request, timeout=60
        ) as response:
            result = json.load(response)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="本地Embedding服务不可用",
        ) from exc

    query_vector = np.asarray(
        result["data"][0]["embedding"], dtype=np.float32
    )

    if query_vector.shape != (gene_vectors.shape[1],):
        raise HTTPException(
            status_code=500,
            detail="查询向量维度与基因向量不一致",
        )

    query_norm = np.linalg.norm(query_vector)
    if not np.isfinite(query_norm) or query_norm <= 0:
        raise HTTPException(
            status_code=500,
            detail="查询向量无效",
        )

    query_vector /= query_norm

    # 余弦相似度排序
    scores = gene_vectors @ query_vector
    top_indices = np.argsort(-scores)[:request.top_k]

    return {
        "query": request.query,
        "total_genes": len(gene_ids),
        "results": [
            {
                "gene_id": gene_ids[i],
                "similarity": round(float(scores[i]), 6),
            }
            for i in top_indices
        ],
    }
from pathlib import Path
from fastapi.staticfiles import StaticFiles

WEBSITE_DIR = Path(__file__).resolve().parents[1] / "website"

app.mount(
    "/site",
    StaticFiles(directory=WEBSITE_DIR, html=True),
    name="site",
)