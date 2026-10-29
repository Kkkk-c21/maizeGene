import csv
import os
import sqlite3
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = PROJECT_ROOT / "01_数据" / "01_原始数据" / "maize_papers.csv"

handle, db_path = tempfile.mkstemp(
    prefix="record_id_audit_",
    suffix=".sqlite",
    dir=os.path.dirname(CSV_PATH)
)
os.close(handle)

db = sqlite3.connect(db_path)

try:
    db.execute("""
        CREATE TABLE counts (
            record_id TEXT PRIMARY KEY,
            count INTEGER NOT NULL
        )
    """)

    sql = """
        INSERT INTO counts(record_id, count) VALUES (?, 1)
        ON CONFLICT(record_id) DO UPDATE SET count = count + 1
    """

    with open(CSV_PATH, "r", encoding="utf-8-sig",
              errors="replace", newline="") as file:
        reader = csv.DictReader(file)

        for number, row in enumerate(reader, start=1):
            record_id = (row.get("record_id") or "").strip().casefold()
            if record_id:
                db.execute(sql, (record_id,))

            if number % 10000 == 0:
                db.commit()

    db.commit()

    duplicate_ids = {
        row[0] for row in db.execute(
            "SELECT record_id FROM counts WHERE count > 1"
        )
    }

    print(f"发现重复 record_id：{len(duplicate_ids)} 个")

    with open(CSV_PATH, "r", encoding="utf-8-sig",
              errors="replace", newline="") as file:
        reader = csv.DictReader(file)

        match_number = 0
        for csv_row, row in enumerate(reader, start=2):
            record_id = (row.get("record_id") or "").strip().casefold()

            if record_id in duplicate_ids:
                match_number += 1
                abstract = (row.get("abstract") or "").strip()

                print(f"\n候选记录 {match_number}")
                print(f"CSV 行号：{csv_row}")
                print(f"record_id：{row.get('record_id', '')}")
                print(f"PMID：{row.get('pmid', '')}")
                print(f"DOI：{row.get('doi', '')}")
                print(f"标题：{row.get('title', '')}")
                print(f"年份：{row.get('year', '')}")
                print(f"来源：{row.get('source', '')}")
                print(f"摘要长度：{len(abstract):,} 字符")
                print(f"采集时间：{row.get('retrieved_at', '')}")

finally:
    db.close()
    try:
        os.remove(db_path)
    except OSError:
        print(f"临时文件未自动删除：{db_path}")
