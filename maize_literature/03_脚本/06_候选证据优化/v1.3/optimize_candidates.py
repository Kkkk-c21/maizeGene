import csv, re, io, zipfile, glob, collections, json, hashlib, os, html, argparse
from pathlib import Path
csv.field_size_limit(10000000)
ROOT=Path(__file__).resolve().parents[3]/'01_数据'
parser=argparse.ArgumentParser(description='MaizeGene无API候选质量分级；保留原字段和人工决定')
parser.add_argument('--candidates',default=str(ROOT/'outputs/maizegene_review_batch2/gene_trait_evidence_candidates_v1_2_reviewed.csv'))
parser.add_argument('--papers-zip',default=str(ROOT/'downloads/opt/MaizeGene_任务1至3_无API规则初筛_v1.4.zip'))
parser.add_argument('--gene-reference',default=str(ROOT/'downloads/opt/neo4j_query_table_data_2026-11-2(1).csv'))
parser.add_argument('--output',default=str(ROOT/'outputs/maizegene_candidates_v1_3'))
args=parser.parse_args();SRC=Path(args.candidates);ZIP=Path(args.papers_zip);GENE=Path(args.gene_reference);OUT=Path(args.output);OUT.mkdir(parents=True,exist_ok=True)
def clean(s):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',s or ''))).strip()
def has(p,s):return bool(re.search(p,s,re.I))
def token(g,s):return bool(re.search(r'(?<![\w-])'+re.escape(g)+r'(?![\w-])',s,re.I))
def load(p):
 with open(p,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
rows=load(SRC); genes=load(GENE); ids={g['gene_id'] for g in genes}; alias=collections.defaultdict(set)
for g in genes:
 for name in [g['gene_id'],g['symbol']]+g['aliases'].split(';'):
  name=name.strip()
  if name and re.fullmatch(r'[A-Za-z0-9_.-]+',name):alias[name].add(g['gene_id'])
needed={r['source_row'] for r in rows}; papers={}
with zipfile.ZipFile(ZIP) as z:
 with io.TextIOWrapper(z.open('papers_master_v1_4.csv'),encoding='utf-8-sig') as f:
  for p in csv.DictReader(f):
   if p['source_row'] in needed:papers[p['source_row']]=p
traits={'drought tolerance':'耐旱性','drought resistance':'耐旱性','drought tolerant':'耐旱性','salt tolerance':'耐盐性','salinity tolerance':'耐盐性','cold tolerance':'耐冷性','heat tolerance':'耐热性','yield':'产量','grain production':'籽粒产量','flowering':'开花','flowering time':'开花时间','plant height':'株高','height':'株高','germination':'萌发','plant growth':'植株生长','biomass':'生物量','biomass accumulation':'生物量积累','root growth':'根系生长','root length':'根长','root biomass':'根系生物量','root architecture':'根系构型','kernel weight':'籽粒重量','grain weight':'籽粒重量','kernel size':'籽粒大小','kernel number':'籽粒数量','starch biosynthesis':'淀粉生物合成','starch accumulation':'淀粉积累','starch content':'淀粉含量','starch quality':'淀粉品质','oil content':'含油量','disease resistance':'抗病性','insect resistance':'抗虫性','insect resistant':'抗虫性','vegetative growth':'营养生长','grain quality':'籽粒品质','nue':'氮利用效率','nitrogen use efficiency':'氮利用效率'}
perturb=r'overexpress\w*|knockout\w*|knock[- ]?down\w*|silenc\w*|loss.of.function|gene.edit\w*|crispr|mutant\w*|mutation\w*|complementation|rna interference'
effects=r'enhanc\w*|increas\w*|reduc\w*|decreas\w*|improv\w*|delay\w*|accelerat\w*|promot\w*|confer\w*|toleran\w*|resistan\w*|regulat\w*|affect\w*|impair\w*|result\w*|lead\w*|exhibit\w*'
spec=r'\bmay\b|\bmight\b|\bcould\b|\blikely\b|\bpotential\b|\bputative\b|\bcandidate\b|\bsuggest\w*|\bpossibly\b'
non_gene={'Mo17','B73','Ye478','ZD958','Chang7-2','IR64','BL21','DH4866','MP1','MP2','MP3','MP4','F2','F1'}
seen={}
for i,r in enumerate(rows,1):
 r['evidence_record_id']=f'E{i:06d}';g=r['gene_mention'];s=clean(r['supporting_text']);p=papers.get(r['source_row']);abstract=clean(p['abstract']) if p else ''
 paper_ok=bool(p and (r['pmid'] and r['pmid']==p['pmid'] or r['doi'] and r['doi'].lower()==p['doi'].lower() or clean(r['title']).casefold()==clean(p['title']).casefold()))
 literal=paper_ok and s in abstract
 r['auto_source_check']='摘要原文匹配' if literal else '来源或原文待核对'
 r['abstract']=p['abstract'] if paper_ok else ''
 reasons=[]
 current=r['gene_id']; matches=alias.get(g,set())
 if g in ids: mapped=g;mapping='精确参考ID'
 elif len(matches)==1:mapped=next(iter(matches));mapping='导出表精确唯一名称'
 elif len(matches)>1:mapped='';mapping='名称存在歧义'
 elif current and current in ids:mapped='';mapping='旧映射缺少名称支持'
 else:mapped='';mapping='部分参考表未匹配'
 r['auto_gene_id']=mapped;r['auto_mapping_status']=mapping;r['auto_mapping_candidates']=';'.join(sorted(matches))
 r['auto_mapping_source']=GENE.name;r['auto_reference_scope']=f'仅{len(ids)}个唯一基因，未确认覆盖44303全量'
 gene_ok=bool(mapped or re.fullmatch(r'Zm[A-Za-z0-9_.-]*\d[A-Za-z0-9_.-]*',g) or re.fullmatch(r'GRMZM\d+G\d+',g))
 mention_ok=token(g,s)
 # Split contrasts and separate semicolon clauses to avoid assigning a neighboring gene's trait.
 clauses=re.split(r';|\bwhereas\b|\bwhile\b|\bbut\b',s,flags=re.I)
 local=' '.join(c for c in clauses if token(g,c))
 tr=r['trait_original'];trait_present=token(tr,local)
 if tr.lower()=='yield' and has(r'yield\s+(?:of\s+)?(?:protein|rna|dna|extract)|high.yield\s+(?:expression|production)',local):trait_present=False
 if tr.lower()=='flowering' and has(r'flowering plants',local) and not has(r'flowering\s+(?:time|transition)|(?:delay|accelerat|early|late)\w*\s+flowering',local):trait_present=False
 if tr.lower()=='height' and not has(r'plant height|stature|height\s+(?:of|was|were)|(?:reduced|increased|plant)\s+height',local):trait_present=False
 if tr.lower()=='flowering' and has(r'flowering (?:stage|genes)|(?:seedling and flowering|flowering and seedling) stages',local) and not has(r'flowering time|delay\w* flowering|accelerat\w* flowering|flowering transition',local):trait_present=False
 bg=has(r'previously\s+(?:shown|reported|identified|characterized)|previous (?:research|studies|study)|has been (?:shown|reported)|have been (?:shown|reported)|known to|^background\b',local)
 host=r'arabidopsis|tobacco|nicotiana|yeast|escherichia|e\. coli|rice|oryza|wheat|tomato'
 hetero=has(host,s) and has(r'overexpress|transgenic|transform\w*|express\w*|complement',s)
 host_unclear=not hetero and has(r'(?:overexpress\w*|transgenic|transform\w*).{0,90}(?:arabidopsis|rice|tobacco|yeast)|(?:arabidopsis|rice|tobacco|yeast).{0,90}(?:overexpress\w*|transgenic|transform\w*)',abstract)
 uncertain=has(spec,local)
 expression=has(r'differentially expressed|rna.seq|q.?rt.?pcr|expression (?:patterns|profiles)|(?:up|down).regulated.{0,60}(?:stress|treatment)|(?:stress|treatment).{0,60}(?:up|down).regulated',local)
 association=has(r'associat\w*|co.localiz\w*|colocaliz\w*|qtl|gwas|linkage|e[q]?tl',local)
 gp=re.escape(g)
 direct_perturb=has(r'(?:'+perturb+r').{0,35}(?<![\w-])'+gp+r'(?![\w-])|(?<![\w-])'+gp+r'(?![\w-]).{0,30}(?:'+perturb+r')',local)
 actual_effect=has(r'enhanc\w*|increas\w*|reduc\w*|decreas\w*|improv\w*|delay\w*|accelerat\w*|promot\w*|confer\w*|impair\w*|result\w*|lead\w*|exhibit\w*|affect\w*|caus\w*',local)
 experimental=direct_perturb and actual_effect
 maize_mentions=set(re.findall(r'\bZm[A-Za-z0-9_.-]*\d[A-Za-z0-9_.-]*',local,re.I))
 multi_gene=len(maize_mentions)>1
 r['auto_relation_scope']='多基因共同或链式陈述' if multi_gene else '单基因提及或非Zm命名待限定'
 generic=has(r'\b(?:plays?|regulates?|controls?|confers?|enhances?|promotes?|increases?|reduces?|improves?|delays?|accelerates?|affects?)\b|positive regulator|negative regulator',local)
 entity_bad=(g in non_gene and (g not in {'MP1','MP2','MP3','MP4'} or has(r'population|PL#|cross',s))) or has(r'^Cas9(?:-mediated)?$',g)
 composite=has(r'-interacting|-mediated|-dependent|-Zm|/Zm|-VIGS|-VOX',g)
 # A gene family cannot be assigned one member ID or interpreted as one gene label.
 family=has(r'\b(?:gene family|these genes|family members)\b',local) and not mapped and not re.search(r'\d',g)
 r['auto_evidence_type']='unknown'
 if experimental:r['auto_evidence_type']='A候选'
 elif association:r['auto_evidence_type']='C候选' if has(r'gwas|qtl|e[q]?tl|co.localiz|colocaliz',local) else 'B候选'
 elif has(r'allele|polymorphism|natural variation',local) and has(effects,local):r['auto_evidence_type']='B候选'
 elif expression:r['auto_evidence_type']='C候选'
 elif has(r'predict\w*|homolog\w*|phylogen\w*|sequence analysis',local):r['auto_evidence_type']='D候选'
 r['auto_source_type']='背景引用' if bg else ('异源宿主实验' if hetero else '摘要研究陈述')
 r['auto_assertion_strength']='可能/候选' if uncertain else ('实验性陈述' if experimental else '关联或功能陈述')
 r['auto_effect_direction']='unknown'
 if has(r'no significant|not significantly|without altering|unaffected|did not|no effect',local):r['auto_effect_direction']='存在无显著效应或不变表述；不可直接作阳性'
 manual=r['review_status']!='待人工核验'
 if manual:
  if '排除' in r['review_status'] or '实体误识别' in r['review_status']:grade='排除';reasons.append('沿用人工排除')
  elif '待定' in r['review_status']:grade='人工待定';reasons.append('保留人工待定结论')
  else:grade='人工保留';reasons.append('沿用人工确认关系；证据类型仍需独立限定')
 elif not literal:grade='来源待核对';reasons.append('未通过对应摘要原文匹配')
 elif entity_bad:grade='规则排除';reasons.append('已知品种/群体/工具或菌株代号，非目标玉米基因')
 elif not mention_ok:grade='关系待定';reasons.append('基因提及未在原句独立匹配')
 elif not trait_present:grade='关系待定';reasons.append('该基因所在分句没有独立出现候选性状，或属于词义误触发')
 elif not gene_ok or family or composite:grade='身份待定';reasons.append('基因身份未满足唯一命名条件，或提及为家族/复合名称')
 elif bg:grade='背景证据';reasons.append('原句为已报道背景，保留但不作本研究新证据')
 elif hetero:grade='异源宿主候选';reasons.append('原句涉及异源实验，宿主性状须分开记录')
 elif host_unclear:grade='异源宿主候选';reasons.append('摘要涉及异源转化，当前原句未能独立限定实验宿主')
 elif uncertain:grade='关联探索候选';reasons.append('原句含可能、候选或推测措辞')
 elif has(r'to characterize|to determine|were obtained|to further determine',local) and not actual_effect:grade='关联探索候选';reasons.append('原句描述研究目的或实验材料，未提供明确效应结果')
 elif multi_gene and not direct_perturb:grade='关联探索候选';reasons.append('多基因共同或链式陈述，暂不拆成单基因直接功能证据')
 elif experimental or generic:grade='规则支持候选';reasons.append('基因与性状同分句且有明确实验效应或功能关系措辞')
 elif association or expression:grade='关联探索候选';reasons.append('存在关联/表达线索，未满足直接功能关系条件')
 else:grade='关系待定';reasons.append('缺少足够明确的关系措辞')
 if not literal:reasons.append('来源校验未通过，即使人工保留也不自动进入导出可用集')
 if uncertain:reasons.append('不提升为因果功能阳性')
 r['auto_quality_group']=grade;r['auto_quality_reason']='；'.join(dict.fromkeys(reasons))
 original_trait=r['trait_normalized'] if manual else tr
 r['auto_trait_normalized']=traits.get(original_trait.lower(),original_trait)
 key=(r['paper_id'],g.lower(),r['auto_trait_normalized'].lower(),s.lower())
 r['duplicate_of']=seen.get(key,'');seen.setdefault(key,r['evidence_record_id'])
 usable=literal and not r['duplicate_of'] and grade in ('人工保留','规则支持候选') and not entity_bad
 r['auto_usable_candidate']='是' if usable else '否'
 r['strict_training_positive']='否：仍需基因映射和证据等级确认'
 r['auto_rule_version']='candidate_quality_v1.3'
def write(name,rs):
 with open(OUT/name,'w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rs)
write('gene_trait_evidence_candidates_v1_3_optimized.csv',rows)
usable=[r for r in rows if r['auto_usable_candidate']=='是']
write('usable_candidates_v1_3.csv',usable)
write('mapped_usable_candidates_v1_3.csv',[r for r in usable if r['auto_gene_id']])
write('association_background_heterologous_v1_3.csv',[r for r in rows if r['auto_quality_group'] in ('关联探索候选','背景证据','异源宿主候选')])
write('unresolved_candidates_v1_3.csv',[r for r in rows if r['auto_quality_group'] in ('人工待定','来源待核对','关系待定','身份待定')])
write('excluded_candidates_v1_3.csv',[r for r in rows if r['auto_quality_group'] in ('排除','规则排除')])
summary={'input_rows':len(rows),'paper_count':len({r['paper_id'] for r in rows}),'reference_rows':len(genes),'reference_unique_genes':len(ids),'source_match':sum(r['auto_source_check']=='摘要原文匹配' for r in rows),'quality_groups':dict(collections.Counter(r['auto_quality_group'] for r in rows)),'mapping_status':dict(collections.Counter(r['auto_mapping_status'] for r in rows)),'duplicate_rows':sum(bool(r['duplicate_of']) for r in rows),'usable_rows':len(usable),'usable_papers':len({r['paper_id'] for r in usable}),'usable_gene_mentions':len({r['gene_mention'] for r in usable}),'mapped_usable_rows':sum(bool(r['auto_gene_id']) for r in usable),'mapped_usable_genes':len({r['auto_gene_id'] for r in usable if r['auto_gene_id']}),'usable_evidence_suggestions':dict(collections.Counter(r['auto_evidence_type'] for r in usable)),'input_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest()}
(OUT/'statistics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
