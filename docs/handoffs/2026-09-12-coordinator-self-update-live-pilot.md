# Coordinator Self-Update — Live Pilot

Date: 2026-09-12

This is a docs-only commissioning marker for the reviewed persistent Coordinator self-updater.

- Base transition head before pilot: `7b9191048e7c933d2e6f8ef9e55a1236b389ec07`.
- Purpose: after the workstation self-updater is activated, merging this pilot PR creates a harmless new transition head that the updater must fetch and fast-forward to automatically, then restart the persistent runner.
- This pilot does not authorize or change AI Core runtime, provider routing, consumers, deployment, release, or platform governance.
- After the local updater proves automatic advancement to the pilot merge head, Architect will publish one harmless `coord/bridge/*` package to verify the restarted persistent runner still completes an end-to-end package automatically.
- This is a commissioning artifact allowed by the transition freeze in issue #12; it is not a new Coordinator feature.
