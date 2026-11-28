use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct HeightMap {
    pub(crate) seed: i64,
    pub(crate) width: i64,
    pub(crate) height: i64,
    pub(crate) scale: f64,
    pub(crate) wrap_x: bool,
    pub(crate) wrap_y: bool,
    pub(crate) force_low_poles: bool,
    pub(crate) _tiles_per_cell_x: f64,
    pub(crate) _tiles_per_cell_y: f64,
    pub(crate) values: Vec<i64>,
}

// Python: strategy/height_map.py:26
pub(crate) fn HeightMap____post_init__(mut self_: HeightMap) -> rt::Result<HeightMap> {
    let (mut width, mut height, mut scale): (i64, i64, f64) =
        ((self_).width, (self_).height, (self_).scale);
    let (mut wrap_x, mut wrap_y, mut force_low_poles): (bool, bool, bool) =
        ((self_).wrap_x, (self_).wrap_y, (self_).force_low_poles);
    if ((width < 2i64)
        || ((height < 2i64) || (!(rt::math_isfinite(scale)) || (scale <= ((0i64) as f64)))))
    {
        return Err(
            "Height map needs dimensions >= 2 and a positive finite scale"
                .to_string()
                .into(),
        );
    }
    self_._tiles_per_cell_x = rt::int_true_div(width, 128i64)?;
    self_._tiles_per_cell_y = rt::int_true_div(height, 64i64)?;
    let mut noise: crate::strategy::noise::OpenSimplexNoise =
        crate::strategy::noise::OpenSimplexNoise____post_init__(
            crate::strategy::noise::OpenSimplexNoise {
                seed: (self_).seed,
                permutation: vec![],
            },
        )?;
    let mut raw: Vec<f64> = {
        let mut __comprehension_result_559: Vec<f64> = Vec::new();
        let __comprehension_source_557 = ((0i64..128i64).collect::<Vec<i64>>());
        for x in __comprehension_source_557.iter().cloned() {
            let __comprehension_source_558 = ((0i64..64i64).collect::<Vec<i64>>());
            for y in __comprehension_source_558.iter().cloned() {
                __comprehension_result_559.push(HeightMap__sample(
                    &noise,
                    x,
                    y,
                    scale,
                    wrap_x,
                    wrap_y,
                    force_low_poles,
                )?);
            }
        }
        __comprehension_result_559
    };
    let (mut low, mut high): (f64, f64) = (
        {
            let __values = &raw;
            let mut __items = __values.iter();
            let mut __best = __items.next().ok_or("min() arg is an empty sequence")?;
            for __candidate in __items {
                if __candidate < __best {
                    __best = __candidate;
                }
            }
            (*__best).clone()
        },
        {
            let __values = &raw;
            let mut __items = __values.iter();
            let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
            for __candidate in __items {
                if __candidate > __best {
                    __best = __candidate;
                }
            }
            (*__best).clone()
        },
    );
    let mut span: f64 = rt::finite(high - low)?;
    self_.values = (if (span != 0.0f64) {
        ({
            let mut __comprehension_result_561: Vec<i64> = Vec::new();
            let __comprehension_source_560 = (raw.clone());
            for value in __comprehension_source_560.iter().cloned() {
                __comprehension_result_561.push(rt::int_float(rt::finite(
                    (0.0f64).max((1.0f64).min(rt::float_true_div(rt::finite(value - low)?, span)?))
                        * ((255i64) as f64),
                )?)?);
            }
            __comprehension_result_561
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>()
    } else {
        vec![((0i64,)).0; std::cmp::max(((raw).len() as i64), 0) as usize]
    });
    Ok(self_.clone())
}

// Python: strategy/height_map.py:41
pub(crate) fn HeightMap__sample(
    noise: &crate::strategy::noise::OpenSimplexNoise,
    mut x: i64,
    mut y: i64,
    mut scale: f64,
    mut wrap_x: bool,
    mut wrap_y: bool,
    mut force_low_poles: bool,
) -> rt::Result<f64> {
    let (mut x_radius, mut y_radius): (f64, f64) = (
        rt::float_true_div(
            ((128i64) as f64),
            rt::finite(3.141592653589793f64 * ((2i64) as f64))?,
        )?,
        rt::float_true_div(
            ((64i64) as f64),
            rt::finite(3.141592653589793f64 * ((2i64) as f64))?,
        )?,
    );
    let (mut theta_x, mut theta_y): (f64, f64) = (
        rt::finite(
            rt::int_true_div(x, 128i64)? * rt::finite(3.141592653589793f64 * ((2i64) as f64))?,
        )?,
        rt::finite(
            rt::int_true_div(y, 64i64)? * rt::finite(3.141592653589793f64 * ((2i64) as f64))?,
        )?,
    );
    let mut chained_locals_45_8: f64 = 1.0f64;
    let mut amplitude: f64 = chained_locals_45_8;
    let mut frequency: f64 = chained_locals_45_8;
    let mut value: f64 = 0.0f64;
    for mut octave in 0i64..8i64 {
        let mut octave_scale: f64 = rt::finite(scale * frequency)?;
        let mut offset: i64 = (octave).checked_mul(1000i64).ok_or("integer overflow")?;
        let mut point: Vec<f64> = vec![];
        if !(wrap_x || wrap_y) {
            point = vec![
                rt::finite(
                    rt::finite(((1000i64) as f64) + rt::finite(octave_scale * ((x) as f64))?)?
                        + ((offset) as f64),
                )?,
                rt::finite(
                    rt::finite(((1000i64) as f64) + rt::finite(octave_scale * ((y) as f64))?)?
                        + ((offset) as f64),
                )?,
            ];
        } else {
            if (wrap_x && wrap_y) {
                point = vec![
                    rt::finite(
                        rt::finite(
                            ((1000i64) as f64)
                                + rt::finite(
                                    rt::finite(octave_scale * x_radius)? * rt::math_sin(theta_x)?,
                                )?,
                        )? + ((offset) as f64),
                    )?,
                    rt::finite(
                        rt::finite(
                            ((1000i64) as f64)
                                + rt::finite(
                                    rt::finite(octave_scale * x_radius)? * rt::math_cos(theta_x)?,
                                )?,
                        )? + ((offset) as f64),
                    )?,
                    rt::finite(
                        rt::finite(
                            ((1000i64) as f64)
                                + rt::finite(
                                    rt::finite(octave_scale * y_radius)? * rt::math_sin(theta_y)?,
                                )?,
                        )? + ((offset) as f64),
                    )?,
                    rt::finite(
                        rt::finite(
                            ((1000i64) as f64)
                                + rt::finite(
                                    rt::finite(octave_scale * y_radius)? * rt::math_cos(theta_y)?,
                                )?,
                        )? + ((offset) as f64),
                    )?,
                ];
            } else {
                if wrap_y {
                    point = vec![
                        rt::finite(
                            rt::finite(
                                ((1000i64) as f64)
                                    + rt::finite(
                                        rt::finite(octave_scale * y_radius)?
                                            * rt::math_sin(theta_y)?,
                                    )?,
                            )? + ((offset) as f64),
                        )?,
                        rt::finite(
                            rt::finite(
                                ((1000i64) as f64)
                                    + rt::finite(
                                        rt::finite(octave_scale * y_radius)?
                                            * rt::math_cos(theta_y)?,
                                    )?,
                            )? + ((offset) as f64),
                        )?,
                        rt::finite(
                            rt::finite(
                                ((1000i64) as f64) + rt::finite(octave_scale * ((x) as f64))?,
                            )? + ((offset) as f64),
                        )?,
                    ];
                } else {
                    point = vec![
                        rt::finite(
                            rt::finite(
                                ((1000i64) as f64)
                                    + rt::finite(
                                        rt::finite(octave_scale * x_radius)?
                                            * rt::math_sin(theta_x)?,
                                    )?,
                            )? + ((offset) as f64),
                        )?,
                        rt::finite(
                            rt::finite(
                                ((1000i64) as f64)
                                    + rt::finite(
                                        rt::finite(octave_scale * x_radius)?
                                            * rt::math_cos(theta_x)?,
                                    )?,
                            )? + ((offset) as f64),
                        )?,
                        rt::finite(
                            rt::finite(
                                ((1000i64) as f64) + rt::finite(octave_scale * ((y) as f64))?,
                            )? + ((offset) as f64),
                        )?,
                    ];
                }
            }
        }
        value = rt::finite(
            value
                + rt::finite(
                    crate::strategy::noise::OpenSimplexNoise__evaluate(noise, &point)? * amplitude,
                )?,
        )?;
        amplitude = rt::finite(amplitude * 0.5f64)?;
        frequency = rt::finite(frequency * ((2i64) as f64))?;
    }
    if (!(wrap_y) && force_low_poles) {
        let mut distance: f64 = rt::finite(
            rt::finite(
                (rt::finite(
                    rt::int_true_div(y, (64i64).checked_sub(1i64).ok_or("integer overflow")?)?
                        - 0.5f64,
                )?)
                .abs(),
            )? * 2.0f64,
        )?;
        value = rt::finite(value * rt::finite(1.0f64 - rt::finite(distance * distance)?)?)?;
    }
    Ok(value)
}

// Python: strategy/height_map.py:74
pub(crate) fn HeightMap__get_height(self_: &HeightMap, mut x: i64, mut y: i64) -> rt::Result<i64> {
    if (!({
        let __compare_0 = 0i64;
        let __compare_1 = x;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = (self_).width;
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) || !({
        let __compare_0 = 0i64;
        let __compare_1 = y;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = (self_).height;
            (__compare_1 < __compare_2)
        } else {
            false
        }
    })) {
        return Err("Height coordinate is outside the map".to_string().into());
    }
    Ok(rt::at(
        &((self_).values.clone()),
        ((rt::int_float(rt::float_true_div(((x) as f64), (self_)._tiles_per_cell_x)?)?)
            .checked_mul(64i64)
            .ok_or("integer overflow")?)
        .checked_add(rt::int_float(rt::float_true_div(
            ((y) as f64),
            (self_)._tiles_per_cell_y,
        )?)?)
        .ok_or("integer overflow")?,
    )?)
}

// Python: strategy/height_map.py:80
pub(crate) fn HeightMap___height_counts_below(self_: &HeightMap) -> rt::Result<Vec<i64>> {
    let mut histogram: Vec<i64> = (vec![0i64]).repeat(std::cmp::max(256i64, 0) as usize);
    for mut x in 0i64..(self_).width {
        for mut y in 0i64..(self_).height {
            {
                let __value = (rt::at(&(histogram.clone()), HeightMap__get_height(self_, x, y)?)?)
                    .checked_add(1i64)
                    .ok_or("integer overflow")?;
                let __key = HeightMap__get_height(self_, x, y)?;
                let __index = rt::index(histogram.len(), __key)?;
                histogram[__index] = __value;
            }
        }
    }
    Ok(({
        let mut __result: Vec<i64> = Vec::new();
        let mut __total = 0i64;
        let mut __has_total = true;
        __result.push(__total);
        for __item in (histogram).into_iter() {
            __total = __total.checked_add(__item).ok_or("integer overflow")?;
            __result.push(__total);
        }
        __result
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>())
}

// Python: strategy/height_map.py:87
pub(crate) fn HeightMap__find_sea_level(
    self_: &HeightMap,
    mut percent_water: i64,
) -> rt::Result<i64> {
    if !({
        let __compare_0 = 0i64;
        let __compare_1 = percent_water;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = 100i64;
            (__compare_1 <= __compare_2)
        } else {
            false
        }
    }) {
        return Err("Water coverage must be between 0 and 100"
            .to_string()
            .into());
    }
    let mut counts_below: Vec<i64> = HeightMap___height_counts_below(self_)?;
    let (mut low, mut high, mut threshold): (i64, i64, i64) = (0i64, 255i64, 128i64);
    let mut total: i64 = ((self_).width)
        .checked_mul((self_).height)
        .ok_or("integer overflow")?;
    for _ in 0i64..8i64 {
        let mut percent: i64 = rt::int_floor_div(
            (rt::at(&counts_below, threshold)?)
                .checked_mul(100i64)
                .ok_or("integer overflow")?,
            total,
        )?;
        if (percent < percent_water) {
            low = threshold;
        } else {
            high = threshold;
        }
        threshold = rt::int_floor_div((low).checked_add(high).ok_or("integer overflow")?, 2i64)?;
        if (low >= (high).checked_sub(1i64).ok_or("integer overflow")?) {
            break;
        }
    }
    Ok(threshold)
}
