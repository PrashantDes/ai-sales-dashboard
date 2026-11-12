import hashlib
from contextlib import closing
import pandas as pd
import pytest
from sales_ai.retail import build,classify,readonly,scoped_lines
from tests.retail_fixture import retail_rows

def test_classification_and_exact_precision():
    rows=retail_rows()
    assert classify(rows[0])[2:5]==(2,1125,2250)
    assert classify(rows[2])[0]['CustomerID'] is None
    assert classify(rows[4])[5]=='cancellation'
    assert classify(rows[5])[6]=='unmatched_adjustment'
    assert classify(rows[6])[6]=='non_monetary'
    assert classify(rows[7])[5]=='quarantined'
    assert classify(rows[-1])[5]=='quarantined'
    assert [classify(row)[5] for row in rows]==[
        'sale','sale','sale','sale','cancellation','excluded','excluded',
        'quarantined','quarantined','quarantined','excluded','quarantined','sale','quarantined']
    assert classify(rows[8])[6]=='invalid_date'
    assert classify(rows[9])[6]=='invalid_numeric'
    assert classify(rows[11])[6]=='contradictory_cancellation'
    assert classify(rows[13])[6]=='excess_price_precision'

def test_build_repeatability_integrity_joins_and_readonly(tmp_path):
    path=tmp_path/'db.sqlite';frame=pd.DataFrame(retail_rows())
    first=build(frame,path,'synthetic')
    assert first['source_rows']==sum(first['dispositions'].values())
    assert first['overlapping_flags']['duplicate_excess']==1
    assert first['invoice_timestamp_conflicts']==1
    assert first['eligible_invoice_join_preserves_rows_and_values']
    assert build(frame,path,'synthetic')==first
    with closing(readonly(path)) as con:
        assert con.execute('SELECT count(*) FROM lines WHERE customer_id IS NULL').fetchone()[0]==1
        assert scoped_lines(con,'2011-01-01','2011-02-01',"x' OR 1=1 --")[0]==0
        with pytest.raises(Exception): con.execute('DELETE FROM lines')
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(RuntimeError): build(frame,path,'synthetic',fail_before_replace=True)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    assert not list(tmp_path.glob('retail-build-*'))

def test_overflow_fails_without_publishing(tmp_path):
    row=retail_rows()[0];row['Quantity']=2**63
    path=tmp_path/'db.sqlite'
    with pytest.raises(OverflowError): build(pd.DataFrame([row]),path,'synthetic')
    assert not path.exists()
