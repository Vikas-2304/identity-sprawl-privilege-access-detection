"""Minimal pandas compatibility layer for the backend.

The project only uses a small slice of pandas functionality for CSV loading,
simple filtering, grouping, and a handful of Series operations. This module
implements that surface area with the standard library so the backend can run
in environments where binary pandas wheels are unavailable.
"""

from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator


def isna(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        return math.isnan(value)
    return False


def to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None:
        raise ValueError("Cannot parse None as datetime")
    text = str(value).strip()
    if not text:
        raise ValueError("Cannot parse empty string as datetime")
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported datetime format: {value!r}")


class _StringMethods:
    def __init__(self, series: "Series"):
        self._series = series

    def lower(self) -> "Series":
        return Series(["" if value is None else str(value).lower() for value in self._series._data], name=self._series.name)

    def contains(self, needle: str) -> "Series":
        needle = str(needle)
        return Series([needle in ("" if value is None else str(value)) for value in self._series._data], name=self._series.name)


class Series:
    def __init__(self, data: Iterable[Any], name: str | None = None):
        self._data = list(data)
        self.name = name

    @property
    def empty(self) -> bool:
        return len(self._data) == 0

    @property
    def str(self) -> _StringMethods:
        return _StringMethods(self)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, item: int) -> Any:
        return self._data[item]

    def __repr__(self) -> str:
        return f"Series({self._data!r})"

    def _binary_op(self, other: Any, op: Callable[[Any, Any], Any]) -> "Series":
        if isinstance(other, Series):
            return Series([op(left, right) for left, right in zip(self._data, other._data)], name=self.name)
        return Series([op(value, other) for value in self._data], name=self.name)

    def __eq__(self, other: Any) -> "Series":
        return self._binary_op(other, lambda left, right: left == right)

    def __ne__(self, other: Any) -> "Series":
        return self._binary_op(other, lambda left, right: left != right)

    def __or__(self, other: Any) -> "Series":
        return self._binary_op(other, lambda left, right: bool(left) or bool(right))

    def __and__(self, other: Any) -> "Series":
        return self._binary_op(other, lambda left, right: bool(left) and bool(right))

    def sum(self) -> Any:
        values = [value for value in self._data if not isna(value)]
        return sum(values) if values else 0

    def max(self) -> Any:
        values = [value for value in self._data if not isna(value)]
        return max(values) if values else None

    def nunique(self) -> int:
        return len({value for value in self._data if not isna(value)})

    def value_counts(self) -> "ValueCountsResult":
        return ValueCountsResult(Counter(self._data))

    def tolist(self) -> list[Any]:
        return list(self._data)

    def head(self, n: int = 5) -> "Series":
        return Series(self._data[:n], name=self.name)

    def apply(self, func: Callable[[Any], Any]) -> "Series":
        return Series([func(value) for value in self._data], name=self.name)

    def astype(self, _type: Any) -> "Series":
        if _type is object:
            return Series(list(self._data), name=self.name)
        return Series([_type(value) if not isna(value) else None for value in self._data], name=self.name)

    def where(self, condition: Iterable[bool], other: Any) -> "Series":
        mask = list(condition)
        return Series([value if keep else other for value, keep in zip(self._data, mask)], name=self.name)

    def fillna(self, value: Any) -> "Series":
        return Series([value if isna(item) else item for item in self._data], name=self.name)

    def notna(self) -> "Series":
        return Series([not isna(item) for item in self._data], name=self.name)


class _ILoc:
    def __init__(self, frame: "DataFrame"):
        self._frame = frame

    def __getitem__(self, index: int) -> dict[str, Any]:
        return dict(self._frame._rows[index])


class ValueCountsResult(dict):
    def __init__(self, counts: Counter):
        super().__init__(counts)

    def to_dict(self) -> dict[str, Any]:
        return dict(self)


class _GroupBy:
    def __init__(self, frame: "DataFrame", key: str):
        self._frame = frame
        self._key = key
        self._groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for row in frame._rows:
            self._groups[row.get(key)].append(dict(row))

    def __iter__(self) -> Iterator[tuple[Any, "DataFrame"]]:
        for group_key, rows in self._groups.items():
            yield group_key, DataFrame(rows)


class DataFrame:
    def __init__(self, data: Iterable[dict[str, Any]] | dict[str, Iterable[Any]] | None = None):
        self._index_name: str | None = None
        self._index_values: list[Any] | None = None
        if data is None:
            self._rows: list[dict[str, Any]] = []
        elif isinstance(data, dict):
            keys = list(data.keys())
            values = [list(column) for column in data.values()]
            row_count = max((len(column) for column in values), default=0)
            self._rows = []
            for index in range(row_count):
                row = {}
                for key, column in zip(keys, values):
                    row[key] = column[index] if index < len(column) else None
                self._rows.append(row)
        else:
            self._rows = [dict(row) for row in data]

    @property
    def empty(self) -> bool:
        return len(self._rows) == 0

    @property
    def iloc(self) -> _ILoc:
        return _ILoc(self)

    @property
    def columns(self) -> list[str]:
        names: list[str] = []
        for row in self._rows:
            for key in row.keys():
                if key not in names:
                    names.append(key)
        return names

    def __len__(self) -> int:
        return len(self._rows)

    def __contains__(self, key: str) -> bool:
        return key in self.columns

    def __getitem__(self, key: str | Series | list[bool]) -> Any:
        if isinstance(key, str):
            return Series([row.get(key) for row in self._rows], name=key)
        if isinstance(key, Series):
            key = list(key)
        if isinstance(key, list) and key and all(isinstance(item, bool) for item in key):
            filtered = [row for row, keep in zip(self._rows, key) if keep]
            result = DataFrame(filtered)
            result._index_name = self._index_name
            result._index_values = self._index_values
            return result
        raise TypeError(f"Unsupported DataFrame indexer: {type(key)!r}")

    def __setitem__(self, key: str, value: Any) -> None:
        if isinstance(value, Series):
            values = list(value)
        elif isinstance(value, list):
            values = value
        else:
            values = [value] * len(self._rows)
        for index, row in enumerate(self._rows):
            row[key] = values[index] if index < len(values) else None

    def get(self, key: str, default: Any = None) -> Any:
        if key in self:
            return self[key]
        if default is None:
            return None
        return Series([default] * len(self._rows), name=key)

    def iterrows(self) -> Iterator[tuple[int, dict[str, Any]]]:
        for index, row in enumerate(self._rows):
            yield index, dict(row)

    def fillna(self, value: Any) -> "DataFrame":
        return DataFrame([
            {key: value if isna(item) else item for key, item in row.items()}
            for row in self._rows
        ])

    def groupby(self, key: str) -> _GroupBy:
        return _GroupBy(self, key)

    def sort_values(self, by: str, ascending: bool = True) -> "DataFrame":
        rows = sorted(
            self._rows,
            key=lambda row: (row.get(by) is None, row.get(by)),
            reverse=not ascending,
        )
        result = DataFrame(rows)
        result._index_name = self._index_name
        result._index_values = self._index_values
        return result

    def reset_index(self, drop: bool = False) -> "DataFrame":
        result = DataFrame(self._rows)
        if not drop and self._index_name and self._index_values is not None:
            for row, index_value in zip(result._rows, self._index_values):
                row[self._index_name] = index_value
        return result

    def head(self, n: int = 5) -> "DataFrame":
        result = DataFrame(self._rows[:n])
        result._index_name = self._index_name
        result._index_values = self._index_values[:n] if self._index_values is not None else None
        return result

    def set_index(self, key: str) -> "DataFrame":
        result = DataFrame(self._rows)
        result._index_name = key
        result._index_values = [row.get(key) for row in result._rows]
        return result

    def to_dict(self, orient: str = "dict") -> Any:
        if orient == "records":
            return [dict(row) for row in self._rows]
        if orient == "index":
            if self._index_name is None:
                return {index: dict(row) for index, row in enumerate(self._rows)}
            return {
                index_value: dict(row)
                for index_value, row in zip(self._index_values or [], self._rows)
            }
        raise ValueError(f"Unsupported orient: {orient!r}")

    def __repr__(self) -> str:
        return f"DataFrame({self._rows!r})"


def concat(frames: Iterable[DataFrame], ignore_index: bool = False) -> DataFrame:
    rows: list[dict[str, Any]] = []
    for frame in frames:
        rows.extend(dict(row) for row in frame._rows)
    return DataFrame(rows)


def read_csv(path: str | Path, dtype: Any = None) -> DataFrame:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, Any]] = []
        for raw_row in reader:
            row: dict[str, Any] = {}
            for key, value in raw_row.items():
                if value is None:
                    row[key] = ""
                elif dtype is str:
                    row[key] = str(value)
                else:
                    row[key] = value
            rows.append(row)
    return DataFrame(rows)