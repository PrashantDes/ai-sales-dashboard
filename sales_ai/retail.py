"""Contract v1.0 preparation: source identity, exact units and atomic SQLite builds."""
from contextlib import closing
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import os
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
COLUMNS=["InvoiceNo","StockCode","Description","Quantity","InvoiceDate","UnitPrice","CustomerID","Country"]
NONMERCH={"POST","DOT","M","C2","D","S","BANK CHARGES","AMAZONFEE","CRUK","B","PADS"}
LIMIT=2**63-1

def integer(value):
    if abs(value)>LIMIT: raise OverflowError("Signed SQLite integer range exceeded")
    return int(value)

def clean(value):
    return None if pd.isna(value) or not str(value).strip() else str(value).strip()

def classify(row):
    data={c:clean(row[c]) for c in COLUMNS}
    reasons=[]; flags=[]; q=p=v=None
    for c in ('InvoiceNo','StockCode','Country'):
        if data[c] is None: reasons.append('missing_'+c)
    date=pd.to_datetime(data['InvoiceDate'],errors='coerce')
    if pd.isna(date): reasons.append('invalid_date'); stamp=None
    else: stamp=date.isoformat()
    try:
        quantity=Decimal(str(row['Quantity'])); price=Decimal(str(row['UnitPrice']))
        if not quantity.is_finite() or not price.is_finite(): raise ValueError()
        if quantity!=quantity.to_integral_value(): reasons.append('noninteger_quantity')
        else: q=integer(quantity)
        scaled=price*1000
        if scaled!=scaled.to_integral_value(): reasons.append('excess_price_precision')
        else: p=integer(scaled)
        if q is not None and p is not None: v=integer(q*p)
        if price<0: reasons.append('negative_price')
    except (ValueError,InvalidOperation): reasons.append('invalid_numeric')
    if data['CustomerID'] is None: flags.append('missing_customer')
    if data['Description'] is None: flags.append('missing_description')
    if not re.fullmatch(r'[0-9]{5}[A-Za-z]?',data['StockCode'] or ''): flags.append('nonstandard_code')
    if reasons: disposition,reason='quarantined',','.join(reasons)
    elif q==0 or p==0: disposition,reason='excluded','non_monetary'
    elif data['StockCode'].upper() in NONMERCH or data['StockCode'].lower().startswith('gift_'): disposition,reason='excluded','non_merchandise'
    elif data['InvoiceNo'].upper().startswith('C'):
        disposition,reason=('cancellation','eligible_cancellation') if q<0 else ('quarantined','contradictory_cancellation')
    elif q>0: disposition,reason='sale','eligible_sale'
    else: disposition,reason='excluded','unmatched_adjustment'
    return (data,stamp,q,p,v,disposition,reason,flags)

def readonly(path):
    connection=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    connection.execute('PRAGMA query_only=ON')
    return connection

def scoped_lines(connection,start,end,country):
    return connection.execute('SELECT count(*),sum(line_units) FROM lines WHERE timestamp>=? AND timestamp<? AND country=?',(start,end,country)).fetchone()

def build(frame,path,source_hash,worksheet='Online Retail',fail_before_replace=False):
    if list(frame.columns)!=COLUMNS: raise ValueError('Unexpected source schema')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    handle,temp=tempfile.mkstemp(prefix='retail-build-',suffix='.sqlite',dir=path.parent);os.close(handle)
    temp=Path(temp);seen=set();totals={};values={};flags_count={};digest=hashlib.sha256();invoices={};staging=[];lines=[];dedup_total=0;unpriceable=0;positive=negative=0
    try:
        with closing(sqlite3.connect(temp)) as con:
            con.executescript((ROOT/'sql/online_retail/00_schema.sql').read_text())
            for index,row in enumerate(frame.to_dict('records'),2):
                raw={c:None if pd.isna(row[c]) else str(row[c]) for c in COLUMNS}
                raw_json=json.dumps(raw,sort_keys=True,ensure_ascii=False)
                duplicate=int(raw_json in seen);seen.add(raw_json)
                data,stamp,q,p,v,disposition,reason,flags=classify(row)
                if duplicate: flags.append('duplicate_excess')
                for flag in flags: flags_count[flag]=flags_count.get(flag,0)+1
                totals[disposition]=totals.get(disposition,0)+1
                if v is None: unpriceable+=1
                else:
                    values[disposition]=integer(values.get(disposition,0)+v)
                    if v>=0: positive=integer(positive+v)
                    else: negative=integer(negative+v)
                    if not duplicate: dedup_total=integer(dedup_total+v)
                if data['InvoiceNo'] and stamp:
                    inv=invoices.setdefault(data['InvoiceNo'],set());inv.add(stamp)
                record=(index,data['InvoiceNo'],data['StockCode'],data['Description'],data['CustomerID'],data['Country'],stamp,q,p,v,disposition,reason,json.dumps(flags),duplicate)
                staging.append((index,raw_json));lines.append(record)
                digest.update(json.dumps(record,ensure_ascii=False).encode())
            con.executemany('INSERT INTO staging VALUES(?,?)',staging)
            con.executemany('INSERT INTO lines VALUES('+','.join('?'*14)+')',lines)
            con.executemany('INSERT INTO invoices VALUES(?,?,?)',[(key,min(stamps),int(len(stamps)>1)) for key,stamps in sorted(invoices.items())])
            metadata={'workbook_sha256':source_hash,'worksheet':worksheet,'schema_version':'1.0','policy_version':'1.0','price_scale':'1000','analytical_sha256':digest.hexdigest()}
            con.executemany('INSERT INTO metadata VALUES(?,?)',metadata.items());con.commit()
            assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not con.execute('PRAGMA foreign_key_check').fetchall()
            actual=dict(con.execute('SELECT disposition,count(*) FROM lines GROUP BY disposition'))
            assert actual==totals and sum(totals.values())==len(frame)
            actual_values=dict(con.execute('SELECT disposition,sum(line_units) FROM lines GROUP BY disposition'))
            assert all((actual_values[k] or 0)==values.get(k,0) for k in actual)
            base=con.execute("SELECT count(*),sum(line_units) FROM lines WHERE disposition IN ('sale','cancellation')").fetchone()
            joined=con.execute("SELECT count(*),sum(l.line_units) FROM lines l JOIN invoices i ON l.invoice_id=i.invoice_id WHERE disposition IN ('sale','cancellation')").fetchone()
            assert base==joined
            assert con.execute('SELECT sum(line_units) FROM deduplicated_sensitivity').fetchone()[0] in (dedup_total,None)
            report={'source_rows':len(frame),'dispositions':totals,'signed_value_units':values,'unpriceable_rows':unpriceable,'overlapping_flags':flags_count,'deduplicated_sensitivity_signed_units':dedup_total,'retained_signed_units':positive+negative,'positive_units':positive,'negative_units':negative,'invoice_timestamp_conflicts':sum(len(v)>1 for v in invoices.values()),'integrity':'ok','foreign_key_violations':0,'eligible_invoice_join_preserves_rows_and_values':True,'analytical_sha256':digest.hexdigest(),'source_identity':metadata}
        if fail_before_replace: raise RuntimeError('Injected failed build')
        temp.replace(path)
        return report
    finally:
        temp.unlink(missing_ok=True)
