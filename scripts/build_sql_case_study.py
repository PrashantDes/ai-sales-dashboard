"""Reproduce aggregate-only historical evidence from accepted SQL; no AI/network."""
from contextlib import closing
from decimal import Decimal, ROUND_HALF_EVEN
import argparse
import hashlib
import json
from pathlib import Path
import sys
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sales_ai.retail import readonly
from sales_ai.retail_queries import run, reconcile, SQL

START, END = '2010-12-01', '2011-12-01'


def money(units):
    return 'GBP ' + format((Decimal(int(units))/1000).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN), ',.2f')


def charts(monthly, exposure):
    """Standard headless plots from SQL aggregates; deterministic in one environment."""
    import io
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    matplotlib.rcParams['svg.hashsalt']='retail-sql-contract-v1'
    fig, axes=plt.subplots(2,1,figsize=(12,8),layout='constrained')
    fig.suptitle('UCI Online Retail | Dec 2010-Nov 2011 | recorded merchandise values',fontsize=15)
    axes[0].bar([r['month'][:7] for r in monthly],[r['gross_units']/1000 for r in monthly],color='#2563eb')
    axes[0].set_title('Monthly gross merchandise sales (GBP)',loc='left')
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda x,_: f'{x/1e6:.1f}m'))
    axes[0].set_ylabel('GBP millions');axes[0].tick_params(axis='x',labelsize=8)
    top=exposure[:10]
    axes[1].barh([r['group_key'] for r in top],[r['cancellation_units']/1000 for r in top],color='#c2410c')
    axes[1].invert_yaxis();axes[1].set_title('Largest product cancellation exposure (top 10)',loc='left')
    axes[1].set_xlabel('GBP (recorded credits, not verified return losses)')
    axes[1].xaxis.set_major_formatter(FuncFormatter(lambda x,_: f'{x:,.0f}'))
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y' if ax is axes[0] else 'x',alpha=.2);ax.set_axisbelow(True)
    svg=io.BytesIO();png=io.BytesIO()
    fig.savefig(svg,format='svg',metadata={'Date':None,'Creator':'Sales Intelligence Dashboard','Title':'Historical UCI retail SQL aggregates'})
    fig.savefig(png,format='png',dpi=130,metadata={'Software':'Sales Intelligence Dashboard'})
    plt.close(fig)
    return svg.getvalue().decode('utf-8'),png.getvalue()


def build(output_dir=ROOT/'docs', db=ROOT/'data/processed/online-retail.sqlite'):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with closing(readonly(db)) as con:
        meta = dict(con.execute('SELECT key,value FROM metadata'))
        accepted = json.loads((ROOT/'docs/evidence/phase-2/quality.json').read_text())
        assert meta['workbook_sha256'] == accepted['source_identity']['workbook_sha256']
        assert meta['analytical_sha256'] == accepted['analytical_sha256']
        content=hashlib.sha256()
        for record in con.execute('SELECT * FROM lines ORDER BY source_row'):
            content.update(json.dumps(record,ensure_ascii=False).encode())
        assert content.hexdigest()==meta['analytical_sha256'], 'Analytical rows changed; reverify preparation'
        assert meta['policy_version']=='1.0' and meta['price_scale']=='1000'
        verification = reconcile(con, START, END)
        names = ['10_monthly', '20_stock_code_exposure', '20_country_exposure', '30_stock_code_concentration', '40_repeat']
        results = {name: run(con, name, START, END) for name in names}
        customers = run(con, '30_customer_id_concentration', START, END)
    monthly, exposure, summary = results['10_monthly'], results['20_stock_code_exposure'], results['40_repeat'][0]
    gross = summary['gross_units']
    cancel = sum(r['cancellation_units'] for r in exposure)
    peak, lead = max(monthly, key=lambda r: r['gross_units']), exposure[0]
    coverage = summary['identified_gross_units']/gross
    top10 = sum(r['gross_units'] for r in customers[:10])
    concentration = top10/summary['identified_gross_units']
    ratio = lead['cancellation_sales_ratio']
    findings = [
        dict(id='monthly_peak', query='10_monthly.sql', evidence=f"{peak['month'][:7]} has the largest complete-month gross merchandise sales: {money(peak['gross_units'])}, across {peak['sales_invoices']:,} sales invoices.", action='Investigate product/country mix and operational capacity before using this month as a stock-planning benchmark.', limitation='One observed annual cycle cannot establish seasonality, promotion effectiveness, stock shortages or the cause of the peak.'),
        dict(id='cancellation_exposure', query='20_stock_code_exposure.sql', evidence=f"Product {lead['group_key']} has the largest cancellation exposure: {money(lead['cancellation_units'])}; gross sales are {money(lead['gross_units'])}." + (f' Its same-window cancellation-to-sales ratio is {ratio*100:.1f}%.' if ratio is not None else ' Its ratio is unavailable because gross sales are zero.'), action='Review invoice/cancellation records and fulfilment history before deciding whether a process investigation is warranted.', limitation='Credits are not matched to original sales and may relate to earlier purchases. This is not a verified return rate or recoverable-savings estimate.'),
        dict(id='identified_repeat', query='40_repeat.sql', supporting_query='30_customer_id_concentration.sql', evidence=f"{summary['repeat_customers']:,} of {summary['identified_customers']:,} identified purchasers bought on at least two distinct invoices ({summary['repeat_share']*100:.1f}%). Identified customers cover {coverage*100:.1f}% of gross sales. The top 10 identified customer groups contribute {concentration*100:.1f}% of identified-customer gross sales.", action='Check customer-ID coverage and concentration before proposing a retention pilot; define a control group and predeclared outcome before measuring an intervention.', limitation='Within-window repeat purchasing is not lifetime retention. Missing IDs are excluded from customer denominators. No intervention or commercial uplift has been measured.')]
    payload = dict(data_kind='real historical public dataset', scope=dict(start_inclusive=START, end_exclusive=END, country=None), currency='GBP', monetary_unit='0.001 GBP', source=meta, queries=results, summary=dict(gross_units=gross, cancellation_units=cancel, net_units=gross-cancel, identified_coverage=coverage, top10_identified_customer_gross_units=top10, top10_identified_customer_share=concentration), findings=findings, quality_whole_workbook=accepted, independent_verification=verification, query_sha256={name: hashlib.sha256((SQL/name).read_bytes()).hexdigest() for name in [*[n+'.sql' for n in names], '30_customer_id_concentration.sql']})
    sections = []
    for i, f in enumerate(findings, 1):
        sections.append(f"### {i}. {f['id'].replace('_',' ').title()}\n\n**Evidence:** {f['evidence']}\n\n**Proposed action:** {f['action']}\n\n**Limit:** {f['limitation']}\n\n[Inspect SQL](../sql/online_retail/{f['query']})" + (f" · [Supporting SQL](../sql/online_retail/{f['supporting_query']})" if 'supporting_query' in f else ''))
    table = '\n'.join(f"| {r['month'][:7]} | {money(r['gross_units'])} | {money(r['cancellation_units'])} | {r['sales_invoices']:,} |" for r in monthly)
    report = f'''# Real-data case study: where should a retailer investigate first?

An independent portfolio investigation of **historical UCI Online Retail transactions**, not a client engagement, current-company assessment or measured business improvement.

## Business question and fixed scope

Where should the retailer investigate sales variation, cancellation exposure and dependence on identified repeat purchasers before making operational or customer-activity decisions?

- Selection: **1 December 2010 through 30 November 2011 inclusive**, all countries; SQL start `{START}`, exclusive end `{END}`.
- December 2011 is incomplete and excluded. The first 12 observed months are provisionally complete, not proof of an uninterrupted export.
- Source workbook SHA-256: `{meta['workbook_sha256']}`; preparation policy/schema 1.0; source-local naive dates; GBP.
- Exact thousandths of GBP are retained; final displays use decimal half-even penny rounding.

## Headline recorded values

| Metric | Selected window |
| --- | ---: |
| Gross merchandise sales | {money(gross)} |
| Cancellation exposure | {money(cancel)} |
| Recorded net merchandise value | {money(gross-cancel)} |
| Distinct sales invoices | {summary['sales_invoices']:,} |

Gross minus cancellation exposure is not profit or audited net revenue; other adjustments/nonmerchandise records are excluded by the contract. Trace figures through [aggregate evidence](sql-case-study.json), [exposure SQL](../sql/online_retail/20_stock_code_exposure.sql), and [scope summary SQL](../sql/online_retail/40_repeat.sql).

## Three findings and proposed investigations

{chr(10).join(sections)}

## Computed charts and source table

![Actual SQL aggregate charts: complete-month sales and top product cancellation exposure](sql-case-study-charts.svg)

This is a generated chart, not an application screenshot. Product exposure shows 10 of {len(exposure)} groups; {max(len(exposure)-10,0)} omitted groups remain in JSON. Customer identities and individual purchase sequences are not published.

| Complete month | Gross merchandise sales | Cancellation value | Distinct sales invoices |
| --- | ---: | ---: | ---: |
{table}

## Preparation judgments and population impact

The following counts cover the **entire {accepted['source_rows']:,}-row workbook**, including December 2011, not just this report's window. Every row remains in staging.

- Eligible sales lines: {accepted['dispositions']['sale']:,}; eligible cancellation lines: {accepted['dispositions']['cancellation']:,}.
- Excluded lines: {accepted['dispositions'].get('excluded',0):,}; quarantined lines: {accepted['dispositions'].get('quarantined',0):,}. Mutually exclusive dispositions sum to {accepted['source_rows']:,}.
- {accepted['overlapping_flags'].get('missing_customer',0):,} missing customer IDs remain nullable: eligible monetary values remain, but customer denominators exclude them. Selected-window coverage is disclosed above.
- {accepted['overlapping_flags'].get('missing_description',0):,} missing descriptions do not invalidate otherwise eligible product-code records.
- {accepted['overlapping_flags'].get('duplicate_excess',0):,} duplicate-looking excess rows are flagged and retained, not assumed erroneous. Excluding them in the SQLite sensitivity view changes the whole-workbook, all-disposition signed bridge by {money(accepted['retained_signed_units']-accepted['deduplicated_sensitivity_signed_units'])}. This is not a gross-merchandise-sales effect or confirmed correction; the retained policy remains primary.
- Negative prices are quarantined. Zero-value records, known nonmerchandise codes and unmatched negative adjustments are separately excluded. Nonstandard code syntax alone does not establish invalid merchandise.
- Source prices have up to three decimal places; rounding every line to pennies could alter the financial bridge and is not performed.

See [treatment rules](retail-data-contract.md), [profile](evidence/phase-1/profile.json), [preparation bridge](evidence/phase-2/quality.json), and [query catalogue](sql-query-catalogue.md). Flags overlap and must not be added as row removals.

## Validation and limits

Generation reruns the independent Python oracle for exactly the same scope before writing files. All seven queries reconcile, even though customer rankings and purchase sequences are not exported. Report figures, chart inputs and narrative come from those accepted results, avoiding hand-entered totals.

Monthly changes require adjacent complete calendar months and a nonzero prior base. Cancellation ratios are not matched-sale return rates and may exceed 100%. Concentration denominators include the full eligible population, including chart omissions. Repeated lines do not imply repeat purchases. Product labels are codes, without future-looking descriptions.

No costs, profit, causal effects, cancellation reasons, verified sale-credit links or intervention outcomes are available. Findings justify investigations, not automatic budget changes. A future pilot needs a predeclared outcome, comparison/control strategy and operational guardrails. No stakeholder approval or pilot result is claimed. Aggregation/removing identifiers does not establish anonymisation.

## Reproduce and inspect

```powershell
python scripts/prepare_online_retail.py
python scripts/verify_retail_sql.py
python scripts/build_sql_case_study.py
python -m pytest
```

To inspect the same selection in the app, choose **Real-data SQL (GBP)**, dates **2010-12-01 through 2011-11-30**, and **All countries**. The app default includes partial December 2011, so its default totals differ.

If the local workbook is absent, follow [source instructions](retail-provenance.md) first and review changed hashes. Report/JSON/SVG omit timestamps so their content is deterministic; environment/hash evidence is separate. The [synthetic case](case-study.md) is a separate demonstration, not part of these real-data results.

## Attribution

Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. [Official source](https://archive.ics.uci.edu/dataset/352/online+retail), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). This project classifies, aggregates and charts the data; its creator has not endorsed this analysis.
'''
    (output_dir/'sql-case-study.md').write_text(report, encoding='utf-8')
    (output_dir/'sql-case-study.json').write_text(json.dumps(payload, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    svg,png=charts(monthly,exposure)
    (output_dir/'sql-case-study-charts.svg').write_text(svg,encoding='utf-8')
    (output_dir/'sql-case-study-charts.png').write_bytes(png)
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'docs')
    args = parser.parse_args()
    payload = build(args.output_dir)
    print(json.dumps(dict(scope=payload['scope'], summary=payload['summary'], findings=payload['findings']), indent=2))
