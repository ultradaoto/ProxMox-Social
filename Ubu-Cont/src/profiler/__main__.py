"""
Profiler package entry point.

Allows running: python -m src.profiler <command>
"""

from .cli import main

if __name__ == '__main__':
    exit(main())
