"""补充交付统计、字段字典及独立核验，再构建最终压缩包；不重新扫描文献。"""
import argparse, collections, csv, hashlib, json, re, shutil, subprocess, sys, zipfile
from pathlib import Path
import run_continuation as core

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default=str(core.ROOT/'delivery_v1_0'));args=ap.parse_args()
    out=Path(args.output);stats=json.loads((out/'statistics.json').read_text(encoding='utf-8'))
    evidence=core.load(out/'gene_trait_evidence.csv');labels=core.load(out/'gene_trait_labels.csv')
    byid={r['evidence_record_id']:r for r in evidence}
    exclusion_audit=[]
    for r in labels:
        e=byid[r['evidence_record_id']]
        for k in ['mapping_status','mapping_reference_verified','mapping_source','condition_text','source_text_type','relation_scope','supplemental_method','supplemental_finding','direction_basis','direction_scope']:
            r[k]=e.get(k,'')
        reasons=[]
        if 'R' in re.split('[;,| ]+',e['original_classification']):reasons.append('原文献R综述/汇总，不能作为独立本研究训练证据')
        if e['gene_mention'].casefold() in {'mrna','rrna','trna','cdna','rnai','gfp','gus'}:reasons.append('通用分子/报告工具提及，不是可唯一识别玉米基因')
        r['review_or_entity_exclusion_flag']=bool(reasons)
        if reasons:
            r['label']='unlabeled';r['training_usable']=False
            r['training_exclusion_reason']='；'.join(filter(None,[r['training_exclusion_reason']]+reasons))
            exclusion_audit.append(dict(evidence_record_id=r['evidence_record_id'],gene_mention=e['gene_mention'],paper_id=r['paper_id'],original_classification=e['original_classification'],reason='；'.join(reasons),action='训练排除；保留原证据/人工结论；非人工确认'))
    if exclusion_audit:core.save(out/'training_exclusion_audit.csv',exclusion_audit)
    previous_strict=stats['strict_positive_relations']
    stats['strict_positive_relations']=sum(str(r['training_usable']).lower()=='true' for r in labels)
    core.jwrite(out/'statistics.json',stats)
    baseline=core.load(out/'baseline_status.csv')
    for r in baseline:r['strict_positive_relations']=stats['strict_positive_relations']
    core.save(out/'baseline_status.csv',baseline)
    core.save(out/'gene_trait_labels.csv',labels)
    # 清楚区分可审阅候选、唯一参考映射和严格训练门槛，避免将这些数混用。
    new=[r for r in evidence if r['candidate_source']=='incremental_title_abstract_scan']
    def true(v):return str(v).lower()=='true'
    mapped=lambda rs:len({r['resolved_gene_id'] for r in rs if true(r['mapping_reference_verified'])})
    groups=collections.Counter(r['supplemental_quality_group'] for r in new)
    metrics=[dict(stage='Task3',status='completed_rule_supplement_not_manual_validation',scanned_papers=stats['scanned_papers'],new_evidence=len(new),duplicate_events=stats['duplicate_old']+stats['duplicate_new'],usable_review_candidates=sum(r['supplemental_quality_group']=='规则支持' for r in new),strict_training_relations=stats['strict_positive_relations'],pending_records=groups['待定'],unique_reference_verified_genes=mapped(new)),
             dict(stage='Task4',status='partial_reference_5000_of_44303',scanned_papers=stats['scanned_papers'],new_evidence=len(new),duplicate_events=stats['duplicate_old']+stats['duplicate_new'],usable_review_candidates=sum(true(r['mapping_reference_verified']) for r in evidence),strict_training_relations=stats['strict_positive_relations'],pending_records=sum(not true(r['mapping_reference_verified']) for r in evidence),unique_reference_verified_genes=mapped(evidence)),
             dict(stage='Task5',status='labels_built_features_metadata_only',scanned_papers=stats['scanned_papers'],new_evidence=len(new),duplicate_events=stats['duplicate_old']+stats['duplicate_new'],usable_review_candidates=stats['old_priority_candidates']+groups['规则支持'],strict_training_relations=stats['strict_positive_relations'],pending_records=sum(r['label']=='unlabeled' for r in labels),unique_reference_verified_genes=mapped(evidence)),
             dict(stage='Task6',status='not_run_missing_auditable_biological_features',scanned_papers=stats['scanned_papers'],new_evidence=len(new),duplicate_events=stats['duplicate_old']+stats['duplicate_new'],usable_review_candidates=0,strict_training_relations=stats['strict_positive_relations'],pending_records='not_applicable',unique_reference_verified_genes=0)]
    core.save(out/'phase_statistics.csv',metrics)
    # trait_sample_statistics中的mapped_genes明确限定为参考验证，另保留语法ID覆盖。
    ts=[]
    grouped=collections.defaultdict(list)
    for r in labels:grouped[r['trait_normalized']].append(r)
    for trait,rs in sorted(grouped.items()):
        ts.append(dict(trait_normalized=trait,records=len(rs),papers=len({r['paper_id'] for r in rs}),reference_verified_genes=len({r['gene_id'] for r in rs if true(r['mapping_reference_verified'])}),syntax_or_verified_ID_genes=len({r['gene_id'] for r in rs if r['gene_id']}),strict_positive_relations=sum(true(r['training_usable']) for r in rs),strict_positive_genes=len({r['gene_id'] for r in rs if true(r['training_usable'])}),strict_positive_papers=len({r['paper_id'] for r in rs if true(r['training_usable'])}),**{k:sum(int(r['evidence_'+k]) for r in rs) for k in 'ABCD'}))
    core.save(out/'trait_sample_statistics.csv',ts)
    # 结构化原子关系之外的集合记录仍留待定，不能误认为多个训练样本。
    aggregate=[]
    pairs=collections.defaultdict(list)
    for r in labels:
        if true(r['mapping_reference_verified']):pairs[(r['gene_id'],r['trait_normalized'])].append(r)
    for (gene,trait),rs in sorted(pairs.items()):
        aggregate.append(dict(gene_id=gene,trait_normalized=trait,evidence_records=len(rs),unique_papers=len({r['paper_id'] for r in rs}),paper_ids=';'.join(sorted({r['paper_id'] for r in rs})),evidence_ids=';'.join(r['evidence_record_id'] for r in rs),observed_directions=';'.join(sorted({r['effect_direction'] for r in rs})),strict_positive_relations=sum(true(r['training_usable']) for r in rs),interpretation='方向属于原实验/等位结果；不同条件及干预不合并或自动判冲突'))
    core.save(out/'mapped_relation_summary.csv',aggregate)
    missing=[dict(resource='完整NAM-5.0 Gene参考',required='44303 unique genes with symbol/aliases/source/version',available='5000 unique genes',remaining='39303 reference genes; export provenance/version; no connection config found',affects='Task4'),
             dict(resource='历史ID转换表',required='traceable GRMZM/Zm00001d to NAM5 mappings',available='only aliases present in partial export',remaining='reliable versioned conversion table',affects='Task4'),
             *[dict(resource=f,required='gene-keyed values plus version/source and target-paper/label contamination audit',available='not found',remaining='actual feature data and provenance',affects='Task5/6') for f in ['Embedding/EmbeddingGemma','GO','ProteinDomain','KEGG','Expression']]]
    core.save(out/'missing_resources.csv',missing)
    source=Path(json.loads((out/'config.json').read_text(encoding='utf-8'))['source'])
    inventory=[dict(path=str(p),bytes=p.stat().st_size) for p in source.rglob('*') if p.is_file()]
    core.jwrite(out/'source_file_inventory.json',inventory)
    fields={
      'evidence_record_id':'旧E编号原样保留；新N+SHA256前20位内容ID。',
      'gene_mention':'原提及或分句中多个提及的分号集合；集合不展开成独立关系。',
      'gene_id':'旧证据表保留旧值，新证据记录本轮解析ID；训练请使用resolved_gene_id及mapping_reference_verified。',
      'resolved_gene_id':'本轮来源支持映射，或参考外NAM5语法ID；必须结合mapping_status解释。',
      'mapping_reference_verified':'仅当前5000参考精确ID或唯一受支持别名为True；家族/描述名不强行映射。',
      'trait_normalized':'性状或F:分子功能；分号表示多个目标仍待消歧。旧字段原样保留，auto_trait_normalized为既有标准化。',
      'supporting_text':'新证据为对应摘要的连续原文，旧证据沿用原字段；source_verified另列。',
      'evidence_type':'旧原类型保留；不能直接用作训练证据等级。',
      'relation_evidence_type':'本轮关系级保守规则建议A/B/C/D/unknown，依据见evidence_type_basis，非人工确认。',
      'review_status':'旧人工决定不改；新增为未人工复核。',
      'auto_quality_group':'仅旧证据v1.3质量分组原样保留。',
      'supplemental_quality_group':'新增规则状态；旧值沿用v1.3。规则支持仅为可审阅候选。',
      'supplemental_effect_direction':'新关系目标邻接措辞；旧关系另作保守派生。increase不等于基因正调控。',
      'experimental_host':'摘要分句明确宿主，否则unknown；异源实验不当作玉米植株验证。',
      'training_usable':'严格规则门槛而非人工确认：需映射、原文、关系级A/B、单基因、宿主和明确非无效应方向。',
      'label':'positive_relation或unlabeled；没有自动阴性。',
      'gene_features.parquet':'5000行身份元数据及真实缺失标记，模型特征全部缺失。',
    }
    core.jwrite(out/'data_dictionary.json',fields)
    review_matches=list(source.rglob('gene_trait_evidence_candidates_v1_2_reviewed.csv'))
    assert len(review_matches)==1, '人工合并源表必须唯一'
    source_review=core.load(review_matches[0])
    old=[r for r in evidence if r['candidate_source']!='incremental_title_abstract_scan']
    keys=['paper_id','source_row','gene_mention','review_status','manual_note','manual_decision','supporting_text']
    assert len(old)==len(source_review)==3214
    assert all(all(a.get(k)==b.get(k) for k in keys) for a,b in zip(old,source_review))
    assert all(r['source_text_type']=='abstract' for r in new)
    assert all(r['label']=='unlabeled' for r in labels if r['effect_direction'] in ['unknown','no_significant_effect','mixed_or_opposite'])
    assert all(not true(r['training_usable']) for r in labels if r['quality_group'] in ['人工待定','待定','背景','异源宿主','排除','规则排除'])
    counts=collections.Counter(r['source_row'] for r in new)
    coverage=core.load(out/'paper_supplement_coverage.csv')
    # 如新增精确重复被移除，以最终交付计数为准，保留原命中数另列。
    for r in coverage:
        r['new_evidence_before_incremental_dedup']=r['new_evidence'];r['new_evidence']=counts[r['source_row']]
    core.save(out/'paper_supplement_coverage.csv',coverage)
    exact_groups=collections.defaultdict(list)
    for r in coverage:exact_groups[r['original_classification']].append(r)
    detailed=[]
    for category,rs in sorted(exact_groups.items()):
        source_rows={r['source_row'] for r in rs};es=[e for e in new if e['source_row'] in source_rows]
        detailed.append(dict(original_classification=category,scanned_papers=len(rs),new_papers=sum(int(r['new_evidence'])>0 for r in rs),new_evidence=len(es),duplicate_old=sum(int(r['duplicate_old']) for r in rs),rule_supported=sum(e['supplemental_quality_group']=='规则支持' for e in es),pending=sum(e['supplemental_quality_group']=='待定' for e in es),unique_reference_verified_genes=mapped(es)))
    core.save(out/'original_category_statistics.csv',detailed)
    verification=json.loads((out/'delivery_validation.json').read_text(encoding='utf-8'))
    verification.update(reviewed_source_3214_rows_preserved=True,manual_pending_8_preserved=True,new_evidence_abstract_only=True,unknown_and_no_effect_not_negative=True,coverage_count_matches_evidence=sum(counts.values())==len(new))
    core.jwrite(out/'delivery_validation.json',verification)
    extra=f'''\n## 最终交付复核补充\n\n人工合并源表与最终旧记录的paper_id、source_row、gene_mention、review_status、manual_note、manual_decision、supporting_text逐行一致，共3,214条；原8条人工待定保持。新增证据全部来自摘要，标题只作检索提示。\n\n参考别名含有部分描述词及酶家族简称，本轮对明确的描述/家族提及保留未解决状态，避免以表内唯一性替代单基因实体确认；mapping_candidates仍保留来源候选。\n\nphase_statistics.csv提供各阶段实际统计；Task4可用数指参考已验证映射记录数，Task5候选数不等于训练阳性。trait_sample_statistics.csv分别列出参考验证基因数、仅语法或已验证ID数及严格门槛的基因/论文数。mapped_relation_summary.csv用于识别跨论文重复关系，保留每条证据，不合并不同条件/方向。original_category_statistics.csv保留原多标签类别逐类统计；分层总表中含任一A-D标签的论文归A-D，其余为X/E/R/U，避免多标签论文重复累计。\n\n本次共发现{len(pairs)}个参考已验证的gene-target组合；可用生物学特征基因数仍为0，未运行基线。数据不足的实际缺项列于missing_resources.csv；不提供空预测文件或占位指标。源码中主流程生成基础包，随后运行python finalize_delivery.py --output <输出目录>执行本补充核验并重新打包。\n'''
    report=out/'quality_report.md';text=report.read_text(encoding='utf-8').split('\n## 最终交付复核补充')[0]
    text=text.replace(f'严格规则门槛可用关系：{previous_strict}条',f"严格规则门槛可用关系：{stats['strict_positive_relations']}条")
    extra+='\ntraining_exclusion_audit.csv追加综述汇总及通用分子/报告工具提及的训练排除依据，只增加训练门禁，不修改原人工结论。R的含义复用既有classification_rules_v1_4.md第21行，不以文献标签提升关系确认等级。\n'
    report.write_text(text+extra,encoding='utf-8')
    test=subprocess.run([sys.executable,'-m','unittest','test_rules','-v'],cwd=core.ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (out/'rule_tests.log').write_bytes(test.stdout)
    assert test.returncode==0, '规则回归检查失败，见rule_tests.log'
    shutil.copy2(core.ROOT/'test_rules.py',out/'test_rules.py')
    shutil.copy2(core.ROOT/'run_pipeline.py',out/'run_pipeline.py')
    readme=out/'README.md'
    readme.write_text(readme.read_text(encoding='utf-8')+'\n推荐运行：python run_pipeline.py --source <原材料目录> --output <新输出目录>。先安装requirements.txt；本项目已将PyArrow安装在.runtime，启动脚本会在导入Pandas前加载该依赖。\n',encoding='utf-8')
    shutil.copy2(Path(__file__),out/'finalize_delivery.py')
    files=[p for p in out.iterdir() if p.is_file() and p.name not in ['manifest.json','archive_validation.json']]
    core.jwrite(out/'manifest.json',[dict(file=p.name,bytes=p.stat().st_size,sha256=core.digest(p)) for p in sorted(files)])
    archive=out.parent/(out.name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[out/'manifest.json']:z.write(p,p.name)
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(m['file'])).hexdigest()==m['sha256'] for m in manifest)
        required=['papers_master.csv','paper_classification.csv','gene_trait_evidence.csv','gene_id_mapping.csv','gene_trait_labels.csv','gene_features.parquet','quality_report.md']
        assert all(n in z.namelist() and z.getinfo(n).file_size>0 for n in required)
    core.jwrite(out/'archive_validation.json',dict(archive=str(archive),sha256=core.digest(archive),testzip='passed',all_entry_hashes_match=True,seven_nonempty_primary_files=True,entry_count=len(files)+1))
    print(json.dumps(dict(phase_statistics=metrics,archive=str(archive),archive_bytes=archive.stat().st_size,verification=verification),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
