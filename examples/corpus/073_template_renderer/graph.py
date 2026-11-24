"""Check every include, reject cycles with a witness, and bound longest include chains."""

# ruff: noqa: PLR1711, PLC0206, C414, FURB192 - explicit returns and supported subset operations


def validate(graph: dict[str, dict[str, str]]) -> None:
    pending: set[str] = set()
    depths: dict[str, int] = {}
    for name in graph:
        pending.add(name)
        for target in graph[name]:
            assert target in graph, graph[name][target] + "unknown included template: " + target
    while len(pending) > 0:
        ready: list[str] = []
        for name in sorted(list(pending)):
            complete: bool = True
            for target in graph[name]:
                complete = complete and target in depths
            if complete:
                ready.append(name)
        if len(ready) == 0:
            current: str = sorted(list(pending))[0]
            chain: list[str] = []
            location: str = ""
            while current not in chain:
                chain.append(current)
                for target in sorted(list(graph[current])):
                    if target in pending:
                        location = graph[current][target]
                        current = target
                        break
            assert False, location + "include cycle: " + " -> ".join(chain + [current])
        for name in ready:
            longest: int = 1
            for target in graph[name]:
                longest = max(longest, 1 + depths[target])
                assert longest <= 12, graph[name][target] + "include depth exceeds 12"
            depths[name] = longest
        pending = pending.difference(set(ready))
    return
