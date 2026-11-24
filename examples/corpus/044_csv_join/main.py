"""Join two bounded CSV documents into an atomically published data/report bundle."""

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from joining import Joined, join
from settings import Table, selection, table, validate

from py2rust.stdlib import (
    Json,
    env_get,
    json_int,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def main() -> None:
    mode: str = env_get("JOIN_MODE", "preview")
    assert mode in ["preview", "join"], "invalid join mode"
    path: str = absolute(env_get("JOIN_CONFIG", "join.json"), path_resolve("."))
    config_document: Document = read(path, 65536)
    config: Json = json_loads(config_document.data.decode())
    validate(config)
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    left_document: Document = read(
        absolute(json_string(config["left"]["path"]), base), json_int(config["max_input_bytes"])
    )
    right_document: Document = read(
        absolute(json_string(config["right"]["path"]), base), json_int(config["max_input_bytes"])
    )
    left: Table = table(left_document, config["left"], config)
    right: Table = table(right_document, config["right"], config)
    result: Joined = join(left, right, selection(config, left, right), config)
    report: Json = result.report
    report["left_sha256"] = sha256_digest(sha256_update(sha256_new(), left_document.data))
    report["right_sha256"] = sha256_digest(sha256_update(sha256_new(), right_document.data))
    report["data_sha256"] = sha256_digest(sha256_update(sha256_new(), result.data.encode()))
    text: str = pretty(report)
    assert len(text.encode()) <= 16777216, "join report exceeds 16 MiB"
    documents: list[Document] = [config_document, left_document, right_document]
    checkpoint("validated")
    unchanged(documents)
    if mode == "join":
        publish(output, result.data, text, documents)
    print(text)
    return  # noqa: PLR1711 - explicit returns follow repository guidelines


if __name__ == "__main__":
    main()
