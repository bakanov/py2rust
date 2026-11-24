fn native_checksum(text: &str, positions: &[i64]) -> rt::Result<i64> {
    // Include construction in each call, just like the generated lazy index.
    let characters: Vec<char> = text.chars().collect();
    let mut result = 0i64;
    for &position in positions {
        let character = characters[rt::index(characters.len(), position)?];
        result = result.checked_add(i64::from(character as u32)).ok_or("integer overflow")?;
    }
    Ok(result)
}

fn main() -> rt::Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let engine = &args[1];
    let size: usize = args[2].parse()?;
    let order = &args[3];
    let repeats: usize = args[4].parse()?;
    assert!(size.is_power_of_two() && repeats > 0);
    let text: String = ['é', '🙂', 'a'].into_iter().cycle().take(size).collect();
    let positions: Vec<i64> = (0..size).map(|index| {
        let position = match order.as_str() {
            "sequential" => index,
            "reverse" => size - index - 1,
            "permuted" => index.wrapping_mul(7919) % size,
            _ => panic!("unknown access order"),
        };
        // Negative indices exercise the same resolution on half the requests.
        if index % 2 == 0 { position as i64 } else { position as i64 - size as i64 }
    }).collect();
    let expected: i64 = text.chars().map(|value| i64::from(value as u32)).sum();
    let start = std::time::Instant::now();
    let mut answer = 0;
    for _ in 0..repeats {
        answer = match engine.as_str() {
            "generated" => checksum(std::hint::black_box(&text), std::hint::black_box(&positions))?,
            "native" => native_checksum(std::hint::black_box(&text), std::hint::black_box(&positions))?,
            _ => panic!("unknown engine"),
        };
        assert_eq!(std::hint::black_box(answer), expected);
    }
    println!("{}", serde_json::json!({"ns":start.elapsed().as_nanos(),"answer":answer,"repeats":repeats}));
    Ok(())
}
