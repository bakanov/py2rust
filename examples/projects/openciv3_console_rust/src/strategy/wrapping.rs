use py2rust_service_runtime as rt;

// Python: strategy/wrapping.py:7
pub(crate) fn wrapping_neg(mut value: i64) -> rt::Result<i64> {
    if (value == i64::MIN) {
        return Ok(i64::MIN);
    }
    Ok((value).checked_neg().ok_or("integer overflow")?)
}

// Python: strategy/wrapping.py:13
pub(crate) fn wrapping_add(mut left: i64, mut right: i64) -> rt::Result<i64> {
    let mut low: i64 = (left
        & (rt::int_lshift(1i64, 32i64)?)
            .checked_sub(1i64)
            .ok_or("integer overflow")?)
    .checked_add(
        (right
            & (rt::int_lshift(1i64, 32i64)?)
                .checked_sub(1i64)
                .ok_or("integer overflow")?),
    )
    .ok_or("integer overflow")?;
    let mut high: i64 = ((rt::int_rshift(left, 32i64)?)
        .checked_add(rt::int_rshift(right, 32i64)?)
        .ok_or("integer overflow")?)
    .checked_add(rt::int_rshift(low, 32i64)?)
    .ok_or("integer overflow")?;
    high = (rt::int_modulo(
        (high)
            .checked_add(rt::int_lshift(1i64, 31i64)?)
            .ok_or("integer overflow")?,
        rt::int_lshift(1i64, 32i64)?,
    )?)
    .checked_sub(rt::int_lshift(1i64, 31i64)?)
    .ok_or("integer overflow")?;
    Ok((rt::int_lshift(high, 32i64)?
        | (low
            & (rt::int_lshift(1i64, 32i64)?)
                .checked_sub(1i64)
                .ok_or("integer overflow")?)))
}

// Python: strategy/wrapping.py:20
pub(crate) fn wrapping_sub(mut left: i64, mut right: i64) -> rt::Result<i64> {
    wrapping_add(left, wrapping_neg(right)?)
}

// Python: strategy/wrapping.py:24
pub(crate) fn wrapping_mul(mut left: i64, mut right: i64) -> rt::Result<i64> {
    if (right == i64::MIN) {
        return Ok((if ((left & 1i64) != 0i64) {
            i64::MIN
        } else {
            0i64
        }));
    }
    if (right < 0i64) {
        return wrapping_neg(wrapping_mul(left, wrapping_neg(right)?)?);
    }
    let mut result: i64 = 0i64;
    let mut factor: i64 = left;
    while (right > 0i64) {
        if ((right & 1i64) != 0i64) {
            result = wrapping_add(result, factor)?;
        }
        factor = wrapping_add(factor, factor)?;
        right = rt::int_rshift(right, 1i64)?;
    }
    Ok(result)
}
