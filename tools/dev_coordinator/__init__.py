"""Deterministic Coordinator v0.1 для agent-bridge.

Это НЕ ИИ-агент. Программа только:
1) читает состояние bridge;
2) решает, можно ли запускать Executor;
3) в режиме launch запускает Cursor ровно один раз;
4) наблюдает exit code и останавливается.

Архитектурные решения Coordinator не принимает.
"""

__version__ = "0.1.0"
