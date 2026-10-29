import csv
import heapq
import math
import random
import re
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_CSV = PROJECT_ROOT / "01_数据" / "01_原始数据" / "maize_papers.csv"
OUTPUT_CSV = PROJECT_ROOT / "02_抽样与复核" / "01_抽样CSV" / "screening_sample_500.csv"
SAMPLE_SIZE = 500
RANDOM_SEED = 20261027


limit = sys.maxsize
while True:
    try:
        csv.field_size_limit(limit)
        break
    except OverflowError:
        limit //= 10


MAIZE_PATTERN = re.compile(
    r"\b(?:maize|corn|zea\s+mays|z\.?\s*mays)\b",
    re.IGNORECASE,
)

GENE_PATTERN = re.compile(
    r"\b(?:gene|genes|genetic|genetics|genome|genomic|"
    r"transcriptome|transcriptomic|expression|qtl|qtls|gwas|"
    r"snp|snps|allele|alleles|mutation|mutant|locus|loci|"
    r"chromosome|chromosomal|protein|proteomic|pathway|"
    r"transcription\s+factor|mirna|methylation|epigenetic)\b",
    re.IGNORECASE,
)


def year_bucket(value):
    try:
        year = int(str(value).strip()[:4])
    except (TypeError, ValueError):
        return "year_unknown"

    if year < 1990:
        return "before_1990"
    if year < 2000:
        return "1990_1999"
    if year < 2010:
        return "2000_2009"
    if year < 2020:
        return "2010_2019"
    return "2020_plus"


def classify_text(row):
    title = row.get("title") or ""
    abstract = row.get("abstract") or ""
    combined = f"{title} {abstract}"

    title_maize = bool(MAIZE_PATTERN.search(title))
    abstract_maize = bool(MAIZE_PATTERN.search(abstract))
    gene_terms = bool(GENE_PATTERN.search(combined))

    if title_maize and gene_terms:
        bucket = "title_maize_with_gene_terms"
    elif title_maize:
        bucket = "title_maize_without_gene_terms"
    elif abstract_maize and gene_terms:
        bucket = "abstract_maize_with_gene_terms"
    elif abstract_maize:
        bucket = "abstract_maize_without_gene_terms"
    elif gene_terms:
        bucket = "no_explicit_maize_with_gene_terms"
    else:
        bucket = "no_explicit_maize_without_gene_terms"

    return bucket, "yes" if abstract.strip() else "no"


def make_stratum(row):
    bucket, abstract_present = classify_text(row)
    source = (row.get("source") or "source_unknown").strip().upper()
    return source, bucket, abstract_present, year_bucket(row.get("year"))


def open_input():
    return open(
        INPUT_CSV,
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline="",
    )


print("第一遍：统计分层规模……")
stratum_counts = Counter()
total = 0

with open_input() as file:
    reader = csv.DictReader(file)
    input_fields = reader.fieldnames or []

    for row in reader:
        total += 1
        stratum_counts[make_stratum(row)] += 1

        if total % 100000 == 0:
            print(f"已统计 {total:,} 条记录……")

if not total:
    raise RuntimeError("输入CSV中没有数据记录。")

sample_size = min(SAMPLE_SIZE, total)
random.seed(RANDOM_SEED)
reservoir = []

print("第二遍：进行可复现的加权分层抽样……")

with open_input() as file:
    reader = csv.DictReader(file)

    for row_number, row in enumerate(reader, start=2):
        stratum = make_stratum(row)

        # 每条记录的权重与所在层规模的平方根成反比。
        # 这样能保留大类，同时提高小来源、早期年份和少见文本类型的入样机会。
        weight = 1.0 / math.sqrt(stratum_counts[stratum])
        priority = math.log(max(random.random(), 1e-15)) / weight

        bucket, abstract_present = classify_text(row)
        sampled_row = dict(row)
        sampled_row["sampling_bucket"] = bucket
        sampled_row["year_bucket"] = year_bucket(row.get("year"))
        sampled_row["abstract_present"] = abstract_present
        sampled_row["source_record_key"] = (
            f"{(row.get('source') or '').strip().upper()}:"
            f"{(row.get('record_id') or '').strip()}"
        )

        item = (priority, row_number, sampled_row)

        if len(reservoir) < sample_size:
            heapq.heappush(reservoir, item)
        elif priority > reservoir[0][0]:
            heapq.heapreplace(reservoir, item)

        if row_number % 100000 == 2:
            print(f"已抽样扫描 {row_number - 1:,} 条记录……")

selected = [item[2] for item in reservoir]
random.shuffle(selected)

annotation_fields = [
    "primary_label",
    "secondary_labels",
    "maize_gene_or_locus",
    "evidence_type",
    "evidence_sentence_or_note",
    "decision_reason",
    "reviewer",
    "review_date",
]

metadata_fields = [
    "sample_id",
    "sampling_bucket",
    "year_bucket",
    "abstract_present",
    "source_record_key",
]

output_fields = metadata_fields + input_fields + annotation_fields

with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=output_fields, extrasaction="ignore")
    writer.writeheader()

    for index, row in enumerate(selected, start=1):
        row["sample_id"] = f"S{index:04d}"
        for field in annotation_fields:
            row[field] = ""
        writer.writerow(row)

bucket_counts = Counter(row["sampling_bucket"] for row in selected)
source_counts = Counter((row.get("source") or "unknown") for row in selected)

print("\n抽样完成")
print(f"原始记录：{total:,}")
print(f"抽样记录：{len(selected):,}")
print(f"输出文件：{OUTPUT_CSV}")

print("\n文本分层：")
for name, count in bucket_counts.most_common():
    print(f"  {name}: {count}")

print("\n来源分布：")
for name, count in source_counts.most_common():
    print(f"  {name}: {count}")

print("\n标注代码：A直接功能；B表型性状；C关联；D计算；E资源；R综述；X排除；U不确定")
