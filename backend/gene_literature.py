import logging
import os
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, TypeAdapter

from .literature_api import find_similar_papers, load_paper_metadata


logger = logging.getLogger(__name__)
GENE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$"
DOI_PATTERN = r"^10\.[0-9]{4,9}/\S+$"
DEFAULT_CURATED = Path(__file__).with_name("gene_literature_curated.json")
RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
MatchType = Literal["gene_id", "legacy_id", "symbol_or_alias"]


class VerifiedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: RequiredText
    doi: Annotated[str, StringConstraints(strip_whitespace=True, pattern=DOI_PATTERN)]
    pmid: str | None = Field(default=None, pattern=r"^[0-9]+$")
    study_context: RequiredText
    finding: RequiredText
    source_locator: RequiredText
    identity_source: HttpUrl
    reviewed_by: RequiredText
    reviewed_on: date


class CuratedGene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aliases: list[RequiredText] = Field(default_factory=list)
    legacy_ids: list[RequiredText] = Field(default_factory=list)
    identity_source: HttpUrl | None = None
    verified_evidence: list[VerifiedEvidence] = Field(default_factory=list)


class Candidate(BaseModel):
    source_record_key: str
    title: str
    doi: str | None
    pmid: str | None
    abstract: str
    match_type: Literal["gene_id", "legacy_id", "symbol_or_alias", "semantic"]
    matched_term: str | None = None
    matched_in: Literal["title", "abstract"] | None = None


class GeneLiterature(BaseModel):
    gene_id: str
    candidate_total: int
    candidates: list[Candidate]
    next_offset: int | None
    verified_evidence: list[VerifiedEvidence]
    semantic_candidates: list[Candidate]
    semantic_status: Literal["not_requested", "ok", "unavailable"]


@lru_cache(maxsize=1)
def load_curated():
    path = Path(os.getenv("MAIZE_GENE_LITERATURE_CURATED", str(DEFAULT_CURATED)))
    gene_id_type = Annotated[str, StringConstraints(pattern=GENE_ID_PATTERN)]
    return TypeAdapter(dict[gene_id_type, CuratedGene]).validate_json(
        path.read_text(encoding="utf-8-sig")
    )


def gene_terms(gene_id, gene, curated):
    aliases = gene.get("aliases")
    if isinstance(aliases, str):
        aliases = re.split(r"[,;|]", aliases)
    if not isinstance(aliases, (list, tuple)):
        aliases = ()

    terms = [(gene_id, "gene_id")]
    seen = {gene_id.casefold()}
    for kind, names in (
        ("legacy_id", curated.legacy_ids),
        ("symbol_or_alias", [gene.get("symbol"), *curated.aliases, *aliases]),
    ):
        for name in names:
            if not isinstance(name, str):
                continue
            name = name.strip()
            key = name.casefold()
            if (
                2 <= len(key) <= 100
                and any(char.isalnum() for char in key)
                and key not in seen
                and key not in {"na", "n/a", "none", "null", "unknown", "uncharacterized"}
            ):
                terms.append((name, kind))
                seen.add(key)
    return tuple(terms)


@lru_cache(maxsize=64)
def find_mentions(terms: tuple[tuple[str, MatchType], ...]):
    papers, abstracts = load_paper_metadata()
    patterns = [
        (term.casefold(), re.compile(rf"(?<!\w){re.escape(term.casefold())}(?!\w)"))
        for term, _ in terms
    ]
    hits = []
    for row, paper in enumerate(papers):
        title = paper["title"].casefold()
        abstract = abstracts.get(paper["source_record_key"], "").casefold()
        for rank, (key, pattern) in enumerate(patterns):
            if key in title and pattern.search(title):
                hits.append((rank, 0, row))
                break
            if key in abstract and pattern.search(abstract):
                hits.append((rank, 1, row))
                break
    # Rank by ID/alias priority, then by field and stable corpus row.
    return sorted(hits)


def paper_identifiers(paper):
    doi = (paper.get("doi") or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        doi = doi.removeprefix(prefix).strip()
    pmid = (paper.get("pmid") or "").strip()
    return (
        doi if re.fullmatch(DOI_PATTERN, doi) else None,
        pmid if re.fullmatch(r"[0-9]+", pmid) else None,
    )


def dedup_keys(source_record_key, doi, pmid):
    return {
        (kind, value)
        for kind, value in (("record", source_record_key), ("doi", doi), ("pmid", pmid))
        if value
    }


def gene_literature(gene_id, gene, offset, limit, include_semantic):
    try:
        curated = load_curated().get(gene_id, CuratedGene())
        terms = gene_terms(gene_id, gene, curated)
        hits = find_mentions(terms)
        papers, abstracts = load_paper_metadata()
    except (OSError, RuntimeError, KeyError, ValueError, AttributeError) as exc:
        logger.error("Gene literature resources unavailable: %s", type(exc).__name__)
        raise HTTPException(503, "Gene literature resources unavailable") from exc

    verified = []
    seen = set()
    for evidence in curated.verified_evidence:
        keys = dedup_keys(None, evidence.doi.lower(), evidence.pmid)
        if not seen.intersection(keys):
            verified.append(evidence)
        seen.update(keys)

    candidates = []
    total = 0
    for rank, field, row in hits:
        paper = papers[row]
        record_key = paper["source_record_key"]
        doi, pmid = paper_identifiers(paper)
        keys = dedup_keys(record_key, doi, pmid)
        duplicate = bool(seen.intersection(keys))
        seen.update(keys)
        if duplicate:
            continue
        if offset <= total < offset + limit:
            term, match_type = terms[rank]
            candidates.append(Candidate(
                source_record_key=record_key,
                title=paper["title"],
                doi=doi,
                pmid=pmid,
                abstract=abstracts.get(record_key, ""),
                match_type=match_type,
                matched_term=term,
                matched_in="title" if field == 0 else "abstract",
            ))
        total += 1

    semantic = []
    semantic_status = "not_requested"
    if include_semantic:
        try:
            query = " ".join(["maize", *(term for term, _ in terms)])[:500]
            for paper in find_similar_papers(query, 10, timeout=8):
                record_key = paper["source_record_key"]
                doi, pmid = paper_identifiers(paper)
                keys = dedup_keys(record_key, doi, pmid)
                duplicate = bool(seen.intersection(keys))
                seen.update(keys)
                if not duplicate:
                    semantic.append(Candidate(
                        source_record_key=record_key,
                        title=paper["title"],
                        doi=doi,
                        pmid=pmid,
                        abstract=paper["abstract"],
                        match_type="semantic",
                    ))
            semantic_status = "ok"
        except (HTTPException, OSError, RuntimeError, KeyError, ValueError) as exc:
            logger.warning("Gene literature semantic search failed: %s", type(exc).__name__)
            semantic = []
            semantic_status = "unavailable"

    return GeneLiterature(
        gene_id=gene_id,
        candidate_total=total,
        candidates=candidates,
        next_offset=offset + limit if offset + limit < total else None,
        verified_evidence=verified,
        semantic_candidates=semantic,
        semantic_status=semantic_status,
    )
