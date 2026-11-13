"""NCBI BLAST proxy. Single-process rate limiter and bounded in-memory jobs."""
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/blast", tags=["BLAST"])
_lock = threading.Lock()
_last = 0.0
_jobs = {}

class Submission(BaseModel):
    sequence: str = Field(min_length=20, max_length=110000)
    program: Literal["blastn", "blastp"] = "blastn"

def ncbi(parameters):
    global _last
    with _lock:
        now = time.monotonic()
        if now - _last < 10:
            raise HTTPException(429, "NCBI 请求间隔至少 10 秒，请稍后重试")
        _last = now
    parameters.update(tool="maizeGene")
    if os.getenv("NCBI_EMAIL"):
        parameters["email"] = os.environ["NCBI_EMAIL"]
    request = urllib.request.Request("https://blast.ncbi.nlm.nih.gov/Blast.cgi",
        data=urllib.parse.urlencode(parameters).encode(), headers={"User-Agent": "maizeGene/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read(20_000_000).decode("utf-8")
    except (OSError, ValueError) as exc:
        raise HTTPException(502, "NCBI 暂时不可用，请稍后重试") from exc

@router.get("/sequence/{gene_id}")
def sequence_provider(gene_id: str):
    """Integration contract: return sequence, sequence_id, molecule, assembly, annotation_release."""
    raise HTTPException(501, "基因序列接口尚未接入，请粘贴已确认来源的玉米序列")

@router.post("/jobs")
def submit(body: Submission):
    lines = body.sequence.strip().splitlines()
    if lines and lines[0].startswith(">"):
        lines = lines[1:]
    sequence = re.sub(r"\s+", "", "".join(lines)).upper()
    alphabet = r"[ACGTRYSWKMBDHVN]+" if body.program == "blastn" else r"[ACDEFGHIKLMNPQRSTVWYBXZJUO]+"
    if not 20 <= len(sequence) <= 100000 or not re.fullmatch(alphabet, sequence):
        raise HTTPException(422, "请输入单条有效序列（20–100000 字符），并选择匹配的程序")
    now = time.monotonic()
    with _lock:
        for rid in list(_jobs):
            if now - _jobs[rid]["created"] > 86400:
                del _jobs[rid]
        if len(_jobs) >= 100:
            raise HTTPException(429, "任务数已达上限，请稍后再试")
    database = "nt" if body.program == "blastn" else "nr"
    text = ncbi(dict(CMD="Put", PROGRAM=body.program, DATABASE=database,
        QUERY=sequence, ENTREZ_QUERY="txid4577[ORGN]", HITLIST_SIZE=20, EXPECT="1e-5"))
    match = re.search(r"RID\s*=\s*([A-Z0-9-]+)", text)
    if not match:
        raise HTTPException(502, "NCBI 未返回任务 ID，请检查输入或稍后重试")
    rid = match[1]
    with _lock:
        _jobs[rid] = dict(created=now, checked=time.monotonic(), program=body.program,
            query_length=len(sequence), database=database + " / Zea mays (taxid 4577)")
    return dict(rid=rid, status="WAITING", poll_after=60)

@router.get("/jobs/{rid}")
def result(rid: str):
    with _lock:
        job = _jobs.get(rid)
        if job is None:
            raise HTTPException(404, "任务不存在或服务已重启，请重新提交")
        if "result" in job:
            return job["result"]
        if time.monotonic() - job["checked"] < 60:
            return dict(rid=rid, status="WAITING", poll_after=60)
        job["checked"] = time.monotonic()
    text = ncbi(dict(CMD="Get", RID=rid, FORMAT_TYPE="JSON2_S"))
    status = re.search(r"Status\s*=\s*(\w+)", text)
    if status:
        return dict(rid=rid, status=status[1], poll_after=60)
    try:
        report = json.loads(text)["BlastOutput2"][0]["report"]
        search = report["results"]["search"]
        if search.get("error"):
            raise ValueError("NCBI search error")
        hits = []
        for hit in search.get("hits", []):
            segments = []
            for hsp in hit.get("hsps", []):
                segments.append(dict(start=min(hsp["query_from"], hsp["query_to"]),
                    end=max(hsp["query_from"], hsp["query_to"]),
                    identity=round(100*hsp["identity"]/hsp["align_len"], 2),
                    evalue=str(hsp["evalue"]), bitscore=hsp["bit_score"]))
            description = hit["description"][0]
            hits.append(dict(name=description.get("accession", description.get("id", "hit")), segments=segments))
        output = dict(rid=rid, status="READY", hits=hits, query_length=search["query_len"],
            program=job["program"], database=job["database"], query_id=search.get("query_title", "Query"))
    except (KeyError, ValueError, TypeError, IndexError) as exc:
        raise HTTPException(502, "NCBI 尚未返回有效结果，可稍后重试") from exc
    with _lock:
        job["result"] = output
    return output
