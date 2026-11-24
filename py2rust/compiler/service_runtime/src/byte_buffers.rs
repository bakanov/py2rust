//! Checked byte construction and bounded growth for the service profile.
use crate::Result;

const MAX_BYTES: usize = 64 * 1024 * 1024;

fn check_size(length: usize) -> Result<()> {
    if length > MAX_BYTES {
        return Err("byte buffer exceeds 64 MiB".into());
    }
    Ok(())
}

pub fn byte_value(value: i64) -> Result<u8> {
    Ok(u8::try_from(value).map_err(|_| "byte must be in range 0..255")?)
}

pub fn byte_buffer_new(length: i64) -> Result<Vec<u8>> {
    let length = usize::try_from(length).map_err(|_| "negative byte buffer length")?;
    check_size(length)?;
    let mut result = Vec::new();
    result.try_reserve_exact(length)?;
    result.resize(length, 0);
    Ok(result)
}

pub fn byte_buffer_copy(data: &[u8]) -> Result<Vec<u8>> {
    check_size(data.len())?;
    let mut result = Vec::new();
    result.try_reserve_exact(data.len())?;
    result.extend_from_slice(data);
    Ok(result)
}

pub fn byte_buffer_from_ints(data: &[i64]) -> Result<Vec<u8>> {
    check_size(data.len())?;
    let mut result = Vec::new();
    result.try_reserve_exact(data.len())?;
    for value in data {
        result.push(byte_value(*value)?);
    }
    Ok(result)
}

pub fn byte_buffer_checked(data: Vec<u8>) -> Result<Vec<u8>> {
    check_size(data.len())?;
    Ok(data)
}

pub fn byte_buffer_append(data: &mut Vec<u8>, value: i64) -> Result<()> {
    let value = byte_value(value)?;
    check_size(
        data.len()
            .checked_add(1)
            .ok_or("byte buffer size overflow")?,
    )?;
    data.try_reserve(1)?;
    data.push(value);
    Ok(())
}

pub fn byte_buffer_extend(data: &mut Vec<u8>, suffix: &[u8]) -> Result<()> {
    check_size(
        data.len()
            .checked_add(suffix.len())
            .ok_or("byte buffer size overflow")?,
    )?;
    data.try_reserve(suffix.len())?;
    data.extend_from_slice(suffix);
    Ok(())
}
