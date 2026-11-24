"""UTF-8 CSV with doubled quotes and exact embedded CR/LF bytes."""


def parse(data: bytes, delimiter: str, max_rows: int, max_columns: int, max_field: int) -> list[list[str]]:
    separator: int = delimiter.encode()[0]
    rows: list[list[str]] = []
    row: list[str] = []
    state: int = 0  # field start, unquoted, quoted, after closing quote
    start: int = 0
    end: int = 0
    quoted: bool = False
    skip_lf: bool = False
    for index in range(len(data) + 1):
        eof: bool = index == len(data)
        character: int = 10 if eof else data[index]
        if skip_lf and character == 10 and not eof:
            skip_lf = False
            start = index + 1
            continue
        skip_lf = False
        assert index - start <= max_field * 2 + 2, "CSV field exceeds byte limit"
        assert not eof or state != 2, "unterminated quoted CSV field"
        if state == 2:
            if character == 34:
                end = index
                state = 3
        elif state == 3 and character == 34:
            state = 2
        elif character == separator or character in [10, 13]:
            active: bool = state != 0 or len(row) > 0
            if character == separator or active:
                value: str = data[start : end if quoted else index].decode()
                if quoted:
                    value = value.replace('""', '"')
                assert len(value.encode()) <= max_field, "CSV field exceeds byte limit"
                row.append(value)
                assert len(row) <= max_columns, "CSV column limit exceeded"
            if character != separator and (not eof or active):
                rows.append(row)
                assert len(rows) <= max_rows, "CSV row limit exceeded"
                row = []
                skip_lf = character == 13
            state = 0
            quoted = False
            start = index + 1
        elif state == 0 and character == 34:
            quoted = True
            state = 2
            start = index + 1
        else:
            assert state != 3, "unexpected character after closing CSV quote"
            state = 1
    return rows


def render(rows: list[list[str]], delimiter: str, max_field: int) -> str:
    lines: list[str] = []
    total: int = 0
    for row in rows:
        cells: list[str] = []
        for cell in row:
            assert len(cell.encode()) <= max_field, "formatted CSV field exceeds byte limit"
            encoded: str = cell
            if delimiter in cell or '"' in cell or "\r" in cell or "\n" in cell or (len(row) == 1 and cell == ""):
                encoded = '"' + cell.replace('"', '""') + '"'
            cells.append(encoded)
        line: str = delimiter.join(cells) + "\r\n"
        total = total + len(line.encode())
        assert total <= 8388608, "converted data exceeds 8 MiB"
        lines.append(line)
    return "".join(lines)
