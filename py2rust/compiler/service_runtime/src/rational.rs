//! Exact fractions with reduced, positive denominators and bounded component sizes.
use crate::Result;
use num_bigint::{BigInt, Sign};
use std::cmp::Ordering;

#[derive(Clone, Debug)]
pub struct Rational {
    numerator: BigInt,
    denominator: BigInt,
}

fn absolute(value: &BigInt) -> BigInt {
    if value.sign() == Sign::Minus {
        -value
    } else {
        value.clone()
    }
}

fn reduced(mut numerator: BigInt, mut denominator: BigInt) -> Result<Rational> {
    if denominator == BigInt::from(0) {
        return Err("rational division by zero".into());
    }
    if denominator.sign() == Sign::Minus {
        numerator = -numerator;
        denominator = -denominator;
    }
    let (mut a, mut b) = (absolute(&numerator), denominator.clone());
    while b != BigInt::from(0) {
        let remainder = &a % &b;
        a = b;
        b = remainder;
    }
    numerator /= &a;
    denominator /= &a;
    if numerator.bits() > 65536 || denominator.bits() > 65536 {
        return Err("rational exceeds 65536 bits".into());
    }
    Ok(Rational {
        numerator,
        denominator,
    })
}

fn integer(text: &str) -> Result<BigInt> {
    let digits = text.strip_prefix(['+', '-']).unwrap_or(text);
    if text.len() > 4096 || digits.is_empty() || !digits.bytes().all(|c| c.is_ascii_digit()) {
        return Err("expected 1..4096 characters of signed ASCII integer".into());
    }
    Ok(BigInt::parse_bytes(text.as_bytes(), 10).ok_or("invalid integer")?)
}

pub fn rational_new(numerator: &str, denominator: &str) -> Result<Rational> {
    reduced(integer(numerator)?, integer(denominator)?)
}

pub fn rational_decimal(text: &str) -> Result<Rational> {
    if text.is_empty() || text.len() > 4096 {
        return Err("expected 1..4096 characters of finite ASCII decimal".into());
    }
    let body = text.strip_prefix(['+', '-']).unwrap_or(text);
    let parts: Vec<&str> = body.split('.').collect();
    if parts.len() > 2
        || parts
            .iter()
            .any(|s| s.is_empty() || !s.bytes().all(|c| c.is_ascii_digit()))
    {
        return Err("expected 1..4096 characters of finite ASCII decimal".into());
    }
    let places = if parts.len() == 2 { parts[1].len() } else { 0 };
    reduced(
        integer(&text.replace('.', ""))?,
        BigInt::from(10).pow(places as u32),
    )
}

pub fn rational_add(left: &Rational, right: &Rational) -> Result<Rational> {
    reduced(
        &left.numerator * &right.denominator + &right.numerator * &left.denominator,
        &left.denominator * &right.denominator,
    )
}

pub fn rational_sub(left: &Rational, right: &Rational) -> Result<Rational> {
    reduced(
        &left.numerator * &right.denominator - &right.numerator * &left.denominator,
        &left.denominator * &right.denominator,
    )
}

pub fn rational_mul(left: &Rational, right: &Rational) -> Result<Rational> {
    reduced(
        &left.numerator * &right.numerator,
        &left.denominator * &right.denominator,
    )
}

pub fn rational_div(left: &Rational, right: &Rational) -> Result<Rational> {
    reduced(
        &left.numerator * &right.denominator,
        &left.denominator * &right.numerator,
    )
}

pub fn rational_compare(left: &Rational, right: &Rational) -> i64 {
    match (&left.numerator * &right.denominator).cmp(&(&right.numerator * &left.denominator)) {
        Ordering::Less => -1,
        Ordering::Equal => 0,
        Ordering::Greater => 1,
    }
}

pub fn rational_numerator(value: &Rational) -> String {
    value.numerator.to_str_radix(10)
}
pub fn rational_denominator(value: &Rational) -> String {
    value.denominator.to_str_radix(10)
}

pub fn rational_fixed(value: &Rational, places: i64) -> Result<String> {
    if !(0..=18).contains(&places) {
        return Err("decimal places must be 0..18".into());
    }
    let scaled = absolute(&value.numerator) * BigInt::from(10).pow(places as u32);
    let mut quotient = &scaled / &value.denominator;
    let twice = (&scaled % &value.denominator) * 2;
    if twice > value.denominator || (twice == value.denominator && &quotient % 2 != BigInt::from(0))
    {
        quotient += 1;
    }
    let mut digits = quotient.to_str_radix(10);
    let places = places as usize;
    if digits.len() <= places {
        digits = "0".repeat(places + 1 - digits.len()) + &digits;
    }
    if places > 0 {
        digits.insert(digits.len() - places, '.');
    }
    if value.numerator.sign() == Sign::Minus && quotient != BigInt::from(0) {
        digits.insert(0, '-');
    }
    Ok(digits)
}
