"""Phase 1 source acquisition/profile only; no analytical database is built."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import platform
import shutil
import urllib.request
import zipfile
import importlib.metadata
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
URL = "https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip"
COLUMNS = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    raw = ROOT / "data/raw/online-retail"
    raw.mkdir(parents=True, exist_ok=True)
    archive = raw / "source.zip"
    workbook = raw / "Online Retail.xlsx"
    if args.download:
        temporary = raw / "download.part"
        try:
            with urllib.request.urlopen(URL, timeout=60) as response, temporary.open("wb") as output:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 50 * 1024 * 1024:
                        raise ValueError("Archive exceeds 50 MB limit")
                    output.write(chunk)
            with zipfile.ZipFile(temporary) as source:
                matches = [i for i in source.infolist() if i.filename == "Online Retail.xlsx"]
                if len(matches) != 1 or matches[0].file_size > 100 * 1024 * 1024:
                    raise ValueError("Unexpected workbook archive")
                with source.open(matches[0]) as inp, workbook.open("wb") as output:
                    shutil.copyfileobj(inp, output)
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
    if not workbook.exists():
        parser.error("Run with --download first")
    excel = pd.ExcelFile(workbook, engine="openpyxl")
    if len(excel.sheet_names) != 1:
        raise ValueError("Expected one source worksheet")
    sheet = excel.sheet_names[0]
    df = pd.read_excel(excel, sheet_name=sheet, dtype={"InvoiceNo": str, "StockCode": str, "CustomerID": str})
    if list(df.columns) != COLUMNS:
        raise ValueError("Source schema changed")
    dates = pd.to_datetime(df.InvoiceDate, errors="coerce")
    qty = pd.to_numeric(df.Quantity, errors="coerce")
    price = pd.to_numeric(df.UnitPrice, errors="coerce")
    cancel = df.InvoiceNo.str.upper().str.startswith("C", na=False)
    precision = price.dropna().map(lambda v: max(0, -Decimal(str(v)).as_tuple().exponent))
    conflicts = {}
    for col in ["CustomerID", "Country", "InvoiceDate"]:
        conflicts[col] = int((df.groupby("InvoiceNo")[col].nunique(dropna=False) > 1).sum())
    codes = df.StockCode.fillna("").str.fullmatch(r"[0-9]{5}[A-Za-z]?")
    profile = {"rows": len(df), "columns": COLUMNS, "worksheet": sheet,
        "date_min": str(dates.min()), "date_max": str(dates.max()),
        "nulls": {k:int(v) for k,v in df.isna().sum().items()},
        "invalid_dates": int(dates.isna().sum()), "duplicate_excess_rows":int(df.duplicated().sum()),
        "quantity_nonpositive":int((qty<=0).sum()), "quantity_noninteger":int((qty%1!=0).sum()),
        "price_zero":int((price==0).sum()), "price_negative":int((price<0).sum()),
        "price_nonfinite":int((~price.map(lambda v: Decimal(str(v)).is_finite())).sum()),
        "max_price_decimal_places":int(precision.max()),
        "cancellation_negative_quantity":int((cancel & (qty<0)).sum()),
        "cancellation_nonnegative_quantity":int((cancel & (qty>=0)).sum()),
        "noncancellation_negative_quantity":int((~cancel & (qty<0)).sum()),
        "invoice_header_conflicts":conflicts,
        "nonstandard_stock_codes":df.loc[~codes,"StockCode"].value_counts().to_dict(),
        "product_codes_multiple_descriptions":int((df.groupby("StockCode").Description.nunique()>1).sum()),
        "month_rows":df.groupby(dates.dt.strftime("%Y-%m")).size().to_dict()}
    manifest = {"source_url":URL,"source_page":"https://archive.ics.uci.edu/dataset/352/online+retail",
        "attribution":"Chen, D. (2015). Online Retail. UCI. DOI 10.24432/C5BW33",
        "license":"CC BY 4.0", "recorded_at_utc":datetime.now(timezone.utc).isoformat(),
        "retrieved_at_utc":datetime.fromtimestamp(archive.stat().st_mtime, timezone.utc).isoformat(),
        "retrieval_time_basis":"local downloaded archive modification time",
        "preparation_policy_version":"1.0", "archive_sha256":sha(archive),"workbook_sha256":sha(workbook),"worksheet":sheet,
        "rows":len(df),"schema_version":"1.0","profile_version":"1.0",
        "python":platform.python_version(),"packages":{p:importlib.metadata.version(p) for p in ["pandas","numpy","openpyxl"]}}
    out = ROOT / "docs/evidence/phase-1"
    out.mkdir(parents=True, exist_ok=True)
    (out/"profile.json").write_text(json.dumps(profile,indent=2)+"\n",encoding="utf-8")
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(profile,indent=2))

if __name__ == "__main__":
    main()
