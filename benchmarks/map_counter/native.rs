use indexmap::IndexMap;
use std::{env, error::Error, fs};

fn main() -> Result<(), Box<dyn Error>> {
    let text = fs::read_to_string(env::var("TEXT_INPUT")?)?;
    let mut frequencies: IndexMap<String, i64> = IndexMap::new();
    for _ in 0..10 {
        for word in text.split('\n') {
            if let Some(count) = frequencies.get_mut(word) {
                *count = count.checked_add(1).ok_or("overflow")?;
            } else {
                frequencies.insert(word.to_owned(), 1);
            }
        }
    }
    let mut total = 0i64;
    for (word, count) in &frequencies {
        total = total
            .checked_add(
                count
                    .checked_mul(word.chars().count() as i64)
                    .ok_or("overflow")?,
            )
            .ok_or("overflow")?;
    }
    println!("{total}");
    Ok(())
}
