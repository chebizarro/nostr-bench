"""Generate a self-contained results.html dashboard from report/dash.json."""
import json, os, html, glob, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
D = json.load(open(os.path.join(HERE, "dash.json")))
cells = D["cells"]; M = D["meta"]

def short(m): return m.split("/")[-1]

# ---- Phase 2: one-shot vs agent on the code tasks (n1_implement + n2_debug) ----
CODE = {"n1_implement", "n2_debug"}
_rows = [json.load(open(p)) for p in glob.glob(os.path.join(ROOT, "runs", "*.json"))
         if not os.path.basename(p).startswith("_")]
_rows = [r for r in _rows if "model" in r and not r.get("error") and r.get("task") in CODE]
_agg = {}
for r in _rows:
    _agg.setdefault((r["model"], r["mode"]), []).append(r["score"])
def _mean(xs): return round(st.mean(xs), 1) if xs else None
compare = []
for m in sorted({k[0] for k in _agg}):
    o = _mean(_agg.get((m, "oneshot"), [])); a = _mean(_agg.get((m, "microagent"), []))
    if a is None:  # models that didn't advance (no agent runs) are out of this view
        continue
    compare.append({"model": m, "oneshot": o, "agent": a,
                    "delta": (round(a - o, 1) if o is not None else None),
                    "local": next((c["tier_local"] for c in cells if c["model"] == m), False)})
compare.sort(key=lambda c: -(c["agent"] or 0))

# whole-project totals (both phases), for the cost KPI
_all = [json.load(open(p)) for p in glob.glob(os.path.join(ROOT, "runs", "*.json"))
        if not os.path.basename(p).startswith("_")]
_all = [r for r in _all if "model" in r]
TOTAL_COST = round(sum((r.get("cost_usd") or 0) for r in _all), 2)
TOTAL_RUNS = len(_all)
REPS = M.get("reps", 1)

# oracle/planner sweep (Repo Prompt CE), if present
_sweep_path = os.path.join(ROOT, "runs", "_oracle_sweep.json")
SWEEP = json.load(open(_sweep_path))["sweep"] if os.path.exists(_sweep_path) else {}

# task matrix sequential color (0..100) -> aqua ramp light
def heat(v):
    if v is None: return "var(--muted-fill)"
    t = max(0, min(100, v)) / 100
    # interpolate pale->aqua (#eaf6f1 -> #199e70)
    a=(234,246,241); b=(25,158,112)
    c=tuple(round(a[i]+(b[i]-a[i])*t) for i in range(3))
    return f"rgb({c[0]},{c[1]},{c[2]})"

# ---- bar chart (mean accuracy, with n=3 min–max range whisker) ----
bw=760; bh=len(cells)*30+20; barmax=100; bx0=230
def BX(v): return bx0+(v or 0)/barmax*(bw-bx0-30)
bars=[]
for i,c in enumerate(cells):
    y=10+i*30; w=BX(c["acc"])-bx0
    local = c["tier_local"]
    lo=c.get("acc_min"); hi=c.get("acc_max")
    whisker=""
    if lo is not None and hi is not None and hi>lo:
        whisker=(f'<line x1="{BX(lo):.1f}" y1="{y+12}" x2="{BX(hi):.1f}" y2="{y+12}" stroke="var(--text-secondary)" stroke-width="1.5" opacity="0.5"/>'
                 f'<line x1="{BX(lo):.1f}" y1="{y+8}" x2="{BX(lo):.1f}" y2="{y+16}" stroke="var(--text-secondary)" stroke-width="1.5" opacity="0.5"/>'
                 f'<line x1="{BX(hi):.1f}" y1="{y+8}" x2="{BX(hi):.1f}" y2="{y+16}" stroke="var(--text-secondary)" stroke-width="1.5" opacity="0.5"/>')
    bars.append(f'''<g class="row">
  <text x="222" y="{y+15}" text-anchor="end" class="bl">{html.escape(short(c['model']))}</text>
  <rect x="{bx0}" y="{y+4}" width="{w:.1f}" height="16" rx="4" fill="var(--series-1)" class="{'loc' if local else ''}"><title>{html.escape(short(c['model']))}: mean {c['acc']} (range {lo}–{hi})</title></rect>
  {whisker}
  <text x="{BX(c['acc'])+6:.1f}" y="{y+15}" class="vl">{c['acc']}{' ◆' if local else ''}</text>
</g>''')
barsvg=f'<svg viewBox="0 0 {bw} {bh}" class="chart" role="img" aria-label="Mean accuracy by model">{"".join(bars)}</svg>'

# ---- scatter accuracy vs cost/run (log x) ----
import math
sw,sh=760,420; padL,padB,padT,padR=54,44,16,120
xs=[max((c["cost"] or 0)/max(c["n"],1),1e-5) for c in cells]
xmin,xmax=1e-4,0.1
def X(v):
    v=max(xmin,min(xmax,v)); return padL+(math.log10(v)-math.log10(xmin))/(math.log10(xmax)-math.log10(xmin))*(sw-padL-padR)
def Y(v): return sh-padB-(v/100)*(sh-padB-padT)
dots=[]
for c in cells:
    cx=X((c["cost"] or 0)/max(c["n"],1)); cy=Y(c["acc"] or 0)
    col="var(--series-1)" if c["tier_local"] else "var(--series-2)"
    dots.append(f'''<g class="dot"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{col}" stroke="var(--surface-1)" stroke-width="2"><title>{html.escape(short(c['model']))}
mean {c['acc']}  ·  ${ (c['cost'] or 0)/max(c['n'],1):.4f}/run</title></circle>
  <text x="{cx+9:.1f}" y="{cy+4:.1f}" class="sl">{html.escape(short(c['model']))}</text></g>''')
# axes ticks
xticks="".join(f'<text x="{X(v):.1f}" y="{sh-padB+16}" class="ax" text-anchor="middle">${v:g}</text><line x1="{X(v):.1f}" y1="{padT}" x2="{X(v):.1f}" y2="{sh-padB}" class="grid"/>' for v in [0.0001,0.001,0.01,0.1])
yticks="".join(f'<text x="{padL-8}" y="{Y(v)+4:.1f}" class="ax" text-anchor="end">{v}</text><line x1="{padL}" y1="{Y(v):.1f}" x2="{sw-padR}" y2="{Y(v):.1f}" class="grid"/>' for v in [0,25,50,75,100])
scsvg=f'''<svg viewBox="0 0 {sw} {sh}" class="chart" role="img" aria-label="Accuracy versus cost per run">
{yticks}{xticks}
<text x="{padL}" y="{sh-6}" class="axt">cost per run (USD, log)  →</text>
<text transform="translate(14,{padT+90}) rotate(-90)" class="axt">mean accuracy →</text>
{"".join(dots)}</svg>'''

# ---- Phase 2 dumbbell: one-shot -> agent on code tasks ----
dw=760; rowh=32; dh=len(compare)*rowh+34; dL=170; dR=70
def DX(v): return dL+(v/100)*(dw-dL-dR)
dgrid="".join(f'<text x="{DX(v):.0f}" y="16" class="ax" text-anchor="middle">{v}</text><line x1="{DX(v):.0f}" y1="22" x2="{DX(v):.0f}" y2="{dh-8}" class="grid"/>' for v in [0,25,50,75,100])
drows=[]
for i,c in enumerate(compare):
    y=30+i*rowh; xo=DX(c["oneshot"] or 0); xa=DX(c["agent"] or 0)
    d=c["delta"]; dcol="var(--pos)" if (d or 0)>=0 else "var(--neg)"
    drows.append(f'''<g>
  <text x="{dL-10}" y="{y+4}" text-anchor="end" class="bl">{html.escape(short(c['model']))}{' ▪' if c['local'] else ''}</text>
  <line x1="{xo:.0f}" y1="{y}" x2="{xa:.0f}" y2="{y}" stroke="var(--line)" stroke-width="3"/>
  <circle cx="{xo:.0f}" cy="{y}" r="5.5" fill="var(--series-2)"><title>{html.escape(short(c['model']))} one-shot: {c['oneshot']}</title></circle>
  <circle cx="{xa:.0f}" cy="{y}" r="5.5" fill="var(--series-1)"><title>{html.escape(short(c['model']))} agent: {c['agent']}</title></circle>
  <text x="{dw-dR+10}" y="{y+4}" class="vl" fill="{dcol}">{('+' if (d or 0)>=0 else '')}{d}</text>
</g>''')
dumbsvg=f'<svg viewBox="0 0 {dw} {dh}" class="chart" role="img" aria-label="One-shot vs agent on code tasks">{dgrid}{"".join(drows)}</svg>'

# ---- oracle/planner sweep card ----
_sweep_card = ""
if SWEEP:
    order = sorted(SWEEP.items(), key=lambda kv: -kv[1])
    rows_s = "".join(
        f'<tr><td class=m>{html.escape(k)}</td>'
        f'<td class=num style="color:{"var(--pos)" if v>=100 else "var(--neg)"}">{v}</td>'
        f'<td>{"✓ correct" if v>=100 else "missed a bug"}</td></tr>' for k, v in order)
    _sweep_card = (
        '<h2 style="margin-top:20px">Planner sweep — which oracle writes the best fix?</h2>'
        '<p class=note>Each model as the Repo Prompt oracle, producing the full N2 fix; graded on the hidden suite. Single run each.</p>'
        '<table style="max-width:520px"><tr><th>oracle model</th><th>fix score</th><th></th></tr>'
        + rows_s + '</table>'
        '<p class=note style="margin-top:6px">Nearly every planner — <b>including the local Muse Glimmer 30B</b> — produces a fully correct fix. The lone miss is frontier <b>GLM-5.2</b>, which compared the tag name against <code>"#e"</code> instead of <code>"e"</code>: a subtle nostr-specific slip a generic planner makes and a nostr-aware one doesn\'t.</p>')

# ---- rows for table + heatmap ----
def td(v, cls=""):
    return f'<td class="{cls}">{"" if v is None else v}</td>'
trows=[]
for c in cells:
    trows.append("<tr>"
      f'<td class="m">{html.escape(short(c["model"]))}</td>'
      f'<td>{"▪ " + str(c["vram"]) + "GB" if c["tier_local"] else ("○ "+str(c["vram"])+"GB" if c["local_any"] else "cloud")}</td>'
      f'<td class="num strong">{c["acc"]}</td>'
      f'<td class="num">{c["nostr"]}</td><td class="num">{c["sec"]}</td>'
      + "".join(f'<td class="num" style="background:{heat(c[t])}">{"" if c[t] is None else c[t]}</td>' for t in ["n1_implement","n2_debug","s1_audit","s2_nostr_sec"])
      + f'<td class="num">{c["t1"]}</td><td class="num">{c["t2"]}</td>'
      f'<td class="num {"pos" if (c["sens"] or 0)>0 else "neg"}">{("+" if (c["sens"] or 0)>0 else "")}{c["sens"]}</td>'
      f'<td class="num">${c["cost"]}</td>'
      f'<td class="num">{("{:,}".format(int(c["pts_per_dollar"])) if c["pts_per_dollar"] else "")}</td>'
      f'<td class="miss">{("−"+str(c["missing"])) if c["missing"] else ""}</td>'
      "</tr>")

# KPI picks
cloud_best=max(cells,key=lambda c:c["acc"] or 0)
# value pick = best accuracy among the near-free models (Pareto frontier), not the
# absolute cheapest — pts/$ alone rewards zero-cost regardless of quality.
# value = best points-per-dollar among models that clear a real accuracy bar
_solid=[c for c in cells if (c["acc"] or 0) >= 60 and c.get("pts_per_dollar")]
value_best=max(_solid or cells,key=lambda c:c.get("pts_per_dollar") or 0)
local_best=max([c for c in cells if c["tier_local"]],key=lambda c:c["acc"] or 0)

HTML=f"""<!doctype html><html lang=en><head><meta charset=utf8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>nostr-bench · Phase 1 results</title>
<style>
:root{{--surface-1:#fcfcfb;--surface-2:#f4f4f1;--text-primary:#0b0b0b;--text-secondary:#52514e;--muted:#8a8a84;
--series-1:#2a78d6;--series-2:#eb6834;--line:#e3e2dd;--muted-fill:#efeeea;--grid:#ecebe6;--pos:#008300;--neg:#e34948;}}
:root[data-theme=dark]{{--surface-1:#1a1a19;--surface-2:#232322;--text-primary:#fff;--text-secondary:#c3c2b7;--muted:#8f8e86;
--series-1:#3987e5;--series-2:#d95926;--line:#333;--muted-fill:#2a2a28;--grid:#2b2b29;--pos:#33a852;--neg:#e66767;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--surface-2);color:var(--text-primary);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:28px 20px 80px}}
h1{{font-size:24px;margin:0 0 2px}}.sub{{color:var(--text-secondary);margin:0 0 20px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0 26px}}
.kpi{{background:var(--surface-1);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
.kpi .k{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
.kpi .v{{font-size:19px;font-weight:650;margin-top:3px}}.kpi .d{{font-size:12px;color:var(--text-secondary);margin-top:2px}}
.card{{background:var(--surface-1);border:1px solid var(--line);border-radius:12px;padding:18px 18px 12px;margin:16px 0}}
.card h2{{font-size:15px;margin:0 0 4px}}.card p.note{{color:var(--text-secondary);font-size:13px;margin:0 0 10px}}
.chart{{width:100%;height:auto}}
.bl{{fill:var(--text-secondary);font-size:12px}}.vl{{fill:var(--text-primary);font-size:12px;font-weight:600}}
.sl{{fill:var(--text-secondary);font-size:11px}}.ax{{fill:var(--muted);font-size:11px}}.axt{{fill:var(--text-secondary);font-size:12px}}
.grid{{stroke:var(--grid);stroke-width:1}}
rect.loc{{stroke:var(--text-primary);stroke-opacity:.28;stroke-width:1.5}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{padding:5px 7px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}}
th{{position:sticky;top:0;background:var(--surface-1);cursor:pointer;color:var(--text-secondary);font-weight:600;text-align:right;user-select:none}}
th:first-child,td.m,td:nth-child(2){{text-align:left}}td.m{{font-weight:600}}
td.num.strong{{font-weight:700}}.pos{{color:var(--pos)}}.neg{{color:var(--neg)}}.miss{{color:var(--muted)}}
.legend{{font-size:12px;color:var(--text-secondary);margin:2px 0 0}}.sw{{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:middle;margin:0 4px 0 10px}}
.toggle{{float:right;font-size:12px;border:1px solid var(--line);background:var(--surface-1);color:var(--text-secondary);
border-radius:8px;padding:5px 10px;cursor:pointer}}
.tablewrap{{overflow-x:auto}}
.foot{{color:var(--muted);font-size:12px;margin-top:18px}}
</style></head><body>
<div class=wrap>
<button class=toggle onclick="document.documentElement.dataset.theme=document.documentElement.dataset.theme=='dark'?'light':'dark'">◑ theme</button>
<h1>nostr-bench — Phases 1–3</h1>
<p class=sub>12 models (incl. Kimi K3) × 4 suites × 2 tiers, n=3 · + agent harness + Repo Prompt CE orchestration & planner sweep · median of 3 reps · via OpenRouter · {M['date']}</p>

<div class=kpis>
<div class=kpi><div class=k>Best accuracy (cloud)</div><div class=v>{short(cloud_best['model'])}</div><div class=d>mean {cloud_best['acc']} / 100</div></div>
<div class=kpi><div class=k>Best bang-for-buck</div><div class=v>{short(value_best['model'])}</div><div class=d>mean {value_best['acc']} at ${value_best['cost']/max(value_best['n'],1):.4f}/run</div></div>
<div class=kpi><div class=k>Best local (≤24 GB)</div><div class=v>{short(local_best['model'])}</div><div class=d>mean {local_best['acc']} · runs on a P40</div></div>
<div class=kpi><div class=k>Total cost · both phases</div><div class=v>${TOTAL_COST}</div><div class=d>{TOTAL_RUNS} runs</div></div>
</div>

<div class=card>
<h2>Mean accuracy by model</h2>
<p class=note>Mean of all four suites (0–100). ◆ / outlined bar = runs locally on ≤24 GB (your P40 rig).</p>
{barsvg}
</div>

<div class=card>
<h2>Phase 2 — does an agent harness change the ranking?</h2>
<p class=note>Code tasks only (N1 implement + N2 debug, both tiers). <span class=sw style="background:var(--series-2)"></span>one-shot → <span class=sw style="background:var(--series-1)"></span>agent (4-tool loop, runs the visible tests as feedback). Δ = agent − one-shot. Sorted by agent score. ▪ = runs on ≤24 GB.</p>
{dumbsvg}
<p class=note style="margin-top:8px">The harness is an <b>equalizer</b>: models that can't one-shot hard code (gpt-oss-20b/120b, muse-glimmer) leap +50–65 when they can iterate against tests, while models that already one-shot well (kimi, deepseek) slip a little as the multi-turn loop adds under-scoping. qwen models mostly decline to drive the loop (call done early). Agent runs are noisier than one-shot (see the wide spreads); n=3, treat small gaps as ties.</p>
</div>

<div class=card>
<h2>Phase 3 — Repo Prompt CE orchestration (N2 debug)</h2>
<p class=note>The oracle/editor split, run natively through Repo Prompt CE on-device: a strong planner writes the plan, a cheap open model applies it.</p>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:6px">
<div class=kpi><div class=k>Oracle → editor pairing</div><div class=v style="color:var(--pos)">100 / 100</div><div class=d>Oracle <b>gpt-oss-120b</b> planned all 5 bugs exactly; editor <b>gpt-oss-20b</b> (OpenCode agent) applied it on-device → 6/6 hidden + 2/2 visible regression, no signature changes.</div></div>
<div class=kpi><div class=k>Same editor, N2, unaided</div><div class=v>0 → 50 → 100</div><div class=d>gpt-oss-20b alone: <b>0</b> one-shot, <b>50</b> in the solo agent harness, <b>100</b> with the oracle's plan. Orchestration lifts the cheap editor to a perfect fix.</div></div>
</div>
<p class=note style="margin-top:8px">Takeaway: the orchestration win is real and it's the <b>oracle</b> doing the heavy lifting — a strong planner turns a fuzzy bug report into an exact, apply-ready plan, and a 30B-class editor that couldn't touch this task alone applies it perfectly. Note: the open-model editor only wrote files in an <i>interactive</i> RepoPrompt session; the same agent completed headlessly twice without editing, so this arm needs a human at the keyboard for now.</p>
{_sweep_card}
</div>

<div class=card>
<h2>Accuracy vs. cost per run</h2>
<p class=note>Up = more accurate, left = cheaper. Log cost axis. <span class=sw style="background:var(--series-1)"></span>local-capable (≤24 GB) <span class=sw style="background:var(--series-2)"></span>cloud / bigger-iron.</p>
{scsvg}
</div>

<div class=card>
<h2>Full results</h2>
<p class=note>Click a header to sort. Task columns shaded by score (darker = higher). <b>sens</b> = prompt sensitivity (T2 − T1): high positive = needs the engineered prompt; negative = the terse prompt worked better. <b>−n</b> = cells dropped (empty completion; see notes).</p>
<div class=tablewrap>
<table id=t>
<thead><tr>
<th data-c=0 data-t=s>model</th><th data-c=1 data-t=s>runs on</th>
<th data-c=2>acc</th><th data-c=3>nostr</th><th data-c=4>sec</th>
<th data-c=5>N1 impl</th><th data-c=6>N2 debug</th><th data-c=7>S1 audit</th><th data-c=8>S2 nostr-sec</th>
<th data-c=9>T1</th><th data-c=10>T2</th><th data-c=11>sens</th><th data-c=12>cost</th><th data-c=13>pts/$</th><th data-c=14>drop</th>
</tr></thead>
<tbody>{"".join(trows)}</tbody>
</table>
</div>
</div>

<p class=foot>Method: each cell is one completion, temperature 0.2, graded by a hidden vitest suite (N1/N2) or a recall×precision findings scorer (S1/S2). Median of 3 reps; whiskers on the bar chart show the min–max spread across reps. Treat gaps ≤5 pts as ties. Reasoning models were given a 30k-token budget with a 15k reasoning cap; kimi-k2.6 ignored the cap on the long N1-T2 prompt and is missing that one cell. Local flag = fits ≤24 GB VRAM per the run matrix. Costs are OpenRouter-reported per request.</p>
</div>
<script>
const tb=document.querySelector('#t tbody');
document.querySelectorAll('#t th').forEach(th=>th.onclick=()=>{{
 const c=+th.dataset.c,txt=th.dataset.t==='s';let d=th._d=!th._d;
 [...tb.rows].sort((a,b)=>{{let x=a.cells[c].innerText.replace(/[$,%+]/g,'')||'-9e9',y=b.cells[c].innerText.replace(/[$,%+]/g,'')||'-9e9';
   return txt?(d?x.localeCompare(y):y.localeCompare(x)):(d?(+x)-(+y):(+y)-(+x));}}).forEach(r=>tb.appendChild(r));
}});
</script>
</body></html>"""
open(os.path.join(HERE,"results.html"),"w").write(HTML)
print("wrote report/results.html", len(HTML), "bytes")
