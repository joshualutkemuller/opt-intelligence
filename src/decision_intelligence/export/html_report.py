# ruff: noqa: E501
"""
Self-contained HTML report generator for OptimizationResult.

The output is a single .html file:
  - No external dependencies (all CSS/JS inlined)
  - SVG charts rendered client-side from embedded JSON data
  - Dark/light theme respecting system preference + toggle
  - Charts: allocation bars, asset-class donut, sensitivity bars, scenario comparison
"""

import json
from pathlib import Path

from decision_intelligence.contracts import OptimizationRequest, OptimizationResult


def generate_report(
    result: OptimizationResult,
    request: OptimizationRequest | None = None,
    path: str | Path | None = None,
) -> str:
    """
    Build a self-contained HTML report.

    Args:
        result:  The optimization result to report.
        request: Optional originating request (adds context to the header).
        path:    If given, write the HTML to this file and return the path string.

    Returns:
        The HTML string (always), and writes to path if provided.
    """
    payload = _build_payload(result, request)
    html = _TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, default=str))

    if path is not None:
        p = Path(path)
        p.write_text(html, encoding="utf-8")

    return html


# ── Payload builder ────────────────────────────────────────────────────────

def _build_payload(result: OptimizationResult, request: OptimizationRequest | None) -> dict:
    allocs = [
        {
            "label":     a.label,
            "value":     round(a.allocated_value, 2),
            "fraction":  round(a.allocated_fraction, 4),
            "metadata":  a.metadata,
        }
        for a in sorted(result.allocations, key=lambda x: -x.allocated_value)
    ]

    # Asset class breakdown for donut
    class_totals: dict[str, float] = {}
    for a in result.allocations:
        ac = a.metadata.get("asset_class") or a.metadata.get("instrument") or a.metadata.get("credit_quality") or "other"
        class_totals[ac] = class_totals.get(ac, 0.0) + a.allocated_value

    sens = [
        {
            "parameter":     s.parameter,
            "shadow_price":  round(s.shadow_price, 4),
            "interpretation": s.interpretation,
        }
        for s in result.sensitivities
    ]

    scenarios = [
        {
            "name":        name,
            "status":      sr.status.value,
            "objective":   round(sr.objective_value, 4),
            "improvement": round(sr.improvement_pct, 2),
            "delta":       round(sr.objective_value - result.objective_value, 2),
        }
        for name, sr in result.scenario_results.items()
    ]

    return {
        "domain":          result.domain,
        "portfolio_id":    request.portfolio_id if request else "—",
        "requestor":       request.requestor if request else "—",
        "objective_label": request.objective.metric if request else result.domain,
        "direction":       request.objective.direction.value if request else "minimize",
        "status":          result.status.value,
        "objective":       round(result.objective_value, 4),
        "baseline":        round(result.baseline_value, 4),
        "improvement":     round(result.improvement, 4),
        "improvement_pct": round(result.improvement_pct, 2),
        "binding":         result.binding_constraints,
        "explanation":     result.explanation,
        "validation_ok":   result.validation.passed,
        "violations":      result.validation.violations,
        "timestamp":       str(result.timestamp),
        "request_id":      result.request_id,
        "allocations":     allocs,
        "class_totals":    [{"label": k, "value": round(v, 2)} for k, v in sorted(class_totals.items(), key=lambda x: -x[1])],
        "sensitivities":   sens,
        "scenarios":       scenarios,
    }


# ── HTML template ──────────────────────────────────────────────────────────

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DI Report</title>
<style>
:root {
  --bg:       #080f1e;
  --surface:  #0d1629;
  --surface2: #111e35;
  --border:   #1a2d4a;
  --border2:  #2a4470;
  --text:     #c8d3e8;
  --muted:    #4a5f7a;
  --dim:      #2a3a52;
  --amber:    #e8a030;
  --amber2:   #f5b84a;
  --teal:     #00c897;
  --blue:     #5b8fcc;
  --blue2:    #7aaee8;
  --violet:   #9b7fe8;
  --red:      #e85555;
  --white:    #eef2f8;
  --ok:       #00c897;
  --err:      #e85555;
}

@media (prefers-color-scheme: light) {
  :root {
    --bg:       #f0f4f8;
    --surface:  #ffffff;
    --surface2: #f8fafc;
    --border:   #d0daea;
    --border2:  #b0c0d8;
    --text:     #1a2540;
    --muted:    #7a90b0;
    --dim:      #c0ccdc;
    --amber:    #c07820;
    --amber2:   #e09030;
    --teal:     #008060;
    --blue:     #2a5fa0;
    --blue2:    #3a70b8;
    --violet:   #6040b8;
    --red:      #c03030;
    --white:    #0a1428;
    --ok:       #008060;
    --err:      #c03030;
  }
}

:root[data-theme="dark"]  { --bg: #080f1e; --surface: #0d1629; --surface2: #111e35; --border: #1a2d4a; --border2: #2a4470; --text: #c8d3e8; --muted: #4a5f7a; --dim: #2a3a52; --amber: #e8a030; --amber2: #f5b84a; --teal: #00c897; --blue: #5b8fcc; --blue2: #7aaee8; --violet: #9b7fe8; --red: #e85555; --white: #eef2f8; --ok: #00c897; --err: #e85555; }
:root[data-theme="light"] { --bg: #f0f4f8; --surface: #ffffff; --surface2: #f8fafc; --border: #d0daea; --border2: #b0c0d8; --text: #1a2540; --muted: #7a90b0; --dim: #c0ccdc; --amber: #c07820; --amber2: #e09030; --teal: #008060; --blue: #2a5fa0; --blue2: #3a70b8; --violet: #6040b8; --red: #c03030; --white: #0a1428; --ok: #008060; --err: #c03030; }

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: ui-monospace, 'Cascadia Code', 'JetBrains Mono', 'Fira Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: 0 0 60px;
  font-variant-numeric: tabular-nums;
}

/* ── Header ── */
.header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 28px 40px 24px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.header-left h1 {
  font-size: 20px;
  font-weight: 600;
  color: var(--white);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.header-left h1 span { color: var(--blue2); }

.header-meta {
  display: flex;
  gap: 20px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.meta-item { color: var(--muted); font-size: 11.5px; }
.meta-item span { color: var(--text); }

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 4px 12px;
  border-radius: 2px;
  border: 1px solid;
}

.status-badge.optimal { color: var(--ok); border-color: var(--ok); background: color-mix(in srgb, var(--ok) 10%, transparent); }
.status-badge.error   { color: var(--err); border-color: var(--err); background: color-mix(in srgb, var(--err) 10%, transparent); }

.header-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.theme-btn {
  background: var(--surface2);
  border: 1px solid var(--border);
  color: var(--muted);
  cursor: pointer;
  font: inherit;
  font-size: 11px;
  letter-spacing: 0.06em;
  padding: 4px 10px;
  border-radius: 2px;
}

.theme-btn:hover { color: var(--text); border-color: var(--border2); }

/* ── Stat tiles ── */
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1px;
  background: var(--border);
  border-bottom: 1px solid var(--border);
}

.stat {
  background: var(--surface);
  padding: 20px 24px;
}

.stat-label {
  font-size: 10.5px;
  letter-spacing: 0.1em;
  color: var(--muted);
  text-transform: uppercase;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 22px;
  font-weight: 600;
  color: var(--amber);
  line-height: 1.1;
}

.stat-value.positive { color: var(--teal); }
.stat-value.negative { color: var(--red); }
.stat-value.neutral  { color: var(--blue2); }

.stat-sub {
  font-size: 11px;
  color: var(--muted);
  margin-top: 4px;
}

/* ── Improvement bar ── */
.impr-bar-section {
  background: var(--surface);
  padding: 16px 40px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 16px;
}

.impr-bar-wrap {
  flex: 1;
  height: 6px;
  background: var(--dim);
  border-radius: 1px;
  overflow: hidden;
}

.impr-bar-fill {
  height: 100%;
  background: var(--teal);
  border-radius: 1px;
  transition: width 1s cubic-bezier(0.4,0,0.2,1);
}

.impr-pct { color: var(--teal); font-weight: 600; font-size: 13px; white-space: nowrap; }
.impr-label { color: var(--muted); font-size: 11px; white-space: nowrap; }

/* ── Main layout ── */
.main {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 1px;
  background: var(--border);
  margin-top: 1px;
}

@media (max-width: 900px) {
  .main { grid-template-columns: 1fr; }
}

.main-left, .main-right { background: var(--surface); }

/* ── Section heading ── */
.section { padding: 24px 28px; border-bottom: 1px solid var(--border); }
.section:last-child { border-bottom: none; }

.section-title {
  font-size: 10.5px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--blue);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}

/* ── SVG chart container ── */
.chart-wrap { overflow-x: auto; }
.chart-wrap svg { display: block; width: 100%; min-width: 300px; }

/* ── Table ── */
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th {
  color: var(--muted);
  font-weight: 400;
  letter-spacing: 0.06em;
  text-align: left;
  padding: 6px 10px 6px 0;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.data-table th.r, .data-table td.r { text-align: right; }
.data-table td {
  padding: 7px 10px 7px 0;
  border-bottom: 1px solid var(--dim);
  vertical-align: middle;
  color: var(--text);
}
.data-table tr:last-child td { border-bottom: none; }
.data-table td.label-cell { color: var(--white); max-width: 240px; }
.data-table td.value-cell { color: var(--amber); }
.data-table td.frac-cell  { color: var(--muted); }

.inline-bar {
  display: inline-block;
  height: 4px;
  background: var(--amber);
  border-radius: 1px;
  opacity: 0.7;
  vertical-align: middle;
  margin-right: 6px;
}

/* ── Chips ── */
.chip-list { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  background: var(--surface2);
  border: 1px solid var(--border);
  color: var(--muted);
  font-size: 11px;
  padding: 3px 9px;
  border-radius: 2px;
}
.chip.binding { color: var(--violet); border-color: color-mix(in srgb, var(--violet) 40%, transparent); }

/* ── Explanation ── */
.explanation {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

/* ── Scenario table ── */
.delta-pos { color: var(--amber); }
.delta-neg { color: var(--teal); }

/* ── Validation ── */
.validation-ok  { color: var(--ok);  font-size: 12px; }
.validation-err { color: var(--err); font-size: 12px; }

/* ── Footer ── */
.footer {
  padding: 20px 40px;
  color: var(--muted);
  font-size: 11px;
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  border-top: 1px solid var(--border);
  margin-top: 1px;
  background: var(--surface);
}
</style>
</head>
<body>
<script>
const D = __PAYLOAD__;
</script>

<div class="header">
  <div class="header-left">
    <h1 id="h-title">—</h1>
    <div class="header-meta">
      <div class="meta-item">portfolio <span id="h-portfolio">—</span></div>
      <div class="meta-item">requestor <span id="h-requestor">—</span></div>
      <div class="meta-item">objective <span id="h-objective">—</span></div>
      <div class="meta-item">generated <span id="h-ts">—</span></div>
    </div>
  </div>
  <div class="header-right">
    <button class="theme-btn" id="theme-btn">LIGHT / DARK</button>
    <div class="status-badge" id="h-status">—</div>
  </div>
</div>

<div class="stats">
  <div class="stat">
    <div class="stat-label">Objective</div>
    <div class="stat-value" id="st-obj">—</div>
    <div class="stat-sub" id="st-obj-label">—</div>
  </div>
  <div class="stat">
    <div class="stat-label">Baseline</div>
    <div class="stat-value neutral" id="st-base">—</div>
    <div class="stat-sub">before optimization</div>
  </div>
  <div class="stat">
    <div class="stat-label">Improvement</div>
    <div class="stat-value positive" id="st-impr">—</div>
    <div class="stat-sub" id="st-impr-sub">—</div>
  </div>
  <div class="stat">
    <div class="stat-label">Allocations</div>
    <div class="stat-value neutral" id="st-allocs">—</div>
    <div class="stat-sub" id="st-binding">— binding</div>
  </div>
</div>

<div class="impr-bar-section">
  <div class="impr-label" id="impr-direction">improvement vs baseline</div>
  <div class="impr-bar-wrap"><div class="impr-bar-fill" id="impr-fill" style="width:0%"></div></div>
  <div class="impr-pct" id="impr-pct">0%</div>
</div>

<div class="main">
  <!-- Left column -->
  <div class="main-left">

    <div class="section">
      <div class="section-title">Allocations</div>
      <div class="chart-wrap"><svg id="chart-alloc" height="0"></svg></div>
    </div>

    <div class="section">
      <div class="section-title">Allocation Detail</div>
      <div style="overflow-x:auto">
        <table class="data-table" id="alloc-table">
          <thead>
            <tr>
              <th>Asset / Source</th>
              <th class="r">Value</th>
              <th>Distribution</th>
              <th class="r">Fraction</th>
            </tr>
          </thead>
          <tbody id="alloc-tbody"></tbody>
        </table>
      </div>
    </div>

    <div class="section" id="explanation-section" style="display:none">
      <div class="section-title">Explanation</div>
      <div class="explanation" id="explanation-text"></div>
    </div>

    <div class="section">
      <div class="section-title">Validation</div>
      <div id="validation-out"></div>
    </div>

  </div>

  <!-- Right column -->
  <div class="main-right">

    <div class="section" id="class-section" style="display:none">
      <div class="section-title">Asset Class Mix</div>
      <div class="chart-wrap"><svg id="chart-donut" height="200"></svg></div>
    </div>

    <div class="section" id="sens-section" style="display:none">
      <div class="section-title">Sensitivity Analysis</div>
      <div class="chart-wrap"><svg id="chart-sens" height="0"></svg></div>
    </div>

    <div class="section" id="scenario-section" style="display:none">
      <div class="section-title">Scenarios</div>
      <div class="chart-wrap"><svg id="chart-scenario" height="0"></svg></div>
      <table class="data-table" id="scenario-table" style="margin-top:14px">
        <thead><tr>
          <th>Scenario</th>
          <th class="r">Objective</th>
          <th class="r">Δ vs Base</th>
          <th class="r">Impr%</th>
        </tr></thead>
        <tbody id="scenario-tbody"></tbody>
      </table>
    </div>

    <div class="section">
      <div class="section-title">Binding Constraints</div>
      <div class="chip-list" id="binding-chips"></div>
    </div>

    <div class="section">
      <div class="section-title">Request Metadata</div>
      <table class="data-table" id="meta-table">
        <tbody>
          <tr><td class="muted">request id</td><td id="m-reqid" style="color:var(--muted);font-size:11px;word-break:break-all"></td></tr>
          <tr><td class="muted">domain</td><td id="m-domain"></td></tr>
          <tr><td class="muted">direction</td><td id="m-direction"></td></tr>
          <tr><td class="muted">timestamp</td><td id="m-ts" style="font-size:11px"></td></tr>
        </tbody>
      </table>
    </div>

  </div>
</div>

<div class="footer">
  <span>Decision Intelligence Platform — v0.1.0</span>
  <span>Solver: HiGHS LP (scipy)</span>
  <span>Simulated data — swap data.py for production adapters</span>
</div>

<script>
// ── Theme toggle ──────────────────────────────────────────────────────────
(function() {
  const btn = document.getElementById('theme-btn');
  const root = document.documentElement;
  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  let current = mq.matches ? 'dark' : 'light';
  root.dataset.theme = current;
  btn.addEventListener('click', () => {
    current = current === 'dark' ? 'light' : 'dark';
    root.dataset.theme = current;
  });
})();

// ── Helpers ───────────────────────────────────────────────────────────────
function fmtNum(v) {
  if (v === undefined || v === null) return '—';
  const abs = Math.abs(v);
  if (abs >= 1e6) return '$' + (v/1e6).toFixed(1) + 'M';
  if (abs >= 1e3) return '$' + v.toLocaleString('en-US', {maximumFractionDigits:0});
  if (abs < 10)   return v.toFixed(4);
  return v.toLocaleString('en-US', {maximumFractionDigits:2});
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function svgEl(tag, attrs) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  return el;
}

// ── Populate header / stats ───────────────────────────────────────────────
(function populate() {
  document.title = 'DI Report — ' + D.domain;
  document.getElementById('h-title').innerHTML =
    '<span>' + D.domain.replace(/_/g,' ').toUpperCase() + '</span> OPTIMIZER';
  document.getElementById('h-portfolio').textContent  = D.portfolio_id;
  document.getElementById('h-requestor').textContent  = D.requestor;
  document.getElementById('h-objective').textContent  = D.objective_label + ' (' + D.direction + ')';
  document.getElementById('h-ts').textContent         = D.timestamp.slice(0,19).replace('T','  ');

  const sb = document.getElementById('h-status');
  sb.textContent = D.status.toUpperCase();
  sb.className = 'status-badge ' + (D.status === 'optimal' ? 'optimal' : 'error');

  document.getElementById('st-obj').textContent   = fmtNum(D.objective);
  document.getElementById('st-obj-label').textContent = D.objective_label;
  document.getElementById('st-base').textContent  = fmtNum(D.baseline);
  document.getElementById('st-impr').textContent  = D.improvement_pct.toFixed(2) + '%';
  document.getElementById('st-impr-sub').textContent = fmtNum(D.improvement) + ' saved';
  document.getElementById('st-allocs').textContent = D.allocations.length;
  document.getElementById('st-binding').textContent = D.binding.length + ' binding constraints';

  document.getElementById('impr-pct').textContent = D.improvement_pct.toFixed(1) + '%';
  setTimeout(() => {
    document.getElementById('impr-fill').style.width = Math.min(100, D.improvement_pct) + '%';
  }, 100);

  // Meta
  document.getElementById('m-reqid').textContent     = D.request_id;
  document.getElementById('m-domain').textContent    = D.domain;
  document.getElementById('m-direction').textContent = D.direction;
  document.getElementById('m-ts').textContent        = D.timestamp;

  // Validation
  const vOut = document.getElementById('validation-out');
  if (D.validation_ok) {
    vOut.innerHTML = '<div class="validation-ok">✓ all constraints satisfied</div>';
  } else {
    vOut.innerHTML = D.violations.map(v =>
      '<div class="validation-err">✗ ' + v + '</div>'
    ).join('');
  }

  // Explanation
  if (D.explanation) {
    document.getElementById('explanation-section').style.display = '';
    document.getElementById('explanation-text').textContent = D.explanation;
  }

  // Binding chips
  const chips = document.getElementById('binding-chips');
  if (D.binding.length) {
    chips.innerHTML = D.binding.map(b =>
      '<span class="chip binding">' + b + '</span>'
    ).join('');
  } else {
    chips.innerHTML = '<span class="chip">none</span>';
  }
})();

// ── Allocation table ──────────────────────────────────────────────────────
(function buildAllocTable() {
  const tbody = document.getElementById('alloc-tbody');
  D.allocations.forEach(a => {
    const tr = document.createElement('tr');
    const barW = Math.round(a.fraction * 80);
    tr.innerHTML = `
      <td class="label-cell">${a.label}</td>
      <td class="r value-cell">${fmtNum(a.value)}</td>
      <td><span class="inline-bar" style="width:${barW}px"></span></td>
      <td class="r frac-cell">${(a.fraction*100).toFixed(1)}%</td>`;
    tbody.appendChild(tr);
  });
})();

// ── SVG bar chart — allocations ───────────────────────────────────────────
(function buildAllocChart() {
  if (!D.allocations.length) return;
  const svg = document.getElementById('chart-alloc');
  const W = svg.parentElement.clientWidth || 560;
  const ROW = 32, PAD_L = 200, PAD_R = 80, PAD_T = 10, PAD_B = 10;
  const H = D.allocations.length * ROW + PAD_T + PAD_B;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('height', H);

  const maxVal = D.allocations[0].value;
  const barW = W - PAD_L - PAD_R;

  D.allocations.forEach((a, i) => {
    const y = PAD_T + i * ROW;
    const bw = Math.max(2, (a.value / maxVal) * barW);
    const cy = y + ROW * 0.5;

    // label
    const lbl = svgEl('text', {
      x: PAD_L - 10, y: cy + 4,
      'text-anchor': 'end',
      fill: 'var(--text)',
      'font-family': 'ui-monospace,monospace',
      'font-size': '11',
    });
    lbl.textContent = a.label.length > 26 ? a.label.slice(0,25)+'…' : a.label;
    svg.appendChild(lbl);

    // bar bg
    svg.appendChild(svgEl('rect', {
      x: PAD_L, y: cy - 7, width: barW, height: 14,
      fill: 'var(--dim)', rx: 1,
    }));

    // bar fill
    svg.appendChild(svgEl('rect', {
      x: PAD_L, y: cy - 7, width: bw, height: 14,
      fill: 'var(--amber)', rx: 1, opacity: '0.85',
    }));

    // value label
    const val = svgEl('text', {
      x: PAD_L + bw + 8, y: cy + 4,
      fill: 'var(--amber)',
      'font-family': 'ui-monospace,monospace',
      'font-size': '11',
    });
    val.textContent = fmtNum(a.value) + '  ' + (a.fraction*100).toFixed(1)+'%';
    svg.appendChild(val);
  });
})();

// ── SVG donut — asset class ───────────────────────────────────────────────
(function buildDonut() {
  if (!D.class_totals || D.class_totals.length < 2) return;
  document.getElementById('class-section').style.display = '';
  const svg = document.getElementById('chart-donut');
  const W = svg.parentElement.clientWidth || 300;
  const CX = W * 0.38, CY = 100, R = 72, r = 42;
  svg.setAttribute('viewBox', `0 0 ${W} 200`);

  const colors = ['var(--amber)', 'var(--blue)', 'var(--teal)', 'var(--violet)', 'var(--blue2)', 'var(--amber2)'];
  const total = D.class_totals.reduce((s, c) => s + c.value, 0);

  let angle = -Math.PI / 2;
  D.class_totals.forEach((c, i) => {
    const frac = c.value / total;
    const sweep = frac * 2 * Math.PI;
    const x1 = CX + R * Math.cos(angle);
    const y1 = CY + R * Math.sin(angle);
    const x2 = CX + R * Math.cos(angle + sweep);
    const y2 = CY + R * Math.sin(angle + sweep);
    const xi1 = CX + r * Math.cos(angle);
    const yi1 = CY + r * Math.sin(angle);
    const xi2 = CX + r * Math.cos(angle + sweep);
    const yi2 = CY + r * Math.sin(angle + sweep);
    const large = sweep > Math.PI ? 1 : 0;

    const path = svgEl('path', {
      d: `M ${x1} ${y1} A ${R} ${R} 0 ${large} 1 ${x2} ${y2} L ${xi2} ${yi2} A ${r} ${r} 0 ${large} 0 ${xi1} ${yi1} Z`,
      fill: colors[i % colors.length],
      opacity: '0.88',
      stroke: 'var(--surface)',
      'stroke-width': '1.5',
    });
    svg.appendChild(path);
    angle += sweep;
  });

  // Legend
  const LX = CX + R + 24, LEG_H = 18;
  D.class_totals.forEach((c, i) => {
    const ly = 30 + i * LEG_H;
    svg.appendChild(svgEl('rect', { x: LX, y: ly, width: 10, height: 10, fill: colors[i % colors.length], rx: 1 }));
    const lbl = svgEl('text', {
      x: LX + 16, y: ly + 9,
      fill: 'var(--text)',
      'font-family': 'ui-monospace,monospace',
      'font-size': '11',
    });
    lbl.textContent = c.label + '  ' + (c.value/total*100).toFixed(0)+'%';
    svg.appendChild(lbl);
  });
})();

// ── SVG bar chart — sensitivity ───────────────────────────────────────────
(function buildSensChart() {
  if (!D.sensitivities.length) return;
  document.getElementById('sens-section').style.display = '';
  const svg = document.getElementById('chart-sens');
  const W = svg.parentElement.clientWidth || 320;
  const ROW = 36, PAD_L = 160, PAD_R = 60, PAD_T = 8, PAD_B = 8;
  const H = D.sensitivities.length * ROW + PAD_T + PAD_B;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('height', H);

  const prices = D.sensitivities.map(s => Math.abs(s.shadow_price));
  const maxP = Math.max(...prices, 1);
  const barW = W - PAD_L - PAD_R;

  D.sensitivities.forEach((s, i) => {
    const y = PAD_T + i * ROW;
    const cy = y + ROW * 0.5;
    const bw = Math.max(2, (Math.abs(s.shadow_price) / maxP) * barW);

    const lbl = svgEl('text', {
      x: PAD_L - 8, y: cy + 4,
      'text-anchor': 'end',
      fill: 'var(--muted)',
      'font-family': 'ui-monospace,monospace',
      'font-size': '10.5',
    });
    const p = s.parameter.replace(/:/g, ' · ');
    lbl.textContent = p.length > 18 ? p.slice(0,17)+'…' : p;
    svg.appendChild(lbl);

    svg.appendChild(svgEl('rect', { x: PAD_L, y: cy-6, width: barW, height: 12, fill: 'var(--dim)', rx: 1 }));
    svg.appendChild(svgEl('rect', { x: PAD_L, y: cy-6, width: bw,  height: 12, fill: 'var(--violet)', rx: 1, opacity: '0.85' }));

    const val = svgEl('text', {
      x: PAD_L + bw + 6, y: cy + 4,
      fill: 'var(--violet)',
      'font-family': 'ui-monospace,monospace',
      'font-size': '10.5',
    });
    val.textContent = s.shadow_price.toFixed(2);
    svg.appendChild(val);
  });
})();

// ── Scenario table + SVG bar chart ───────────────────────────────────────
(function buildScenarios() {
  if (!D.scenarios.length) return;
  document.getElementById('scenario-section').style.display = '';

  const tbody = document.getElementById('scenario-tbody');
  D.scenarios.forEach(s => {
    const isUp = s.delta > 0;
    const cls  = isUp ? 'delta-pos' : 'delta-neg';
    const sign = isUp ? '+' : '';
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${s.name}</td>
      <td class="r value-cell">${fmtNum(s.objective)}</td>
      <td class="r ${cls}">${sign}${fmtNum(s.delta)}</td>
      <td class="r ${cls}">${s.improvement.toFixed(1)}%</td>`;
    tbody.appendChild(tr);
  });

  // Bar chart comparing base vs scenario objectives
  const svg = document.getElementById('chart-scenario');
  const all = [{name: 'base', objective: D.objective}, ...D.scenarios];
  const W = svg.parentElement.clientWidth || 300;
  const ROW = 30, PAD_L = 100, PAD_R = 70, PAD_T = 6, PAD_B = 6;
  const H = all.length * ROW + PAD_T + PAD_B;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('height', H);

  const maxObj = Math.max(...all.map(s => s.objective));
  const barW = W - PAD_L - PAD_R;

  all.forEach((s, i) => {
    const y = PAD_T + i * ROW;
    const cy = y + ROW * 0.5;
    const bw = Math.max(2, (s.objective / maxObj) * barW);
    const color = i === 0 ? 'var(--teal)' : 'var(--amber)';

    const lbl = svgEl('text', { x: PAD_L-8, y: cy+4, 'text-anchor':'end', fill:'var(--muted)', 'font-family':'ui-monospace,monospace', 'font-size':'10.5' });
    lbl.textContent = s.name.length > 12 ? s.name.slice(0,11)+'…' : s.name;
    svg.appendChild(lbl);

    svg.appendChild(svgEl('rect', { x:PAD_L, y:cy-6, width:barW, height:12, fill:'var(--dim)', rx:1 }));
    svg.appendChild(svgEl('rect', { x:PAD_L, y:cy-6, width:bw,   height:12, fill:color, rx:1, opacity:'0.85' }));

    const val = svgEl('text', { x:PAD_L+bw+6, y:cy+4, fill:color, 'font-family':'ui-monospace,monospace', 'font-size':'10.5' });
    val.textContent = fmtNum(s.objective);
    svg.appendChild(val);
  });
})();
</script>
</body>
</html>
"""
