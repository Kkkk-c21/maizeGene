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
    return re.sub(
        r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", value
    ).strip()

def normalize_title(value):
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return "".join(char for char in value if char.isalnum())

handle, db_path = tempfile.mkstemp(
    prefix="maize_classify_",
    suffix=".sqlite",
    dir=os.path.dirname(CSV_PATH)
)
os.close(handle)

db = sqlite3.connect(db_path)

try:
    db.executescript("""
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        PRAGMA temp_store=FILE;
        PRAGMA cache_size=-20000;

        CREATE TABLE records (
            title_key TEXT,
            doi TEXT,
            pmid TEXT,
            record_id TEXT
        );

        CREATE INDEX idx_title ON records(title_key);
        CREATE INDEX idx_pmid ON records(pmid);
        CREATE INDEX idx_record_id ON records(record_id);
    """)

    insert_sql = """
        INSERT INTO records(title_key, doi, pmid, record_id)
        VALUES (?, ?, ?, ?)
    """

    batch = []
    total = 0

    with open(CSV_PATH, "r", encoding="utf-8-sig",
              errors="replace", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            total += 1
            batch.append((
                normalize_title(row.get("title")),
                normalize_doi(row.get("doi")),
                (row.get("pmid") or "").strip(),
                (row.get("record_id") or "").strip().casefold()
            ))

            if len(batch) >= 10000:
                db.executemany(insert_sql, batch)
                db.commit()
                batch.clear()

            if total % 100000 == 0:
                print(f"已检查 {total:,} 条记录……")

    if batch:
        db.executemany(insert_sql, batch)
        db.commit()

    def duplicate_stats(column):
        query = f"""
            SELECT COUNT(*), COALESCE(SUM(n - 1), 0)
            FROM (
                SELECT {column}, COUNT(*) AS n
                FROM records
                WHERE {column} <> ''
                GROUP BY {column}
                HAVING n > 1
            )
        """
        return db.execute(query).fetchone()

    pmid_groups, pmid_extra = duplicate_stats("pmid")
    id_groups, id_extra = duplicate_stats("record_id")

    categories = db.execute("""
        WITH duplicate_titles AS (
            SELECT
                title_key,
                COUNT(*) AS row_count,
                SUM(CASE WHEN doi <> '' THEN 1 ELSE 0 END) AS doi_rows
            FROM records
            WHERE title_key <> ''
            GROUP BY title_key
            HAVING row_count > 1
        )
        SELECT
            CASE
                WHEN doi_rows = 0 THEN '全部缺少 DOI'
                WHEN doi_rows = 1 THEN '仅一条有 DOI'
                ELSE '存在多个不同 DOI'
            END AS category,
            COUNT(*) AS group_count,
            SUM(row_count) AS row_count,
            SUM(row_count - 1) AS extra_count
        FROM duplicate_titles
        GROUP BY category
        ORDER BY
            CASE category
                WHEN '仅一条有 DOI' THEN 1
                WHEN '全部缺少 DOI' THEN 2
                ELSE 3
            END
    """).fetchall()

    print("\n分类审计完成")
    print(f"CSV 数据记录：{total:,}")
    print(f"重复 PMID：{pmid_groups:,} 组，涉及多余记录 {pmid_extra:,} 条")
    print(f"重复 record_id：{id_groups:,} 组，涉及多余记录 {id_extra:,} 条")

    print("\n相同标题候选分类：")
    for category, groups, rows, extra in categories:
        print(
            f"{category}：{groups:,} 组，"
            f"共 {rows:,} 条，候选多余 {extra:,} 条"
        )

finally:
    db.close()
    try:
        os.remove(db_path)
    except OSError:
        print(f"临时文件未自动删除：{db_path}")
