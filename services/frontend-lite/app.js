(function () {
  const DEFAULT_BACKEND = localStorage.getItem('sql2bi_backend') || 'http://127.0.0.1:18000';
  const DEFAULT_SQLMD = '/Users/lyg/software/sql2bi/testdata/sql/demo.sql.md';

  const state = {
    backend: DEFAULT_BACKEND,
    sqlmd: DEFAULT_SQLMD,
    dashboard: null,
    filters: {},
    charts: {}
  };

  const $ = (id) => document.getElementById(id);

  function unique(arr) { return [...new Set((arr || []).filter(Boolean))]; }

  function toQuery(filters) {
    const p = new URLSearchParams();
    p.set('include_filters', 'true');
    Object.entries(filters || {}).forEach(([k, v]) => {
      const t = String(v || '').trim();
      if (t) p.set(k, t);
    });
    return p.toString();
  }

  async function req(path, init) {
    const res = await fetch(`${state.backend}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(init && init.headers ? init.headers : {}) },
      ...init
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    }
    return res.json();
  }

  async function importSql() {
    await req('/api/v1/import/sql-md', {
      method: 'POST',
      body: JSON.stringify({ sql_md_path: state.sqlmd })
    });
  }

  function renderGlobalFilters(page) {
    const root = $('globalFilters');
    root.innerHTML = '';

    const defs = (page.global_filters && page.global_filters.length)
      ? page.global_filters
      : unique((page.widgets || []).flatMap((w) => w.filters || [])).map((f) => ({ field: f, suggested_widget: 'select' }));

    defs.forEach((f) => {
      const wrap = document.createElement('div');
      wrap.className = 'filter-item';
      const label = document.createElement('label');
      label.textContent = f.field;
      const input = document.createElement('input');
      input.placeholder = f.suggested_widget || 'value';
      input.value = state.filters[f.field] || '';
      input.addEventListener('change', () => {
        state.filters[f.field] = input.value;
        renderWidgets(page).catch((e) => alert(e.message));
      });
      wrap.appendChild(label);
      wrap.appendChild(input);
      root.appendChild(wrap);
    });
  }

  function chartOption(payload) {
    const t = (payload.chart || 'table').toLowerCase();
    const x = payload.rows.map((r) => r[payload.dimension]);
    const m1 = payload.metrics[0];
    const m2 = payload.metrics[1];
    const y1 = payload.rows.map((r) => Number(r[m1] || 0));
    const y2 = payload.rows.map((r) => Number(r[m2] || 0));

    if (t === 'line') return {
      tooltip: { trigger: 'axis' },
      grid: { left: 36, right: 12, top: 20, bottom: 24 },
      xAxis: { type: 'category', data: x },
      yAxis: { type: 'value' },
      series: [{ type: 'line', smooth: true, data: y1 }]
    };

    if (t === 'bar') return {
      tooltip: { trigger: 'axis' },
      grid: { left: 36, right: 12, top: 20, bottom: 24 },
      xAxis: { type: 'category', data: x, axisLabel: { rotate: 25 } },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: y1 }]
    };

    if (t === 'grouped_bar') return {
      tooltip: { trigger: 'axis' },
      legend: { top: 0 },
      grid: { left: 36, right: 12, top: 24, bottom: 24 },
      xAxis: { type: 'category', data: x, axisLabel: { rotate: 20 } },
      yAxis: { type: 'value' },
      series: [
        { name: m1, type: 'bar', data: y1 },
        { name: m2, type: 'bar', data: y2 }
      ]
    };

    if (t === 'kpi') {
      const total = y1.reduce((a, b) => a + b, 0);
      return {
        xAxis: { show: false, type: 'value' },
        yAxis: { show: false, type: 'value' },
        series: [{ type: 'bar', data: [total], barWidth: 80, itemStyle: { color: '#2f6fed' } }],
        graphic: [{ type: 'text', left: 'center', top: '45%', style: { text: String(total), font: '700 24px monospace', fill: '#101828' } }]
      };
    }

    return null;
  }

  function tableHtml(rows) {
    const cols = Object.keys(rows[0] || {});
    let html = '<div class="table-wrap"><table><thead><tr>';
    cols.forEach((c) => { html += `<th>${c}</th>`; });
    html += '</tr></thead><tbody>';
    rows.slice(0, 8).forEach((r) => {
      html += '<tr>';
      cols.forEach((c) => { html += `<td>${r[c]}</td>`; });
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    return html;
  }

  async function renderWidgets(page) {
    const grid = $('grid');
    grid.innerHTML = '';

    for (const w of page.widgets || []) {
      const node = document.createElement('article');
      node.className = 'widget';
      node.style.gridColumn = `${(w.position?.x || 0) + 1} / span ${w.position?.w || 6}`;
      node.style.gridRow = `${(w.position?.y || 0) + 1} / span ${w.position?.h || 4}`;
      node.innerHTML = `
        <div class="widget-head">
          <div class="widget-title">${w.title || w.query_id}</div>
          <div class="widget-type">${w.chart || 'table'}</div>
        </div>
        <div class="widget-body"></div>
      `;
      grid.appendChild(node);

      const payload = await req(`/api/v1/queries/${encodeURIComponent(w.query_id)}/data?${toQuery(state.filters)}`);
      const body = node.querySelector('.widget-body');
      const chartType = (w.chart || 'table').toLowerCase();

      if (chartType === 'table') {
        body.innerHTML = tableHtml(payload.rows || []);
      } else if (window.echarts) {
        body.innerHTML = '<div class="chart"></div>';
        const chartNode = body.querySelector('.chart');
        if (!state.charts[w.query_id]) {
          state.charts[w.query_id] = window.echarts.init(chartNode);
          state.charts[w.query_id].on('click', (params) => {
            const defs = page.global_filters || [];
            if (!defs.length || !params || params.name == null) return;
            state.filters[defs[0].field] = String(params.name);
            renderGlobalFilters(page);
            renderWidgets(page).catch((e) => alert(e.message));
          });
        }
        const option = chartOption(payload);
        if (option) state.charts[w.query_id].setOption(option, true);
      }
    }
  }

  async function reload() {
    const dashboard = await req('/api/v1/dashboard/current');
    state.dashboard = dashboard;
    const page = (dashboard.pages || [])[0] || { widgets: [] };
    $('title').textContent = dashboard.name || page.title || 'SQL2BI Dashboard';
    renderGlobalFilters(page);
    await renderWidgets(page);
  }

  $('backend').value = state.backend;
  $('sqlmd').value = state.sqlmd;

  $('backend').addEventListener('change', (e) => {
    state.backend = e.target.value.trim() || DEFAULT_BACKEND;
    localStorage.setItem('sql2bi_backend', state.backend);
  });

  $('sqlmd').addEventListener('change', (e) => {
    state.sqlmd = e.target.value.trim() || DEFAULT_SQLMD;
  });

  $('importBtn').addEventListener('click', async () => {
    try {
      await importSql();
      await reload();
    } catch (e) {
      alert(e.message || String(e));
    }
  });

  $('reloadBtn').addEventListener('click', async () => {
    try {
      await reload();
    } catch (e) {
      alert(e.message || String(e));
    }
  });

  req('/api/health')
    .then(() => reload())
    .catch(() => {
      $('title').textContent = 'Backend unavailable: click Import after backend starts';
    });
})();
