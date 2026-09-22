from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    """Convert ORM rows, Pydantic models and dataclasses to JSON-safe data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump(mode="python"))
    if is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    columns = getattr(getattr(value, "__table__", None), "columns", None)
    if columns is not None:
        return {c.name: to_jsonable(getattr(value, c.name)) for c in columns}
    return str(value)


def dumps(value: Any) -> str:
    return json.dumps(to_jsonable(value), ensure_ascii=False, indent=2)
