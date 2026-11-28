use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct Pose {
    pub(crate) action: String,
    pub(crate) started: f64,
    pub(crate) loops: bool,
    pub(crate) transition: bool,
}

#[derive(Clone, PartialEq)]
pub(crate) struct UnitMotion {
    pub(crate) started: f64,
    pub(crate) dx: i64,
    pub(crate) dy: i64,
}

#[derive(Clone, PartialEq)]
pub(crate) struct UnitAnimation {
    pub(crate) poses: indexmap::IndexMap<i64, Pose>,
    pub(crate) positions: indexmap::IndexMap<i64, (i64, i64)>,
    pub(crate) runs: indexmap::IndexMap<i64, UnitMotion>,
}

// Python: openciv3/unit_animation.py:16
pub(crate) fn facing(
    unit: &crate::openciv3::units::Unit,
    world: &crate::openciv3::world::WorldMap,
) -> rt::Result<String> {
    if (&(unit).facing_override).is_some() {
        return Ok((*((unit).facing_override.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone());
    }
    let mut delta: (i64, i64) = (
        crate::strategy::grid::axis_delta(
            (unit).x,
            (unit).previous_x,
            (world).width,
            (world).wrap_x,
        )?,
        crate::strategy::grid::axis_delta(
            (unit).y,
            (unit).previous_y,
            (world).height,
            (world).wrap_y,
        )?,
    );
    Ok({
        let __mapping = {
            static __CONSTANT_py__openciv3__unit_animation__DIRECTIONS: std::sync::OnceLock<
                indexmap::IndexMap<(i64, i64), String>,
            > = std::sync::OnceLock::new();
            if __CONSTANT_py__openciv3__unit_animation__DIRECTIONS
                .get()
                .is_none()
            {
                let __constant_value = [
                    (
                        (0i64, (2i64).checked_neg().ok_or("integer overflow")?),
                        "N".to_string(),
                    ),
                    (
                        (1i64, (1i64).checked_neg().ok_or("integer overflow")?),
                        "NE".to_string(),
                    ),
                    ((2i64, 0i64), "E".to_string()),
                    ((1i64, 1i64), "SE".to_string()),
                    ((0i64, 2i64), "S".to_string()),
                    (
                        ((1i64).checked_neg().ok_or("integer overflow")?, 1i64),
                        "SW".to_string(),
                    ),
                    (
                        ((2i64).checked_neg().ok_or("integer overflow")?, 0i64),
                        "W".to_string(),
                    ),
                    (
                        (
                            (1i64).checked_neg().ok_or("integer overflow")?,
                            (1i64).checked_neg().ok_or("integer overflow")?,
                        ),
                        "NW".to_string(),
                    ),
                ]
                .into_iter()
                .collect::<indexmap::IndexMap<_, _>>();
                let _ = __CONSTANT_py__openciv3__unit_animation__DIRECTIONS.set(__constant_value);
            }
            __CONSTANT_py__openciv3__unit_animation__DIRECTIONS
                .get()
                .ok_or("missing module constant")?
        };
        let __key = delta;
        let __default = "SE".to_string();
        __mapping.get(&__key).cloned().unwrap_or(__default)
    })
}

// Python: openciv3/unit_animation.py:24
pub(crate) fn facing_toward(
    world: &crate::openciv3::world::WorldMap,
    origin: &(i64, i64),
    target: &(i64, i64),
    mut rotate_before_attack: bool,
) -> rt::Result<String> {
    let mut dx: i64 = crate::strategy::grid::axis_delta(
        (target).0.clone(),
        (origin).0.clone(),
        (world).width,
        (world).wrap_x,
    )?;
    let mut dy: i64 = crate::strategy::grid::axis_delta(
        (target).1.clone(),
        (origin).1.clone(),
        (world).height,
        (world).wrap_y,
    )?;
    if (!(dx != 0i64) && !(dy != 0i64)) {
        return Ok("SE".to_string());
    }
    let mut headings: Vec<String> = vec![
        "E".to_string(),
        "SE".to_string(),
        "S".to_string(),
        "SW".to_string(),
        "W".to_string(),
        "NW".to_string(),
        "N".to_string(),
        "NE".to_string(),
    ];
    let mut direction: i64 = rt::round_float(rt::float_true_div(
        rt::math_atan2(
            ((dy) as f64),
            (((2i64).checked_mul(dx).ok_or("integer overflow")?) as f64),
        )?,
        rt::float_true_div(3.141592653589793f64, ((4i64) as f64))?,
    )?)?;
    if rotate_before_attack {
        direction = (direction).checked_sub(2i64).ok_or("integer overflow")?;
    }
    Ok(rt::at(
        &headings,
        rt::int_modulo(direction, ((headings).len() as i64))?,
    )?)
}

// Python: openciv3/unit_animation.py:54
pub(crate) fn UnitMotion__progress(self_: &UnitMotion, mut now: f64) -> rt::Result<f64> {
    Ok((1.0f64).min((0.0f64).max(rt::float_true_div(
        rt::finite(now - (self_).started)?,
        0.24f64,
    )?)))
}

// Python: openciv3/unit_animation.py:64
pub(crate) fn UnitAnimation__pose(
    mut self_: UnitAnimation,
    unit: &crate::openciv3::units::Unit,
    mut now: f64,
    job_order: &str,
    job_animation: &str,
) -> rt::Result<Pose> {
    let mut action: String = String::new();
    if (&(unit).worker_job).is_some() {
        action = {
            let __boolean_123705974183504 = job_animation.to_owned();
            if !(__boolean_123705974183504).is_empty() {
                __boolean_123705974183504
            } else {
                {
                    let __mapping = {
                        static __CONSTANT_py__openciv3__unit_animation__JOB_ACTIONS:
                            std::sync::OnceLock<indexmap::IndexMap<String, String>> =
                            std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__unit_animation__JOB_ACTIONS
                            .get()
                            .is_none()
                        {
                            let __constant_value = [
                                ("BuildRoad".to_string(), "ROAD".to_string()),
                                ("BuildRailroad".to_string(), "ROAD".to_string()),
                                ("BuildMine".to_string(), "MINE".to_string()),
                                ("Irrigate".to_string(), "IRRIGATE".to_string()),
                                ("BuildFortress".to_string(), "FORTRESS".to_string()),
                                ("BuildBarricade".to_string(), "FORTRESS".to_string()),
                                ("ClearForest".to_string(), "FOREST".to_string()),
                                ("ClearWetlands".to_string(), "JUNGLE".to_string()),
                                ("PlantForest".to_string(), "PLANT".to_string()),
                            ]
                            .into_iter()
                            .collect::<indexmap::IndexMap<_, _>>();
                            let _ = __CONSTANT_py__openciv3__unit_animation__JOB_ACTIONS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__unit_animation__JOB_ACTIONS
                            .get()
                            .ok_or("missing module constant")?
                    };
                    let __key = (job_order).replace(" ", "");
                    let __default = "DEFAULT".to_string();
                    __mapping.get(&__key).cloned().unwrap_or(__default)
                }
            }
        };
    } else {
        action = (if (unit).fortified {
            "FORTIFY".to_string()
        } else {
            "DEFAULT".to_string()
        });
    }
    let mut previous: Option<Pose> = ((self_).poses.clone()).get(&((unit).id)).cloned();
    if ((previous).is_none()
        || ((((*(previous.clone()).as_ref().ok_or("expected a value")?).clone())
            .action
            .clone())
        .as_str()
            != action.as_str()))
    {
        previous = Some(Pose {
            action: action.clone(),
            started: now,
            loops: (&(unit).worker_job).is_some(),
            transition: ((action.as_str() == "FORTIFY") && (previous).is_some()),
        });
        self_.poses.insert(
            (unit).id,
            (*(previous.clone()).as_ref().ok_or("expected a value")?).clone(),
        );
    }
    Ok((*(previous).as_ref().ok_or("expected a value")?).clone())
}

// Python: openciv3/unit_animation.py:77
pub(crate) fn UnitAnimation__motion(
    mut self_: UnitAnimation,
    unit: &crate::openciv3::units::Unit,
    world: &crate::openciv3::world::WorldMap,
    mut now: f64,
    mut animate: bool,
) -> rt::Result<Option<UnitMotion>> {
    let mut point: (i64, i64) = ((unit).x, (unit).y);
    let mut before: Option<(i64, i64)> = ((self_).positions.clone()).get(&((unit).id)).cloned();
    self_.positions.insert((unit).id, point.clone());
    if !(animate) {
        ((self_).runs).remove(&((unit).id));
        return Ok(None);
    }
    if ((before).is_some() && (before.clone() != Some(point))) {
        let mut dx: i64 = crate::strategy::grid::axis_delta(
            (unit).x,
            (unit).previous_x,
            (world).width,
            (world).wrap_x,
        )?;
        let mut dy: i64 = crate::strategy::grid::axis_delta(
            (unit).y,
            (unit).previous_y,
            (world).height,
            (world).wrap_y,
        )?;
        if {
            let __needle = (dx, dy);
            let __container = {
                static __CONSTANT_py__openciv3__unit_animation__DIRECTIONS: std::sync::OnceLock<
                    indexmap::IndexMap<(i64, i64), String>,
                > = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__unit_animation__DIRECTIONS
                    .get()
                    .is_none()
                {
                    let __constant_value = [
                        (
                            (0i64, (2i64).checked_neg().ok_or("integer overflow")?),
                            "N".to_string(),
                        ),
                        (
                            (1i64, (1i64).checked_neg().ok_or("integer overflow")?),
                            "NE".to_string(),
                        ),
                        ((2i64, 0i64), "E".to_string()),
                        ((1i64, 1i64), "SE".to_string()),
                        ((0i64, 2i64), "S".to_string()),
                        (
                            ((1i64).checked_neg().ok_or("integer overflow")?, 1i64),
                            "SW".to_string(),
                        ),
                        (
                            ((2i64).checked_neg().ok_or("integer overflow")?, 0i64),
                            "W".to_string(),
                        ),
                        (
                            (
                                (1i64).checked_neg().ok_or("integer overflow")?,
                                (1i64).checked_neg().ok_or("integer overflow")?,
                            ),
                            "NW".to_string(),
                        ),
                    ]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>();
                    let _ =
                        __CONSTANT_py__openciv3__unit_animation__DIRECTIONS.set(__constant_value);
                }
                __CONSTANT_py__openciv3__unit_animation__DIRECTIONS
                    .get()
                    .ok_or("missing module constant")?
            };
            __container.contains_key(&__needle)
        } {
            self_.runs.insert(
                (unit).id,
                UnitMotion {
                    started: now,
                    dx: dx,
                    dy: dy,
                },
            );
        } else {
            ((self_).runs).remove(&((unit).id));
        }
    }
    let mut run: Option<UnitMotion> = ((self_).runs.clone()).get(&((unit).id)).cloned();
    if ((run).is_some()
        && (UnitMotion__progress(
            &((*(run.clone()).as_ref().ok_or("expected a value")?).clone()),
            now,
        )? >= ((1i64) as f64)))
    {
        ((self_).runs).remove(&((unit).id));
        return Ok(None);
    }
    Ok(run)
}

// Python: openciv3/unit_animation.py:97
pub(crate) fn UnitAnimation__prune_motion(
    mut self_: UnitAnimation,
    visible: &std::collections::BTreeSet<i64>,
) -> rt::Result<()> {
    self_.positions = {
        let mut __comprehension_result_700: indexmap::IndexMap<i64, (i64, i64)> =
            indexmap::IndexMap::new();
        let __comprehension_source_699 = (((self_).positions.clone())
            .iter()
            .map(|(__key, __value)| (__key.clone(), __value.clone()))
            .collect::<Vec<_>>());
        for (key, point) in __comprehension_source_699.iter().cloned() {
            if {
                let __needle = key;
                let __container = visible;
                __container.contains(&__needle)
            } {
                {
                    let (__key, __value) = (key, point.clone());
                    __comprehension_result_700.insert(__key, __value);
                }
            }
        }
        __comprehension_result_700
    };
    self_.runs = {
        let mut __comprehension_result_702: indexmap::IndexMap<i64, UnitMotion> =
            indexmap::IndexMap::new();
        let __comprehension_source_701 = (((self_).runs.clone())
            .iter()
            .map(|(__key, __value)| (__key.clone(), __value.clone()))
            .collect::<Vec<_>>());
        for (key, run) in __comprehension_source_701.iter().cloned() {
            if {
                let __needle = key;
                let __container = visible;
                __container.contains(&__needle)
            } {
                {
                    let (__key, __value) = (key, run.clone());
                    __comprehension_result_702.insert(__key, __value);
                }
            }
        }
        __comprehension_result_702
    };
    Ok(())
}

// Python: openciv3/unit_animation.py:101
pub(crate) fn UnitAnimation__prune(
    mut self_: UnitAnimation,
    live: &std::collections::BTreeSet<i64>,
) -> rt::Result<()> {
    self_.poses = {
        let mut __comprehension_result_704: indexmap::IndexMap<i64, Pose> =
            indexmap::IndexMap::new();
        let __comprehension_source_703 = (((self_).poses.clone())
            .iter()
            .map(|(__key, __value)| (__key.clone(), __value.clone()))
            .collect::<Vec<_>>());
        for (key, pose) in __comprehension_source_703.iter().cloned() {
            if {
                let __needle = key;
                let __container = live;
                __container.contains(&__needle)
            } {
                {
                    let (__key, __value) = (key, pose.clone());
                    __comprehension_result_704.insert(__key, __value);
                }
            }
        }
        __comprehension_result_704
    };
    Ok(())
}

// Python: openciv3/unit_animation.py:105
pub(crate) fn frame_at(
    pose: &Pose,
    mut now: f64,
    mut frames: i64,
    mut speed_ms: i64,
    mut animate: bool,
) -> rt::Result<(i64, bool)> {
    if (frames <= 0i64) {
        return Err("Animation must have frames".to_string().into());
    }
    if (!(animate) || (!((pose).loops) && !((pose).transition))) {
        return Ok(((frames).checked_sub(1i64).ok_or("integer overflow")?, false));
    }
    let mut index: i64 = rt::int_float(rt::float_true_div(
        rt::finite((0.0f64).max(rt::finite(now - (pose).started)?) * ((1000i64) as f64))?,
        (((1i64).max(speed_ms)) as f64),
    )?)?;
    if (pose).loops {
        return Ok((rt::int_modulo(index, frames)?, (frames > 1i64)));
    }
    Ok((
        (index).min((frames).checked_sub(1i64).ok_or("integer overflow")?),
        (index < (frames).checked_sub(1i64).ok_or("integer overflow")?),
    ))
}
