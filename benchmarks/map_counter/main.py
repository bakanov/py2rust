"""Repeated string-key counters, as used by batch workers and traffic summaries."""

from py2rust.stdlib import env_get, read_text


def main() -> None:
    text: str = read_text(env_get("TEXT_INPUT", "input.txt"))
    frequencies: dict[str, int] = {}
    for repeat in range(10):
        for word in text.split("\n"):
            frequencies[word] = frequencies.get(word, 0) + 1
    total: int = 0
    for word in frequencies:
        total = total + frequencies[word] * len(word)
    print(total)
    return


if __name__ == "__main__":
    main()
