use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct Record {
    pub(crate) data: Vec<u8>,
    pub(crate) section: String,
    pub(crate) encoding: String,
}

// Python: openciv3/binary.py:11
pub(crate) fn Record__bytes(
    self_: &Record,
    mut offset: i64,
    mut length: i64,
) -> rt::Result<Vec<u8>> {
    if (((offset).min(length) < 0i64)
        || ((offset).checked_add(length).ok_or("integer overflow")?
            > ((&(self_).data).len() as i64)))
    {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Truncated ".to_string(),
                ((self_).section.clone()).to_string(),
                " field at byte ".to_string(),
                (offset).to_string(),
                " (size ".to_string(),
                (length).to_string(),
                ")".to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok(rt::byte_buffer_copy(rt::slice_view(
        &(self_).data,
        offset,
        (offset).checked_add(length).ok_or("integer overflow")?,
    ))?)
}

// Python: openciv3/binary.py:16
pub(crate) fn Record__integer(self_: &Record, mut offset: i64) -> rt::Result<i64> {
    rt::int_from_bytes_signed(&(Record__bytes(self_, offset, 4i64)?), "little", true)
}

// Python: openciv3/binary.py:19
pub(crate) fn Record__count(
    self_: &Record,
    mut offset: i64,
    mut item_size: i64,
) -> rt::Result<i64> {
    let mut value: i64 = Record__integer(self_, offset)?;
    if ((value < 0i64)
        || ((value).checked_mul(item_size).ok_or("integer overflow")?
            > (((&(self_).data).len() as i64)
                .checked_sub(offset)
                .ok_or("integer overflow")?)
            .checked_sub(4i64)
            .ok_or("integer overflow")?))
    {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Invalid ".to_string(),
                ((self_).section.clone()).to_string(),
                " array length at byte ".to_string(),
                (offset).to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok(value)
}

// Python: openciv3/binary.py:25
pub(crate) fn Record__text(self_: &Record, mut offset: i64, mut length: i64) -> rt::Result<String> {
    rt::decode_bytes(
        &(rt::at(
            &(rt::bytes_split(&(Record__bytes(self_, offset, length)?), &(vec![0u8]), 1i64)),
            0i64,
        )?),
        &(self_).encoding,
        "replace",
    )
}
