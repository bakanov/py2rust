//! Bounded UTF-8 CSV dialect: doubled quotes, embedded CR/LF and blank records.
use crate::common::{require, Result};
pub fn parse(
    data: &[u8],
    delimiter: u8,
    max_rows: usize,
    max_columns: usize,
    max_field: usize,
) -> Result<Vec<Vec<String>>> {
    let mut rows = Vec::new();
    let mut row = Vec::new();
    let mut state = 0;
    let mut start = 0;
    let mut end = 0;
    let mut quoted = false;
    let mut skip_lf = false;
    for index in 0..=data.len() {
        let eof = index == data.len();
        let c = if eof { b'\n' } else { data[index] };
        if skip_lf && c == b'\n' && !eof {
            skip_lf = false;
            start = index + 1;
            continue;
        }
        skip_lf = false;
        require(
            index - start <= max_field * 2 + 2,
            "CSV field exceeds byte limit",
        )?;
        require(!eof || state != 2, "unterminated quoted CSV field")?;
        if state == 2 {
            if c == b'"' {
                end = index;
                state = 3;
            }
        } else if state == 3 && c == b'"' {
            state = 2;
        } else if c == delimiter || c == b'\n' || c == b'\r' {
            let active = state != 0 || !row.is_empty();
            if c == delimiter || active {
                let raw = std::str::from_utf8(&data[start..if quoted { end } else { index }])?;
                let value = if quoted {
                    raw.replace("\"\"", "\"")
                } else {
                    raw.into()
                };
                require(value.len() <= max_field, "CSV field exceeds byte limit")?;
                row.push(value);
                require(row.len() <= max_columns, "CSV column limit exceeded")?;
            }
            if c != delimiter && (!eof || active) {
                rows.push(std::mem::take(&mut row));
                require(rows.len() <= max_rows, "CSV row limit exceeded")?;
                skip_lf = c == b'\r';
            }
            state = 0;
            quoted = false;
            start = index + 1;
        } else if state == 0 && c == b'"' {
            quoted = true;
            state = 2;
            start = index + 1;
        } else {
            require(state != 3, "unexpected character after closing CSV quote")?;
            state = 1;
        }
    }
    Ok(rows)
}
pub fn render_row(row: &[String], delimiter: char, max_field: usize) -> Result<String> {
    let mut result = String::new();
    for (index, cell) in row.iter().enumerate() {
        require(
            cell.len() <= max_field,
            "formatted CSV field exceeds byte limit",
        )?;
        if index > 0 {
            result.push(delimiter);
        }
        if cell.contains([delimiter, '"', '\r', '\n']) || (row.len() == 1 && cell.is_empty()) {
            result.push('"');
            result.push_str(&cell.replace('"', "\"\""));
            result.push('"');
        } else {
            result.push_str(cell);
        }
    }
    result.push_str("\r\n");
    require(result.len() <= 8388608, "converted data exceeds 8 MiB")?;
    Ok(result)
}
