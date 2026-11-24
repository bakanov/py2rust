"""Tuple-key n-gram postings, maximal aligned matches and union-based token coverage."""

# ruff: noqa: C414, PLC0206 - typed sorting and supported dictionary iteration

from model import Source

from py2rust.stdlib import Json, json_canonical


def anchors(sources: list[Source], size: int) -> tuple[dict[tuple[int, int, int], list[int]], int, int]:
    index: dict[tuple[str, ...], list[tuple[int, int]]] = {}
    windows: int = 0
    for number in range(len(sources)):
        words: list[str] = []
        for token in sources[number].tokens:
            words.append(token.value)
        for start in range(len(words) - size + 1):
            key: tuple[str, ...] = tuple(words[start : start + size])
            if key not in index:
                index[key] = []
            index[key].append((number, start))
            windows = windows + 1
    diagonals: dict[tuple[int, int, int], list[int]] = {}
    hits: int = 0
    for key in index:
        positions: list[tuple[int, int]] = index[key]
        for first in range(len(positions)):
            left: tuple[int, int] = positions[first]
            for second in range(first + 1, len(positions)):
                right: tuple[int, int] = positions[second]
                if left[0] == right[0]:
                    continue
                hits = hits + 1
                assert hits <= 100000, "cross-document n-gram hits exceed 100000"
                diagonal: tuple[int, int, int] = (left[0], right[0], right[1] - left[1])
                if diagonal not in diagonals:
                    diagonals[diagonal] = []
                diagonals[diagonal].append(left[1])
    return (diagonals, windows, hits)


def merge(diagonals: dict[tuple[int, int, int], list[int]], size: int) -> list[tuple[int, int, int, int, int]]:
    spans: list[tuple[int, int, int, int, int]] = []
    for key in sorted(list(diagonals)):
        begin: int = -1
        end: int = -1
        for start in sorted(diagonals[key]):
            if begin < 0:
                begin = start
                end = start + size
            elif start <= end:
                end = max(end, start + size)
            else:
                spans.append((key[0], key[1], begin, begin + key[2], end - begin))
                assert len(spans) <= 4096, "merged match count exceeds 4096"
                begin = start
                end = start + size
        if begin >= 0:
            spans.append((key[0], key[1], begin, begin + key[2], end - begin))
            assert len(spans) <= 4096, "merged match count exceeds 4096"
    return sorted(spans)


def union(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for interval in sorted(intervals):
        if len(result) == 0 or interval[0] > result[-1][1]:
            result.append(interval)
        else:
            result[-1] = (result[-1][0], max(result[-1][1], interval[1]))
    return result


def location(source: Source, start: int, end: int) -> Json:
    first: int = source.tokens[start].start
    last: int = source.tokens[end - 1].end
    return {
        "document": source.identifier,
        "start_token": start,
        "end_token": end,
        "start_char": first,
        "end_char": last,
        "text": source.text[first:last],
    }


def audit(sources: list[Source], size: int) -> Json:
    indexed: tuple[dict[tuple[int, int, int], list[int]], int, int] = anchors(sources, size)
    spans: list[tuple[int, int, int, int, int]] = merge(indexed[0], size)
    covered: dict[int, list[tuple[int, int]]] = {}
    for number in range(len(sources)):
        covered[number] = []
    pairs: set[tuple[int, int]] = set()
    matches: list[Json] = []
    matched_windows: int = 0
    payload: int = 0
    for span in spans:
        left: Source = sources[span[0]]
        right: Source = sources[span[1]]
        normalized: list[str] = []
        for token in left.tokens[span[2] : span[2] + span[4]]:
            normalized.append(token.value)
        record: Json = {
            "left": location(left, span[2], span[2] + span[4]),
            "right": location(right, span[3], span[3] + span[4]),
            "length": span[4],
            "tokens": normalized,
            "ngram_hits": span[4] - size + 1,
        }
        payload = payload + len((json_canonical(record) + "\n").encode())
        assert payload <= 8388608, "match records exceed 8 MiB"
        matches.append(record)
        matched_windows = matched_windows + span[4] - size + 1
        covered[span[0]].append((span[2], span[2] + span[4]))
        covered[span[1]].append((span[3], span[3] + span[4]))
        pairs.add((span[0], span[1]))
    assert matched_windows == indexed[2], "merged n-gram accounting mismatch"
    documents: list[Json] = []
    total_tokens: int = 0
    total_covered: int = 0
    for number in range(len(sources)):
        source: Source = sources[number]
        intervals: list[tuple[int, int]] = union(covered[number])
        count: int = 0
        ranges: list[Json] = []
        for interval in intervals:
            count = count + interval[1] - interval[0]
            ranges.append({"start_token": interval[0], "end_token": interval[1]})
        total_tokens = total_tokens + len(source.tokens)
        total_covered = total_covered + count
        documents.append(
            {
                "id": source.identifier,
                "characters": len(source.text),
                "bytes": len(source.text.encode()),
                "tokens": len(source.tokens),
                "covered_tokens": count,
                "coverage": ranges,
            }
        )
    return {
        "documents": documents,
        "matches": matches,
        "counts": {
            "documents": len(sources),
            "tokens": total_tokens,
            "ngram_windows": indexed[1],
            "ngram_hits": indexed[2],
            "matches": len(matches),
            "document_pairs": len(pairs),
            "covered_tokens": total_covered,
        },
    }
