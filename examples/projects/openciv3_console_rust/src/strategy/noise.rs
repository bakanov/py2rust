use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct _Contribution {
    pub(crate) offset: Vec<f64>,
    pub(crate) lattice: Vec<i64>,
}

#[derive(Clone, PartialEq)]
pub(crate) struct OpenSimplexNoise {
    pub(crate) seed: i64,
    pub(crate) permutation: Vec<i64>,
}

// Python: strategy/noise.py:25
pub(crate) fn _lookup(
    mut dimension: i64,
    bases: &[Vec<i64>],
    points: &[i64],
    pairs: &[i64],
) -> rt::Result<indexmap::IndexMap<i64, Vec<_Contribution>>> {
    let mut width: i64 = (dimension).checked_add(1i64).ok_or("integer overflow")?;
    let mut stride: i64 = (dimension)
        .checked_mul(dimension)
        .ok_or("integer overflow")?;
    let mut contributions: Vec<Vec<_Contribution>> = vec![];
    for mut start in rt::integer_range(0i64, ((points).len() as i64), stride)? {
        let mut data: Vec<i64> = {
            let mut __left: Vec<i64> = rt::at(bases, rt::at(points, start)?)?;
            let __right: Vec<i64> = rt::list_slice(
                points,
                (start).checked_add(1i64).ok_or("integer overflow")?,
                (start).checked_add(stride).ok_or("integer overflow")?,
            );
            __left.extend(__right);
            __left
        };
        let mut row: Vec<_Contribution> = vec![];
        for mut index in rt::integer_range(0i64, ((data).len() as i64), width)? {
            let mut lattice: Vec<i64> = rt::list_slice(
                &data,
                (index).checked_add(1i64).ok_or("integer overflow")?,
                (index).checked_add(width).ok_or("integer overflow")?,
            );
            {
                row.push(_Contribution { offset: ({ let mut __comprehension_result_563: Vec<f64> = Vec::new();  let __comprehension_source_562 = (lattice.clone()); for axis in __comprehension_source_562.iter().cloned() { __comprehension_result_563.push(rt::finite((((axis).checked_neg().ok_or("integer overflow")?) as f64) - rt::finite(((rt::at(&data, index)?) as f64) * ({ static __CONSTANT_py__strategy__noise__escaped_5f535155495348: std::sync::OnceLock<indexmap::IndexMap<i64, f64>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__noise__escaped_5f535155495348.get().is_none() { let __constant_value = [(2i64, 0.366025403784439f64), (3i64, rt::float_true_div(1.0f64, 3.0f64)?), (4i64, 0.309016994374947f64)].into_iter().collect::<indexmap::IndexMap<_, _>>(); let _ = __CONSTANT_py__strategy__noise__escaped_5f535155495348.set(__constant_value); } __CONSTANT_py__strategy__noise__escaped_5f535155495348.get().ok_or("missing module constant")? }).get(&(dimension)).ok_or("missing dict key")?.clone())?)?); } __comprehension_result_563 }).iter().cloned().collect::<Vec<_>>(), lattice: lattice.clone() });
            };
        }
        {
            contributions.push((row).iter().cloned().collect::<Vec<_>>());
        };
    }
    Ok({
        let mut __comprehension_result_565: indexmap::IndexMap<i64, Vec<_Contribution>> =
            indexmap::IndexMap::new();
        let __comprehension_source_564 = (rt::range_values(0i64, ((pairs).len() as i64), 2i64)?);
        for index in __comprehension_source_564.iter().cloned() {
            {
                let (__key, __value) = (
                    rt::at(pairs, index)?,
                    rt::at(
                        &contributions,
                        rt::at(pairs, (index).checked_add(1i64).ok_or("integer overflow")?)?,
                    )?,
                );
                __comprehension_result_565.insert(__key, __value);
            }
        }
        __comprehension_result_565
    })
}

// Python: strategy/noise.py:47
pub(crate) fn _signed64(mut value: i64) -> rt::Result<i64> {
    Ok(value)
}

// Python: strategy/noise.py:51
pub(crate) fn _sum(values: &[f64]) -> rt::Result<f64> {
    let mut result: f64 = 0.0f64;
    for mut value in (values).iter().copied() {
        result = rt::finite(result + value)?;
    }
    Ok(result)
}

// Python: strategy/noise.py:64
pub(crate) fn OpenSimplexNoise____post_init__(
    mut self_: OpenSimplexNoise,
) -> rt::Result<OpenSimplexNoise> {
    let mut seed: i64 = (self_).seed;
    let mut source: Vec<i64> = ((0i64..256i64).collect::<Vec<i64>>())
        .iter()
        .cloned()
        .collect::<Vec<_>>();
    self_.permutation = (vec![0i64]).repeat(std::cmp::max(256i64, 0) as usize);
    for _ in 0i64..3i64 {
        seed = _signed64(crate::strategy::wrapping::wrapping_add(
            crate::strategy::wrapping::wrapping_mul(seed, 6364136223846793005i64)?,
            1442695040888963407i64,
        )?)?;
    }
    for mut index in rt::integer_range(
        255i64,
        (1i64).checked_neg().ok_or("integer overflow")?,
        (1i64).checked_neg().ok_or("integer overflow")?,
    )? {
        seed = _signed64(crate::strategy::wrapping::wrapping_add(
            crate::strategy::wrapping::wrapping_mul(seed, 6364136223846793005i64)?,
            1442695040888963407i64,
        )?)?;
        let mut selected: i64 = rt::int_modulo(
            _signed64((seed).checked_add(31i64).ok_or("integer overflow")?)?,
            (index).checked_add(1i64).ok_or("integer overflow")?,
        )?;
        {
            let __index = rt::index(self_.permutation.len(), index)?;
            self_.permutation[__index] = rt::at(&source, selected)?;
        }
        {
            let __value = rt::at(&source, index)?;
            let __key = selected;
            let __index = rt::index(source.len(), __key)?;
            source[__index] = __value;
        }
    }
    Ok(self_.clone())
}

// Python: strategy/noise.py:77
pub(crate) fn OpenSimplexNoise__evaluate(
    self_: &OpenSimplexNoise,
    coordinates: &[f64],
) -> rt::Result<f64> {
    let mut dimension: i64 = ((coordinates).len() as i64);
    if {
        let __needle = dimension;
        let __container = {
            static __CONSTANT_py__strategy__noise__escaped_5f53545245544348: std::sync::OnceLock<
                indexmap::IndexMap<i64, f64>,
            > = std::sync::OnceLock::new();
            if __CONSTANT_py__strategy__noise__escaped_5f53545245544348
                .get()
                .is_none()
            {
                let __constant_value = [
                    (2i64, -(0.211324865405187f64)),
                    (3i64, rt::float_true_div(-(1.0f64), 6.0f64)?),
                    (4i64, -(0.138196601125011f64)),
                ]
                .into_iter()
                .collect::<indexmap::IndexMap<_, _>>();
                let _ =
                    __CONSTANT_py__strategy__noise__escaped_5f53545245544348.set(__constant_value);
            }
            __CONSTANT_py__strategy__noise__escaped_5f53545245544348
                .get()
                .ok_or("missing module constant")?
        };
        !__container.contains_key(&__needle)
    } {
        return Err("OpenSimplex noise requires 2, 3 or 4 coordinates"
            .to_string()
            .into());
    }
    let mut stretch: f64 = rt::finite(
        _sum(coordinates)?
            * ({
                static __CONSTANT_py__strategy__noise__escaped_5f53545245544348:
                    std::sync::OnceLock<indexmap::IndexMap<i64, f64>> = std::sync::OnceLock::new();
                if __CONSTANT_py__strategy__noise__escaped_5f53545245544348
                    .get()
                    .is_none()
                {
                    let __constant_value = [
                        (2i64, -(0.211324865405187f64)),
                        (3i64, rt::float_true_div(-(1.0f64), 6.0f64)?),
                        (4i64, -(0.138196601125011f64)),
                    ]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>();
                    let _ = __CONSTANT_py__strategy__noise__escaped_5f53545245544348
                        .set(__constant_value);
                }
                __CONSTANT_py__strategy__noise__escaped_5f53545245544348
                    .get()
                    .ok_or("missing module constant")?
            })
            .get(&(dimension))
            .ok_or("missing dict key")?
            .clone(),
    )?;
    let mut stretched: Vec<f64> = ({
        let mut __comprehension_result_567: Vec<f64> = Vec::new();
        let __comprehension_source_566 = (coordinates.to_vec());
        for axis in __comprehension_source_566.iter().cloned() {
            __comprehension_result_567.push(rt::finite(axis + stretch)?);
        }
        __comprehension_result_567
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut cell: Vec<i64> = ({
        let mut __comprehension_result_569: Vec<i64> = Vec::new();
        let __comprehension_source_568 = (stretched.clone());
        for axis in __comprehension_source_568.iter().cloned() {
            __comprehension_result_569.push(rt::floor(axis)?);
        }
        __comprehension_result_569
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut squish: f64 = rt::finite(
        (((cell.clone()).into_iter().sum::<i64>()) as f64)
            * ({
                static __CONSTANT_py__strategy__noise__escaped_5f535155495348: std::sync::OnceLock<
                    indexmap::IndexMap<i64, f64>,
                > = std::sync::OnceLock::new();
                if __CONSTANT_py__strategy__noise__escaped_5f535155495348
                    .get()
                    .is_none()
                {
                    let __constant_value = [
                        (2i64, 0.366025403784439f64),
                        (3i64, rt::float_true_div(1.0f64, 3.0f64)?),
                        (4i64, 0.309016994374947f64),
                    ]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>();
                    let _ = __CONSTANT_py__strategy__noise__escaped_5f535155495348
                        .set(__constant_value);
                }
                __CONSTANT_py__strategy__noise__escaped_5f535155495348
                    .get()
                    .ok_or("missing module constant")?
            })
            .get(&(dimension))
            .ok_or("missing dict key")?
            .clone(),
    )?;
    let mut delta: Vec<f64> = ({
        let mut __comprehension_result_571: Vec<f64> = Vec::new();
        let __comprehension_source_570 = ({
            let __left = coordinates.to_vec();
            let __right = cell.clone();
            if false && __left.len() != __right.len() {
                return Err("zip() argument lengths differ".into());
            }
            let mut __result: Vec<(f64, i64)> = Vec::new();
            let __length = __left.len().min(__right.len());
            let mut __left_iter = __left.into_iter();
            let mut __right_iter = __right.into_iter();
            for __index in 0..__length {
                __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
            }
            __result
        });
        for (axis, base) in __comprehension_source_570.iter().cloned() {
            __comprehension_result_571
                .push(rt::finite(axis - rt::finite(((base) as f64) + squish)?)?);
        }
        __comprehension_result_571
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut inside: Vec<f64> = ({
        let mut __comprehension_result_573: Vec<f64> = Vec::new();
        let __comprehension_source_572 = ({
            let __left = stretched.clone();
            let __right = cell.clone();
            if false && __left.len() != __right.len() {
                return Err("zip() argument lengths differ".into());
            }
            let mut __result: Vec<(f64, i64)> = Vec::new();
            let __length = __left.len().min(__right.len());
            let mut __left_iter = __left.into_iter();
            let mut __right_iter = __right.into_iter();
            for __index in 0..__length {
                __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
            }
            __result
        });
        for (axis, base) in __comprehension_source_572.iter().cloned() {
            __comprehension_result_573.push(rt::finite(axis - ((base) as f64))?);
        }
        __comprehension_result_573
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut total: f64 = _sum(&(inside.clone()))?;
    let (mut x, mut y): (f64, f64) = {
        let __tuple_values = rt::list_slice(&inside, 0i64, 2i64);
        if __tuple_values.len() != 2 {
            return Err("tuple length mismatch".into());
        }
        (
            rt::at(&__tuple_values, 0i64)?,
            rt::at(&__tuple_values, 1i64)?,
        )
    };
    let mut key: i64 = 0i64;
    if (dimension == 2i64) {
        key = (((rt::int_float(rt::finite(rt::finite(x - y)? + ((1i64) as f64))?)?
            | rt::int_lshift(rt::int_float(total)?, 1i64)?)
            | rt::int_lshift(rt::int_float(rt::finite(total + y)?)?, 2i64)?)
            | rt::int_lshift(rt::int_float(rt::finite(total + x)?)?, 4i64)?);
    } else {
        if (dimension == 3i64) {
            let mut z: f64 = rt::at(&inside, 2i64)?;
            key = ((((((rt::int_float(rt::finite(rt::finite(y - z)? + ((1i64) as f64))?)?
                | rt::int_lshift(
                    rt::int_float(rt::finite(rt::finite(x - y)? + ((1i64) as f64))?)?,
                    1i64,
                )?)
                | rt::int_lshift(
                    rt::int_float(rt::finite(rt::finite(x - z)? + ((1i64) as f64))?)?,
                    2i64,
                )?)
                | rt::int_lshift(rt::int_float(total)?, 3i64)?)
                | rt::int_lshift(rt::int_float(rt::finite(total + z)?)?, 5i64)?)
                | rt::int_lshift(rt::int_float(rt::finite(total + y)?)?, 7i64)?)
                | rt::int_lshift(rt::int_float(rt::finite(total + x)?)?, 9i64)?);
        } else {
            let (mut z, mut w): (f64, f64) = {
                let __tuple_values = rt::list_slice(&inside, 2i64, i64::MAX);
                if __tuple_values.len() != 2 {
                    return Err("tuple length mismatch".into());
                }
                (
                    rt::at(&__tuple_values, 0i64)?,
                    rt::at(&__tuple_values, 1i64)?,
                )
            };
            key = ((((((((((rt::int_float(rt::finite(
                rt::finite(z - w)? + ((1i64) as f64),
            )?)? | rt::int_lshift(
                rt::int_float(rt::finite(rt::finite(y - z)? + ((1i64) as f64))?)?,
                1i64,
            )?) | rt::int_lshift(
                rt::int_float(rt::finite(rt::finite(y - w)? + ((1i64) as f64))?)?,
                2i64,
            )?) | rt::int_lshift(
                rt::int_float(rt::finite(rt::finite(x - y)? + ((1i64) as f64))?)?,
                3i64,
            )?) | rt::int_lshift(
                rt::int_float(rt::finite(rt::finite(x - z)? + ((1i64) as f64))?)?,
                4i64,
            )?) | rt::int_lshift(
                rt::int_float(rt::finite(rt::finite(x - w)? + ((1i64) as f64))?)?,
                5i64,
            )?) | rt::int_lshift(rt::int_float(total)?, 6i64)?)
                | rt::int_lshift(rt::int_float(rt::finite(total + w)?)?, 8i64)?)
                | rt::int_lshift(rt::int_float(rt::finite(total + z)?)?, 11i64)?)
                | rt::int_lshift(rt::int_float(rt::finite(total + y)?)?, 14i64)?)
                | rt::int_lshift(rt::int_float(rt::finite(total + x)?)?, 17i64)?);
        }
    }
    let mut value: f64 = 0.0f64;
    let mut gradient: Vec<i64> = ({ static __CONSTANT_py__strategy__noise__escaped_5f4752414449454e5453: std::sync::OnceLock<indexmap::IndexMap<i64, Vec<i64>>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__noise__escaped_5f4752414449454e5453.get().is_none() { let __constant_value = [(2i64, { static __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__GRADIENTS_2: std::sync::OnceLock<Vec<i64>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__GRADIENTS_2.get().is_none() { let __constant_value = vec![5i64, 2i64, 2i64, 5i64, (5i64).checked_neg().ok_or("integer overflow")?, 2i64, (2i64).checked_neg().ok_or("integer overflow")?, 5i64, 5i64, (2i64).checked_neg().ok_or("integer overflow")?, 2i64, (5i64).checked_neg().ok_or("integer overflow")?, (5i64).checked_neg().ok_or("integer overflow")?, (2i64).checked_neg().ok_or("integer overflow")?, (2i64).checked_neg().ok_or("integer overflow")?, (5i64).checked_neg().ok_or("integer overflow")?]; let _ = __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__GRADIENTS_2.set(__constant_value); } __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__GRADIENTS_2.get().ok_or("missing module constant")?.clone() }), (3i64, { static __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__GRADIENTS_3: std::sync::OnceLock<Vec<i64>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__GRADIENTS_3.get().is_none() { let __constant_value = vec![(11i64).checked_neg().ok_or("integer overflow")?, 4i64, 4i64, (4i64).checked_neg().ok_or("integer overflow")?, 11i64, 4i64, (4i64).checked_neg().ok_or("integer overflow")?, 4i64, 11i64, 11i64, 4i64, 4i64, 4i64, 11i64, 4i64, 4i64, 4i64, 11i64, (11i64).checked_neg().ok_or("integer overflow")?, (4i64).checked_neg().ok_or("integer overflow")?, 4i64, (4i64).checked_neg().ok_or("integer overflow")?, (11i64).checked_neg().ok_or("integer overflow")?, 4i64, (4i64).checked_neg().ok_or("integer overflow")?, (4i64).checked_neg().ok_or("integer overflow")?, 11i64, 11i64, (4i64).checked_neg().ok_or("integer overflow")?, 4i64, 4i64, (11i64).checked_neg().ok_or("integer overflow")?, 4i64, 4i64, (4i64).checked_neg().ok_or("integer overflow")?, 11i64, (11i64).checked_neg().ok_or("integer overflow")?, 4i64, (4i64).checked_neg().ok_or("integer overflow")?, (4i64).checked_neg().ok_or("integer overflow")?, 11i64, (4i64).checked_neg().ok_or("integer overflow")?, (4i64).checked_neg().ok_or("integer overflow")?, 4i64, (11i64).checked_neg().ok_or("integer overflow")?, 11i64, 4i64, (4i64).checked_neg().ok_or("integer overflow")?, 4i64, 11i64, (4i64).checked_neg().ok_or("integer overflow")?, 4i64, 4i64, (11i64).checked_neg().ok_or("integer overflow")?, (11i64).checked_neg().ok_or("integer overflow")?, (4i64).checked_neg().ok_or("integer overflow")?, (4i64).checked_neg().ok_or("integer overflow")?, (4i64).checked_neg().ok_or("integer overflow")?, (11i64).checked_neg().ok_or("integer overflow")?, (4i64).checked_neg().ok_or("integer overflow")?, (4i64).checked_neg().ok_or("integer overflow")?, (4i64).checked_neg().ok_or("integer overflow")?, (11i64).checked_neg().ok_or("integer overflow")?, 11i64, (4i64).checked_neg().ok_or("integer overflow")?, (4i64).checked_neg().ok_or("integer overflow")?, 4i64, (11i64).checked_neg().ok_or("integer overflow")?, (4i64).checked_neg().ok_or("integer overflow")?, 4i64, (4i64).checked_neg().ok_or("integer overflow")?, (11i64).checked_neg().ok_or("integer overflow")?]; let _ = __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__GRADIENTS_3.set(__constant_value); } __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__GRADIENTS_3.get().ok_or("missing module constant")?.clone() }), (4i64, { static __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__GRADIENTS_4: std::sync::OnceLock<Vec<i64>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__GRADIENTS_4.get().is_none() { let __constant_value = vec![3i64, 1i64, 1i64, 1i64, 1i64, 3i64, 1i64, 1i64, 1i64, 1i64, 3i64, 1i64, 1i64, 1i64, 1i64, 3i64, (3i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 3i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 3i64, 3i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, (3i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 3i64, (3i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 3i64, 3i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 3i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, (3i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, (3i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (3i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, 3i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, (3i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, (3i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, 3i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 3i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 3i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, (3i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 3i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, (3i64).checked_neg().ok_or("integer overflow")?, 3i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (3i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (3i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (3i64).checked_neg().ok_or("integer overflow")?, 3i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 3i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, (3i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (3i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, 3i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (3i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (1i64).checked_neg().ok_or("integer overflow")?, (3i64).checked_neg().ok_or("integer overflow")?]; let _ = __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__GRADIENTS_4.set(__constant_value); } __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__GRADIENTS_4.get().ok_or("missing module constant")?.clone() })].into_iter().collect::<indexmap::IndexMap<_, _>>(); let _ = __CONSTANT_py__strategy__noise__escaped_5f4752414449454e5453.set(__constant_value); } __CONSTANT_py__strategy__noise__escaped_5f4752414449454e5453.get().ok_or("missing module constant")? }).get(&(dimension)).ok_or("missing dict key")?.clone();
    for mut contribution in {
        let __mapping = ({ static __CONSTANT_py__strategy__noise__escaped_5f4c4f4f4b555053: std::sync::OnceLock<indexmap::IndexMap<i64, indexmap::IndexMap<i64, Vec<_Contribution>>>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__noise__escaped_5f4c4f4f4b555053.get().is_none() { let __constant_value = [(2i64, _lookup(2i64, { static __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__BASE_2: std::sync::OnceLock<Vec<Vec<i64>>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__BASE_2.get().is_none() { let __constant_value = vec![vec![1i64, 1i64, 0i64, 1i64, 0i64, 1i64, 0i64, 0i64, 0i64], vec![1i64, 1i64, 0i64, 1i64, 0i64, 1i64, 2i64, 1i64, 1i64]]; let _ = __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__BASE_2.set(__constant_value); } __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__BASE_2.get().ok_or("missing module constant")? }, { static __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__POINTS_2: std::sync::OnceLock<Vec<i64>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__POINTS_2.get().is_none() { let __constant_value = vec![0i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 2i64, 1i64, 1i64, 1i64, 2i64, 2i64, 0i64, 1i64, 2i64, 0i64, 2i64, 1i64, 0i64, 0i64, 0i64]; let _ = __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__POINTS_2.set(__constant_value); } __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__POINTS_2.get().ok_or("missing module constant")? }, { static __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__LOOKUP_2: std::sync::OnceLock<Vec<i64>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__LOOKUP_2.get().is_none() { let __constant_value = vec![0i64, 1i64, 1i64, 0i64, 4i64, 1i64, 17i64, 0i64, 20i64, 2i64, 21i64, 2i64, 22i64, 5i64, 23i64, 5i64, 26i64, 4i64, 39i64, 3i64, 42i64, 4i64, 43i64, 3i64]; let _ = __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__LOOKUP_2.set(__constant_value); } __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__LOOKUP_2.get().ok_or("missing module constant")? })?), (3i64, _lookup(3i64, { static __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__BASE_3: std::sync::OnceLock<Vec<Vec<i64>>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__BASE_3.get().is_none() { let __constant_value = vec![vec![0i64, 0i64, 0i64, 0i64, 1i64, 1i64, 0i64, 0i64, 1i64, 0i64, 1i64, 0i64, 1i64, 0i64, 0i64, 1i64], vec![2i64, 1i64, 1i64, 0i64, 2i64, 1i64, 0i64, 1i64, 2i64, 0i64, 1i64, 1i64, 3i64, 1i64, 1i64, 1i64], vec![1i64, 1i64, 0i64, 0i64, 1i64, 0i64, 1i64, 0i64, 1i64, 0i64, 0i64, 1i64, 2i64, 1i64, 1i64, 0i64, 2i64, 1i64, 0i64, 1i64, 2i64, 0i64, 1i64, 1i64]]; let _ = __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__BASE_3.set(__constant_value); } __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__BASE_3.get().ok_or("missing module constant")? }, { static __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__POINTS_3: std::sync::OnceLock<Vec<i64>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__POINTS_3.get().is_none() { let __constant_value = vec![0i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 0i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 0i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 2i64, 1i64, 1i64, 0i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 2i64, 1i64, 0i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 2i64, 0i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, 3i64, 2i64, 1i64, 0i64, 3i64, 1i64, 2i64, 0i64, 1i64, 3i64, 2i64, 0i64, 1i64, 3i64, 1i64, 0i64, 2i64, 1i64, 3i64, 0i64, 2i64, 1i64, 3i64, 0i64, 1i64, 2i64, 1i64, 1i64, 1i64, 0i64, 0i64, 2i64, 2i64, 0i64, 0i64, 1i64, 1i64, 0i64, 1i64, 0i64, 2i64, 0i64, 2i64, 0i64, 1i64, 1i64, 0i64, 0i64, 1i64, 2i64, 0i64, 0i64, 2i64, 2i64, 0i64, 0i64, 0i64, 0i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 2i64, 0i64, 0i64, 0i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 2i64, 0i64, 0i64, 0i64, 0i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 2i64, 3i64, 1i64, 1i64, 1i64, 2i64, 0i64, 0i64, 2i64, 2i64, 3i64, 1i64, 1i64, 1i64, 2i64, 2i64, 0i64, 0i64, 2i64, 3i64, 1i64, 1i64, 1i64, 2i64, 0i64, 2i64, 0i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 2i64, 0i64, 0i64, 2i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 2i64, 2i64, 0i64, 0i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 2i64, 0i64, 0i64, 2i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 2i64, 0i64, 2i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 2i64, 2i64, 0i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 2i64, 0i64, 2i64, 0i64]; let _ = __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__POINTS_3.set(__constant_value); } __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__POINTS_3.get().ok_or("missing module constant")? }, { static __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__LOOKUP_3: std::sync::OnceLock<Vec<i64>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__LOOKUP_3.get().is_none() { let __constant_value = vec![0i64, 2i64, 1i64, 1i64, 2i64, 2i64, 5i64, 1i64, 6i64, 0i64, 7i64, 0i64, 32i64, 2i64, 34i64, 2i64, 129i64, 1i64, 133i64, 1i64, 160i64, 5i64, 161i64, 5i64, 518i64, 0i64, 519i64, 0i64, 546i64, 4i64, 550i64, 4i64, 645i64, 3i64, 647i64, 3i64, 672i64, 5i64, 673i64, 5i64, 674i64, 4i64, 677i64, 3i64, 678i64, 4i64, 679i64, 3i64, 680i64, 13i64, 681i64, 13i64, 682i64, 12i64, 685i64, 14i64, 686i64, 12i64, 687i64, 14i64, 712i64, 20i64, 714i64, 18i64, 809i64, 21i64, 813i64, 23i64, 840i64, 20i64, 841i64, 21i64, 1198i64, 19i64, 1199i64, 22i64, 1226i64, 18i64, 1230i64, 19i64, 1325i64, 23i64, 1327i64, 22i64, 1352i64, 15i64, 1353i64, 17i64, 1354i64, 15i64, 1357i64, 17i64, 1358i64, 16i64, 1359i64, 16i64, 1360i64, 11i64, 1361i64, 10i64, 1362i64, 11i64, 1365i64, 10i64, 1366i64, 9i64, 1367i64, 9i64, 1392i64, 11i64, 1394i64, 11i64, 1489i64, 10i64, 1493i64, 10i64, 1520i64, 8i64, 1521i64, 8i64, 1878i64, 9i64, 1879i64, 9i64, 1906i64, 7i64, 1910i64, 7i64, 2005i64, 6i64, 2007i64, 6i64, 2032i64, 8i64, 2033i64, 8i64, 2034i64, 7i64, 2037i64, 6i64, 2038i64, 7i64, 2039i64, 6i64]; let _ = __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__LOOKUP_3.set(__constant_value); } __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__LOOKUP_3.get().ok_or("missing module constant")? })?), (4i64, _lookup(4i64, { static __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__BASE_4: std::sync::OnceLock<Vec<Vec<i64>>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__BASE_4.get().is_none() { let __constant_value = vec![vec![0i64, 0i64, 0i64, 0i64, 0i64, 1i64, 1i64, 0i64, 0i64, 0i64, 1i64, 0i64, 1i64, 0i64, 0i64, 1i64, 0i64, 0i64, 1i64, 0i64, 1i64, 0i64, 0i64, 0i64, 1i64], vec![3i64, 1i64, 1i64, 1i64, 0i64, 3i64, 1i64, 1i64, 0i64, 1i64, 3i64, 1i64, 0i64, 1i64, 1i64, 3i64, 0i64, 1i64, 1i64, 1i64, 4i64, 1i64, 1i64, 1i64, 1i64], vec![1i64, 1i64, 0i64, 0i64, 0i64, 1i64, 0i64, 1i64, 0i64, 0i64, 1i64, 0i64, 0i64, 1i64, 0i64, 1i64, 0i64, 0i64, 0i64, 1i64, 2i64, 1i64, 1i64, 0i64, 0i64, 2i64, 1i64, 0i64, 1i64, 0i64, 2i64, 1i64, 0i64, 0i64, 1i64, 2i64, 0i64, 1i64, 1i64, 0i64, 2i64, 0i64, 1i64, 0i64, 1i64, 2i64, 0i64, 0i64, 1i64, 1i64], vec![3i64, 1i64, 1i64, 1i64, 0i64, 3i64, 1i64, 1i64, 0i64, 1i64, 3i64, 1i64, 0i64, 1i64, 1i64, 3i64, 0i64, 1i64, 1i64, 1i64, 2i64, 1i64, 1i64, 0i64, 0i64, 2i64, 1i64, 0i64, 1i64, 0i64, 2i64, 1i64, 0i64, 0i64, 1i64, 2i64, 0i64, 1i64, 1i64, 0i64, 2i64, 0i64, 1i64, 0i64, 1i64, 2i64, 0i64, 0i64, 1i64, 1i64]]; let _ = __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__BASE_4.set(__constant_value); } __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__BASE_4.get().ok_or("missing module constant")? }, { static __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__POINTS_4: std::sync::OnceLock<Vec<i64>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__POINTS_4.get().is_none() { let __constant_value = vec![0i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, 0i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, 1i64, 0i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 0i64, 0i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, 0i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 0i64, 0i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 0i64, 0i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, 1i64, 0i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 0i64, 0i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 2i64, 1i64, 1i64, 0i64, 0i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 1i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 2i64, 1i64, 0i64, 1i64, 0i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 1i64, 1i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 2i64, 0i64, 1i64, 1i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 0i64, 1i64, 0i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 2i64, 1i64, 0i64, 0i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 1i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 2i64, 0i64, 1i64, 0i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 1i64, 1i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 2i64, 0i64, 0i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 1i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, 4i64, 2i64, 1i64, 1i64, 0i64, 4i64, 1i64, 2i64, 1i64, 0i64, 4i64, 1i64, 1i64, 2i64, 0i64, 1i64, 4i64, 2i64, 1i64, 0i64, 1i64, 4i64, 1i64, 2i64, 0i64, 1i64, 4i64, 1i64, 1i64, 0i64, 2i64, 1i64, 4i64, 2i64, 0i64, 1i64, 1i64, 4i64, 1i64, 0i64, 2i64, 1i64, 4i64, 1i64, 0i64, 1i64, 2i64, 1i64, 4i64, 0i64, 2i64, 1i64, 1i64, 4i64, 0i64, 1i64, 2i64, 1i64, 4i64, 0i64, 1i64, 1i64, 2i64, 1i64, 2i64, 1i64, 1i64, 0i64, 0i64, 3i64, 2i64, 1i64, 0i64, 0i64, 3i64, 1i64, 2i64, 0i64, 0i64, 1i64, 2i64, 1i64, 0i64, 1i64, 0i64, 3i64, 2i64, 0i64, 1i64, 0i64, 3i64, 1i64, 0i64, 2i64, 0i64, 1i64, 2i64, 0i64, 1i64, 1i64, 0i64, 3i64, 0i64, 2i64, 1i64, 0i64, 3i64, 0i64, 1i64, 2i64, 0i64, 1i64, 2i64, 1i64, 0i64, 0i64, 1i64, 3i64, 2i64, 0i64, 0i64, 1i64, 3i64, 1i64, 0i64, 0i64, 2i64, 1i64, 2i64, 0i64, 1i64, 0i64, 1i64, 3i64, 0i64, 2i64, 0i64, 1i64, 3i64, 0i64, 1i64, 0i64, 2i64, 1i64, 2i64, 0i64, 0i64, 1i64, 1i64, 3i64, 0i64, 0i64, 2i64, 1i64, 3i64, 0i64, 0i64, 1i64, 2i64, 2i64, 3i64, 1i64, 1i64, 1i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 2i64, 2i64, 0i64, 0i64, 0i64, 2i64, 3i64, 1i64, 1i64, 0i64, 1i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 2i64, 2i64, 0i64, 0i64, 0i64, 2i64, 3i64, 1i64, 0i64, 1i64, 1i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 2i64, 2i64, 0i64, 0i64, 0i64, 2i64, 3i64, 1i64, 1i64, 1i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 2i64, 0i64, 2i64, 0i64, 0i64, 2i64, 3i64, 1i64, 1i64, 0i64, 1i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 2i64, 0i64, 2i64, 0i64, 0i64, 2i64, 3i64, 0i64, 1i64, 1i64, 1i64, 2i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, 2i64, 0i64, 2i64, 0i64, 0i64, 2i64, 3i64, 1i64, 1i64, 1i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 2i64, 0i64, 0i64, 2i64, 0i64, 2i64, 3i64, 1i64, 0i64, 1i64, 1i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 2i64, 0i64, 0i64, 2i64, 0i64, 2i64, 3i64, 0i64, 1i64, 1i64, 1i64, 2i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, 2i64, 0i64, 0i64, 2i64, 0i64, 2i64, 3i64, 1i64, 1i64, 0i64, 1i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 2i64, 0i64, 0i64, 0i64, 2i64, 2i64, 3i64, 1i64, 0i64, 1i64, 1i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 2i64, 0i64, 0i64, 0i64, 2i64, 2i64, 3i64, 0i64, 1i64, 1i64, 1i64, 2i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, 2i64, 0i64, 0i64, 0i64, 2i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 1i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, 0i64, 0i64, 0i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 1i64, 1i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, 0i64, 0i64, 0i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 0i64, 1i64, 0i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 0i64, 0i64, 0i64, 0i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 1i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 0i64, 0i64, 0i64, 0i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 1i64, 1i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 0i64, 0i64, 0i64, 0i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 1i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 0i64, 0i64, 0i64, 0i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 1i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 2i64, 2i64, 0i64, 0i64, 0i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 1i64, 1i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 2i64, 2i64, 0i64, 0i64, 0i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 1i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 2i64, 2i64, 0i64, 0i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 1i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 2i64, 0i64, 2i64, 0i64, 0i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 0i64, 1i64, 0i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 2i64, 0i64, 2i64, 0i64, 0i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 1i64, 1i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 2i64, 0i64, 2i64, 0i64, 0i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 1i64, 1i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 2i64, 0i64, 0i64, 2i64, 0i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 0i64, 1i64, 0i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 2i64, 0i64, 0i64, 2i64, 0i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 1i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 2i64, 0i64, 0i64, 2i64, 0i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 1i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 2i64, 0i64, 0i64, 0i64, 2i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 0i64, 1i64, 1i64, 0i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 2i64, 0i64, 0i64, 0i64, 2i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 0i64, 1i64, 1i64, 1i64, 0i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 2i64, 0i64, 0i64, 0i64, 2i64, 3i64, 1i64, 1i64, 0i64, 0i64, 0i64, 2i64, 2i64, 0i64, 0i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, 1i64, 0i64, 1i64, 0i64, 0i64, 2i64, 0i64, 2i64, 0i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, 1i64, 0i64, 0i64, 1i64, 0i64, 2i64, 0i64, 0i64, 2i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, 1i64, 1i64, 0i64, 0i64, 0i64, 2i64, 2i64, 0i64, 0i64, 0i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 3i64, 1i64, 0i64, 1i64, 0i64, 0i64, 2i64, 0i64, 2i64, 0i64, 0i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 3i64, 1i64, 0i64, 0i64, 0i64, 1i64, 2i64, 0i64, 0i64, 0i64, 2i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 3i64, 1i64, 1i64, 0i64, 0i64, 0i64, 2i64, 2i64, 0i64, 0i64, 0i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 3i64, 1i64, 0i64, 0i64, 1i64, 0i64, 2i64, 0i64, 0i64, 2i64, 0i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 3i64, 1i64, 0i64, 0i64, 0i64, 1i64, 2i64, 0i64, 0i64, 0i64, 2i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 3i64, 1i64, 0i64, 1i64, 0i64, 0i64, 2i64, 0i64, 2i64, 0i64, 0i64, 2i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, 3i64, 1i64, 0i64, 0i64, 1i64, 0i64, 2i64, 0i64, 0i64, 2i64, 0i64, 2i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, 3i64, 1i64, 0i64, 0i64, 0i64, 1i64, 2i64, 0i64, 0i64, 0i64, 2i64, 2i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, 3i64, 3i64, 2i64, 1i64, 0i64, 0i64, 3i64, 1i64, 2i64, 0i64, 0i64, 4i64, 1i64, 1i64, 1i64, 1i64, 3i64, 3i64, 2i64, 0i64, 1i64, 0i64, 3i64, 1i64, 0i64, 2i64, 0i64, 4i64, 1i64, 1i64, 1i64, 1i64, 3i64, 3i64, 0i64, 2i64, 1i64, 0i64, 3i64, 0i64, 1i64, 2i64, 0i64, 4i64, 1i64, 1i64, 1i64, 1i64, 3i64, 3i64, 2i64, 0i64, 0i64, 1i64, 3i64, 1i64, 0i64, 0i64, 2i64, 4i64, 1i64, 1i64, 1i64, 1i64, 3i64, 3i64, 0i64, 2i64, 0i64, 1i64, 3i64, 0i64, 1i64, 0i64, 2i64, 4i64, 1i64, 1i64, 1i64, 1i64, 3i64, 3i64, 0i64, 0i64, 2i64, 1i64, 3i64, 0i64, 0i64, 1i64, 2i64, 4i64, 1i64, 1i64, 1i64, 1i64, 3i64, 3i64, 2i64, 1i64, 0i64, 0i64, 3i64, 1i64, 2i64, 0i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, 3i64, 2i64, 0i64, 1i64, 0i64, 3i64, 1i64, 0i64, 2i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, 3i64, 0i64, 2i64, 1i64, 0i64, 3i64, 0i64, 1i64, 2i64, 0i64, 2i64, 1i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 3i64, 3i64, 2i64, 1i64, 0i64, 0i64, 3i64, 1i64, 2i64, 0i64, 0i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 3i64, 3i64, 2i64, 0i64, 0i64, 1i64, 3i64, 1i64, 0i64, 0i64, 2i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 3i64, 3i64, 0i64, 2i64, 0i64, 1i64, 3i64, 0i64, 1i64, 0i64, 2i64, 2i64, 1i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 3i64, 3i64, 2i64, 0i64, 1i64, 0i64, 3i64, 1i64, 0i64, 2i64, 0i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 3i64, 3i64, 2i64, 0i64, 0i64, 1i64, 3i64, 1i64, 0i64, 0i64, 2i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 3i64, 3i64, 0i64, 0i64, 2i64, 1i64, 3i64, 0i64, 0i64, 1i64, 2i64, 2i64, 1i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 3i64, 3i64, 0i64, 2i64, 1i64, 0i64, 3i64, 0i64, 1i64, 2i64, 0i64, 2i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, 3i64, 3i64, 0i64, 2i64, 0i64, 1i64, 3i64, 0i64, 1i64, 0i64, 2i64, 2i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64, 3i64, 3i64, 0i64, 0i64, 2i64, 1i64, 3i64, 0i64, 0i64, 1i64, 2i64, 2i64, (1i64).checked_neg().ok_or("integer overflow")?, 1i64, 1i64, 1i64]; let _ = __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__POINTS_4.set(__constant_value); } __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__POINTS_4.get().ok_or("missing module constant")? }, { static __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__LOOKUP_4: std::sync::OnceLock<Vec<i64>> = std::sync::OnceLock::new(); if __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__LOOKUP_4.get().is_none() { let __constant_value = vec![0i64, 3i64, 1i64, 2i64, 2i64, 3i64, 5i64, 2i64, 6i64, 1i64, 7i64, 1i64, 8i64, 3i64, 9i64, 2i64, 10i64, 3i64, 13i64, 2i64, 16i64, 3i64, 18i64, 3i64, 22i64, 1i64, 23i64, 1i64, 24i64, 3i64, 26i64, 3i64, 33i64, 2i64, 37i64, 2i64, 38i64, 1i64, 39i64, 1i64, 41i64, 2i64, 45i64, 2i64, 54i64, 1i64, 55i64, 1i64, 56i64, 0i64, 57i64, 0i64, 58i64, 0i64, 59i64, 0i64, 60i64, 0i64, 61i64, 0i64, 62i64, 0i64, 63i64, 0i64, 256i64, 3i64, 258i64, 3i64, 264i64, 3i64, 266i64, 3i64, 272i64, 3i64, 274i64, 3i64, 280i64, 3i64, 282i64, 3i64, 2049i64, 2i64, 2053i64, 2i64, 2057i64, 2i64, 2061i64, 2i64, 2081i64, 2i64, 2085i64, 2i64, 2089i64, 2i64, 2093i64, 2i64, 2304i64, 9i64, 2305i64, 9i64, 2312i64, 9i64, 2313i64, 9i64, 16390i64, 1i64, 16391i64, 1i64, 16406i64, 1i64, 16407i64, 1i64, 16422i64, 1i64, 16423i64, 1i64, 16438i64, 1i64, 16439i64, 1i64, 16642i64, 8i64, 16646i64, 8i64, 16658i64, 8i64, 16662i64, 8i64, 18437i64, 6i64, 18439i64, 6i64, 18469i64, 6i64, 18471i64, 6i64, 18688i64, 9i64, 18689i64, 9i64, 18690i64, 8i64, 18693i64, 6i64, 18694i64, 8i64, 18695i64, 6i64, 18696i64, 9i64, 18697i64, 9i64, 18706i64, 8i64, 18710i64, 8i64, 18725i64, 6i64, 18727i64, 6i64, 131128i64, 0i64, 131129i64, 0i64, 131130i64, 0i64, 131131i64, 0i64, 131132i64, 0i64, 131133i64, 0i64, 131134i64, 0i64, 131135i64, 0i64, 131352i64, 7i64, 131354i64, 7i64, 131384i64, 7i64, 131386i64, 7i64, 133161i64, 5i64, 133165i64, 5i64, 133177i64, 5i64, 133181i64, 5i64, 133376i64, 9i64, 133377i64, 9i64, 133384i64, 9i64, 133385i64, 9i64, 133400i64, 7i64, 133402i64, 7i64, 133417i64, 5i64, 133421i64, 5i64, 133432i64, 7i64, 133433i64, 5i64, 133434i64, 7i64, 133437i64, 5i64, 147510i64, 4i64, 147511i64, 4i64, 147518i64, 4i64, 147519i64, 4i64, 147714i64, 8i64, 147718i64, 8i64, 147730i64, 8i64, 147734i64, 8i64, 147736i64, 7i64, 147738i64, 7i64, 147766i64, 4i64, 147767i64, 4i64, 147768i64, 7i64, 147770i64, 7i64, 147774i64, 4i64, 147775i64, 4i64, 149509i64, 6i64, 149511i64, 6i64, 149541i64, 6i64, 149543i64, 6i64, 149545i64, 5i64, 149549i64, 5i64, 149558i64, 4i64, 149559i64, 4i64, 149561i64, 5i64, 149565i64, 5i64, 149566i64, 4i64, 149567i64, 4i64, 149760i64, 9i64, 149761i64, 9i64, 149762i64, 8i64, 149765i64, 6i64, 149766i64, 8i64, 149767i64, 6i64, 149768i64, 9i64, 149769i64, 9i64, 149778i64, 8i64, 149782i64, 8i64, 149784i64, 7i64, 149786i64, 7i64, 149797i64, 6i64, 149799i64, 6i64, 149801i64, 5i64, 149805i64, 5i64, 149814i64, 4i64, 149815i64, 4i64, 149816i64, 7i64, 149817i64, 5i64, 149818i64, 7i64, 149821i64, 5i64, 149822i64, 4i64, 149823i64, 4i64, 149824i64, 37i64, 149825i64, 37i64, 149826i64, 36i64, 149829i64, 34i64, 149830i64, 36i64, 149831i64, 34i64, 149832i64, 37i64, 149833i64, 37i64, 149842i64, 36i64, 149846i64, 36i64, 149848i64, 35i64, 149850i64, 35i64, 149861i64, 34i64, 149863i64, 34i64, 149865i64, 33i64, 149869i64, 33i64, 149878i64, 32i64, 149879i64, 32i64, 149880i64, 35i64, 149881i64, 33i64, 149882i64, 35i64, 149885i64, 33i64, 149886i64, 32i64, 149887i64, 32i64, 150080i64, 49i64, 150082i64, 48i64, 150088i64, 49i64, 150098i64, 48i64, 150104i64, 47i64, 150106i64, 47i64, 151873i64, 46i64, 151877i64, 45i64, 151881i64, 46i64, 151909i64, 45i64, 151913i64, 44i64, 151917i64, 44i64, 152128i64, 49i64, 152129i64, 46i64, 152136i64, 49i64, 152137i64, 46i64, 166214i64, 43i64, 166215i64, 42i64, 166230i64, 43i64, 166247i64, 42i64, 166262i64, 41i64, 166263i64, 41i64, 166466i64, 48i64, 166470i64, 43i64, 166482i64, 48i64, 166486i64, 43i64, 168261i64, 45i64, 168263i64, 42i64, 168293i64, 45i64, 168295i64, 42i64, 168512i64, 31i64, 168513i64, 28i64, 168514i64, 31i64, 168517i64, 28i64, 168518i64, 25i64, 168519i64, 25i64, 280952i64, 40i64, 280953i64, 39i64, 280954i64, 40i64, 280957i64, 39i64, 280958i64, 38i64, 280959i64, 38i64, 281176i64, 47i64, 281178i64, 47i64, 281208i64, 40i64, 281210i64, 40i64, 282985i64, 44i64, 282989i64, 44i64, 283001i64, 39i64, 283005i64, 39i64, 283208i64, 30i64, 283209i64, 27i64, 283224i64, 30i64, 283241i64, 27i64, 283256i64, 22i64, 283257i64, 22i64, 297334i64, 41i64, 297335i64, 41i64, 297342i64, 38i64, 297343i64, 38i64, 297554i64, 29i64, 297558i64, 24i64, 297562i64, 29i64, 297590i64, 24i64, 297594i64, 21i64, 297598i64, 21i64, 299365i64, 26i64, 299367i64, 23i64, 299373i64, 26i64, 299383i64, 23i64, 299389i64, 20i64, 299391i64, 20i64, 299584i64, 31i64, 299585i64, 28i64, 299586i64, 31i64, 299589i64, 28i64, 299590i64, 25i64, 299591i64, 25i64, 299592i64, 30i64, 299593i64, 27i64, 299602i64, 29i64, 299606i64, 24i64, 299608i64, 30i64, 299610i64, 29i64, 299621i64, 26i64, 299623i64, 23i64, 299625i64, 27i64, 299629i64, 26i64, 299638i64, 24i64, 299639i64, 23i64, 299640i64, 22i64, 299641i64, 22i64, 299642i64, 21i64, 299645i64, 20i64, 299646i64, 21i64, 299647i64, 20i64, 299648i64, 61i64, 299649i64, 60i64, 299650i64, 61i64, 299653i64, 60i64, 299654i64, 59i64, 299655i64, 59i64, 299656i64, 58i64, 299657i64, 57i64, 299666i64, 55i64, 299670i64, 54i64, 299672i64, 58i64, 299674i64, 55i64, 299685i64, 52i64, 299687i64, 51i64, 299689i64, 57i64, 299693i64, 52i64, 299702i64, 54i64, 299703i64, 51i64, 299704i64, 56i64, 299705i64, 56i64, 299706i64, 53i64, 299709i64, 50i64, 299710i64, 53i64, 299711i64, 50i64, 299904i64, 61i64, 299906i64, 61i64, 299912i64, 58i64, 299922i64, 55i64, 299928i64, 58i64, 299930i64, 55i64, 301697i64, 60i64, 301701i64, 60i64, 301705i64, 57i64, 301733i64, 52i64, 301737i64, 57i64, 301741i64, 52i64, 301952i64, 79i64, 301953i64, 79i64, 301960i64, 76i64, 301961i64, 76i64, 316038i64, 59i64, 316039i64, 59i64, 316054i64, 54i64, 316071i64, 51i64, 316086i64, 54i64, 316087i64, 51i64, 316290i64, 78i64, 316294i64, 78i64, 316306i64, 73i64, 316310i64, 73i64, 318085i64, 77i64, 318087i64, 77i64, 318117i64, 70i64, 318119i64, 70i64, 318336i64, 79i64, 318337i64, 79i64, 318338i64, 78i64, 318341i64, 77i64, 318342i64, 78i64, 318343i64, 77i64, 430776i64, 56i64, 430777i64, 56i64, 430778i64, 53i64, 430781i64, 50i64, 430782i64, 53i64, 430783i64, 50i64, 431000i64, 75i64, 431002i64, 72i64, 431032i64, 75i64, 431034i64, 72i64, 432809i64, 74i64, 432813i64, 69i64, 432825i64, 74i64, 432829i64, 69i64, 433032i64, 76i64, 433033i64, 76i64, 433048i64, 75i64, 433065i64, 74i64, 433080i64, 75i64, 433081i64, 74i64, 447158i64, 71i64, 447159i64, 68i64, 447166i64, 71i64, 447167i64, 68i64, 447378i64, 73i64, 447382i64, 73i64, 447386i64, 72i64, 447414i64, 71i64, 447418i64, 72i64, 447422i64, 71i64, 449189i64, 70i64, 449191i64, 70i64, 449197i64, 69i64, 449207i64, 68i64, 449213i64, 69i64, 449215i64, 68i64, 449408i64, 67i64, 449409i64, 67i64, 449410i64, 66i64, 449413i64, 64i64, 449414i64, 66i64, 449415i64, 64i64, 449416i64, 67i64, 449417i64, 67i64, 449426i64, 66i64, 449430i64, 66i64, 449432i64, 65i64, 449434i64, 65i64, 449445i64, 64i64, 449447i64, 64i64, 449449i64, 63i64, 449453i64, 63i64, 449462i64, 62i64, 449463i64, 62i64, 449464i64, 65i64, 449465i64, 63i64, 449466i64, 65i64, 449469i64, 63i64, 449470i64, 62i64, 449471i64, 62i64, 449472i64, 19i64, 449473i64, 19i64, 449474i64, 18i64, 449477i64, 16i64, 449478i64, 18i64, 449479i64, 16i64, 449480i64, 19i64, 449481i64, 19i64, 449490i64, 18i64, 449494i64, 18i64, 449496i64, 17i64, 449498i64, 17i64, 449509i64, 16i64, 449511i64, 16i64, 449513i64, 15i64, 449517i64, 15i64, 449526i64, 14i64, 449527i64, 14i64, 449528i64, 17i64, 449529i64, 15i64, 449530i64, 17i64, 449533i64, 15i64, 449534i64, 14i64, 449535i64, 14i64, 449728i64, 19i64, 449729i64, 19i64, 449730i64, 18i64, 449734i64, 18i64, 449736i64, 19i64, 449737i64, 19i64, 449746i64, 18i64, 449750i64, 18i64, 449752i64, 17i64, 449754i64, 17i64, 449784i64, 17i64, 449786i64, 17i64, 451520i64, 19i64, 451521i64, 19i64, 451525i64, 16i64, 451527i64, 16i64, 451528i64, 19i64, 451529i64, 19i64, 451557i64, 16i64, 451559i64, 16i64, 451561i64, 15i64, 451565i64, 15i64, 451577i64, 15i64, 451581i64, 15i64, 451776i64, 19i64, 451777i64, 19i64, 451784i64, 19i64, 451785i64, 19i64, 465858i64, 18i64, 465861i64, 16i64, 465862i64, 18i64, 465863i64, 16i64, 465874i64, 18i64, 465878i64, 18i64, 465893i64, 16i64, 465895i64, 16i64, 465910i64, 14i64, 465911i64, 14i64, 465918i64, 14i64, 465919i64, 14i64, 466114i64, 18i64, 466118i64, 18i64, 466130i64, 18i64, 466134i64, 18i64, 467909i64, 16i64, 467911i64, 16i64, 467941i64, 16i64, 467943i64, 16i64, 468160i64, 13i64, 468161i64, 13i64, 468162i64, 13i64, 468163i64, 13i64, 468164i64, 13i64, 468165i64, 13i64, 468166i64, 13i64, 468167i64, 13i64, 580568i64, 17i64, 580570i64, 17i64, 580585i64, 15i64, 580589i64, 15i64, 580598i64, 14i64, 580599i64, 14i64, 580600i64, 17i64, 580601i64, 15i64, 580602i64, 17i64, 580605i64, 15i64, 580606i64, 14i64, 580607i64, 14i64, 580824i64, 17i64, 580826i64, 17i64, 580856i64, 17i64, 580858i64, 17i64, 582633i64, 15i64, 582637i64, 15i64, 582649i64, 15i64, 582653i64, 15i64, 582856i64, 12i64, 582857i64, 12i64, 582872i64, 12i64, 582873i64, 12i64, 582888i64, 12i64, 582889i64, 12i64, 582904i64, 12i64, 582905i64, 12i64, 596982i64, 14i64, 596983i64, 14i64, 596990i64, 14i64, 596991i64, 14i64, 597202i64, 11i64, 597206i64, 11i64, 597210i64, 11i64, 597214i64, 11i64, 597234i64, 11i64, 597238i64, 11i64, 597242i64, 11i64, 597246i64, 11i64, 599013i64, 10i64, 599015i64, 10i64, 599021i64, 10i64, 599023i64, 10i64, 599029i64, 10i64, 599031i64, 10i64, 599037i64, 10i64, 599039i64, 10i64, 599232i64, 13i64, 599233i64, 13i64, 599234i64, 13i64, 599235i64, 13i64, 599236i64, 13i64, 599237i64, 13i64, 599238i64, 13i64, 599239i64, 13i64, 599240i64, 12i64, 599241i64, 12i64, 599250i64, 11i64, 599254i64, 11i64, 599256i64, 12i64, 599257i64, 12i64, 599258i64, 11i64, 599262i64, 11i64, 599269i64, 10i64, 599271i64, 10i64, 599272i64, 12i64, 599273i64, 12i64, 599277i64, 10i64, 599279i64, 10i64, 599282i64, 11i64, 599285i64, 10i64, 599286i64, 11i64, 599287i64, 10i64, 599288i64, 12i64, 599289i64, 12i64, 599290i64, 11i64, 599293i64, 10i64, 599294i64, 11i64, 599295i64, 10i64]; let _ = __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__LOOKUP_4.set(__constant_value); } __CONSTANT_py__strategy__escaped_5f6e6f6973655f7461626c6573__LOOKUP_4.get().ok_or("missing module constant")? })?)].into_iter().collect::<indexmap::IndexMap<_, _>>(); let _ = __CONSTANT_py__strategy__noise__escaped_5f4c4f4f4b555053.set(__constant_value); } __CONSTANT_py__strategy__noise__escaped_5f4c4f4f4b555053.get().ok_or("missing module constant")? }).get(&(dimension)).ok_or("missing dict key")?;
        let __key = key;
        let __default = vec![];
        __mapping.get(&__key).cloned().unwrap_or(__default)
    } {
        let mut distances: Vec<f64> = ({
            let mut __comprehension_result_575: Vec<f64> = Vec::new();
            let __comprehension_source_574 = ({
                let __left = delta.clone();
                let __right = (contribution).offset.clone();
                if false && __left.len() != __right.len() {
                    return Err("zip() argument lengths differ".into());
                }
                let mut __result: Vec<(f64, f64)> = Vec::new();
                let __length = __left.len().min(__right.len());
                let mut __left_iter = __left.into_iter();
                let mut __right_iter = __right.into_iter();
                for __index in 0..__length {
                    __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
                }
                __result
            });
            for (axis, offset) in __comprehension_source_574.iter().cloned() {
                __comprehension_result_575.push(rt::finite(axis + offset)?);
            }
            __comprehension_result_575
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        let mut attenuation: f64 = 2.0f64;
        for mut distance in (distances).iter().copied() {
            attenuation = rt::finite(attenuation - rt::finite(distance * distance)?)?;
        }
        if (attenuation <= ((0i64) as f64)) {
            continue;
        }
        let mut index: i64 = 0i64;
        for mut for_target_112_12 in {
            let __left = cell.clone();
            let __right = (contribution).lattice.clone();
            if false && __left.len() != __right.len() {
                return Err("zip() argument lengths differ".into());
            }
            let mut __result: Vec<(i64, i64)> = Vec::new();
            let __length = __left.len().min(__right.len());
            let mut __left_iter = __left.into_iter();
            let mut __right_iter = __right.into_iter();
            for __index in 0..__length {
                __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
            }
            __result
        } {
            let (mut base, mut offset): (i64, i64) = for_target_112_12;
            index = rt::at(
                &(self_).permutation,
                (((index).checked_add(base).ok_or("integer overflow")?)
                    .checked_add(offset)
                    .ok_or("integer overflow")?
                    & 255i64),
            )?;
        }
        let mut gradient_index: i64 = (if (dimension == 3i64) {
            (rt::int_modulo(index, 24i64)?)
                .checked_mul(3i64)
                .ok_or("integer overflow")?
        } else {
            (index & (if (dimension == 2i64) { 14i64 } else { 252i64 }))
        });
        let mut part: f64 = _sum(
            &(({
                let mut __comprehension_result_577: Vec<f64> = Vec::new();
                let __comprehension_source_576 = ((distances.clone())
                    .into_iter()
                    .enumerate()
                    .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                    .collect::<Vec<_>>());
                for (axis, distance) in __comprehension_source_576.iter().cloned() {
                    __comprehension_result_577.push(rt::finite(
                        ((rt::at(
                            &gradient,
                            (gradient_index)
                                .checked_add(axis)
                                .ok_or("integer overflow")?,
                        )?) as f64)
                            * distance,
                    )?);
                }
                __comprehension_result_577
            })
            .iter()
            .cloned()
            .collect::<Vec<_>>()),
        )?;
        attenuation = rt::finite(attenuation * attenuation)?;
        value = rt::finite(value + rt::finite(rt::finite(attenuation * attenuation)? * part)?)?;
    }
    Ok(rt::finite(
        value
            * ({
                static __CONSTANT_py__strategy__noise__escaped_5f4e4f524d: std::sync::OnceLock<
                    indexmap::IndexMap<i64, f64>,
                > = std::sync::OnceLock::new();
                if __CONSTANT_py__strategy__noise__escaped_5f4e4f524d
                    .get()
                    .is_none()
                {
                    let __constant_value = [
                        (2i64, rt::float_true_div(1.0f64, 47.0f64)?),
                        (3i64, rt::float_true_div(1.0f64, 103.0f64)?),
                        (4i64, rt::float_true_div(1.0f64, 30.0f64)?),
                    ]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>();
                    let _ =
                        __CONSTANT_py__strategy__noise__escaped_5f4e4f524d.set(__constant_value);
                }
                __CONSTANT_py__strategy__noise__escaped_5f4e4f524d
                    .get()
                    .ok_or("missing module constant")?
            })
            .get(&(dimension))
            .ok_or("missing dict key")?
            .clone(),
    )?)
}
