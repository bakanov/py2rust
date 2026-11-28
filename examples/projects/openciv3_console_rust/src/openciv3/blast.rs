use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct _Bits {
    pub(crate) data: Vec<u8>,
    pub(crate) position: i64,
    pub(crate) buffer: i64,
    pub(crate) count: i64,
}

// Python: openciv3/blast.py:70
pub(crate) fn _Bits__take(mut self_: _Bits, mut width: i64) -> rt::Result<i64> {
    while ((self_).count < width) {
        if ((self_).position == ((&(self_).data).len() as i64)) {
            return Err("Truncated DCL stream".to_string().into());
        }
        self_.buffer = ((self_).buffer
            | rt::int_lshift(
                (rt::at(&(self_).data, (self_).position)? as i64),
                (self_).count,
            )?);
        self_.position = ((self_).position)
            .checked_add(1i64)
            .ok_or("integer overflow")?;
        self_.count = ((self_).count)
            .checked_add(8i64)
            .ok_or("integer overflow")?;
    }
    let mut value: i64 = ((self_).buffer
        & (rt::int_lshift(1i64, width)?)
            .checked_sub(1i64)
            .ok_or("integer overflow")?);
    self_.buffer = rt::int_rshift((self_).buffer, width)?;
    self_.count = ((self_).count)
        .checked_sub(width)
        .ok_or("integer overflow")?;
    Ok(value)
}

// Python: openciv3/blast.py:83
pub(crate) fn _codebook(compact: &[i64]) -> rt::Result<indexmap::IndexMap<(i64, i64), i64>> {
    let mut lengths: Vec<i64> = {
        let mut __comprehension_result_192: Vec<i64> = Vec::new();
        let __comprehension_source_190 = (compact.to_vec());
        for item in __comprehension_source_190.iter().cloned() {
            let __comprehension_source_191 = ((0i64..(1i64)
                .checked_add(rt::int_rshift(item, 4i64)?)
                .ok_or("integer overflow")?)
                .collect::<Vec<i64>>());
            for _ in __comprehension_source_191.iter().cloned() {
                __comprehension_result_192.push((item & 15i64));
            }
        }
        __comprehension_result_192
    };
    let mut book: indexmap::IndexMap<(i64, i64), i64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    let mut code: i64 = 0i64;
    for mut width in 1i64..({
        let __values = &lengths;
        let mut __items = __values.iter();
        let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
        for __candidate in __items {
            if __candidate > __best {
                __best = __candidate;
            }
        }
        (*__best).clone()
    })
    .checked_add(1i64)
    .ok_or("integer overflow")?
    {
        code = rt::int_lshift(code, 1i64)?;
        for mut for_target_89_8 in (lengths.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>()
        {
            let (mut symbol, mut length): (i64, i64) = for_target_89_8;
            if (length == width) {
                {
                    let __value = symbol;
                    let __key = (width, code);
                    book.insert(__key, __value);
                }
                code = (code).checked_add(1i64).ok_or("integer overflow")?;
            }
        }
    }
    Ok(book)
}

// Python: openciv3/blast.py:101
pub(crate) fn _symbol(bits: &_Bits, book: &indexmap::IndexMap<(i64, i64), i64>) -> rt::Result<i64> {
    let mut code: i64 = 0i64;
    for mut width in 1i64..14i64 {
        code = (rt::int_lshift(code, 1i64)? | (_Bits__take((*bits).clone(), 1i64)? ^ 1i64));
        let mut symbol: Option<i64> = ((*book).clone()).get(&((width, code))).cloned();
        if (symbol).is_some() {
            return Ok((*(symbol).as_ref().ok_or("expected a value")?).clone());
        }
    }
    return Err("Invalid DCL Huffman code".to_string().into());
}

/// Decode one or more concatenated, byte-aligned DCL streams.
// Python: openciv3/blast.py:111
pub(crate) fn decompress(data: &[u8]) -> rt::Result<Vec<u8>> {
    let mut bits: _Bits = _Bits {
        data: data.to_vec(),
        position: 0i64,
        buffer: 0i64,
        count: 0i64,
    };
    let mut output: Vec<u8> = Vec::<u8>::new();
    loop {
        let mut coded: i64 = _Bits__take(bits.clone(), 8i64)?;
        let mut dictionary_bits: i64 = _Bits__take(bits.clone(), 8i64)?;
        if ((coded > 1i64) || {
            let __needle = dictionary_bits;
            let __container = &({
                let __tuple_value = &((4i64, 5i64, 6i64));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                ]
            });
            !__container.contains(&__needle)
        }) {
            return Err("Invalid DCL header".to_string().into());
        }
        let mut start: i64 = ((output).len() as i64);
        loop {
            if !(_Bits__take(bits.clone(), 1i64)? != 0i64) {
                {
                    let __value = (if (coded != 0i64) {
                        _symbol(&bits, {
                            static __CONSTANT_py__openciv3__blast__LITERALS: std::sync::OnceLock<
                                indexmap::IndexMap<(i64, i64), i64>,
                            > = std::sync::OnceLock::new();
                            if __CONSTANT_py__openciv3__blast__LITERALS.get().is_none() {
                                let __constant_value = _codebook(
                                    &({
                                        let __tuple_value = &({
                                            static __CONSTANT_py__openciv3__blast__LITERAL_LENGTHS: std::sync::OnceLock<(i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64, i64,)> = std::sync::OnceLock::new();
                                            if __CONSTANT_py__openciv3__blast__LITERAL_LENGTHS
                                                .get()
                                                .is_none()
                                            {
                                                let __constant_value = (
                                                    11i64, 124i64, 8i64, 7i64, 28i64, 7i64, 188i64,
                                                    13i64, 76i64, 4i64, 10i64, 8i64, 12i64, 10i64,
                                                    12i64, 10i64, 8i64, 23i64, 8i64, 9i64, 7i64,
                                                    6i64, 7i64, 8i64, 7i64, 6i64, 55i64, 8i64,
                                                    23i64, 24i64, 12i64, 11i64, 7i64, 9i64, 11i64,
                                                    12i64, 6i64, 7i64, 22i64, 5i64, 7i64, 24i64,
                                                    6i64, 11i64, 9i64, 6i64, 7i64, 22i64, 7i64,
                                                    11i64, 38i64, 7i64, 9i64, 8i64, 25i64, 11i64,
                                                    8i64, 11i64, 9i64, 12i64, 8i64, 12i64, 5i64,
                                                    38i64, 5i64, 38i64, 5i64, 11i64, 7i64, 5i64,
                                                    6i64, 21i64, 6i64, 10i64, 53i64, 8i64, 7i64,
                                                    24i64, 10i64, 27i64, 44i64, 253i64, 253i64,
                                                    253i64, 252i64, 252i64, 252i64, 13i64, 12i64,
                                                    45i64, 12i64, 45i64, 12i64, 61i64, 12i64,
                                                    45i64, 44i64, 173i64,
                                                );
                                                let _ =
                                                    __CONSTANT_py__openciv3__blast__LITERAL_LENGTHS
                                                        .set(__constant_value);
                                            }
                                            __CONSTANT_py__openciv3__blast__LITERAL_LENGTHS
                                                .get()
                                                .ok_or("missing module constant")?
                                                .clone()
                                        });
                                        vec![
                                            __tuple_value.0.clone(),
                                            __tuple_value.1.clone(),
                                            __tuple_value.2.clone(),
                                            __tuple_value.3.clone(),
                                            __tuple_value.4.clone(),
                                            __tuple_value.5.clone(),
                                            __tuple_value.6.clone(),
                                            __tuple_value.7.clone(),
                                            __tuple_value.8.clone(),
                                            __tuple_value.9.clone(),
                                            __tuple_value.10.clone(),
                                            __tuple_value.11.clone(),
                                            __tuple_value.12.clone(),
                                            __tuple_value.13.clone(),
                                            __tuple_value.14.clone(),
                                            __tuple_value.15.clone(),
                                            __tuple_value.16.clone(),
                                            __tuple_value.17.clone(),
                                            __tuple_value.18.clone(),
                                            __tuple_value.19.clone(),
                                            __tuple_value.20.clone(),
                                            __tuple_value.21.clone(),
                                            __tuple_value.22.clone(),
                                            __tuple_value.23.clone(),
                                            __tuple_value.24.clone(),
                                            __tuple_value.25.clone(),
                                            __tuple_value.26.clone(),
                                            __tuple_value.27.clone(),
                                            __tuple_value.28.clone(),
                                            __tuple_value.29.clone(),
                                            __tuple_value.30.clone(),
                                            __tuple_value.31.clone(),
                                            __tuple_value.32.clone(),
                                            __tuple_value.33.clone(),
                                            __tuple_value.34.clone(),
                                            __tuple_value.35.clone(),
                                            __tuple_value.36.clone(),
                                            __tuple_value.37.clone(),
                                            __tuple_value.38.clone(),
                                            __tuple_value.39.clone(),
                                            __tuple_value.40.clone(),
                                            __tuple_value.41.clone(),
                                            __tuple_value.42.clone(),
                                            __tuple_value.43.clone(),
                                            __tuple_value.44.clone(),
                                            __tuple_value.45.clone(),
                                            __tuple_value.46.clone(),
                                            __tuple_value.47.clone(),
                                            __tuple_value.48.clone(),
                                            __tuple_value.49.clone(),
                                            __tuple_value.50.clone(),
                                            __tuple_value.51.clone(),
                                            __tuple_value.52.clone(),
                                            __tuple_value.53.clone(),
                                            __tuple_value.54.clone(),
                                            __tuple_value.55.clone(),
                                            __tuple_value.56.clone(),
                                            __tuple_value.57.clone(),
                                            __tuple_value.58.clone(),
                                            __tuple_value.59.clone(),
                                            __tuple_value.60.clone(),
                                            __tuple_value.61.clone(),
                                            __tuple_value.62.clone(),
                                            __tuple_value.63.clone(),
                                            __tuple_value.64.clone(),
                                            __tuple_value.65.clone(),
                                            __tuple_value.66.clone(),
                                            __tuple_value.67.clone(),
                                            __tuple_value.68.clone(),
                                            __tuple_value.69.clone(),
                                            __tuple_value.70.clone(),
                                            __tuple_value.71.clone(),
                                            __tuple_value.72.clone(),
                                            __tuple_value.73.clone(),
                                            __tuple_value.74.clone(),
                                            __tuple_value.75.clone(),
                                            __tuple_value.76.clone(),
                                            __tuple_value.77.clone(),
                                            __tuple_value.78.clone(),
                                            __tuple_value.79.clone(),
                                            __tuple_value.80.clone(),
                                            __tuple_value.81.clone(),
                                            __tuple_value.82.clone(),
                                            __tuple_value.83.clone(),
                                            __tuple_value.84.clone(),
                                            __tuple_value.85.clone(),
                                            __tuple_value.86.clone(),
                                            __tuple_value.87.clone(),
                                            __tuple_value.88.clone(),
                                            __tuple_value.89.clone(),
                                            __tuple_value.90.clone(),
                                            __tuple_value.91.clone(),
                                            __tuple_value.92.clone(),
                                            __tuple_value.93.clone(),
                                            __tuple_value.94.clone(),
                                            __tuple_value.95.clone(),
                                            __tuple_value.96.clone(),
                                            __tuple_value.97.clone(),
                                        ]
                                    }),
                                )?;
                                let _ =
                                    __CONSTANT_py__openciv3__blast__LITERALS.set(__constant_value);
                            }
                            __CONSTANT_py__openciv3__blast__LITERALS
                                .get()
                                .ok_or("missing module constant")?
                        })?
                    } else {
                        _Bits__take(bits.clone(), 8i64)?
                    });
                    rt::byte_buffer_append(&mut output, __value)?;
                };
                continue;
            }
            let mut symbol: i64 = _symbol(&bits, {
                static __CONSTANT_py__openciv3__blast__LENGTHS: std::sync::OnceLock<
                    indexmap::IndexMap<(i64, i64), i64>,
                > = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__blast__LENGTHS.get().is_none() {
                    let __constant_value = _codebook(
                        &({
                            let __tuple_value = &({
                                static __CONSTANT_py__openciv3__blast__LENGTH_LENGTHS:
                                    std::sync::OnceLock<(i64, i64, i64, i64, i64, i64)> =
                                    std::sync::OnceLock::new();
                                if __CONSTANT_py__openciv3__blast__LENGTH_LENGTHS
                                    .get()
                                    .is_none()
                                {
                                    let __constant_value =
                                        (2i64, 35i64, 36i64, 53i64, 38i64, 23i64);
                                    let _ = __CONSTANT_py__openciv3__blast__LENGTH_LENGTHS
                                        .set(__constant_value);
                                }
                                __CONSTANT_py__openciv3__blast__LENGTH_LENGTHS
                                    .get()
                                    .ok_or("missing module constant")?
                                    .clone()
                            });
                            vec![
                                __tuple_value.0.clone(),
                                __tuple_value.1.clone(),
                                __tuple_value.2.clone(),
                                __tuple_value.3.clone(),
                                __tuple_value.4.clone(),
                                __tuple_value.5.clone(),
                            ]
                        }),
                    )?;
                    let _ = __CONSTANT_py__openciv3__blast__LENGTHS.set(__constant_value);
                }
                __CONSTANT_py__openciv3__blast__LENGTHS
                    .get()
                    .ok_or("missing module constant")?
            })?;
            let mut length: i64 = (rt::at(
                &({
                    let __tuple_value = {
                        static __CONSTANT_py__openciv3__blast__BASE: std::sync::OnceLock<(
                            i64,
                            i64,
                            i64,
                            i64,
                            i64,
                            i64,
                            i64,
                            i64,
                            i64,
                            i64,
                            i64,
                            i64,
                            i64,
                            i64,
                            i64,
                            i64,
                        )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__blast__BASE.get().is_none() {
                            let __constant_value = (
                                3i64, 2i64, 4i64, 5i64, 6i64, 7i64, 8i64, 9i64, 10i64, 12i64,
                                16i64, 24i64, 40i64, 72i64, 136i64, 264i64,
                            );
                            let _ = __CONSTANT_py__openciv3__blast__BASE.set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__blast__BASE
                            .get()
                            .ok_or("missing module constant")?
                    };
                    vec![
                        __tuple_value.0.clone(),
                        __tuple_value.1.clone(),
                        __tuple_value.2.clone(),
                        __tuple_value.3.clone(),
                        __tuple_value.4.clone(),
                        __tuple_value.5.clone(),
                        __tuple_value.6.clone(),
                        __tuple_value.7.clone(),
                        __tuple_value.8.clone(),
                        __tuple_value.9.clone(),
                        __tuple_value.10.clone(),
                        __tuple_value.11.clone(),
                        __tuple_value.12.clone(),
                        __tuple_value.13.clone(),
                        __tuple_value.14.clone(),
                        __tuple_value.15.clone(),
                    ]
                }),
                symbol,
            )?)
            .checked_add(_Bits__take(
                bits.clone(),
                rt::at(
                    &({
                        let __tuple_value = {
                            static __CONSTANT_py__openciv3__blast__EXTRA: std::sync::OnceLock<(
                                i64,
                                i64,
                                i64,
                                i64,
                                i64,
                                i64,
                                i64,
                                i64,
                                i64,
                                i64,
                                i64,
                                i64,
                                i64,
                                i64,
                                i64,
                                i64,
                            )> = std::sync::OnceLock::new();
                            if __CONSTANT_py__openciv3__blast__EXTRA.get().is_none() {
                                let __constant_value = (
                                    0i64, 0i64, 0i64, 0i64, 0i64, 0i64, 0i64, 0i64, 1i64, 2i64,
                                    3i64, 4i64, 5i64, 6i64, 7i64, 8i64,
                                );
                                let _ = __CONSTANT_py__openciv3__blast__EXTRA.set(__constant_value);
                            }
                            __CONSTANT_py__openciv3__blast__EXTRA
                                .get()
                                .ok_or("missing module constant")?
                        };
                        vec![
                            __tuple_value.0.clone(),
                            __tuple_value.1.clone(),
                            __tuple_value.2.clone(),
                            __tuple_value.3.clone(),
                            __tuple_value.4.clone(),
                            __tuple_value.5.clone(),
                            __tuple_value.6.clone(),
                            __tuple_value.7.clone(),
                            __tuple_value.8.clone(),
                            __tuple_value.9.clone(),
                            __tuple_value.10.clone(),
                            __tuple_value.11.clone(),
                            __tuple_value.12.clone(),
                            __tuple_value.13.clone(),
                            __tuple_value.14.clone(),
                            __tuple_value.15.clone(),
                        ]
                    }),
                    symbol,
                )?,
            )?)
            .ok_or("integer overflow")?;
            if (length == 519i64) {
                break;
            }
            let mut width: i64 = (if (length == 2i64) {
                2i64
            } else {
                dictionary_bits
            });
            let mut distance: i64 = ((rt::int_lshift(
                _symbol(&bits, {
                    static __CONSTANT_py__openciv3__blast__DISTANCES: std::sync::OnceLock<
                        indexmap::IndexMap<(i64, i64), i64>,
                    > = std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__blast__DISTANCES.get().is_none() {
                        let __constant_value = _codebook(
                            &({
                                let __tuple_value = &({
                                    static __CONSTANT_py__openciv3__blast__DISTANCE_LENGTHS:
                                        std::sync::OnceLock<(i64, i64, i64, i64, i64, i64, i64)> =
                                        std::sync::OnceLock::new();
                                    if __CONSTANT_py__openciv3__blast__DISTANCE_LENGTHS
                                        .get()
                                        .is_none()
                                    {
                                        let __constant_value =
                                            (2i64, 20i64, 53i64, 230i64, 247i64, 151i64, 248i64);
                                        let _ = __CONSTANT_py__openciv3__blast__DISTANCE_LENGTHS
                                            .set(__constant_value);
                                    }
                                    __CONSTANT_py__openciv3__blast__DISTANCE_LENGTHS
                                        .get()
                                        .ok_or("missing module constant")?
                                        .clone()
                                });
                                vec![
                                    __tuple_value.0.clone(),
                                    __tuple_value.1.clone(),
                                    __tuple_value.2.clone(),
                                    __tuple_value.3.clone(),
                                    __tuple_value.4.clone(),
                                    __tuple_value.5.clone(),
                                    __tuple_value.6.clone(),
                                ]
                            }),
                        )?;
                        let _ = __CONSTANT_py__openciv3__blast__DISTANCES.set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__blast__DISTANCES
                        .get()
                        .ok_or("missing module constant")?
                })?,
                width,
            )?)
            .checked_add(_Bits__take(bits.clone(), width)?)
            .ok_or("integer overflow")?)
            .checked_add(1i64)
            .ok_or("integer overflow")?;
            if (distance
                > ((output).len() as i64)
                    .checked_sub(start)
                    .ok_or("integer overflow")?)
            {
                return Err("DCL reference before start of stream".to_string().into());
            }
            let mut pattern: Vec<u8> = rt::bytes_slice(
                rt::slice_view(
                    &output,
                    (distance).checked_neg().ok_or("integer overflow")?,
                    i64::MAX,
                ),
                0i64,
                length,
            );
            let (mut repeats, mut remainder): (i64, i64) =
                rt::divmod_int(length, ((pattern).len() as i64))?;
            {
                let __values = [
                    (pattern.clone()).repeat(std::cmp::max(repeats, 0) as usize),
                    rt::bytes_slice(&pattern, 0i64, remainder),
                ]
                .concat();
                rt::byte_buffer_extend(&mut output, &__values)?;
            };
        }
        if ((bits).position == ((data).len() as i64)) {
            return Ok(rt::byte_buffer_copy(&output)?);
        }
        let mut chained_fields_138_8: i64 = 0i64;
        bits.buffer = chained_fields_138_8;
        bits.count = chained_fields_138_8;
    }
}
