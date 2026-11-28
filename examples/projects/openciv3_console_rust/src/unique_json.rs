//! Strict object-key validation while retaining JSON number tokens and ordinary keys.
use crate::{Json, Result};
use serde::de::{self, MapAccess, SeqAccess, Visitor};
use serde::Deserializer;
use serde_json::value::RawValue;
use std::fmt;

struct Container {
    depth: usize,
    unique: bool,
}

impl<'de> Visitor<'de> for Container {
    type Value = Json;

    fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
        formatter.write_str("a JSON container")
    }

    fn visit_seq<A: SeqAccess<'de>>(self, mut input: A) -> std::result::Result<Json, A::Error> {
        let mut values = Vec::new();
        while let Some(raw) = input.next_element::<&'de RawValue>()? {
            values.push(parse(raw.get(), self.depth + 1, self.unique).map_err(de::Error::custom)?);
        }
        Ok(Json::Array(values))
    }

    fn visit_map<A: MapAccess<'de>>(self, mut input: A) -> std::result::Result<Json, A::Error> {
        let mut values = serde_json::Map::new();
        while let Some(key) = input.next_key::<String>()? {
            if self.unique && values.contains_key(&key) {
                return Err(de::Error::custom("duplicate JSON object key"));
            }
            let raw = input.next_value::<&'de RawValue>()?;
            let value = parse(raw.get(), self.depth + 1, self.unique).map_err(de::Error::custom)?;
            values.insert(key, value);
        }
        Ok(Json::Object(values))
    }
}

pub(crate) fn parse(text: &str, depth: usize, unique: bool) -> Result<Json> {
    // Bound the parser's stack separately from the resulting JSON value. The
    // ordinary parser keeps the last duplicate value, so an overwritten value
    // must not be subjected to the final tree's 64-level/numeric restrictions.
    if depth >= 128 {
        return Err("JSON parsing nesting exceeds 128".into());
    }
    let first = text
        .trim_start_matches([' ', '\t', '\r', '\n'])
        .as_bytes()
        .first();
    let mut input = serde_json::Deserializer::from_str(text);
    // Explicit container methods avoid serde's private arbitrary-precision number
    // map protocol interpreting an ordinary object key as a number wrapper.
    let value = match first {
        Some(b'{') => input.deserialize_map(Container { depth, unique })?,
        Some(b'[') => input.deserialize_seq(Container { depth, unique })?,
        _ => {
            let value = serde_json::from_str(text)?;
            return Ok(value);
        }
    };
    input.end()?;
    Ok(value)
}

pub fn json_loads_unique(text: &str) -> Result<Json> {
    let value = parse(text, 0, true)?;
    crate::json_check(&value, 0)?;
    Ok(value)
}
