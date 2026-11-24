"""A small, explicit shell lexer: quotes and pipes, with no implicit expansion."""


def parse(command: str) -> list[list[str]]:
    assert 0 < len(command.encode()) <= 8192 and "\x00" not in command, "invalid command bytes"
    stages: list[list[str]] = []
    arguments: list[str] = []
    token: str = ""
    quote: str = ""
    escaped: bool = False
    active: bool = False
    for char in command:
        if escaped:
            if quote == '"' and char not in ['"', "\\"]:
                token = token + "\\"
            token = token + char
            escaped = False
            active = True
        elif char == "\\" and quote != "'":
            escaped = True
            active = True
        elif quote != "":
            if char == quote:
                quote = ""
            else:
                token = token + char
        elif char in ["'", '"']:
            quote = char
            active = True
        elif char in [" ", "\t", "|"]:
            if active:
                arguments.append(token)
                assert len(arguments) <= 128, "too many arguments"
                token = ""
                active = False
            if char == "|":
                assert len(arguments) > 0, "empty pipeline stage"
                stages.append(arguments.copy())
                assert len(stages) < 8, "too many pipeline stages"
                arguments = []
        else:
            assert char not in ["\n", "\r", ";", "&", "<", ">", "`"], "unsupported shell operator"
            token = token + char
            active = True
    assert not escaped, "trailing escape"
    assert quote == "", "unterminated quote"
    if active:
        arguments.append(token)
    assert 0 < len(arguments) <= 128, "empty stage or too many arguments"
    stages.append(arguments)
    return stages
