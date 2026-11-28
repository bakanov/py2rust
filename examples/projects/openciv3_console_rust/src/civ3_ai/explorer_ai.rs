use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct ExplorationPlan {
    pub(crate) path: crate::openciv3::pathfinding::UnitPath,
    pub(crate) score: i64,
}

#[derive(Clone, PartialEq)]
pub(crate) struct ExplorationStep {
    pub(crate) plan: Option<ExplorationPlan>,
    pub(crate) movement: Option<crate::openciv3::unit_movement::MoveResult>,
}

// Python: civ3_ai/explorer_ai.py:29
pub(crate) fn exploration_score(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<Option<i64>> {
    let mut knowledge: crate::openciv3::visibility::TileKnowledge = (&(game).visibility)
        .get(&((unit).owner))
        .ok_or("missing dict key")?
        .clone();
    let mut point: (i64, i64) = ((tile).x, (tile).y);
    if ({
        let mut __comprehension_result_750: Vec<bool> = Vec::new();
        let __comprehension_source_749 = ((game).cities.clone());
        for city in __comprehension_source_749.iter().cloned() {
            __comprehension_result_750.push((((city).x, (city).y) == point.clone()));
        }
        __comprehension_result_750
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Ok(None);
    }
    let mut targets: Vec<Option<crate::openciv3::world::Tile>> = {
        let mut __comprehension_result_753: Vec<Option<crate::openciv3::world::Tile>> = Vec::new();
        let __comprehension_source_751 = (((knowledge).exploration_targets.clone())
            .iter()
            .map(|(__key, __value)| (__key.clone(), __value.clone()))
            .collect::<Vec<_>>());
        for (owner, target) in __comprehension_source_751.iter().cloned() {
            if (owner != (unit).id) {
                __comprehension_result_753.push({
                    let __star_args_752: Vec<i64> = {
                        let __tuple_value = &(target.clone());
                        vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                    };
                    if !(2..=2).contains(&__star_args_752.len()) {
                        return Err("wrong function argument count".into());
                    }
                    crate::openciv3::world::WorldMap__tile_at(
                        &(game).world,
                        rt::at(&__star_args_752, 0 as i64)?,
                        rt::at(&__star_args_752, 1 as i64)?,
                    )?
                });
            }
        }
        __comprehension_result_753
    };
    if ({
        let mut __comprehension_result_755: Vec<bool> = Vec::new();
        let __comprehension_source_754 = (targets.clone());
        for target in __comprehension_source_754.iter().cloned() {
            __comprehension_result_755.push((target.clone() == Some((*tile).clone())));
        }
        __comprehension_result_755
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Ok(None);
    }
    let mut unknown: i64 = ({
        let mut __comprehension_result_757: Vec<bool> = Vec::new();
        let __comprehension_source_756 = ({
            let mut __left: Vec<crate::openciv3::world::Tile> = vec![(*tile).clone()];
            let __right: Vec<crate::openciv3::world::Tile> =
                crate::openciv3::world::WorldMap__neighbors(&(game).world, tile)?;
            __left.extend(__right);
            __left
        });
        for neighbor in __comprehension_source_756.iter().cloned() {
            __comprehension_result_757.push({
                let __needle = ((neighbor).x, (neighbor).y);
                let __container = &(knowledge).known;
                !__container.contains(&__needle)
            });
        }
        __comprehension_result_757
    })
    .into_iter()
    .map(|value| value as i64)
    .sum::<i64>();
    if !(unknown != 0i64) {
        return Ok(None);
    }
    let mut origin: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if (origin).is_none() {
        return Err("Explorer is outside the map".to_string().into());
    }
    let mut score: i64 = ({
        let __exponent = 2i64;
        if __exponent < 0 {
            return Err("negative integer exponent".into());
        }
        (unknown)
            .checked_pow(__exponent as u32)
            .ok_or("integer power overflow")?
    })
    .checked_sub(crate::strategy::grid::distance(
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
            let __structural_value = (*tile).clone();
            crate::strategy::grid::GridPoint {
                x: (__structural_value).x.clone(),
                y: (__structural_value).y.clone(),
            }
        }),
    )?)
    .ok_or("integer overflow")?;
    let mut cities: Vec<Option<crate::openciv3::world::Tile>> = {
        let mut __comprehension_result_759: Vec<Option<crate::openciv3::world::Tile>> = Vec::new();
        let __comprehension_source_758 = ((game).cities.clone());
        for city in __comprehension_source_758.iter().cloned() {
            if ((city).owner == (unit).owner) {
                __comprehension_result_759.push(crate::openciv3::world::WorldMap__tile_at(
                    &(game).world,
                    (city).x,
                    (city).y,
                )?);
            }
        }
        __comprehension_result_759
    };
    if (((cities).len() as i64) != 0i64) {
        score = (score)
            .checked_sub({
                let __values = &({
                    let mut __comprehension_result_761: Vec<i64> = Vec::new();
                    let __comprehension_source_760 = (cities.clone());
                    for city in __comprehension_source_760.iter().cloned() {
                        if (city).is_some() {
                            __comprehension_result_761.push(crate::strategy::grid::distance(
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
                                    let __structural_value =
                                        (*(city.clone()).as_ref().ok_or("expected a value")?)
                                            .clone();
                                    crate::strategy::grid::GridPoint {
                                        x: (__structural_value).x.clone(),
                                        y: (__structural_value).y.clone(),
                                    }
                                }),
                                &({
                                    let __structural_value = (*tile).clone();
                                    crate::strategy::grid::GridPoint {
                                        x: (__structural_value).x.clone(),
                                        y: (__structural_value).y.clone(),
                                    }
                                }),
                            )?);
                        }
                    }
                    __comprehension_result_761
                });
                let mut __items = __values.iter();
                let mut __best = __items.next().ok_or("min() arg is an empty sequence")?;
                for __candidate in __items {
                    if __candidate < __best {
                        __best = __candidate;
                    }
                }
                (*__best).clone()
            })
            .ok_or("integer overflow")?;
    }
    if (((targets).len() as i64) != 0i64) {
        score = (score)
            .checked_add({
                let __values = &({
                    let mut __comprehension_result_763: Vec<i64> = Vec::new();
                    let __comprehension_source_762 = (targets.clone());
                    for target in __comprehension_source_762.iter().cloned() {
                        if (target).is_some() {
                            __comprehension_result_763.push(crate::strategy::grid::distance(
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
                                    let __structural_value =
                                        (*(target.clone()).as_ref().ok_or("expected a value")?)
                                            .clone();
                                    crate::strategy::grid::GridPoint {
                                        x: (__structural_value).x.clone(),
                                        y: (__structural_value).y.clone(),
                                    }
                                }),
                                &({
                                    let __structural_value = (*tile).clone();
                                    crate::strategy::grid::GridPoint {
                                        x: (__structural_value).x.clone(),
                                        y: (__structural_value).y.clone(),
                                    }
                                }),
                            )?);
                        }
                    }
                    __comprehension_result_763
                });
                let mut __items = __values.iter();
                let mut __best = __items.next().ok_or("min() arg is an empty sequence")?;
                for __candidate in __items {
                    if __candidate < __best {
                        __best = __candidate;
                    }
                }
                (*__best).clone()
            })
            .ok_or("integer overflow")?;
    }
    Ok(Some(score))
}

// Python: civ3_ai/explorer_ai.py:52
pub(crate) fn _safe_naval_route(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    kind: &crate::openciv3::unit_rules::UnitPrototype,
    path: &crate::openciv3::pathfinding::UnitPath,
    mut safe_sea: bool,
) -> rt::Result<bool> {
    let mut source: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if !((source).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    let mut remaining: f64 = (unit).movement_remaining;
    for mut point in (&(path).steps).iter() {
        if (remaining <= 0.0001f64) {
            if {
                let __call_764_0 = kind;
                let __call_764_1 =
                    &((*(source.clone()).as_ref().ok_or("expected a value")?).clone());
                let __call_764_2 = safe_sea;
                crate::openciv3::naval_risk::hazardous_waters(
                    __call_764_0,
                    __call_764_1,
                    __call_764_2,
                )
            }? {
                return Ok(false);
            }
            remaining = ((kind).movement as f64);
        }
        let mut target: Option<crate::openciv3::world::Tile> = {
            let __star_args_765: Vec<i64> = {
                let __tuple_value = &((*point).clone());
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_765.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &(game).world,
                rt::at(&__star_args_765, 0 as i64)?,
                rt::at(&__star_args_765, 1 as i64)?,
            )?
        };
        if !((target).is_some()) {
            rt::assertion(false, &("".to_string()))?;
        }
        if (crate::openciv3::hydrology::land_strip(
            &(game).world,
            &((*(source.clone()).as_ref().ok_or("expected a value")?).clone()),
            &((*(target.clone()).as_ref().ok_or("expected a value")?).clone()),
        )? || !(crate::openciv3::unit_entry::EntryIntent__peaceful({
            let __call_766_0 = game;
            let __call_766_1 = unit;
            let __call_766_2 = &target;
            let __call_766_3 = false;
            crate::openciv3::unit_entry::resolve_entry(
                __call_766_0,
                __call_766_1,
                __call_766_2,
                __call_766_3,
            )
        }?)?)) {
            return Ok(false);
        }
        remaining = rt::finite(
            remaining - {
                let __call_767_0 = game;
                let __call_767_1 = (unit).owner;
                let __call_767_2 = &((*(source).as_ref().ok_or("expected a value")?).clone());
                let __call_767_3 =
                    &((*(target.clone()).as_ref().ok_or("expected a value")?).clone());
                let __call_767_4 = &(Some((unit).prototype));
                let __call_767_5 = false;
                let __call_767_default_4 = &({
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in vec![].into_iter() {
                        __result.insert(__item);
                    }
                    __result
                });
                crate::openciv3::pathfinding::movement_cost(
                    __call_767_0,
                    __call_767_1,
                    __call_767_2,
                    __call_767_3,
                    __call_767_default_4,
                    __call_767_4,
                    __call_767_5,
                )
            }?,
        )?;
        source = target;
    }
    Ok(!({
        let __call_768_0 = kind;
        let __call_768_1 = &((*(source).as_ref().ok_or("expected a value")?).clone());
        let __call_768_2 = safe_sea;
        crate::openciv3::naval_risk::hazardous_waters(__call_768_0, __call_768_1, __call_768_2)
    }?))
}

// Python: civ3_ai/explorer_ai.py:71
pub(crate) fn plan_exploration(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut reserve: bool,
) -> rt::Result<Option<ExplorationPlan>> {
    let mut knowledge: crate::openciv3::visibility::TileKnowledge = (&(game).visibility)
        .get(&((unit).owner))
        .ok_or("missing dict key")?
        .clone();
    if reserve {
        ((knowledge).exploration_targets).remove(&((unit).id));
    }
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    let mut land: bool = ((kind).domain == 0i64);
    let mut avoid_wreck: bool = (((kind).domain == 1i64)
        && (((kind).abilities & (2048i64 | 4096i64)) != 0
            && !(({
                let __source = &(game).players;
                let __key = (unit).owner;
                &__source[rt::index(__source.len(), __key)?]
            })
            .human)));
    let mut safe_sea: bool =
        (avoid_wreck && crate::openciv3::naval_risk::safe_sea_travel(game, (unit).owner)?);
    let mut candidates: Vec<(i64, crate::openciv3::world::Tile)> = vec![];
    for mut tile in (&(&(game).world).tiles).iter() {
        if ({
            let __needle = ((tile).x, (tile).y);
            let __container = &(knowledge).frontier;
            !__container.contains(&__needle)
        } || (crate::openciv3::hydrology::is_water(tile)? == land))
        {
            continue;
        }
        if (avoid_wreck && {
            let __call_769_0 = &kind;
            let __call_769_1 = tile;
            let __call_769_2 = safe_sea;
            crate::openciv3::naval_risk::hazardous_waters(__call_769_0, __call_769_1, __call_769_2)
        }?) {
            continue;
        }
        let mut score: Option<i64> = exploration_score(game, unit, tile)?;
        if (score).is_some() {
            {
                candidates.push((
                    (*(score.clone()).as_ref().ok_or("expected a value")?).clone(),
                    (*tile).clone(),
                ));
            };
        }
    }
    for mut for_target_88_4 in {
        let mut __decorated: Vec<(i64, (i64, crate::openciv3::world::Tile))> = Vec::new();
        for __item in (candidates).into_iter() {
            let item = __item;
            let __key = { (item).0.clone() };
            __decorated.push((__key, item));
        }
        __decorated.sort_by(|left, right| {
            if true {
                right.0.cmp(&left.0)
            } else {
                left.0.cmp(&right.0)
            }
        });
        let mut __result = Vec::new();
        for (_, __item) in __decorated {
            __result.push(__item);
        }
        __result
    } {
        let (mut score, mut tile): (i64, crate::openciv3::world::Tile) = for_target_88_4;
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
        if ((path).reachable
            && (!(avoid_wreck) || {
                let __call_770_0 = game;
                let __call_770_1 = unit;
                let __call_770_2 = &kind;
                let __call_770_3 = &path;
                let __call_770_4 = safe_sea;
                _safe_naval_route(
                    __call_770_0,
                    __call_770_1,
                    __call_770_2,
                    __call_770_3,
                    __call_770_4,
                )
            }?))
        {
            if reserve {
                knowledge
                    .exploration_targets
                    .insert((unit).id, (path).destination.clone());
            }
            return Ok(Some(ExplorationPlan {
                path: path,
                score: score,
            }));
        }
    }
    if (reserve
        && (!(land) && (!(avoid_wreck) || !(((&(knowledge).frontier).len() as i64) != 0i64))))
    {
        knowledge.fully_explored_oceans = true;
    }
    Ok(None)
}

// Python: civ3_ai/explorer_ai.py:99
pub(crate) fn advance_exploration_plan(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    plan: &ExplorationPlan,
    rng: &Option<rt::Random>,
) -> rt::Result<ExplorationStep> {
    let mut knowledge: crate::openciv3::visibility::TileKnowledge = (&(game).visibility)
        .get(&((unit).owner))
        .ok_or("missing dict key")?
        .clone();
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    let mut avoid_wreck: bool = (((kind).domain == 1i64)
        && (((kind).abilities & (2048i64 | 4096i64)) != 0
            && !(({
                let __source = &(game).players;
                let __key = (unit).owner;
                &__source[rt::index(__source.len(), __key)?]
            })
            .human)));
    let mut safe_sea: bool =
        (avoid_wreck && crate::openciv3::naval_risk::safe_sea_travel(game, (unit).owner)?);
    let mut origin: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    let mut endangered: bool = (avoid_wreck
        && ((origin).is_some() && {
            let __call_771_0 = &kind;
            let __call_771_1 = &((*(origin.clone()).as_ref().ok_or("expected a value")?).clone());
            let __call_771_2 = safe_sea;
            crate::openciv3::naval_risk::hazardous_waters(__call_771_0, __call_771_1, __call_771_2)
        }?));
    if (!(({
        let mut __comprehension_result_773: Vec<bool> = Vec::new();
        let __comprehension_source_772 = ((game).units.clone());
        for other in __comprehension_source_772.iter().cloned() {
            __comprehension_result_773.push(((other).id == (unit).id));
        }
        __comprehension_result_773
    })
    .into_iter()
    .any(|__value| __value))
        || (({
            let __needle = (&(plan).path).destination.clone();
            let __container = &(knowledge).known;
            __container.contains(&__needle)
        } && !(endangered))
            || ((((unit).x, (unit).y) == (&(plan).path).destination.clone())
                || !(((&(&(plan).path).steps).len() as i64) != 0i64))))
    {
        ((knowledge).exploration_targets).remove(&((unit).id));
        return Ok(ExplorationStep {
            plan: None,
            movement: None,
        });
    }
    let mut destination: Option<crate::openciv3::world::Tile> = {
        let __star_args_774: Vec<i64> = {
            let __tuple_value = &(rt::at(&(&(plan).path).steps, 0i64)?);
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        };
        if !(2..=2).contains(&__star_args_774.len()) {
            return Err("wrong function argument count".into());
        }
        crate::openciv3::world::WorldMap__tile_at(
            &(game).world,
            rt::at(&__star_args_774, 0 as i64)?,
            rt::at(&__star_args_774, 1 as i64)?,
        )?
    };
    let mut entering_risk: bool = (avoid_wreck
        && ((destination).is_some() && {
            let __call_775_0 = &kind;
            let __call_775_1 =
                &((*(destination.clone()).as_ref().ok_or("expected a value")?).clone());
            let __call_775_2 = safe_sea;
            crate::openciv3::naval_risk::hazardous_waters(__call_775_0, __call_775_1, __call_775_2)
        }?));
    if (entering_risk
        && !({
            let __call_776_0 = game;
            let __call_776_1 = unit;
            let __call_776_2 = &kind;
            let __call_776_3 = &(plan).path;
            let __call_776_4 = safe_sea;
            _safe_naval_route(
                __call_776_0,
                __call_776_1,
                __call_776_2,
                __call_776_3,
                __call_776_4,
            )
        }?))
    {
        ((knowledge).exploration_targets).remove(&((unit).id));
        return Ok(ExplorationStep {
            plan: None,
            movement: None,
        });
    }
    let mut result: crate::openciv3::unit_movement::MoveResult = {
        let __call_777_0 = game;
        let __call_777_1 = unit;
        let __call_777_2 = &destination;
        let __call_777_3 = rng;
        let __call_777_default_3 = &({
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        });
        let __call_777_default_4 = None;
        crate::openciv3::unit_movement::move_unit(
            __call_777_0,
            __call_777_1,
            __call_777_2,
            __call_777_default_3,
            __call_777_default_4,
            __call_777_3,
        )
    }?;
    if ((result).status.clone() == crate::openciv3::unit_movement::MoveStatus::EXHAUSTED) {
        return Ok(ExplorationStep {
            plan: Some((*plan).clone()),
            movement: Some(result),
        });
    }
    if (((result).status.clone() != crate::openciv3::unit_movement::MoveStatus::MOVED)
        || ((&(result).combat).is_some()
            || ((&(result).raid).is_some()
                || (({
                    let __needle = (&(plan).path).destination.clone();
                    let __container = &(knowledge).known;
                    __container.contains(&__needle)
                } && !(entering_risk))
                    || (((&(&(plan).path).steps).len() as i64) == 1i64)))))
    {
        ((knowledge).exploration_targets).remove(&((unit).id));
        return Ok(ExplorationStep {
            plan: None,
            movement: Some(result),
        });
    }
    Ok(ExplorationStep {
        plan: Some({
            let mut __replacement = ((*plan).clone()).clone();
            __replacement.path = {
                let mut __replacement = ((plan).path.clone()).clone();
                __replacement.steps = rt::list_slice(&(&(plan).path).steps, 1i64, i64::MAX);
                __replacement
            };
            __replacement
        }),
        movement: Some(result),
    })
}
