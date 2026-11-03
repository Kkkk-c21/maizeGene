#!/usr/bin/env python3
"""Conservative, no-API gene/trait sentence candidate extraction from title/abstract."""
import argparse,csv,re,json,collections
from pathlib import Path
csv.field_size_limit(50_000_000)
GENE_RE=re.compile(r'\b(?:Zm\d{2,}d\d+[A-Za-z0-9._-]*|GRMZM\d+[A-Za-z0-9._-]*|Zm[A-Za-z][A-Za-z0-9._-]{1,}|[A-Z][a-z]{1,8}\d{1,3}(?:[-.;][A-Za-z0-9]+)?|[A-Z]{2,8}\d{1,3}(?:[-.;][A-Za-z0-9]+)?)\b')
TRAITS=[
 ('flowering_time',r'\bflowering time\b|\bflowering\b|\bheading date\b'),
 ('yield',r'\byield\b|\bgrain production\b'),
 ('kernel_weight',r'\bkernel weight\b|\bgrain weight\b|\b1000.kernel weight\b'),
 ('drought_tolerance',r'\bdrought toleran(?:ce|t)\b|\bdrought resistan(?:ce|t)\b'),
 ('salt_tolerance',r'\bsalt toleran(?:ce|t)\b|\bsalinity toleran(?:ce|t)\b'),
 ('disease_resistance',r'\bdisease resistan(?:ce|t)\b|\bresistan(?:ce|t) to [\w -]+ disease\b'),
 ('insect_resistance',r'\binsect resistan(?:ce|t)\b|\bpest resistan(?:ce|t)\b'),
 ('plant_height',r'\bplant height\b|\bheight\b'),
 ('biomass',r'\bbiomass\b'),
 ('root_trait',r'\broot (?:length|architecture|growth|biomass|mechanical properties)\b'),
 ('germination',r'\bgermination\b|\bseedling vigor\b'),
 ('kernel_trait',r'\bkernel (?:size|number|composition|quality|hardness)\b|\bgrain quality\b'),
 ('starch_trait',r'\bstarch (?:content|biosynthesis|accumulation|quality)\b'),
 ('oil_trait',r'\boil content\b|\bfatty acid composition\b'),
 ('nitrogen_use_efficiency',r'\bnitrogen use efficiency\b|\bNUE\b'),
 ('abiotic_stress',r'\bheat toleran(?:ce|t)\b|\bcold toleran(?:ce|t)\b|\blead toleran(?:ce|t)\b|\baluminum toleran(?:ce|t)\b'),
 ('plant_growth',r'\bplant growth\b|\bvegetative growth\b|\bbiomass accumulation\b'),
]
TRAIT_RE=[(name,re.compile(pattern,re.I)) for name,pattern in TRAITS]
METHOD_RE=re.compile(r'\b(?:GWAS|QTL|RNA.seq|transcriptom\w*|qRT.PCR|RT.PCR|overexpress\w*|knock(?:out|down)|CRISPR|mutant\w*|complementation|RNAi|ChIP(?:.seq)?|ATAC.seq|proteom\w*|metabolom\w*|phylogen\w*|in silico|association mapping|linkage mapping|transgenic)\b',re.I)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('input',type=Path);ap.add_argument('--out',type=Path,default=Path('output_v1_4/gene_trait_evidence_candidates_v1_0.csv'));args=ap.parse_args()
 args.out.parent.mkdir(parents=True,exist_ok=True)
 counts=collections.Counter()
 fields=['paper_id','source_row','doi','pmid','title','gene_mention','gene_id','trait_original','trait_normalized','method','finding','effect_direction','evidence_type','supporting_text','source_text_type','review_status','candidate_note']
 with args.input.open('r',encoding='utf-8-sig',newline='') as fi,args.out.open('w',encoding='utf-8-sig',newline='') as fo:
  rd=csv.DictReader(fi);wr=csv.DictWriter(fo,fieldnames=fields);wr.writeheader()
  for r in rd:
   labels=[x for x in r.get('candidate_evidence_labels','').split(';') if x in {'A','B','C','D'}]
   if not labels: continue
   text=r.get('abstract','') or ''
   # Sentence snippets preserve exact original abstract wording; no generated paraphrase.
   for sent in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9(\[])',text):
    genes=list(dict.fromkeys(m.group(0) for m in GENE_RE.finditer(sent)))
    traits=[]
    for name,rgx in TRAIT_RE:
     for m in rgx.finditer(sent): traits.append((m.group(0),name))
    if not genes or not traits: continue
    methods=list(dict.fromkeys(m.group(0) for m in METHOD_RE.finditer(sent)))
    # Keep the exact sentence and mark all biological interpretation as unverified.
    for gene in genes:
     for raw,norm in dict.fromkeys(traits):
      wr.writerow({'paper_id':r.get('record_id',''),'source_row':r.get('source_row',''),'doi':r.get('doi',''),'pmid':r.get('pmid',''),'title':r.get('title',''),'gene_mention':gene,'gene_id':'','trait_original':raw,'trait_normalized':'','method':';'.join(methods) if methods else 'unknown','finding':'unknown','effect_direction':'unknown','evidence_type':';'.join(labels),'supporting_text':sent.strip(),'source_text_type':'abstract','review_status':'待人工核验','candidate_note':'规则共现候选；基因身份、基因—性状关系、因果方向和方法均须人工核对。'})
      counts['rows']+=1
   counts['papers_with_candidate']+=1 if genes and traits else 0
 summary={'rule_version':'gene_trait_candidates_no_api_v1.0','input':str(args.input),'output':str(args.out),'candidate_rows':counts['rows'],'papers_with_at_least_one_candidate_sentence':counts['papers_with_candidate'],'interpretation':'candidate co-occurrence only; not an extracted or validated gene-trait assertion'}
 args.out.with_suffix('.summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
