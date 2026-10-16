# -*- coding: utf-8 -*-
"""端到端真跑：把内置模板交到 QUAFU 上，等结果、分析，打印一张 Markdown 表。要已登录（或设 QUAFU_API_KEY）。

    python tests/e2e.py --target sim                       全部模板，理想模拟器
    python tests/e2e.py --target Shenglian-sim             全部模板，带噪模拟
    python tests/e2e.py --target Shenglian bell bernstein-vazirani    真机只挑一两个
记账写在 --runs 目录（默认 ./quafu-runs-e2e）。"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QF = os.path.join(ROOT, 'skills', 'quafu', 'scripts', 'qf.py')
sys.path.insert(0, os.path.dirname(QF))
import algorithms as A  # noqa: E402

CASES = {'grover3': ('grover', ['marked=101'])}


def headline(a):
    m, k = a['metrics'], a['kind']
    if k == 'rotation':
        return '对比度 %.2f（理想 1）' % m['contrast']
    if k == 'vqe':
        return '最低能量 %.4f Ha（精确 %.4f，差 %.1f mHa）' % (m['fit']['min'], m['exact'],
                                                     1000 * (m['fit']['min'] - m['exact']))
    if k == 'qaoa':
        return '最好平均割值 %.2f（理想 %.2f）；测到最大割 %.1f%%' % (m['best']['cut'], m['best']['ideal'],
                                                         100 * m['best']['p_max'])
    s = '保真度 %.3f；正确结果占 %.1f%%' % (m['fidelity'], 100 * m['good_mass'])
    if m.get('p1_c0') is not None:
        s += '；P(1)=%.1f%%' % (100 * m['p1_c0'])
    return s


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--target', default='sim')
    p.add_argument('--runs', default='quafu-runs-e2e')
    p.add_argument('--budget', type=int, default=600)
    p.add_argument('names', nargs='*')
    a = p.parse_args()
    names = a.names or list(A.TEMPLATES) + ['grover3']
    env = dict(os.environ, QUAFU_RUNS_DIR=os.path.abspath(a.runs))
    rows = []
    for n in names:
        tpl, params = CASES.get(n, (n, []))
        cmd = [sys.executable, QF, 'run', tpl, '--target', a.target] + sum((['-p', x] for x in params), [])
        out = subprocess.run(cmd, env=env, capture_output=True, text=True)
        job = next((ln.split('：', 1)[1].strip() for ln in out.stdout.splitlines() if ln.startswith('已提交')), None)
        if not job:
            rows.append((n, '-', '提交失败：' + (out.stderr or out.stdout).strip().splitlines()[-1]))
            continue
        w = subprocess.run([sys.executable, QF, 'wait', job, '--budget', str(a.budget)], env=env,
                           capture_output=True, text=True)
        if w.returncode:
            rows.append((n, job, '未完成：' + w.stdout.strip().splitlines()[0]))
            continue
        subprocess.run([sys.executable, QF, 'analyze', job], env=env, capture_output=True, text=True)
        with open(os.path.join(a.runs, job + '.analysis.json'), encoding='utf-8') as f:
            rows.append((n, job, headline(json.load(f))))
    print('| 模板 | 任务组号 | 结果（%s） |' % a.target)
    print('|---|---|---|')
    for r in rows:
        print('| %s | `%s` | %s |' % r)


if __name__ == '__main__':
    main()
