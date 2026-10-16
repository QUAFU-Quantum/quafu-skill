# QUAFU Skill：让 AI agent 替你在量子计算机上跑程序

[English](README.en.md)

装上这个 skill 后，你可以在 Claude Code、Codex、OpenCode（含 Mimo Code）里直接说「帮我在量子计算机上做个贝尔态实验」，agent 会：

1. 引导你注册 [QUAFU 量子计算云平台](https://quafu.com.cn)，在网页上点一下「授权」完成登录——不用复制粘贴任何 token；
2. 替你写好量子线路（内置 10 个已在 QUAFU 上真跑通的经典小算法，也能按你的想法现写）；
3. 先在模拟器上验证，再按你的意愿交到超导量子真机；
4. 真机要排队时告诉你大概等多久，先短后长地去取结果；关掉对话也能凭任务组号接着取；
5. 用 Python 和理想结果对比，用大白话讲清楚噪声和读出误差；
6. 把结果做成一张好看、可交互、离线能开的网页，在你的浏览器里打开。

面向量子计算爱好者和其他领域的科研人员：不追求量子优势，但每个例子都必须真能跑。

## 为什么做

> 「我们的quafu在本地就可以编程，并且会引导在网页上直接登录就可以拿到sdk凭证，无需自己管理登录状态。既然这么方便，就很适合做成一个skill。你先做，并且这个项目应该取代以前的quafu-skill」
>
> 「取代旧 skill 的时候，完全不需要考虑旧 skill 的格式或模式，因为旧版做的时候本来就非常不好用。」
>
> 「这个 skill 做好以后，放在组织账号下（我原来那个夸父 skill 是在个人账号下的）。」
>
> —— Neo

这个仓库取代了原先个人账号下的旧 quafu-skill（已归档），从头按新平台和新 SDK（[`quafu-sdk`](https://github.com/QUAFU-Quantum/quafu-sdk)）重写，不沿用旧版的任何格式。

## 安装（各一行）

| 平台 | 命令 |
|---|---|
| Claude Code | `claude plugin install quafu --marketplace QUAFU-Quantum/quafu-skill` |
| Codex | `codex plugin marketplace add QUAFU-Quantum/quafu-skill && codex plugin add quafu@quafu` |
| OpenCode / Mimo Code | `npx skills add QUAFU-Quantum/quafu-skill -g -a opencode -y` |

- macOS、Linux、Windows PowerShell 写法相同（Windows PowerShell 5.1 把 `&&` 换成 `;`）。
- `npx skills` 需要 Node.js；它把 skill 放进 `~/.agents/skills/quafu`，OpenCode、Mimo Code、Codex 都会读这个目录。Windows 上建不了软链接时加 `--copy`。
- 不想用命令？把本仓库的 `skills/quafu/` 整个文件夹复制到 `~/.claude/skills/`（Claude Code）或 `~/.agents/skills/`（Codex、OpenCode、Mimo Code）下即可。
- 同一个工具里只用一种装法，否则会出现两个同名 skill（插件装的叫 `quafu:quafu`，复制或 `npx skills` 装的叫 `quafu`）。

装好后检查是否识别：

```bash
claude plugin list --json | grep '"quafu@quafu"'          # Claude Code
codex debug prompt-input | grep -- '- quafu:quafu:'       # Codex
opencode debug skill | grep '"quafu"'                      # OpenCode
mimo debug skill | grep '"quafu"'                          # Mimo Code
```

用之前还需要：Python 3.9 或以上（skill 会帮你装 `quafu-sdk`），以及一个 QUAFU 账号（没有的话 agent 会带你注册）。

## 用法

装好后直接用自然语言说，例如：

- 「用 QUAFU 做一个贝尔态实验，先模拟器再真机，结果做成网页」
- 「我想看看 Grover 搜索在真量子计算机上能不能找到答案」
- 「用 VQE 算一下氢分子的基态能量」
- 「帮我取一下昨天那个 QUAFU 任务的结果」

Claude Code 里也可以用 `/quafu:quafu` 显式调用。

## 内置算法与实测

2026-10-16 在 QUAFU 正式平台上真跑（每条线路 1024 次测量）：

| 模板 | 演示什么 | 比特 | 理想模拟器 | 带噪模拟 Baihua-sim | 真机 |
|---|---|---|---|---|---|
| `bell` | 纠缠 | 2 | 与理想一致 | 正确 95.4% | Shenglian 90.9% |
| `ghz` | 多比特纠缠 | 3 | 与理想一致 | 94.0% | — |
| `qrng` | 量子随机 | 1 | 1 占 48.5% | 50.9% | Dongling 1 占 55.0%（读出偏向） |
| `rotation` | 单比特旋转 | 1 | 对比度 1.00 | 0.98 | Dongling 0.79 |
| `deutsch-jozsa` | 一次判断常数/平衡 | 4 | 与理想一致 | 88.9% | — |
| `bernstein-vazirani` | 一次读出暗号 | 4 | 与理想一致 | 93.2% | Shenglian 86.4%，答案正确 |
| `grover` | 搜索（2 / 3 比特） | 2–3 | 100% / 93.8% | 94.8% / 51.1% | — |
| `teleport` | 隐形传态 | 3 | 与理想一致 | 保真度 0.999 | — |
| `vqe-h2` | 氢分子基态能量 | 2 | −1.1347 Ha（精确 −1.1373） | −1.1054 Ha | 只放模拟器 |
| `qaoa-maxcut` | 四点环最大割 | 4 | 平均割值 2.97（理想 3.0） | 2.72 | 只放模拟器 |

完整数字（含 Shenglian-sim、等待时间）见 [skills/quafu/references/algorithms.md](skills/quafu/references/algorithms.md)。

结果网页示例（下载后双击打开，离线可看）：[真机贝尔态](examples/bell-shenglian.html)、[贝尔态：理想 / 带噪 / 真机对比](examples/bell-compare.html)、[单比特旋转：理想 / 带噪 / 真机对比](examples/rotation-compare.html)、[VQE](examples/vqe-baihua-sim.html)、[QAOA](examples/qaoa-baihua-sim.html)。

## 仓库结构

```
skills/quafu/
  SKILL.md                 agent 读的主说明：六步流程
  references/              按需读取：登录、写线路、等结果、解读结果、可视化、SDK 速查、算法实测
  scripts/qf.py            助手命令：list / show / devices / run / wait / runs / analyze / page（单次或 2–3 次对比）
  scripts/algorithms.py    内置模板（线路 + 预期）
  scripts/qfsim.py         标准库写的小型理想模拟器，算「理想应该是什么」
  assets/pages/            两个自包含的结果网页参考实现（仪器面板 aurora、纸面 paper）
.claude-plugin/            Claude Code / Codex 插件清单
examples/                  用真实运行数据生成的结果网页
tests/test_offline.py      不联网的检查
tests/e2e.py               在 QUAFU 上真跑全部模板
docs/                      国产平台接入调研
```

## 开发

```bash
python -m unittest discover tests                    # 不联网
python tests/e2e.py --target sim                     # 真跑（需已登录 QUAFU）
python tests/e2e.py --target Shenglian bell          # 真机只挑一两个
claude plugin validate .                             # 插件清单
```

改了模板或分析逻辑，就重跑 e2e 并更新 `references/algorithms.md` 里的实测数字。每次发布改动都要把 `.claude-plugin/plugin.json` 的 `version` 加一——Claude Code 和 Codex 按版本号判断要不要更新，版本号不变，用户那边的 `plugin update` 不会拿到新内容。不要在任何文件里写凭证。

## 许可

MIT
