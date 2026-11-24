"""Deterministic Huffman tree lengths and validated canonical prefix codes."""

# ruff: noqa: PLC0206 - supported dictionary iteration

import heapq


def frequencies(data: bytes) -> list[int]:
    counts: list[int] = []
    for symbol in range(256):
        counts.append(0)
    for symbol in data:
        counts[symbol] = counts[symbol] + 1
    return counts


def lengths(data: bytes) -> dict[int, int]:
    counts: list[int] = frequencies(data)
    heap: list[tuple[int, int, int]] = []
    left: list[int] = []
    right: list[int] = []
    symbols: list[int] = []
    for symbol in range(256):
        if counts[symbol] > 0:
            heapq.heappush(heap, (counts[symbol], symbol, len(symbols)))
            symbols.append(symbol)
            left.append(-1)
            right.append(-1)
    while len(heap) > 1:
        first: tuple[int, int, int] = heapq.heappop(heap)
        second: tuple[int, int, int] = heapq.heappop(heap)
        heapq.heappush(heap, (first[0] + second[0], min(first[1], second[1]), len(symbols)))
        symbols.append(-1)
        left.append(first[2])
        right.append(second[2])
    result: dict[int, int] = {}
    if len(heap) == 0:
        return result
    pending: list[tuple[int, int]] = [(heap[0][2], 0)]
    while len(pending) > 0:
        entry: tuple[int, int] = pending.pop()
        node: int = entry[0]
        depth: int = entry[1]
        if symbols[node] >= 0:
            result[symbols[node]] = max(1, depth)
        else:
            pending.append((left[node], depth + 1))
            pending.append((right[node], depth + 1))
    return result


def canonical(widths: dict[int, int]) -> dict[int, tuple[int, int]]:
    ordered: list[tuple[int, int]] = []
    for symbol in widths:
        assert 0 <= symbol <= 255 and 1 <= widths[symbol] <= 32, "invalid codebook entry"
        ordered.append((widths[symbol], symbol))
    assert len(ordered) <= 256, "too many symbols"
    result: dict[int, tuple[int, int]] = {}
    code: int = 0
    previous: int = 0
    for item in sorted(ordered):
        width: int = item[0]
        code = code << (width - previous)
        assert code < (1 << width), "oversubscribed codebook"
        result[item[1]] = (code, width)
        code = code + 1
        previous = width
    if len(ordered) == 1:
        assert previous == 1, "single-symbol code must have length one"
    elif len(ordered) > 1:
        assert code == (1 << previous), "incomplete codebook"
    return result


def spelling(code: int, width: int) -> str:
    bits: list[str] = []
    for shift in range(width - 1, -1, -1):
        bits.append("1" if ((code >> shift) & 1) != 0 else "0")
    return "".join(bits)
