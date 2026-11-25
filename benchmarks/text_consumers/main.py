"""Isolate collection consumers also found in corpus 019, 080, 095 and 118."""

from py2rust.stdlib import env_get, read_text


def main() -> None:
    text: str = read_text(env_get("TEXT_INPUT", "input.txt"))
    case: str = env_get("TEXT_CASE", "count")
    total: int = 0
    if case == "prefix":
        for repeat in range(100):
            total = total + len(text.split("?")[0])
    elif case == "count":
        for repeat in range(100):
            total = total + len(text.split("\n"))
    else:
        for repeat in range(10):
            for word in text.split("\n"):
                total = total + len(word)
    print(total)
    return


if __name__ == "__main__":
    main()
