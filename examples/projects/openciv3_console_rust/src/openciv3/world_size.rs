use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct WorldSize {
    pub(crate) optimal_cities: i64,
    pub(crate) tech_rate: i64,
    pub(crate) name: String,
    pub(crate) height: i64,
    pub(crate) civilization_distance: i64,
    pub(crate) civilization_count: i64,
    pub(crate) width: i64,
}

// Python: openciv3/world_size.py:17
pub(crate) fn WorldSize__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<WorldSize> {
    Ok(WorldSize {
        optimal_cities: crate::openciv3::binary::Record__integer(record, 4i64)?,
        tech_rate: crate::openciv3::binary::Record__integer(record, 8i64)?,
        name: crate::openciv3::binary::Record__text(record, 36i64, 32i64)?,
        height: crate::openciv3::binary::Record__integer(record, 68i64)?,
        civilization_distance: crate::openciv3::binary::Record__integer(record, 72i64)?,
        civilization_count: crate::openciv3::binary::Record__integer(record, 76i64)?,
        width: crate::openciv3::binary::Record__integer(record, 80i64)?,
    })
}
