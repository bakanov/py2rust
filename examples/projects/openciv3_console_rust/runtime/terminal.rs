//! Terminal I/O and a pinned Unicode 16 cell profile shared with the Python reference.
use crate::{Json, Result};
use std::io::{IsTerminal, Write};
use unicode_segmentation::UnicodeSegmentation;

pub fn terminal_info() -> Json {
    let attached = std::io::stdout().is_terminal();
    let (mut columns, mut rows) = (80_u16, 24_u16);
    #[cfg(unix)]
    if attached {
        let mut size = libc::winsize {
            ws_row: 0,
            ws_col: 0,
            ws_xpixel: 0,
            ws_ypixel: 0,
        };
        // stdout is a live descriptor; TIOCGWINSZ writes this initialized winsize.
        if unsafe { libc::ioctl(libc::STDOUT_FILENO, libc::TIOCGWINSZ, &mut size) } == 0 {
            if size.ws_col > 0 {
                columns = size.ws_col;
            }
            if size.ws_row > 0 {
                rows = size.ws_row;
            }
        }
    }
    let term = std::env::var("TERM").unwrap_or_default();
    serde_json::json!({"isatty": attached, "ansi": attached && !["", "dumb", "unknown"].contains(&term.as_str()),
                      "columns": columns, "rows": rows})
}

pub fn terminal_write(text: &str) -> Result<()> {
    if text.len() > 1048576 {
        return Err("terminal output byte limit".into());
    }
    let mut output = std::io::stdout().lock();
    output.write_all(text.as_bytes())?;
    output.flush()?;
    Ok(())
}

fn member(code: u32, table: &[(u32, u32)]) -> bool {
    table
        .binary_search_by(|&(start, end)| {
            if code < start {
                std::cmp::Ordering::Greater
            } else if code > end {
                std::cmp::Ordering::Less
            } else {
                std::cmp::Ordering::Equal
            }
        })
        .is_ok()
}

fn cluster_width(cluster: &str) -> i64 {
    use crate::terminal_tables::{VS16, WIDE, ZERO};
    let mut characters = cluster.chars();
    let mut last = None;
    let mut width = 0;
    while let Some(character) = characters.next() {
        let code = character as u32;
        if code == 0x200d {
            characters.next();
        } else if code == 0xfe0f && last.is_some() {
            if member(last.unwrap(), VS16) {
                width += 1;
            }
            last = None;
        } else if !member(code, ZERO) {
            width += if member(code, WIDE) { 2 } else { 1 };
            last = Some(code);
        }
    }
    width
}

pub fn terminal_cells(text: &str) -> Result<Vec<(String, i64)>> {
    if text.len() > 65536 {
        return Err("terminal text requires at most 65536 UTF-8 bytes".into());
    }
    for character in text.chars() {
        let code = character as u32;
        if code < 32
            || (127..=159).contains(&code)
            || [0x061c, 0x200e, 0x200f, 0x2028, 0x2029].contains(&code)
            || (0x202a..=0x202e).contains(&code)
            || (0x2066..=0x2069).contains(&code)
        {
            return Err("terminal text contains control or bidi formatting".into());
        }
    }
    Ok(text
        .graphemes(true)
        .map(|cluster| {
            let width = cluster_width(cluster);
            if width == 0 {
                (format!("◌{cluster}"), 1)
            } else {
                (cluster.to_owned(), width)
            }
        })
        .collect())
}
