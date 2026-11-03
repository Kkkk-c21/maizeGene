#!/usr/bin/env python3
import csv,json,re,collections,datetime
from pathlib import Path
csv.field_size_limit(100_000_000)
root=Path('outputs/MaizeGene_task1_2')
src=Path('inputs/分类前清洗表_主表.csv')
base=root/'paper_classification.csv'
out=root/'paper_classification_no_api.csv'
queue=root/'manual_review_queue_no_api.csv'
stats_path=root/'task1_2_statistics.json'
with src.open(encoding='utf-8-sig',newline='') as sf, base.open(encoding='utf-8-sig',newline='') as bf:
    source=csv.DictReader(sf); rules=csv.DictReader(bf)
    fields=list(rules.fieldnames or [])+['review_priority','review_priority_label','manual_review_status','classification_state','rule_supporting_quotes']
    status_counts=collections.Counter(); label_counts=collections.Counter(); quote_misses=0; n=0
    with out.open('w',encoding='utf-8-sig',newline='') as of, queue.open('w',encoding='utf-8-sig',newline='') as qf:
        writer=csv.DictWriter(of,fieldnames=fields,extrasaction='ignore'); writer.writeheader()
        qwriter=csv.DictWriter(qf,fieldnames=fields,extrasaction='ignore'); qwriter.writeheader()
        for srow,rrow in zip(source,rules):
            n+=1
            title=srow.get('title') or ''; abstract=srow.get('abstract') or ''
            labels=[x for x in (rrow.get('rule_candidate_labels') or '').split(';') if x]
            core=any(x in {'A','B','C','D','E'} for x in labels)
            st=rrow.get('rule_screen_status','')
            if core:
                p,label='P1','核心证据关键词候选'
            elif st=='review_candidate':
                p,label='P2','综述关键词候选'
            elif 'X_candidate' in labels:
                p,label='P3','非核心主题词候选'
            else:
                p,label='P4','未命中规则，待分流'
            quotes=[]
            for hit in (rrow.get('rule_trigger_terms') or '').split(';'):
                if ':' not in hit: continue
                tag,term=hit.split(':',1)
                if tag not in {'A','B','C','D','E','R'}: continue
                found=False
                for field,text in [('title',title),('abstract',abstract)]:
                    m=re.search(re.escape(term),text,re.I)
                    if m:
                        lo=max(0,m.start()-90); hi=min(len(text),m.end()+90)
                        quotes.append({'label':tag,'term':term,'source_text_type':field,'supporting_text':text[lo:hi]})
                        found=True; break
                if found: continue
                quote_misses+=1
            if not quotes and 'X_candidate' in labels:
                for term in (rrow.get('noncore_context_terms') or '').split(';'):
                    if not term: continue
                    for field,text in [('title',title),('abstract',abstract)]:
                        m=re.search(re.escape(term),text,re.I)
                        if m:
                            lo=max(0,m.start()-90); hi=min(len(text),m.end()+90)
                            quotes.append({'label':'X_candidate','term':term,'source_text_type':field,'supporting_text':text[lo:hi]})
                            break
                    if quotes: break
            rrow.update({
                'review_priority':p,
                'review_priority_label':label,
                'manual_review_status':'待人工核验',
                'classification_state':'仅规则候选，非最终分类',
                'rule_supporting_quotes':json.dumps(quotes[:6],ensure_ascii=False)
            })
            writer.writerow(rrow); qwriter.writerow(rrow)
            status_counts[p]+=1; label_counts.update(labels)
        if next(source,None) is not None or next(rules,None) is not None:
            raise RuntimeError('Source and rule result row counts differ.')
summary=json.loads(stats_path.read_text(encoding='utf-8'))
summary['no_api_mode']={'enabled':True,'generative_model_calls':0,'rows':n,'priority_counts':dict(status_counts),'quote_match_misses':quote_misses,'rule_labels_final':False}
summary['no_api_output']=str(out.resolve())
summary['manual_review_queue']=str(queue.resolve())
stats_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
report=root/'quality_report_no_api.md'
q=summary['quality_counts']; d=summary['duplicates']; N=n
fmt=lambda n: f'{n:,} ({n/N:.2%})' if N else str(n)
lines=[
'# MaizeGene Task 1–2 无 API 运行报告','',
'## 运行方式','',
'本版本未调用任何外部生成式模型 API。规则标签是关键词候选，不是最终证据判断。原始主表只读，未删除或合并任何记录。','',
'## Task 1：输入核查','',
'- 实际记录数：72,467条；预期参考数78,456条，少5,989条。按当前指定主表范围处理，未从其他表补行。',
'- 实际字段：26列；UTF-8 BOM编码；逗号分隔。',
'- 标题缺失：'+fmt(q['title_missing']),
'- 摘要缺失：'+fmt(q['abstract_missing']),
'- DOI缺失：'+fmt(q['doi_missing']),
'- PMID缺失：'+fmt(q['pmid_missing']),
'- DOI/PMID规范化重复：0组。',
'- 标题精确重复：'+str(d['title_exact']['duplicate_groups'])+'组；NFKC、忽略大小写和空白后的重复：'+str(d['title_normalized_nfkc_casefold_whitespace']['duplicate_groups'])+'组。仅统计，不去重。','',
'## Task 2：全表规则候选与复核队列','',
'已对全部72,467条标题和完整摘要运行高召回词项筛选。候选命中不代表文献确实提供该类玉米基因证据。所有标签都保留人工核验状态。','',
'|优先级|含义|记录数|','|---|---|---:|'
]
for p,desc in [('P1','A–E核心证据关键词候选'),('P2','综述关键词候选'),('P3','非核心主题词候选'),('P4','未命中规则，待分流')]: lines.append(f"|{p}|{desc}|{status_counts[p]:,}|")
lines+=['','候选标签可多选。`X_candidate`、`U_candidate`仅为队列建议，不等同于最终X/U。P4未命中关键词不代表没有基因证据。当前规则依赖标题和摘要中的词项，不能可靠辨别物种指向、研究设计或因果关系。','',
'## 输出文件','',
'- `paper_classification_no_api.csv`：72,467条候选标签、原文触发片段、处理状态和人工复核优先级。',
'- `manual_review_queue_no_api.csv`：相同记录，附P1–P4复核排序。',
'- `task1_2_statistics.json`：机器可读质量和规则统计。',
'- `maizegene_task1_2.py`、`augment_maizegene_no_api.py`：可复跑的本地脚本。','',
'若要形成可用于训练的最终A–E标签，仍需人工核验候选并抽查未命中记录；本版本没有调用API，也没有将规则候选当作金标准。']
report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'rows':n,'priority_counts':dict(status_counts),'quote_match_misses':quote_misses,'outputs':[str(out),str(queue),str(report)]},ensure_ascii=False,indent=2))
