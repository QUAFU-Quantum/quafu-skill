# 写能在 QUAFU 上跑的线路

## 格式

OpenQASM 2.0 文本，或 Qiskit 的 `QuantumCircuit`（要 `pip install "quafu-sdk[qiskit]"`，带参数的先 `assign_parameters` 绑定）。

```
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
```

## 规矩

1. **写逻辑线路，只声明用到的比特。** 默认 `compiler="qiskit"`：平台替你挑物理比特、把门换成真机的本机门（`h, rx, ry, rz, cz`）、按连通关系插 SWAP。结果里的 `executed_qasm` 是实际上机的线路，`measurements` 告诉你每个经典位测的是哪个物理比特。
2. **测量放最后，按经典位从小到大写。** 真机不支持测量后再做门、不支持按测量结果做条件操作（`if`）。要「测了再根据结果纠正」的算法（如隐形传态），改写成延迟测量：把经典控制换成受控门（见模板 `teleport`）。
3. **位序**：计数的键是经典位串，**最右一位是 `c[0]`**（和 Qiskit 一样）。`'01'` 表示 c[0]=1、c[1]=0。向用户展示时说清楚，或用 `r.reorder('c0_leftmost')` 换过来。
4. **门**：`qelib1.inc` 里的常用门都能用：`x y z h s sdg t tdg sx rx ry rz p u1 u2 u3 cx cz cy swap ccx cp/cu1 crz` 等。角度可以写 `pi/2` 这类表达式。本 skill 的本地模拟器 `scripts/qfsim.py` 支持这些门，可以先算理想结果。
5. **参数扫描**：模板里写 `{{theta}}`，用 `quafu.sweep(template, parameters=[("theta","rad")], points=[...], target=...)`，平台逐点代入，一个点一条任务；或者像 `qf.py` 那样本地代入后一次提交一组线路。
6. `compiler="none"` 只给已经按某台真机物理编号写好的线路用，一般用户不需要。

## 真机上什么能跑好

真机的误差主要来自三处：双比特门（每个约 1%–5% 出错）、读出（每个比特把 0/1 看错约 2%–10%）、比特在线路运行中逐渐丢失状态（退相干，线路越深越严重）。所以：

| 线路规模 | 真机上的样子 |
|---|---|
| 1 个比特、几个单比特门 | 很接近理想，误差几个百分点，主要是读出 |
| 2–3 个比特、几个双比特门 | 能清楚看出算法效果，正确答案占 70%–90% |
| 4–5 个比特、十几个双比特门 | 正确答案还常是最多的那个，但只占三四成 |
| 更多 | 基本被噪声淹没，接近随机 |

真机还会被编译器插入 SWAP（比特不相邻时），实际双比特门数比你写的多。`qf devices` 的「可用双比特连接」为 0 的真机只能跑单比特线路。

## 用 Qiskit 写

```python
from qiskit import QuantumCircuit
import quafu
qc = QuantumCircuit(2, 2); qc.h(0); qc.cx(0, 1); qc.measure([0, 1], [0, 1])
job = quafu.submit(qc, target="sim", shots=1024)
```

也可以用 `from quafu.qiskit import QuafuProvider`，`QuafuProvider().get_backend("Shenglian").run(transpile(qc, backend))`，后端的门集和拓扑来自平台。
