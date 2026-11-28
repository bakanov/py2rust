use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct WorkerPlan {
    pub(crate) path: crate::openciv3::pathfinding::UnitPath,
    pub(crate) job: i64,
}

#[derive(Clone, PartialEq)]
pub(crate) struct WorkerStep {
    pub(crate) plan: Option<WorkerPlan>,
    pub(crate) movement: Option<crate::openciv3::unit_movement::MoveResult>,
    pub(crate) started_job: Option<i64>,
    pub(crate) completion: Option<crate::openciv3::worker_jobs::JobCompletion>,
}

// Python: civ3_ai/worker_ai.py:48
pub(crate) fn important_resource(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<bool> {
    if ((tile).resource < 0i64) {
        return Ok(false);
    }
    let mut resource: crate::openciv3::rules::Resource =
        rt::at(&(&(&(game).scenario).rules).resources, (tile).resource)?;
    Ok(({
        let __needle = (resource).kind;
        let __container = &({
            let __tuple_value = &((1i64, 2i64));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        __container.contains(&__needle)
    } && (((resource).prerequisite < 0i64) || {
        let __needle = (resource).prerequisite;
        let __container = &({
            let __source = &(game).players;
            let __key = owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .known_technologies;
        __container.contains(&__needle)
    })))
}

// Python: civ3_ai/worker_ai.py:56
pub(crate) fn improvement_score(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    tile: &crate::openciv3::world::Tile,
    mut job: i64,
) -> rt::Result<i64> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut worker_job: crate::openciv3::rules::WorkerJob = rt::at(&(rules).worker_jobs, job)?;
    let mut key: String = crate::openciv3::worker_rules::order_key(&worker_job)?;
    let mut score: crate::openciv3::rules::WorkerScore = match ((worker_job).ai_score.clone()) {
        Some(__value) => __value,
        None => {
            let __mapping = {
                static __CONSTANT_py__civ3_ai__worker_ai__DEFAULT_SCORES: std::sync::OnceLock<
                    indexmap::IndexMap<String, crate::openciv3::rules::WorkerScore>,
                > = std::sync::OnceLock::new();
                if __CONSTANT_py__civ3_ai__worker_ai__DEFAULT_SCORES
                    .get()
                    .is_none()
                {
                    let __constant_value = [
                        (
                            "ClearWetlands".to_string(),
                            crate::openciv3::rules::WorkerScore::CLEAR_WETLANDS,
                        ),
                        (
                            "BuildRailroad".to_string(),
                            crate::openciv3::rules::WorkerScore::RAILROAD,
                        ),
                        (
                            "ClearForest".to_string(),
                            crate::openciv3::rules::WorkerScore::CLEAR_FOREST,
                        ),
                        (
                            "Irrigate".to_string(),
                            crate::openciv3::rules::WorkerScore::YIELD_IMPROVEMENT,
                        ),
                        (
                            "BuildMine".to_string(),
                            crate::openciv3::rules::WorkerScore::YIELD_IMPROVEMENT,
                        ),
                        (
                            "BuildRoad".to_string(),
                            crate::openciv3::rules::WorkerScore::ROAD,
                        ),
                    ]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>();
                    let _ = __CONSTANT_py__civ3_ai__worker_ai__DEFAULT_SCORES.set(__constant_value);
                }
                __CONSTANT_py__civ3_ai__worker_ai__DEFAULT_SCORES
                    .get()
                    .ok_or("missing module constant")?
            };
            let __key = key;
            let __default = crate::openciv3::rules::WorkerScore::DEFAULT;
            __mapping.get(&__key).cloned().unwrap_or(__default)
        }
    };
    if (score.clone()) == (crate::openciv3::rules::WorkerScore::DEFAULT) {
        return Ok(0i64);
    }
    if (score.clone()) == (crate::openciv3::rules::WorkerScore::CLEAR_WETLANDS) {
        return Ok(3i64);
    }
    if (score.clone()) == (crate::openciv3::rules::WorkerScore::RAILROAD) {
        return Ok(10i64);
    }
    if (score.clone()) == (crate::openciv3::rules::WorkerScore::CLEAR_FOREST) {
        return Ok((if {
            let __needle = ((tile).x, (tile).y);
            let __container = &(game).cleared_forests;
            __container.contains(&__needle)
        } {
            0i64
        } else {
            2i64
        }));
    }
    let mut penalty: bool = ({
        let __source = &(rules).governments;
        let __key = ({
            let __source = &(game).players;
            let __key = owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .government;
        &__source[rt::index(__source.len(), __key)?]
    })
    .tile_penalty;
    let mut terrain: crate::openciv3::rules::Terrain =
        rt::at(&(rules).terrains, (tile).overlay_terrain)?;
    let mut improvement: i64 = crate::openciv3::worker_rules::improvement_for(&worker_job)?;
    if (penalty && {
        let __needle = ((tile).overlay_terrain, improvement);
        let __container = &({
            let __tuple_value = &(((2i64, 8i64), (1i64, 4i64)));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        __container.contains(&__needle)
    }) {
        return Ok(0i64);
    }
    let mut value: crate::civ::economy::Yield =
        crate::openciv3::worker_rules::improvement_yield(&terrain, improvement)?;
    let mut resource_bonus: i64 = (if ((score) == (crate::openciv3::rules::WorkerScore::ROAD)
        && important_resource(game, owner, tile)?)
    {
        20i64
    } else {
        0i64
    });
    Ok(
        (((((value).food).checked_mul(5i64).ok_or("integer overflow")?)
            .checked_add(
                ((value).shields)
                    .checked_mul(3i64)
                    .ok_or("integer overflow")?,
            )
            .ok_or("integer overflow")?)
        .checked_add((value).commerce)
        .ok_or("integer overflow")?)
        .checked_add(resource_bonus)
        .ok_or("integer overflow")?,
    )
}

// Python: civ3_ai/worker_ai.py:79
pub(crate) fn choose_improvement(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    tile: &crate::openciv3::world::Tile,
    network: &Option<crate::openciv3::trade_network::TradeNetwork>,
    hydro: &Option<crate::openciv3::hydrology::Hydrology>,
) -> rt::Result<Option<i64>> {
    if crate::openciv3::hydrology::is_water(tile)? {
        return Ok(None);
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut available: Vec<i64> = {
        let mut __comprehension_result_1181: Vec<i64> = Vec::new();
        let __comprehension_source_1179 =
            ((0i64..((&(rules).worker_jobs).len() as i64)).collect::<Vec<i64>>());
        for index in __comprehension_source_1179.iter().cloned() {
            if {
                let __call_1180_0 = game;
                let __call_1180_1 = unit;
                let __call_1180_2 = index;
                let __call_1180_3 = Some((*tile).clone());
                let __call_1180_4 = network;
                let __call_1180_5 = hydro;
                crate::openciv3::worker_rules::can_work(
                    __call_1180_0,
                    __call_1180_1,
                    __call_1180_2,
                    __call_1180_3,
                    __call_1180_4,
                    __call_1180_5,
                )
            }? {
                __comprehension_result_1181.push(index);
            }
        }
        __comprehension_result_1181
    };
    let mut claim: Option<i64> = ((game).ownership.clone())
        .get(&(((tile).x, (tile).y)))
        .cloned();
    if !(({
        let mut __comprehension_result_1183: Vec<bool> = Vec::new();
        let __comprehension_source_1182 = ((game).cities.clone());
        for city in __comprehension_source_1182.iter().cloned() {
            __comprehension_result_1183
                .push(((Some((city).id) == claim.clone()) && ((city).owner == (unit).owner)));
        }
        __comprehension_result_1183
    })
    .into_iter()
    .any(|__value| __value))
    {
        return Ok({
            let __find_source_1184 = available;
            let mut __find_result_1184: Option<i64> = None;
            for index in __find_source_1184.iter().cloned() {
                if (crate::openciv3::worker_rules::improvement_for({
                    let __source = &(rules).worker_jobs;
                    let __key = index;
                    &__source[rt::index(__source.len(), __key)?]
                })? == 1i64)
                {
                    __find_result_1184 = Some(index);
                    break;
                }
            }
            __find_result_1184
        });
    }
    let mut positive: Vec<i64> = {
        let mut __comprehension_result_1186: Vec<i64> = Vec::new();
        let __comprehension_source_1185 = (available.clone());
        for index in __comprehension_source_1185.iter().cloned() {
            if (improvement_score(game, (unit).owner, tile, index)? > 0i64) {
                __comprehension_result_1186.push(index);
            }
        }
        __comprehension_result_1186
    };
    Ok('__extreme: {
        let __values = &positive;
        let mut __items = __values.iter();
        let Some(mut __best) = __items.next() else {
            break '__extreme None;
        };
        let mut __best_key = {
            let index = (*__best).clone();
            (
                improvement_score(game, (unit).owner, tile, index)?,
                (({
                    let __source = &(rules).worker_jobs;
                    let __key = index;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .turns_to_complete)
                    .checked_neg()
                    .ok_or("integer overflow")?,
            )
        };
        for __candidate in __items {
            let __key = {
                let index = (*__candidate).clone();
                (
                    improvement_score(game, (unit).owner, tile, index)?,
                    (({
                        let __source = &(rules).worker_jobs;
                        let __key = index;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .turns_to_complete)
                        .checked_neg()
                        .ok_or("integer overflow")?,
                )
            };
            if __key > __best_key {
                __best = __candidate;
                __best_key = __key;
            }
        }
        Some((*__best).clone())
    })
}

// Python: civ3_ai/worker_ai.py:93
pub(crate) fn plan_worker(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<Option<WorkerPlan>> {
    let mut origin: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if (origin).is_none() {
        return Err("Worker is outside the map".to_string().into());
    }
    let mut cities: Vec<crate::openciv3::cities::City> = {
        let mut __comprehension_result_1188: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_1187 = ((game).cities.clone());
        for city in __comprehension_source_1187.iter().cloned() {
            if ((city).owner == (unit).owner) {
                __comprehension_result_1188.push(city.clone());
            }
        }
        __comprehension_result_1188
    };
    let mut city_ids: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_1190: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_1189 = (cities.clone());
        for city in __comprehension_source_1189.iter().cloned() {
            __comprehension_result_1190.insert((city).id);
        }
        __comprehension_result_1190
    };
    let mut high: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_1193: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_1191 = (cities.clone());
        for city in __comprehension_source_1191.iter().cloned() {
            let __comprehension_source_1192 = ((city).residents.clone());
            for resident in __comprehension_source_1192.iter().cloned() {
                if (&(resident).tile_worked).is_some() {
                    __comprehension_result_1193.insert(
                        (*((resident).tile_worked.clone())
                            .as_ref()
                            .ok_or("expected a value")?)
                        .clone(),
                    );
                }
            }
        }
        __comprehension_result_1193
    };
    let mut low: std::collections::BTreeSet<(i64, i64)> = std::collections::BTreeSet::new();
    for mut tile in (&(&(game).world).tiles).iter() {
        let mut point: (i64, i64) = ((tile).x, (tile).y);
        if match (((game).ownership.clone()).get(&(point.clone())).cloned()) {
            Some(__value) => {
                let __needle = __value;
                let __container = &city_ids;
                __container.contains(&__needle)
            }
            None => false,
        } {
            (if important_resource(game, (unit).owner, tile)? {
                high.clone()
            } else {
                low.clone()
            })
            .insert(point);
        }
    }
    let (mut network, mut hydro): (
        crate::openciv3::trade_network::TradeNetwork,
        crate::openciv3::hydrology::Hydrology,
    ) = (
        crate::openciv3::trade_network::TradeNetwork____post_init__(
            crate::openciv3::trade_network::TradeNetwork {
                game: (*game).clone(),
                owner: Some((unit).owner),
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
        crate::openciv3::hydrology::Hydrology__from_world(&(game).world)?,
    );
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (unit).owner)?;

    for mut points in {
        let __tuple_items = (high, low);
        [__tuple_items.0, __tuple_items.1]
    } {
        for mut tile in {
            let __values = {
                let mut __comprehension_result_1195: Vec<crate::openciv3::world::Tile> = Vec::new();
                let __comprehension_source_1194 = ((&(game).world).tiles.clone());
                for tile in __comprehension_source_1194.iter().cloned() {
                    if {
                        let __needle = ((tile).x, (tile).y);
                        let __container = &points;
                        __container.contains(&__needle)
                    } {
                        __comprehension_result_1195.push(tile.clone());
                    }
                }
                __comprehension_result_1195
            };
            let __reverse = false;
            rt::sorted_by_comparable_key(
                __values,
                |__item| {
                    plan_worker__priority(
                        player.clone(),
                        game.clone(),
                        unit.clone(),
                        origin.clone(),
                        __item,
                    )
                },
                __reverse,
                |left, right| left.0.cmp(&right.0).then(left.1.total_cmp(&right.1)),
            )?
        } {
            let mut job: Option<i64> = {
                let __call_1196_0 = game;
                let __call_1196_1 = unit;
                let __call_1196_2 = &tile;
                let __call_1196_3 = &(Some(network.clone()));
                let __call_1196_4 = &(Some(hydro.clone()));
                choose_improvement(
                    __call_1196_0,
                    __call_1196_1,
                    __call_1196_2,
                    __call_1196_3,
                    __call_1196_4,
                )
            }?;
            if (job).is_some() {
                let mut path: crate::openciv3::pathfinding::UnitPath =
                    crate::openciv3::pathfinding::find_path(
                        game,
                        unit,
                        &tile,
                        &({
                            let mut __result = std::collections::BTreeSet::new();
                            for __item in vec![].into_iter() {
                                __result.insert(__item);
                            }
                            __result
                        }),
                    )?;
                if (path).reachable {
                    return Ok(Some(WorkerPlan {
                        path: path,
                        job: (*(job).as_ref().ok_or("expected a value")?).clone(),
                    }));
                }
            }
        }
    }
    Ok(None)
}

// Python: civ3_ai/worker_ai.py:122
pub(crate) fn advance_worker_plan(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    plan: &WorkerPlan,
    rng: &Option<rt::Random>,
    mut work_en_route: bool,
) -> rt::Result<WorkerStep> {
    if !(({
        let mut __comprehension_result_1198: Vec<bool> = Vec::new();
        let __comprehension_source_1197 = ((game).units.clone());
        for other in __comprehension_source_1197.iter().cloned() {
            __comprehension_result_1198.push(((other).id == (unit).id));
        }
        __comprehension_result_1198
    })
    .into_iter()
    .any(|__value| __value))
    {
        return Ok(WorkerStep {
            plan: None,
            movement: None,
            started_job: None,
            completion: None,
        });
    }
    if ((unit).movement_remaining <= 0.0001f64) {
        return Ok(WorkerStep {
            plan: Some((*plan).clone()),
            movement: None,
            started_job: None,
            completion: None,
        });
    }
    let mut tile: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if !((tile).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    let mut at_target: bool = ((
        ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
        ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
    ) == (&(plan).path).destination.clone());
    let mut job: Option<i64> = (if at_target { Some((plan).job) } else { None });
    if (!(at_target) && work_en_route) {
        job = choose_improvement(
            game,
            unit,
            &((*(tile).as_ref().ok_or("expected a value")?).clone()),
            &None,
            &None,
        )?;
    }
    if (job).is_some() {
        if !(crate::openciv3::worker_rules::can_work(
            game,
            unit,
            (*(job.clone()).as_ref().ok_or("expected a value")?).clone(),
            None,
            &None,
            &None,
        )?) {
            return Ok(WorkerStep {
                plan: None,
                movement: None,
                started_job: None,
                completion: None,
            });
        }
        let mut completion: Option<crate::openciv3::worker_jobs::JobCompletion> =
            crate::openciv3::worker_jobs::assign_worker_job(
                game,
                (*unit).clone(),
                (*(job.clone()).as_ref().ok_or("expected a value")?).clone(),
            )?;
        return Ok(WorkerStep {
            plan: Some((*plan).clone()),
            started_job: job,
            completion: completion,
            movement: None,
        });
    }
    if (!((&(plan).path).reachable) || !(((&(&(plan).path).steps).len() as i64) != 0i64)) {
        return Ok(WorkerStep {
            plan: None,
            movement: None,
            started_job: None,
            completion: None,
        });
    }
    let mut movement: crate::openciv3::unit_movement::MoveResult = {
        let __call_1199_0 = &((*game).clone());
        let __call_1199_1 = &((*unit).clone());
        let __call_1199_2 = &({
            let __star_args_1200: Vec<i64> = {
                let __tuple_value = &(rt::at(&(&(plan).path).steps, 0i64)?);
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_1200.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &(game).world,
                rt::at(&__star_args_1200, 0 as i64)?,
                rt::at(&__star_args_1200, 1 as i64)?,
            )?
        });
        let __call_1199_3 = rng;
        let __call_1199_default_3 = &({
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        });
        let __call_1199_default_4 = None;
        crate::openciv3::unit_movement::move_unit(
            __call_1199_0,
            __call_1199_1,
            __call_1199_2,
            __call_1199_default_3,
            __call_1199_default_4,
            __call_1199_3,
        )
    }?;
    if ((movement).status.clone() == crate::openciv3::unit_movement::MoveStatus::EXHAUSTED) {
        return Ok(WorkerStep {
            plan: Some((*plan).clone()),
            movement: Some(movement),
            started_job: None,
            completion: None,
        });
    }
    if (((movement).status.clone() != crate::openciv3::unit_movement::MoveStatus::MOVED)
        || (&(movement).combat).is_some())
    {
        return Ok(WorkerStep {
            plan: None,
            movement: Some(movement),
            started_job: None,
            completion: None,
        });
    }
    Ok(WorkerStep {
        plan: Some({
            let mut __replacement = ((*plan).clone()).clone();
            __replacement.path = {
                let mut __replacement = ((plan).path.clone()).clone();
                __replacement.steps = rt::list_slice(&(&(plan).path).steps, 1i64, i64::MAX);
                __replacement
            };
            __replacement
        }),
        movement: Some(movement),
        started_job: None,
        completion: None,
    })
}

// Python: civ3_ai/worker_ai.py:107
pub(crate) fn plan_worker__priority(
    mut player: crate::openciv3::players::Player,
    mut game: crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
    mut origin: Option<crate::openciv3::world::Tile>,
    mut tile: crate::openciv3::world::Tile,
) -> rt::Result<(i64, f64)> {
    let mut value: crate::civ::economy::Yield = {
        let __call_1201_0 = &(tile.clone());
        let __call_1201_1 = &player;
        let __call_1201_2 = &(Some(rt::at(&(&(game).scenario).civilizations, (unit).owner)?));
        let __call_1201_3 = &((&(game).scenario).rules.clone());
        let __call_1201_4 =
            &(Some((crate::openciv3::hydrology::river_edges(&(game).world, &tile)?) != 0));
        let __call_1201_default_4 = &None;
        let __call_1201_default_5 = false;
        let __call_1201_default_6 = false;
        let __call_1201_default_7 = &(vec![]);
        crate::openciv3::yields::tile_yield(
            __call_1201_0,
            __call_1201_1,
            __call_1201_2,
            __call_1201_3,
            __call_1201_default_4,
            __call_1201_default_5,
            __call_1201_default_6,
            __call_1201_default_7,
            __call_1201_4,
        )
    }?;
    let mut score: f64 = crate::openciv3::yields::tile_assignment_score(
        &value,
        crate::openciv3::rules::RuleCatalog__food_per_citizen(&(&(game).scenario).rules)?,
    )?;
    Ok((
        crate::strategy::grid::distance(
            &({
                let __structural_value = (game).world.clone();
                crate::strategy::grid::DistanceMap {
                    width: (__structural_value).width.clone(),
                    height: (__structural_value).height.clone(),
                    wrap_x: (__structural_value).wrap_x.clone(),
                    wrap_y: (__structural_value).wrap_y.clone(),
                }
            }),
            &({
                let __structural_value = (*(origin).as_ref().ok_or("expected a value")?).clone();
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
            &({
                let __structural_value = tile;
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
        )?,
        -(score),
    ))
}
