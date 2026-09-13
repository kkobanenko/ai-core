"""Deterministic Coordinator v0.2 для agent-bridge.

Это НЕ ИИ-агент. Программа:
1) читает состояние bridge;
2) решает, можно ли запускать Executor;
3) атомарно CLAIM identity + process lock;
4) запускает Cursor ровно один раз;
5) проверяет фактический git state (postconditions);
6) при успехе сам делает exact-path commit/push/verify;
7) останавливается.

Executor exit code 0 ≠ work-package success.
"""

__version__ = "0.2.1"
