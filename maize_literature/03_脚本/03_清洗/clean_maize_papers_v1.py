import csv
import hashlib
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT = PROJECT_ROOT / "01_数据" / "01_原始数据" / "maize_papers.csv"
CLEAN_DIR = PROJECT_ROOT / "01_数据" / "02_清洗数据"
OUTPUT = CLEAN_DIR / "maize_papers_cleaned_v1.csv"
PART = CLEAN_DIR / "maize_papers_cleaned_v1.csv.part"
REPORT = CLEAN_DIR / "maize_papers_cleaned_v1_report.json"

INPUT_FIELDS = [
    "doi", "title", "abstract", "pmid", "year", "source", "record_id", "retrieved_at"
]
OUTPUT_FIELDS = INPUT_FIELDS + ["source_record_key", "cleaning_flags"]
STRICT_TAG = re.compile(r"</?(?:i|b|em|italic|sub|sup)\b[^>]*>", re.I)
DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)


def enable_large_fields():
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


def clean_text(value):
    value = value or ""
    decoded = html.unescape(value)
    strict_tags = STRICT_TAG.findall(decoded)
    cleaned = STRICT_TAG.sub(" ", decoded)
    cleaned = " ".join(cleaned.split())
    return cleaned, len(strict_tags)


def normalize_doi(value):
    value = (value or "").strip()
    return DOI_PREFIX.sub("", value).strip().lower()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    enable_large_fields()
    for path in (OUTPUT, PART, REPORT):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    if not INPUT.exists():
        raise FileNotFoundError(INPUT)

    input_hash = sha256(INPUT)
    counts = Counter()
    source_counts = Counter()
    total = 0

    with INPUT.open("r", encoding="utf-8-sig", errors="replace", newline="") as source_handle, \
            PART.open("x", encoding="utf-8-sig", newline="") as output_handle:
        reader = csv.DictReader(source_handle)
        if (reader.fieldnames or []) != INPUT_FIELDS:
            raise ValueError(f"Unexpected fields: {reader.fieldnames}")
        writer = csv.DictWriter(output_handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()

        for row in reader:
            total += 1
            flags = []

            doi = normalize_doi(row.get("doi"))
            title_raw = row.get("title") or ""
            abstract_raw = row.get("abstract") or ""
            title, title_tag_count = clean_text(title_raw)
            abstract, abstract_tag_count = clean_text(abstract_raw)
            pmid = (row.get("pmid") or "").strip()
            year = (row.get("year") or "").strip()
            source = (row.get("source") or "").strip().upper()
            record_id = (row.get("record_id") or "").strip()
            retrieved_at = (row.get("retrieved_at") or "").strip()

            if not doi:
                flags.append("missing_doi")
            if not title:
                flags.append("missing_title")
            if not abstract:
                flags.append("missing_abstract")
            if not pmid:
                flags.append("missing_pmid")
            if not year:
                flags.append("missing_year")
            elif year == "2027":
                flags.append("year_2027_review")
            if title_tag_count:
                flags.append("title_format_tags_removed")
                counts["rows_title_format_tags_removed"] += 1
                counts["title_format_tags_removed"] += title_tag_count
            if abstract_tag_count:
                flags.append("abstract_format_tags_removed")
                counts["rows_abstract_format_tags_removed"] += 1
                counts["abstract_format_tags_removed"] += abstract_tag_count
            replacement_count = title.count("\ufffd") + abstract.count("\ufffd")
            if replacement_count:
                flags.append("encoding_replacement_character")
                counts["rows_encoding_replacement_character"] += 1
                counts["encoding_replacement_characters"] += replacement_count

            for flag in flags:
                counts[flag] += 1
            source_counts[source] += 1

            writer.writerow({
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "pmid": pmid,
                "year": year,
                "source": source,
                "record_id": record_id,
                "retrieved_at": retrieved_at,
                "source_record_key": f"{source}:{record_id}",
                "cleaning_flags": ";".join(flags),
            })

    PART.rename(OUTPUT)
    report = {
        "input": str(INPUT),
        "input_sha256": input_hash,
        "output": str(OUTPUT),
        "output_sha256": sha256(OUTPUT),
        "rows_written": total,
        "output_fields": OUTPUT_FIELDS,
        "source_counts": dict(source_counts.most_common()),
        "flag_and_transformation_counts": dict(counts.most_common()),
        "records_deleted": 0,
        "deduplication_applied": False,
        "relevance_filter_applied": False,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
