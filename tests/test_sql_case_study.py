"""Case study must regenerate deterministically and exclude customer identities."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
import pandas as pd
import pytest
from scripts import build_sql_case_study as report
from sales_ai.retail import build
from tests.retail_fixture import BASE


def test_report_reproducibility_traceability_and_privacy(tmp_path,monkeypatch):
    rows=[]
    for i,month in enumerate(pd.date_range('2010-12-01',periods=13,freq='MS')):
        rows.append({**BASE,'InvoiceNo':f'SALE-{i}','InvoiceDate':month.strftime('%Y-%m-%d'),'CustomerID':'PRIVATE_TEST_CUSTOMER'})
    rows.append({**BASE,'InvoiceNo':'C-TEST','InvoiceDate':'2011-01-15','Quantity':-1})
    database=tmp_path/'data.sqlite'
    quality=build(pd.DataFrame(rows),database,'fixture-source')
    quality_path=tmp_path/'docs/evidence/phase-2';quality_path.mkdir(parents=True)
    (quality_path/'quality.json').write_text(json.dumps(quality))
    monkeypatch.setattr(report,'ROOT',tmp_path)
    first=tmp_path/'first';second=tmp_path/'second'
    payload=report.build(first,database);report.build(second,database)
    names=['sql-case-study.md','sql-case-study.json','sql-case-study-charts.svg','sql-case-study-charts.png']
    for name in names:
        assert (first/name).read_bytes()==(second/name).read_bytes()
    text=json.dumps(payload)
    assert 'PRIVATE_TEST_CUSTOMER' not in text
    assert '30_customer_id_concentration' not in payload['queries']
    assert '41_purchase_sequence' not in payload['queries']
    assert len(payload['findings'])==3
    assert payload['independent_verification']['all_queries_match_independent_python']
    assert sum(r['gross_units'] for r in payload['queries']['10_monthly'])==payload['summary']['gross_units']
    assert payload['summary']['net_units']==payload['summary']['gross_units']-payload['summary']['cancellation_units']
    ET.fromstring((first/'sql-case-study-charts.svg').read_text())
    assert (first/'sql-case-study-charts.png').read_bytes().startswith(b'\x89PNG')
    for finding in payload['findings']:
        assert finding['action'] and finding['limitation'] and finding['query']
    with __import__('sqlite3').connect(database) as con:
        con.execute("UPDATE lines SET line_units=line_units+1 WHERE source_row=2")
    with pytest.raises(AssertionError):report.build(tmp_path/'bad',database)


def test_currency_rounds_only_at_display_boundary():
    assert report.money(1125)=='GBP 1.12'
    assert report.money(3375)=='GBP 3.38'
