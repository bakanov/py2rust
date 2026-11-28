use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct DefensePlan {
    pub(crate) path: crate::openciv3::pathfinding::UnitPath,
    pub(crate) city: Option<i64>,
}

#[derive(Clone, PartialEq)]
pub(crate) struct DefenseStep {
    pub(crate) plan: Option<DefensePlan>,
    pub(crate) movement: Option<crate::openciv3::unit_movement::MoveResult>,
}

// Python: civ3_ai/defender_ai.py:26
pub(crate) fn defense_scores(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut min_defenders: i64,
) -> rt::Result<indexmap::IndexMap<i64, i64>> {
    if (min_defenders < 0i64) {
        return Err("Minimum defenders must be nonnegative".to_string().into());
    }
    let mut origin: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if (origin).is_none() {
        return Err("Defender is outside the map".to_string().into());
    }
    let mut scores: indexmap::IndexMap<i64, i64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut city in (&(game).cities).iter() {
        if ((city).owner != (unit).owner) {
            continue;
        }
        let mut target: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(&(game).world, (city).x, (city).y)?;
        if !((target).is_some()) {
            rt::assertion(false, &("".to_string()))?;
        }
        let mut count: i64 = ({
            let mut __comprehension_result_732: Vec<bool> = Vec::new();
            let __comprehension_source_731 = ((game).units.clone());
            for other in __comprehension_source_731.iter().cloned() {
                __comprehension_result_732.push(
                    (((other).owner == (city).owner)
                        && ((((other).x, (other).y) == ((city).x, (city).y))
                            && crate::openciv3::unit_entry::can_defend_on_land(game, &other)?)),
                );
            }
            __comprehension_result_732
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        let mut assigned: i64 = ({
            let mut __comprehension_result_734: Vec<bool> = Vec::new();
            let __comprehension_source_733 = ((game).units.clone());
            for other in __comprehension_source_733.iter().cloned() {
                __comprehension_result_734.push(
                    (((other).owner == (unit).owner)
                        && ((other).defender_destination.clone() == Some(((city).x, (city).y)))),
                );
            }
            __comprehension_result_734
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        {
            let __value = ((if (count < min_defenders) { 10i64 } else { 0i64 })
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
                        let __structural_value =
                            (*(origin.clone()).as_ref().ok_or("expected a value")?).clone();
                        crate::strategy::grid::GridPoint {
                            x: (__structural_value).x.clone(),
                            y: (__structural_value).y.clone(),
                        }
                    }),
                    &({
                        let __structural_value =
                            (*(target).as_ref().ok_or("expected a value")?).clone();
                        crate::strategy::grid::GridPoint {
                            x: (__structural_value).x.clone(),
                            y: (__structural_value).y.clone(),
                        }
                    }),
                )?)
                .ok_or("integer overflow")?)
            .checked_sub((3i64).checked_mul(assigned).ok_or("integer overflow")?)
            .ok_or("integer overflow")?;
            let __key = (city).id;
            scores.insert(__key, __value);
        }
    }
    Ok(scores)
}

// Python: civ3_ai/defender_ai.py:45
pub(crate) fn defend_in_place(mut unit: crate::openciv3::units::Unit) -> rt::Result<DefensePlan> {
    let mut point: (i64, i64) = ((unit).x, (unit).y);
    unit.defender_destination = Some(point.clone());
    Ok(DefensePlan {
        path: crate::openciv3::pathfinding::UnitPath {
            destination: point,
            steps: vec![],
            reachable: true,
            cost: 0.0f64,
        },
        city: None,
    })
}

// Python: civ3_ai/defender_ai.py:51
pub(crate) fn plan_city_defense(
    game: &crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
    mut min_defenders: i64,
) -> rt::Result<Option<DefensePlan>> {
    if !(crate::openciv3::unit_entry::can_defend_on_land(game, &unit)?) {
        return Ok(Some(defend_in_place(unit)?));
    }
    let mut scores: indexmap::IndexMap<i64, i64> = defense_scores(game, &unit, min_defenders)?;
    let mut cities: indexmap::IndexMap<i64, crate::openciv3::cities::City> = {
        let mut __comprehension_result_736: indexmap::IndexMap<i64, crate::openciv3::cities::City> =
            indexmap::IndexMap::new();
        let __comprehension_source_735 = ((game).cities.clone());
        for city in __comprehension_source_735.iter().cloned() {
            if ((city).owner == (unit).owner) {
                {
                    let (__key, __value) = ((city).id, city.clone());
                    __comprehension_result_736.insert(__key, __value);
                }
            }
        }
        __comprehension_result_736
    };
    for mut selected in {
        let mut __decorated: Vec<(i64, i64)> = Vec::new();
        for __item in ((scores.clone()).keys().cloned().collect::<Vec<_>>()).into_iter() {
            let selected = __item;
            let __key = { (scores).get(&(selected)).ok_or("missing dict key")?.clone() };
            __decorated.push((__key, selected));
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
        if (((scores).get(&(selected)).ok_or("missing dict key")?.clone() <= 0i64)
            && (min_defenders
                != ({
                    let __exponent = 31i64;
                    if __exponent < 0 {
                        return Err("negative integer exponent".into());
                    }
                    (2i64)
                        .checked_pow(__exponent as u32)
                        .ok_or("integer power overflow")?
                })
                .checked_sub(1i64)
                .ok_or("integer overflow")?))
        {
            break;
        }
        let mut city: crate::openciv3::cities::City =
            (cities).get(&(selected)).ok_or("missing dict key")?.clone();
        let mut tile: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(&(game).world, (city).x, (city).y)?;
        if !((tile).is_some()) {
            rt::assertion(false, &("".to_string()))?;
        }
        let mut path: crate::openciv3::pathfinding::UnitPath =
            crate::openciv3::pathfinding::find_path(
                game,
                &unit,
                &((*(tile).as_ref().ok_or("expected a value")?).clone()),
                &({
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in vec![].into_iter() {
                        __result.insert(__item);
                    }
                    __result
                }),
            )?;
        if (path).reachable {
            unit.defender_destination = Some((path).destination.clone());
            return Ok(Some(DefensePlan {
                path: path,
                city: Some((city).id),
            }));
        }
    }
    unit.defender_destination = None;
    Ok(None)
}

/// Fortify at the destination; cancel routes to cities lost or destroyed.
// Python: civ3_ai/defender_ai.py:71
pub(crate) fn advance_defense_plan(
    game: &crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
    plan: &DefensePlan,
    mut rng: rt::Random,
) -> rt::Result<DefenseStep> {
    if (!(({
        let mut __comprehension_result_738: Vec<bool> = Vec::new();
        let __comprehension_source_737 = ((game).units.clone());
        for other in __comprehension_source_737.iter().cloned() {
            __comprehension_result_738.push(((other).id == (unit).id));
        }
        __comprehension_result_738
    })
    .into_iter()
    .any(|__value| __value))
        || ((&(plan).city).is_some()
            && !(({
                let mut __comprehension_result_740: Vec<bool> = Vec::new();
                let __comprehension_source_739 = ((game).cities.clone());
                for city in __comprehension_source_739.iter().cloned() {
                    __comprehension_result_740.push(
                        ((Some((city).id) == (plan).city.clone())
                            && (((city).owner == (unit).owner)
                                && (((city).x, (city).y) == (&(plan).path).destination.clone()))),
                    );
                }
                __comprehension_result_740
            })
            .into_iter()
            .any(|__value| __value))))
    {
        unit.defender_destination = None;
        return Ok(DefenseStep {
            plan: None,
            movement: None,
        });
    }
    if (((unit).x, (unit).y) == (&(plan).path).destination.clone()) {
        crate::openciv3::unit_turns::fortify_unit(unit)?;
        return Ok(DefenseStep {
            plan: None,
            movement: None,
        });
    }
    if (!((&(plan).path).reachable) || !(((&(&(plan).path).steps).len() as i64) != 0i64)) {
        unit.defender_destination = None;
        return Ok(DefenseStep {
            plan: None,
            movement: None,
        });
    }
    let mut result: crate::openciv3::unit_movement::MoveResult = {
        let __call_741_0 = &((*game).clone());
        let __call_741_1 = &(unit.clone());
        let __call_741_2 = &({
            let __star_args_742: Vec<i64> = {
                let __tuple_value = &(rt::at(&(&(plan).path).steps, 0i64)?);
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_742.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &(game).world,
                rt::at(&__star_args_742, 0 as i64)?,
                rt::at(&__star_args_742, 1 as i64)?,
            )?
        });
        let __call_741_3 = &(Some(rng.clone()));
        let __call_741_default_3 = &({
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        });
        let __call_741_default_4 = None;
        crate::openciv3::unit_movement::move_unit(
            __call_741_0,
            __call_741_1,
            __call_741_2,
            __call_741_default_3,
            __call_741_default_4,
            __call_741_3,
        )
    }?;
    if ((result).status.clone() == crate::openciv3::unit_movement::MoveStatus::EXHAUSTED) {
        return Ok(DefenseStep {
            plan: Some((*plan).clone()),
            movement: Some(result),
        });
    }
    if (((result).status.clone() != crate::openciv3::unit_movement::MoveStatus::MOVED)
        || ((&(result).combat).is_some() || (&(result).raid).is_some()))
    {
        unit.defender_destination = None;
        return Ok(DefenseStep {
            plan: None,
            movement: Some(result),
        });
    }
    let mut remaining: DefensePlan = {
        let mut __replacement = ((*plan).clone()).clone();
        __replacement.path = {
            let mut __replacement = ((plan).path.clone()).clone();
            __replacement.steps = rt::list_slice(&(&(plan).path).steps, 1i64, i64::MAX);
            __replacement
        };
        __replacement
    };
    Ok(DefenseStep {
        plan: Some(remaining),
        movement: Some(result),
    })
}
