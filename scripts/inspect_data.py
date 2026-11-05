#!/usr/bin/env python3
"""Что показывает:
    - количество записей,
    - список ключей в первой записи,
    - пример записи (первые 2 уровня вложенности),
    - пустые/None поля в первой записи (для быстрой оценки качества).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DEMO = PROJECT_ROOT / "data" / "catalog"


def _walk(obj, depth: int, max_depth: int = 2) -> None:
    """Печатает структуру объекта до max_depth."""
    pad = "  " * depth
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and depth < max_depth:
                print(f"{pad}{k}:")
                _walk(v, depth + 1, max_depth)
            else:
                val = "None" if v is None else repr(v)[:60]
                print(f"{pad}{k}: {val}")
    elif isinstance(obj, list):
        print(f"{pad}[{len(obj)} items]")
        if obj:
            _walk(obj[0], depth + 1, max_depth)


def inspect_file(path: Path) -> None:
    print("=" * 68)
    print(path.name)
    print("=" * 68)
    if not path.exists():
        print("  файл отсутствует")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  ошибка чтения: {exc}")
        return

    if not isinstance(data, list):
        print(f"  ожидался list, получено {type(data).__name__}")
        return

    print(f"  записей: {len(data)}")
    if not data:
        return

    sample = data[0]
    print(f"  ключей в первой записи: {len(sample)}")
    print(f"  поля (2 уровня):")
    _walk(sample, depth=2)

    none_fields = [k for k, v in sample.items() if v is None]
    if none_fields:
        print(f"  None в первой записи: {none_fields}")


def main() -> int:
    if len(sys.argv) > 1:
        targets = [DATA_DEMO / sys.argv[1]]
    else:
        targets = sorted(DATA_DEMO.glob("*.json"))

    if not targets:
        print(f"Нет JSON в {DATA_DEMO}")
        return 1

    for p in targets:
        inspect_file(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
