"""MAIZEGENE 增量证据补查。仅读取本地材料，不调用API或修改数据库。"""
import argparse, collections, csv, hashlib, json, logging, re, shutil, sys, zipfile
from pathlib import Path

VERSION = 'supplement_v1.0'
csv.field_size_limit(20_000_000)
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.runtime'))
import pandas as pd

def load(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def save(path, rows, columns=None):
    rows = list(rows)
    if columns is None:
        columns = list(dict.fromkeys(k for r in rows for k in r))
    if not columns:
        return
    temp = path.with_suffix(path.suffix + '.tmp')
    with open(temp, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)
    temp.replace(path)

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def jwrite(path, obj):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def hit(pattern, text): return bool(re.search(pattern, text, re.I))
def norm(text): return re.sub(r'\s+', ' ', text).strip().casefold()
def ident(parts): return 'N' + hashlib.sha256('\x1f'.join(parts).encode()).hexdigest()[:20]

# 每组首项为标准化名称，其余是原文词组；功能与植株性状分别编码。
TRAITS = {
 '耐旱性': ['drought tolerance','drought resistance','drought survival','water deficit tolerance'],
 '耐盐性': ['salt tolerance','salinity tolerance','salt resistance'],
 '耐冷性': ['cold tolerance','chilling tolerance','freezing tolerance'],
 '耐热性': ['heat tolerance','thermotolerance'],
 '抗病性': ['disease resistance','pathogen resistance','southern leaf blight resistance','smut resistance'],
 '抗虫性': ['insect resistance','herbivore resistance'],
 '干旱响应': ['drought stress','water deficit'], '盐胁迫响应': ['salt stress','salinity stress'],
 '低温响应': ['cold stress','chilling stress'], '高温响应': ['heat stress'],
 '氧化胁迫响应': ['oxidative stress'], '淹水响应': ['waterlogging','flooding tolerance','submergence tolerance'],
 '营养胁迫响应': ['phosphate starvation','phosphate deficiency','nitrogen deficiency','low nitrogen tolerance'],
 '金属胁迫响应': ['cadmium tolerance','aluminum tolerance','aluminium tolerance'],
 '开花时间': ['flowering time','flowering transition','floral transition'],
 '株高': ['plant height','plant stature'], '叶角': ['leaf angle'],
 '根系构型': ['root architecture','root system architecture'], '根长': ['root length'],
 '根系发育': ['root development','root growth','lateral root formation','crown root development'],
 '叶片发育': ['leaf development','leaf morphology','leaf senescence'],
 '分蘖': ['tillering','tiller number'], '穗发育': ['ear development','inflorescence development','tassel development'],
 '花发育': ['floral development','flower development'], '雄性育性': ['male fertility','male sterility','pollen development','anther development'],
 '胚发育': ['embryo development','embryogenesis'], '胚乳发育': ['endosperm development'],
 '种子发育': ['seed development','kernel development'], '种子萌发': ['seed germination','germination rate','seed dormancy'],
 '籽粒重量': ['kernel weight','grain weight','100-kernel weight','hundred-kernel weight'],
 '籽粒大小': ['kernel size','grain size','kernel thickness','kernel length','kernel width'],
 '籽粒数量': ['kernel number','grain number'], '产量': ['grain yield','yield traits','yield improvement'],
 '生物量': ['biomass accumulation','biomass production','shoot biomass','root biomass'],
 '植株生长': ['plant growth','vegetative growth','seedling growth'],
 '籽粒品质': ['grain quality','kernel quality'], '含油量': ['oil content','lipid content'],
 '淀粉含量': ['starch content','starch accumulation'], '蛋白含量': ['protein content'],
 '糖含量': ['sugar content','sucrose content'], '木质素含量': ['lignin content'],
 '氮利用效率': ['nitrogen use efficiency'], '磷吸收': ['phosphate uptake','phosphorus uptake'],
 '光合作用': ['photosynthetic efficiency','photosynthesis','chlorophyll content'],
 '细胞壁形成': ['cell wall formation','cell wall biosynthesis'],
 '气孔调节': ['stomatal closure','stomatal opening','stomatal development'],
 '抗倒伏': ['lodging resistance','stalk strength'],
 'F:转录调控': ['transcriptional regulation','transcriptional activation','transcriptional repression','transcription factor activity'],
 'F:DNA结合': ['DNA binding','DNA-binding','binds to the promoter','binding to the promoter'],
 'F:蛋白互作': ['protein interaction','protein-protein interaction','interacts with','interacted with'],
 'F:磷酸化': ['phosphorylation','kinase activity','phosphatase activity'],
 'F:泛素化': ['ubiquitination','ubiquitylation','ubiquitin ligase activity'],
 'F:转运': ['transporter activity','ion transport','auxin transport','nitrate transport','sugar transport'],
 'F:激素信号': ['auxin signaling','abscisic acid signaling','ABA signaling','gibberellin signaling','ethylene signaling','brassinosteroid signaling','jasmonate signaling'],
 'F:激素合成': ['auxin biosynthesis','gibberellin biosynthesis','ABA biosynthesis','ethylene biosynthesis'],
 'F:代谢': ['starch biosynthesis','lipid biosynthesis','lignin biosynthesis','anthocyanin biosynthesis','carotenoid biosynthesis','benzoxazinoid biosynthesis','flavonoid biosynthesis','sucrose metabolism'],
 'F:染色质调控': ['histone modification','DNA methylation','chromatin remodeling'],
 'F:RNA加工': ['RNA splicing','RNA editing','RNA processing'],
 'F:细胞过程': ['cell division','cell proliferation','cell elongation','programmed cell death','autophagy'],
 'F:亚细胞定位': ['localized to the nucleus','localized in the nucleus','localized to the plasma membrane','localized in chloroplasts'],
 'F:酶活性': ['enzyme activity','enzymatic activity','catalytic activity'],
}
PERT = r'overexpress\w*|knock[- ]?out\w*|knock[- ]?down\w*|silenc\w*|loss.of.function|CRISPR|mutant\w*|complementation|RNA interference|gene editing'
RESULT = r'enhanc\w*|increas\w*|reduc\w*|decreas\w*|improv\w*|delay\w*|accelerat\w*|promot\w*|confer\w*|impair\w*|resulted|led to|exhibit\w*|affect\w*|caus\w*|regulat\w*|control\w*|required for|essential for|interact\w*|binds?\b|catalyz\w*|phosphorylat\w*|localized|no significant|not significantly'
ASSOC = r'associat\w*|GWAS|\bQTL\b|eQTL|co.localiz\w*|linkage mapping'
EXPR = r'differential\w* express\w*|expression (?:level|pattern|profil)|up.regulat\w*|down.regulat\w*|RNA.seq|transcriptom\w*|co.expression'
COMP = r'homolog\w*|phylogen\w*|in silico|predict\w*|sequence analysis|molecular docking'
SPEC = r'\bmay\b|\bmight\b|\bcould\b|putative|potential|candidate|suggest\w*|hypothes\w*'
BG = r'previous(?:ly)? (?:studies|study|report\w*|shown|identified|characterized)|has been (?:shown|reported)|have been (?:shown|reported)|known to'
NAM = re.compile(r'Zm00001eb\d{6}')
GENE_PATTERN = re.compile(r'(?<![\w-])(?:Zm00001(?:eb|d)\d{6}|GRMZM\d+G\d+|AC\d+\.\d+_FG\d+|Zm[A-Za-z][A-Za-z0-9_.-]*\d[A-Za-z0-9_.-]*|Zm[A-Z][A-Za-z0-9_.-]{1,20})(?![\w-])')
BAD = {'B73','B104','Mo17','H95','F1','F2','BL21','DH5alpha','Cas9','CRISPR','RNA','DNA','PCR','qPCR','QTL','GWAS','ABA','NIL','NILs','ROS','ATP','SNP','SNPs','MAPK','MAP4K','H2O2','CO2','O2','H2','C4','C3'}
GENERIC_ENTITIES={'pal','della','sdr','pod','agpase','sod','atpase','ppiase','prx','hmg','bhlh','pepck','fbpase','gstl','gstu','abcg','acp','op r','mRNA','mapk','map4k'}

def generic_entity(name):
    return name.casefold() in GENERIC_ENTITIES or (not re.search(r'\d',name) and not name.startswith('Zm') and len(name)>5 and name.islower())

def build_reference(genes):
    aliases = collections.defaultdict(set)
    for r in genes:
        for name in [r['gene_id'], r['symbol']] + r['aliases'].split(';'):
            name = name.strip()
            if name and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*', name) and name not in BAD:
                aliases[name].add(r['gene_id'])
    return aliases

def map_gene(mention, aliases, ids, reference_name):
    matches = sorted(aliases.get(mention, set()))
    if generic_entity(mention):gid,method,status='','generic_entity_not_single_gene','unresolved_entity_scope'
    elif mention in ids: gid, method, status = mention, 'exact_NAM5_reference_ID', 'resolved'
    elif len(matches) == 1: gid, method, status = matches[0], 'exact_source_supported_alias', 'resolved'
    elif len(matches) > 1: gid, method, status = '', 'exact_alias_multiple', 'ambiguous'
    elif NAM.fullmatch(mention): gid, method, status = mention, 'NAM5_ID_syntax_only_outside_reference', 'unresolved_reference_membership'
    else: gid, method, status = '', 'no_supported_match', 'unresolved'
    return dict(resolved_gene_id=gid, mapping_status=status, mapping_method=method,
                mapping_source=reference_name if matches or mention in ids else 'none',
                mapping_candidates=';'.join(matches), reference_scope=f'{len(ids)}/44303; partial',
                mapping_reference_verified=status == 'resolved')

def make_extractors(aliases, old):
    # 旧提及仅扩充检索词典，不赋予身份确认；可疑普通名称须有gene/protein邻接语境。
    names = set(aliases) | {r['gene_mention'] for r in old}
    names = {n for n in names if n not in BAD and not generic_entity(n) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{1,35}', n)}
    lex = re.compile(r'(?<![\w-])(?:'+'|'.join(re.escape(n) for n in sorted(names, key=lambda x:(-len(x),x)))+r')(?![\w-])')
    terms = {term.lower(): key for key, terms in TRAITS.items() for term in terms}
    tr = re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(t) for t in sorted(terms, key=lambda x:(-len(x),x)))+r')(?!\w)', re.I)
    return lex, tr, terms

def genes_in(text, lex):
    found = {m.group() for m in GENE_PATTERN.finditer(text)} | {m.group() for m in lex.finditer(text)}
    # 新命名补充：仅在明确gene/protein邻接时识别非Zm的含数字符号。
    for m in re.finditer(r'\b([A-Za-z][A-Za-z0-9_.-]*\d[A-Za-z0-9_.-]*)\s+(?:gene|protein|mutant)\b', text): found.add(m.group(1))
    if hit(r'gene|protein|mutant|allele|encod|homolog|overexpress',text):
        found.update(m.group() for m in re.finditer(r'\b[A-Za-z]{2,}\d+[a-zA-Z0-9.]*\b',text))
    found={re.sub(r'-(?:overexpress\w*|OE|KO|RNAi|mutant\w*)$','',g,flags=re.I).rstrip('-.') for g in found}
    return sorted(g for g in found if g not in BAD and not generic_entity(g) and not g.endswith(('-mediated','-dependent','-interacting')))

def scoped_direction(text, traits, normalized):
    if len(traits)!=1 or normalized.endswith('响应'): return 'unknown'
    target=re.escape(traits[0])
    if hit(r'(?:no significant|not significantly|no effect|unaffected).{0,45}'+target,text):return 'no_significant_effect'
    up=hit(r'(?:increas\w*|enhanc\w*|improv\w*|promot\w*|accelerat\w*)\s+(?:[\w-]+\s+){0,3}'+target,text)
    down=hit(r'(?:decreas\w*|reduc\w*|impair\w*|delay\w*|inhibit\w*)\s+(?:[\w-]+\s+){0,3}'+target,text)
    if up and down:return 'mixed_or_opposite'
    return 'increase_or_promote' if up else ('decrease_or_inhibit' if down else 'unknown')

def annotations(text, gene, all_genes):
    multi = len(all_genes) != 1
    methods = []
    for label, pattern in [('gene_perturbation',PERT),('genetic_association',ASSOC),('expression_or_omics',EXPR),('computation_or_homology',COMP),('protein_interaction',r'yeast two.hybrid|pull.down|co.immunoprecipitation|BiFC'),('binding_assay',r'EMSA|ChIP|electrophoretic mobility|luciferase assay')]:
        if hit(pattern,text): methods.append(label)
    bg = hit(BG,text)
    hosts = [h for h,p in [('Arabidopsis',r'Arabidopsis'),('Nicotiana/tobacco',r'Nicotiana|tobacco'),('yeast',r'yeast'),('E. coli',r'Escherichia|E\. coli'),('rice',r'\brice\b|Oryza'),('wheat',r'\bwheat\b'),('tomato',r'\btomato\b')] if hit(p,text)]
    hetero = bool(hosts) and hit(r'overexpress|transgenic|transform|express|complement|two.hybrid',text)
    direction = 'unknown'
    if hit(r'no significant|not significantly|unaffected|no effect|did not (?:alter|affect|change)|without (?:altering|affecting)',text): direction='no_significant_effect'
    else:
        up = hit(r'\b(?:increas\w*|enhanc\w*|improv\w*|promot\w*|accelerat\w*)\b', text)
        down = hit(r'\b(?:decreas\w*|reduc\w*|impair\w*|delay\w*|inhibit\w*)\b', text)
        # 多目标或多基因不将句子方向赋给单关系。
        if up and down: direction='mixed_or_opposite'
        elif not multi and up: direction='increase_or_promote'
        elif not multi and down: direction='decrease_or_inhibit'
    et='unknown'; basis='缺少关系级明确方法，未继承文献分类'
    if hit(EXPR,text) and not hit(PERT,text): et='C';basis='本分句表达/组学措辞'
    elif hit(ASSOC,text): et='C' if hit(r'GWAS|\bQTL\b|eQTL|co.localiz|linkage mapping',text) else 'B';basis='本分句遗传关联措辞'
    elif hit(PERT,text) and hit(RESULT,text): et='A';basis='本分句干预与结果措辞；候选级'
    elif hit(r'yeast two.hybrid|pull.down|co.immunoprecipitation|BiFC|EMSA|ChIP|electrophoretic mobility',text) and hit(RESULT,text): et='A';basis='本分句直接蛋白/结合实验措辞；候选级'
    elif hit(COMP,text): et='D';basis='本分句同源/计算措辞'
    uncertain=hit(SPEC,text)
    if multi: group='待定';reason='多基因/符号共同或链式陈述，未展开笛卡尔积'
    elif bg: group='背景';reason='既往研究措辞'
    elif hetero: group='异源宿主';reason='本句涉及异源表达/实验，不能认作玉米植株表型'
    elif uncertain or et in ('B','C','D'): group='关联探索';reason='关联/预测/候选措辞'
    elif et=='A': group='规则支持';reason='单基因分句含直接实验和结果；非人工确认'
    else: group='待定';reason='方法/关系未充分明确'
    if hit(r'to (?:test|determine|investigate|examine|characterize|elucidate)|aim(?:ed)? to',text):
        group='待定';reason+='；含研究目的，不能仅凭方法词确认结果'
    return dict(relation_evidence_type=et,evidence_type_basis=basis, supplemental_method=';'.join(methods) or 'unknown',
        supplemental_finding=text if hit(RESULT+'|'+ASSOC+'|'+EXPR,text) else 'unknown',
        supplemental_effect_direction=direction, direction_basis=text if direction!='unknown' else 'unknown',
        direction_scope='observed_intervention_or_allele_outcome; not gene benefit',
        study_context='background' if bg else 'current_study_or_unspecified',
        species='Zea mays' if gene.startswith(('Zm','GRMZM')) or hit(r'\bmaize\b|Zea mays',text) else 'unknown',
        experimental_host=';'.join(hosts) if hetero else ('Zea mays' if hit(r'(?:maize|Zea mays).{0,35}(?:mutant|transgenic)|(?:mutant|transgenic).{0,35}(?:maize|Zea mays)',text) else 'unknown'),
        heterologous_host_flag=hetero, supplemental_quality_group=group, quality_basis=reason,
        relation_scope='multiple_genes_unresolved' if multi else 'single_gene_clause',
        condition_text=text, manual_notes='')

def scan_paper(p, lex, tr, terms, existing, aliases, ids, refname):
    result=[]; duplicates=0; hits=0
    pid=p.get('pmid') or p.get('doi') or p['source_row']
    # 标题用于检索提示；证据原文只从对应摘要连续切片生成。
    for source in ['abstract']:
        # 分隔符仍保留在完整原句中；supporting_text直接取原始字符串切片。
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z])',p[source]):
            clauses=re.split(r';|\bwhereas\b|\bwhile\b|\bbut\b',sentence, flags=re.I)
            for text in clauses:
                text=text.strip()
                if not hit(RESULT+'|'+ASSOC+'|'+EXPR+'|'+COMP,text): continue
                gs=genes_in(text,lex)
                ts=list(dict.fromkeys(m.group() for m in tr.finditer(text)))
                if not gs or not ts: continue
                hits+=1
                # 只生成一个分句断言，多基因或多目标以集合保存，留待关系消歧。
                gene=';'.join(gs); trait=';'.join(ts)
                normalized=';'.join(dict.fromkeys(terms[t.lower()] for t in ts))
                oldmatch=[existing.get((p['source_row'],norm(g),norm(t),norm(s)), '') for g in gs for t in ts for s in [sentence,text]]
                if len(gs)==1 and len(ts)==1 and any(oldmatch): duplicates+=1;continue
                a=annotations(text,gene,gs)
                a['supplemental_effect_direction']=scoped_direction(text,ts,normalized) if len(gs)==1 else 'unknown'
                a['direction_basis']=text if a['supplemental_effect_direction']!='unknown' else 'unknown'
                if any(hit(r'\([^)]*'+re.escape(t)+r'[^)]*\)',text) for t in ts):
                    a['supplemental_quality_group']='待定';a['quality_basis']+='；目标在括号说明中，需核对是否真实研究断言'
                if len(ts)>1:
                    a['supplemental_quality_group']='待定'; a['quality_basis']+='；多个功能/性状尚未逐一绑定'
                    a['supplemental_effect_direction']='unknown';a['direction_basis']='unknown'
                m=map_gene(gene,aliases,ids,refname)
                r=dict(paper_id=pid,source_row=p['source_row'],doi=p.get('doi',''),pmid=p.get('pmid',''),title=p['title'],
                    gene_mention=gene,gene_id=m['resolved_gene_id'],trait_original=trait,trait_normalized=normalized,
                    method=a['supplemental_method'],finding=a['supplemental_finding'],effect_direction=a['supplemental_effect_direction'],
                    evidence_type=a['relation_evidence_type'],supporting_text=text,source_text_type=source,
                    review_status='新增规则候选；未人工复核',evidence_record_id=ident([p['source_row'],source,gene,normalized,text]),
                    candidate_source='incremental_title_abstract_scan',rule_version=VERSION,
                    original_classification=p.get('candidate_evidence_labels',''), source_verified=text in p[source],
                    trait_domain='mixed' if any(t.startswith('F:') for t in normalized.split(';')) and any(not t.startswith('F:') for t in normalized.split(';')) else ('molecular_function' if normalized.startswith('F:') else 'plant_trait'),
                    prior_overlap_ids=';'.join(sorted(set(x for x in oldmatch if x))),original_gene_members=';'.join(gs),**a,**m)
                result.append(r)
    return result,duplicates,hits

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',default=str(ROOT.parents[1]/'01_数据'));ap.add_argument('--output',default=str(ROOT/'delivery_v1_0'));ap.add_argument('--batch-size',type=int,default=1000);args=ap.parse_args()
    source=Path(args.source);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    cache=out/'cache';cache.mkdir(exist_ok=True)
    logging.basicConfig(filename=out/'execution.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',encoding='utf-8')
    def locate(name):
        matches=sorted(source.rglob(name))
        if len(matches)!=1:
            raise ValueError(f'{name}: expected exactly one local input, found {len(matches)}; use --source with one input version')
        return matches[0]
    master=locate('papers_master_v1_4.csv')
    classification=locate('paper_classification_v1_4.csv')
    optimized=locate('gene_trait_evidence_candidates_v1_3_optimized.csv')
    reviewed=locate('gene_trait_evidence_candidates_v1_2_reviewed.csv')
    ref=locate('neo4j_query_table_data_2026-11-2(1).csv')
    inputs=[master,classification,optimized,reviewed,ref]
    hashes={str(p):digest(p) for p in inputs}
    config=dict(version=VERSION,source=str(source),batch_size=args.batch_size,traits=TRAITS,inputs=hashes,script_sha256=digest(Path(__file__)))
    jwrite(out/'config.json',config)
    fingerprint=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()[:16]
    old=load(optimized);genes=load(ref);ids={g['gene_id'] for g in genes};aliases=build_reference(genes)
    lex,tr,terms=make_extractors(aliases,old)
    shutil.copy2(master,out/'papers_master.csv');shutil.copy2(classification,out/'paper_classification.csv')
    existing={}
    for r in old:
        for trait in [r['trait_original'],r.get('trait_normalized',''),r.get('auto_trait_normalized','')]:
            existing[(r['source_row'],norm(r['gene_mention']),norm(trait),norm(r['supporting_text']))]=r['evidence_record_id']
    oldpapers={r['source_row'] for r in old}
    new=[];coverage=[];errors=[];paper_lookup={};batch=[]
    def process(batch,index):
        path=cache/f'{fingerprint}_{index:04d}.json'
        if path.exists():
            data=json.loads(path.read_text(encoding='utf-8'));logging.info('reuse batch %s',index)
        else:
            data={'evidence':[],'coverage':[],'errors':[]}
            for p in batch:
                try:
                    rows,dups,hits=scan_paper(p,lex,tr,terms,existing,aliases,ids,ref.name)
                    labels=p.get('candidate_evidence_labels','')
                    stratum='A-D' if any(x in {'A','B','C','D'} for x in re.split('[;,| ]+',labels)) else 'X/E/R/U_or_other'
                    data['evidence'].extend(rows)
                    data['coverage'].append(dict(source_row=p['source_row'],paper_id=p.get('pmid') or p.get('doi') or p['source_row'],original_classification=labels,scan_stratum=stratum,had_prior_candidates=p['source_row'] in oldpapers,title_scanned=True,title_gene_hint=';'.join(genes_in(p['title'],lex)),abstract_scanned=True,hit_clauses=hits,duplicate_old=dups,new_evidence=len(rows),scan_status='success'))
                except Exception as e:
                    logging.exception('paper %s',p['source_row']);data['errors'].append(dict(source_row=p['source_row'],error=repr(e)))
            jwrite(path,data)
        new.extend(data['evidence']);coverage.extend(data['coverage']);errors.extend(data['errors'])
        print(f'batch {index}: scanned={len(coverage)} new={len(new)} errors={len(errors)}',flush=True)
    with open(master,encoding='utf-8-sig',newline='') as f:
        for p in csv.DictReader(f):
            paper_lookup[p['source_row']]={'title':p['title'],'abstract':p['abstract'],'labels':p.get('candidate_evidence_labels','')}
            batch.append(p)
            if len(batch)>=args.batch_size:process(batch,len(coverage)//args.batch_size);batch=[]
        if batch:process(batch,len(coverage)//args.batch_size)
    # 同一次补查的精确重复：只去完全相同原文/基因/性状/来源。不同条件/方向原文不同，不合并。
    unique={};duplicates=[]
    for r in new:
        k=(r['source_row'],r['source_text_type'],norm(r['gene_mention']),norm(r['trait_normalized']),norm(r['supporting_text']),r['effect_direction'])
        if k in unique:duplicates.append(dict(evidence_record_id=r['evidence_record_id'],duplicate_of=unique[k]['evidence_record_id'],reason='exact_incremental_duplicate'))
        else:unique[k]=r
    new=list(unique.values())
    # 原优化字段原样保留；本轮派生字段使用独立列，不改人工结论。
    for r in old:
        p=paper_lookup.get(r['source_row'],{})
        r.update(candidate_source='v1.2_reviewed_plus_v1.3_quality',rule_version=VERSION,original_classification=p.get('labels',''),
                 source_verified=norm(r['supporting_text']) in norm(p.get('abstract','')),
                 manual_notes=r.get('manual_note',''),original_gene_members=r['gene_mention'],
                 trait_domain='plant_trait_legacy',legacy_gene_id=r['gene_id'])
        gs=genes_in(r['supporting_text'],lex)
        a=annotations(r['supporting_text'],r['gene_mention'],gs)
        a['manual_notes']=r.get('manual_note','')
        a['supplemental_quality_group']=r['auto_quality_group']
        a['quality_basis']='沿用v1.3质量字段；关系证据类型另作保守派生'
        r.update(a);r.update(map_gene(r['gene_mention'],aliases,ids,ref.name))
    combined=old+new
    save(out/'gene_trait_evidence.csv',combined)
    save(out/'new_evidence.csv',new)
    save(out/'candidate_merge.csv',combined)
    save(out/'paper_supplement_coverage.csv',coverage)
    if duplicates:save(out/'duplicate_records.csv',duplicates)
    if errors:save(out/'errors.csv',errors)
    pending=[r for r in combined if '待定' in r['supplemental_quality_group'] or '待核对' in r['supplemental_quality_group']]
    excluded=[r for r in combined if '排除' in r['supplemental_quality_group']]
    save(out/'pending_records.csv',pending);save(out/'excluded_records.csv',excluded)
    suggestions=[dict(source_row=r['source_row'],paper_id=r['paper_id'],original_classification=r['original_classification'],suggested_relation_evidence=r['relation_evidence_type'],evidence_record_id=r['evidence_record_id'],basis=r['supporting_text'],status='仅建议，不覆盖原分类或人工结论') for r in new if r['relation_evidence_type']!='unknown']
    save(out/'classification_suggestions.csv',suggestions)
    mappings={}
    for r in combined:
        key=r['gene_mention'];mappings.setdefault(key,dict(gene_mention=key,**map_gene(key,aliases,ids,ref.name),legacy_gene_ids=set(),evidence_ids=set()))
        mappings[key]['legacy_gene_ids'].add(r.get('legacy_gene_id',''));mappings[key]['evidence_ids'].add(r['evidence_record_id'])
    for m in mappings.values():
        m['legacy_gene_ids']=';'.join(sorted(x for x in m['legacy_gene_ids'] if x));m['evidence_ids']=';'.join(sorted(m['evidence_ids']))
        m['legacy_mapping_note']='旧映射仅保留溯源；训练只用resolved_gene_id及reference_verified'
    save(out/'gene_id_mapping.csv',mappings.values())
    labels=[]
    for r in combined:
        group=r['supplemental_quality_group'];et=r['relation_evidence_type'];direction=r['supplemental_effect_direction']
        reasons=[]
        if not r['mapping_reference_verified']:reasons.append('基因未获当前参考唯一验证')
        if not r['source_verified']:reasons.append('原文来源未匹配')
        if group not in ('人工保留','规则支持','规则支持候选'):reasons.append('审核/质量状态不满足')
        if et not in ('A','B'):reasons.append('非关系级A/B证据')
        if r['relation_scope']!='single_gene_clause':reasons.append('多基因关系待消歧')
        if r['study_context']=='background':reasons.append('背景引用')
        if r['heterologous_host_flag']:reasons.append('异源宿主')
        if r['experimental_host']!='Zea mays':reasons.append('玉米实验宿主未明确')
        if direction in ('unknown','no_significant_effect','mixed_or_opposite'):reasons.append('方向未知/无效应/相反结果')
        if hit(SPEC,r['supporting_text']):reasons.append('推测或候选断言')
        if ';' in r['trait_normalized']:reasons.append('多个目标尚未绑定')
        strict=not reasons
        labels.append(dict(evidence_record_id=r['evidence_record_id'],paper_id=r['paper_id'],source_row=r['source_row'],gene_mention=r['gene_mention'],gene_id=r['resolved_gene_id'],trait_original=r['trait_original'],trait_normalized=r.get('auto_trait_normalized') or r['trait_normalized'],trait_domain=r['trait_domain'],
            evidence_A=int(et=='A'),evidence_B=int(et=='B'),evidence_C=int(et=='C'),evidence_D=int(et=='D'),relation_evidence_type=et,legacy_evidence_type=r['evidence_type'],evidence_type_basis=r['evidence_type_basis'],review_status=r['review_status'],quality_group=group,effect_direction=direction,study_context=r['study_context'],experimental_host=r['experimental_host'],
            label='positive_relation' if strict else 'unlabeled',training_usable=strict,training_scope='trait_effect_relation; direction is not gene benefit',training_exclusion_reason='；'.join(reasons),label_provenance=r['candidate_source'],feature_eligible=False))
    save(out/'gene_trait_labels.csv',labels)
    trait_stats=[]
    for trait in sorted({r['trait_normalized'] for r in labels}):
        rs=[r for r in labels if r['trait_normalized']==trait]
        trait_stats.append(dict(trait_normalized=trait,records=len(rs),papers=len({r['paper_id'] for r in rs}),mapped_genes=len({r['gene_id'] for r in rs if r['gene_id']}),strict_positive_relations=sum(r['training_usable'] for r in rs),A=sum(r['evidence_A'] for r in rs),B=sum(r['evidence_B'] for r in rs),C=sum(r['evidence_C'] for r in rs),D=sum(r['evidence_D'] for r in rs)))
    save(out/'trait_sample_statistics.csv',trait_stats)
    # 实际仅有Gene节点身份元数据；不把名称或本次标签派生为可训练生物学特征。
    features=[]
    for g in genes:
        features.append(dict(gene_id=g['gene_id'],symbol=g['symbol'] or None,aliases=g['aliases'] or None,feature_source=ref.name,reference_scope='5000/44303 partial',reference_version='NAM-5.0 ID format; export version not provided',
            embedding=None,GO=None,ProteinDomain=None,KEGG=None,Expression=None,embedding_missing=True,GO_missing=True,ProteinDomain_missing=True,KEGG_missing=True,Expression_missing=True,model_feature_available=False))
    frame=pd.DataFrame(features).drop_duplicates('gene_id')
    frame.to_parquet(out/'gene_features.parquet',index=False,engine='pyarrow')
    reopened=pd.read_parquet(out/'gene_features.parquet');assert len(reopened)==len(ids)
    sourceaudit=[dict(feature=f,available_genes=0,source='not found in supplied source tree or project',target_label_contamination='not assessable: source absent',target_paper_contamination='not assessable: source absent',model_use='blocked') for f in ['Embedding','GO','ProteinDomain','KEGG','Expression']]
    save(out/'feature_source_leakage_audit.csv',sourceaudit)
    baseline=[]
    for model in ['Embedding_similarity','GO_association','supervised_or_PU_ranking']:
        for split in ['paper_group_holdout','gene_independent_holdout']:
            baseline.append(dict(model=model,split=split,status='not_run_insufficient_features',strict_positive_relations=sum(r['training_usable'] for r in labels),available_feature_genes=0,metric_value='not_computed',prediction_output='not_created',reason='缺少有来源及泄漏可审计的基因向量/GO/数值生物学特征；身份元数据不代替特征；不生成虚构指标'))
    save(out/'baseline_status.csv',baseline)
    pair_papers=collections.defaultdict(set)
    for r in labels:
        if r['gene_id']:pair_papers[(r['gene_id'],r['trait_normalized'])].add(r['paper_id'])
    leakage=dict(repeated_gene_trait_pairs_across_papers=sum(len(v)>1 for v in pair_papers.values()),background_rows=sum(r['study_context']=='background' for r in labels),split_executed=False,
        split_policy='先将同一gene-trait关系跨论文连接为分组，再论文分组留出；另做基因独立留出；划分后检查论文、关系交集，所有特征构建仅用训练数据；当前无特征，未执行划分',
        embedding_and_GO_provenance='缺失，无法证明不含目标标签/文献；禁止训练')
    jwrite(out/'leakage_audit.json',leakage)
    strata=[]
    for s in ['A-D','X/E/R/U_or_other']:
        cs=[c for c in coverage if c['scan_stratum']==s];keys={c['source_row'] for c in cs};rs=[r for r in new if r['source_row'] in keys]
        strata.append(dict(stratum=s,scanned_papers=len(cs),papers_without_prior_candidates=sum(not c['had_prior_candidates'] for c in cs),new_records=len(rs),new_papers=len({r['source_row'] for r in rs}),duplicate_old=sum(c['duplicate_old'] for c in cs),rule_supported=sum(r['supplemental_quality_group']=='规则支持' for r in rs),pending=sum(r['supplemental_quality_group']=='待定' for r in rs),unique_reference_genes=len({r['resolved_gene_id'] for r in rs if r['mapping_reference_verified']})))
    summary=dict(scanned_papers=len(coverage),scan_errors=len(errors),old_records=len(old),new_records=len(new),merged_records=len(combined),duplicate_old=sum(c['duplicate_old'] for c in coverage),duplicate_new=len(duplicates),old_priority_candidates=sum(r['auto_usable_candidate']=='是' for r in old),old_manual_pending=sum(r['auto_quality_group']=='人工待定' for r in old),new_quality_groups=dict(collections.Counter(r['supplemental_quality_group'] for r in new)),new_relation_types=dict(collections.Counter(r['relation_evidence_type'] for r in new)),mapping_status=dict(collections.Counter(r['mapping_status'] for r in combined)),unique_resolved_genes=len({r['resolved_gene_id'] for r in combined if r['mapping_reference_verified']}),new_unique_resolved_genes=len({r['resolved_gene_id'] for r in new if r['mapping_reference_verified']}),strict_positive_relations=sum(r['training_usable'] for r in labels),reference_unique_genes=len(ids),target_reference_genes=44303,feature_rows=len(reopened),model_feature_genes=0,baseline_metrics_computed=0,strata=strata)
    jwrite(out/'statistics.json',summary);save(out/'stage_statistics.csv',strata)
    # 主表/分类字节级复用及人工字段保留验证，不重做已完成的质量初检。
    assert digest(out/'papers_master.csv')==hashes[str(master)]
    assert digest(out/'paper_classification.csv')==hashes[str(classification)]
    assert len(old)==3214 and summary['old_manual_pending']==8
    assert all(r['supporting_text'] in paper_lookup[r['source_row']][r['source_text_type']] for r in new)
    assert len({r['evidence_record_id'] for r in combined})==len(combined)
    assert all(r['review_status']==q['review_status'] and r['manual_note']==q['manual_note'] for r,q in zip(old,load(optimized)))
    jwrite(out/'delivery_validation.json',dict(master_byte_identical=True,classification_byte_identical=True,legacy_review_preserved=True,new_supporting_text_exact_substring=True,stable_ids_unique=True,parquet_readback_rows=len(reopened),source_hashes_rechecked=all(digest(p)==hashes[str(p)] for p in inputs)))
    previous=optimized.parent/'quality_report.md'
    shutil.copy2(previous,out/'prior_quality_report_v1_3.md')
    report=f'''# MAIZEGENE 接续交付质量报告

日期：2026-11-03。无API、未下载文献、未重新筛选玉米相关性、未修改数据库。主表与分类字节级复用，人工决定与v1.3字段保留。

## 实际完成情况

- 扫描标题/摘要：{len(coverage):,}篇；错误：{len(errors)}；原候选：{len(old):,}条。
- 新增分句断言候选：{len(new):,}条；新旧合并：{len(combined):,}条；旧记录重复命中：{summary['duplicate_old']:,}次；新增完全重复：{len(duplicates)}条。
- 原优先候选仍为{summary['old_priority_candidates']}条，原人工待定{summary['old_manual_pending']}条。优先候选不等于已验证训练阳性。
- 新增质量组：{json.dumps(summary['new_quality_groups'],ensure_ascii=False)}。
- 新增关系类型：{json.dumps(summary['new_relation_types'],ensure_ascii=False)}。A/B/C/D只是关系级规则建议，不能当成人工证据确认。
- 已唯一映射到当前参考的合并基因：{summary['unique_resolved_genes']}个；新增候选对应{summary['new_unique_resolved_genes']}个。
- 严格规则门槛可用关系：{summary['strict_positive_relations']}条；仅指有明确实验宿主、映射、关系级方法和方向的候选，不代表增加性状或人工确认。其余保持unlabeled，没有自动负样本。

## 分层补查

| 原类别 | 扫描篇数 | 原无候选篇数 | 新增记录 | 新增论文 | 旧重复命中 | 规则支持 | 待定 | 唯一映射基因 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
'''
    for s in strata:report+='|'+'|'.join(str(s[k]) for k in ['stratum','scanned_papers','papers_without_prior_candidates','new_records','new_papers','duplicate_old','rule_supported','pending','unique_reference_genes'])+'|\n'
    report+='''
## 方法及边界

仅使用给定主表标题和摘要。保留原分类，不执行全库再分类；classification_suggestions仅为新增关系类型的建议。补查不是覆盖所有证据的保证。词典、明确Zm/历史ID、原词典提及及gene/protein邻接命名共同检索；疑似符号身份不自动确认。条件保留完整分句。

新增supporting_text是原文连续子串；分句通过分号及whereas/while/but切分。多基因、多性状不展开全组合，保存集合断言并待定；这类gene_mention的分号集合不能映射为单基因。existing overlap只作为溯源；原句新增其他目标可能形成重叠集合记录，不将它们当独立训练关系。duplicate_old统计为重复命中事件，非删除旧记录数。完全相同的原文、提及、目标和方向才合并，不跨条件和方向合并。新ID由内容哈希生成；旧E编号保持不变。

新增方向只是原句干预/等位结果措辞，并非正常基因的作用方向，尤其敲除造成降低不能解释成基因负调控。多目标方向保持unknown；相反/混合和无显著效应独立保留。未明确方法、结果、方向填unknown。表达归C，不升级为A。背景、异源宿主保守标记，未说明宿主不假设玉米。旧证据类型及质量原样保留，relation_evidence_type另列本轮保守推断，标签使用该列而非文献分类。

## 映射覆盖与缺项

只发现5,000唯一基因导出，占44,303预期范围的11.29%；缺少39,303基因完整参考、版本元数据及可靠历史ID转换表。无现成可用只读连接配置，未发起数据库连接。精确参考ID、唯一来源别名优先；歧义不选首项；参考外NAM格式ID仅记录语法匹配，不能视为参考已验证。旧gene_id原值保留，训练映射取resolved_gene_id。未匹配不表示不是基因。未联网补造别名/历史映射。

## 特征与基线

gene_features.parquet为实际5,000基因身份元数据及来源/缺失标记清单；Embedding、GO、ProteinDomain、KEGG、Expression全部缺失，不是可训练生物学特征矩阵。名称/aliases不被伪装成向量。输入目录未提供EmbeddingGemma模型、基因向量或可溯源功能/表达矩阵，本轮没有生成替代性标签文本向量。

三类基线均未运行，指标未计算、预测结果未生成。baseline_status.csv逐方法及两种留出方案说明缺项，不能把该状态表当作性能结果。GO/Embedding目标文献/标签污染因来源缺失无法核实，禁止训练。leakage_audit.json记录跨论文重复关系及排除背景的策略；真实划分尚未运行。

获得可溯源特征后，先依据trait_sample_statistics确定足够基因/论文的任务，再按论文连通分组和基因独立留出，避免同关系跨集；未知/待定不作负样本，监督须有可信阴性，否则采用PU排序并清楚说明未标记集合。相似度及排序分数不作概率。

## 复现与后续

运行：python run_continuation.py --source <原材料目录> --output <新输出目录>。依赖pandas、pyarrow（requirements.txt）。批缓存按输入SHA256、规则、脚本和批大小指纹隔离；成功批次原子写入，重跑复用缓存；错误记录execution.log及非空errors.csv，不以空文件表示成功。

七主文件齐备，但Task4全量映射、Task5生物学特征和Task6实际基线仍因缺源未完成。需要完整Gene参考/只读连接、NAM5历史ID来源表、独立于目标标签/文献的基因向量及GO/结构域/KEGG/Expression版本与来源。未要求逐条人工核验；新增歧义另表保留。此前61,596待复核和原排除文献未读取。

旧质量报告附prior_quality_report_v1_3.md；本报告补充，不覆盖旧结论。manifest.json提供文件哈希，压缩包由zipfile.testzip及解压逐文件哈希验证。
'''
    (out/'quality_report.md').write_text(report,encoding='utf-8')
    shutil.copy2(Path(__file__),out/'run_continuation.py')
    (out/'requirements.txt').write_text('pandas>=1.3\npyarrow>=10\n',encoding='utf-8')
    (out/'README.md').write_text('主文件见quality_report.md。原始数据只读。cache为批处理断点，不纳入交付包；可在本工作目录复用。原文及人工字段不覆盖。统计单位分别为文献、分句集合断言及唯一映射基因，不把集合待定拆成训练阳性。\n',encoding='utf-8')
    logging.info('completed %s',json.dumps(summary,ensure_ascii=False))
    files=[p for p in out.iterdir() if p.is_file() and p.name not in ['manifest.json','archive_validation.json']]
    manifest=[dict(file=p.name,bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(files)]
    jwrite(out/'manifest.json',manifest)
    archive=out.parent/(out.name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[out/'manifest.json']:z.write(p,p.name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for m in manifest:assert hashlib.sha256(z.read(m['file'])).hexdigest()==m['sha256']
    jwrite(out/'archive_validation.json',dict(archive=str(archive),sha256=digest(archive),testzip='passed',all_entry_hashes_match=True,entry_count=len(files)+1))
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
