import csv
import os
import re
import sqlite3
import sys
import tempfile
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = PROJECT_ROOT / "01_数据" / "01_原始数据" / "maize_papers.csv"

limit = sys.maxsize
while True:
    try:
        csv.field_size_limit(limit)
        break
    except OverflowError:
        limit //= 10

def normalize_doi(value):
    value = (value or "").strip().lower()
    value = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", value)
    return value.strip()

def normalize_title(value):
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return "".join(char for char in value if char.isalnum())

folder = os.path.dirname(CSV_PATH)
handle, db_path = tempfile.mkstemp(
    prefix="maize_duplicate_audit_",
    suffix=".sqlite",
    dir=folder
)
os.close(handle)

connection = sqlite3.connect(db_path)

try:
    connection.executescript("""
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        PRAGMA temp_store=FILE;
        PRAGMA cache_size=-20000;

        CREATE TABLE doi_counts (
            value TEXT PRIMARY KEY,
            count INTEGER NOT NULL
        );

        CREATE TABLE title_counts (
            value TEXT PRIMARY KEY,
            count INTEGER NOT NULL
        );
    """)

    doi_sql = """
        INSERT INTO doi_counts(value, count) VALUES (?, 1)
        ON CONFLICT(value) DO UPDATE SET count = count + 1
    """

    title_sql = """
        INSERT INTO title_counts(value, count) VALUES (?, 1)
        ON CONFLICT(value) DO UPDATE SET count = count + 1
    """

    total = 0

    with open(CSV_PATH, "r", encoding="utf-8-sig",
              errors="replace", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            total += 1

            doi = normalize_doi(row.get("doi"))
            title = normalize_title(row.get("title"))

            if doi:
                connection.execute(doi_sql, (doi,))
            if title:
                connection.execute(title_sql, (title,))

            if total % 10000 == 0:
                connection.commit()

            if total % 100000 == 0:
                print(f"已检查 {total:,} 条记录……")

    connection.commit()

    doi_groups, doi_extra = connection.execute("""
        SELECT COUNT(*), COALESCE(SUM(count - 1), 0)
        FROM doi_counts
        WHERE count > 1
    """).fetchone()

    title_groups, title_extra = connection.execute("""
        SELECT COUNT(*), COALESCE(SUM(count - 1), 0)
        FROM title_counts
        WHERE count > 1
    """).fetchone()

    unique_dois = connection.execute(
        "SELECT COUNT(*) FROM doi_counts"
    ).fetchone()[0]

    unique_titles = connection.execute(
        "SELECT COUNT(*) FROM title_counts"
    ).fetchone()[0]

    print("\n重复审计完成")
    print(f"CSV 数据记录：{total:,}")
    print(f"不同 DOI 数：{unique_dois:,}")
    print(f"重复 DOI 组数：{doi_groups:,}")
    print(f"重复 DOI 造成的多余记录：{doi_extra:,}")
    print(f"不同标准化标题数：{unique_titles:,}")
    print(f"重复标题组数：{title_groups:,}")
    print(f"重复标题造成的多余记录：{title_extra:,}")
    print("说明：标题重复只是候选重复，不能直接据此删除。")

finally:
    connection.close()
    try:
        os.remove(db_path)
    except OSError:
        print(f"临时审计文件未自动删除：{db_path}")
