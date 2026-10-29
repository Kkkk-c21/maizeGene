# -*- coding: utf-8 -*-
"""PlantKG 玉米文献分级 v1：低内存、保留原始数据、先试运行再全量。

默认输入：玉米相关文献_全库初筛_v1.csv（已初筛保留的约7.8万条）。
分级只表示“下一步审查优先级/证据候选类型”，不是已验证的基因功能结论。

用法：
  python plantkg_literature_grade_v1.py --mode pilot
  python plantkg_literature_grade_v1.py --mode full
  python plantkg_literature_grade_v1.py --mode pilot --input "D:\\other\\file.csv"
  python plantkg_literature_grade_v1.py --mode pilot --input "sample.zip" --out-dir "results"

不依赖第三方包；按行读取，标准 CSV 或单 CSV 的 ZIP 均支持。
"""
from __future__ import annotations
import argparse
import contextlib
import csv
import hashlib
import io
import json
import random
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

VERSION = "plantkg_literature_grade_v1.0"
DEFAULT_INPUT = Path(r"D:\cyq\maizeGene\maize_literature\01_数据\02_清洗数据\玉米文献_全库初筛_v1_完整结果\玉米相关文献_全库初筛_v1.csv")
DEFAULT_OUTPUT = Path(r"D:\cyq\maizeGene\maize_literature\04_运行状态\玉米已保留文献分级_v1")

# 少量审核线索，不是完整词典；基于题名/摘要的规则不会证明因果关系。
MAIZE = re.compile(r"\b(?:maize|zea\s+mays|z\.?\s*mays|corn)\b", re.I)
MAIZE_GENE_ID = re.compile(r"\b(?:Zm00001[de]b\d{6}|GRMZM\d+G\d+|Zm[A-Za-z0-9][\w:;.-]{1,24})\b")
GENE_FOCUS = re.compile(r"\b(?:gene|genes|genetic|genetics|genome|genomic|transcript|promoter|allele|locus|loci|protein|transcription factor|mutant|mutation|rna[- ]?seq)\b", re.I)
ASSAY = re.compile(r"\b(?:CRISPR|gene[- ]edit(?:ing|ed)|knock[- ]?(?:out|down)|overexpress(?:ion|ed|ing)?|loss[- ]of[- ]function|gain[- ]of[- ]function|complementation|transgenic|silenc(?:ing|ed)|RNAi|mutant|mutants|protein[- ]protein interaction|reporter assay|yeast two[- ]hybrid|electrophoretic mobility shift|EMSA|enzyme activity|subcellular locali[sz]ation)\b", re.I)
TRAIT = re.compile(r"\b(?:phenotype|trait|yield|kernel|grain|seed|flowering|plant height|root|tassel|ear|stress|drought|salt|disease resistance|tolerance|starch content|protein content|tocopherol)\b", re.I)
RESULT = re.compile(r"\b(?:regulat(?:e|es|ed|es)|control(?:s|led)|required for|affect(?:ed|s)?|increas(?:e|ed|es)|decreas(?:e|ed|es)|enhanc(?:e|ed|es)|reduc(?:e|ed|es)|conferr?\w*|alter(?:ed|s)?|contribut(?:e|es|ed)|showed|resulted in|involved in|interact(?:ion|s|ed)|associated with)\b", re.I)
ASSOCIATION = re.compile(r"\b(?:GWAS|genome[- ]wide association|QTL|association mapping|linkage analysis|fine mapping|eQTL|differential(?:ly)? expressed|transcriptom\w*|RNA[- ]seq|co[- ]expression|proteom\w*|metabolom\w*)\b", re.I)
COMPUTATIONAL = re.compile(r"\b(?:ortholog|homolog|paralog|phylogen|in silico|bioinformatic|domain analysis|motif analysis|comparative genomics|functional annotation|sequence analysis)\w*", re.I)
RESOURCE = re.compile(r"\b(?:database|knowledge graph|knowledgebase|atlas|pan[- ]genome|pangenome|genome assembly|genome sequence|reference genome|gene catalog|web portal|gene network|genomic resource|data resource)\b", re.I)
REVIEW = re.compile(r"\b(?:review|perspective|meta[- ]analysis|overview|recent advances|current progress)\b", re.I)
MATERIAL = re.compile(r"\b(?:stover|stalk|silage|biofuel|biomass|feed|diet|feeding|food|processing|ethanol production|starch extraction|packaging|fermentation|digestibility|corn oil|corn syrup|corn flour|corn meal|corn starch|zein film)\b", re.I)
HOMONYM = re.compile(r"\b(?:corn snake|corn poppy|corn salad|corn cockle|foot corn|corns on the foot)\b", re.I)
NONMAIZE_FOCUS = re.compile(r"\b(?:human patients?|Arabidopsis thaliana|Oryza sativa|Triticum aestivum|Gossypium|Vitis vinifera|COVID[- ]19|SARS[- ]CoV[- ]2)\b", re.I)
OTHER_SPECIES_TITLE = re.compile(
    r"\b(?:sorghum|rice|wheat|barley|cotton|pepper|potato|tomato|arabidopsis|"
    r"oat|oats|tef|sugarcane|aven[a]?\s+sativa|betula|paspalum|"
    r"fusarium|ustilago|aspergillus|colletotrichum|bipolaris|chaetomium|"
    r"spodoptera|fungal pathogen|mycorrhizal fungi)\b", re.I
)
MAIZE_SPECIFIC_GENE = re.compile(r"\b(?:maize|zea mays|corn)\s+(?:gene|genes|allele|protein|locus|mutant|genome|transcriptome|transcription factor)\b", re.I)

OUTPUT_FIELDS = [
 "grade_v1_tier", "grade_v1_legacy_candidate", "grade_v1_maize_relevance", "grade_v1_decision",
 "grade_v1_evidence_signal", "grade_v1_heterologous_risk", "grade_v1_support_excerpt", "grade_v1_reason",
 "grade_v1_verification", "grade_v1_rule_version",
]


def sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])|\n+", text.strip())[:100]


def matches(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(text))


def snippet(text: str, max_chars=240) -> str:
    text = " ".join(text.split())
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


STUDIED_MAIZE = re.compile(
    r"\b(?:in|from|using|among|of|on|within|between|for)\s+(?:the\s+)?(?:maize|zea\s+mays)\b|"
    r"\bmaize\s+(?:genes?|genome|mutants?|plants?|lines?|cultivars?|accessions?|hybrids?|"
    r"seedlings?|kernels?|tissues?|roots?|leaves|transcriptome|genotypes?|populations?|proteins?|"
    r"expression|samples?|germplasm|genetic|phenotyp|genomic|breeding|diversity)\b|"
    r"\b(?:studied|evaluated|tested|sequenced|analyzed|analysed|investigated|measured|used|"
    r"collected|examined|characterized|characterised)\s+(?:the\s+)?(?:maize|zea\s+mays)\b",
    re.I,
)


def grade(row: dict[str, str]) -> dict[str, str]:
    title = str(row.get("title") or row.get("英文题名") or "").strip()
    abstract = str(row.get("abstract") or row.get("英文摘要") or "").strip()
    joined = title + ". " + abstract
    parts = sentences(abstract or title)
    maize = matches(MAIZE, joined)
    maize_title = matches(MAIZE, title)
    named = matches(MAIZE_GENE_ID, joined)
    named_title = matches(MAIZE_GENE_ID, title)
    specific_gene = named or matches(MAIZE_SPECIFIC_GENE, joined)
    gene = matches(GENE_FOCUS, joined)
    assoc = matches(ASSOCIATION, joined)
    assay = matches(ASSAY, joined)
    trait = matches(TRAIT, joined)
    material_title = matches(MATERIAL, title)
    resource_title = matches(RESOURCE, title)
    review_title = matches(REVIEW, title)
    comput = matches(COMPUTATIONAL, joined)
    homonym = matches(HOMONYM, title) and not named
    other_title = matches(NONMAIZE_FOCUS, title) or matches(OTHER_SPECIES_TITLE,title)

    # 研究对象必须有证据：摘要单纯出现 maize 不足以推断其为研究材料。
    maize_study_sentence = next((part for part in parts if matches(STUDIED_MAIZE, part)), "")
    maize_is_subject = maize_title or named_title or bool(maize_study_sentence)
    # For generic titles, maize must be linked to molecular evidence in a sentence,
    # rather than simply appearing in introductory examples.
    specific_study_evidence = bool(next((part for part in parts if matches(STUDIED_MAIZE, part)
        and matches(GENE_FOCUS, part) and (matches(ASSOCIATION, part) or matches(ASSAY, part)
        or matches(COMPUTATIONAL,part))), ""))
    # 标题明确以非玉米物种为对象时，不因摘要中的泛泛提及就升为核心。
    if other_title and not maize_title and not named_title:
        maize_is_subject = False
    cues = []
    for label, val in [("玉米明示",maize),("玉米基因标识",named),("题名明确玉米",maize_title),
                       ("基因分子研究",gene),("功能实验用语",assay),("性状用语",trait),
                       ("关联组学",assoc),("计算同源",comput),("资源",resource_title),
                       ("综述",review_title),("材料主题",material_title)]:
        if val:
            cues.append(label)
    experiment_sentence = next((part for part in parts if matches(ASSAY,part) and
                                (matches(RESULT,part) or matches(MAIZE_GENE_ID,part))), "")
    trait_sentence = next((part for part in parts if matches(TRAIT,part) and
                           (matches(RESULT,part) or matches(ASSOCIATION,part))), "")
    association_sentence = next((part for part in parts if matches(ASSOCIATION,part)), "")
    evidence = experiment_sentence or trait_sentence or association_sentence or next((part for part in parts if matches(MAIZE_GENE_ID,part)), "") or title

    if homonym and not matches(MAIZE_SPECIFIC_GENE, abstract):
        tier, legacy, relevance, decision = "X_明确异义", "X", "非玉米", "排除候选"
        reason = "题名中的corn是其他事物的名称，并非玉米作物。"
    elif not title and not abstract:
        tier, legacy, relevance, decision = "U_缺失信息", "U", "不能判断", "暂缓复核"
        reason = "题名和摘要均缺失，不能推断研究对象。"
    elif not maize and not named:
        tier, legacy, relevance, decision = "U_关联待核", "U", "未见直接玉米证据", "暂缓复核"
        reason = "现有元数据缺少玉米研究证据，不直接删掉可能因全文命中而被初筛保留的记录。"
    elif not maize_is_subject:
        tier, legacy, relevance, decision = "U_跨物种边界", "U", "玉米可能仅为背景", "暂缓复核"
        reason = "论文研究主体尚不能确认是玉米，或题名明确以其他物种为对象；即使摘要出现玉米也不归入玉米核心功能。"
    elif not abstract:
        tier, legacy, relevance, decision = "U_缺失摘要", "U", "主题可能相关但证据不足", "暂缓复核"
        reason = "题名有玉米相关线索但摘要缺失；没有确认实验结果，暂不赋A/B等证据标签。"
    elif (resource_title or review_title) and gene and not (named_title and assay):
        if resource_title:
            tier, legacy, relevance, decision = "P5_数据资源", "E?", "玉米功能资源相关", "辅助候选"
            reason = "资源类论文可用于获取注释和数据，不能直接当功能实验。"
        else:
            tier, legacy, relevance, decision = "P5_综述背景", "R?", "玉米功能综述相关", "辅助候选"
            reason = "综述用于追踪原始证据，不应作为独立功能验证计数。"
    elif material_title and not (named_title and assay):
        tier, legacy, relevance, decision = "P6_玉米相关辅助", "—", "玉米材料/加工应用", "辅助候选"
        reason = "标题偏材料、食品、加工、饲料或生物质，不等于玉米内源基因功能研究。"
    elif specific_gene and assay and experiment_sentence and (maize_title or named_title or matches(STUDIED_MAIZE,experiment_sentence)):
        tier, legacy, relevance, decision = "P1_直接功能实验候选", "A?", "玉米基因直接实验线索", "核心候选"
        reason = "玉米基因对象与实验结果线索同时存在；仍须查验实验物种、对照、功能方向与原始文献。"
    elif specific_gene and trait and trait_sentence and (maize_title or named_title):
        tier, legacy, relevance, decision = "P2_基因性状候选", "B?", "玉米基因—性状候选", "核心候选"
        reason = "具体玉米基因/等位基因与性状线索相联系；不能据此推断因果已证明。"
    elif assoc and (gene or trait) and maize_is_subject and (maize_title or named_title or specific_study_evidence):
        tier, legacy, relevance, decision = "P3_遗传关联组学", "C?", "玉米组学/遗传关联", "核心候选"
        reason = "玉米研究中存在GWAS/QTL/表达或其他组学线索，尚不是直接功能验证。"
    elif (comput or specific_gene) and gene and maize_is_subject and (maize_title or named_title or specific_study_evidence):
        tier, legacy, relevance, decision = "P4_计算同源注释", "D?", "玉米计算注释/基因分析", "核心候选"
        reason = "玉米基因、序列或计算注释线索，需核实是否为玉米基因、同源推断还是原始实验。"
    else:
        tier, legacy, relevance, decision = "P6_玉米相关辅助", "—", "玉米相关但非明确基因功能", "辅助候选"
        reason = "能够确认玉米参与研究，但未发现可用于直接功能断言的具体基因证据。"

    verification = ("不纳入候选，但保存原始记录及原因" if decision == "排除候选" else
                    "优先补摘要/物种信息，再决定是否入库" if decision == "暂缓复核" else
                    "核对基因ID、实验物种、证据原句、关联与因果边界" if decision == "核心候选" else
                    "作为资料索引；如需提取功能结论先核对原文")
    return {
        "grade_v1_tier": tier,
        "grade_v1_legacy_candidate": legacy,
        "grade_v1_maize_relevance": relevance,
        "grade_v1_decision": decision,
        "grade_v1_evidence_signal": ";".join(cues),
        "grade_v1_heterologous_risk": ("题名出现非玉米实验物种；谨防把异源表达表型当作玉米植株中的直接功能验证"
            if named_title and other_title else ""),
        "grade_v1_support_excerpt": snippet(evidence),
        "grade_v1_reason": reason,
        "grade_v1_verification": verification,
        "grade_v1_rule_version": VERSION,
    }


@contextlib.contextmanager
def source_reader(path: Path):
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            members = [m for m in zf.namelist() if m.lower().endswith(".csv")]
            if len(members) != 1:
                raise ValueError("ZIP应当只包含一个CSV，实际发现: " + str(members))
            with zf.open(members[0]) as raw:
                with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as stream:
                    yield csv.DictReader(stream)
    else:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            yield csv.DictReader(stream)


def field_limit():
    lim = sys.maxsize
    while True:
        try:
            csv.field_size_limit(lim)
            return
        except OverflowError:
            lim //= 10


def row_hash(row):
    return hashlib.sha256((str(row.get("source_record_key", "")) + "|" + str(row.get("title", ""))).encode("utf-8")).hexdigest()[:12]


def process(input_path: Path, out_dir: Path, mode: str, sample_size: int, seed: int, pilot_scan_rows: int):
    field_limit()
    if not input_path.is_file():
        raise FileNotFoundError(f"找不到输入文件: {input_path}")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"输出目录不是空目录，为防止覆盖已拒绝运行: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    reservoir, targeted = [], []
    rows_seen = 0
    counters = Counter()
    decisions = Counter()
    outputs = {}
    summary_file = None
    try:
        with source_reader(input_path) as reader:
            original_fields = list(reader.fieldnames or [])
            if not {"title", "abstract"}.issubset(original_fields):
                raise ValueError("输入CSV必须包含title和abstract两列，实际字段: " + str(original_fields))
            combined_fields = original_fields + [f for f in OUTPUT_FIELDS if f not in original_fields]
            if mode == "full":
                for code, name in [("核心候选", "核心基因功能候选.csv"), ("辅助候选", "玉米相关辅助.csv"),
                                   ("暂缓复核", "信息不足待核.csv"), ("排除候选", "本轮排除.csv")]:
                    fp = (out_dir / name).open("x", encoding="utf-8-sig", newline="")
                    writer = csv.DictWriter(fp, fieldnames=combined_fields)
                    writer.writeheader()
                    outputs[code] = (fp, writer)
            for row in reader:
                rows_seen += 1
                g = grade(row)
                merged = dict(row)
                merged.update(g)
                counters[g["grade_v1_tier"]] += 1
                decisions[g["grade_v1_decision"]] += 1
                if mode == "full":
                    outputs[g["grade_v1_decision"]][1].writerow(merged)
                else:
                    # 统一随机reservoir抽样，固定种子；附带优先候选抽样供人工检查。
                    if len(reservoir) < sample_size:
                        reservoir.append(merged)
                    else:
                        pos = rng.randrange(rows_seen)
                        if pos < sample_size:
                            reservoir[pos] = merged
                    if g["grade_v1_decision"] == "核心候选":
                        if len(targeted) < 40:
                            targeted.append(merged)
                        else:
                            # Core events are more likely; maintain independent reservoir for manual check.
                            targeted_seen = counters["P1_直接功能实验候选"] + counters["P2_基因性状候选"] + counters["P3_遗传关联组学"] + counters["P4_计算同源注释"]
                            pos = rng.randrange(targeted_seen)
                            if pos < 40:
                                targeted[pos] = merged
                    if rows_seen >= pilot_scan_rows:
                        break
            if mode == "pilot":
                sample_path = out_dir / "随机抽样_分级结果.csv"
                with sample_path.open("x", encoding="utf-8-sig", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=combined_fields)
                    w.writeheader()
                    w.writerows(reservoir)
                targeted_path = out_dir / "核心候选加测_40条.csv"
                with targeted_path.open("x", encoding="utf-8-sig", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=combined_fields)
                    w.writeheader()
                    w.writerows(targeted)
        report = {
            "version": VERSION,
            "mode": mode,
            "input": str(input_path),
            "source_rows_scanned": rows_seen,
            "total_assigned": sum(counters.values()),
            "decision_counts": dict(decisions),
            "tier_counts": dict(counters),
            "pilot_scan_limit": pilot_scan_rows if mode == "pilot" else None,
            "pilot_sampling_scope": "只在输入CSV前N条中随机抽样，若源文件按日期排序则不代表全库随机样本。" if mode == "pilot" else None,
            "pilot_random_rows": len(reservoir) if mode == "pilot" else None,
            "pilot_targeted_core_rows": len(targeted) if mode == "pilot" else None,
            "sample_seed": seed if mode == "pilot" else None,
            "method_limitation": "启发式题名/摘要分级，不是逐篇全文审查；A?/B?/C?/D?等不是已核实的功能真值；任何自动排除均只从候选集排除，源文件不修改。",
        }
        with (out_dir / "分级统计报告.json").open("x", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        for fh, _ in outputs.values():
            fh.close()


def main():
    parser = argparse.ArgumentParser(description="玉米功能文献分级：先抽样试运行，验证后才全库处理")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mode", choices=["pilot", "full"], default="pilot")
    parser.add_argument("--sample-size", type=int, default=240)
    parser.add_argument("--pilot-scan-rows", type=int, default=5000, help="试运行最多扫描的记录数；全量运行时无此限制")
    parser.add_argument("--seed", type=int, default=20261029)
    args = parser.parse_args()
    if not 1 <= args.sample_size <= 5000:
        parser.error("--sample-size必须在1到5000之间")
    if args.pilot_scan_rows < args.sample_size:
        parser.error("--pilot-scan-rows必须大于等于--sample-size")
    process(args.input, args.out_dir, args.mode, args.sample_size, args.seed, args.pilot_scan_rows)

if __name__ == "__main__":
    main()
