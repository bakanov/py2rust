use std::{env, error::Error, fs};

fn main() -> Result<(), Box<dyn Error>> {
    let text = fs::read_to_string(env::var("TEXT_INPUT")?)?;
    let case = env::var("TEXT_CASE")?;
    let mut total = 0i64;
    match case.as_str() {
        "prefix" => {
            for _ in 0..100 {
                total = total
                    .checked_add(text.split('?').next().unwrap().chars().count() as i64)
                    .ok_or("overflow")?;
            }
        }
        "count" => {
            for _ in 0..100 {
                total = total
                    .checked_add(text.split('\n').count() as i64)
                    .ok_or("overflow")?;
            }
        }
        _ => {
            for _ in 0..10 {
                for word in text.split('\n') {
                    total = total
                        .checked_add(word.chars().count() as i64)
                        .ok_or("overflow")?;
                }
            }
        }
    }
    println!("{total}");
    Ok(())
}
