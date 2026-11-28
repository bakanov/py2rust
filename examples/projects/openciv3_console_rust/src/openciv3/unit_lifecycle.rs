use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct RemovalResult {
    pub(crate) removed: Vec<i64>,
    pub(crate) defeated: Vec<i64>,
    pub(crate) shields: i64,
}

// Python: openciv3/unit_lifecycle.py:22
pub(crate) fn _king(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<bool> {
    Ok((({
        let __source = &(&(&(game).scenario).rules).units;
        let __key = (unit).prototype;
        &__source[rt::index(__source.len(), __key)?]
    })
    .abilities
        & 536870912i64)
        != 0)
}

// Python: openciv3/unit_lifecycle.py:26
pub(crate) fn _has_king(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<bool> {
    Ok(({
        let mut __comprehension_result_472: Vec<bool> = Vec::new();
        let __comprehension_source_471 = ((game).units.clone());
        for unit in __comprehension_source_471.iter().cloned() {
            __comprehension_result_472.push((((unit).owner == owner) && _king(game, &unit)?));
        }
        __comprehension_result_472
    })
    .into_iter()
    .any(|__value| __value))
}

// Python: openciv3/unit_lifecycle.py:30
pub(crate) fn regicide_survival_after_removal(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    removed: &std::collections::BTreeSet<i64>,
) -> rt::Result<Option<bool>> {
    if !(((&(&(game).scenario).options).victory_flags
        & (rt::int_lshift(1i64, 11i64)? | rt::int_lshift(1i64, 12i64)?))
        != 0i64)
    {
        return Ok(None);
    }
    let mut kings: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_474: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_473 = ((game).units.clone());
        for unit in __comprehension_source_473.iter().cloned() {
            if (((unit).owner == owner) && _king(game, &unit)?) {
                __comprehension_result_474.insert((unit).id);
            }
        }
        __comprehension_result_474
    };
    Ok((if (((kings).len() as i64) != 0i64) {
        Some(
            !({
                let __set_left = kings.clone();
                let __set_right = (*removed).clone();
                let mut __result = std::collections::BTreeSet::new();
                for __item in __set_left.difference(&__set_right) {
                    __result.insert(__item.clone());
                }
                __result
            })
            .is_empty(),
        )
    } else {
        None
    }))
}

/// Remove a unit and its cargo, then apply the existing elimination rule.
// Python: openciv3/unit_lifecycle.py:37
pub(crate) fn remove_unit(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<RemovalResult> {
    remove_units((*game).clone(), &(vec![(*unit).clone()]))
}

// Python: openciv3/unit_lifecycle.py:42
pub(crate) fn remove_unit_state(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<(crate::openciv3::game_state::GameState, RemovalResult)> {
    remove_units_state((*game).clone(), &(vec![(*unit).clone()]))
}

// Python: openciv3/unit_lifecycle.py:46
pub(crate) fn remove_units(
    mut game: crate::openciv3::game_state::GameState,
    units: &[crate::openciv3::units::Unit],
) -> rt::Result<RemovalResult> {
    let (mut game, mut result): (crate::openciv3::game_state::GameState, RemovalResult) =
        remove_units_state(game, units)?;
    Ok(result)
}

/// Remove a group and its cargo before checking elimination and visibility.
///
/// Outside Regicide, a civilization survives with a populated city or a settler.
// Python: openciv3/unit_lifecycle.py:51
pub(crate) fn remove_units_state(
    mut game: crate::openciv3::game_state::GameState,
    units: &[crate::openciv3::units::Unit],
) -> rt::Result<(crate::openciv3::game_state::GameState, RemovalResult)> {
    if !(((units).len() as i64) != 0i64) {
        return Ok((
            game,
            RemovalResult {
                removed: vec![],
                defeated: vec![],
                shields: 0i64,
            },
        ));
    }
    let mut live: indexmap::IndexMap<i64, crate::openciv3::units::Unit> = {
        let mut __comprehension_result_476: indexmap::IndexMap<i64, crate::openciv3::units::Unit> =
            indexmap::IndexMap::new();
        let __comprehension_source_475 = ((game).units.clone());
        for unit in __comprehension_source_475.iter().cloned() {
            {
                let (__key, __value) = ((unit).id, unit.clone());
                __comprehension_result_476.insert(__key, __value);
            }
        }
        __comprehension_result_476
    };
    if ({
        let mut __comprehension_result_478: Vec<bool> = Vec::new();
        let __comprehension_source_477 = (units.to_vec());
        for unit in __comprehension_source_477.iter().cloned() {
            __comprehension_result_478.push({
                let __needle = (unit).id;
                let __container = &live;
                !__container.contains_key(&__needle)
            });
        }
        __comprehension_result_478
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("Unit is not in this game".to_string().into());
    }
    game.next_unit_id = ((game).next_unit_id).max(
        ({
            let __values = &({
                let mut __comprehension_result_480: Vec<i64> = Vec::new();
                let __comprehension_source_479 = ((game).units.clone());
                for other in __comprehension_source_479.iter().cloned() {
                    __comprehension_result_480.push((other).id);
                }
                __comprehension_result_480
            });
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
        .ok_or("integer overflow")?,
    );
    let mut removed: Vec<i64> = vec![];
    let mut affected: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
    let mut pending: Vec<crate::openciv3::units::Unit> =
        ((units.to_vec()).into_iter().rev().collect::<Vec<_>>())
            .iter()
            .cloned()
            .collect::<Vec<_>>();
    let mut defeated: Vec<i64> = vec![];
    let mut lost_kings: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
    let mut regicide: bool = ((&(&(game).scenario).options).victory_flags
        & (rt::int_lshift(1i64, 11i64)? | rt::int_lshift(1i64, 12i64)?))
        != 0;
    while (((pending).len() as i64) != 0i64) {
        let mut dead: crate::openciv3::units::Unit = {
            let __key = -1i64;
            let __index = rt::index(pending.len(), __key)?;
            pending.remove(__index)
        };
        if ((live).remove(&((dead).id))).is_none() {
            continue;
        }
        {
            let __values = {
                let mut __comprehension_result_482: Vec<crate::openciv3::units::Unit> = Vec::new();
                let __comprehension_source_481 = ((game).units.clone());
                for other in __comprehension_source_481.iter().cloned() {
                    if (((other).transported_by.clone() == Some((dead).id))
                        && ((other).id != (dead).id))
                    {
                        __comprehension_result_482.push(other.clone());
                    }
                }
                __comprehension_result_482
            };
            pending.extend(__values);
        };
        {
            affected.insert((dead).owner);
        };
        if (regicide && _king(&game, &dead)?) {
            {
                lost_kings.insert((dead).owner);
            };
        }
        crate::openciv3::unit_missions::clear_unit_missions(game.clone(), dead.clone())?;
        dead.hit_points = 0i64;
        dead.movement_remaining = 0.0f64;
        dead.transported_by = None;
        dead.worker_job = None;
        dead.worker_progress = 0.0f64;
        dead.action = String::new();
        dead.fortified = false;
        dead.skipped_with_full_movement = false;
        dead.defensive_bombards_remaining = 0i64;
        {
            let __removed = (&({
                let mut __comprehension_result_484: Vec<crate::openciv3::units::Unit> = Vec::new();
                let __comprehension_source_483 = ((game).units.clone());
                for unit in __comprehension_source_483.iter().cloned() {
                    if ((unit).id == (dead).id) {
                        __comprehension_result_484.push(unit.clone());
                    }
                }
                __comprehension_result_484
            }))
                .iter()
                .next()
                .cloned()
                .ok_or("StopIteration")?;
            let __index = ((game).units)
                .iter()
                .position(|__item| (*__item).clone() == __removed)
                .ok_or("list.remove: value not found")?;
            ((game).units).remove(__index);
        };
        {
            removed.push((dead).id);
        };
        if ({
            let mut __comprehension_result_486: Vec<bool> = Vec::new();
            let __comprehension_source_485 = (pending.clone());
            for other in __comprehension_source_485.iter().cloned() {
                __comprehension_result_486.push({
                    let __needle = (other).id;
                    let __container = &live;
                    __container.contains_key(&__needle)
                });
            }
            __comprehension_result_486
        })
        .into_iter()
        .any(|__value| __value)
        {
            continue;
        }
        for mut owner in {
            let mut __sorted = (affected.clone()).into_iter().collect::<Vec<_>>();
            __sorted.sort();
            __sorted
        } {
            let mut player: crate::openciv3::players::Player = rt::at(&(game).players, owner)?;
            if (crate::openciv3::players::Player__barbarian(&player)? || (player).defeated) {
                continue;
            }
            if (regicide && _has_king(&game, owner)?) {
                continue;
            }
            if {
                let __needle = owner;
                let __container = &lost_kings;
                __container.contains(&__needle)
            } {
                crate::openciv3::city_lifecycle::raze_cities(
                    game.clone(),
                    &({
                        let mut __comprehension_result_488: Vec<crate::openciv3::cities::City> =
                            Vec::new();
                        let __comprehension_source_487 = ((game).cities.clone());
                        for city in __comprehension_source_487.iter().cloned() {
                            if ((city).owner == owner) {
                                __comprehension_result_488.push(city.clone());
                            }
                        }
                        __comprehension_result_488
                    }),
                )?;
            } else {
                if (({
                    let mut __comprehension_result_490: Vec<bool> = Vec::new();
                    let __comprehension_source_489 = ((game).cities.clone());
                    for city in __comprehension_source_489.iter().cloned() {
                        __comprehension_result_490.push(
                            (((city).owner == owner)
                                && (crate::openciv3::cities::City__size(&city)? > 0i64)),
                        );
                    }
                    __comprehension_result_490
                })
                .into_iter()
                .any(|__value| __value)
                    || ({
                        let mut __comprehension_result_492: Vec<bool> = Vec::new();
                        let __comprehension_source_491 = ((game).units.clone());
                        for other in __comprehension_source_491.iter().cloned() {
                            __comprehension_result_492.push(
                                (((other).owner == owner)
                                    && (({
                                        let __source = &(&(&(game).scenario).rules).units;
                                        let __key = (other).prototype;
                                        &__source[rt::index(__source.len(), __key)?]
                                    })
                                    .orders
                                        & 4194304i64)
                                        != 0),
                            );
                        }
                        __comprehension_result_492
                    })
                    .into_iter()
                    .any(|__value| __value))
                {
                    continue;
                }
            }
            player.defeated = true;
            {
                defeated.push(owner);
            };
            {
                let __values = {
                    let mut __comprehension_result_494: Vec<crate::openciv3::units::Unit> =
                        Vec::new();
                    let __comprehension_source_493 = ((game).units.clone());
                    for other in __comprehension_source_493.iter().cloned() {
                        if ((other).owner == owner) {
                            __comprehension_result_494.push(other.clone());
                        }
                    }
                    __comprehension_result_494
                };
                pending.extend(__values);
            };
            ((player).contacts).clear();
            for mut other_player in (&(game).players).iter().cloned() {
                ((other_player).contacts).remove(&(owner));
            }
            game.diplomacy.relationships = {
                let mut __comprehension_result_496: indexmap::IndexMap<
                    (i64, i64),
                    crate::openciv3::diplomacy::Relationship,
                > = indexmap::IndexMap::new();
                let __comprehension_source_495 = (((&(game).diplomacy).relationships.clone())
                    .iter()
                    .map(|(__key, __value)| (__key.clone(), __value.clone()))
                    .collect::<Vec<_>>());
                for (pair, relation) in __comprehension_source_495.iter().cloned() {
                    if {
                        let __needle = owner;
                        let __container = &({
                            let __tuple_value = &pair;
                            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                        });
                        !__container.contains(&__needle)
                    } {
                        {
                            let (__key, __value) = (pair.clone(), relation.clone());
                            __comprehension_result_496.insert(__key, __value);
                        }
                    }
                }
                __comprehension_result_496
            };
        }
    }
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
    Ok((
        game,
        RemovalResult {
            removed: (removed).iter().cloned().collect::<Vec<_>>(),
            defeated: (defeated).iter().cloned().collect::<Vec<_>>(),
            shields: 0i64,
        },
    ))
}

/// Convert an owned-city unit to shields, then remove it from play.
// Python: openciv3/unit_lifecycle.py:116
pub(crate) fn disband_unit(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    shield_rate: &Option<f64>,
) -> rt::Result<RemovalResult> {
    if !(({
        let mut __comprehension_result_498: Vec<bool> = Vec::new();
        let __comprehension_source_497 = ((game).units.clone());
        for other in __comprehension_source_497.iter().cloned() {
            __comprehension_result_498.push(((other).id == (unit).id));
        }
        __comprehension_result_498
    })
    .into_iter()
    .any(|__value| __value))
    {
        return Err("Unit is not in this game".to_string().into());
    }
    let mut reward: i64 = {
        let __call_499_0 = game;
        let __call_499_1 = unit;
        let __call_499_2 = (*shield_rate).clone();
        disband_reward(__call_499_0, __call_499_1, __call_499_2)
    }?;
    let mut city: Option<crate::openciv3::cities::City> = {
        let __find_source_500 = (game).cities.clone();
        let mut __find_result_500: Option<crate::openciv3::cities::City> = None;
        for city in __find_source_500.iter().cloned() {
            if (((city).owner == (unit).owner) && (((city).x, (city).y) == ((unit).x, (unit).y))) {
                __find_result_500 = Some(city.clone());
                break;
            }
        }
        __find_result_500
    };
    let mut result: RemovalResult = remove_unit(game, unit)?;
    if (city).is_some() {
        city.as_mut().ok_or("expected a value")?.shields_stored =
            (((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).shields_stored)
                .checked_add(reward)
                .ok_or("integer overflow")?;
    }
    Ok(RemovalResult {
        removed: (result).removed.clone(),
        defeated: (result).defeated.clone(),
        shields: reward,
    })
}

// Python: openciv3/unit_lifecycle.py:129
pub(crate) fn disband_reward(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut shield_rate: Option<f64>,
) -> rt::Result<i64> {
    if (shield_rate).is_none() {
        let mut rules: Vec<crate::openciv3::global_rules::GlobalRules> =
            (&(&(game).scenario).rules).global_rules.clone();
        shield_rate = (if (((rules).len() as i64) != 0i64) {
            Some(
                ({
                    let __source = &rules;
                    let __key = 0i64;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .shield_rate_for_disbanding,
            )
        } else {
            Some(0.25f64)
        });
    }
    if (!(rt::math_isfinite((*(shield_rate.clone()).as_ref().ok_or("expected a value")?).clone()))
        || ((*(shield_rate.clone()).as_ref().ok_or("expected a value")?).clone() < 0.0f64))
    {
        return Err("Disband shield rate must be finite and nonnegative"
            .to_string()
            .into());
    }
    let mut city: Option<crate::openciv3::cities::City> = {
        let __find_source_501 = (game).cities.clone();
        let mut __find_result_501: Option<crate::openciv3::cities::City> = None;
        for city in __find_source_501.iter().cloned() {
            if (((city).owner == (unit).owner) && (((city).x, (city).y) == ((unit).x, (unit).y))) {
                __find_result_501 = Some(city.clone());
                break;
            }
        }
        __find_result_501
    };
    let mut reward: i64 = 0i64;
    if ((city).is_some()
        && (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
            .producing_inflow
            .clone())
        .is_none())
    {
        let mut great_wonder: bool = ((((*(city.clone()).as_ref().ok_or("expected a value")?)
            .clone())
        .producing_building
        .clone())
        .is_some()
            && (({
                let __source = &(&(&(game).scenario).rules).buildings;
                let __key = (*(((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                    .producing_building
                    .clone())
                .as_ref()
                .ok_or("expected a value")?)
                .clone();
                &__source[rt::index(__source.len(), __key)?]
            })
            .effects
                & 268435456i64)
                != 0);
        if (!(great_wonder)
            && ((((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                .producing_unit
                .clone())
            .is_some()
                || (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                    .producing_building
                    .clone())
                .is_some()))
        {
            reward = rt::floor(rt::finite(
                ((({
                    let __source = &(&(&(game).scenario).rules).units;
                    let __key = (unit).prototype;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .shield_cost) as f64)
                    * (*(shield_rate).as_ref().ok_or("expected a value")?).clone(),
            )?)?;
        }
    }
    Ok(reward)
}

/// Apply elimination after loss of a city, including when no units remain.
// Python: openciv3/unit_lifecycle.py:146
pub(crate) fn eliminate_if_needed(
    mut game: crate::openciv3::game_state::GameState,
    mut owner: i64,
    mut force: bool,
) -> rt::Result<RemovalResult> {
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, owner)?;
    if (crate::openciv3::players::Player__barbarian(&player)? || (player).defeated) {
        return Ok(RemovalResult {
            removed: vec![],
            defeated: vec![],
            shields: 0i64,
        });
    }
    if (!(force)
        && ((((&(&(game).scenario).options).victory_flags
            & (rt::int_lshift(1i64, 11i64)? | rt::int_lshift(1i64, 12i64)?))
            != 0
            && _has_king(&game, owner)?)
            || (({
                let mut __comprehension_result_503: Vec<bool> = Vec::new();
                let __comprehension_source_502 = ((game).cities.clone());
                for city in __comprehension_source_502.iter().cloned() {
                    __comprehension_result_503.push(
                        (((city).owner == owner)
                            && (crate::openciv3::cities::City__size(&city)? > 0i64)),
                    );
                }
                __comprehension_result_503
            })
            .into_iter()
            .any(|__value| __value)
                || ({
                    let mut __comprehension_result_505: Vec<bool> = Vec::new();
                    let __comprehension_source_504 = ((game).units.clone());
                    for unit in __comprehension_source_504.iter().cloned() {
                        __comprehension_result_505.push(
                            (((unit).owner == owner)
                                && (({
                                    let __source = &(&(&(game).scenario).rules).units;
                                    let __key = (unit).prototype;
                                    &__source[rt::index(__source.len(), __key)?]
                                })
                                .orders
                                    & 4194304i64)
                                    != 0),
                        );
                    }
                    __comprehension_result_505
                })
                .into_iter()
                .any(|__value| __value))))
    {
        return Ok(RemovalResult {
            removed: vec![],
            defeated: vec![],
            shields: 0i64,
        });
    }
    player.defeated = true;
    ((player).contacts).clear();
    for mut other in (&(game).players).iter().cloned() {
        ((other).contacts).remove(&(owner));
    }
    game.diplomacy.relationships = {
        let mut __comprehension_result_507: indexmap::IndexMap<
            (i64, i64),
            crate::openciv3::diplomacy::Relationship,
        > = indexmap::IndexMap::new();
        let __comprehension_source_506 = (((&(game).diplomacy).relationships.clone())
            .iter()
            .map(|(__key, __value)| (__key.clone(), __value.clone()))
            .collect::<Vec<_>>());
        for (pair, relation) in __comprehension_source_506.iter().cloned() {
            if {
                let __needle = owner;
                let __container = &({
                    let __tuple_value = &pair;
                    vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                });
                !__container.contains(&__needle)
            } {
                {
                    let (__key, __value) = (pair.clone(), relation.clone());
                    __comprehension_result_507.insert(__key, __value);
                }
            }
        }
        __comprehension_result_507
    };
    let mut result: RemovalResult = remove_units(
        game.clone(),
        &({
            let mut __comprehension_result_509: Vec<crate::openciv3::units::Unit> = Vec::new();
            let __comprehension_source_508 = ((game).units.clone());
            for unit in __comprehension_source_508.iter().cloned() {
                if ((unit).owner == owner) {
                    __comprehension_result_509.push(unit.clone());
                }
            }
            __comprehension_result_509
        }),
    )?;
    Ok(RemovalResult {
        removed: (result).removed.clone(),
        defeated: {
            let mut __left: Vec<i64> = vec![owner];
            let __right: Vec<i64> = (result).defeated.clone();
            __left.extend(__right);
            __left
        },
        shields: 0i64,
    })
}
