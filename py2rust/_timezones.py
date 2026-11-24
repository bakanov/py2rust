"""Bounded TZif-based timezone primitives; appointment policies belong in Python."""

from __future__ import annotations

import datetime as dt
import io
import itertools
import re
import struct
from zoneinfo import ZoneInfo


def _zone(data: bytes) -> tuple[ZoneInfo, set[int]]:
    if not 44 <= len(data) <= 1048576:
        raise ValueError("TZif data must be 44 bytes..1 MiB")
    position, width, version = 0, 4, data[4]
    offsets: set[int] = set()
    if version not in (0, 50, 51):
        raise ValueError("expected TZif version 1, 2 or 3")
    for block in range(1 if version == 0 else 2):
        if data[position : position + 4] != b"TZif" or data[position + 4 : position + 5] != bytes([version]):
            raise ValueError("inconsistent TZif header")
        if position + 44 > len(data):
            raise ValueError("truncated TZif header")
        utc, standard, leaps, times, types, characters = struct.unpack_from(">6I", data, position + 20)
        if not (
            1 <= types <= 256
            and 1 <= characters <= 4096
            and times <= 20000
            and leaps == 0
            and utc in (0, types)
            and standard in (0, types)
        ):
            raise ValueError("unsupported TZif counts or leap-second table")
        size = times * (width + 1) + types * 6 + characters + utc + standard
        start = position + 44
        if start + size > len(data):
            raise ValueError("truncated TZif block")
        transitions = [
            int.from_bytes(data[start + index * width : start + (index + 1) * width], "big", signed=True)
            for index in range(times)
        ]
        if any(left >= right for left, right in itertools.pairwise(transitions)):
            raise ValueError("TZif transitions must increase strictly")
        indices = data[start + times * width : start + times * (width + 1)]
        if any(index >= types for index in indices):
            raise ValueError("invalid TZif transition type")
        table = start + times * (width + 1)
        names = data[table + types * 6 : table + types * 6 + characters]
        for index in range(types):
            offset, dst, abbreviation = struct.unpack_from(">iBB", data, table + index * 6)
            if not (
                -86400 < offset < 86400
                and dst in (0, 1)
                and abbreviation < len(names)
                and b"\0" in names[abbreviation:]
                and names.isascii()
            ):
                raise ValueError("invalid TZif local time type")
            designation = names[abbreviation:].split(b"\0", 1)[0]
            if not re.fullmatch(rb"[A-Za-z0-9+-]{3,7}", designation):
                raise ValueError("expected a 3..7-character TZif designation")
            offsets.add(offset)
        flags = data[table + types * 6 + characters : start + size]
        if any(flag not in (0, 1) for flag in flags):
            raise ValueError("invalid TZif indicator")
        if utc and any(flags[standard + index] and (not standard or not flags[index]) for index in range(types)):
            raise ValueError("UTC TZif indicators require standard indicators")
        position = start + size
        width = 8
    if version == 0 and position != len(data):
        raise ValueError("unexpected TZif trailing data")
    if version != 0 and not (data[position : position + 1] == b"\n" and data[-1:] == b"\n"):
        raise ValueError("invalid TZif footer")
    return ZoneInfo.from_file(io.BytesIO(data)), offsets


def _local(text: str) -> dt.datetime:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?", text):
        raise ValueError("expected local YYYY-MM-DDTHH:MM:SS with at most 6 fractional digits")
    return dt.datetime.fromisoformat(text)


def _view(zone: ZoneInfo, value: dt.datetime) -> dict:
    if value.tzinfo is None:
        raise ValueError("expected an aware UTC instant")
    utc = value.astimezone(dt.timezone.utc)
    local = utc.astimezone(zone)
    delta = local.utcoffset()
    return {
        "utc": utc.isoformat(timespec="microseconds"),
        "local": local.replace(tzinfo=None).isoformat(timespec="microseconds"),
        "offset_seconds": delta.days * 86400 + delta.seconds,
        "abbreviation": local.tzname(),
        "is_dst": local.dst() != dt.timedelta(0),
    }


def timezone_project(data: bytes, value: dt.datetime) -> dict:
    """Project a UTC instant using the supplied TZif bytes, retaining historical second offsets."""
    return _view(_zone(data)[0], value)


def timezone_local(data: bytes, text: str) -> dict:
    """Return exact candidates, or the two offset-based projections of a nonexistent local time."""
    (zone, offsets), local = _zone(data), _local(text)
    candidates, projections, by_offset = {}, {}, {}
    for fold in (0, 1):
        aware = local.replace(tzinfo=zone, fold=fold)
        # Reject an overflowing interpretation rather than silently making a
        # repeated local time look unique at the supported year boundaries.
        aware.astimezone(dt.timezone.utc)
        delta = aware.utcoffset()
        offsets.add(delta.days * 86400 + delta.seconds)
    # Include all recorded offsets and footer offsets. UTC round trips also
    # handle first-transition gaps where ZoneInfo's fold shortcut is incomplete.
    for seconds in offsets:
        try:
            utc = (local - dt.timedelta(seconds=seconds)).replace(tzinfo=dt.timezone.utc)
            value = _view(zone, utc)
        except OverflowError:
            continue
        by_offset[seconds] = value
        if value["local"] == local.isoformat(timespec="microseconds"):
            candidates[value["utc"]] = value
    if len(candidates) > 2:
        raise ValueError("more than two local-time candidates")
    kind = "gap" if not candidates else "unique" if len(candidates) == 1 else "fold"
    if kind == "gap":
        for seconds, value in by_offset.items():
            actual = value["offset_seconds"]
            if actual in by_offset and by_offset[actual]["offset_seconds"] == seconds:
                projections[value["utc"]] = value
        if len(projections) != 2:
            raise ValueError("local time has no pair of gap projections")
    return {
        "kind": kind,
        "local": local.isoformat(timespec="microseconds"),
        "candidates": [candidates[key] for key in sorted(candidates)],
        "projections": [projections[key] for key in sorted(projections)] if kind == "gap" else [],
    }
