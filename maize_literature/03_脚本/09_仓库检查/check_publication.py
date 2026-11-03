"""检查相对于主分支新增/修改的文件，不读取或上传本地原始数据。"""
import argparse, csv, json, subprocess
from pathlib import Path

FORBIDDEN_SUFFIX={'.xlsx','.xls','.parquet','.zip','.npy','.npz','.pt','.safetensors','.log'}
RAW_NAMES={'gene_trait_labels.csv','gene_id_mapping.csv','candidate_merge.csv','new_evidence.csv','pending_records.csv','excluded_records.csv','paper_supplement_coverage.csv','classification_suggestions.csv','source_file_inventory.json','config.json'}
ROW_FIELDS={'paper_id','source_row','abstract','title','supporting_text','doi','pmid','embedding_text','OriginalPath','NewPath'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',default='origin/main');ap.add_argument('--staged',action='store_true');args=ap.parse_args()
    root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True,encoding='utf-8').strip())
    command=['git','diff','--name-only','--diff-filter=ACMR','-z']
    command+=['--cached',args.base] if args.staged else [args.base,'HEAD']
    paths=[p for p in subprocess.check_output(command,cwd=root).decode('utf-8').split('\0') if p]
    errors=[]
    for relative in paths:
        path=root/relative;parts=Path(relative).parts
        if path.suffix.lower() in FORBIDDEN_SUFFIX or path.name in RAW_NAMES or any(p in {'01_数据','cache','.runtime','__pycache__'} for p in parts):errors.append(relative+': local data/artifact path')
        if path.stat().st_size>1024*1024:errors.append(relative+': over 1 MiB; inspect publication scope')
        if path.suffix.lower()=='.csv':
            with path.open(encoding='utf-8-sig',newline='') as f:
                fields=set(csv.DictReader(f).fieldnames or [])
            if fields & ROW_FIELDS:errors.append(relative+': row-level evidence/path fields')
        if path.suffix.lower() in {'.py','.json','.md','.txt','.ps1','.csv','.yml','.yaml'}:
            text=path.read_text(encoding='utf-8-sig')
            # 本次发布只允许可移植路径。主分支历史内容不在diff中。
            if ('E:'+'\\Desktop\\') in text or ('/workspace/'+'scratch/') in text:errors.append(relative+': machine-specific absolute path')
        if path.suffix.lower()=='.json':json.loads(path.read_text(encoding='utf-8-sig'))
    if errors:raise SystemExit('\n'.join(errors))
    print(f'Publication checks passed for {len(paths)} changed files; no new raw-data files found.')

if __name__=='__main__':main()
