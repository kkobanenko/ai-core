# Agent bridge protocol

This directory is a persistent coordination channel between the repository
agent, ChatGPT, and the user.

1. `latest-report.md` is the current agent report for ChatGPT.
2. `next-prompt.md` is the current ChatGPT/user instruction to the agent.
3. After each iteration, archive the report as
   `reports/YYYY-MM-DD-<short-name>.md`.
4. Archive each received next prompt as
   `prompts/YYYY-MM-DD-<short-name>.md`.
5. Before a new large iteration, read `AGENTS.md`, `next-prompt.md`, and the
   relevant latest report/handoff.
6. Bridge files are coordination artifacts, not a source of governance truth.
7. If bridge content conflicts with `AGENTS.md`, an accepted platform-control
   decision, or immutable evidence, governance/evidence takes precedence and
   the conflict must be recorded in the next report.

Never store secrets, credentials, production payloads, private data, product
prompts, or domain content in this directory.
