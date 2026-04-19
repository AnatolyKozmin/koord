from typing import Any

from pydantic import BaseModel


class WriteQueueRequest(BaseModel):
    """Диапазон в нотации A1, например 'Domashki!D5' или 'Лист1!A1:B2'."""

    range_a1: str
    values: list[list[Any]]


class BatchRangeUpdate(BaseModel):
    range_a1: str
    values: list[list[Any]]


class WriteBatchQueueRequest(BaseModel):
    """Несколько диапазонов за один вызов values.batchUpdate (одна задача в очереди)."""

    updates: list[BatchRangeUpdate]
