"""在项目级依赖目录优先加载PyArrow，避免Pandas过早缓存缺失依赖版本。"""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.runtime'))
import pyarrow
import run_continuation

if __name__=='__main__':
    run_continuation.main()
    # --source/--batch-size仅用于主流程，finalize只需要同一个输出目录。
    import argparse
    ap=argparse.ArgumentParser(add_help=False)
    ap.add_argument('--output',default=str(ROOT/'delivery_v1_0'))
    args,_=ap.parse_known_args()
    sys.argv=[sys.argv[0],'--output',args.output]
    import finalize_delivery
    finalize_delivery.main()
