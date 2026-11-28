use py2rust_service_runtime as rt;

// Python: openciv3/worker_rules.py:36
pub(crate) fn order_key(job: &crate::openciv3::rules::WorkerJob) -> rt::Result<String> {
    Ok((&(job).order).replace(" ", ""))
}

// Python: openciv3/worker_rules.py:40
pub(crate) fn is_worker_prototype(
    kind: &crate::openciv3::unit_rules::UnitPrototype,
) -> rt::Result<bool> {
    if (&(kind).worker_jobs).is_some() {
        return Ok(((kind).worker_jobs.clone()).is_some());
    }
    Ok(({
        let __boolean_123705997689872 = {
            let __boolean_123705997688912 = ((kind).strategies & 4096i64);
            if (__boolean_123705997688912) != 0 {
                __boolean_123705997688912
            } else {
                ((kind).orders & 4294967296i64)
            }
        };
        if (__boolean_123705997689872) != 0 {
            ((kind).orders
                & (({
                    static __CONSTANT_py__openciv3__worker_rules__ORDERS: std::sync::OnceLock<
                        indexmap::IndexMap<String, i64>,
                    > = std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__worker_rules__ORDERS
                        .get()
                        .is_none()
                    {
                        let __constant_value = [
                            ("BuildRoad".to_string(), 8388608i64),
                            ("BuildRailroad".to_string(), 16777216i64),
                            ("BuildMine".to_string(), 67108864i64),
                            ("Irrigate".to_string(), 134217728i64),
                            ("BuildFortress".to_string(), 33554432i64),
                            ("BuildBarricade".to_string(), 137438953472i64),
                            ("ClearForest".to_string(), 268435456i64),
                            ("ClearWetlands".to_string(), 536870912i64),
                            ("PlantForest".to_string(), 1073741824i64),
                            ("ClearDamage".to_string(), 2147483648i64),
                            ("BuildAirfield".to_string(), 17179869184i64),
                            ("BuildRadarTower".to_string(), 34359738368i64),
                            ("BuildOutpost".to_string(), 68719476736i64),
                        ]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>();
                        let _ = __CONSTANT_py__openciv3__worker_rules__ORDERS.set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__worker_rules__ORDERS
                        .get()
                        .ok_or("missing module constant")?
                        .clone()
                })
                .values()
                .cloned()
                .collect::<Vec<_>>())
                .into_iter()
                .sum::<i64>())
        } else {
            __boolean_123705997689872
        }
    }) != 0)
}

// Python: openciv3/worker_rules.py:47
pub(crate) fn improvement_for(job: &crate::openciv3::rules::WorkerJob) -> rt::Result<i64> {
    Ok((if (&(job).improvement).is_some() {
        (*((job).improvement.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone()
    } else {
        {
            let __mapping = {
                static __CONSTANT_py__openciv3__worker_rules__IMPROVEMENTS: std::sync::OnceLock<
                    indexmap::IndexMap<String, i64>,
                > = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__worker_rules__IMPROVEMENTS
                    .get()
                    .is_none()
                {
                    let __constant_value = {
                        let mut __result: indexmap::IndexMap<String, i64> =
                            indexmap::IndexMap::new();
                        __result.extend(
                            [
                                ("BuildRoad".to_string(), 1i64),
                                ("BuildRailroad".to_string(), 2i64),
                                ("BuildMine".to_string(), 4i64),
                                ("Irrigate".to_string(), 8i64),
                                ("BuildFortress".to_string(), 16i64),
                                ("BuildBarricade".to_string(), 268435456i64),
                            ]
                            .into_iter()
                            .collect::<indexmap::IndexMap<_, _>>(),
                        );
                        __result.extend({
                            static __CONSTANT_py__openciv3__worker_rules__INSTALLATIONS:
                                std::sync::OnceLock<indexmap::IndexMap<String, i64>> =
                                std::sync::OnceLock::new();
                            if __CONSTANT_py__openciv3__worker_rules__INSTALLATIONS
                                .get()
                                .is_none()
                            {
                                let __constant_value = [
                                    ("BuildAirfield".to_string(), 536870912i64),
                                    ("BuildRadarTower".to_string(), 1073741824i64),
                                    ("BuildOutpost".to_string(), 2147483648i64),
                                ]
                                .into_iter()
                                .collect::<indexmap::IndexMap<_, _>>();
                                let _ = __CONSTANT_py__openciv3__worker_rules__INSTALLATIONS
                                    .set(__constant_value);
                            }
                            __CONSTANT_py__openciv3__worker_rules__INSTALLATIONS
                                .get()
                                .ok_or("missing module constant")?
                                .clone()
                        });
                        __result
                    };
                    let _ =
                        __CONSTANT_py__openciv3__worker_rules__IMPROVEMENTS.set(__constant_value);
                }
                __CONSTANT_py__openciv3__worker_rules__IMPROVEMENTS
                    .get()
                    .ok_or("missing module constant")?
                    .clone()
            };
            let __key = order_key(job)?;
            let __default = 0i64;
            __mapping.get(&__key).cloned().unwrap_or(__default)
        }
    }))
}

// Python: openciv3/worker_rules.py:51
pub(crate) fn improvement_yield(
    terrain: &crate::openciv3::rules::Terrain,
    mut flag: i64,
) -> rt::Result<crate::civ::economy::Yield> {
    let mut improvements: crate::openciv3::rules::ImprovementYields =
        crate::openciv3::rules::Terrain__improvements(terrain)?;
    if (flag == 1i64) {
        return Ok((improvements).road.clone());
    }
    if (flag == 2i64) {
        return Ok((improvements).railroad.clone());
    }
    if (flag == 4i64) {
        return Ok((improvements).mine.clone());
    }
    if (flag == 8i64) {
        return Ok((improvements).irrigation.clone());
    }
    Ok({
        let __find_source_510 = (terrain).extra_improvement_yields.clone();
        let mut __find_result_510: crate::civ::economy::Yield = crate::civ::economy::Yield {
            food: 0i64,
            shields: 0i64,
            commerce: 0i64,
        };
        for (overlay, value) in __find_source_510.iter().cloned() {
            if (overlay == flag) {
                __find_result_510 = value.clone();
                break;
            }
        }
        __find_result_510
    })
}

// Python: openciv3/worker_rules.py:64
pub(crate) fn worker_speed(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<f64> {
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (unit).owner)?;
    let mut speed: f64 = (if ((unit).nationality != (unit).owner) {
        1.0f64
    } else {
        2.0f64
    });
    if {
        let __needle = "Industrious".to_string();
        let __container = &({
            let __source = &(&(game).scenario).civilizations;
            let __key = (unit).owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .traits;
        __container.contains(&__needle)
    } {
        speed = rt::finite(speed * 1.5f64)?;
    }
    speed = rt::finite(
        speed
            * rt::int_true_div(
                ({
                    let __source = &(&(&(game).scenario).rules).governments;
                    let __key = (player).government;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .worker_rate,
                2i64,
            )?,
    )?;
    if ({
        let mut __comprehension_result_512: Vec<i64> = Vec::new();
        let __comprehension_source_511 = ((player).known_technologies.clone());
        for tech in __comprehension_source_511.iter().cloned() {
            __comprehension_result_512.push(
                (({
                    let __source = &(&(&(game).scenario).rules).technologies;
                    let __key = tech;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .effects
                    & 262144i64),
            );
        }
        __comprehension_result_512
    })
    .into_iter()
    .any(|__value| __value != 0)
    {
        speed = rt::finite(speed * ((2i64) as f64))?;
    }
    Ok(speed)
}

// Python: openciv3/worker_rules.py:76
pub(crate) fn worker_job_cost(
    game: &crate::openciv3::game_state::GameState,
    tile: &crate::openciv3::world::Tile,
    job: &crate::openciv3::rules::WorkerJob,
) -> rt::Result<i64> {
    Ok((({
        let __source = &(&(&(game).scenario).rules).terrains;
        let __key = (tile).overlay_terrain;
        &__source[rt::index(__source.len(), __key)?]
    })
    .movement_cost)
        .checked_mul((job).turns_to_complete)
        .ok_or("integer overflow")?)
}

// Python: openciv3/worker_rules.py:80
pub(crate) fn irrigation_access(
    game: &crate::openciv3::game_state::GameState,
    tile: &crate::openciv3::world::Tile,
    mut hydro: Option<crate::openciv3::hydrology::Hydrology>,
) -> rt::Result<bool> {
    hydro = Some(match (hydro) {
        Some(__value) => __value,
        None => crate::openciv3::hydrology::Hydrology__from_world(&(game).world)?,
    });
    if crate::openciv3::hydrology::Hydrology__fresh_access(
        &((*(hydro.clone()).as_ref().ok_or("expected a value")?).clone()),
        &(game).world,
        tile,
    )? {
        return Ok(true);
    }
    let mut cities: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_514: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_513 = ((game).cities.clone());
        for city in __comprehension_source_513.iter().cloned() {
            __comprehension_result_514.insert(((city).x, (city).y));
        }
        __comprehension_result_514
    };
    for mut neighbor in crate::openciv3::world::WorldMap__neighbors(&(game).world, tile)? {
        if (((neighbor).overlays & 8i64) != 0i64) {
            return Ok(true);
        }
        if ({
            let __needle = ((neighbor).x, (neighbor).y);
            let __container = &cities;
            __container.contains(&__needle)
        } && (crate::openciv3::hydrology::Hydrology__fresh_access(
            &((*(hydro.clone()).as_ref().ok_or("expected a value")?).clone()),
            &(game).world,
            &neighbor,
        )? || ({
            let mut __comprehension_result_516: Vec<i64> = Vec::new();
            let __comprehension_source_515 =
                (crate::openciv3::world::WorldMap__neighbors(&(game).world, &neighbor)?);
            for other in __comprehension_source_515.iter().cloned() {
                __comprehension_result_516.push(((other).overlays & 8i64));
            }
            __comprehension_result_516
        })
        .into_iter()
        .any(|__value| __value != 0)))
        {
            return Ok(true);
        }
    }
    Ok(false)
}

// Python: openciv3/worker_rules.py:94
pub(crate) fn meets_job_requirements(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    tile: &crate::openciv3::world::Tile,
    job: &crate::openciv3::rules::WorkerJob,
    mut network: Option<crate::openciv3::trade_network::TradeNetwork>,
) -> rt::Result<bool> {
    if (((job).prerequisite >= 0i64) && {
        let __needle = (job).prerequisite;
        let __container = &({
            let __source = &(game).players;
            let __key = owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .known_technologies;
        !__container.contains(&__needle)
    }) {
        return Ok(false);
    }
    if !(((&(job).required_resources).len() as i64) != 0i64) {
        return Ok(true);
    }
    network = Some(match (network) {
        Some(__value) => __value,
        None => crate::openciv3::trade_network::TradeNetwork____post_init__(
            crate::openciv3::trade_network::TradeNetwork {
                game: (*game).clone(),
                owner: Some(owner),
                trade_with: None,
                segments: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                _routed_deals: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                _delivered_deals: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                _domestic_stock: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                _resource_indexes: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                _embargoes: {
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in vec![].into_iter() {
                        __result.insert(__item);
                    }
                    __result
                },
                _capitals: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
            },
        )?,
    });
    Ok(({
        let mut __comprehension_result_518: Vec<bool> = Vec::new();
        let __comprehension_source_517 = ((job).required_resources.clone());
        for resource in __comprehension_source_517.iter().cloned() {
            __comprehension_result_518.push(
                crate::openciv3::trade_network::TradeNetwork__has_trade_access(
                    &((*(network.clone()).as_ref().ok_or("expected a value")?).clone()),
                    &(((tile).x, (tile).y)),
                    owner,
                    resource,
                )?,
            );
        }
        __comprehension_result_518
    })
    .into_iter()
    .all(|__value| __value))
}

/// Check worker prerequisites, configured validators, and terrain constraints.
// Python: openciv3/worker_rules.py:104
pub(crate) fn can_work(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut job_index: i64,
    mut tile: Option<crate::openciv3::world::Tile>,
    network: &Option<crate::openciv3::trade_network::TradeNetwork>,
    hydro: &Option<crate::openciv3::hydrology::Hydrology>,
) -> rt::Result<bool> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    if !({
        let __compare_0 = 0i64;
        let __compare_1 = job_index;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = ((&(rules).worker_jobs).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) {
        return Ok(false);
    }
    let mut job: crate::openciv3::rules::WorkerJob = rt::at(&(rules).worker_jobs, job_index)?;
    let mut key: String = order_key(&job)?;
    let mut order: Option<i64> = ({
        static __CONSTANT_py__openciv3__worker_rules__ORDERS: std::sync::OnceLock<
            indexmap::IndexMap<String, i64>,
        > = std::sync::OnceLock::new();
        if __CONSTANT_py__openciv3__worker_rules__ORDERS
            .get()
            .is_none()
        {
            let __constant_value = [
                ("BuildRoad".to_string(), 8388608i64),
                ("BuildRailroad".to_string(), 16777216i64),
                ("BuildMine".to_string(), 67108864i64),
                ("Irrigate".to_string(), 134217728i64),
                ("BuildFortress".to_string(), 33554432i64),
                ("BuildBarricade".to_string(), 137438953472i64),
                ("ClearForest".to_string(), 268435456i64),
                ("ClearWetlands".to_string(), 536870912i64),
                ("PlantForest".to_string(), 1073741824i64),
                ("ClearDamage".to_string(), 2147483648i64),
                ("BuildAirfield".to_string(), 17179869184i64),
                ("BuildRadarTower".to_string(), 34359738368i64),
                ("BuildOutpost".to_string(), 68719476736i64),
            ]
            .into_iter()
            .collect::<indexmap::IndexMap<_, _>>();
            let _ = __CONSTANT_py__openciv3__worker_rules__ORDERS.set(__constant_value);
        }
        __CONSTANT_py__openciv3__worker_rules__ORDERS
            .get()
            .ok_or("missing module constant")?
            .clone()
    })
    .get(&(key.clone()))
    .cloned();
    let mut prototype: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(rules).units, (unit).prototype)?;
    if (&(unit).transported_by).is_some() {
        return Ok(false);
    }
    if (&(prototype).worker_jobs).is_none() {
        if ((order).is_none()
            || !(((prototype).orders
                & (*(order.clone()).as_ref().ok_or("expected a value")?).clone())
                != 0i64))
        {
            return Ok(false);
        }
    } else {
        if {
            let __needle = job_index;
            let __container = &((*(&(prototype).worker_jobs)
                .as_ref()
                .ok_or("expected a value")?)
            .clone());
            !__container.contains(&__needle)
        } {
            return Ok(false);
        }
    }
    if ((order).is_none()
        && !(((job).effects.clone()).is_some() || ((job).improvement.clone()).is_some()))
    {
        return Ok(false);
    }
    tile = {
        let __boolean_123705998232464 = tile;
        if (__boolean_123705998232464).is_some() {
            __boolean_123705998232464
        } else {
            crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?
        }
    };
    if ((tile).is_none()
        || ({
            let mut __comprehension_result_520: Vec<bool> = Vec::new();
            let __comprehension_source_519 = ((game).cities.clone());
            for city in __comprehension_source_519.iter().cloned() {
                __comprehension_result_520.push(
                    (((city).x, (city).y)
                        == (
                            ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                            ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                        )),
                );
            }
            __comprehension_result_520
        })
        .into_iter()
        .any(|__value| __value))
    {
        return Ok(false);
    }
    if !(meets_job_requirements(
        game,
        (unit).owner,
        &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
        &job,
        (*network).clone(),
    )?) {
        return Ok(false);
    }
    let mut flags: i64 = ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).overlays;
    let mut terrain: crate::openciv3::rules::Terrain = rt::at(
        &(rules).terrains,
        ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).overlay_terrain,
    )?;
    let mut improvement: i64 = improvement_for(&job)?;
    let mut validators: Vec<crate::openciv3::rules::WorkerValidator> = (if (&(job).validators)
        .is_some()
    {
        (*((job).validators.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone()
    } else {
        {
            let __mapping = {
                static __CONSTANT_py__openciv3__worker_rules__DEFAULT_VALIDATORS:
                    std::sync::OnceLock<
                        indexmap::IndexMap<String, Vec<crate::openciv3::rules::WorkerValidator>>,
                    > = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__worker_rules__DEFAULT_VALIDATORS
                    .get()
                    .is_none()
                {
                    let __constant_value = [
                        (
                            "BuildMine".to_string(),
                            vec![crate::openciv3::rules::WorkerValidator::MINE],
                        ),
                        (
                            "Irrigate".to_string(),
                            vec![crate::openciv3::rules::WorkerValidator::IRRIGATE],
                        ),
                        (
                            "ClearForest".to_string(),
                            vec![crate::openciv3::rules::WorkerValidator::CLEAR_FOREST],
                        ),
                        (
                            "ClearWetlands".to_string(),
                            vec![crate::openciv3::rules::WorkerValidator::CLEAR_WETLANDS],
                        ),
                    ]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>();
                    let _ = __CONSTANT_py__openciv3__worker_rules__DEFAULT_VALIDATORS
                        .set(__constant_value);
                }
                __CONSTANT_py__openciv3__worker_rules__DEFAULT_VALIDATORS
                    .get()
                    .ok_or("missing module constant")?
            };
            let __key = key.clone();
            let __default = vec![];
            __mapping.get(&__key).cloned().unwrap_or(__default)
        }
    });
    for mut validator in validators {
        if ((validator.clone()) == (crate::openciv3::rules::WorkerValidator::MINE)
            && ((improvement_yield(&terrain, improvement)?).shields <= 0i64))
        {
            return Ok(false);
        }
        if ((validator.clone()) == (crate::openciv3::rules::WorkerValidator::IRRIGATE)
            && (((improvement_yield(&terrain, improvement)?).food <= 0i64)
                || !(irrigation_access(
                    game,
                    &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
                    (*hydro).clone(),
                )?)))
        {
            return Ok(false);
        }
        if ((validator.clone()) == (crate::openciv3::rules::WorkerValidator::CLEAR_FOREST)
            && ((terrain).worker_job != 6i64))
        {
            return Ok(false);
        }
        if ((validator) == (crate::openciv3::rules::WorkerValidator::CLEAR_WETLANDS)
            && ((terrain).worker_job != 7i64))
        {
            return Ok(false);
        }
    }
    if ((key.as_str() == "ClearDamage") && !((flags & (64i64 | 256i64)) != 0i64)) {
        return Ok(false);
    }
    if ((key.as_str() == "PlantForest")
        && (((terrain).worker_job != 5i64)
            || (((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).overlay_terrain
                != ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).base_terrain)))
    {
        return Ok(false);
    }
    if (improvement == 1i64) {
        return Ok(!((flags & (1i64 | 2i64)) != 0));
    }
    if (improvement == 2i64) {
        return Ok(((flags & 1i64) != 0 && !((flags & 2i64) != 0)));
    }
    if (improvement == 16i64) {
        return Ok(((terrain).allow_forts && !((flags & (16i64 | 268435456i64)) != 0)));
    }
    if (improvement == 268435456i64) {
        return Ok(
            ((terrain).allow_forts && ((flags & 16i64) != 0 && !((flags & 268435456i64) != 0)))
        );
    }
    if ((improvement & ((536870912i64 | 1073741824i64) | 2147483648i64)) != 0i64) {
        let mut allowed: indexmap::IndexMap<i64, bool> = [
            (536870912i64, (terrain).allow_airfields),
            (1073741824i64, (terrain).allow_radar_towers),
            (2147483648i64, (terrain).allow_outposts),
        ]
        .into_iter()
        .collect::<indexmap::IndexMap<_, _>>();
        let mut claim: Option<i64> = ((game).ownership.clone())
            .get(
                &((
                    ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                    ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                )),
            )
            .cloned();
        let mut blocked: i64 = improvement;
        if (improvement == 536870912i64) {
            blocked = (blocked
                | ((((((((536870912i64 | 1073741824i64) | 2147483648i64) | 1i64) | 2i64)
                    | 4i64)
                    | 8i64)
                    | 16i64)
                    | 268435456i64));
        }
        return Ok(((allowed)
            .get(&(improvement))
            .ok_or("missing dict key")?
            .clone()
            && (!((flags & blocked) != 0)
                && (((improvement != 536870912i64)
                    || (((*(tile).as_ref().ok_or("expected a value")?).clone()).colony
                        < 0i64))
                    && ((claim).is_none()
                        || ({
                            let mut __comprehension_result_522: Vec<bool> = Vec::new();
                            let __comprehension_source_521 = ((game).cities.clone());
                            for city in __comprehension_source_521.iter().cloned() {
                                __comprehension_result_522.push(
                                    ((Some((city).id) == claim.clone())
                                        && ((city).owner == (unit).owner)),
                                );
                            }
                            __comprehension_result_522
                        })
                        .into_iter()
                        .any(|__value| __value))))));
    }
    Ok(!((flags & improvement) != 0))
}
