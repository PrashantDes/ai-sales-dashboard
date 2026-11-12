"""Build the Phase 2 database from the locally profiled, hash-verified workbook."""
import hashlib,json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sales_ai.retail import build

def main():
    source=ROOT/'data/raw/online-retail/Online Retail.xlsx'
    manifest=json.loads((ROOT/'docs/evidence/phase-1/manifest.json').read_text())
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest!=manifest['workbook_sha256']: raise ValueError('Source changed: repeat Phase 1 contract review')
    frame=pd.read_excel(source,sheet_name=manifest['worksheet'],engine='openpyxl',dtype={'InvoiceNo':str,'StockCode':str,'CustomerID':str})
    report=build(frame,ROOT/'data/processed/online-retail.sqlite',digest,manifest['worksheet'])
    out=ROOT/'docs/evidence/phase-2';out.mkdir(parents=True,exist_ok=True)
    (out/'quality.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
