from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .paths import history_path


@dataclass
class HistoryItem:
    title: str
    source_url: str
    selected_format: str
    output_path: str
    status: str
    date_time: str

    @classmethod
    def now(
        cls,
        title: str,
        source_url: str,
        selected_format: str,
        output_path: str,
        status: str,
    ) -> "HistoryItem":
        return cls(
            title=title,
            source_url=source_url,
            selected_format=selected_format,
            output_path=output_path,
            status=status,
            date_time=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        )


class HistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or history_path()

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def save_all(self, items: Iterable[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(list(items), indent=2), encoding="utf-8")

    def add(self, item: HistoryItem) -> list[dict]:
        items = self.load()
        items.insert(0, asdict(item))
        self.save_all(items[:200])
        return items[:200]

    def remove(self, index: int) -> list[dict]:
        items = self.load()
        if 0 <= index < len(items):
            items.pop(index)
            self.save_all(items)
        return items

    def clear(self) -> None:
        self.save_all([])

