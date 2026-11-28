use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct MapRandom {
    pub(crate) seed: i64,
    pub(crate) _values: Vec<i64>,
    pub(crate) _index: i64,
    pub(crate) _other: i64,
}

// Python: strategy/random.py:11
pub(crate) fn seed32(mut value: i64) -> rt::Result<i64> {
    Ok((rt::int_modulo(
        (value)
            .checked_add({
                let __exponent = 31i64;
                if __exponent < 0 {
                    return Err("negative integer exponent".into());
                }
                (2i64)
                    .checked_pow(__exponent as u32)
                    .ok_or("integer power overflow")?
            })
            .ok_or("integer overflow")?,
        {
            let __exponent = 32i64;
            if __exponent < 0 {
                return Err("negative integer exponent".into());
            }
            (2i64)
                .checked_pow(__exponent as u32)
                .ok_or("integer power overflow")?
        },
    )?)
    .checked_sub({
        let __exponent = 31i64;
        if __exponent < 0 {
            return Err("negative integer exponent".into());
        }
        (2i64)
            .checked_pow(__exponent as u32)
            .ok_or("integer power overflow")?
    })
    .ok_or("integer overflow")?)
}

// Python: strategy/random.py:22
pub(crate) fn MapRandom____post_init__(mut self_: MapRandom) -> rt::Result<MapRandom> {
    let mut seed: i64 = seed32((self_).seed)?;
    let mut previous: i64 = (161803398i64)
        .checked_sub(
            (if (seed == (2147483648i64).checked_neg().ok_or("integer overflow")?) {
                2147483647i64
            } else {
                (seed).checked_abs().ok_or("integer overflow")?
            }),
        )
        .ok_or("integer overflow")?;
    self_._values = (vec![0i64]).repeat(std::cmp::max(56i64, 0) as usize);
    {
        let __index = rt::index(self_._values.len(), 55i64)?;
        self_._values[__index] = previous;
    }
    let mut current: i64 = 1i64;
    for mut index in 1i64..55i64 {
        let mut slot: i64 =
            rt::int_modulo((21i64).checked_mul(index).ok_or("integer overflow")?, 55i64)?;
        {
            let __index = rt::index(self_._values.len(), slot)?;
            self_._values[__index] = current;
        }
        current = seed32((previous).checked_sub(current).ok_or("integer overflow")?)?;
        if (current < 0i64) {
            current = (current)
                .checked_add(2147483647i64)
                .ok_or("integer overflow")?;
        }
        previous = rt::at(&(self_)._values, slot)?;
    }
    for _ in 0i64..4i64 {
        for mut index in 1i64..56i64 {
            {
                let __index = rt::index(self_._values.len(), index)?;
                self_._values[__index] = seed32(
                    (rt::at(&(self_)._values, index)?)
                        .checked_sub(rt::at(
                            &(self_)._values,
                            (1i64)
                                .checked_add(rt::int_modulo(
                                    (index).checked_add(30i64).ok_or("integer overflow")?,
                                    55i64,
                                )?)
                                .ok_or("integer overflow")?,
                        )?)
                        .ok_or("integer overflow")?,
                )?;
            }
            if (rt::at(&(self_)._values, index)? < 0i64) {
                {
                    let __index = rt::index(self_._values.len(), index)?;
                    self_._values[__index] = (rt::at(&(self_)._values, index)?)
                        .checked_add(2147483647i64)
                        .ok_or("integer overflow")?;
                }
            }
        }
    }
    self_._index = 0i64;
    self_._other = 21i64;
    Ok(self_.clone())
}

// Python: strategy/random.py:43
pub(crate) fn MapRandom___sample(mut self_: MapRandom) -> rt::Result<i64> {
    self_._index = (if ((self_)._index < 55i64) {
        ((self_)._index)
            .checked_add(1i64)
            .ok_or("integer overflow")?
    } else {
        1i64
    });
    self_._other = (if ((self_)._other < 55i64) {
        ((self_)._other)
            .checked_add(1i64)
            .ok_or("integer overflow")?
    } else {
        1i64
    });
    let mut value: i64 = seed32(
        (rt::at(&(self_)._values, (self_)._index)?)
            .checked_sub(rt::at(&(self_)._values, (self_)._other)?)
            .ok_or("integer overflow")?,
    )?;
    if (value == 2147483647i64) {
        value = (value).checked_sub(1i64).ok_or("integer overflow")?;
    }
    if (value < 0i64) {
        value = (value)
            .checked_add(2147483647i64)
            .ok_or("integer overflow")?;
    }
    {
        let __index = rt::index(self_._values.len(), (self_)._index)?;
        self_._values[__index] = value;
    }
    Ok(value)
}

// Python: strategy/random.py:54
pub(crate) fn MapRandom__next_double(mut self_: &mut MapRandom) -> rt::Result<f64> {
    Ok(rt::finite(
        (({
            let mut __map_random = self_.clone();
            __map_random._index = if __map_random._index < 55 {
                __map_random._index + 1
            } else {
                1
            };
            __map_random._other = if __map_random._other < 55 {
                __map_random._other + 1
            } else {
                1
            };
            let __sample_index = __map_random._index as usize;
            let mut __value = (__map_random._values[__sample_index]
                - __map_random._values[__map_random._other as usize]
                + 2147483648i64)
                .rem_euclid(4294967296i64)
                - 2147483648i64;
            if __value == 2147483647i64 {
                __value -= 1;
            }
            if __value < 0 {
                __value += 2147483647i64;
            }
            __map_random._values[__sample_index] = __value;
            *self_ = __map_random;
            __value
        }) as f64)
            * rt::float_true_div(1.0f64, ((2147483647i64) as f64))?,
    )?)
}

// Python: strategy/random.py:57
pub(crate) fn MapRandom__next(mut self_: &mut MapRandom, maximum: &Option<i64>) -> rt::Result<i64> {
    if (maximum).is_none() {
        return Ok({
            let mut __map_random = self_.clone();
            __map_random._index = if __map_random._index < 55 {
                __map_random._index + 1
            } else {
                1
            };
            __map_random._other = if __map_random._other < 55 {
                __map_random._other + 1
            } else {
                1
            };
            let __sample_index = __map_random._index as usize;
            let mut __value = (__map_random._values[__sample_index]
                - __map_random._values[__map_random._other as usize]
                + 2147483648i64)
                .rem_euclid(4294967296i64)
                - 2147483648i64;
            if __value == 2147483647i64 {
                __value -= 1;
            }
            if __value < 0 {
                __value += 2147483647i64;
            }
            __map_random._values[__sample_index] = __value;
            *self_ = __map_random;
            __value
        });
    }
    if !({
        let __compare_0 = 0i64;
        let __compare_1 = (*maximum).clone();
        if (__compare_0 <= (*(__compare_1).as_ref().ok_or("expected a value")?).clone()) {
            let __compare_2 = 2147483647i64;
            ((*(__compare_1).as_ref().ok_or("expected a value")?).clone() <= __compare_2)
        } else {
            false
        }
    }) {
        return Err("Random upper bound must be a nonnegative Int32"
            .to_string()
            .into());
    }
    rt::int_float(rt::finite(
        {
            let mut __map_random = self_.clone();
            __map_random._index = if __map_random._index < 55 {
                __map_random._index + 1
            } else {
                1
            };
            __map_random._other = if __map_random._other < 55 {
                __map_random._other + 1
            } else {
                1
            };
            let __sample_index = __map_random._index as usize;
            let mut __value = (__map_random._values[__sample_index]
                - __map_random._values[__map_random._other as usize]
                + 2147483648i64)
                .rem_euclid(4294967296i64)
                - 2147483648i64;
            if __value == 2147483647i64 {
                __value -= 1;
            }
            if __value < 0 {
                __value += 2147483647i64;
            }
            __map_random._values[__sample_index] = __value;
            *self_ = __map_random;
            (__value as f64) * (1.0 / 2147483647.0)
        } * (((*((*maximum).clone()).as_ref().ok_or("expected a value")?).clone()) as f64),
    )?)
}

// Python: strategy/random.py:64
pub(crate) fn MapRandom__next_range(
    mut self_: &mut MapRandom,
    mut minimum: i64,
    mut maximum: i64,
) -> rt::Result<i64> {
    if !({
        let __compare_0 = (2147483648i64).checked_neg().ok_or("integer overflow")?;
        let __compare_1 = minimum;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = maximum;
            if (__compare_1 <= __compare_2) {
                let __compare_3 = 2147483647i64;
                (__compare_2 <= __compare_3)
            } else {
                false
            }
        } else {
            false
        }
    }) {
        return Err("Invalid Int32 random range".to_string().into());
    }
    let mut span: i64 = (maximum).checked_sub(minimum).ok_or("integer overflow")?;
    if (span <= 2147483647i64) {
        return Ok((rt::int_float(rt::finite(
            {
                let mut __map_random = self_.clone();
                __map_random._index = if __map_random._index < 55 {
                    __map_random._index + 1
                } else {
                    1
                };
                __map_random._other = if __map_random._other < 55 {
                    __map_random._other + 1
                } else {
                    1
                };
                let __sample_index = __map_random._index as usize;
                let mut __value = (__map_random._values[__sample_index]
                    - __map_random._values[__map_random._other as usize]
                    + 2147483648i64)
                    .rem_euclid(4294967296i64)
                    - 2147483648i64;
                if __value == 2147483647i64 {
                    __value -= 1;
                }
                if __value < 0 {
                    __value += 2147483647i64;
                }
                __map_random._values[__sample_index] = __value;
                *self_ = __map_random;
                (__value as f64) * (1.0 / 2147483647.0)
            } * ((span) as f64),
        )?)?)
        .checked_add(minimum)
        .ok_or("integer overflow")?);
    }
    let mut value: i64 = {
        let mut __map_random = self_.clone();
        __map_random._index = if __map_random._index < 55 {
            __map_random._index + 1
        } else {
            1
        };
        __map_random._other = if __map_random._other < 55 {
            __map_random._other + 1
        } else {
            1
        };
        let __sample_index = __map_random._index as usize;
        let mut __value = (__map_random._values[__sample_index]
            - __map_random._values[__map_random._other as usize]
            + 2147483648i64)
            .rem_euclid(4294967296i64)
            - 2147483648i64;
        if __value == 2147483647i64 {
            __value -= 1;
        }
        if __value < 0 {
            __value += 2147483647i64;
        }
        __map_random._values[__sample_index] = __value;
        *self_ = __map_random;
        __value
    };
    if (rt::int_modulo(
        {
            let mut __map_random = self_.clone();
            __map_random._index = if __map_random._index < 55 {
                __map_random._index + 1
            } else {
                1
            };
            __map_random._other = if __map_random._other < 55 {
                __map_random._other + 1
            } else {
                1
            };
            let __sample_index = __map_random._index as usize;
            let mut __value = (__map_random._values[__sample_index]
                - __map_random._values[__map_random._other as usize]
                + 2147483648i64)
                .rem_euclid(4294967296i64)
                - 2147483648i64;
            if __value == 2147483647i64 {
                __value -= 1;
            }
            if __value < 0 {
                __value += 2147483647i64;
            }
            __map_random._values[__sample_index] = __value;
            *self_ = __map_random;
            __value
        },
        2i64,
    )? == 0i64)
    {
        value = (value).checked_neg().ok_or("integer overflow")?;
    }
    let mut sample: f64 = rt::float_true_div(
        rt::finite(
            (value as f64)
                + (((2147483647i64)
                    .checked_sub(1i64)
                    .ok_or("integer overflow")?) as f64),
        )?,
        ((((2i64)
            .checked_mul(2147483647i64)
            .ok_or("integer overflow")?)
        .checked_sub(1i64)
        .ok_or("integer overflow")?) as f64),
    )?;
    Ok((rt::int_float(rt::finite(sample * ((span) as f64))?)?)
        .checked_add(minimum)
        .ok_or("integer overflow")?)
}
