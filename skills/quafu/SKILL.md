---
name: quafu
description: 在 QUAFU 量子计算云平台（quafu.com.cn）上替用户写并运行量子程序：引导注册与网页登录（不用手抄 token）、挑选或编写量子线路（贝尔态、GHZ、Deutsch-Jozsa、Bernstein-Vazirani、Grover、量子随机数、隐形传态、VQE、QAOA 等内置模板）、提交到模拟器或超导量子真机（Baihua、Shenglian、Dongling 等）、异步等待并取回结果、与理想结果对比并用大白话解释噪声、把结果做成好看的本地网页。用户提到 QUAFU、夸父、量子计算、量子线路、量子程序、量子真机、跑个量子算法、quafu-sdk 时使用。Use when the user wants to write or run quantum circuits on the QUAFU quantum cloud (quafu.com.cn), log in to QUAFU, check quantum devices, fetch QUAFU job results, or visualize quantum measurement results.
---

# QUAFU：在真实的量子计算机上跑程序

QUAFU 是北京量子信息科学研究院的量子计算云平台（<https://quafu.com.cn>），有理想模拟器、按真机校准数据的带噪模拟器，以及几台超导量子真机。用户多半是兴趣爱好者或别的领域的科研人员：**不追求量子优势，但要真能跑、结果要讲得明白、要好看**。

你的工作分六步，按顺序来；每步结束用一两句人话告诉用户做到哪了。

1. 准备环境 → 2. 登录 → 3. 选算法、写线路 → 4. 选目标、提交 → 5. 等结果 → 6. 分析并做成网页

本 skill 的目录记为 `SKILL_DIR`（就是这份 SKILL.md 所在的目录）。下文的 `qf` 指：

```bash
python "$SKILL_DIR/scripts/qf.py"      # Windows 上 python 可能叫 py
```

`qf.py` 是一个只依赖标准库和 `quafu-sdk` 的助手：列模板、本地算理想结果、提交、记账、退避等待、分析、生成网页。它把每次提交记在**当前目录**的 `quafu-runs/` 里，换个会话也能接着取。需要更细的控制时直接用 SDK（见 [references/sdk.md](references/sdk.md)）。

## 1. 准备环境

- 要 Python 3.9+ 和 `quafu-sdk`（运行时零依赖）。先查：`python -c "import quafu; print(quafu.__version__)"`。
- 没装就装。优先用 [uv](https://docs.astral.sh/uv/) 建一个干净的虚拟环境，因为 PyPI 上有个同名的旧包 `quafu` 会冲突：
  ```bash
  uv venv .venv && uv pip install --python .venv quafu-sdk     # 之后用 .venv 里的 python
  # 没有 uv：python -m venv .venv，再用 .venv 里的 pip install quafu-sdk
  ```
- `import quafu` 报「另一个包占用了 quafu 这个名字」：就是撞上了旧包，按上面新建虚拟环境，不要在原环境里卸来卸去。
- 用户电脑上没有 Python：请用户去 python.org 装 3.9 以上版本（Windows 勾选 Add to PATH），装好再继续。

## 2. 登录（网页授权，不碰 token）

先查是否已登录：`python -m quafu whoami`（装了命令行入口时也可以直接 `quafu whoami`）。显示账号和到期时间就跳到第 3 步。

没登录时：

1. 问用户有没有 QUAFU 账号。没有就请对方打开 <https://quafu.com.cn> 注册（邮箱验证码，一两分钟）。**游客身份不能授权 SDK**，必须是注册账号。
2. 由你在后台运行 `python -m quafu login`。它会自动用本机浏览器打开授权页，并打印一个链接（60 分钟内有效）。请用户：在网页上登录 → 核对应用是「QUAFU SDK」、设备是这台电脑 → 点「授权」。浏览器会自动跳回，命令随即结束。
   - 这条命令要等用户操作，**放后台跑**（Claude Code 用后台运行；其他工具用足够长的超时，比如 10 分钟），然后每隔二三十秒用 `python -m quafu whoami` 查一次，查到就继续。
   - 浏览器没自动打开：把命令输出里的链接原样发给用户，请对方在**这台电脑**的浏览器里打开。
3. 远程环境（SSH、容器、云端开发机）里浏览器跳不回来：请用户**自己在终端**运行 `python -m quafu login`（Claude Code 里可以在输入框敲 `! python -m quafu login`），授权后网页会显示一串授权码，请对方粘贴到**那个终端**里，不要贴到聊天里。
4. 服务器、定时任务、CI：用 API Key。请用户在网站个人中心创建（`qf_` 开头），自己设到环境变量 `QUAFU_API_KEY`。

铁律：**不要让用户把 token、API Key、授权码发到对话里；不要打印、保存或提交任何凭证。** 网页登录 90 天有效，SDK 自己保管在 `~/.quafu-sdk/`。登录细节与各种报错见 [references/login.md](references/login.md)。

## 3. 选算法、写线路

先问用户想看什么（或许已经说了）。没有想法时，按兴趣推荐：

| 用户想… | 推荐模板 | 比特 | 推荐目标 |
|---|---|---|---|
| 看看量子纠缠 | `bell`、`ghz` | 2、3 | sim → Shenglian 真机 |
| 要一串真随机数 / 第一次上真机 | `qrng`、`rotation` | 1 | sim → Dongling 或 Shenglian 真机 |
| 体会「量子比经典快」 | `deutsch-jozsa`、`bernstein-vazirani`、`grover` | 2–4 | sim → Shenglian-sim → Shenglian |
| 量子通信 | `teleport` | 3 | sim → Shenglian-sim |
| 量子化学 / 优化 | `vqe-h2`、`qaoa-maxcut` | 2、4 | sim → Shenglian-sim（多条线路，别上真机） |

`qf list` 列出全部模板（预期结果、可调参数）；`qf show <模板> [-p 参数=值]` 不联网打印线路和**理想结果**。每个模板在 QUAFU 上的真实运行结果见 [references/algorithms.md](references/algorithms.md)，向用户承诺效果前先看它。

用户想要模板以外的东西时，你自己写 OpenQASM 2.0 线路（或 Qiskit 线路），存成 `.qasm` 文件，然后：
- 先用 `qf show` 的同款本地模拟器算理想结果：`python "$SKILL_DIR/scripts/qfsim.py" < my.qasm`；
- 再 `qf run custom --qasm my.qasm --target sim`。

写线路的规矩（细节见 [references/circuits.md](references/circuits.md)）：写逻辑线路、只声明用到的比特、测量放最后且按经典位从小到大写；比特数越少、双比特门越少，真机上越好看。**真机上 3 个以上比特、十几个双比特门以后，结果基本会被噪声淹没**，事先告诉用户。

## 4. 选目标、提交

先 `qf devices` 看现状（状态、排队、可用双比特连接）。选法：

1. **永远先在 `sim`（理想模拟器）跑一遍**，确认线路是对的。几秒出结果，不消耗真机。
2. 想知道真机上大概什么样，用 `<真机名>-sim`（按那台真机校准数据的带噪模拟），还是几秒出结果。
3. 上真机：
   - 只挑 `online` 的；排队少的优先（Baihua 常年排上万条，别选它，除非用户点名）；
   - 「可用双比特连接」为 0 的真机（目前 Dongling 就是）**只能跑单比特线路**，`qf run` 会拦住；
   - 真机 shots 最少 1024、必须是 1024 的倍数；一次只交需要的线路数，别把扫几十个点的模板（VQE、QAOA）交到真机；
   - 每人每天有额度，超了普通额度会降到最低优先级排队（`quafu.stats()` 查）。

提交：`qf run <模板> --target <目标> [--shots 1024] [-p 参数=值]`。它会打印**任务组号**和预计等待时间，把这两样原样告诉用户，并说明「任务组号就是取件码，关掉对话也能用它取结果」。

## 5. 等结果（异步，先短后长）

真机要排队，结果可能几分钟到几小时才出来。按这个节奏，不要一次死等：

| 第几次取 | 命令 | 说明 |
|---|---|---|
| 模拟器 | `qf wait <号> --budget 120` | 通常几秒就完成 |
| 真机第 1 次 | `qf wait <号> --budget 60` | 排队短的话这次就好了 |
| 第 2 次 | `--budget 300` | 期间告诉用户排在第几、大概还要多久 |
| 第 3 次起 | `--budget 540`（不超过你的命令超时） | 累计超过 30 分钟就停下来 |

`qf wait` 没等到会以**退出码 3** 结束，并打印完成了几条——这不是错误，任务还在平台上。累计等了半小时还没好，或用户不想等：告诉用户任务组号和「之后回来说『取一下 QUAFU 结果』就行」，结束等待。支持后台任务的工具（如 Claude Code）可以把 `qf wait <号> --budget 7200` 放后台，完成后再分析。

**新会话里接着取**：先确认第 1 步的环境（`--refresh` 要联网、要装好 SDK），然后在当初提交的目录运行 `qf runs --refresh`，列出所有记过的任务组和状态，挑没取的 `qf wait`。用户只给了任务组号也行，`qf wait <号>` 照样能取（没有本地记录时只做通用分析）。

失败、超时、额度、被取消怎么处理见 [references/waiting.md](references/waiting.md)。

## 6. 分析并做成网页

1. `qf analyze <号>`：和理想结果对比，打印几句人话总结（真机还会查当次校准数据里被测比特的读出保真度，估算「光读出误差就会损失多少」）。完整数据存在 `quafu-runs/<号>.analysis.json`，你可以在它基础上用 Python 再算。
2. 用你自己的话向用户讲清楚三件事：**算法想得到什么、实际得到了什么、差别从哪来**。词汇与讲法见 [references/explain-results.md](references/explain-results.md)。不说「保真度」「退相干」这类词而不解释；数字给百分比；说清楚哪些偏差只是测量次数有限带来的统计起伏。
3. 做网页，用本地浏览器打开（**不要**只给静态图片、PDF 或让用户自己找文件）：
   - 先问一句用户喜欢什么风格（给三四个具体选项，比如「深色仪表盘 / 杂志排版 / 极简白底 / 活泼彩色」），没有偏好就用公认好看的克制设计；
   - 最快：`qf page <号>`（默认深浅自适应的仪器面板风格）或 `qf page <号> --template "$SKILL_DIR/assets/pages/paper.html"`（纸面排版风格）；它会生成自包含 HTML 并用默认浏览器打开；
   - 同一个模板跑了几次（理想模拟 / 带噪模拟 / 真机），用 `qf page <号1> <号2> [<号3>]` 放在一页对比，这是最能说明噪声的页面；
   - 用户想要别的风格或别的内容，就自己写：拿这两个参考实现改，或从头写，但**不能比参考实现粗糙**——要有大数字结论、带刻度和图例的图、悬停看数值、深浅色、手机不溢出。要求见 [references/visualization.md](references/visualization.md)：**单个 HTML 文件、离线能开、不连任何外部资源**，图是可悬停查看数值的 SVG/Canvas，深浅色都好看，手机上不溢出。**不要照搬 QUAFU 官网的视觉风格。**

## 不要做的事

- 不要编造结果。没跑完就说没跑完；结果和预期不符就照实说并分析原因。
- 不要替用户在真机上一次交很多条线路或很大的 shots；真机机时是大家共用的。
- 不要用旧的 `quafu` 包（pyquafu）的写法，也不要自己拼 HTTP 请求；一律用 `quafu-sdk`。
- 不要把凭证写进代码、日志、网页或对话。
