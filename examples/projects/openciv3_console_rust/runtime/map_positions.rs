//! Entry positions are valid only while a map retains all existing keys in order.

use crate::Result;
use indexmap::IndexMap;
use std::cell::Cell;

pub fn cached_map_position<V>(
    slot: &Cell<Option<usize>>,
    map: &IndexMap<String, V>,
    key: &str,
) -> Option<usize> {
    if let Some(position) = slot.get() {
        return Some(position);
    }
    let position = map.get_index_of(key);
    slot.set(position);
    position
}

pub fn cached_map_get<'a, V>(
    slot: &Cell<Option<usize>>,
    map: &'a IndexMap<String, V>,
    key: &str,
) -> Result<&'a V> {
    let position = cached_map_position(slot, map, key).ok_or("missing dict key")?;
    Ok(map.get_index(position).ok_or("missing dict key")?.1)
}

pub fn cached_map_insert<V>(
    slot: &Cell<Option<usize>>,
    map: &mut IndexMap<String, V>,
    key: &str,
    value: V,
) {
    if let Some(position) = cached_map_position(slot, map, key) {
        *map.get_index_mut(position).expect("stable map position").1 = value;
    } else {
        let (position, _) = map.insert_full(key.to_owned(), value);
        slot.set(Some(position));
    }
}
