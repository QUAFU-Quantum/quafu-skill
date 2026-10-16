# quafu-sdk 速查

完整手册：<https://quafu.com.cn/docs/sdk>。这里只列 agent 常用的；以 SDK 实际行为为准（`help(quafu.submit)` 等）。

```python
import quafu

quafu.whoami()                                   # 当前身份
quafu.devices()                                  # [{name, kind(real/sim), status, n_qubits, queue, limits}]
quafu.Client().metadata("Shenglian")             # 门集 basis_gates、可用连接 coupling_map、limits
quafu.device("Shenglian").calibration()          # 当前校准：.qubit(i)["t1_us"]、.measured_qubit(i)["readout_fidelity_0"]、.coupler(i,j)
quafu.stats()["quota"]["real"]                   # 今日额度：used / limit / hard_limit / degraded / resets_at

job = quafu.submit(qasm_or_list, target="sim", shots=1024, name="我的实验")   # 立即返回
job.id; job.status(); job.wait(timeout=60)       # 超时抛 quafu.Timeout，任务仍在平台上
r = job.result()                                 # 只有一条线路时；失败抛 JobFailed
rs = job.results()                               # 多条线路，按提交顺序；失败的 counts=None
job = quafu.job("任务组号")                      # 跨进程接回
job.cancel()

r.counts            # {'00': 517, '11': 507}，最右一位是 c[0]
r.probabilities()   # 按 shots_returned 归一化
r.measurements      # [{cbit, physical_qubit, virtual_qubit}]
r.executed_qasm     # 实际上机的线路
r.calibration_id    # 用了哪份校准数据 → quafu.calibration(id)
r.backend           # 实际执行的设备
r.expectation_z([0, 1])   # Z⊗Z 期望值
r.reorder("c0_leftmost")  # 换位序
```

扫参与迭代：

```python
job = quafu.sweep(template_with_{{theta}}, parameters=[("theta", "rad")], points=[0, 0.5, 1.0], target="sim")
job.table().expectation_z([0])

job = quafu.open_job("sim", template=template, parameters=[("theta", "rad")])
job.append(points=[[0.1]], iteration=0); job.wait(); job.results()[-1]; ...; job.close()
```

target 取值：`"sim"` 理想模拟器；`"<真机>"`；`"<真机>-sim"` 按该真机校准数据的带噪模拟；`"<真机>-sim-jiuding"` 按该真机编号与连通关系的理想模拟（最多 30 比特）；`"all-race"` / `"all-redispatch"` 让平台在真机间调度。

异常都继承 `quafu.QuafuError`：`NotLoggedIn`、`LoginFailed`、`LoginExpired`、`LoginRevoked`、`PrecheckError`、`QuotaError`、`DeviceUnavailable`、`JobFailed`、`JobCancelled`、`JobNotFound`、`Timeout`、`ServerUnavailable`。错误信息自带原因和下一步。

显示语言默认英文，`quafu.set_language('zh')` 或环境变量 `QUAFU_LANG=zh` 切中文。
