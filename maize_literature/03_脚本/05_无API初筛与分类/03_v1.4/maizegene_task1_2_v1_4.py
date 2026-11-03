#!/usr/bin/env python3
"""MaizeGene Task 1-2: deterministic abstract/title rule screen; no API calls."""
from __future__ import annotations
import argparse, csv, json, re, hashlib, collections, statistics
from pathlib import Path
from datetime import datetime, timezone
csv.field_size_limit(50_000_000)

RULE_VERSION = 'maizegene_rules_v1.4_20261102'
# Candidate triggers only: these do not replace abstract-level human adjudication.
RULES = {
 'A': [r'overexpress(?:ion|ed)?', r'knock(?:out|down)', r'gene silencing', r'gene editing', r'CRISPR', r'RNAi', r'complementation', r'loss.of.function', r'gain.of.function', r'transient expression', r'ectopic expression', r'mutant(?:s)?', r'functional characterization', r'functional analysis'],
 'B': [r'allelic variation', r'allele(?:s|ic)?', r'polymorphism', r'genetic variant', r'natural variation', r'SNPs?', r'haplotype', r'genotype', r'causal variant', r'variant effect', r'genetic association', r'association with (?:yield|trait|resistance|tolerance|flowering|kernel|grain|plant height|drought|disease)'],
 'C': [r'GWAS', r'genome.wide association', r'QTL', r'eQTL', r'caQTL', r'GWAS signal', r'RNA.seq', r'transcriptom', r'differential(?:ly)? expressed', r'gene expression', r'expression pattern', r'expression profile', r'expression analysis', r'qRT.PCR', r'RT.PCR', r'proteom', r'metabolom', r'methylom', r'DNA methylation', r'ChIP(?:.seq)?', r'chromatin immunoprecipitation', r'ATAC.seq', r'chromatin accessibility', r'single.cell', r'multi.omics', r'co.expression', r'weighted gene co.expression', r'microarray', r'transcript abundance', r'transcriptional analysis'],
 'D': [r'gene family', r'genome.wide identification', r'phylogen', r'homolog(?:y|ous)', r'synten', r'conserved motif', r'protein domain', r'protein structure', r'in silico', r'computational prediction', r'functional prediction', r' deleterious', r'deleteriousness', r'variant pathogenicity', r'sequence analysis', r'promoter analysis', r'cis.regulatory element', r'comparative genom', r'gene model', r'population genetic', r'deleterious load', r'genetic load', r'gene harmfulness'],
 'E': [r'database', r'reference genome', r'genome resource', r'genomic resource', r'web server', r'online tool', r'open.source tool', r'pipeline', r'protocol', r'patent', r'vector construction', r'promoter (?:sequence|construct|application)', r'catalogue of', r'catalog of'],
 'R': [r' review\b', r'review of', r'systematic review', r'scoping review', r'meta.analysis', r'we summarize', r'this review', r'review article', r'综述'],
}
# To avoid treating generic agronomy/food/feed studies as gene evidence, A/B/C/D
# need an explicit molecular/genetic signal; a standalone trigger is insufficient.
GENE_CONTEXT = re.compile(r'\b(?:gene|genes|genetic|genomic|genome|allele|allelic|variant|locus|loci|QTL|GWAS|transcript|expression|protein|transcription factor|RNA|DNA|chromosome|chromatin|mutation|mutant|Zm[A-Z0-9][A-Za-z0-9_-]*|GRMZM\d+|Zm\d{2,})\b', re.I)
MAIZE = re.compile(r'\b(?:maize|corn|Zea\s+mays|Z\.\s*mays|teosinte|B73|Mo17|W22|NAM-5\.0|Zm[A-Z0-9][A-Za-z0-9_-]*)\b', re.I)
NONCORE = re.compile(r'\b(?:food safety|feed|feeding|broiler|chicken|cow|cattle|human health|human consumption|food processing|starch processing|milling|flour|tortilla|silage|ethanol production|biofuel|fertili[sz]er|herbicide tax|life cycle assessment|soil cover|soil erosion|food product|nutrition|digestibility|aflatoxin|mycotoxin|pesticide residue)\b', re.I)
OMICS = re.compile(r'\b(?:GWAS|QTL|eQTL|caQTL|RNA.seq|transcriptom|differential(?:ly)? expressed|gene expression|expression pattern|expression profile|expression analysis|qRT.PCR|RT.PCR|proteom|metabolom|methylom|DNA methylation|ChIP(?:.seq)?|chromatin immunoprecipitation|ATAC.seq|chromatin accessibility|single.cell|multi.omics|microarray|transcript abundance|transcriptional analysis)\b', re.I)
INTERVENTION = re.compile(r'\b(?:overexpress(?:ion|ed)?|knock(?:out|down)|gene silencing|gene editing|CRISPR|RNAi|complementation|loss.of.function|gain.of.function|transient expression|ectopic expression|mutant(?:s)?|mutagenesis|functional characterization)\b', re.I)
GENE_SYMBOL = re.compile(r'\b(?:Zm[A-Z][A-Za-z0-9_-]{1,}|Zm\d{2,}d\d+|GRMZM\d+|CDK[AB]\d+;\d+[A-Za-z]?|GA20OX-?\d+|MOP\d+|RMR\d+)\b', re.I)
PROTEIN_ASSAY = re.compile(r'\b(?:recombinant protein|expressed in (?:E\.\s*coli|Escherichia coli)|in vitro kinase|kinase assay|biochemical assay|protein purification|enzyme activity assay)\b', re.I)
ALLELE_TRAIT = re.compile(r'\b(?:allele|allelic|polymorphism|SNP|haplotype|genotype|variant|mutation|natural variation|genetic association)\b', re.I)
TRAIT_LINK = re.compile(r'\b(?:associated|association|linked|linkage|affect(?:s|ed)?|confer(?:s|red)?|contribut(?:e|es|ed)|increase(?:s|d)?|decrease(?:s|d)?|resistan(?:ce|t)|toleran(?:ce|t)|yield|phenotyp|flowering|kernel|grain|plant height|drought|disease|fitness)\b', re.I)
GENE_COMPUTE = re.compile(r'\b(?:gene family|genome.wide identification|phylogen|homolog|synten|conserved motif|protein domain|protein structure|in silico|computational prediction|functional prediction|deleterious|sequence analysis|DNA sequence|repetitive sequence|sequence loss|promoter analysis|cis.regulatory element|gene model|population genetic|deleterious load|genetic load|gene harmfulness)\b', re.I)
RESOURCE = re.compile(r'\b(?:database|reference genome|genome resource|genomic resource|web server|online tool|open.source tool|pipeline|protocol|patent|vector construction|promoter sequence|promoter construct)\b', re.I)
REVIEW = re.compile(r'\b(?:review|meta.analysis|we summarize|this review|综述)\b', re.I)


def compile_rules(): return {k:[re.compile(p,re.I) for p in v] for k,v in RULES.items()}
CR=compile_rules()
def get_field(row,*names):
    for n in names:
        if n in row and row[n] is not None: return str(row[n]).strip()
    return ''
def norm(s): return re.sub(r'\s+',' ',(s or '').strip()).casefold()
def dedup_patterns(text, regs): return [r.pattern for r in regs if r.search(text)]
def classify(title, abstract):
    text=f'{title} {abstract}'
    gene_context=bool(GENE_CONTEXT.search(text))
    vals=[]; triggers=[]
    if gene_context:
        # Require a recognizable maize gene symbol and an actual manipulation cue.
        # Generic mutant/transgenic mentions often refer to insects, microbes, or patents.
        maize_target=bool(re.search(r'\b(?:maize|corn|Zea\s+mays|B73|Mo17|transgenic maize|maize plants?)\b',title,re.I))
        nonmaize_subject=bool(re.search(r'\b(?:armyworm|fall armyworm|parasitoid|parasite|beetle|moth|cattle|broiler|geese|human|rat|mouse|microbe|bacterium|virus)\b',title,re.I))
        if GENE_SYMBOL.search(text) and (INTERVENTION.search(text) or PROTEIN_ASSAY.search(text)) and maize_target and not nonmaize_subject and not re.search(r'\b(?:in silico|simulation|simulated|computationally)\b.{0,80}\b(?:knockout|knockdown|mutant)\b',text,re.I):
            vals.append('A'); triggers.extend('A:'+p for p in dedup_patterns(text,CR['A']))
        if ALLELE_TRAIT.search(text) and TRAIT_LINK.search(text) and GENE_SYMBOL.search(text):
            vals.append('B'); triggers.extend('B:'+p for p in dedup_patterns(text,CR['B']))
        if OMICS.search(text):
            vals.append('C'); triggers.extend('C:'+p for p in dedup_patterns(text,CR['C']))
        if GENE_COMPUTE.search(text):
            vals.append('D'); triggers.extend('D:'+p for p in dedup_patterns(text,CR['D']))
        if RESOURCE.search(text):
            vals.append('E'); triggers.extend('E:'+p for p in dedup_patterns(text,CR['E']))
    if REVIEW.search(text):
        vals.append('R'); triggers.extend('R:'+p for p in dedup_patterns(text,CR['R']))
    vals=list(dict.fromkeys(vals))
    # X is the non-core bucket only when no positive gene-evidence category is triggered.
    if not any(x in vals for x in 'ABCDE') and (NONCORE.search(text) or bool(MAIZE.search(text))):
        vals.append('X')
        if NONCORE.search(text): triggers.append('X:'+NONCORE.search(text).group(0))
        else: triggers.append('X:no_A-E_gene_evidence')
    if not vals: vals=['U']; triggers=['U:no_rule_match']
    # Relationship labels are independent contextual cues, not semantic adjudications.
    maize=bool(MAIZE.search(text))
    maize_direct=bool(GENE_SYMBOL.search(text) or re.search(r'\b(?:maize|corn|Zea\s+mays|B73|Mo17|W22|NAM-5\.0)\s+(?:plant|line|cultivar|hybrid|root|gene|genotype|yield|kernel|grain|seedling|tissue|mutant|transgenic|growth|development|trait|drought|disease)\w*\b',title+' '+abstract,re.I) or re.search(r'\b(?:maize|corn)\s+(?:yield|growth|plant|root|kernel|grain|flowering|gene|line|cultivar)\b',title,re.I))
    indirect_focus=bool(re.search(r'\b(?:human health|consumption|food safety|pest control|fall armyworm|armyworm|parasitoid|Diabrotica|Chelonus|broiler|livestock feed|animal feeding|flour consumption)\b',title,re.I))
    maize_in_title=bool(re.search(r'\b(?:maize|corn|Zea\s+mays|Z\.\s*mays)\b',title,re.I))
    title_ingredient_only=bool(re.search(r'\b(?:corn peptides?|maize peptides?)\b',title,re.I))
    clearly_unrelated_title=bool(re.search(r'\b(?:greylag geese|geese|Chenopodium album|sweet potato starch|instant drink|protein solubility in E\. coli)\b',title,re.I))
    if indirect_focus and maize: rel='M2'
    elif maize_in_title and not title_ingredient_only: rel='M1'
    elif maize_direct and maize_in_title: rel='M1'
    elif (maize_in_title and title_ingredient_only) or clearly_unrelated_title: rel='N'
    elif maize: rel='U_rel'
    else: rel='N'
    priority='P1' if ('A' in vals or ('B' in vals and 'C' in vals)) else ('P2' if ('B' in vals or 'C' in vals) else ('P3' if ('D' in vals or 'E' in vals) else 'P4'))
    return ';'.join(vals),';'.join(dict.fromkeys(triggers)),rel,priority

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('input',type=Path)
    ap.add_argument('--outdir',type=Path,default=Path('output_v1_4'))
    ap.add_argument('--manual',type=Path,default=None)
    args=ap.parse_args(); args.outdir.mkdir(parents=True,exist_ok=True)
    source_hash=hashlib.sha256(args.input.read_bytes()).hexdigest()
    counts=collections.Counter(); missing=collections.Counter(); dups={k:collections.Counter() for k in ('doi','pmid','title')}; seen={k:set() for k in dups}; class_counts=collections.Counter(); rel_counts=collections.Counter(); priority_counts=collections.Counter(); examples=collections.defaultdict(list)
    classification_path=args.outdir/'paper_classification_v1_4.csv'
    queue_path=args.outdir/'manual_review_queue_v1_4.csv'
    master_path=args.outdir/'papers_master_v1_4.csv'
    with args.input.open('r',encoding='utf-8-sig',newline='') as fi:
        reader=csv.DictReader(fi); fields=reader.fieldnames
        if not fields: raise ValueError('CSV header missing')
        required={'title','abstract'}
        if not required.issubset(fields): raise ValueError(f'required actual columns absent: {required-set(fields)}')
        extra=['rule_version_task2','candidate_evidence_labels','candidate_triggers','relatedness_candidate','manual_priority']
        outfields=fields+[x for x in extra if x not in fields]
        with master_path.open('w',encoding='utf-8-sig',newline='') as fm, classification_path.open('w',encoding='utf-8-sig',newline='') as fc, queue_path.open('w',encoding='utf-8-sig',newline='') as fq:
            wm=csv.DictWriter(fm,fieldnames=outfields,extrasaction='ignore'); wm.writeheader()
            wc=csv.DictWriter(fc,fieldnames=['source_row','record_id','doi','pmid','year','title','abstract','candidate_evidence_labels','candidate_triggers','relatedness_candidate','manual_priority','rule_version_task2']); wc.writeheader()
            wq=csv.DictWriter(fq,fieldnames=['source_row','record_id','doi','pmid','year','title','abstract','candidate_evidence_labels','candidate_triggers','relatedness_candidate','manual_priority','rule_version_task2']); wq.writeheader()
            for row in reader:
                counts['records']+=1
                title=get_field(row,'title'); abstract=get_field(row,'abstract')
                for k,v in [('title',title),('abstract',abstract),('doi',get_field(row,'doi')),('pmid',get_field(row,'pmid'))]:
                    if not v: missing[k]+=1
                    if v and k in seen:
                        key=norm(v)
                        if key in seen[k]: dups[k][key]+=1
                        else: seen[k].add(key)
                labels,triggers,rel,priority=classify(title,abstract)
                row.update(rule_version_task2=RULE_VERSION,candidate_evidence_labels=labels,candidate_triggers=triggers,relatedness_candidate=rel,manual_priority=priority)
                base={k:row.get(k,'') for k in ['source_row','record_id','doi','pmid','year','title','abstract']}
                rec={**base,'candidate_evidence_labels':labels,'candidate_triggers':triggers,'relatedness_candidate':rel,'manual_priority':priority,'rule_version_task2':RULE_VERSION}
                wm.writerow(row); wc.writerow(rec)
                # Keep only the current high-priority evidence candidates in the human queue.
                if priority in {'P1','P2'}: wq.writerow(rec)
                for tag in labels.split(';'): class_counts[tag]+=1
                rel_counts[rel]+=1; priority_counts[priority]+=1
                if len(examples[labels])<5: examples[labels].append({'source_row':base['source_row'],'title':title[:240]})
    # Exact normalized duplicates: count excess records and groups.
    dup_stats={k:{'duplicate_groups':len(v),'excess_records':sum(v.values())} for k,v in dups.items()}
    manual_stats={}
    if args.manual:
        import pandas as pd
        m=pd.read_excel(args.manual,sheet_name='第二轮核查',dtype=str).fillna('')
        # Re-run the exact current classifier on each reviewed record and compare to human labels.
        mc=collections.Counter(); cc=collections.Counter(); overlap=collections.Counter(); missed=collections.Counter(); extra=collections.Counter()
        related=collections.Counter(); related_match=collections.Counter()
        for _,r in m.iterrows():
            h={x.strip() for x in str(r.get('证据类别_人工填写','')).split(';') if x.strip()}
            cl,_,rel,_=classify(str(r.get('title','')),str(r.get('abstract','')))
            c=set(cl.split(';'))
            for x in h: mc[x]+=1
            for x in c: cc[x]+=1
            for x in h&c: overlap[x]+=1
            for x in h-c: missed[x]+=1
            for x in c-h: extra[x]+=1
            human_rel=str(r.get('相关性标签_人工填写','')).strip()
            related[human_rel]+=1
            if human_rel==rel: related_match[rel]+=1
        manual_stats={'evidence':{'manual_counts':dict(mc),'current_rule_candidate_counts':dict(cc),'candidate_overlap':dict(overlap),'manual_not_triggered':dict(missed),'candidate_not_manual':dict(extra),'n':len(m)},'relatedness':{'manual_counts':dict(related),'current_rule_exact_matches':dict(related_match),'n':len(m),'note':'Small stratified validation sample; counts calibrate rule revisions only and are not prevalence estimates.'}}
    else: manual_stats={'warning':'no manual calibration workbook supplied'}
    summary={'rule_version':RULE_VERSION,'generated_utc':datetime.now(timezone.utc).isoformat(),'source_file':str(args.input),'source_sha256':source_hash,'input_header_actual':fields,'record_count':counts['records'],'missing':{k:{'count':missing[k],'rate_pct':round(missing[k]/counts['records']*100,4)} for k in ('title','abstract','doi','pmid')},'duplicate_check_normalized_casefold':dup_stats,'candidate_evidence_label_counts':dict(class_counts),'relatedness_candidate_counts':dict(rel_counts),'priority_queue_counts':dict(priority_counts),'manual_round2_calibration_only':manual_stats,'label_examples':dict(examples),'output_files':[str(master_path),str(classification_path),str(queue_path)]}
    (args.outdir/'task1_2_statistics_v1_4.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
