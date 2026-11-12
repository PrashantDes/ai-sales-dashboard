from contextlib import closing
import pandas as pd
import pytest
from sales_ai.retail import build,readonly
from sales_ai.retail_queries import run,reconcile
from tests.retail_fixture import BASE

@pytest.fixture
def database(tmp_path):
    rows=[]
    for invoice,date,customer,quantity,price in [
        ('A','2011-01-05','X',1,1),('A','2011-01-05','X',1,1),
        ('B','2011-01-06','X',1,1),('C1','2011-01-07',None,-10,1),
        ('D','2011-03-05','Y',1,3),('E','2011-04-09','X',1,1)]:
        rows.append({**BASE,'InvoiceNo':invoice,'InvoiceDate':date,'CustomerID':customer,'Quantity':quantity,'UnitPrice':price})
    path=tmp_path/'retail.sqlite';build(pd.DataFrame(rows),path,'fixture');return path

def test_queries_match_independent_oracle_and_edge_cases(database):
    with closing(readonly(database)) as con:
        assert reconcile(con,'2011-01-01','2011-04-10')['all_queries_match_independent_python']
        monthly=run(con,'10_monthly','2011-01-01','2011-04-10')
        assert [m['month'] for m in monthly]==['2011-01-01','2011-03-01']
        assert all(m['growth'] is None for m in monthly)
        assert run(con,'20_country_exposure','2011-01-01','2011-02-01')[0]['cancellation_sales_ratio']>1
        assert run(con,'40_repeat','2011-01-01','2011-02-01')[0]['repeat_share']==1
        sequence=run(con,'41_purchase_sequence','2011-01-01','2011-02-01')
        assert [r['purchase_number'] for r in sequence]==[1,2]
        assert reconcile(con,'2011-01-01','2011-02-01',"' OR 1=1 --")['gross_units']==0
        assert run(con,'40_repeat','2010-01-01','2010-02-01')[0]['repeat_share'] is None
        assert run(con,'20_stock_code_exposure','2011-01-07','2011-01-08')[0]['cancellation_sales_ratio'] is None
        assert run(con,'10_monthly','2011-01-02','2011-02-01')==[]

def test_rank_ties_are_deterministic_and_null_customers_excluded(tmp_path):
    rows=[{**BASE,'StockCode':'12345B','CustomerID':None},{**BASE,'StockCode':'12345A','CustomerID':'X'}]
    path=tmp_path/'db';build(pd.DataFrame(rows),path,'fixture')
    with closing(readonly(path)) as con:
        assert reconcile(con,'2011-01-01','2011-02-01')['all_queries_match_independent_python']
        assert [r['group_key'] for r in run(con,'30_stock_code_concentration','2011-01-01','2011-02-01')]==['12345A','12345B']
        assert len(run(con,'30_customer_id_concentration','2011-01-01','2011-02-01'))==1


def test_query_validation_and_quarantined_dates(tmp_path):
    rows=[dict(BASE),{**BASE,'InvoiceDate':'not a date'}]
    path=tmp_path/'db';build(pd.DataFrame(rows),path,'fixture')
    with closing(readonly(path)) as con:
        assert reconcile(con,'2011-01-01','2011-02-01')['all_queries_match_independent_python']
        with pytest.raises(ValueError):run(con,'../unsafe','2011-01-01','2011-02-01')
        with pytest.raises(ValueError):run(con,'40_repeat','2011-02-01','2011-01-01')
        with pytest.raises(ValueError):run(con,'40_repeat','2011-1-1','2011-02-01')
