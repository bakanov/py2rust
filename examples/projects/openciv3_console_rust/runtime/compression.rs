//! Bounded raw DEFLATE and the legacy byte-name codec used by ZIP.
use crate::Result;
use flate2::{Decompress, FlushDecompress, Status};

pub fn deflate_decompress(input: &[u8], maximum: i64) -> Result<Vec<u8>> {
    if input.len() > 33554432 {
        return Err("deflate input requires at most 32 MiB of bytes".into());
    }
    if !(0..=67108864).contains(&maximum) {
        return Err("deflate output limit must be 0..64 MiB".into());
    }
    let limit = maximum as usize;
    let mut decoder = Decompress::new(false);
    let mut output = Vec::new();
    loop {
        let mut chunk = [0u8; 65536];
        // One extra byte detects an exceeded budget at an exact chunk boundary.
        // Never allocate according to an untrusted archive's advertised size.
        let available = chunk.len().min(limit - output.len() + 1);
        let before_in = decoder.total_in();
        let before_out = decoder.total_out();
        let status = decoder.decompress(
            &input[before_in as usize..],
            &mut chunk[..available],
            FlushDecompress::None,
        )?;
        let produced = (decoder.total_out() - before_out) as usize;
        if produced > limit - output.len() {
            return Err("deflate output exceeds limit".into());
        }
        output.extend_from_slice(&chunk[..produced]);
        if status == Status::StreamEnd {
            if decoder.total_in() as usize != input.len() {
                return Err("expected exactly one complete deflate stream".into());
            }
            return Ok(output);
        }
        if decoder.total_in() == before_in && produced == 0 {
            return Err("expected exactly one complete deflate stream".into());
        }
    }
}

/// CP437 upper-half mapping; ASCII/control bytes retain their Unicode values.
pub fn decode_cp437(data: &[u8]) -> String {
    const HIGH: [char; 128] = [
        '\u{c7}', '\u{fc}', '\u{e9}', '\u{e2}', '\u{e4}', '\u{e0}', '\u{e5}', '\u{e7}', '\u{ea}',
        '\u{eb}', '\u{e8}', '\u{ef}', '\u{ee}', '\u{ec}', '\u{c4}', '\u{c5}', '\u{c9}', '\u{e6}',
        '\u{c6}', '\u{f4}', '\u{f6}', '\u{f2}', '\u{fb}', '\u{f9}', '\u{ff}', '\u{d6}', '\u{dc}',
        '\u{a2}', '\u{a3}', '\u{a5}', '\u{20a7}', '\u{192}', '\u{e1}', '\u{ed}', '\u{f3}',
        '\u{fa}', '\u{f1}', '\u{d1}', '\u{aa}', '\u{ba}', '\u{bf}', '\u{2310}', '\u{ac}', '\u{bd}',
        '\u{bc}', '\u{a1}', '\u{ab}', '\u{bb}', '\u{2591}', '\u{2592}', '\u{2593}', '\u{2502}',
        '\u{2524}', '\u{2561}', '\u{2562}', '\u{2556}', '\u{2555}', '\u{2563}', '\u{2551}',
        '\u{2557}', '\u{255d}', '\u{255c}', '\u{255b}', '\u{2510}', '\u{2514}', '\u{2534}',
        '\u{252c}', '\u{251c}', '\u{2500}', '\u{253c}', '\u{255e}', '\u{255f}', '\u{255a}',
        '\u{2554}', '\u{2569}', '\u{2566}', '\u{2560}', '\u{2550}', '\u{256c}', '\u{2567}',
        '\u{2568}', '\u{2564}', '\u{2565}', '\u{2559}', '\u{2558}', '\u{2552}', '\u{2553}',
        '\u{256b}', '\u{256a}', '\u{2518}', '\u{250c}', '\u{2588}', '\u{2584}', '\u{258c}',
        '\u{2590}', '\u{2580}', '\u{3b1}', '\u{df}', '\u{393}', '\u{3c0}', '\u{3a3}', '\u{3c3}',
        '\u{b5}', '\u{3c4}', '\u{3a6}', '\u{398}', '\u{3a9}', '\u{3b4}', '\u{221e}', '\u{3c6}',
        '\u{3b5}', '\u{2229}', '\u{2261}', '\u{b1}', '\u{2265}', '\u{2264}', '\u{2320}',
        '\u{2321}', '\u{f7}', '\u{2248}', '\u{b0}', '\u{2219}', '\u{b7}', '\u{221a}', '\u{207f}',
        '\u{b2}', '\u{25a0}', '\u{a0}',
    ];
    data.iter()
        .map(|&byte| {
            if byte < 128 {
                char::from(byte)
            } else {
                HIGH[(byte - 128) as usize]
            }
        })
        .collect()
}
