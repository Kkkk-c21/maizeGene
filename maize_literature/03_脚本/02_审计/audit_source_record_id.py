import csv
import os
import sqlite3
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = PROJECT_ROOT / "01_数据" / "01_原始数据" / "maize_papers.csv"

handle, db_path = tempfile.mkstemp(
    prefix="source_record_audit_",
    suffix=".sqlite",
    dir=os.path.dirname(CSV_PATH)
)
os.close(handle)

db = sqlite3.connect(db_path)

try:
    db.execute("""
        CREATE TABLE counts (
            source TEXT NOT NULL,
            record_id TEXT NOT NULL,
            count INTEGER NOT NULL,
            PRIMARY KEY (source, record_id)
        )
    """)

    sql = """
        INSERT INTO counts(source, record_id, count)
        VALUES (?, ?, 1)
        ON CONFLICT(source, record_id)
        DO UPDATE SET count = count + 1
    """

    with open(CSV_PATH, "r", encoding="utf-8-sig",
              errors="replace", newline="") as file:
        reader = csv.DictReader(file)

        for number, row in enumerate(reader, start=1):
            source = (row.get("source") or "").strip().upper()
            record_id = (row.get("record_id") or "").strip()

            if source and record_id:
                db.execute(sql, (source, record_id))

            if number % 10000 == 0:
                db.commit()

            if number % 100000 == 0:
                print(f"已检查 {number:,} 条记录……")

    db.commit()

    duplicates = db.execute("""
        SELECT source, record_id, count
        FROM counts
        WHERE count > 1
        ORDER BY count DESC
    """).fetchall()

    print("\n组合键审计完成")
    print(f"重复的 source + record_id 组数：{len(duplicates):,}")
    print(
        "涉及的多余记录："
        f"{sum(count - 1 for _, _, count in duplicates):,}"
    )

    for source, record_id, count in duplicates[:20]:
        print(f"{source} + {record_id}：{count} 条")

finally:
    db.close()
    try:
        os.remove(db_path)
    except OSError:
        print(f"临时文件未自动删除：{db_path}")
