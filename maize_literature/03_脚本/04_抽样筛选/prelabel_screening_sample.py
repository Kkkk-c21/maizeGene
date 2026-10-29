import csv
import random
import re
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = PROJECT_ROOT / "02_抽样与复核" / "01_抽样CSV"
INPUT_CSV = SAMPLE_DIR / "screening_sample_500.csv"
OUTPUT_CSV = SAMPLE_DIR / "screening_sample_500_prelabelled.csv"
FIRST_REVIEW_CSV = SAMPLE_DIR / "screening_review_first30.csv"
RANDOM_SEED = 20261027


MAIZE = re.compile(
    r"\b(?:maize|corn|zea\s+mays|z\.?\s*mays)\b",
    re.IGNORECASE,
)

GENE = re.compile(
    r"\b(?:gene|genes|genetic|genetics|genome|genomic|transcript|"
    r"transcriptome|expression|protein|enzyme|allele|locus|loci|"
    r"chromosome|qtl|qtls|gwas|snp|snps|mirna|lncrna|methylation|"
    r"epigenetic|transcription\s+factor|zm[a-z0-9_-]+|grmzm[a-z0-9_-]+)\b",
    re.IGNORECASE,
)

DIRECT = re.compile(
    r"\b(?:crispr|knockout|knock-out|knockdown|knock-down|"
    r"loss[- ]of[- ]function|gain[- ]of[- ]function|overexpress(?:ion|ed)?|"
    r"silenc(?:e|ed|ing)|rnai|transgenic|complementation|complemented|"
    r"mutant|mutation|functional characterization|direct assay|"
    r"binds?|binding|interacts?|interaction|localization|localised|localized|"
    r"regulates?|regulated|controls?|controlled|required for|confers?|"
    r"promotes?|inhibits?|mediates?|enzyme activity)\b",
    re.IGNORECASE,
)

PHENOTYPE = re.compile(
    r"\b(?:phenotype|phenotypic|trait|yield|flowering|plant height|"
    r"kernel|grain|seed|root|leaf|ear|tassel|stalk|biomass|"
    r"drought|salinity|salt stress|heat stress|cold stress|lodging|"
    r"disease resistance|insect resistance|photosynthesis|fertility|"
    r"germination|development)\b",
    re.IGNORECASE,
)

ASSOCIATION = re.compile(
    r"\b(?:gwas|genome-wide association|qtl|qtls|eqtl|association mapping|"
    r"linkage mapping|fine mapping|candidate gene|rna-seq|rna seq|"
    r"transcriptom(?:e|ic)|proteom(?:e|ic)|metabolom(?:e|ic)|"
    r"differential(?:ly)? expressed|differential expression|coexpression|"
    r"co-expression|expression profiling)\b",
    re.IGNORECASE,
)

COMPUTATIONAL = re.compile(
    r"\b(?:blast|homolog|homology|ortholog|orthology|paralog|"
    r"phylogenetic|comparative genomics|domain analysis|motif analysis|"
    r"in silico|bioinformatic|prediction model|machine learning|"
    r"deep learning|annotation pipeline)\b",
    re.IGNORECASE,
)

RESOURCE = re.compile(
    r"\b(?:database|knowledgebase|resource|atlas|reference genome|"
    r"genome assembly|genome sequence|pan-genome|pangenome|"
    r"catalog|dataset|data set|web server|portal)\b",
    re.IGNORECASE,
)

REVIEW = re.compile(
    r"\b(?:review|systematic review|meta-analysis|overview|perspective)\b",
    re.IGNORECASE,
)

OBVIOUS_NON_MAIZE = re.compile(
    r"\b(?:swine|pig|pigs|poultry|chicken|chickens|cattle|cow|cows|"
    r"sheep|goat|rumen|broiler|human|patients?|mice|mouse|rats?|"
    r"cassava|potato|wheat|rice|soybean|sorghum|rose|roses|arabidopsis|"
    r"food processing|corn oil|corn starch|corn syrup|ethanol production|"
    r"diet|diets|feed|feeding|nutrition|toxicity to)\b",
    re.IGNORECASE,
)


def suggest(row):
    title = row.get("title") or ""
    abstract = row.get("abstract") or ""
    text = f"{title} {abstract}"

    title_maize = bool(MAIZE.search(title))
    maize = bool(MAIZE.search(text))
    gene = bool(GENE.search(text))
    direct = bool(DIRECT.search(text))
    phenotype = bool(PHENOTYPE.search(text))
    association = bool(ASSOCIATION.search(text))
    computational = bool(COMPUTATIONAL.search(text))
    resource = bool(RESOURCE.search(text))
    review = bool(REVIEW.search(title))
    obvious_non_maize = bool(OBVIOUS_NON_MAIZE.search(title))

    matched = []
    if direct and gene:
        matched.append("A")
    if phenotype and gene:
        matched.append("B")
    if association and gene:
        matched.append("C")
    if computational and gene:
        matched.append("D")
    if resource:
        matched.append("E")
    if review:
        matched.append("R")

    # 先判断文献的主题是否确实指向玉米，再判断证据类型。
    if obvious_non_maize and not title_maize and not gene:
        primary = "X"
        confidence = "high"
        reason = "标题主体明显是其他物种、动物营养或加工用途，未检测到玉米基因信号"
    elif not maize:
        primary = "U"
        confidence = "low"
        reason = "标题和摘要未明确出现 maize/corn/Zea mays，需要确认检索命中原因"
    elif review:
        primary = "R"
        confidence = "medium"
        reason = "标题显示为综述类文章；可用于追溯原始研究，不直接作为实验事实"
    elif obvious_non_maize and not title_maize and not direct:
        primary = "X"
        confidence = "medium"
        reason = "玉米可能仅作为比较、饲料或背景材料出现，文章主体疑似不是玉米基因研究"
    elif direct and gene:
        primary = "A"
        confidence = "medium"
        reason = "检测到玉米、基因信号及扰动、调控、互作或功能实验用语"
    elif association and gene:
        primary = "C"
        confidence = "medium"
        reason = "检测到玉米基因信号以及GWAS、QTL或组学关联用语"
    elif phenotype and gene:
        primary = "B"
        confidence = "medium"
        reason = "检测到玉米基因信号及表型或农艺性状用语，但直接因果证据尚不明确"
    elif computational and gene:
        primary = "D"
        confidence = "medium"
        reason = "检测到玉米基因信号及同源、BLAST、结构域或计算预测用语"
    elif resource:
        primary = "E"
        confidence = "medium"
        reason = "检测到玉米相关数据库、图谱、基因组组装或数据资源用语"
    else:
        primary = "U"
        confidence = "low"
        reason = "与玉米有关，但仅凭标题摘要无法确定是否能形成基因功能知识边"

    secondary = [label for label in matched if label != primary]

    evidence_names = []
    if direct and gene:
        evidence_names.append("direct_function_candidate")
    if phenotype and gene:
        evidence_names.append("phenotype_trait_candidate")
    if association and gene:
        evidence_names.append("association_omics_candidate")
    if computational and gene:
        evidence_names.append("computational_candidate")
    if resource:
        evidence_names.append("resource_candidate")
    if review:
        evidence_names.append("review")

    return {
        "computer_suggested_label": primary,
        "computer_secondary_labels": ",".join(secondary),
        "computer_confidence": confidence,
        "computer_evidence_signals": ",".join(evidence_names),
        "computer_reason": reason,
    }


with open(INPUT_CSV, "r", encoding="utf-8-sig", errors="replace", newline="") as file:
    reader = csv.DictReader(file)
    input_fields = reader.fieldnames or []
    rows = []

    for row in reader:
        row.update(suggest(row))
        rows.append(row)


computer_fields = [
    "computer_suggested_label",
    "computer_secondary_labels",
    "computer_confidence",
    "computer_evidence_signals",
    "computer_reason",
]

output_fields = input_fields + computer_fields

with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=output_fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


# 为第一次人工校准构造30篇平衡样本。
random.seed(RANDOM_SEED)
groups = defaultdict(list)
for row in rows:
    groups[row["computer_suggested_label"]].append(row)

for group in groups.values():
    random.shuffle(group)

target_quota = {
    "A": 4,
    "B": 4,
    "C": 4,
    "D": 3,
    "E": 3,
    "R": 3,
    "X": 4,
    "U": 5,
}

review_rows = []
selected_ids = set()

for label, quota in target_quota.items():
    for row in groups.get(label, [])[:quota]:
        review_rows.append(row)
        selected_ids.add(row.get("sample_id"))

if len(review_rows) < 30:
    remaining = [row for row in rows if row.get("sample_id") not in selected_ids]
    random.shuffle(remaining)
    review_rows.extend(remaining[: 30 - len(review_rows)])

random.shuffle(review_rows)

with open(FIRST_REVIEW_CSV, "w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=output_fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(review_rows[:30])


label_counts = Counter(row["computer_suggested_label"] for row in rows)
review_counts = Counter(row["computer_suggested_label"] for row in review_rows[:30])

print("电脑预标完成")
print(f"完整预标文件：{OUTPUT_CSV}")
print(f"首批人工核对文件：{FIRST_REVIEW_CSV}")

print("\n500篇建议标签分布：")
for label in "ABC DERXU".replace(" ", ""):
    print(f"  {label}: {label_counts[label]}")

print("\n首批30篇建议标签分布：")
for label in "ABC DERXU".replace(" ", ""):
    print(f"  {label}: {review_counts[label]}")

print("\n注意：computer_*列只是电脑建议；人工结论填写在 primary_label 等人工标注列。")
