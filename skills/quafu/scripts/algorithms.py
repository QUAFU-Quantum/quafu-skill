# -*- coding: utf-8 -*-
"""内置算法模板：每个模板给出线路、理想结果和「怎么算成功」。

每个模板是一个 dict：
  name        命令行里用的名字
  title       中文名
  idea        一句话讲它在干什么（给普通人）
  qubits      用到几个比特
  circuits    几条线路（一次提交里的任务数）
  targets     推荐目标，按优先级
  expect      预期结果（人话）
  build(**p)  返回 [(标签 dict, qasm), ...]
  params      可调参数及默认值
所有线路都是「逻辑线路」：交给平台时用默认编译（compiler="qiskit"），平台会自己挑物理比特、换成本机门。
"""
import math

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'


def _qasm(nq, nc, body, meas):
    lines = [HEAD + 'qreg q[%d];\ncreg c[%d];' % (nq, nc)]
    lines += body
    lines += ['measure q[%d] -> c[%d];' % (q, c) for q, c in meas]
    return '\n'.join(lines) + '\n'


def _f(x):
    return repr(round(float(x), 12))


# ── 1. 贝尔态 ─────────────────────────────────────────────────────

def bell():
    return [({}, _qasm(2, 2, ['h q[0];', 'cx q[0],q[1];'], [(0, 0), (1, 1)]))]


# ── 2. GHZ 态 ─────────────────────────────────────────────────────

def ghz(n=3):
    n = int(n)
    body = ['h q[0];'] + ['cx q[%d],q[%d];' % (i, i + 1) for i in range(n - 1)]
    return [({'n': n}, _qasm(n, n, body, [(i, i) for i in range(n)]))]


# ── 3. 量子随机数 ─────────────────────────────────────────────────

def qrng(n=1):
    n = int(n)
    return [({'n': n}, _qasm(n, n, ['h q[%d];' % i for i in range(n)], [(i, i) for i in range(n)]))]


# ── 4. 量子硬币：转一个角度再看正反面 ───────────────────────────────

def rotation(points=9):
    """ry(θ) 后测量；理想 P(1) = sin²(θ/2)。单比特，适合只开放单比特线路的真机。"""
    pts = int(points)
    out = []
    for k in range(pts):
        th = math.pi * k / (pts - 1) if pts > 1 else 0.0
        out.append(({'theta': th}, _qasm(1, 1, ['ry(%s) q[0];' % _f(th)], [(0, 0)])))
    return out


# ── 5. Deutsch-Jozsa ──────────────────────────────────────────────

def deutsch_jozsa(oracle='balanced', n=3):
    """n 个输入比特 + 1 个辅助比特。常数函数 → 输入全测到 0；平衡函数 → 一定不全是 0。
    balanced 用 f(x)=x0⊕x1⊕…（每个输入比特 CNOT 到辅助比特），理想结果是全 1。"""
    n = int(n)
    a = n
    body = ['x q[%d];' % a] + ['h q[%d];' % i for i in range(n + 1)]
    if oracle == 'balanced':
        body += ['cx q[%d],q[%d];' % (i, a) for i in range(n)]
    elif oracle == 'constant1':
        body += ['x q[%d];' % a]
    elif oracle != 'constant':
        raise ValueError('oracle 只能是 balanced / constant / constant1')
    body += ['h q[%d];' % i for i in range(n)]
    return [({'oracle': oracle, 'n': n}, _qasm(n + 1, n, body, [(i, i) for i in range(n)]))]


# ── 6. Bernstein-Vazirani ─────────────────────────────────────────

def bernstein_vazirani(secret='101'):
    """一次查询读出暗号 secret。secret 按结果的写法给：最右一位对应 c[0]。"""
    s = str(secret)
    if not s or set(s) - {'0', '1'}:
        raise ValueError('secret 只能由 0/1 组成')
    n = len(s)
    a = n
    body = ['x q[%d];' % a] + ['h q[%d];' % i for i in range(n + 1)]
    body += ['cx q[%d],q[%d];' % (i, a) for i in range(n) if s[n - 1 - i] == '1']
    body += ['h q[%d];' % i for i in range(n)]
    return [({'secret': s}, _qasm(n + 1, n, body, [(i, i) for i in range(n)]))]


# ── 7. Grover 搜索 ────────────────────────────────────────────────

def _flip_zeros(target, n):
    return ['x q[%d];' % i for i in range(n) if target[n - 1 - i] == '0']


def _mcz(n):
    if n == 2:
        return ['cz q[0],q[1];']
    if n == 3:
        return ['h q[2];', 'ccx q[0],q[1],q[2];', 'h q[2];']
    raise ValueError('只做 2 或 3 比特的 Grover')


def grover(marked='11'):
    """在 2^n 个答案里找被标记的那一个。2 比特迭代 1 次理想 100%；3 比特迭代 2 次理想约 94.5%。"""
    m = str(marked)
    n = len(m)
    if n not in (2, 3) or set(m) - {'0', '1'}:
        raise ValueError('marked 要是 2 或 3 位的 0/1 串')
    rounds = 1 if n == 2 else 2
    body = ['h q[%d];' % i for i in range(n)]
    for _ in range(rounds):
        body += _flip_zeros(m, n) + _mcz(n) + _flip_zeros(m, n)          # 给答案打上负号
        body += ['h q[%d];' % i for i in range(n)] + ['x q[%d];' % i for i in range(n)]
        body += _mcz(n)                                                    # 关于平均值翻转
        body += ['x q[%d];' % i for i in range(n)] + ['h q[%d];' % i for i in range(n)]
    return [({'marked': m, 'rounds': rounds}, _qasm(n, n, body, [(i, i) for i in range(n)]))]


# ── 8. 量子隐形传态 ───────────────────────────────────────────────

def teleport(theta=math.pi / 3):
    """把 q0 上 ry(θ) 准备的状态传到 q2。用「延迟测量」写法：经典控制换成 CNOT/CZ，所以真机也能跑。
    只测 q2：理想 P(1) = sin²(θ/2)，θ=π/3 时是 0.25，和直接在 q2 上准备完全一样。"""
    th = float(theta)
    body = ['ry(%s) q[0];' % _f(th),
            'h q[1];', 'cx q[1],q[2];',          # 1、2 号比特先纠缠成一对
            'cx q[0],q[1];', 'h q[0];',          # 发送方的贝尔测量（不真的测）
            'cx q[1],q[2];', 'cz q[0],q[2];']    # 接收方按「测量结果」纠正
    return [({'theta': th}, _qasm(3, 1, body, [(2, 0)]))]


# ── 9. VQE：氢分子基态能量 ────────────────────────────────────────

# 氢分子在键长 0.735 Å、STO-3G 基组、宇称映射约化到 2 比特后的哈密顿量（单位 Hartree）。
# 'ZI' 写法里最右一个字母作用在 q0。核排斥能另加。
H2 = {'II': -1.052373245772859, 'IZ': 0.39793742484318045, 'ZI': -0.39793742484318045,
      'ZZ': -0.01128010425623538, 'XX': 0.18093119978423156}
H2_NUCLEAR = 0.7199689944489797
H2_EXACT_TOTAL = -1.857275030202381 + H2_NUCLEAR    # 精确对角化得到的基态总能量 ≈ -1.13731 Ha


def vqe_h2(points=9):
    """单参数试探态 cos(θ/2)|10⟩ + sin(θ/2)|01⟩，扫 θ；每个 θ 交两条线路：Z 基测量和 X 基测量。
    能量 E(θ) 一定是 a + b·cosθ + c·sinθ 的形状，所以扫几个点就能拟合出最低点。"""
    pts = int(points)
    out = []
    for k in range(pts):
        th = 2 * math.pi * k / pts
        prep = ['ry(%s) q[0];' % _f(th), 'x q[1];', 'cx q[0],q[1];']
        out.append(({'theta': th, 'basis': 'Z'}, _qasm(2, 2, prep, [(0, 0), (1, 1)])))
        out.append(({'theta': th, 'basis': 'X'}, _qasm(2, 2, prep + ['h q[0];', 'h q[1];'], [(0, 0), (1, 1)])))
    return out


# ── 10. QAOA：4 个点围成一圈的最大割 ──────────────────────────────

RING4 = [(0, 1), (1, 2), (2, 3), (3, 0)]


def cut_value(bits, edges=RING4):
    """bits 是结果位串（最右一位是 c[0]=节点 0）。"""
    n = len(bits)
    return sum(1 for i, j in edges if bits[n - 1 - i] != bits[n - 1 - j])


def qaoa_maxcut(grid=4):
    """p=1 的 QAOA，扫 (γ, β) 网格。默认 4×4 网格含理想最好点 γ=3π/8、β=π/8，那里平均割值正好是 3（最大割是 4）。"""
    g = int(grid)
    out = []
    for i in range(g):
        gamma = math.pi / 2 * (i + 1) / g
        for j in range(g):
            beta = math.pi / 4 * (j + 1) / g
            body = ['h q[%d];' % k for k in range(4)]
            for a, b in RING4:
                body += ['cx q[%d],q[%d];' % (a, b), 'rz(%s) q[%d];' % (_f(2 * gamma), b), 'cx q[%d],q[%d];' % (a, b)]
            body += ['rx(%s) q[%d];' % (_f(2 * beta), k) for k in range(4)]
            out.append(({'gamma': gamma, 'beta': beta}, _qasm(4, 4, body, [(k, k) for k in range(4)])))
    return out


TEMPLATES = {
    'bell': dict(
        title='贝尔态（两枚纠缠的硬币）', build=bell, params={}, qubits=2, circuits=1,
        targets=['sim', 'Shenglian', 'Baihua'],
        idea='让两个比特纠缠：单看每个都是随机的，但两个总是一样。',
        expect='理想只出现 00 和 11，各约一半；真机上 01、10 会因噪声和读出误差占百分之几到十几。',
        kind='distribution'),
    'ghz': dict(
        title='GHZ 态（多比特纠缠）', build=ghz, params={'n': 3}, qubits=3, circuits=1,
        targets=['sim', 'Shenglian', 'Baihua'],
        idea='把贝尔态推广到 n 个比特：要么全 0，要么全 1。',
        expect='理想只出现全 0 和全 1；比特越多，真机上「混进来的杂项」越多。',
        kind='distribution'),
    'qrng': dict(
        title='量子随机数', build=qrng, params={'n': 1}, qubits=1, circuits=1,
        targets=['sim', 'Dongling', 'Shenglian'],
        idea='让比特处在 0 和 1 的等量叠加，再测量：每次结果由量子测量决定，没人能预测。',
        expect='0 和 1 各约一半；每次运行给出 shots 个随机比特。真机上会有一两个百分点的偏向（读出误差）。',
        kind='qrng'),
    'rotation': dict(
        title='量子硬币转角度（单比特旋转扫描）', build=rotation, params={'points': 9}, qubits=1, circuits=9,
        targets=['sim', 'Dongling', 'Shenglian'],
        idea='把比特绕一个轴转 θ 角再测：转得越多，测到 1 的概率越大，画出来是一条正弦曲线。',
        expect='理想 P(1)=sin²(θ/2)，从 0 平滑升到 1；真机曲线形状对但两端到不了 0 和 1。',
        kind='rotation'),
    'deutsch-jozsa': dict(
        title='Deutsch-Jozsa（一次看出函数是常数还是平衡）', build=deutsch_jozsa,
        params={'oracle': 'balanced', 'n': 3}, qubits=4, circuits=1,
        targets=['sim', 'Shenglian-sim', 'Shenglian'],
        idea='一个黑盒函数要么永远输出同一个值，要么一半 0 一半 1。经典上最坏要问很多次，这里问一次就知道。',
        expect='oracle=constant 时理想全测到 000；balanced 时理想测到 111（只要不是 000 就判为平衡）。',
        kind='distribution'),
    'bernstein-vazirani': dict(
        title='Bernstein-Vazirani（一次读出暗号）', build=bernstein_vazirani,
        params={'secret': '101'}, qubits=4, circuits=1,
        targets=['sim', 'Shenglian-sim', 'Shenglian'],
        idea='黑盒里藏着一串 0/1 暗号。经典上要问 n 次，量子一次就把整串读出来。',
        expect='理想 100% 测到暗号本身（默认 101）。',
        kind='distribution'),
    'grover': dict(
        title='Grover 搜索（2–3 比特）', build=grover, params={'marked': '11'}, qubits=2, circuits=1,
        targets=['sim', 'Shenglian-sim', 'Shenglian'],
        idea='在一堆答案里找被标记的那个：量子版通过「放大」正确答案的概率来找。',
        expect='2 比特（marked 两位）理想 100% 找到；3 比特（marked 三位）理想约 94.5%。真机上 3 比特版噪声较大。',
        kind='distribution'),
    'teleport': dict(
        title='量子隐形传态', build=teleport, params={'theta': math.pi / 3}, qubits=3, circuits=1,
        targets=['sim', 'Shenglian-sim', 'Shenglian'],
        idea='借助一对纠缠比特，把一个比特的状态「搬」到另一个比特上，原来的那个不再保留。',
        expect='只测接收方 q2：理想 P(1)=sin²(θ/2)，默认 θ=π/3 时 0.25。',
        kind='distribution'),
    'vqe-h2': dict(
        title='VQE：算氢分子的基态能量', build=vqe_h2, params={'points': 9}, qubits=2, circuits=18,
        targets=['sim', 'Shenglian-sim', 'Baihua-sim'],
        idea='用量子线路准备一族候选状态，测它们的能量，找最低的那个——这是量子化学最常见的入门算法。',
        expect='理想最低能量约 -1.137 Ha（精确值 -1.13731）；带噪模拟会偏高几十毫 Ha。',
        kind='vqe'),
    'qaoa-maxcut': dict(
        title='QAOA：四点环的最大割', build=qaoa_maxcut, params={'grid': 4}, qubits=4, circuits=16,
        targets=['sim', 'Shenglian-sim', 'Baihua-sim'],
        idea='把 4 个点分成两组，让跨组的连线尽量多。QAOA 用两个旋转角度调出好答案的概率。',
        expect='最大割是 4（0101 或 1010）；p=1 理想最好点平均割值 3.0（γ=3π/8、β=π/8）。',
        kind='qaoa'),
}


def build(name, **params):
    t = TEMPLATES[name]
    p = dict(t['params'])
    p.update({k: v for k, v in params.items() if v is not None})
    return t['build'](**p), p
