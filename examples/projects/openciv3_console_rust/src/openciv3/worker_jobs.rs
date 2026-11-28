use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct JobCompletion {
    pub(crate) job: i64,
    pub(crate) point: (i64, i64),
    pub(crate) workers: Vec<i64>,
    pub(crate) shield_city: Option<i64>,
    pub(crate) shields: i64,
}

// Python: openciv3/worker_jobs.py:32
pub(crate) fn cancel_worker_job(mut unit: crate::openciv3::units::Unit) -> rt::Result<()> {
    unit.worker_job = None;
    unit.worker_progress = 0.0f64;
    Ok(())
}

// Python: openciv3/worker_jobs.py:37
pub(crate) fn _workers(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut job: i64,
) -> rt::Result<Vec<crate::openciv3::units::Unit>> {
    Ok({
        let mut __comprehension_result_442: Vec<crate::openciv3::units::Unit> = Vec::new();
        let __comprehension_source_441 = ((game).units.clone());
        for other in __comprehension_source_441.iter().cloned() {
            if (((other).worker_job.clone() == Some(job))
                && (((other).x, (other).y) == ((unit).x, (unit).y)))
            {
                __comprehension_result_442.push(other.clone());
            }
        }
        __comprehension_result_442
    })
}

// Python: openciv3/worker_jobs.py:41
pub(crate) fn turns_to_finish(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut job: i64,
) -> rt::Result<Option<i64>> {
    let mut tile: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if (tile).is_none() {
        return Err("Worker is outside the map".to_string().into());
    }
    let mut workers: Vec<crate::openciv3::units::Unit> = _workers(game, unit, job)?;
    let mut speed: f64 = rt::finite(
        crate::openciv3::worker_rules::worker_speed(game, unit)?
            + ({
                let mut __comprehension_result_444: Vec<f64> = Vec::new();
                let __comprehension_source_443 = (workers.clone());
                for other in __comprehension_source_443.iter().cloned() {
                    if ((other).id != (unit).id) {
                        __comprehension_result_444
                            .push(crate::openciv3::worker_rules::worker_speed(game, &other)?);
                    }
                }
                __comprehension_result_444
            })
            .into_iter()
            .sum::<f64>(),
    )?;
    let mut remaining: Box<dyn std::any::Any> = Box::new(rt::finite(
        ((crate::openciv3::worker_rules::worker_job_cost(
            game,
            &((*(tile).as_ref().ok_or("expected a value")?).clone()),
            {
                let __source = &(&(&(game).scenario).rules).worker_jobs;
                let __key = job;
                &__source[rt::index(__source.len(), __key)?]
            },
        )?) as f64)
            - ({
                let mut __comprehension_result_446: Vec<f64> = Vec::new();
                let __comprehension_source_445 = (workers.clone());
                for other in __comprehension_source_445.iter().cloned() {
                    __comprehension_result_446.push((other).worker_progress);
                }
                __comprehension_result_446
            })
            .into_iter()
            .sum::<f64>(),
    )?) as Box<dyn std::any::Any>;
    Ok((if (speed > ((0i64) as f64)) {
        Some((0i64).max(rt::ceil(rt::float_true_div(
            if let Some(__value) = (&(remaining)).downcast_ref::<f64>() {
                *__value
            } else if let Some(__value) = (&(remaining)).downcast_ref::<i64>() {
                *__value as f64
            } else {
                return Err("numeric union mismatch".into());
            },
            speed,
        )?)?))
    } else {
        None
    }))
}

// Python: openciv3/worker_jobs.py:51
pub(crate) fn assign_worker_job(
    game: &crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
    mut job: i64,
) -> rt::Result<Option<JobCompletion>> {
    if (!(({
        let mut __comprehension_result_448: Vec<bool> = Vec::new();
        let __comprehension_source_447 = ((game).units.clone());
        for other in __comprehension_source_447.iter().cloned() {
            __comprehension_result_448.push(((other).id == (unit).id));
        }
        __comprehension_result_448
    })
    .into_iter()
    .any(|__value| __value))
        || !(crate::openciv3::worker_rules::can_work(game, &unit, job, None, &None, &None)?))
    {
        return Err("Worker cannot perform this job".to_string().into());
    }
    if ((unit).worker_job.clone() != Some(job)) {
        unit.worker_progress = 0.0f64;
    }
    unit.worker_job = Some(job);
    unit.movement_remaining = 0.0f64;
    unit.fortified = false;
    let mut tile: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if !((tile).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    let mut workers: Vec<crate::openciv3::units::Unit> = _workers(game, &unit, job)?;
    let mut pending: Box<dyn std::any::Any> = Box::new(
        ({
            let mut __comprehension_result_450: Vec<f64> = Vec::new();
            let __comprehension_source_449 = (workers.clone());
            for other in __comprehension_source_449.iter().cloned() {
                __comprehension_result_450.push(rt::finite(
                    (other).worker_progress
                        + crate::openciv3::worker_rules::worker_speed(game, &other)?,
                )?);
            }
            __comprehension_result_450
        })
        .into_iter()
        .sum::<f64>(),
    ) as Box<dyn std::any::Any>;
    if ((*(&(pending))
        .downcast_ref::<i64>()
        .ok_or("union type mismatch")?)
    .clone()
        == crate::openciv3::worker_rules::worker_job_cost(
            game,
            &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
            {
                let __source = &(&(&(game).scenario).rules).worker_jobs;
                let __key = job;
                &__source[rt::index(__source.len(), __key)?]
            },
        )?)
    {
        return Ok(Some(_complete(
            (*game).clone(),
            &unit,
            job,
            &((*(tile).as_ref().ok_or("expected a value")?).clone()),
        )?));
    }
    Ok(None)
}

// Python: openciv3/worker_jobs.py:69
pub(crate) fn _forest_shields(
    mut game: crate::openciv3::game_state::GameState,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<(Option<i64>, i64)> {
    let mut point: (i64, i64) = ((tile).x, (tile).y);
    if {
        let __needle = point.clone();
        let __container = &(game).cleared_forests;
        __container.contains(&__needle)
    } {
        return Ok((None, 0i64));
    }
    ((game).cleared_forests).insert(point.clone());
    if {
        let __needle = point;
        let __container = &(game).ownership;
        !__container.contains_key(&__needle)
    } {
        return Ok((None, 0i64));
    }
    let mut cities: indexmap::IndexMap<(i64, i64), crate::openciv3::cities::City> = {
        let mut __comprehension_result_452: indexmap::IndexMap<
            (i64, i64),
            crate::openciv3::cities::City,
        > = indexmap::IndexMap::new();
        let __comprehension_source_451 = ((game).cities.clone());
        for city in __comprehension_source_451.iter().cloned() {
            {
                let (__key, __value) = (((city).x, (city).y), city.clone());
                __comprehension_result_452.insert(__key, __value);
            }
        }
        __comprehension_result_452
    };
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    for mut nearby in crate::strategy::grid::within_rank(
        &((game).world.clone()),
        &((*tile).clone()),
        crate::openciv3::rules::RuleCatalog__workable_rank(&rules)?,
    )? {
        let mut city: Option<crate::openciv3::cities::City> =
            (cities.clone()).get(&(((nearby).x, (nearby).y))).cloned();
        if (city).is_none() {
            continue;
        }
        let mut player: crate::openciv3::players::Player = rt::at(
            &(game).players,
            ((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).owner,
        )?;
        let mut difficulty: crate::openciv3::scenario_model::Difficulty =
            rt::at(&(&(game).scenario).difficulties, (game).difficulty)?;
        let mut cost: i64 = 0i64;
        if (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
            .producing_building
            .clone())
        .is_some()
        {
            let mut building: crate::openciv3::building_rules::Building = rt::at(
                &(rules).buildings,
                (*(((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                    .producing_building
                    .clone())
                .as_ref()
                .ok_or("expected a value")?)
                .clone(),
            )?;
            if (((building).effects & (268435456i64 | 536870912i64)) != 0i64) {
                continue;
            }
            cost = crate::openciv3::production_cost::city_building_cost(
                &game,
                &((*(city.clone()).as_ref().ok_or("expected a value")?).clone()),
                &building,
            )?;
        } else {
            if (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                .producing_unit
                .clone())
            .is_some()
            {
                cost = crate::openciv3::production_cost::unit_cost(
                    {
                        let __source = &(rules).units;
                        let __key = (*(((*(city.clone()).as_ref().ok_or("expected a value")?)
                            .clone())
                        .producing_unit
                        .clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                        .clone();
                        &__source[rt::index(__source.len(), __key)?]
                    },
                    (player).human,
                    &difficulty,
                )?;
            } else {
                continue;
            }
        }
        let mut award: i64 = ((cost)
            .checked_sub(
                ((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).shields_stored,
            )
            .ok_or("integer overflow")?)
        .min(
            ({
                let __source = &(rules).global_rules;
                let __key = 0i64;
                &__source[rt::index(__source.len(), __key)?]
            })
            .forest_value_in_shields,
        );
        if (award > 0i64) {
            city.as_mut().ok_or("expected a value")?.shields_stored =
                (((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).shields_stored)
                    .checked_add(award)
                    .ok_or("integer overflow")?;
            return Ok((
                Some(((*(city).as_ref().ok_or("expected a value")?).clone()).id),
                award,
            ));
        }
    }
    Ok((None, 0i64))
}

// Python: openciv3/worker_jobs.py:101
pub(crate) fn _complete(
    mut game: crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut job: i64,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<JobCompletion> {
    let mut worker_job: crate::openciv3::rules::WorkerJob =
        rt::at(&(&(&(game).scenario).rules).worker_jobs, job)?;
    let mut key: String = crate::openciv3::worker_rules::order_key(&worker_job)?;
    let mut improvement: i64 = crate::openciv3::worker_rules::improvement_for(&worker_job)?;
    let mut flags: i64 = (tile).overlays;
    let mut terrain: i64 = (tile).overlay_terrain;
    let (mut shield_city, mut shields): (Option<i64>, i64) = (None, 0i64);
    let mut effects: Vec<crate::openciv3::rules::WorkerEffect> = (if (&(worker_job).effects)
        .is_some()
    {
        (*((worker_job).effects.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone()
    } else {
        {
            let __mapping = {
                static __CONSTANT_py__openciv3__worker_jobs__DEFAULT_EFFECTS: std::sync::OnceLock<
                    indexmap::IndexMap<String, Vec<crate::openciv3::rules::WorkerEffect>>,
                > = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__worker_jobs__DEFAULT_EFFECTS
                    .get()
                    .is_none()
                {
                    let __constant_value = [
                        (
                            "ClearForest".to_string(),
                            vec![crate::openciv3::rules::WorkerEffect::CLEAR_FOREST],
                        ),
                        (
                            "ClearWetlands".to_string(),
                            vec![crate::openciv3::rules::WorkerEffect::CLEAR_WETLANDS],
                        ),
                    ]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>();
                    let _ =
                        __CONSTANT_py__openciv3__worker_jobs__DEFAULT_EFFECTS.set(__constant_value);
                }
                __CONSTANT_py__openciv3__worker_jobs__DEFAULT_EFFECTS
                    .get()
                    .ok_or("missing module constant")?
            };
            let __key = key.clone();
            let __default = vec![];
            __mapping.get(&__key).cloned().unwrap_or(__default)
        }
    });
    for mut effect in effects {
        if (effect) == (crate::openciv3::rules::WorkerEffect::CLEAR_FOREST) {
            let (mut city, mut awarded): (Option<i64>, i64) = _forest_shields(game.clone(), tile)?;
            if (city).is_some() {
                (shield_city, shields) = (city.clone(), awarded);
            }
        }
        terrain = (tile).base_terrain;
    }
    if (key.as_str() == "ClearDamage") {
        flags = (flags & !(64i64 | 256i64));
    } else {
        if (key.as_str() == "PlantForest") {
            terrain = 7i64;
        }
    }
    if (improvement != 0i64) {
        if {
            let __needle = improvement;
            let __container = &({
                let __tuple_value = &((1i64, 2i64));
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            });
            __container.contains(&__needle)
        } {
            flags = (flags & !(1i64 | 2i64));
        } else {
            if {
                let __needle = improvement;
                let __container = &({
                    let __tuple_value = &((4i64, 8i64));
                    vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                });
                __container.contains(&__needle)
            } {
                flags = (flags & !(4i64 | 8i64));
            } else {
                if ((improvement & ((536870912i64 | 1073741824i64) | 2147483648i64)) != 0i64) {
                    flags = (flags & !((536870912i64 | 1073741824i64) | 2147483648i64));
                } else {
                    flags = (flags & !(16i64 | 268435456i64));
                }
            }
        }
        flags = (flags | improvement);
    }
    let mut updated: crate::openciv3::world::Tile = {
        let mut __replacement = ((*tile).clone()).clone();
        __replacement.overlays = flags;
        __replacement.overlay_terrain = terrain;
        __replacement.installation_owner =
            (if ((improvement & ((536870912i64 | 1073741824i64) | 2147483648i64)) != 0i64) {
                Some((unit).owner)
            } else {
                (tile).installation_owner.clone()
            });
        __replacement
    };
    game.world = {
        let mut __replacement = ((game).world.clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_454: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_453 = ((&(game).world).tiles.clone());
            for other in __comprehension_source_453.iter().cloned() {
                __comprehension_result_454.push(
                    (if (other.clone() == (*tile).clone()) {
                        updated.clone()
                    } else {
                        other.clone()
                    }),
                );
            }
            __comprehension_result_454
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    };
    if {
        let __needle = improvement;
        let __container = &({
            let __tuple_value = &((1i64, 2i64));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        __container.contains(&__needle)
    } {
        let mut cities: indexmap::IndexMap<(i64, i64), i64> = {
            let mut __comprehension_result_456: indexmap::IndexMap<(i64, i64), i64> =
                indexmap::IndexMap::new();
            let __comprehension_source_455 = ((game).cities.clone());
            for city in __comprehension_source_455.iter().cloned() {
                {
                    let (__key, __value) = (((city).x, (city).y), (city).owner);
                    __comprehension_result_456.insert(__key, __value);
                }
            }
            __comprehension_result_456
        };
        let mut center: Option<crate::openciv3::world::Tile> = {
            let __find_source_457 =
                crate::openciv3::world::WorldMap__neighbors(&(game).world, &updated)?;
            let mut __find_result_457: Option<crate::openciv3::world::Tile> = None;
            for neighbor in __find_source_457.iter().cloned() {
                if {
                    let __needle = ((neighbor).x, (neighbor).y);
                    let __container = &cities;
                    __container.contains_key(&__needle)
                } {
                    __find_result_457 = Some(neighbor.clone());
                    break;
                }
            }
            __find_result_457
        };
        if (center).is_some() {
            let mut route: i64 =
                (((*(center.clone()).as_ref().ok_or("expected a value")?).clone()).overlays
                    & (1i64 | 2i64));
            let mut can_extend: bool = (route == (if (improvement == 2i64) { 1i64 } else { 0i64 }));
            let mut owner: i64 = (cities)
                .get(
                    &((
                        ((*(center.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                        ((*(center.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                    )),
                )
                .ok_or("missing dict key")?
                .clone();
            if (can_extend
                && crate::openciv3::worker_rules::meets_job_requirements(
                    &game,
                    owner,
                    &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
                    &worker_job,
                    None,
                )?)
            {
                let mut connected: crate::openciv3::world::Tile = {
                    let mut __replacement =
                        ((*(center.clone()).as_ref().ok_or("expected a value")?).clone()).clone();
                    __replacement.overlays =
                        ((((*(center.clone()).as_ref().ok_or("expected a value")?).clone())
                            .overlays
                            & !(route))
                            | improvement);
                    __replacement
                };
                game.world = {
                    let mut __replacement = ((game).world.clone()).clone();
                    __replacement.tiles = ({
                        let mut __comprehension_result_459: Vec<crate::openciv3::world::Tile> =
                            Vec::new();
                        let __comprehension_source_458 = ((&(game).world).tiles.clone());
                        for other in __comprehension_source_458.iter().cloned() {
                            __comprehension_result_459.push(
                                (if (((other).x, (other).y)
                                    == (
                                        ((*(center.clone()).as_ref().ok_or("expected a value")?)
                                            .clone())
                                        .x,
                                        ((*(center.clone()).as_ref().ok_or("expected a value")?)
                                            .clone())
                                        .y,
                                    ))
                                {
                                    connected.clone()
                                } else {
                                    other.clone()
                                }),
                            );
                        }
                        __comprehension_result_459
                    })
                    .iter()
                    .cloned()
                    .collect::<Vec<_>>();
                    __replacement
                };
            }
        }
    }
    game.scenario.world = Some((game).world.clone());
    let mut workers: Vec<crate::openciv3::units::Unit> = _workers(&game, unit, job)?;
    for mut other in (workers).iter() {
        cancel_worker_job((*other).clone())?;
    }
    if ((improvement & ((536870912i64 | 1073741824i64) | 2147483648i64)) != 0i64) {
        crate::openciv3::unit_lifecycle::remove_unit(&game, unit)?;
    } else {
        game.visibility = crate::openciv3::visibility::update_visibility(
            &(game).world,
            &(game).cities,
            &(game).units,
            &(&(game).scenario).rules,
            &(game).ownership,
            (game).visibility.clone(),
            None,
            &None,
        )?;
    }
    Ok(JobCompletion {
        job: job,
        point: ((tile).x, (tile).y),
        workers: ({
            let mut __comprehension_result_461: Vec<i64> = Vec::new();
            let __comprehension_source_460 = (workers.clone());
            for other in __comprehension_source_460.iter().cloned() {
                __comprehension_result_461.push((other).id);
            }
            __comprehension_result_461
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        shield_city: shield_city,
        shields: shields,
    })
}

/// Contribute once at this unit's end-of-turn phase.
// Python: openciv3/worker_jobs.py:155
pub(crate) fn advance_worker(
    game: &crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
) -> rt::Result<Option<JobCompletion>> {
    if (&(unit).worker_job).is_none() {
        return Ok(None);
    }
    let mut job: i64 = (*((unit).worker_job.clone())
        .as_ref()
        .ok_or("expected a value")?)
    .clone();
    if !(crate::openciv3::worker_rules::can_work(game, &unit, job, None, &None, &None)?) {
        cancel_worker_job(unit)?;
        return Ok(None);
    }
    let mut tile: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if !((tile).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    unit.worker_progress = rt::finite(
        (unit).worker_progress + crate::openciv3::worker_rules::worker_speed(game, &unit)?,
    )?;
    unit.movement_remaining = 0.0f64;
    if (rt::int_float(
        ({
            let mut __comprehension_result_465: Vec<f64> = Vec::new();
            let __comprehension_source_464 = (_workers(game, &unit, job)?);
            for other in __comprehension_source_464.iter().cloned() {
                __comprehension_result_465.push((other).worker_progress);
            }
            __comprehension_result_465
        })
        .into_iter()
        .sum::<f64>(),
    )? >= crate::openciv3::worker_rules::worker_job_cost(
        game,
        &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
        {
            let __source = &(&(&(game).scenario).rules).worker_jobs;
            let __key = job;
            &__source[rt::index(__source.len(), __key)?]
        },
    )?) {
        return Ok(Some(_complete(
            (*game).clone(),
            &unit,
            job,
            &((*(tile).as_ref().ok_or("expected a value")?).clone()),
        )?));
    }
    Ok(None)
}
