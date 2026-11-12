"""Local, aggregate-only retail SQL view; no provider or customer exports."""
from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st
from sales_ai.retail import readonly
from sales_ai.retail_queries import run, SQL, QUERIES

ROOT=Path(__file__).resolve().parents[1]
DB_PATH=ROOT/'data/processed/online-retail.sqlite'

def db_token(path):
    stat=Path(path).stat()
    return (stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)

@st.cache_data(max_entries=4,show_spinner=False)
def database_info(path,token):
    with closing(readonly(path)) as con:
        if con.execute('PRAGMA quick_check').fetchone()[0]!='ok': raise ValueError('Database integrity check failed')
        meta=dict(con.execute('SELECT key,value FROM metadata'))
        if not meta.get('workbook_sha256') or not meta.get('analytical_sha256'): raise ValueError('Missing provenance metadata')
        if meta.get('schema_version')!='1.0' or meta.get('policy_version')!='1.0' or meta.get('price_scale')!='1000': raise ValueError('Unsupported database version')
        minimum,maximum=con.execute('SELECT min(timestamp),max(timestamp) FROM lines').fetchone()
        if not minimum or not maximum: raise ValueError('Database has no dated records')
        countries=[r[0] for r in con.execute('SELECT DISTINCT country FROM lines WHERE country IS NOT NULL ORDER BY country')]
        quality=[dict(disposition=r[0],rows=r[1]) for r in con.execute('SELECT disposition,count(*) FROM lines GROUP BY disposition')]
        missing_customer,missing_description,duplicates=con.execute('SELECT sum(customer_id IS NULL),sum(description IS NULL),sum(duplicate_excess) FROM lines').fetchone()
        conflicts=con.execute('SELECT sum(timestamp_conflict) FROM invoices').fetchone()[0]
        quality_flags=dict(missing_customer_ids=missing_customer,missing_descriptions=missing_description,duplicate_excess_rows=duplicates,invoice_timestamp_conflicts=conflicts)
        return dict(meta=meta,minimum=minimum,maximum=maximum,countries=countries,quality=quality,quality_flags=quality_flags)

@st.cache_data(max_entries=16,show_spinner=False)
def aggregate_results(path,token,start,end,country):
    with closing(readonly(path)) as con:
        data={name:run(con,name,start,end,country) for name in QUERIES if name!='41_purchase_sequence'}
    # Never return customer identifiers to the presentation/cache/download layer.
    for row in data['30_customer_id_concentration']: row.pop('group_key',None)
    return data

def gbp(units):
    return 'GBP '+format((Decimal(int(units))/1000).quantize(Decimal('0.01'),rounding=ROUND_HALF_EVEN),',.2f')

def export_payload(data,info,start,end,country):
    # Explicit aggregate allowlist; customer-level rankings/sequences are not exported.
    allowed=['10_monthly','20_stock_code_exposure','20_country_exposure','30_stock_code_concentration','40_repeat']
    return dict(source='UCI Online Retail; historical 2010-2011',currency='GBP',monetary_unit='0.001 GBP',
        source_sha256=info['meta']['workbook_sha256'],policy_version=info['meta']['policy_version'],
        scope=dict(start_inclusive=start,end_exclusive=end,country=country),
        queries={k:data[k] for k in allowed},limitations=['Cancellation exposure is not a matched-sale return rate','Customer measures exclude missing IDs; no profit or causal effect is estimated'])

def remember(name):
    st.session_state[name]=st.session_state['_widget_'+name]

def render_retail_view():
    st.title('Real-data SQL investigation')
    st.caption('Historical UCI Online Retail | GBP | local SQLite | no online AI requests')
    st.markdown('[Source and attribution: Chen (2015), UCI, CC BY 4.0](https://archive.ics.uci.edu/dataset/352/online+retail)')
    try:
        token=db_token(DB_PATH)
        info=database_info(str(DB_PATH),token)
    except (OSError,sqlite3.Error,ValueError,KeyError):
        st.error('The retail database is missing, invalid, or unsupported. No sample results are substituted.')
        st.code('python scripts/prepare_online_retail.py',language='powershell')
        st.caption('If the raw workbook is absent, first run python scripts/profile_online_retail.py --download. Review the source manifest and contract if its hash changes.')
        return
    minimum=date.fromisoformat(str(info['minimum'])[:10]); maximum=date.fromisoformat(str(info['maximum'])[:10])
    st.caption(f'Observed source coverage: {minimum} to {maximum}. This is historical data, not current trading.')
    fingerprint=str(token)
    if st.session_state.get('retail_db_token')!=fingerprint:
        st.session_state['retail_db_token']=fingerprint
        st.session_state['retail_dates']=(minimum,maximum)
        st.session_state['retail_country']='All countries'
        st.session_state.pop('_widget_retail_dates',None);st.session_state.pop('_widget_retail_country',None)
    dates=st.date_input('Retail date range',value=st.session_state.get('retail_dates',(minimum,maximum)),min_value=minimum,max_value=maximum,key='_widget_retail_dates',on_change=remember,args=('retail_dates',))
    options=['All countries',*info['countries']]
    country_label=st.selectbox('Retail country',options,index=options.index(st.session_state.get('retail_country','All countries')),key='_widget_retail_country',on_change=remember,args=('retail_country',))
    if not isinstance(dates,(tuple,list)) or len(dates)!=2:
        st.info('Select both retail dates to calculate results.');return
    start,end=str(dates[0]),str(dates[1]+timedelta(days=1)); country=None if country_label=='All countries' else country_label
    st.caption(f'Active scope: {dates[0]} through {dates[1]} inclusive | {country_label}')
    st.info('Definitions: gross merchandise sales retain eligible duplicate-looking lines; cancellation value is separate recorded credit activity. Net merchandise value excludes other adjustments and is not profit. Customer measures cover identified purchasers only.')
    try:data=aggregate_results(str(DB_PATH),token,start,end,country)
    except (OSError,sqlite3.Error,ValueError,KeyError):
        st.error('The accepted SQL could not run against this database. Rebuild it and retry; no stale figures are shown.');return
    summary=data['40_repeat'][0]
    gross=summary['gross_units'];cancel=sum(r['cancellation_units'] for r in data['20_stock_code_exposure'])
    if gross==0 and cancel==0:
        st.warning('No eligible sales or cancellation values in this scope. Ratios are unavailable.')
    cols=st.columns(4)
    for col,label,value in zip(cols,['Gross merchandise sales','Cancellation exposure','Recorded net merchandise value','Sales invoices'],[gbp(gross),gbp(cancel),gbp(gross-cancel),f"{summary['sales_invoices']:,}"]): col.metric(label,value)
    st.caption('Monetary values use exact thousandths of GBP, with half-even penny rounding only for display. Cancellation-to-sales ratios can exceed 100%; they are not verified return rates.')
    st.markdown('### 1. Complete-month trends')
    monthly=data['10_monthly']
    if monthly:
        chart=pd.DataFrame([{'Month':r['month'],'Gross sales (GBP)':float(Decimal(r['gross_units'])/1000),'Cancellation value (GBP)':float(Decimal(r['cancellation_units'])/1000)} for r in monthly]).set_index('Month')
        st.line_chart(chart,alt='Gross merchandise sales and cancellation value by complete observed month, GBP')
        st.dataframe(pd.DataFrame(monthly),hide_index=True,alt='Complete-month SQL results; monetary columns in thousandths of GBP')
    else:st.info('No complete observed month is available for comparison in this selection.')
    st.caption('The terminal source month, December 2011, is incomplete. Monthly comparisons exclude it and selection-boundary partial months; other summaries above include your full selected window. Missing months are not bridged by growth calculations.')
    st.markdown('### 2. Cancellation exposure')
    for name,label in [('20_stock_code_exposure','Products'),('20_country_exposure','Countries')]:
        rows=data[name];display=rows[:10]
        st.caption(f'{label}: largest cancellation values, showing {len(display)} of {len(rows)} groups; {max(len(rows)-10,0)} omitted from this table. Downloads include all groups.')
        if display:
            chart=pd.DataFrame([{'Group':r['group_key'],'Cancellation value (GBP)':r['cancellation_units']/1000} for r in display]).set_index('Group')
            st.bar_chart(chart,alt=f'Largest cancellation exposure by {label.lower()}, GBP')
            st.dataframe(pd.DataFrame(display),hide_index=True,alt=f'{label} exposure SQL output; monetary units are thousandths of GBP, ratio is a fraction')
    st.markdown('### 3. Sales concentration')
    for name,label in [('30_stock_code_concentration','Products'),('30_customer_id_concentration','Identified customer ranks')]:
        rows=data[name]
        if rows:
            display=[]
            for row in rows[:10]:
                item=dict(row);item['cumulative_share_pct']=100*row['cumulative_units']/row['population_units'];display.append(item)
            st.caption(f'{label}: top {len(display)} of {len(rows)}; {max(len(rows)-10,0)} omitted. Cumulative share uses the full eligible population, not just the displayed groups. Customer identifiers are removed.')
            st.dataframe(pd.DataFrame(display),hide_index=True,alt=f'{label} ranked gross sales and cumulative share')
    st.markdown('### 4. Repeat purchasing and identification coverage')
    st.metric('Within-window repeat-customer share',f"{summary['repeat_share']*100:.1f}%" if summary['repeat_share'] is not None else 'Not available')
    st.write(f"{summary['repeat_customers']:,} repeat purchasers among {summary['identified_customers']:,} identified purchasing customers. Repeat means at least two distinct eligible sales invoices in this window.")
    coverage=100*summary['identified_gross_units']/gross if gross else None
    st.caption(f"Identified-customer gross-sales coverage: {coverage:.1f}%." if coverage is not None else 'Identification coverage is unavailable without eligible sales.')
    if not summary['identified_customers']:st.info('No identified purchasing customers in this scope; repeat share is unavailable.')
    st.caption('This is observed within-window purchasing, not lifetime retention. Missing customer IDs still contribute to eligible monetary totals. No causal recommendation or realised business impact is claimed.')
    with st.expander('Quality and provenance (whole workbook)'):
        st.dataframe(pd.DataFrame(info['quality']),hide_index=True,alt='Whole-workbook disposition counts, independent of selected filters')
        st.json(info['quality_flags'])
        st.caption('Overlapping quality flags above apply to the whole workbook and must not be summed as removed rows.')
        st.write('Source workbook SHA-256: '+info['meta']['workbook_sha256'])
        st.write('Policy '+info['meta']['policy_version']+' | duplicate-looking rows retained; sensitivity view available in SQLite; timestamp conflicts flagged at invoice grain.')
        st.caption('Missing customer IDs, descriptions, duplicate-looking lines and adjustments were profiled before preparation. See docs/retail-data-contract.md for definitions and precedence.')
    with st.expander('Inspect accepted SQL and parameters'):
        for name in QUERIES:
            st.markdown('**'+name+'**');st.code((SQL/(name+'.sql')).read_text(),language='sql')
        st.json(dict(start_inclusive=start,end_exclusive=end,country=country))
    st.download_button('Download scoped SQL aggregates',json.dumps(export_payload(data,info,start,end,country),indent=2),file_name='retail-sql-aggregates.json',mime='application/json')
