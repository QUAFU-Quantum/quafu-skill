# -*- coding: utf-8 -*-
"""极小的本地理想模拟器：只用标准库，算 OpenQASM 2.0 线路在理想情况下的测量概率。

用途是拿来和 QUAFU 上的真实结果对比（「理想应该是什么」），不是用来代替平台。
支持本 skill 模板用到的门：id x y z h s sdg t tdg sx rx ry rz p u1 u2 u3 cx cz cy swap ccx crz cp/cu1，
以及末尾的 measure q[i] -> c[j]。比特数建议不超过 12。

位序与 QUAFU 一致：计数的键是经典位串，最右一位是 c[0]。
"""
import cmath
import math
import re

_SQ2 = 1 / math.sqrt(2)


def _expr(s):
    """解析门参数里的算式，只允许数字、pi 和四则运算。"""
    s = s.strip()
    if not re.fullmatch(r'[0-9eE+\-*/(). pi]*', s):
        raise ValueError('不认识的参数表达式: %r' % s)
    return float(eval(s, {'__builtins__': {}}, {'pi': math.pi}))


def _u3(t, p, l):
    c, s = math.cos(t / 2), math.sin(t / 2)
    return [[c, -cmath.exp(1j * l) * s],
            [cmath.exp(1j * p) * s, cmath.exp(1j * (p + l)) * c]]


def _single(name, a):
    if name == 'id':
        return [[1, 0], [0, 1]]
    if name == 'x':
        return [[0, 1], [1, 0]]
    if name == 'y':
        return [[0, -1j], [1j, 0]]
    if name == 'z':
        return [[1, 0], [0, -1]]
    if name == 'h':
        return [[_SQ2, _SQ2], [_SQ2, -_SQ2]]
    if name == 's':
        return [[1, 0], [0, 1j]]
    if name == 'sdg':
        return [[1, 0], [0, -1j]]
    if name == 't':
        return [[1, 0], [0, cmath.exp(1j * math.pi / 4)]]
    if name == 'tdg':
        return [[1, 0], [0, cmath.exp(-1j * math.pi / 4)]]
    if name == 'sx':
        return [[(1 + 1j) / 2, (1 - 1j) / 2], [(1 - 1j) / 2, (1 + 1j) / 2]]
    if name == 'rx':
        c, s = math.cos(a[0] / 2), math.sin(a[0] / 2)
        return [[c, -1j * s], [-1j * s, c]]
    if name == 'ry':
        c, s = math.cos(a[0] / 2), math.sin(a[0] / 2)
        return [[c, -s], [s, c]]
    if name == 'rz':
        return [[cmath.exp(-1j * a[0] / 2), 0], [0, cmath.exp(1j * a[0] / 2)]]
    if name in ('p', 'u1'):
        return [[1, 0], [0, cmath.exp(1j * a[0])]]
    if name == 'u2':
        return _u3(math.pi / 2, a[0], a[1])
    if name in ('u3', 'u'):
        return _u3(a[0], a[1], a[2])
    return None


class State:
    def __init__(self, n):
        self.n = n
        self.amp = [0j] * (1 << n)
        self.amp[0] = 1 + 0j

    def apply1(self, m, q):
        bit = 1 << q
        a = self.amp
        for i in range(len(a)):
            if not i & bit:
                j = i | bit
                x, y = a[i], a[j]
                a[i] = m[0][0] * x + m[0][1] * y
                a[j] = m[1][0] * x + m[1][1] * y

    def controlled1(self, m, ctrls, q):
        bit = 1 << q
        cmask = 0
        for c in ctrls:
            cmask |= 1 << c
        a = self.amp
        for i in range(len(a)):
            if (i & cmask) == cmask and not i & bit:
                j = i | bit
                x, y = a[i], a[j]
                a[i] = m[0][0] * x + m[0][1] * y
                a[j] = m[1][0] * x + m[1][1] * y

    def swap(self, p, q):
        a = self.amp
        bp, bq = 1 << p, 1 << q
        for i in range(len(a)):
            if (i & bp) and not (i & bq):
                j = (i ^ bp) | bq
                a[i], a[j] = a[j], a[i]


_LINE = re.compile(r'^([a-z0-9_]+)\s*(?:\(([^)]*)\))?\s+(.+)$')
_ARG = re.compile(r'([A-Za-z_]\w*)\[(\d+)\]')


def parse(qasm):
    """把 QASM 拆成 (比特数, 门列表, 测量表 {cbit: qubit}, 经典位数)。"""
    qregs, cregs, ops, meas = {}, {}, [], {}
    nq = nc = 0
    text = re.sub(r'//[^\n]*', '', qasm)
    for stmt in text.split(';'):
        s = stmt.strip()
        if not s or s.startswith('OPENQASM') or s.startswith('include'):
            continue
        if s.startswith('barrier'):
            continue
        m = re.match(r'^qreg\s+(\w+)\[(\d+)\]$', s)
        if m:
            qregs[m.group(1)] = nq
            nq += int(m.group(2))
            continue
        m = re.match(r'^creg\s+(\w+)\[(\d+)\]$', s)
        if m:
            cregs[m.group(1)] = nc
            nc += int(m.group(2))
            continue
        m = re.match(r'^measure\s+(\w+)\[(\d+)\]\s*->\s*(\w+)\[(\d+)\]$', s)
        if m:
            meas[cregs[m.group(3)] + int(m.group(4))] = qregs[m.group(1)] + int(m.group(2))
            continue
        m = _LINE.match(s)
        if not m:
            raise ValueError('不认识的语句: %r' % s)
        name, params, args = m.group(1), m.group(2), m.group(3)
        vals = [_expr(p) for p in params.split(',')] if params else []
        qs = [qregs[r] + int(i) for r, i in _ARG.findall(args)]
        ops.append((name, vals, qs))
    return nq, ops, meas, nc


def probabilities(qasm):
    """理想测量概率 {经典位串: 概率}，最右一位是 c[0]；概率极小（<1e-12）的键省略。"""
    nq, ops, meas, nc = parse(qasm)
    st = State(nq)
    for name, a, qs in ops:
        m = _single(name, a)
        if m is not None and len(qs) == 1:
            st.apply1(m, qs[0])
        elif name in ('cx', 'CX'):
            st.controlled1(_single('x', []), [qs[0]], qs[1])
        elif name == 'cy':
            st.controlled1(_single('y', []), [qs[0]], qs[1])
        elif name == 'cz':
            st.controlled1(_single('z', []), [qs[0]], qs[1])
        elif name in ('cp', 'cu1'):
            st.controlled1(_single('p', a), [qs[0]], qs[1])
        elif name == 'crz':
            st.controlled1(_single('rz', a), [qs[0]], qs[1])
        elif name == 'ccx':
            st.controlled1(_single('x', []), [qs[0], qs[1]], qs[2])
        elif name == 'swap':
            st.swap(qs[0], qs[1])
        else:
            raise ValueError('本地模拟器不支持的门: %s' % name)
    out = {}
    for i, amp in enumerate(st.amp):
        p = abs(amp) ** 2
        if p < 1e-15:
            continue
        key = ''.join('1' if (i >> meas[c]) & 1 else '0' if c in meas else '0' for c in range(nc - 1, -1, -1))
        out[key] = out.get(key, 0.0) + p
    return {k: v for k, v in sorted(out.items()) if v > 1e-12}


if __name__ == '__main__':
    import json
    import sys
    print(json.dumps(probabilities(sys.stdin.read()), indent=2))
