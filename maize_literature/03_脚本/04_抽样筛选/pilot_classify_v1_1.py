from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from openpyxl import load_workbook


RULE_VERSION = "plantkg-maize-pilot-v1.1"
LABELS = ("A", "B", "C", "D", "E", "R", "X", "U")

MAIZE = re.compile(r"\b(?:maize|corn|zea\s+mays|z\.?\s*mays)\b", re.I)
GENE_WORD = re.compile(
    r"\b(?:gene|genes|allele|alleles|locus|loci|protein|enzyme|cDNA|"
    r"transcription\s+factor|promoter|QTL|GWAS|SNP|transcript|expression)\b",
    re.I,
)
GENE_ID = re.compile(
    r"\b(?:Zm[A-Za-z0-9][A-Za-z0-9_-]*|GRMZM\d+G\d+|"
    r"[A-Z][A-Za-z]{1,8}\d+(?:-[A-Za-z0-9]+)?|"
    r"[A-Z][A-Za-z0-9]{1,7}-[A-Z][A-Za-z0-9-]{1,10})\b"
)
MAIZE_MOLECULE = re.compile(
    r"\b(?:maize|corn|zea\s+mays)\s+(?:gene|allele|protein|enzyme|cDNA|"
    r"transcription\s+factor|promoter|locus|QTL)\b",
    re.I,
)

DIRECT_ASSAY = re.compile(
    r"\b(?:CRISPR|knock(?:out|down)|loss[- ]of[- ]function|gain[- ]of[- ]function|"
    r"overexpress(?:ion|ed|ing)?|silenc(?:e|ed|ing)|RNAi|transgenic|"
    r"complement(?:ation|ed)?|reporter\s+gene|luciferase|GUS|EMSA|"
    r"electrophoretic\s+mobility\s+shift|yeast[- ]two[- ]hybrid|"
    r"pull[- ]down|co[- ]immunoprecipitation|enzyme\s+(?:activity|kinetics)|"
    r"kinetic\s+characterization|recombinant\s+(?:protein|enzyme)|"
    r"protein\s+purification|purified\s+protein|subcellular\s+locali[sz]ation|"
    r"immunogold|locali[sz]ed\s+to|binding\s+assay)\b",
    re.I,
)
MUTATION_ONLY = re.compile(
    r"\b(?:mutant|mutants|mutation|mutations|mutagenesis|EMS|insertion\s+line)\b",
    re.I,
)
FUNCTION_RESULT = re.compile(
    r"\b(?:regulat(?:e|es|ed|ing)|promot(?:e|es|ed|ing)|inhibit(?:s|ed|ing)?|"
    r"control(?:s|led|ling)?|required\s+for|confers?|mediate(?:s|d)?|"
    r"increas(?:e|es|ed|ing)|decreas(?:e|es|ed|ing)|affect(?:s|ed|ing)?|"
    r"locali[sz](?:e|es|ed|ation)|bind(?:s|ing)?|interact(?:s|ed|ion)?|"
    r"cataly[sz](?:e|es|ed)|activity|accumulation)\b",
    re.I,
)
PHENOTYPE = re.compile(
    r"\b(?:phenotype|trait|kernel|grain|seed|root|leaf|ear|tassel|stalk|"
    r"plant\s+height|flowering|fertility|male[- ]steril|yield|biomass|"
    r"drought|salinity|cold|heat|disease\s+resistance|insect\s+resistance|"
    r"tocopherol|vitamin\s+E|biofortification|electrophoretic\s+mobility|protein\s+content)\b",
    re.I,
)
ASSOCIATION = re.compile(
    r"\b(?:QTL|GWAS|genome[- ]wide\s+association|association\s+mapping|"
    r"linkage\s+mapping|fine\s+mapping|eQTL|candidate\s+gene|"
    r"differential(?:ly)?\s+expressed|expression\s+profiling|RNA[- ]?seq|"
    r"transcriptom(?:e|ic)|proteom(?:e|ic)|metabolom(?:e|ic)|co[- ]expression)\b",
    re.I,
)
COMPUTATIONAL = re.compile(
    r"\b(?:phylogen(?:y|etic)|homolog|ortholog|paralog|comparative\s+genomics|"
    r"domain\s+analysis|motif\s+analysis|in\s+silico|bioinformatic|"
    r"sequence\s+analysis|functional\s+prediction|annotation\s+pipeline)\b",
    re.I,
)
RESOURCE = re.compile(
    r"\b(?:database|knowledgebase|atlas|reference\s+genome|genome\s+assembly|"
    r"genome\s+sequence|pan[- ]?genome|gene\s+catalog|web\s+portal|"
    r"genomic\s+resource|expression\s+resource|network\s+resource|"
    r"co[- ]functional\s+network|gene\s+network)\b",
    re.I,
)
REVIEW = re.compile(
    r"\b(?:review|systematic\s+review|meta[- ]analysis|perspective|overview|"
    r"current\s+status|recent\s+advances)\b",
    re.I,
)

OTHER_SUBJECT = re.compile(
    r"\b(?:human|patients?|mice|mouse|rats?|swine|pigs?|poultry|chickens?|"
    r"cattle|cows?|rumen|broilers?|lymphocytes?|cassava|potato|wheat|rice|"
    r"soybean|arabidopsis|sorghum|bacillus|pseudomonas|helicoverpa|"
    r"mycotoxins?|bacteri(?:a|um)|fung(?:us|al)|insect\s+midgut)\b",
    re.I,
)
FOOD_FEED = re.compile(
    r"\b(?:feed|feeding|diet|nutrition|food|starch|corn\s+oil|corn\s+syrup|"
    r"ethanol\s+production|toxic(?:ity|ology)|cytotoxicity|fermentation|"
    r"processing|digestibility|supplementation)\b",
    re.I,
)
AGRONOMY = re.compile(
    r"\b(?:fertili[sz]er|irrigation|tillage|planting\s+density|intercropping|"
    r"soil\s+fertility|manure|sludge|nitrogen\s+rate|phosphorus\s+rate|"
    r"climate\s+change|regional\s+yield|cropping\s+system|weed\s+control)\b",
    re.I,
)
PATENT_CLAIM = re.compile(r"\b(?:patent|invention|claims?|method\s+for)\b", re.I)


@dataclass(frozen=True)
class Suggestion:
    candidate_label: str
    secondary_labels: str
    screening_status: str
    reason: str
    flags: str
    rule_version: str = RULE_VERSION


def ordered_labels(labels):
    found = set(labels)
    return [label for label in LABELS if label in found]


def status_for(label: str) -> str:
    if label == "X":
        return "exclude_candidate"
    if label == "U":
        return "needs_manual_review"
    return "retain_for_evidence_review"


def has_traceable_gene_phenotype(text: str) -> bool:
    """Require a named genetic object, mutation signal, and phenotype nearby.

    The broad GENE_ID pattern is useful for recall, but it can also match short
    chemistry tokens such as H2O2 or NMR peak names.  B therefore uses a
    relation-level check rather than treating any identifier-like token plus a
    physiological outcome as a gene-phenotype relation.
    """
    for match in GENE_ID.finditer(text):
        start = max(0, match.start() - 450)
        end = min(len(text), match.end() + 450)
        window = text[start:end]
        if PHENOTYPE.search(window) and MUTATION_ONLY.search(window):
            return True
    return False


def suggest(row: dict[str, str]) -> Suggestion:
    title = (row.get("title") or row.get("英文题名") or "").strip()
    abstract = (row.get("abstract") or row.get("英文摘要") or "").strip()
    source = (row.get("source") or row.get("来源") or "").strip().upper()
    text = f"{title}\n{abstract}"

    maize = bool(MAIZE.search(text))
    title_maize = bool(MAIZE.search(title))
    gene_word = bool(GENE_WORD.search(text))
    specific_gene_identity = bool(GENE_ID.search(text))
    gene_identity = bool(specific_gene_identity or MAIZE_MOLECULE.search(text))
    direct_assay = bool(DIRECT_ASSAY.search(text))
    mutation_only = bool(MUTATION_ONLY.search(text))
    function_result = bool(FUNCTION_RESULT.search(text))
    phenotype = bool(PHENOTYPE.search(text))
    association = bool(ASSOCIATION.search(text))
    computational = bool(COMPUTATIONAL.search(text))
    resource = bool(RESOURCE.search(text))
    review = bool(REVIEW.search(title))
    other_title = bool(OTHER_SUBJECT.search(title))
    other_anywhere = bool(OTHER_SUBJECT.search(text))
    food_feed = bool(FOOD_FEED.search(text))
    agronomy = bool(AGRONOMY.search(text))
    patent_claim = source == "PAT" or bool(PATENT_CLAIM.search(title))
    traceable_gene_phenotype = has_traceable_gene_phenotype(text)

    flags = []
    if not abstract:
        flags.append("missing_abstract")
    if not maize:
        flags.append("maize_not_explicit")
    if maize and not title_maize:
        flags.append("maize_only_outside_title")
    if gene_identity:
        flags.append("gene_or_molecule_identity_signal")
        if specific_gene_identity:
            flags.append("specific_gene_identifier_signal")
    elif gene_word:
        flags.append("generic_gene_term_only")
    if direct_assay:
        flags.append("direct_assay_signal")
    if mutation_only:
        flags.append("mutation_signal")
    if association:
        flags.append("association_signal")
    if computational:
        flags.append("computational_signal")
    if resource:
        flags.append("resource_signal")
    if review:
        flags.append("review_title")
    if other_anywhere:
        flags.append("possible_non_maize_subject")
    if food_feed:
        flags.append("food_feed_processing_signal")
    if agronomy:
        flags.append("agronomy_management_signal")
    if patent_claim:
        flags.append("patent_or_claim_only_risk")
    if traceable_gene_phenotype:
        flags.append("traceable_gene_phenotype_signal")

    secondary = []

    # Missing abstracts remain unresolved even when a title looks decisive.
    # This prevents title-only A/B/C/X decisions from masquerading as evidence.
    if not abstract:
        label = "U"
        reason = "The abstract is missing; title-only evidence is insufficient for a conservative screening decision."
    # With a present abstract, no maize mention anywhere is a clear scope
    # exclusion.  This is structural, not a growing dictionary of topics.
    elif not maize:
        label = "X"
        reason = "Neither the title nor the available abstract mentions maize; the record is outside the maize screening scope."
    # A different organism in the title is not sufficient by itself: keep the
    # record unresolved when the abstract also provides molecular/functional
    # evidence that could genuinely connect that work to maize.
    elif other_title and not title_maize and (
        computational
        or not ((gene_identity or gene_word) and (direct_assay or association or function_result))
    ):
        label = "X"
        reason = "A non-maize title subject is only contextually connected to maize and no traceable maize molecular relation is present."
    elif review:
        if (food_feed or agronomy) and not (gene_identity or association or resource):
            label = "X"
            reason = "The review concerns agronomy, food/feed, or processing rather than traceable maize gene-function evidence."
        elif gene_word or association or resource or phenotype:
            label = "R"
            reason = "The title identifies a maize-relevant review; retain it for tracing primary studies, not as direct evidence."
        else:
            label = "X"
            reason = "The review is maize-related but lacks a clear maize gene-function scope for the core evidence queue."
    elif resource and (gene_word or association):
        label = "E"
        reason = "The record describes a maize genomic, omics, network, or database resource relevant to gene function."
        if computational:
            secondary.append("D")
    elif gene_identity and direct_assay and function_result:
        label = "A"
        reason = "A maize gene/protein identity, a direct assay, and an observed molecular or functional result are all present."
        if phenotype:
            secondary.append("B")
        if association:
            secondary.append("C")
    elif association and (gene_identity or gene_word):
        label = "C"
        reason = "The record supports QTL, GWAS, expression, or omics association rather than a confirmed single-gene mechanism."
        if phenotype:
            secondary.append("B")
    elif patent_claim and (gene_word or gene_identity):
        label = "U"
        reason = "A patent or claim mentions maize molecular material, but experimental controls and measured outcomes are not verified."
    elif specific_gene_identity and traceable_gene_phenotype:
        label = "B"
        reason = "A named genetic object, a mutation signal, and a phenotype occur in a traceable local relation, without enough direct molecular evidence for A."
    elif computational and (gene_identity or gene_word):
        label = "D"
        reason = "The support is sequence, homology, phylogenetic, or other computational evidence for a maize gene or protein."
    elif (food_feed or agronomy) and not (specific_gene_identity and (direct_assay or association)) and not resource:
        label = "X"
        reason = "The record is primarily food/feed, processing, toxicity, or crop management and lacks a specific maize gene-level relation."
    elif gene_word or gene_identity or phenotype:
        label = "U"
        reason = "The record is maize-related, but the abstract does not establish a traceable gene-level evidence relation."
    else:
        label = "X"
        reason = "The maize record lacks gene, protein, locus, functional-resource, or association evidence for the current core scope."

    if label == "U":
        flags.append("full_text_or_identity_check_required")
    if label == "X" and maize and not other_title and not (food_feed or agronomy):
        flags.append("core_scope_exclusion")
    if secondary:
        flags.append("mixed_evidence_candidate")

    return Suggestion(
        candidate_label=label,
        secondary_labels=",".join(ordered_labels(secondary)),
        screening_status=status_for(label),
        reason=reason,
        flags=";".join(sorted(set(flags))),
    )


def field_limit():
    value = sys.maxsize
    while True:
        try:
            csv.field_size_limit(value)
            return
        except OverflowError:
            value //= 10


def classify_csv(input_path: Path, output_path: Path, max_rows: int) -> dict:
    blocked = {"maize_papers.csv", "maize_papers_cleaned_v1.csv"}
    if input_path.name.lower() in blocked:
        raise RuntimeError(f"Refusing full-corpus input: {input_path}")

    field_limit()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    rows = 0
    with input_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as src:
        reader = csv.DictReader(src)
        input_fields = reader.fieldnames or []
        required = {"title", "abstract"}
        missing = required - set(input_fields)
        if missing:
            raise RuntimeError(f"Missing required columns in {input_path.name}: {sorted(missing)}")
        added = [
            "pilot_v1_1_candidate_label",
            "pilot_v1_1_secondary_labels",
            "pilot_v1_1_screening_status",
            "pilot_v1_1_reason",
            "pilot_v1_1_flags",
            "pilot_v1_1_rule_version",
        ]
        with output_path.open("w", encoding="utf-8-sig", newline="") as dst:
            writer = csv.DictWriter(dst, fieldnames=input_fields + added, extrasaction="ignore")
            writer.writeheader()
            for row in reader:
                rows += 1
                if rows > max_rows:
                    raise RuntimeError(
                        f"Safety limit exceeded ({max_rows} rows) for {input_path.name}; pilot aborted."
                    )
                result = suggest(row)
                row.update(
                    {
                        "pilot_v1_1_candidate_label": result.candidate_label,
                        "pilot_v1_1_secondary_labels": result.secondary_labels,
                        "pilot_v1_1_screening_status": result.screening_status,
                        "pilot_v1_1_reason": result.reason,
                        "pilot_v1_1_flags": result.flags,
                        "pilot_v1_1_rule_version": result.rule_version,
                    }
                )
                counts[result.candidate_label] += 1
                writer.writerow(row)
    return {
        "input": str(input_path),
        "output": str(output_path),
        "rows": rows,
        "input_columns": input_fields,
        "label_counts": {label: counts[label] for label in LABELS},
    }


def table_rows(ws, header_row: int) -> list[dict[str, str]]:
    headers = [str(cell.value).strip() if cell.value is not None else "" for cell in ws[header_row]]
    while headers and not headers[-1]:
        headers.pop()
    rows = []
    for values in ws.iter_rows(min_row=header_row + 1, max_col=len(headers), values_only=True):
        row = {header: "" if value is None else str(value).strip() for header, value in zip(headers, values) if header}
        if any(row.values()):
            rows.append(row)
    return rows


def load_cohort(path: Path, cohort: str, label_sheet: str, label_header: int,
                id_field: str, label_field: str, record_sheet: str,
                record_header: int) -> list[dict]:
    wb = load_workbook(path, read_only=False, data_only=False)
    labels = table_rows(wb[label_sheet], label_header)
    records = table_rows(wb[record_sheet], record_header)
    record_by_id = {
        row.get("sample_id") or row.get("样本ID"): row
        for row in records
        if row.get("sample_id") or row.get("样本ID")
    }
    result = []
    for label_row in labels:
        sample_id = label_row.get(id_field, "")
        manual_label = label_row.get(label_field, "").strip().upper()
        if not sample_id or manual_label not in LABELS:
            continue
        record = record_by_id.get(sample_id)
        if record is None:
            raise RuntimeError(f"{path.name}: no source record for {sample_id}")
        title = record.get("title") or record.get("英文题名") or ""
        abstract = record.get("abstract") or record.get("英文摘要") or ""
        source = record.get("source") or record.get("来源") or ""
        prediction = suggest({"title": title, "abstract": abstract, "source": source})
        result.append(
            {
                "cohort": cohort,
                "workbook": str(path),
                "sample_id": sample_id,
                "source_record_key": record.get("source_record_key") or record.get("来源记录键") or "",
                "title": title,
                "manual_label": manual_label,
                "manual_status": status_for(manual_label),
                "pilot_v1_1_candidate_label": prediction.candidate_label,
                "pilot_v1_1_secondary_labels": prediction.secondary_labels,
                "pilot_v1_1_screening_status": prediction.screening_status,
                "pilot_v1_1_reason": prediction.reason,
                "pilot_v1_1_flags": prediction.flags,
                "exact_label_match": str(prediction.candidate_label == manual_label).lower(),
                "screening_status_match": str(prediction.screening_status == status_for(manual_label)).lower(),
            }
        )
    wb.close()
    return result


def metrics(rows: list[dict]) -> dict:
    n = len(rows)
    exact = sum(row["exact_label_match"] == "true" for row in rows)
    status = sum(row["screening_status_match"] == "true" for row in rows)
    confusion = {label: {pred: 0 for pred in LABELS} for label in LABELS}
    for row in rows:
        confusion[row["manual_label"]][row["pilot_v1_1_candidate_label"]] += 1
    return {
        "records": n,
        "exact_matches": exact,
        "exact_match_rate": exact / n if n else None,
        "screening_status_matches": status,
        "screening_status_match_rate": status / n if n else None,
        "manual_distribution": dict(Counter(row["manual_label"] for row in rows)),
        "prediction_distribution": dict(Counter(row["pilot_v1_1_candidate_label"] for row in rows)),
        "confusion_manual_by_prediction": confusion,
        "errors": [
            {
                "sample_id": row["sample_id"],
                "manual": row["manual_label"],
                "predicted": row["pilot_v1_1_candidate_label"],
                "title": row["title"],
                "reason": row["pilot_v1_1_reason"],
                "flags": row["pilot_v1_1_flags"],
            }
            for row in rows
            if row["exact_label_match"] != "true"
        ],
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(rows)


def workbook_inventory(review_root: Path) -> list[dict]:
    inventory = []
    for path in sorted(review_root.rglob("*.xlsx")):
        wb = load_workbook(path, read_only=False, data_only=False)
        sheets = []
        for ws in wb.worksheets:
            best = None
            for row_number in range(1, min(ws.max_row, 20) + 1):
                values = ["" if cell.value is None else str(cell.value).strip() for cell in ws[row_number]]
                score = sum(
                    value in {"sample_id", "样本ID", "测试ID", "title", "英文题名"}
                    or "标签" in value
                    for value in values
                )
                if score and (best is None or score > best[0]):
                    while values and not values[-1]:
                        values.pop()
                    best = (score, row_number, values)
            sheets.append(
                {
                    "name": ws.title,
                    "rows": ws.max_row,
                    "columns": ws.max_column,
                    "detected_header_row": best[1] if best else None,
                    "detected_headers": best[2] if best else [],
                }
            )
        inventory.append({"path": str(path), "sheets": sheets})
        wb.close()
    return inventory


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def markdown_report(report: dict) -> str:
    lines = [
        "# PlantKG maize pilot classification v1.1",
        "",
        f"Rule version: `{RULE_VERSION}`",
        "",
        "This pilot processed only the three sample CSVs and small review workbooks. The full corpus was not read or classified.",
        "",
        "The labels mix evidence type (A/B/C/D/E/R) with screening state (X/U). The output therefore keeps `candidate_label` separate from `screening_status`.",
        "",
        f"Source integrity check: {report['source_integrity']['files_checked']} files checked; all unchanged = {report['source_integrity']['all_unchanged']}.",
        "",
        "## Sample CSV outputs",
        "",
        "| Input | Rows | A | B | C | D | E | R | X | U |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["csv_runs"]:
        counts = item["label_counts"]
        lines.append(
            f"| {Path(item['input']).name} | {item['rows']} | "
            + " | ".join(str(counts[label]) for label in LABELS)
            + " |"
        )
    lines.extend(["", "## Manual comparison", ""])
    for name in ("manual_30_final", "manual_6_targeted", "manual_36_union", "manual_20_separate", "unique_56"):
        item = report["metrics"][name]
        lines.append(
            f"- {name}: {item['exact_matches']}/{item['records']} exact labels "
            f"({item['exact_match_rate']:.1%}); {item['screening_status_matches']}/{item['records']} screening statuses "
            f"({item['screening_status_match_rate']:.1%})."
        )
    overlap = report["overlap"]
    lines.extend(
        [
            "",
            "## Dependence and overlap",
            "",
            f"- 30 final IDs: {overlap['manual_30_count']}",
            f"- Six targeted IDs: {overlap['manual_6_count']}",
            f"- 36 union IDs: {overlap['manual_36_count']}",
            f"- 36 equals 30 union 6: {overlap['manual_36_equals_30_union_6']}",
            f"- 20 versus 36 overlap: {overlap['manual_20_36_overlap_count']}",
            f"- Two 36-workbook ID sets identical: {overlap['two_36_workbooks_identical']}",
            "",
            "The 36-record workbook is not an independent validation set: it is the 30 final records plus the six targeted candidates. The two 36-record workbooks are derivative copies, and the six-record set is deliberately enriched for A/B evidence.",
            "",
            "## Errors in the deduplicated 56-record comparison",
            "",
        ]
    )
    for err in report["metrics"]["unique_56"]["errors"]:
        lines.append(
            f"- {err['sample_id']}: manual {err['manual']}, pilot {err['predicted']} — {err['title']}"
        )
    return "\n".join(lines) + "\n"


def parse_args():
    parser = argparse.ArgumentParser(description="Low-memory pilot classifier for PlantKG maize sample/review files.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(r"D:\cyq\maizeGene\maize_literature"),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--max-rows-per-csv", type=int, default=5000)
    return parser.parse_args()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    root = args.project_root.resolve()
    output_dir = (args.output_dir or (root / "04_运行状态" / "pilot_v1_1_2026-10-28")).resolve()
    sample_dir = root / "02_抽样与复核" / "01_抽样CSV"
    review_root = root / "02_抽样与复核"

    csv_names = [
        "screening_review_first30.csv",
        "screening_sample_500.csv",
        "screening_sample_500_prelabelled.csv",
    ]
    current20 = review_root / "02_当前复核工作簿" / "玉米功能文献小批测试_v1_20篇_中文翻译版.xlsx"
    history = review_root / "03_历史复核版本"
    final30 = history / "玉米文献30篇_学校全文复核版.xlsx"
    targeted6 = history / "玉米文献6篇_功能实验优先候选.xlsx"
    union36 = history / "玉米文献36篇_S0450-v5映射版.xlsx"
    union36_prior = history / "玉米文献36篇_复核汇总与证据示范.xlsx"

    source_files = [sample_dir / name for name in csv_names]
    source_files.extend(sorted(review_root.rglob("*.xlsx")))
    source_files.append(root / "00_项目说明与规则" / "玉米功能文献筛选规则_v1_草案.md")
    hashes_before = {str(path): sha256_file(path) for path in source_files}

    csv_runs = []
    for name in csv_names:
        input_path = sample_dir / name
        output_path = output_dir / name.replace(".csv", "_pilot_v1_1.csv")
        csv_runs.append(classify_csv(input_path, output_path, args.max_rows_per_csv))

    rows20 = load_cohort(
        current20, "manual_20_separate", "人工复核", 6, "样本ID", "人工确认标签", "英文原文", 6
    )
    rows30 = load_cohort(
        final30, "manual_30_final", "逐篇判断", 6, "样本ID", "人工确认标签", "原始记录", 1
    )
    rows6 = load_cohort(
        targeted6, "manual_6_targeted", "候选判读", 6, "样本ID", "人工确认标签", "原始记录", 1
    )
    rows36 = load_cohort(
        union36, "manual_36_union", "36篇复核汇总", 6, "样本ID", "人工确认标签", "原始样本记录", 1
    )
    rows36_prior = load_cohort(
        union36_prior, "manual_36_prior_copy", "36篇复核汇总", 6, "样本ID", "人工确认标签", "原始样本记录", 1
    )

    all_comparisons = rows30 + rows6 + rows36 + rows36_prior + rows20
    write_csv(output_dir / "manual_comparison_all_workbooks_pilot_v1_1.csv", all_comparisons)

    # Deduplicated evaluation uses the current 20-record workbook plus the newest
    # 36-record union. The 30 and six cohorts are retained separately for
    # diagnostic metrics but are not counted again.
    unique_rows = rows20 + rows36
    write_csv(output_dir / "manual_comparison_unique_56_pilot_v1_1.csv", unique_rows)

    ids20 = {row["sample_id"] for row in rows20}
    ids30 = {row["sample_id"] for row in rows30}
    ids6 = {row["sample_id"] for row in rows6}
    ids36 = {row["sample_id"] for row in rows36}
    ids36_prior = {row["sample_id"] for row in rows36_prior}
    hashes_after = {str(path): sha256_file(path) for path in source_files}
    integrity = {
        path: {
            "sha256_before": hashes_before[path],
            "sha256_after": hashes_after[path],
            "unchanged": hashes_before[path] == hashes_after[path],
        }
        for path in hashes_before
    }

    report = {
        "rule_version": RULE_VERSION,
        "project_root": str(root),
        "output_dir": str(output_dir),
        "safety": {
            "full_corpus_processed": False,
            "max_rows_per_csv": args.max_rows_per_csv,
            "blocked_full_corpus_filenames": ["maize_papers.csv", "maize_papers_cleaned_v1.csv"],
        },
        "label_semantics_note": (
            "A/B/C/D/E/R describe evidence types, while X/U describe screening state. "
            "The pilot therefore outputs candidate_label and screening_status separately."
        ),
        "source_integrity": {
            "files_checked": len(integrity),
            "all_unchanged": all(item["unchanged"] for item in integrity.values()),
            "files": integrity,
        },
        "csv_runs": csv_runs,
        "workbook_inventory": workbook_inventory(review_root),
        "overlap": {
            "manual_20_count": len(ids20),
            "manual_30_count": len(ids30),
            "manual_6_count": len(ids6),
            "manual_36_count": len(ids36),
            "manual_36_equals_30_union_6": ids36 == (ids30 | ids6),
            "manual_30_6_overlap_count": len(ids30 & ids6),
            "manual_20_36_overlap_count": len(ids20 & ids36),
            "two_36_workbooks_identical": ids36 == ids36_prior,
        },
        "metrics": {
            "manual_30_final": metrics(rows30),
            "manual_6_targeted": metrics(rows6),
            "manual_36_union": metrics(rows36),
            "manual_20_separate": metrics(rows20),
            "unique_56": metrics(unique_rows),
        },
    }

    with (output_dir / "pilot_v1_1_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    with (output_dir / "pilot_v1_1_report.md").open("w", encoding="utf-8") as handle:
        handle.write(markdown_report(report))

    print(json.dumps({
        "output_dir": str(output_dir),
        "csv_rows": {Path(item["input"]).name: item["rows"] for item in csv_runs},
        "overlap": report["overlap"],
        "metrics": {
            name: {
                "records": value["records"],
                "exact_match_rate": value["exact_match_rate"],
                "screening_status_match_rate": value["screening_status_match_rate"],
                "errors": len(value["errors"]),
            }
            for name, value in report["metrics"].items()
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
