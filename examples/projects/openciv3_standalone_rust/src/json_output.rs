//! Direct serialization for representations whose Serde output already matches
//! the subset contract. Insertion-ordered maps and floats use the owned fallback.
use crate::{json_check, Json, Result};
use serde::Serialize;

pub trait CheckedJson: Serialize {
    fn check_json(&self, depth: usize) -> Result<()>;
}

fn check_depth(depth: usize) -> Result<()> {
    if depth > 64 {
        return Err("JSON nesting exceeds 64".into());
    }
    Ok(())
}

impl CheckedJson for Json {
    fn check_json(&self, depth: usize) -> Result<()> {
        json_check(self, depth)
    }
}

macro_rules! scalar {
    ($($typ:ty),*) => {$(
        impl CheckedJson for $typ {
            fn check_json(&self, depth: usize) -> Result<()> {
                check_depth(depth)
            }
        }
    )*};
}
scalar!(str, String, i64, bool, ());

impl<T: CheckedJson> CheckedJson for [T] {
    fn check_json(&self, depth: usize) -> Result<()> {
        check_depth(depth)?;
        for item in self {
            item.check_json(depth + 1)?;
        }
        Ok(())
    }
}

impl<T: CheckedJson> CheckedJson for Vec<T> {
    fn check_json(&self, depth: usize) -> Result<()> {
        self.as_slice().check_json(depth)
    }
}

macro_rules! tuple {
    ($($typ:ident:$index:tt),+) => {
        impl<$($typ: CheckedJson),+> CheckedJson for ($($typ,)+) {
            fn check_json(&self, depth: usize) -> Result<()> {
                check_depth(depth)?;
                $(self.$index.check_json(depth + 1)?;)+
                Ok(())
            }
        }
    };
}
tuple!(A:0);
tuple!(A:0, B:1);
tuple!(A:0, B:1, C:2);
tuple!(A:0, B:1, C:2, D:3);
tuple!(A:0, B:1, C:2, D:3, E:4);
tuple!(A:0, B:1, C:2, D:3, E:4, F:5);
tuple!(A:0, B:1, C:2, D:3, E:4, F:5, G:6);
tuple!(A:0, B:1, C:2, D:3, E:4, F:5, G:6, H:7);
tuple!(A:0, B:1, C:2, D:3, E:4, F:5, G:6, H:7, I:8);
tuple!(A:0, B:1, C:2, D:3, E:4, F:5, G:6, H:7, I:8, J:9);
tuple!(A:0, B:1, C:2, D:3, E:4, F:5, G:6, H:7, I:8, J:9, K:10);
tuple!(A:0, B:1, C:2, D:3, E:4, F:5, G:6, H:7, I:8, J:9, K:10, L:11);

pub fn json_dumps_view<T: CheckedJson + ?Sized>(value: &T) -> Result<String> {
    value.check_json(0)?;
    Ok(serde_json::to_string(value)?)
}

pub fn pretty_view<T: CheckedJson + ?Sized>(value: &T) -> Result<String> {
    value.check_json(0)?;
    Ok(serde_json::to_string_pretty(value)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn output_and_errors_match_owned_serialization() {
        for text in ["null", "1.0", "-0.0", "1e20", r#"{"z":[1,"世界"],"a":{}}"#] {
            let value = crate::json_loads(text).unwrap();
            assert_eq!(
                json_dumps_view(&value).unwrap(),
                crate::json_dumps(&value).unwrap()
            );
            assert_eq!(pretty_view(&value).unwrap(), crate::pretty(&value).unwrap());
            assert_eq!(
                crate::json_canonical_view(&value).unwrap(),
                crate::json_canonical(&value).unwrap()
            );
        }
        let mut value = Json::Null;
        for _ in 0..64 {
            value = Json::Array(vec![value]);
        }
        assert_eq!(
            json_dumps_view(&value).unwrap(),
            crate::json_dumps(&value).unwrap()
        );
        value = Json::Array(vec![value]);
        assert!(json_dumps_view(&value).is_err());
        assert!(pretty_view(&value).is_err());
        assert!(crate::json_canonical_view(&value).is_err());
        assert!(crate::json_dumps(&value).is_err());
        let invalid: Json = serde_json::from_str("9223372036854775808").unwrap();
        assert!(json_dumps_view(&invalid).is_err());
        assert!(json_dumps_view(&vec![invalid]).is_err());
        let typed = ("abc".to_string(), vec![vec![1i64, 2]], true);
        assert_eq!(
            json_dumps_view(&typed).unwrap(),
            crate::json_dumps(&typed).unwrap()
        );
        assert_eq!(pretty_view(&typed).unwrap(), crate::pretty(&typed).unwrap());
    }
}
