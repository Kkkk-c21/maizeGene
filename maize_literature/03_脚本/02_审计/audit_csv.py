import csv
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = PROJECT_ROOT / "01_数据" / "01_原始数据" / "maize_papers.csv"

# 允许读取较长的摘要字段
limit = sys.maxsize
while True:
    try:
        csv.field_size_limit(limit)
        break
    except OverflowError:
        limit //= 10

def normalize(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())

def find_column(fieldnames, candidates):
    normalized = {normalize(name): name for name in fieldnames}
    for candidate in candidates:
        if normalize(candidate) in normalized:
            return normalized[normalize(candidate)]
    return None

file_size = os.path.getsize(CSV_PATH)

with open(CSV_PATH, "r", encoding="utf-8-sig",
          errors="replace", newline="") as file:
    reader = csv.DictReader(file)
    fieldnames = reader.fieldnames or []

    doi_col = find_column(fieldnames, ["doi"])
    title_col = find_column(fieldnames, ["title", "article_title"])
    abstract_col = find_column(
        fieldnames,
        ["abstract", "abstractText", "abstract_text"]
    )

    total = 0
    with_doi = 0
    with_title = 0
    with_abstract = 0

    for row in reader:
        total += 1

        if doi_col and (row.get(doi_col) or "").strip():
            with_doi += 1
        if title_col and (row.get(title_col) or "").strip():
            with_title += 1
        if abstract_col and (row.get(abstract_col) or "").strip():
            with_abstract += 1

        if total % 100000 == 0:
            print(f"已检查 {total:,} 条记录……")

def coverage(count):
    return f"{count:,}（{count / total:.2%}）" if total else "0"

print("\n审计完成")
print(f"文件大小：{file_size / 1024**2:,.2f} MB")
print(f"数据记录总数：{total:,}")
print(f"有 DOI：{coverage(with_doi)}")
print(f"有标题：{coverage(with_title)}")
print(f"有摘要：{coverage(with_abstract)}")
print(f"识别到的 DOI 列：{doi_col or '未找到'}")
print(f"识别到的标题列：{title_col or '未找到'}")
print(f"识别到的摘要列：{abstract_col or '未找到'}")
print("CSV 字段：", ", ".join(fieldnames))
