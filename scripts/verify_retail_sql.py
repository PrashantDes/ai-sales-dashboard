"""Full-data Phase 3 reconciliation; publishes aggregate checks only."""
from contextlib import closing
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from sales_ai.retail import readonly
from sales_ai.retail_queries import reconcile
if __name__=='__main__':
    with closing(readonly(ROOT/'data/processed/online-retail.sqlite')) as con:
        checks=[dict(scope=scope,result=reconcile(con,*scope)) for scope in [('2010-12-01','2011-12-10',None),('2011-03-01','2011-10-01','United Kingdom'),('2011-12-01','2011-12-10',None),('2011-01-01','2011-02-01',"x' OR 1=1 --")]]
    out=ROOT/'docs/evidence/phase-3';out.mkdir(parents=True,exist_ok=True)
    (out/'reconciliation.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks,indent=2))
