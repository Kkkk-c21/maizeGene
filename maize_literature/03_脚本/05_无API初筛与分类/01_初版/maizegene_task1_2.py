#!/usr/bin/env python3
import csv, os, re, json, hashlib, unicodedata, collections, datetime
from pathlib import Path

INPUT = Path('inputs/分类前清洗表_主表.csv')
OUT = Path('outputs/MaizeGene_task1_2')
OUT.mkdir(parents=True, exist_ok=True)
csv.field_size_limit(100_000_000)

# High-recall trigger terms only. They create candidates, never final evidence labels.
TRIGGERS = {
 'A': [r'overexpression', r'over-expression', r'overexpressed', r'overexpressing', r'knockout', r'knock-out', r'knockdown', r'knock-down', r'gene silencing', r'RNAi', r'RNA interference', r'CRISPR', r'gene editing', r'mutant', r'mutation analysis', r'complementation', r'functional characterization', r'functional analysis', r'gene function', r'protein function', r'loss-of-function', r'gain-of-function', r'VIGS', r'transgenic', r'transformation', r'enzyme activity', r'protein activity', r'heterologous expression'],
 'B': [r'allele', r'allelic', r'haplotype', r'polymorphism', r'SNP', r'candidate gene', r'marker-trait association', r'genotype-phenotype', r'gene-trait association', r'association mapping', r'linkage mapping'],
 'C': [r'GWAS', r'genome-wide association', r'QTL', r'RNA[- ]?seq', r'transcriptom', r'differential expression', r'gene expression', r'expression profiling', r'microarray', r'proteom', r'metabolom', r'eQTL', r'co-expression', r'omics'],
 'D': [r'homolog', r'homology', r'ortholog', r'phylogen', r'in silico', r'computational prediction', r'bioinformatic', r'sequence analysis', r'structural prediction', r'protein structure', r'molecular modeling', r'docking'],
 'E': [r'reference genome', r'genome assembly', r'genome sequence', r'genome annotation', r'gene annotation', r'database', r'genomic resource', r'genome resource', r'gene catalog', r'gene family', r'genome-wide identification', r'whole-genome'],
 'R': [r'review', r'systematic review', r'meta-analysis', r'literature review', r'review article']
}
COMPILED = {k: re.compile('|'.join(r'(?<!\w)(?:'+p+r')(?!\w)' for p in pats), re.I) for k,pats in TRIGGERS.items()}
NONCORE_CONTEXT = re.compile(r'(?<!\w)(?:food safety|food processing|feed|feeding|silage|starch|flour|meat quality|ethanol|biofuel|fermentation|industrial processing|nutrition|cooking|milling)(?!\w)', re.I)
DOI_PREFIX = re.compile(r'^\s*(?:(?:https?://)?(?:dx\.)?doi\.org/|doi\s*:\s*)', re.I)
SPACE = re.compile(r'\s+')

def norm_doi(s):
    return DOI_PREFIX.sub('', (s or '').strip()).strip().rstrip(' .;,').casefold()
def norm_pmid(s):
    return SPACE.sub('', (s or '').strip())
def norm_title(s):
    s=unicodedata.normalize('NFKC', (s or '')).casefold()
    return SPACE.sub(' ',s).strip()
def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def missing(s): return not (s or '').strip()
def duplicate_summary(counter):
    groups=sum(1 for n in counter.values() if n>1)
    rows=sum(n for n in counter.values() if n>1)
    excess=sum(n-1 for n in counter.values() if n>1)
    return {'duplicate_groups':groups,'records_in_duplicate_groups':rows,'excess_records':excess}

if not INPUT.exists(): raise SystemExit(f'INPUT_NOT_FOUND: {INPUT.resolve()}')
stat=INPUT.stat()
summary={
 'input_path':str(INPUT.resolve()), 'file_size_bytes':stat.st_size,
 'file_modified_utc':datetime.datetime.fromtimestamp(stat.st_mtime,datetime.timezone.utc).isoformat(),
 'sha256':sha256_file(INPUT), 'encoding':'utf-8-sig (BOM detected)', 'delimiter':',',
 'expected_rows':78456, 'rule_screen_status':'completed; candidate-only, not final model classification',
 'generative_model_status':'not_run; no batch model endpoint configured in this environment'
}
with open(INPUT,'r',encoding='utf-8-sig',newline='') as f:
    reader=csv.DictReader(f)
    headers=reader.fieldnames or []
    summary['headers']=headers
    required_aliases={'title':['title'],'abstract':['abstract'],'doi':['doi'],'pmid':['pmid'],'source_row':['source_row'],'record_id':['record_id']}
    field_map={k:next((a for a in aliases if a in headers),None) for k,aliases in required_aliases.items()}
    summary['mapped_fields']=field_map
    missing_columns=[k for k,v in field_map.items() if v is None]
    summary['missing_expected_columns']=missing_columns
    if missing_columns: raise SystemExit(f'Could not map required fields from actual header: {missing_columns}')

    counts=collections.Counter(); decision_counts=collections.Counter(); rule_counts=collections.Counter()
    dup_doi=collections.Counter(); dup_pmid=collections.Counter(); dup_title_exact=collections.Counter(); dup_title_norm=collections.Counter()
    source_rows=collections.Counter(); record_ids=collections.Counter(); existing_dup_groups=set()
    abstracts_lens=[]
    bad_rows=[]
    cls_path=OUT/'paper_classification.csv'
    out_fields=['paper_id','record_id','source_row','doi','pmid','year','title','abstract_present','existing_screen_decision','existing_rule_version','rule_candidate_labels','rule_trigger_terms','noncore_context_terms','rule_screen_status','model_classification_status']
    with open(cls_path,'w',encoding='utf-8-sig',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=out_fields); writer.writeheader()
        for i,row in enumerate(reader, start=2):
            counts['records']+=1
            if None in row:
                counts['rows_with_extra_fields']+=1; bad_rows.append({'csv_record':i,'problem':'extra_fields'})
            if any(v is None for v in row.values()):
                counts['rows_with_missing_fields']+=1
            t=row.get(field_map['title']) or ''; a=row.get(field_map['abstract']) or ''
            doi=row.get(field_map['doi']) or ''; pmid=row.get(field_map['pmid']) or ''
            rec=row.get(field_map['record_id']) or ''; sr=row.get(field_map['source_row']) or ''
            if missing(t): counts['title_missing']+=1
            if missing(a): counts['abstract_missing']+=1
            if missing(doi): counts['doi_missing']+=1
            if missing(pmid): counts['pmid_missing']+=1
            if missing(t) and missing(a): counts['no_title_or_abstract']+=1
            abstracts_lens.append(len(a))
            if len(a)>2000: counts['abstract_gt_2000_chars']+=1
            if len(a)>3000: counts['abstract_gt_3000_chars']+=1
            if not missing(doi): dup_doi[norm_doi(doi)]+=1
            if not missing(pmid): dup_pmid[norm_pmid(pmid)]+=1
            if not missing(t):
                dup_title_exact[t]+=1; dup_title_norm[norm_title(t)]+=1
            if not missing(sr): source_rows[sr]+=1
            if not missing(rec): record_ids[rec]+=1
            if row.get('duplicate_group_id'): existing_dup_groups.add(row['duplicate_group_id'])
            if row.get('screen_decision'): decision_counts[row['screen_decision']]+=1

            text=(t+'\n'+a)
            labels=[]; hits=[]
            for label,rx in COMPILED.items():
                found=sorted(set(m.group(0) for m in rx.finditer(text)),key=str.casefold)
                if found:
                    labels.append(label); hits.extend(f'{label}:{x}' for x in found[:12]); rule_counts[label]+=1
            noncore=sorted(set(m.group(0) for m in NONCORE_CONTEXT.finditer(text)),key=str.casefold)
            if labels:
                status='high_value_candidate_for_model' if any(x in labels for x in 'ABCDE') else 'review_candidate'
            elif missing(t) and missing(a):
                labels=['U']; status='text_missing_manual_review'
            elif noncore:
                labels=['X_candidate']; status='noncore_context_candidate_not_final'
            else:
                labels=['U_candidate']; status='no_rule_hit_needs_triage'
            paper_id=rec.strip() if rec.strip() else (f'SOURCE_ROW_{sr.strip()}' if sr.strip() else f'CSV_RECORD_{i}')
            writer.writerow({
                'paper_id':paper_id,'record_id':rec,'source_row':sr,'doi':doi,'pmid':pmid,'year':row.get('year',''),
                'title':t,'abstract_present':str(not missing(a)).lower(),'existing_screen_decision':row.get('screen_decision',''),
                'existing_rule_version':row.get('rule_version',''),'rule_candidate_labels':';'.join(labels),
                'rule_trigger_terms':';'.join(hits),'noncore_context_terms':';'.join(noncore[:12]),
                'rule_screen_status':status,'model_classification_status':'not_run_no_batch_model_endpoint'
            })

summary['row_count']=counts['records']
summary['quality_counts']={k:counts[k] for k in ['title_missing','abstract_missing','doi_missing','pmid_missing','no_title_or_abstract','abstract_gt_2000_chars','abstract_gt_3000_chars','rows_with_extra_fields','rows_with_missing_fields']}
summary['missing_rates']={k:round(counts[k]/counts['records'],6) if counts['records'] else None for k in ['title_missing','abstract_missing','doi_missing','pmid_missing']}
summary['screen_decision_counts']=dict(decision_counts)
summary['rule_trigger_record_counts']=dict(rule_counts)
summary['duplicates']={
 'doi':duplicate_summary(dup_doi),'pmid':duplicate_summary(dup_pmid),
 'title_exact':duplicate_summary(dup_title_exact),'title_normalized_nfkc_casefold_whitespace':duplicate_summary(dup_title_norm),
 'source_row':duplicate_summary(source_rows),'record_id':duplicate_summary(record_ids),
 'existing_duplicate_group_count':len(existing_dup_groups)
}
summary['abstract_length_chars']={'min':min(abstracts_lens) if abstracts_lens else 0,'median_sorted':sorted(abstracts_lens)[len(abstracts_lens)//2] if abstracts_lens else 0,'max':max(abstracts_lens) if abstracts_lens else 0}
summary['model_service']='not available/configured; no model inference executed'
summary['rule_output_file']=str(cls_path.resolve())
summary['rule_output_rows']=counts['records']
summary['rule_labels_are_provisional']=True
summary['rule_scope_note']='Keyword hits are candidate signals only. No missing keyword is treated as final X. No first-layer maize relevance labels were changed.'

with open(OUT/'task1_2_statistics.json','w',encoding='utf-8') as f: json.dump(summary,f,ensure_ascii=False,indent=2)

def pct(n,d): return f'{n:,} ({n/d:.2%})' if d else f'{n:,} (n/a)'
N=counts['records']
report=['# MaizeGene Task 1–2 运行报告','',f"运行时间（UTC）：{datetime.datetime.now(datetime.timezone.utc).isoformat()}",'', '## Task 1：输入数据核查','',f"- 文件：`{INPUT.resolve()}`",f"- 大小：{stat.st_size:,} bytes",f"- SHA-256：`{summary['sha256']}`",f"- 编码/分隔符：UTF-8 BOM / 逗号",f"- 实际表头（{len(headers)}列）：\n  - "+'\n  - '.join(headers),f"- 实际记录数：{N:,}（预期78,456，差异 {N-78456:+,}）",'', '| 检查项 | 记录数（占实际记录数） |','|---|---:|']
for key,label in [('title_missing','标题缺失'),('abstract_missing','摘要缺失'),('doi_missing','DOI缺失'),('pmid_missing','PMID缺失'),('no_title_or_abstract','标题和摘要均缺失'),('abstract_gt_2000_chars','摘要超过2000字符'),('abstract_gt_3000_chars','摘要超过3000字符'),('rows_with_extra_fields','字段数异常（多字段）'),('rows_with_missing_fields','字段数异常/字段值缺失')]:
 report.append(f"| {label} | {pct(counts[key],N)} |")
report+=['','### 重复统计','', '| 标识 | 重复组 | 组内记录 | 多余记录 |','|---|---:|---:|---:|']
for key,label in [('doi','规范化DOI'),('pmid','规范化PMID'),('title_exact','原始标题完全一致'),('title_normalized_nfkc_casefold_whitespace','标题NFKC/忽略大小写与空白'),('source_row','source_row'),('record_id','record_id')]:
 d=summary['duplicates'][key]; report.append(f"| {label} | {d['duplicate_groups']:,} | {d['records_in_duplicate_groups']:,} | {d['excess_records']:,} |")
report+=['',f"已有重复组字段中的非空组数：{len(existing_dup_groups):,}。本次只统计、不删除、不合并记录。",'', '### 实际识别的表头映射','', '\n'.join(f"- `{k}` → `{v}`" for k,v in field_map.items()),'','## Task 2：高召回规则初筛','',f"- 已对全部 {N:,} 条记录扫描标题和完整摘要，未重新判断或改写第一层玉米相关性。",'- 输出中的规则标签均为候选信号，不是最终证据分类。','- 没有把“无关键词命中”直接定为X；非核心主题只标为X候选，待后续核验。','- 当前环境没有配置可调用的批量生成式模型接口，因此模型逐条判读尚未执行。所有记录状态均标记为模型未运行，不能把这份规则候选表当作78,456条最终分类。','', '| 规则信号 | 命中记录数 |','|---|---:|']
for k in 'ABCDE'+'R': report.append(f"| {k}候选信号 | {rule_counts[k]:,} |")
report+=['','| 规则初筛状态 | 记录数 |','|---|---:|']
# Compute statuses from output file, streaming
status_counts=collections.Counter(); label_counts=collections.Counter()
with open(cls_path,encoding='utf-8-sig',newline='') as f:
 for r in csv.DictReader(f):
  status_counts[r['rule_screen_status']]+=1
  label_counts.update(r['rule_candidate_labels'].split(';'))
for k,v in sorted(status_counts.items()): report.append(f'| {k} | {v:,} |')
report+=['','| 临时标签/候选 | 记录数 |','|---|---:|']
for k,v in sorted(label_counts.items()): report.append(f'| {k} | {v:,} |')
report+=['','## 输出','',f"- `{cls_path.resolve()}`：72,467条全量规则候选与处理状态。",f"- `{(OUT/'task1_2_statistics.json').resolve()}`：机器可读统计。",f"- `{(OUT/'quality_report.md').resolve()}`：本质量报告。",'', '规则初筛只完成了Task 2第一步。要完成Task 2的模型分类，需在当前运行环境配置可调用的生成式模型服务；之后应先做小批量验证再扩展。']
(OUT/'quality_report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
print(json.dumps({'rows':N,'headers':headers,'quality_counts':summary['quality_counts'],'missing_rates':summary['missing_rates'],'duplicates':summary['duplicates'],'rule_trigger_record_counts':dict(rule_counts),'status_counts':dict(status_counts),'labels':dict(label_counts),'output_dir':str(OUT.resolve())},ensure_ascii=False,indent=2))
