"""Small synthetic databases exercise the real-data UI without downloads or AI."""
from contextlib import closing
from datetime import date
from pathlib import Path
import json
import sqlite3
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
import sales_ai.ai as ai
import sales_ai.retail_view as view
from sales_ai.retail import build
from tests.retail_fixture import BASE

APP=str(Path(__file__).resolve().parents[1]/'app.py')

@pytest.fixture
def retail_app(tmp_path,monkeypatch):
    path=tmp_path/'retail.sqlite'
    rows=[{**BASE,'InvoiceDate':'2011-01-05','InvoiceNo':'A','CustomerID':'SECRET-CUSTOMER'},
          {**BASE,'InvoiceDate':'2011-01-06','InvoiceNo':'B','CustomerID':'SECRET-CUSTOMER'},
          {**BASE,'InvoiceDate':'2011-02-02','InvoiceNo':'C1','Quantity':-1,'CustomerID':None}]
    build(pd.DataFrame(rows),path,'synthetic')
    monkeypatch.setattr(view,'DB_PATH',path)
    def forbidden(*args,**kwargs): raise AssertionError('No provider calls in local SQL view')
    monkeypatch.setattr(ai,'_call_llm',forbidden);monkeypatch.setattr(ai,'verify_api_key',forbidden)
    app=AppTest.from_file(APP,default_timeout=40).run()
    next(w for w in app.radio if w.label=='Data source').set_value('Real-data SQL (GBP)').run()
    return app,path,rows

def test_scoped_metrics_privacy_and_state(retail_app):
    app,path,rows=retail_app
    assert not app.exception
    assert [(m.label,m.value) for m in app.metric][:3]==[
        ('Gross merchandise sales','GBP 4.50'),('Cancellation exposure','GBP 1.12'),('Recorded net merchandise value','GBP 3.38')]
    # 1.125 rounds half-even to1.12; net3.375 rounds to3.38 independently.
    assert all('profit' not in m.label.lower() for m in app.metric)
    assert all('SECRET-CUSTOMER' not in str(table.value) for table in app.dataframe)
    token=view.db_token(path);info=view.database_info(str(path),token)
    data=view.aggregate_results(str(path),token,'2011-01-01','2011-03-01',None)
    payload=view.export_payload(data,info,'2011-01-01','2011-03-01',None)
    assert 'SECRET-CUSTOMER' not in json.dumps(payload)
    assert '30_customer_id_concentration' not in payload['queries']
    assert '41_purchase_sequence' not in payload['queries']
    app.date_input[0].set_value((date(2011,2,2),date(2011,2,2))).run()
    assert not app.exception
    assert app.metric[0].value=='GBP 0.00'
    assert app.metric[-1].value=='Not available'
    assert any('No identified' in n.value for n in app.info)
    source=next(w for w in app.radio if w.label=='Data source')
    source.set_value(source.options[0]).run()
    next(w for w in app.radio if w.label=='Data source').set_value('Real-data SQL (GBP)').run()
    assert app.date_input[0].value==(date(2011,2,2),date(2011,2,2))
    assert app.metric[0].value=='GBP 0.00'

def test_incomplete_dates_and_database_rebuild_invalidate_cache(retail_app):
    app,path,rows=retail_app
    app.date_input[0].set_value((date(2011,1,5),)).run()
    assert not app.exception and not app.metric
    assert any('both retail dates' in n.value for n in app.info)
    old=view.db_token(path)
    build(pd.DataFrame([{**rows[0],'UnitPrice':'9.00'},rows[-1]]),path,'replacement')
    assert view.db_token(path)!=old
    app.run()
    assert not app.exception
    assert app.metric[0].value=='GBP 18.00'

def test_missing_and_corrupt_database_never_substitute_sample(retail_app):
    app,path,rows=retail_app
    path.unlink();app.run()
    assert not app.exception and app.error and not app.metric
    path.write_bytes(b'not sqlite');app.run()
    assert not app.exception and app.error and not app.metric

def test_empty_country_and_unsupported_database(retail_app):
    app,path,rows=retail_app
    with sqlite3.connect(path) as con:
        con.execute("UPDATE lines SET country='Other' WHERE disposition='cancellation'")
    app.run()
    app.selectbox[0].set_value('Other').run()
    assert not app.exception
    assert app.metric[0].value=='GBP 0.00'
    app.date_input[0].set_value((date(2011,1,5),date(2011,1,5))).run()
    assert app.warning and app.metric[0].value=='GBP 0.00' and not app.exception
    with sqlite3.connect(path) as con: con.execute("UPDATE metadata SET value='unsupported' WHERE key='policy_version'")
    app.run()
    assert app.error and not app.metric and not app.exception


def test_original_dashboard_filters_and_tab_survive_source_switch(retail_app):
    app,path,rows=retail_app
    source=next(w for w in app.radio if w.label=='Data source')
    source.set_value(source.options[0]).run()
    app.date_input[0].set_value((date(2026,9,1),date(2026,9,30))).run()
    next(w for w in app.multiselect if w.label=='Region').set_value(['North']).run()
    app.session_state['dashboard_tabs']='Forecast';app.run()
    next(w for w in app.radio if w.label=='Data source').set_value('Real-data SQL (GBP)').run()
    source=next(w for w in app.radio if w.label=='Data source');source.set_value(source.options[0]).run()
    assert not app.exception
    assert app.date_input[0].value==(date(2026,9,1),date(2026,9,30))
    assert next(w for w in app.multiselect if w.label=='Region').value==['North']
    assert app.session_state['dashboard_tabs']=='Forecast'
