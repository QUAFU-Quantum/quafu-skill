# -*- coding: utf-8 -*-
"""不联网的检查：模板的理想结果、分析逻辑、网页模板、SKILL.md 格式。  python -m unittest discover tests"""
import json
import math
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, 'skills', 'quafu')
sys.path.insert(0, os.path.join(SKILL, 'scripts'))

import algorithms as A  # noqa: E402
import qf  # noqa: E402
import qfsim  # noqa: E402


def ideal(name, **p):
    return [qfsim.probabilities(q) for _, q in A.build(name, **p)[0]]


class Templates(unittest.TestCase):
    def test_answers(self):
        self.assertAlmostEqual(ideal('bell')[0]['00'], 0.5)
        self.assertEqual(set(ideal('ghz', n=4)[0]), {'0000', '1111'})
        self.assertAlmostEqual(ideal('deutsch-jozsa')[0]['111'], 1.0)
        self.assertAlmostEqual(ideal('deutsch-jozsa', oracle='constant')[0]['000'], 1.0)
        self.assertAlmostEqual(ideal('bernstein-vazirani', secret='0110')[0]['0110'], 1.0)
        self.assertAlmostEqual(ideal('grover', marked='01')[0]['01'], 1.0)
        self.assertAlmostEqual(ideal('grover', marked='110')[0]['110'], 0.9453125)
        self.assertAlmostEqual(ideal('teleport')[0]['1'], 0.25)

    def test_rotation_curve(self):
        for (lab, _), p in zip(A.build('rotation')[0], ideal('rotation')):
            self.assertAlmostEqual(p.get('1', 0.0), math.sin(lab['theta'] / 2) ** 2)

    def test_every_template_fits_platform_limits(self):
        for name, t in A.TEMPLATES.items():
            circuits, _ = A.build(name)
            self.assertEqual(len(circuits), t['circuits'], name)
            for _, q in circuits:
                nq = qfsim.parse(q)[0]
                self.assertLessEqual(nq, 16, name)        # 带噪模拟器上限

    def _record(self, name, sample=None):
        circuits, params = A.build(name)
        res = []
        for _, q in circuits:
            p = qfsim.probabilities(q)
            counts = {k: int(round(v * 8192)) for k, v in p.items() if round(v * 8192)}
            res.append({'status': 'Finished', 'counts': counts, 'shots_returned': sum(counts.values()),
                        'backend': 'sim'})
        return {'job_id': 'x', 'template': name, 'kind': A.TEMPLATES[name]['kind'], 'params': params,
                'target': 'sim', 'shots': 8192, 'labels': [l for l, _ in circuits],
                'circuits': [c for _, c in circuits], 'results': res}

    def test_analysis_on_ideal_data(self):
        out = qf.analyze_record(self._record('vqe-h2'))
        self.assertAlmostEqual(out['metrics']['fit']['min'], A.H2_EXACT_TOTAL, places=3)
        out = qf.analyze_record(self._record('qaoa-maxcut'))
        self.assertAlmostEqual(out['metrics']['best']['cut'], 3.0, places=2)
        out = qf.analyze_record(self._record('rotation'))
        self.assertAlmostEqual(out['metrics']['contrast'], 1.0, places=2)
        for name in ('bell', 'ghz', 'bernstein-vazirani', 'grover', 'deutsch-jozsa', 'teleport', 'qrng'):
            out = qf.analyze_record(self._record(name))
            self.assertGreater(out['metrics']['fidelity'], 0.999, name)


class Ledger(unittest.TestCase):
    def test_runs_listing_never_rewrites_records(self):
        import tempfile
        import contextlib
        import io
        d = tempfile.mkdtemp()
        rec = {'job_id': 'j1', 'template': 'bell', 'status': 'Finished', 'results': []}
        json.dump(rec, open(os.path.join(d, 'j1.json'), 'w'))
        json.dump({'job_id': 'j1', 'items': []}, open(os.path.join(d, 'j1.analysis.json'), 'w'))
        os.environ['QUAFU_RUNS_DIR'] = d
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                qf.main(['runs'])
        finally:
            del os.environ['QUAFU_RUNS_DIR']
        self.assertEqual(out.getvalue().count('j1'), 1)
        self.assertEqual(json.load(open(os.path.join(d, 'j1.json'))), rec)


class Packaging(unittest.TestCase):
    def test_pages_have_placeholder_and_no_external_resources(self):
        d = os.path.join(SKILL, 'assets', 'pages')
        for f in os.listdir(d):
            html = open(os.path.join(d, f), encoding='utf-8').read()
            self.assertIn('/*QUAFU_DATA*/null', html, f)
            self.assertIsNone(re.search(r'(src|href)\s*=\s*["\']https?://', html), f)
            self.assertNotIn('@import', html, f)

    def test_skill_frontmatter(self):
        s = open(os.path.join(SKILL, 'SKILL.md'), encoding='utf-8').read()
        m = re.match(r'^---\nname: (.+)\ndescription: (.+)\n---\n', s)
        self.assertTrue(m)
        self.assertEqual(m.group(1), 'quafu')
        self.assertRegex(m.group(1), r'^[a-z0-9]+(-[a-z0-9]+)*$')
        self.assertLessEqual(len(m.group(2)), 1024)
        for ref in set(re.findall(r'\]\((references/[^)]+)\)', s)):
            self.assertTrue(os.path.exists(os.path.join(SKILL, ref)), ref)

    def test_manifests(self):
        for f in ('marketplace.json', 'plugin.json'):
            json.load(open(os.path.join(ROOT, '.claude-plugin', f), encoding='utf-8'))

    def test_workbuddy_package(self):
        import tempfile
        import zipfile
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
        import build_workbuddy as W
        out = os.path.join(tempfile.mkdtemp(), 'quafu.zip')
        W.build(out, 'QUAFU-Quantum')
        self.assertEqual(W.verify(out), [])
        head = zipfile.ZipFile(out).read('quafu/SKILL.md').decode('utf-8').split('\n---\n')[0]
        version = json.load(open(os.path.join(ROOT, '.claude-plugin', 'plugin.json')))['version']
        self.assertIn('\nversion: %s\n' % version, head + '\n')
        self.assertTrue(W.check_frontmatter('---\ndescription: a: b\n---\n'))


if __name__ == '__main__':
    unittest.main()
