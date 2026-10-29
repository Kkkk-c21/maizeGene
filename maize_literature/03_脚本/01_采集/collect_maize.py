
import csv
import html
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
QUERY = 'maize OR "Zea mays" OR "Z. mays"'
PAGE_SIZE = 200

# First test: download two pages, then resume the remaining results.
MAX_PAGES = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = PROJECT_ROOT / "01_数据" / "01_原始数据" / "maize_papers.csv"
CHECKPOINT = PROJECT_ROOT / "04_运行状态" / "maize_checkpoint.json"

FIELDS = [
    "doi", "title", "abstract", "pmid",
    "year", "source", "record_id", "retrieved_at"
]


def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(html.unescape(value).split())


def normalize_doi(value):
    value = (value or "").strip()
    value = re.sub(
        r"^https?://(?:dx\.)?doi\.org/",
        "", value, flags=re.I
    )
    return value.lower()


def record_keys(row):
    keys = set()

    if row["doi"]:
        keys.add("doi:" + row["doi"])

    if row["pmid"]:
        keys.add("pmid:" + row["pmid"])

    if row["title"]:
        title = re.sub(r"[\W_]+", "", row["title"].lower())
        keys.add("title:" + title + ":" + row["year"])

    return keys


def fetch_page(cursor):
    params = urlencode({
        "query": QUERY,
        "format": "json",
        "resultType": "core",
        "pageSize": PAGE_SIZE,
        "cursorMark": cursor,
    })

    request = Request(
        BASE_URL + "?" + params,
        headers={"User-Agent": "PlantKG-literature-research/1.0"}
    )

    for attempt in range(5):
        try:
            with urlopen(request, timeout=90) as response:
                return json.load(response)
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def main():
    seen = set()

    if OUTPUT.exists():
        with OUTPUT.open(
            "r", encoding="utf-8-sig", newline=""
        ) as f:
            for row in csv.DictReader(f):
                seen.update(record_keys(row))

    cursor = "*"

    if CHECKPOINT.exists():
        state = json.loads(CHECKPOINT.read_text(encoding="utf-8"))

        if state["query"] != QUERY:
            raise ValueError(
                "The search query changed. Use a new output folder."
            )

        if state.get("complete"):
            print("Collection already completed.")
            return

        cursor = state["cursor"]

    pages = 0
    new_records = 0

    with OUTPUT.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)

        if OUTPUT.stat().st_size == 0:
            writer.writeheader()

        while True:
            data = fetch_page(cursor)
            records = data.get("resultList", {}).get("result", [])

            for item in records:
                row = {
                    "doi": normalize_doi(item.get("doi")),
                    "title": clean_text(item.get("title")),
                    "abstract": clean_text(item.get("abstractText")),
                    "pmid": item.get("pmid", ""),
                    "year": item.get("pubYear", ""),
                    "source": item.get("source", ""),
                    "record_id": item.get("id", ""),
                    "retrieved_at": date.today().isoformat(),
                }

                keys = record_keys(row)

                if not keys or keys.isdisjoint(seen):
                    writer.writerow(row)
                    new_records += 1

                seen.update(keys)

            f.flush()
            pages += 1

            next_cursor = data.get("nextCursorMark")

            print(
                f"Page {pages} | "
                f"New records this run: {new_records} | "
                f"Database matches: {data.get('hitCount', 'unknown')}"
            )

            if (
                not records
                or not next_cursor
                or next_cursor == cursor
            ):
                CHECKPOINT.write_text(
                    json.dumps({
                        "query": QUERY,
                        "cursor": cursor,
                        "complete": True,
                    }),
                    encoding="utf-8"
                )
                print("Collection completed.")
                break

            cursor = next_cursor

            CHECKPOINT.write_text(
                json.dumps({
                    "query": QUERY,
                    "cursor": cursor,
                    "complete": False,
                }),
                encoding="utf-8"
            )

            if MAX_PAGES is not None and pages >= MAX_PAGES:
                print("Test paused. Set MAX_PAGES = None to continue.")
                break

            time.sleep(0.3)


if __name__ == "__main__":
    main()
