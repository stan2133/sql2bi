#!/usr/bin/env python3.11
"""Generate static UI scaffold from dashboard spec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


INDEX_HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>SQL BI Scaffold</title>
  <link rel=\"stylesheet\" href=\"style.css\" />
</head>
<body>
  <header class=\"topbar\">
    <h1 id=\"dashboard-title\">SQL Generated Dashboard</h1>
  </header>
  <main class=\"layout\">
    <section id=\"grid\" class=\"grid\"></section>
    <aside class=\"filters\">
      <h2>Filters</h2>
      <ul id=\"filters-list\"></ul>
    </aside>
  </main>
  <script src=\"app.js\"></script>
</body>
</html>
"""

STYLE_CSS = """:root {
  --bg: #f5f7fb;
  --panel: #ffffff;
  --text: #1a1d21;
  --muted: #667085;
  --line: #e7ebf3;
  --accent: #2054d8;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--text);
  background: radial-gradient(1200px 500px at 10% -20%, #dae4ff 0%, transparent 55%), var(--bg);
}
.topbar {
  border-bottom: 1px solid var(--line);
  background: var(--panel);
  padding: 14px 20px;
}
.layout {
  display: grid;
  grid-template-columns: 1fr 260px;
  gap: 16px;
  padding: 16px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  grid-auto-rows: 70px;
  gap: 12px;
}
.widget {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--panel);
  padding: 12px;
  overflow: hidden;
}
.widget h3 {
  margin: 0 0 6px;
  font-size: 14px;
}
.widget p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.filters {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--panel);
  padding: 12px;
  height: fit-content;
}
@media (max-width: 960px) {
  .layout { grid-template-columns: 1fr; }
}
"""

APP_JS = """(async function () {
  const res = await fetch('dashboard.json');
  const spec = await res.json();

  const page = spec.pages[0];
  document.getElementById('dashboard-title').textContent = spec.name || page.title;

  const grid = document.getElementById('grid');
  const filterSet = new Set();

  page.widgets.forEach((w) => {
    const node = document.createElement('article');
    node.className = 'widget';
    node.style.gridColumn = `${w.position.x + 1} / span ${w.position.w}`;
    node.style.gridRow = `${w.position.y + 1} / span ${w.position.h}`;
    node.innerHTML = `
      <h3>${w.title}</h3>
      <p>chart: ${w.chart}</p>
      <p>metrics: ${(w.fields.metrics || []).join(', ') || '-'}</p>
      <p>dimensions: ${(w.fields.dimensions || []).join(', ') || '-'}</p>
    `;
    grid.appendChild(node);

    (w.filters || []).forEach((f) => filterSet.add(f));
  });

  const ul = document.getElementById('filters-list');
  if (filterSet.size === 0) {
    ul.innerHTML = '<li>No explicit filters</li>';
  } else {
    [...filterSet].forEach((f) => {
      const li = document.createElement('li');
      li.textContent = f;
      ul.appendChild(li);
    });
  }
})();
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate static UI scaffold")
    parser.add_argument("--dashboard", required=True, help="Path to dashboard.json")
    parser.add_argument("--out", required=True, help="Output directory for UI files")
    args = parser.parse_args()

    dashboard_path = Path(args.dashboard)
    out_dir = Path(args.out)

    spec = json.loads(dashboard_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (out_dir / "style.css").write_text(STYLE_CSS, encoding="utf-8")
    (out_dir / "app.js").write_text(APP_JS, encoding="utf-8")
    (out_dir / "dashboard.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Generated UI scaffold -> {out_dir}")


if __name__ == "__main__":
    main()
