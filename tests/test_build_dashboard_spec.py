import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / 'skills/sql-to-bi-builder/scripts/build_dashboard_spec.py'


def load_module():
  spec = importlib.util.spec_from_file_location('build_dashboard_spec', SCRIPT_PATH)
  if spec is None or spec.loader is None:
    raise RuntimeError(f'Failed to load module from {SCRIPT_PATH}')
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


class BuildDashboardSpecHelpersTest(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.mod = load_module()

  def test_unique_keep_order(self):
    result = self.mod.unique_keep_order(['region', 'dt', 'region', '', 'dt', 'channel'])
    self.assertEqual(result, ['region', 'dt', 'channel'])

  def test_next_position_wraps_when_exceeding_grid(self):
    x, y, next_x, next_y, row_h = self.mod.next_position(cursor_x=9, cursor_y=0, h_row_max=3, w=6, h=4)
    self.assertEqual((x, y), (0, 3))
    self.assertEqual((next_x, next_y, row_h), (6, 3, 4))


class BuildDashboardSpecCliTest(unittest.TestCase):
  def setUp(self):
    self.tmp = tempfile.TemporaryDirectory(prefix='sql2bi-test-')
    self.tmp_path = Path(self.tmp.name)

    self.queries = self.tmp_path / 'query_catalog.json'
    self.semantics = self.tmp_path / 'semantic_catalog.json'
    self.charts = self.tmp_path / 'chart_plan.json'

    self.queries.write_text(
      json.dumps(
        {
          'queries': [
            {
              'id': 'q_sales',
              'title': 'Sales',
              'filters': ['region'],
              'datasource': 'duckdb_demo',
              'refresh': '5m',
            },
            {
              'id': 'q_users',
              'title': 'Users',
              'filters': [],
            },
          ]
        },
        ensure_ascii=False,
      ),
      encoding='utf-8',
    )

    self.semantics.write_text(
      json.dumps(
        {
          'queries': [
            {
              'id': 'q_sales',
              'metrics': ['gmv'],
              'dimensions': ['dt'],
              'time_fields': ['dt'],
              'dsl_filter_fields': ['dt'],
              'dsl_filters': [
                {
                  'field': 'dt',
                  'operator': 'between',
                  'suggested_widget': 'date_range',
                  'is_time': True,
                }
              ],
            },
            {
              'id': 'q_users',
              'metrics': ['uv'],
              'dimensions': ['dt'],
              'time_fields': ['dt'],
              'dsl_filter_fields': [],
              'dsl_filters': [],
            },
          ]
        },
        ensure_ascii=False,
      ),
      encoding='utf-8',
    )

    self.charts.write_text(
      json.dumps({'charts': [{'id': 'q_sales', 'chart': 'line'}, {'id': 'q_users', 'chart': 'kpi'}]}, ensure_ascii=False),
      encoding='utf-8',
    )

  def tearDown(self):
    self.tmp.cleanup()

  def run_builder(self, output: Path, extra_args=None):
    cmd = [
      sys.executable,
      str(SCRIPT_PATH),
      '--queries',
      str(self.queries),
      '--semantics',
      str(self.semantics),
      '--charts',
      str(self.charts),
      '--output',
      str(output),
    ]
    if extra_args:
      cmd.extend(extra_args)

    completed = subprocess.run(cmd, cwd=REPO_ROOT, check=True, capture_output=True, text=True)
    return completed

  def test_default_includes_ui_theme(self):
    output = self.tmp_path / 'dashboard.with-ui.json'
    completed = self.run_builder(output)
    self.assertIn('with_ui_theme=True', completed.stdout)

    data = json.loads(output.read_text(encoding='utf-8'))
    self.assertIn('ui', data)
    self.assertIn('theme', data['ui'])
    self.assertIn('chart_palette', data['ui'])
    self.assertEqual(len(data['pages'][0]['widgets']), 2)

  def test_without_ui_theme_omits_ui(self):
    output = self.tmp_path / 'dashboard.no-ui.json'
    completed = self.run_builder(output, ['--without-ui-theme'])
    self.assertIn('with_ui_theme=False', completed.stdout)

    data = json.loads(output.read_text(encoding='utf-8'))
    self.assertNotIn('ui', data)
    self.assertIn('grid', data)
    self.assertEqual(data['pages'][0]['title'], 'Overview')


if __name__ == '__main__':
  unittest.main()
