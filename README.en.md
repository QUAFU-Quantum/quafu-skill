# QUAFU Skill: let an AI agent run your programs on a quantum computer

[中文](README.md)

An agent skill for Claude Code, Codex and OpenCode (including Mimo Code). Once installed, ask your agent something like "run a Bell-state experiment on a quantum computer" and it will:

1. help you sign up for the [QUAFU quantum computing cloud](https://quafu.com.cn) and log in by clicking "Authorize" in your browser — no tokens to copy;
2. write the quantum circuit (10 built-in small algorithms that are verified to run on QUAFU, or a custom one);
3. check it on the ideal simulator, then submit it to a noisy simulator or a superconducting quantum device;
4. tell you roughly how long the device queue is, poll for the result with growing intervals, and resume from the job ID in a later session;
5. compare the result with the ideal one in Python and explain noise and readout error in plain words;
6. build a good-looking, interactive, offline HTML page of the result and open it in your browser.

The skill's instructions are written in Chinese; agents read them fine and answer in the user's language.

## Install (one line each)

| Agent | Command |
|---|---|
| Claude Code | `claude plugin install quafu --marketplace QUAFU-Quantum/quafu-skill` |
| Codex | `codex plugin marketplace add QUAFU-Quantum/quafu-skill && codex plugin add quafu@quafu` |
| OpenCode / Mimo Code | `npx skills add QUAFU-Quantum/quafu-skill -g -a opencode -y` |

Or copy `skills/quafu/` into `~/.claude/skills/` (Claude Code) or `~/.agents/skills/` (Codex, OpenCode, Mimo Code). Use one method per agent to avoid duplicate skills.

Requirements: Python 3.9+ (the skill installs [`quafu-sdk`](https://github.com/QUAFU-Quantum/quafu-sdk)) and a QUAFU account.

## Built-in algorithms

Bell state, GHZ, quantum random numbers, single-qubit rotation sweep, Deutsch-Jozsa, Bernstein-Vazirani, Grover (2–3 qubits), teleportation (deferred measurement), VQE for H2, and QAOA max-cut on a 4-node ring. Measured results from 2026-10-16 (ideal simulator, noisy simulators and real devices) are in [skills/quafu/references/algorithms.md](skills/quafu/references/algorithms.md).

## License

MIT
