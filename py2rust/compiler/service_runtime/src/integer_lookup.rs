//! A bounded read-only acceleration view; the original dictionary stays unchanged.
use indexmap::IndexMap;

pub struct IntLookup<'a, V> {
    source: &'a IndexMap<i64, V>,
    dense: Option<[Option<&'a V>; 256]>,
}
impl<'a, V> IntLookup<'a, V> {
    pub fn new(source: &'a IndexMap<i64, V>) -> Self {
        // Bound preparation work even for huge sparse dictionaries. References
        // preserve values and insertion order without cloning or new ownership.
        let dense = if source.len() <= 256 {
            let mut slots = [None; 256];
            for (&key, value) in source {
                if let Ok(index) = u8::try_from(key) {
                    slots[index as usize] = Some(value);
                }
            }
            Some(slots)
        } else {
            None
        };
        Self { source, dense }
    }
    pub fn get(&self, key: &i64) -> Option<&'a V> {
        if let (Some(slots), Ok(index)) = (&self.dense, u8::try_from(*key)) {
            return slots[index as usize];
        }
        self.source.get(key)
    }
}
