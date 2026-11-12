"""Named, parameterised SQL and an independent Python reconciliation oracle."""
from collections import defaultdict
from contextlib import closing
from datetime import datetime
from pathlib import Path
from sales_ai.retail import readonly

QUERIES=['10_monthly','20_stock_code_exposure','20_country_exposure','30_stock_code_concentration','30_customer_id_concentration','40_repeat','41_purchase_sequence']
SQL=Path(__file__).resolve().parents[1]/'sql/online_retail'

def run(connection,name,start,end,country=None):
    if name not in QUERIES: raise ValueError('Unknown named query')
    for value in (start,end):
        if datetime.strptime(value,'%Y-%m-%d').strftime('%Y-%m-%d')!=value: raise ValueError('Use canonical YYYY-MM-DD dates')
    if start>=end: raise ValueError('End must be after start (exclusive)')
    cursor=connection.execute((SQL/(name+'.sql')).read_text(),dict(start=start,end=end,country=country))
    return [dict(zip([c[0] for c in cursor.description],row)) for row in cursor]

def reconcile(connection,start,end,country=None):
    # Reads canonical line records, never a SQL aggregate or query output as the oracle.
    rows=[dict(zip(['invoice','product','customer','country','date','units','kind'],r)) for r in connection.execute('SELECT invoice_id,stock_code,customer_id,country,timestamp,line_units,disposition FROM lines')]
    selected=[r for r in rows if r['date'] is not None and start<=r['date']<end and (country is None or r['country']==country)]
    outputs={name:run(connection,name,start,end,country) for name in QUERIES}
    def exposure(dim):
        groups=defaultdict(lambda: [0,0])
        for r in selected:
            if r['kind']=='sale': groups[r[dim]][0]+=r['units']
            elif r['kind']=='cancellation': groups[r[dim]][1]-=r['units']
        return groups
    for dim,name in [('product','20_stock_code_exposure'),('country','20_country_exposure')]:
        expected=exposure(dim); actual=outputs[name]
        assert {r['group_key']:(r['gross_units'],r['cancellation_units']) for r in actual}=={k:tuple(v) for k,v in expected.items()}
        for r in actual:
            ratio=r['cancellation_units']/r['gross_units'] if r['gross_units'] else None
            assert r['cancellation_sales_ratio']==ratio
    for dim,name in [('product','30_stock_code_concentration'),('customer','30_customer_id_concentration')]:
        grouped=defaultdict(int)
        for r in selected:
            if r['kind']=='sale' and r[dim] is not None: grouped[r[dim]]+=r['units']
        cumulative=0
        expected=[]
        for i,(key,value) in enumerate(sorted(grouped.items(),key=lambda kv:(-kv[1],kv[0])),1):
            cumulative+=value
            expected.append(dict(group_key=key,gross_units=value,position=i,population_units=sum(grouped.values()),cumulative_units=cumulative))
        assert outputs[name]==expected
    customers=defaultdict(set); invoices=set();gross=identified=0
    for r in selected:
        if r['kind']=='sale':
            gross+=r['units'];invoices.add(r['invoice'])
            if r['customer'] is not None: customers[r['customer']].add(r['invoice']);identified+=r['units']
    repeat=sum(len(v)>=2 for v in customers.values())
    assert outputs['40_repeat']==[dict(identified_customers=len(customers),repeat_customers=repeat,repeat_share=repeat/len(customers) if customers else None,gross_units=gross,identified_gross_units=identified,sales_invoices=len(invoices))]
    purchases={}
    for r in rows:
        if r['date'] is not None and r['date']<end and r['kind']=='sale' and r['customer'] is not None and (country is None or r['country']==country):
            key=(r['customer'],r['invoice']);purchases[key]=min(purchases.get(key,r['date']),r['date'])
    expected=[];counts=defaultdict(int)
    for (customer,invoice),date in sorted(purchases.items(),key=lambda kv:(kv[0][0],kv[1],kv[0][1])):
        counts[customer]+=1
        if date>=start: expected.append(dict(customer_id=customer,invoice_id=invoice,purchase_time=date,purchase_number=counts[customer]))
    assert outputs['41_purchase_sequence']==expected
    months=defaultdict(lambda: [0,0,set()]);last_month=max((r['date'][:7] for r in rows if r['date'] is not None),default='')
    for r in selected:
        m=r['date'][:7]+'-01';g=months[m]
        if r['kind']=='sale':g[0]+=r['units'];g[2].add(r['invoice'])
        elif r['kind']=='cancellation':g[1]-=r['units']
    expected=[];previous=None
    for m,g in sorted(months.items()):
        year,month=map(int,m[:7].split('-'));following=f'{year+int(month==12):04d}-{month%12+1:02d}-01'
        if m<start or following>end or m[:7]>=last_month:continue
        growth=None
        if previous and previous[1]==m and previous[2]>0:growth=(g[0]-previous[2])/previous[2]
        expected.append(dict(month=m,gross_units=g[0],cancellation_units=g[1],net_units=g[0]-g[1],sales_invoices=len(g[2]),growth=growth));previous=(m,following,g[0])
    assert outputs['10_monthly']==expected
    return {'queries_checked':len(QUERIES),'selected_line_count':len(selected),'gross_units':gross,'identified_gross_units':identified,'sales_invoices':len(invoices),'identified_customers':len(customers),'repeat_customers':repeat,'all_queries_match_independent_python':True,'output_rows':{k:len(v) for k,v in outputs.items()}}
