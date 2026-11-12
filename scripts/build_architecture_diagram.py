"""Generate editable Excalidraw architecture and a matching README SVG preview."""
from pathlib import Path
import json
from html import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/assets"


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    elements = []
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1320" height="980" viewBox="0 0 1320 980" role="img" aria-labelledby="title desc">',
           '<title id="title">Sales Intelligence architecture and workflow</title>',
           '<desc id="desc">Sales inputs are validated for pandas analytics. The historical retail workbook is classified into SQLite and read through reconciled SQL. Streamlit displays these separate flows. Optional online AI receives aggregates after explicit user action. Tests verify both paths.</desc>',
           '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10" fill="none" stroke="#475569" stroke-width="1.5"/></marker></defs>',
           '<rect width="1320" height="980" fill="#f8fafc"/>']
    def base(identifier, kind, x, y, w, h):
        return dict(id=identifier, type=kind, x=x, y=y, width=w, height=h, angle=0,
                    strokeColor="#334155", backgroundColor="transparent", fillStyle="solid",
                    strokeWidth=2, strokeStyle="solid", roughness=1, opacity=100,
                    groupIds=[], frameId=None, roundness=None, seed=100+len(elements),
                    version=1, versionNonce=200+len(elements), isDeleted=False,
                    boundElements=None, updated=1, link=None, locked=False)
    def text(identifier, x, y, content, size=20, color="#0f172a"):
        lines=content.split('\n'); h=len(lines)*size*1.35
        item=base(identifier,"text",x,y,1200,h)
        item.update(text=content, originalText=content, fontSize=size, fontFamily=2,
                    textAlign="left", verticalAlign="top", containerId=None,
                    autoResize=True, lineHeight=1.35, strokeColor=color,
                    width=max(len(line) for line in lines)*size*.57)
        elements.append(item)
        for i,line in enumerate(lines):
            svg.append(f'<text x="{x}" y="{y+size+i*size*1.35}" font-family="Arial, sans-serif" font-size="{size}" fill="{color}">{escape(line)}</text>')
    def box(identifier,x,y,w,h,title,body,color):
        item=base(identifier,"rectangle",x,y,w,h)
        item.update(backgroundColor=color,roundness={"type":3})
        elements.append(item)
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{color}" stroke="#334155" stroke-width="2"/>')
        text(identifier+'-title',x+18,y+14,title,22)
        text(identifier+'-body',x+18,y+52,body,17,"#334155")
    def arrow(identifier,x,y,dx,dy,dashed=False):
        item=base(identifier,"arrow",x,y,abs(dx),abs(dy))
        item.update(points=[[0,0],[dx,dy]],lastCommittedPoint=None,startBinding=None,
                    endBinding=None,startArrowhead=None,endArrowhead="arrow",elbowed=False,
                    strokeStyle="dashed" if dashed else "solid")
        elements.append(item)
        dash=' stroke-dasharray="7 5"' if dashed else ''
        svg.append(f'<path d="M{x},{y} l{dx},{dy}" fill="none" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"{dash}/>')
    text('heading',40,22,'Sales Intelligence | architecture and workflow',30)
    text('subtitle',40,65,'Two analytical paths, one local-first interface. Online generation is optional.',19,'#475569')
    box('sales-input',40,120,390,120,'Sales inputs (INR / USD)','Generated sample or CSV upload\nSynthetic QA pack / Superstore', '#dbeafe')
    box('retail-input',480,120,390,120,'Historical retail input (GBP)','UCI Online Retail workbook\nLocal acquisition + source manifest','#dcfce7')
    box('scope',920,120,360,270,'Interpretation boundaries','Synthetic data is fictional\nHistorical retail: 2010–2011\nNo invented retail profit\nNo causal uplift claims\nNo realised impact claimed\nSeparate currencies and contracts','#fef3c7')
    box('sales-validation',40,285,390,120,'Validate and audit','Dates, IDs, numeric ranges, discounts\nRecorded profit = revenue − cost','#dbeafe')
    box('retail-prep',480,285,390,120,'Classify and prepare SQLite','Contract, exclusions, quarantine\nAtomic rebuild + exact GBP units','#dcfce7')
    box('sales-engine',40,450,390,120,'Pandas analytics','KPIs, decisions, loss exposure\nForecast validation + anomaly screening','#dbeafe')
    box('retail-sql',480,450,390,120,'Read-only, parameterised SQL','Trends, exposure, concentration, repeat\nIndependent Python reconciliation','#dcfce7')
    box('interface',40,635,830,135,'Streamlit interface | source, dates and dimension filters','Separate sales dashboard and Real-data SQL view; lazy tabs and cached results\nCharts, scoped tables, definitions, cleaning reports and aggregate downloads','#ede9fe')
    box('online-ai',920,635,360,135,'Optional online AI','Explicit toggle + user action\nGroq / Gemini / Anthropic\nAggregates in; generated text out','#ffedd5')
    box('verification',40,840,1240,100,'Verification and portfolio evidence','Offline pytest + UI flows | Python 3.11 / 3.12 CI + dependency audit | deterministic reports + exact-value QA references','#e2e8f0')
    for x in (235,675):
        arrow(f'{x}-a',x,240,0,45);arrow(f'{x}-b',x,405,0,45);arrow(f'{x}-c',x,570,0,65)
    arrow('opt-in',870,704,50,0,True)
    text('ai-note',935,798,'No provider request in local mode',16,'#475569')
    text('footer',40,951,'Editable source: architecture.excalidraw | SVG preview generated from the same layout',15,'#475569')
    svg.append('</svg>')
    (OUT/'architecture.excalidraw').write_text(json.dumps(dict(type="excalidraw",version=2,source="https://excalidraw.com",elements=elements,appState=dict(viewBackgroundColor="#f8fafc",gridSize=None),files={}),indent=2)+'\n',encoding='utf-8')
    (OUT/'architecture.svg').write_text('\n'.join(svg)+'\n',encoding='utf-8')


if __name__ == '__main__':
    build()
