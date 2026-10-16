# -*- coding: utf-8 -*-
"""QUAFU skill 的命令行助手：提交内置算法、记下任务组号、退避等待、分析、生成结果网页。

    python qf.py list                                  内置算法清单
    python qf.py show bell                             看线路与理想结果（不联网）
    python qf.py devices                               现在能交到哪些目标、排队多少
    python qf.py run bell --target sim                 提交；任务组号记进 ./quafu-runs/
    python qf.py run custom --qasm my.qasm --target sim   提交自己写的线路
    python qf.py wait <任务组号> --budget 120          等一会儿；没好就退出码 3，之后再来
    python qf.py runs                                  本目录下记过的任务组和状态（新会话从这里接着取）
    python qf.py analyze <任务组号>                    和理想结果对比，打印人话总结
    python qf.py page <任务组号> [--template 文件]     生成结果网页并用本地浏览器打开
    python qf.py page <号1> <号2> [<号3>]              同一模板的几次运行（模拟器/带噪/真机）放一页对比

除 list / show 外都要装 quafu-sdk（pip install quafu-sdk）。记账目录默认是当前目录下的 quafu-runs/，
可用环境变量 QUAFU_RUNS_DIR 改。
"""
import argparse
import datetime
import json
import math
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import algorithms as A  # noqa: E402
import qfsim  # noqa: E402

SKILL_DIR = os.path.dirname(HERE)
PAGES = os.path.join(SKILL_DIR, 'assets', 'pages')
EXIT_PENDING = 3


def runs_dir():
    d = os.environ.get('QUAFU_RUNS_DIR') or os.path.join(os.getcwd(), 'quafu-runs')
    os.makedirs(d, exist_ok=True)
    return d


def ledger_path(job_id):
    return os.path.join(runs_dir(), '%s.json' % job_id)


def load(job_id):
    p = ledger_path(job_id)
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    return None


def save(rec):
    with open(ledger_path(rec['job_id']), 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def quafu():
    try:
        import quafu as q
    except ImportError:
        sys.exit('还没装 QUAFU SDK：先运行  pip install quafu-sdk  （或 uv pip install quafu-sdk）')
    if not hasattr(q, 'submit'):
        sys.exit('当前环境里的 quafu 不是 QUAFU SDK（被同名旧包占了）。新建一个虚拟环境再装 quafu-sdk。')
    return q


def parse_params(items):
    out = {}
    for it in items or []:
        k, _, v = it.partition('=')
        out[k.strip()] = v.strip()
    return out


# ── 等待时间估计 ──────────────────────────────────────────────────

def eta_text(target, queue):
    """给人看的大概等待时间。依据：模拟器通常几秒到一分钟；真机按排队任务数粗估（经验值，每条约 3–10 秒）。"""
    if target == 'sim' or target.endswith('-sim'):
        return '模拟器，一般几秒到一分钟。'
    if target.endswith('-sim-jiuding'):
        return '九鼎模拟器，空闲时要先启动，第一条任务可能要等几分钟。'
    if queue is None:
        return '真机，排队情况未知，可能几分钟到几小时。'
    lo, hi = queue * 3 / 60, queue * 10 / 60
    if hi < 5:
        return '真机，前面排着 %d 条任务，大概几分钟。' % queue
    return '真机，前面排着 %d 条任务，粗估 %d–%d 分钟（只是估计，真机还会穿插校准）。' % (queue, max(1, lo), hi)


# ── 命令 ──────────────────────────────────────────────────────────

def cmd_list(a):
    rows = []
    for name, t in A.TEMPLATES.items():
        rows.append({'name': name, 'title': t['title'], 'qubits': t['qubits'], 'circuits': t['circuits'],
                     'targets': t['targets'], 'params': t['params'], 'idea': t['idea'], 'expect': t['expect']})
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    for r in rows:
        print('%-20s %s' % (r['name'], r['title']))
        print('    比特 %s · 线路 %s 条 · 推荐 %s · 参数 %s' % (r['qubits'], r['circuits'], ' / '.join(r['targets']),
                                                         r['params'] or '无'))
        print('    %s' % r['expect'])


def cmd_show(a):
    circuits, params = A.build(a.template, **parse_params(a.param))
    print('参数：%s，共 %d 条线路' % (params, len(circuits)))
    for i, (lab, q) in enumerate(circuits[:a.limit]):
        print('── 线路 %d %s' % (i, lab or ''))
        print(q)
        print('理想结果：', {k: round(v, 4) for k, v in qfsim.probabilities(q).items()})
    if len(circuits) > a.limit:
        print('……其余 %d 条省略（--limit 调）' % (len(circuits) - a.limit))


def couplers(q, name):
    """真机现在能用的双比特连接数（平台按校准与实测筛过的）。0 表示这台只能跑单比特线路。查不到为 None。"""
    try:
        return len(q.Client().metadata(name).get('coupling_map') or [])
    except Exception:
        return None


def cmd_devices(a):
    q = quafu()
    print('%-22s %-4s %-12s %-6s %-7s %-12s %s' % ('目标', '类型', '状态', '比特', '排队', 'shots', '可用双比特连接'))
    for d in q.devices():
        lim = d.get('limits') or {}
        n = couplers(q, d['name']) if d['kind'] == 'real' and d['status'] == 'online' else None
        cp = '' if d['kind'] != 'real' else ('—' if n is None else ('0（只能跑单比特线路）' if n == 0 else str(n)))
        shots = '%s–%s' % (lim.get('min_shots'), lim.get('max_shots')) + (
            '，%s 的倍数' % lim['shots_step'] if (lim.get('shots_step') or 1) > 1 else '')
        print('%-22s %-4s %-12s %-6s %-7s %-12s %s' % (d['name'], d['kind'], d['status'], d['n_qubits'],
                                                      d['queue'], shots, cp))


def _target_info(q, target):
    for d in q.devices():
        if d['name'] == target:
            return d
    return None


def cmd_run(a):
    q = quafu()
    if a.template == 'custom':
        if not a.qasm:
            sys.exit('custom 要配 --qasm 文件')
        with open(a.qasm, encoding='utf-8') as f:
            circuits, params = [({'file': os.path.basename(a.qasm)}, f.read())], {}
        kind = 'distribution'
    else:
        circuits, params = A.build(a.template, **parse_params(a.param))
        kind = A.TEMPLATES[a.template]['kind']
    info = _target_info(q, a.target)
    if info is None:
        sys.exit('没有叫 %s 的目标。先运行 qf.py devices 看看有哪些。' % a.target)
    if info['status'] not in ('online', 'standby', 'starting'):
        sys.exit('%s 现在是 %s 状态，交不了。换一台在线的（qf.py devices）。' % (a.target, info['status']))
    if info['kind'] == 'real' and any(re.search(r'^(cx|cz|cy|swap|ccx|cp|cu1|crz)\b', ln.strip(), re.M)
                                      for _, c in circuits for ln in c.splitlines()):
        if couplers(q, a.target) == 0:
            sys.exit('%s 现在没有可用的双比特连接，只能跑单比特线路。换一台（qf.py devices 看「可用双比特连接」）。'
                     % a.target)
    lim = info.get('limits') or {}
    shots = a.shots or max(1024, lim.get('min_shots') or 1)
    step = lim.get('shots_step') or 1
    if shots % step:
        shots = (shots // step + 1) * step
        print('这台目标要求 shots 是 %d 的倍数，已调成 %d。' % (step, shots))
    name = a.name or 'quafu-skill %s' % a.template
    job = q.submit([c for _, c in circuits], target=a.target, shots=shots, name=name)
    rec = {'job_id': job.id, 'template': a.template, 'params': params, 'kind': kind, 'target': a.target,
           'shots': shots, 'submitted_at': now(), 'labels': [lab for lab, _ in circuits],
           'circuits': [c for _, c in circuits], 'status': 'Queued', 'queue_at_submit': info.get('queue')}
    save(rec)
    print('已提交。任务组号：%s' % job.id)
    print('预计：%s' % eta_text(a.target, info.get('queue')))
    print('记账文件：%s' % ledger_path(job.id))
    print('取结果：python %s wait %s' % (os.path.abspath(__file__), job.id))


def _fetch(q, rec):
    job = q.job(rec['job_id'])
    rs = job.results(timeout=60)
    rec['results'] = [{'status': r.status, 'counts': r.counts, 'shots_returned': r.shots_returned,
                       'backend': r.backend, 'calibration_id': r.calibration_id, 'measurements': r.measurements,
                       'error': r.error, 'executed_qasm': r.executed_qasm} for r in rs]
    rec['finished_at'] = now()
    rec['readout'] = _readout(q, rec['results'])
    return rec


def _readout(q, results):
    """真机结果：查这次用的校准数据里，被测量的物理比特的读出保真度和 T1/T2。查不到就空着，不影响分析。"""
    out = {}
    for r in results:
        cid = r.get('calibration_id')
        if not cid or not r.get('measurements'):
            continue
        try:
            cal = q.calibration(cid)
        except Exception:
            continue
        for m in r['measurements']:
            pq = m.get('physical_qubit')
            if pq is None or str(m.get('cbit')) in out:
                continue
            try:
                base, meas = cal.qubit(pq) or {}, cal.measured_qubit(pq) or {}
            except Exception:
                continue
            out[str(m['cbit'])] = {'physical_qubit': pq, 'calibration_id': cid,
                                   'f0': meas.get('readout_fidelity_0') or base.get('readout_fidelity_0'),
                                   'f1': meas.get('readout_fidelity_1') or base.get('readout_fidelity_1'),
                                   't1_us': base.get('t1_us'), 't2_us': base.get('t2_us')}
        break
    return out


def cmd_wait(a):
    q = quafu()
    rec = load(a.job_id) or {'job_id': a.job_id, 'template': 'unknown', 'kind': 'distribution', 'params': {},
                             'labels': [], 'circuits': [], 'target': None}
    job = q.job(a.job_id)
    start = time.monotonic()
    try:
        st = job.wait(timeout=a.budget)
    except q.Timeout:
        d = job._refresh()
        c = d.get('counts') or {}
        rec['status'] = d.get('status')
        save(rec)
        waited = time.monotonic() - start
        print('还没好（等了 %d 秒）。状态 %s：完成 %s / 共 %s 条。' % (waited, rec['status'], c.get('finished'),
                                                          c.get('total')))
        print('任务组仍在平台上排队/运行，随时可以再来取：python %s wait %s' % (os.path.abspath(__file__), a.job_id))
        sys.exit(EXIT_PENDING)
    rec['status'] = st
    _fetch(q, rec)
    save(rec)
    ok = sum(1 for r in rec['results'] if r['status'] == 'Finished')
    print('结束：%s（成功 %d / 共 %d 条），用时 %d 秒。' % (st, ok, len(rec['results']), time.monotonic() - start))
    for i, r in enumerate(rec['results'][:3]):
        print('  线路 %d：%s %s' % (i, r['status'], r['counts'] if r['counts'] else (r['error'] or {}).get('detail')))
    print('下一步：python %s analyze %s' % (os.path.abspath(__file__), a.job_id))


def cmd_runs(a):
    d = runs_dir()
    files = sorted(f for f in os.listdir(d) if f.endswith('.json') and not f.endswith('.analysis.json'))
    if not files:
        print('%s 下还没有记录。' % d)
        return
    q = quafu() if a.refresh else None
    for f in files:
        with open(os.path.join(d, f), encoding='utf-8') as fh:
            rec = json.load(fh)
        if q and rec.get('status') not in ('Finished', 'PartiallyFinished', 'Failed', 'Cancelled'):
            try:
                rec['status'] = q.job(rec['job_id']).status()
                save(rec)
            except Exception as e:  # 查不到就照旧显示本地记录
                rec['status'] = '%s（刷新失败：%s）' % (rec.get('status'), e.__class__.__name__)
        print('%-32s %-18s %-14s %-18s %s' % (rec['job_id'], rec.get('template'), rec.get('target'),
                                            rec.get('status'), rec.get('submitted_at', '')))


# ── 分析 ──────────────────────────────────────────────────────────

def norm(counts):
    tot = float(sum(counts.values())) or 1.0
    return {k: v / tot for k, v in counts.items()}


def compare(ideal, meas):
    keys = set(ideal) | set(meas)
    tvd = 0.5 * sum(abs(ideal.get(k, 0) - meas.get(k, 0)) for k in keys)
    hf = sum(math.sqrt(ideal.get(k, 0) * meas.get(k, 0)) for k in keys) ** 2
    good = [k for k, v in ideal.items() if v >= 0.05]
    return {'tvd': tvd, 'fidelity': hf, 'good_states': good, 'good_mass_measured': sum(meas.get(k, 0) for k in good),
            'good_mass_ideal': sum(ideal.get(k, 0) for k in good)}


def _pct(x):
    return '%.1f%%' % (100 * x)


def analyze_record(rec):
    res = rec.get('results') or []
    kind = rec.get('kind', 'distribution')
    items = []
    for i, r in enumerate(res):
        lab = rec['labels'][i] if i < len(rec.get('labels', [])) else {}
        q = rec['circuits'][i] if i < len(rec.get('circuits', [])) else (r.get('executed_qasm') or '')
        try:
            ideal = qfsim.probabilities(q) if q else {}
        except ValueError:
            ideal = {}
        meas = norm(r['counts']) if r.get('counts') else {}
        it = {'label': lab, 'ideal': ideal, 'measured': meas, 'counts': r.get('counts'),
              'shots': r.get('shots_returned'), 'backend': r.get('backend'), 'status': r.get('status')}
        if ideal and meas:
            it.update(compare(ideal, meas))
        items.append(it)
    out = {'job_id': rec['job_id'], 'template': rec.get('template'), 'title': A.TEMPLATES.get(
        rec.get('template'), {}).get('title', rec.get('template')), 'kind': kind, 'target': rec.get('target'),
        'backend': next((it['backend'] for it in items if it['backend']), rec.get('target')),
        'params': rec.get('params'), 'shots': rec.get('shots'), 'submitted_at': rec.get('submitted_at'),
        'finished_at': rec.get('finished_at'), 'items': items, 'summary': [], 'metrics': {}}
    ok = [it for it in items if it['measured']]
    if not ok:
        out['summary'].append('没有成功的线路，没法分析。看看 wait 输出里的失败原因。')
        return out
    shots = ok[0]['shots'] or 1
    noise_floor = 1 / math.sqrt(shots)
    real = not (str(out['target']).endswith('sim') or str(out['target']).endswith('-sim-jiuding')
                or out['target'] == 'sim')
    if kind in ('distribution', 'qrng') or len(ok) == 1:
        it = ok[0]
        top = max(it['measured'].items(), key=lambda kv: kv[1])
        out['metrics'] = {'fidelity': it.get('fidelity'), 'tvd': it.get('tvd'),
                          'good_mass': it.get('good_mass_measured'), 'top': top[0], 'top_p': top[1],
                          'stat_noise': noise_floor}
        nbits = len(top[0])
        full = it.get('good_states') is not None and len(it['good_states']) == 2 ** nbits
        if full:
            out['summary'].append('理想情况下每种结果都可能出现：' + '；'.join(
                '%s 理想 %s、实测 %s' % (k, _pct(v), _pct(it['measured'].get(k, 0))) for k, v in it['ideal'].items())
                + '。统计起伏约 ±%s。' % _pct(noise_floor / 2))
            out['summary'].append('分布相似度（经典保真度）%.3f，1 表示与理想完全一样。' % it['fidelity'])
        elif it.get('good_states') is not None:
            g = it['good_states']
            out['summary'].append('理想情况下结果集中在 %s（合计 %s）；实测这些结果占 %s。' % (
                '、'.join(g), _pct(it['good_mass_ideal']), _pct(it['good_mass_measured'])))
            bad = it['good_mass_ideal'] - it['good_mass_measured']
            if bad > 2 * noise_floor:
                out['summary'].append('其余 %s 是「不该出现」的结果，来自噪声：门操作不完美、比特在计算中途丢失状态'
                                      '（退相干），以及测量时把 0 看成 1 或反过来（读出误差）。' % _pct(max(bad, 0)))
            else:
                out['summary'].append('偏差在 %d 次测量本身的统计起伏（约 ±%s）之内，可以看成和理想一致。' % (
                    shots, _pct(noise_floor)))
            out['summary'].append('分布相似度（经典保真度）%.3f，1 表示与理想完全一样。' % it['fidelity'])
            best_ideal = max(it['ideal'].items(), key=lambda kv: kv[1])
            if best_ideal[1] >= 0.5 and len(g) == 1:
                right = top[0] == best_ideal[0]
                out['summary'].append('出现最多的结果是 %s（%s），%s' % (
                    top[0], _pct(top[1]), '正是正确答案——按「取出现最多的那个」读结果，算法答对了。' if right
                    else '不是正确答案 %s——噪声已经大到把答案淹没了。' % best_ideal[0]))
        if kind == 'qrng':
            p1 = sum(v for k, v in it['measured'].items() if k.endswith('1'))
            out['metrics']['p1_c0'] = p1
            biased = abs(p1 - 0.5) > 3 * 0.5 / math.sqrt(shots)
            out['summary'].append('c[0] 测到 1 的比例 %s，理想 50%%；偏离 %s，统计起伏约 ±%s。%s' % (
                _pct(p1), _pct(abs(p1 - 0.5)), _pct(0.5 / math.sqrt(shots)),
                '偏离明显大于统计起伏：这台机器的这个比特有偏向。'
                if biased else '在统计起伏之内，看不出偏向。'))
            r0 = (rec.get('readout') or {}).get('0') or {}
            if biased and r0.get('f0') and r0.get('f1'):
                exp1 = 0.5 * (1 - r0['f0']) + 0.5 * r0['f1']
                out['summary'].append('按当次校准数据，Q%s 把 0 看成 1 的概率 %s、把 1 看成 0 的概率 %s，光读出误差就会让 1 的比例变成约 %s。' % (
                    r0['physical_qubit'], _pct(1 - r0['f0']), _pct(1 - r0['f1']), _pct(exp1)))
    elif kind == 'rotation':
        pts = []
        for it in ok:
            th = it['label'].get('theta')
            pts.append({'theta': th, 'p1': it['measured'].get('1', 0.0), 'ideal': it['ideal'].get('1', 0.0)})
        # 拟合 P1 = a - b·cosθ
        n = len(pts)
        cs = [math.cos(p['theta']) for p in pts]
        ys = [p['p1'] for p in pts]
        mc, my = sum(cs) / n, sum(ys) / n
        var = sum((c - mc) ** 2 for c in cs) or 1
        b = -sum((c - mc) * (y - my) for c, y in zip(cs, ys)) / var
        a_ = my + b * mc
        out['metrics'] = {'points': pts, 'contrast': 2 * b, 'offset': a_, 'p1_at_0': a_ - b, 'p1_at_pi': a_ + b}
        out['summary'].append('理想曲线从 0 升到 1；拟合到的实测曲线从 %s 升到 %s，「振幅」（对比度）%.2f，理想是 1。' % (
            _pct(max(0.0, a_ - b)), _pct(min(1.0, a_ + b)), 2 * b))
        if 2 * b < 0.95:
            out['summary'].append('两端够不着 0 和 1，主要是读出误差和比特能量弛豫；曲线形状（正弦）是对的，说明旋转本身准确。')
        else:
            out['summary'].append('和理想几乎重合，剩下的小起伏来自有限次数测量的统计起伏。')
    elif kind == 'vqe':
        H = A.H2
        by = {}
        for it in ok:
            th = round(it['label']['theta'], 9)
            by.setdefault(th, {})[it['label']['basis']] = it
        curve = []
        for th in sorted(by):
            z, x = by[th].get('Z'), by[th].get('X')
            if not (z and x):
                continue

            def ez(dist, c0, c1):
                return sum(p * (1 if ((k[-1 - c0] == '1') + (k[-1 - c1] == '1' if c1 is not None else 0)) % 2 == 0
                                else -1) for k, p in dist.items())

            def energy(zd, xd):
                return (H['II'] + H['IZ'] * ez(zd, 0, None) + H['ZI'] * ez(zd, 1, None) + H['ZZ'] * ez(zd, 0, 1)
                        + H['XX'] * ez(xd, 0, 1)) + A.H2_NUCLEAR
            curve.append({'theta': th, 'energy': energy(z['measured'], x['measured']),
                          'ideal': energy(z['ideal'], x['ideal'])})
        fit = _fit_sin([p['theta'] for p in curve], [p['energy'] for p in curve])
        out['metrics'] = {'curve': curve, 'fit': fit, 'exact': A.H2_EXACT_TOTAL,
                          'best_point': min(curve, key=lambda p: p['energy']) if curve else None}
        if fit:
            out['summary'].append('拟合出的最低能量 %.4f Ha（θ≈%.2f），精确答案 %.4f Ha，差 %.1f 毫 Ha。' % (
                fit['min'], fit['argmin'], A.H2_EXACT_TOTAL, 1000 * (fit['min'] - A.H2_EXACT_TOTAL)))
            out['summary'].append('「化学精度」是 1.6 毫 Ha；%s' % (
                '这次达到了。' if abs(fit['min'] - A.H2_EXACT_TOTAL) < 0.0016 else
                '没达到很正常——噪声会让能量偏高，有限的测量次数也带来起伏。'))
    elif kind == 'qaoa':
        grid = []
        for it in ok:
            e = sum(p * A.cut_value(k) for k, p in it['measured'].items())
            ei = sum(p * A.cut_value(k) for k, p in it['ideal'].items())
            pmax = sum(p for k, p in it['measured'].items() if A.cut_value(k) == 4)
            grid.append({'gamma': it['label']['gamma'], 'beta': it['label']['beta'], 'cut': e, 'ideal': ei,
                         'p_max': pmax})
        best = max(grid, key=lambda g: g['cut'])
        out['metrics'] = {'grid': grid, 'best': best, 'random_guess': 2.0}
        out['summary'].append('最好的一组角度（γ=%.2f, β=%.2f）平均割值 %.2f，理想同点 %.2f；随便乱分平均是 2，最优是 4。' % (
            best['gamma'], best['beta'], best['cut'], best['ideal']))
        out['summary'].append('在这组角度下，直接测到最优分法（0101 或 1010）的概率 %s。' % _pct(best['p_max']))
    ro = rec.get('readout') or {}
    out['readout'] = ro
    if ro and all(v.get('f0') and v.get('f1') for v in ro.values()):
        parts = ['c[%s]→Q%s：0 读对 %s、1 读对 %s' % (c, v['physical_qubit'], _pct(v['f0']), _pct(v['f1']))
                 for c, v in sorted(ro.items(), key=lambda kv: int(kv[0]))]
        out['summary'].append('读出（测量时看错）有多大影响：' + '；'.join(parts) + '。')
        it = ok[0]
        if kind == 'distribution' and it.get('good_states'):
            est = 0.0
            for k, p in it['ideal'].items():
                prod = 1.0
                for c, v in ro.items():
                    bit = k[-1 - int(c)] if int(c) < len(k) else '0'
                    prod *= v['f1'] if bit == '1' else v['f0']
                est += p * prod
            out['metrics']['readout_only_estimate'] = est
            got = it.get('good_mass_measured', 0)
            out['summary'].append('光是读出误差，就会让正确结果只剩约 %s；实测 %s，%s' % (
                _pct(est), _pct(got),
                '比这个估计还高：校准表上的读出数据是校准那一刻测的，和这次运行不在同一时刻，这个估计只能当参考。'
                if got > est + 0.05 else
                '和这个估计相当——这条线路里读出误差是主要的噪声来源。' if got > est - 0.03
                else '剩下的差距来自门操作误差和退相干。'))
    if real:
        out['summary'].append('这是在真机 %s 上跑的。' % out['backend'])
    return out


def _fit_sin(xs, ys):
    """最小二乘拟合 y = a + b·cos x + c·sin x，返回最低点。"""
    n = len(xs)
    if n < 3:
        return None
    rows = [[1.0, math.cos(x), math.sin(x)] for x in xs]
    ata = [[sum(r[i] * r[j] for r in rows) for j in range(3)] for i in range(3)]
    aty = [sum(r[i] * y for r, y in zip(rows, ys)) for i in range(3)]
    m = [ata[i] + [aty[i]] for i in range(3)]
    for i in range(3):
        p = max(range(i, 3), key=lambda k: abs(m[k][i]))
        m[i], m[p] = m[p], m[i]
        for k in range(3):
            if k != i:
                f = m[k][i] / m[i][i]
                m[k] = [u - f * v for u, v in zip(m[k], m[i])]
    a, b, c = (m[i][3] / m[i][i] for i in range(3))
    amp = math.hypot(b, c)
    arg = math.atan2(-c, -b) % (2 * math.pi)
    return {'a': a, 'b': b, 'c': c, 'min': a - amp, 'argmin': arg}


def cmd_analyze(a):
    rec = load(a.job_id)
    if rec is None or not rec.get('results'):
        sys.exit('本地还没有这个任务组的结果。先运行：python %s wait %s' % (os.path.abspath(__file__), a.job_id))
    out = analyze_record(rec)
    p = os.path.join(runs_dir(), '%s.analysis.json' % a.job_id)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    print('%s · %s · 任务组 %s' % (out['title'], out['backend'], out['job_id']))
    for s in out['summary']:
        print(' - ' + s)
    print('完整分析已存到 %s' % p)


# ── 网页 ──────────────────────────────────────────────────────────

def open_in_browser(path):
    path = os.path.abspath(path)
    try:
        if sys.platform == 'darwin':
            return subprocess.call(['open', path]) == 0
        if os.name == 'nt':
            os.startfile(path)  # noqa
            return True
        if 'microsoft' in open('/proc/version').read().lower():
            win = subprocess.check_output(['wslpath', '-w', path]).decode().strip()
            return subprocess.call(['explorer.exe', win]) in (0, 1)   # explorer.exe 成功也常返回 1
        return subprocess.call(['xdg-open', path]) == 0
    except Exception:
        import webbrowser
        return webbrowser.open('file://' + path)


def cmd_page(a):
    datas = []
    for jid in a.job_id:
        rec = load(jid)
        if rec is None or not rec.get('results'):
            sys.exit('本地还没有任务组 %s 的结果。先运行 wait。' % jid)
        datas.append(analyze_record(rec))
    if len({d['template'] for d in datas}) > 1:
        sys.exit('对比页只能放同一个模板的多次运行（比如模拟器 vs 带噪模拟 vs 真机）。')
    if len(datas) > 3:
        sys.exit('对比页最多放 3 次运行。')
    data = datas[0] if len(datas) == 1 else {'runs': datas}
    tpl = a.template or os.path.join(PAGES, 'aurora.html')
    with open(tpl, encoding='utf-8') as f:
        html = f.read()
    marker = '/*QUAFU_DATA*/null'
    if marker not in html:
        sys.exit('模板里没有数据占位符 %s' % marker)
    html = html.replace(marker, json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))
    out = a.out or os.path.join(runs_dir(), '%s.html' % '_vs_'.join(a.job_id))
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print('网页：%s' % os.path.abspath(out))
    if not a.no_open:
        print('已用浏览器打开。' if open_in_browser(out) else '没能自动打开，请手动双击上面的文件。')


def main(argv=None):
    p = argparse.ArgumentParser(prog='qf.py', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('list')
    s.add_argument('--json', action='store_true')
    s.set_defaults(func=cmd_list)
    s = sub.add_parser('show')
    s.add_argument('template', choices=list(A.TEMPLATES))
    s.add_argument('--param', '-p', action='append', help='k=v，可重复')
    s.add_argument('--limit', type=int, default=2)
    s.set_defaults(func=cmd_show)
    s = sub.add_parser('devices')
    s.set_defaults(func=cmd_devices)
    s = sub.add_parser('run')
    s.add_argument('template', choices=list(A.TEMPLATES) + ['custom'])
    s.add_argument('--target', '-t', default='sim')
    s.add_argument('--shots', type=int)
    s.add_argument('--param', '-p', action='append', help='k=v，可重复')
    s.add_argument('--qasm', help='custom 时的线路文件')
    s.add_argument('--name')
    s.set_defaults(func=cmd_run)
    s = sub.add_parser('wait')
    s.add_argument('job_id')
    s.add_argument('--budget', type=float, default=120, help='这次最多等几秒（默认 120）')
    s.set_defaults(func=cmd_wait)
    s = sub.add_parser('runs')
    s.add_argument('--refresh', action='store_true', help='向平台刷新未结束的状态')
    s.set_defaults(func=cmd_runs)
    s = sub.add_parser('analyze')
    s.add_argument('job_id')
    s.add_argument('--json', action='store_true')
    s.set_defaults(func=cmd_analyze)
    s = sub.add_parser('page')
    s.add_argument('job_id', nargs='+', help='一个任务组号；给 2–3 个同模板的号就生成对比页')
    s.add_argument('--template', help='网页模板（含 /*QUAFU_DATA*/null 占位符）')
    s.add_argument('--out')
    s.add_argument('--no-open', action='store_true')
    s.set_defaults(func=cmd_page)
    a = p.parse_args(argv)
    a.func(a)


if __name__ == '__main__':
    main()
