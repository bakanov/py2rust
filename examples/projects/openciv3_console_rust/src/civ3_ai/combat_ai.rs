use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct CombatPlan {
    pub(crate) path: crate::openciv3::pathfinding::UnitPath,
    pub(crate) score: f64,
}

#[derive(Clone, PartialEq)]
pub(crate) struct CombatStep {
    pub(crate) plan: Option<CombatPlan>,
    pub(crate) movement: Option<crate::openciv3::unit_movement::MoveResult>,
}

// Python: civ3_ai/combat_ai.py:35
pub(crate) fn _known_camp(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<bool> {
    let mut knowledge: crate::openciv3::visibility::TileKnowledge = (&(game).visibility)
        .get(&(owner))
        .ok_or("missing dict key")?
        .clone();
    let mut point: (i64, i64) = ((tile).x, (tile).y);
    let mut overlays: i64 = (if {
        let __needle = point.clone();
        let __container = &(knowledge).visible;
        __container.contains(&__needle)
    } {
        (tile).overlays
    } else {
        {
            let __mapping = &(knowledge).known_overlays;
            let __key = point.clone();
            let __default = 0i64;
            __mapping.get(&__key).cloned().unwrap_or(__default)
        }
    });
    Ok((overlays & 128i64) != 0)
}

// Python: civ3_ai/combat_ai.py:42
pub(crate) fn plan_camp_attack(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<Option<CombatPlan>> {
    if (({
        let __source = &(&(&(game).scenario).rules).units;
        let __key = (unit).prototype;
        &__source[rt::index(__source.len(), __key)?]
    })
    .attack
        <= 0i64)
    {
        return Ok(None);
    }
    let mut origin: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if (origin).is_none() {
        return Err("Attacker is outside the map".to_string().into());
    }
    let mut nearby: std::collections::BTreeSet<crate::openciv3::world::Tile> = {
        let mut __comprehension_result_707: std::collections::BTreeSet<
            crate::openciv3::world::Tile,
        > = std::collections::BTreeSet::new();
        let __comprehension_source_705 = ((1i64..4i64).collect::<Vec<i64>>());
        for radius in __comprehension_source_705.iter().cloned() {
            let __comprehension_source_706 = (crate::strategy::grid::ring(
                &(game).world,
                &((*(origin.clone()).as_ref().ok_or("expected a value")?).clone()),
                radius,
                true,
            )?);
            for tile in __comprehension_source_706.iter().cloned() {
                __comprehension_result_707.insert(tile.clone());
            }
        }
        __comprehension_result_707
    };
    let mut camps: Vec<crate::openciv3::world::Tile> = {
        let mut __decorated: Vec<((i64, i64, i64), crate::openciv3::world::Tile)> = Vec::new();
        for __item in ({
            let mut __comprehension_result_709: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_708 = (nearby.clone());
            for tile in __comprehension_source_708.iter().cloned() {
                if ((((tile).x, (tile).y)
                    != (
                        ((*(origin.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                        ((*(origin.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                    ))
                    && _known_camp(game, (unit).owner, &tile)?)
                {
                    __comprehension_result_709.push(tile.clone());
                }
            }
            __comprehension_result_709
        })
        .into_iter()
        {
            let tile = __item;
            let __key = {
                (
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
                            let __structural_value =
                                (*(origin.clone()).as_ref().ok_or("expected a value")?).clone();
                            crate::strategy::grid::GridPoint {
                                x: (__structural_value).x.clone(),
                                y: (__structural_value).y.clone(),
                            }
                        }),
                        &({
                            let __structural_value = tile.clone();
                            crate::strategy::grid::GridPoint {
                                x: (__structural_value).x.clone(),
                                y: (__structural_value).y.clone(),
                            }
                        }),
                    )?,
                    (tile).y,
                    (tile).x,
                )
            };
            __decorated.push((__key, tile));
        }
        __decorated.sort_by(|left, right| {
            if false {
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
    };
    for mut camp in camps {
        if crate::openciv3::unit_entry::EntryIntent__forceable(
            crate::openciv3::unit_entry::resolve_entry(game, unit, &(Some(camp.clone())), true)?,
        )? {
            let mut route: crate::openciv3::pathfinding::UnitPath =
                crate::openciv3::pathfinding::find_path(
                    game,
                    unit,
                    &camp,
                    &({
                        let mut __result = std::collections::BTreeSet::new();
                        for __item in vec![].into_iter() {
                            __result.insert(__item);
                        }
                        __result
                    }),
                )?;
            if ((route).reachable && !((route).steps.clone()).is_empty()) {
                return Ok(Some(CombatPlan {
                    path: route,
                    score: ((0i64) as f64),
                }));
            }
        }
    }
    Ok(None)
}

// Python: civ3_ai/combat_ai.py:59
pub(crate) fn _enemies(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<(bool, bool)> {
    let mut point: (i64, i64) = ((tile).x, (tile).y);
    let mut city: bool = ({
        let mut __comprehension_result_711: Vec<bool> = Vec::new();
        let __comprehension_source_710 = ((game).cities.clone());
        for city in __comprehension_source_710.iter().cloned() {
            __comprehension_result_711.push(
                ((((city).x, (city).y) == point.clone())
                    && crate::openciv3::diplomacy::Diplomacy__at_war(
                        &(game).diplomacy,
                        (unit).owner,
                        (city).owner,
                    )?),
            );
        }
        __comprehension_result_711
    })
    .into_iter()
    .any(|__value| __value);
    let mut units: bool = ({
        let mut __comprehension_result_713: Vec<bool> = Vec::new();
        let __comprehension_source_712 = ((game).units.clone());
        for other in __comprehension_source_712.iter().cloned() {
            __comprehension_result_713.push(
                ((((other).x, (other).y) == point.clone())
                    && crate::openciv3::diplomacy::Diplomacy__at_war(
                        &(game).diplomacy,
                        (unit).owner,
                        (other).owner,
                    )?),
            );
        }
        __comprehension_result_713
    })
    .into_iter()
    .any(|__value| __value);
    Ok((city, units))
}

// Python: civ3_ai/combat_ai.py:69
pub(crate) fn score_target(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<Option<f64>> {
    let (mut enemy_city, mut enemy_units): (bool, bool) = _enemies(game, unit, tile)?;
    if (!(enemy_city) && !(enemy_units)) {
        return Ok(None);
    }
    if (!(crate::openciv3::hydrology::is_water(tile)?)
        != (({
            let __source = &(&(&(game).scenario).rules).units;
            let __key = (unit).prototype;
            &__source[rt::index(__source.len(), __key)?]
        })
        .domain
            == 0i64))
    {
        return Ok(None);
    }
    let mut origin: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if (origin).is_none() {
        return Err("Attacker is outside the map".to_string().into());
    }
    let mut score: f64 = 0.0f64;
    if (enemy_units && !(enemy_city)) {
        let mut defender: Option<crate::openciv3::units::Unit> =
            crate::openciv3::combat_strength::top_defender(game, unit, tile, &None)?;
        if (defender).is_none() {
            return Ok(None);
        }
        let mut attack: i64 = ({
            let __source = &(&(&(game).scenario).rules).units;
            let __key = ((*(defender).as_ref().ok_or("expected a value")?).clone()).prototype;
            &__source[rt::index(__source.len(), __key)?]
        })
        .attack;
        let mut claim: Option<i64> = ((game).ownership.clone())
            .get(&(((tile).x, (tile).y)))
            .cloned();
        if ({
            let mut __comprehension_result_715: Vec<bool> = Vec::new();
            let __comprehension_source_714 = ((game).cities.clone());
            for city in __comprehension_source_714.iter().cloned() {
                __comprehension_result_715
                    .push(((Some((city).id) == claim.clone()) && ((city).owner == (unit).owner)));
            }
            __comprehension_result_715
        })
        .into_iter()
        .any(|__value| __value)
        {
            score = rt::finite(
                score + (((3i64).checked_mul(attack).ok_or("integer overflow")?) as f64),
            )?;
        }
        for mut neighbor in crate::openciv3::world::WorldMap__neighbors(&(game).world, tile)? {
            if ({
                let mut __comprehension_result_717: Vec<bool> = Vec::new();
                let __comprehension_source_716 = ((game).cities.clone());
                for city in __comprehension_source_716.iter().cloned() {
                    __comprehension_result_717.push(
                        ((((city).x, (city).y) == ((neighbor).x, (neighbor).y))
                            && ((city).owner == (unit).owner)),
                    );
                }
                __comprehension_result_717
            })
            .into_iter()
            .any(|__value| __value)
            {
                score = rt::finite(
                    score + (((3i64).checked_mul(attack).ok_or("integer overflow")?) as f64),
                )?;
            }
            if (Some(neighbor) == origin.clone()) {
                score = rt::finite(score + ((attack) as f64))?;
            }
        }
    }
    if enemy_city {
        score = rt::finite(score + ((if enemy_units { 10i64 } else { 20i64 }) as f64))?;
    }
    Ok(Some(rt::finite(
        score
            - (({
                let __exponent = 2i64;
                if __exponent < 0 {
                    return Err("negative integer exponent".into());
                }
                (crate::strategy::grid::distance(
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
                            (*(origin).as_ref().ok_or("expected a value")?).clone();
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
                .checked_pow(__exponent as u32)
                .ok_or("integer power overflow")?
            }) as f64),
    )?))
}

// Python: civ3_ai/combat_ai.py:97
pub(crate) fn plan_combat(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<Option<CombatPlan>> {
    let mut origin: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if (origin).is_none() {
        return Err("Attacker is outside the map".to_string().into());
    }
    let mut known: std::collections::BTreeSet<(i64, i64)> = ((&(game).visibility)
        .get(&((unit).owner))
        .ok_or("missing dict key")?)
    .known
    .clone();
    let mut hostile_owners: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_719: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_718 = ((game).players.clone());
        for player in __comprehension_source_718.iter().cloned() {
            if crate::openciv3::diplomacy::Diplomacy__at_war(
                &(game).diplomacy,
                (unit).owner,
                (player).civilization,
            )? {
                __comprehension_result_719.insert((player).civilization);
            }
        }
        __comprehension_result_719
    };
    let mut occupied: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_721: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_720 = ((game).cities.clone());
        for city in __comprehension_source_720.iter().cloned() {
            if {
                let __needle = (city).owner;
                let __container = &hostile_owners;
                __container.contains(&__needle)
            } {
                __comprehension_result_721.insert(((city).x, (city).y));
            }
        }
        __comprehension_result_721
    };
    (occupied).extend({
        let mut __comprehension_result_723: Vec<(i64, i64)> = Vec::new();
        let __comprehension_source_722 = ((game).units.clone());
        for other in __comprehension_source_722.iter().cloned() {
            if {
                let __needle = (other).owner;
                let __container = &hostile_owners;
                __container.contains(&__needle)
            } {
                __comprehension_result_723.push(((other).x, (other).y));
            }
        }
        __comprehension_result_723
    });
    let mut candidates: Vec<(f64, crate::openciv3::world::Tile)> = vec![];
    for mut for_target_109_4 in {
        let mut __decorated: Vec<((i64, i64), (i64, i64))> = Vec::new();
        for __item in ({
            let __set_left = occupied;
            let __set_right = known;
            let mut __result = std::collections::BTreeSet::new();
            for __item in __set_left.intersection(&__set_right) {
                __result.insert(__item.clone());
            }
            __result
        })
        .into_iter()
        {
            let point = __item;
            let __key = { ((point).1.clone(), (point).0.clone()) };
            __decorated.push((__key, point));
        }
        __decorated.sort_by(|left, right| {
            if false {
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
        let (mut x, mut y): (i64, i64) = for_target_109_4;
        let mut tile: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(&(game).world, x, y)?;
        if (tile).is_none() {
            continue;
        }
        if (((unit).owner == 0i64)
            && (crate::strategy::grid::distance(
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
                        (*(tile.clone()).as_ref().ok_or("expected a value")?).clone();
                    crate::strategy::grid::GridPoint {
                        x: (__structural_value).x.clone(),
                        y: (__structural_value).y.clone(),
                    }
                }),
            )? > 4i64))
        {
            continue;
        }
        let mut score: Option<f64> = score_target(
            game,
            unit,
            &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?;
        if (score).is_some() {
            {
                candidates.push((
                    (*(score.clone()).as_ref().ok_or("expected a value")?).clone(),
                    (*(tile.clone()).as_ref().ok_or("expected a value")?).clone(),
                ));
            };
        }
    }
    for mut for_target_119_4 in {
        let mut __decorated: Vec<(f64, (f64, crate::openciv3::world::Tile))> = Vec::new();
        for __item in (candidates).into_iter() {
            let candidate = __item;
            let __key = { (candidate).0.clone() };
            __decorated.push((__key, candidate));
        }
        __decorated.sort_by(|left, right| {
            if true {
                right.0.total_cmp(&left.0)
            } else {
                left.0.total_cmp(&right.0)
            }
        });
        let mut __result = Vec::new();
        for (_, __item) in __decorated {
            __result.push(__item);
        }
        __result
    } {
        let (mut score, mut tile): (f64, crate::openciv3::world::Tile) = for_target_119_4;
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
            return Ok(Some(CombatPlan {
                path: path,
                score: score,
            }));
        }
    }
    Ok(None)
}

/// Execute one step; retain exhausted plans, retire stale or blocked plans.
///
/// The controller can call again while movement remains. Combat cancels the old
/// route, allowing a fresh plan to account for casualties and changed targets.
// Python: civ3_ai/combat_ai.py:126
pub(crate) fn advance_combat_plan(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut plan: CombatPlan,
    mut rng: rt::Random,
) -> rt::Result<CombatStep> {
    if !(({
        let mut __comprehension_result_725: Vec<bool> = Vec::new();
        let __comprehension_source_724 = ((game).units.clone());
        for other in __comprehension_source_724.iter().cloned() {
            __comprehension_result_725.push(((other).id == (unit).id));
        }
        __comprehension_result_725
    })
    .into_iter()
    .any(|__value| __value))
    {
        return Ok(CombatStep {
            plan: None,
            movement: None,
        });
    }
    let mut target: Option<crate::openciv3::world::Tile> = {
        let __star_args_726: Vec<i64> = {
            let __tuple_value = &((&(plan).path).destination.clone());
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        };
        if !(2..=2).contains(&__star_args_726.len()) {
            return Err("wrong function argument count".into());
        }
        crate::openciv3::world::WorldMap__tile_at(
            &(game).world,
            rt::at(&__star_args_726, 0 as i64)?,
            rt::at(&__star_args_726, 1 as i64)?,
        )?
    };
    let mut origin: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if ((target).is_none()
        || ((origin).is_none()
            || ((origin.clone() == target.clone())
                || !(((&(&(plan).path).steps).len() as i64) != 0i64))))
    {
        return Ok(CombatStep {
            plan: None,
            movement: None,
        });
    }
    if (!(({
        let __tuple_value = &(_enemies(
            game,
            unit,
            &((*(target.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?);
        vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
    })
    .into_iter()
    .any(|__value| __value))
        && !(_known_camp(
            game,
            (unit).owner,
            &((*(target.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?))
    {
        return Ok(CombatStep {
            plan: None,
            movement: None,
        });
    }
    if ((((&(&(plan).path).steps).len() as i64) > 1i64)
        && ({
            let mut __comprehension_result_728: Vec<bool> = Vec::new();
            let __comprehension_source_727 = (crate::openciv3::world::WorldMap__neighbors(
                &(game).world,
                &((*(origin.clone()).as_ref().ok_or("expected a value")?).clone()),
            )?);
            for neighbor in __comprehension_source_727.iter().cloned() {
                __comprehension_result_728.push(
                    (({
                        let __tuple_value = &(_enemies(game, unit, &neighbor)?);
                        vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                    })
                    .into_iter()
                    .any(|__value| __value)
                        || _known_camp(game, (unit).owner, &neighbor)?),
                );
            }
            __comprehension_result_728
        })
        .into_iter()
        .any(|__value| __value))
    {
        let mut replacement: Option<CombatPlan> = plan_combat(game, unit)?;
        if ((replacement).is_some()
            && ((((*(replacement.clone()).as_ref().ok_or("expected a value")?).clone())
                .path
                .clone())
            .destination
            .clone()
                != (&(plan).path).destination.clone()))
        {
            plan = (*(replacement).as_ref().ok_or("expected a value")?).clone();
        }
    }
    let mut result: crate::openciv3::unit_movement::MoveResult = {
        let __call_729_0 = &((*game).clone());
        let __call_729_1 = &((*unit).clone());
        let __call_729_2 = &({
            let __star_args_730: Vec<i64> = {
                let __tuple_value = &(rt::at(&(&(plan).path).steps, 0i64)?);
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_730.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &(game).world,
                rt::at(&__star_args_730, 0 as i64)?,
                rt::at(&__star_args_730, 1 as i64)?,
            )?
        });
        let __call_729_3 = &(Some(rng.clone()));
        let __call_729_default_3 = &({
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        });
        let __call_729_default_4 = None;
        crate::openciv3::unit_movement::move_unit(
            __call_729_0,
            __call_729_1,
            __call_729_2,
            __call_729_default_3,
            __call_729_default_4,
            __call_729_3,
        )
    }?;
    if ((result).status.clone() == crate::openciv3::unit_movement::MoveStatus::EXHAUSTED) {
        return Ok(CombatStep {
            plan: Some(plan),
            movement: Some(result),
        });
    }
    if (((result).status.clone() != crate::openciv3::unit_movement::MoveStatus::MOVED)
        || ((&(result).combat).is_some() || (&(result).raid).is_some()))
    {
        return Ok(CombatStep {
            plan: None,
            movement: Some(result),
        });
    }
    let mut steps: Vec<(i64, i64)> = rt::list_slice(&(&(plan).path).steps, 1i64, i64::MAX);
    Ok(CombatStep {
        plan: (if (((steps).len() as i64) != 0i64) {
            Some({
                let mut __replacement = (plan.clone()).clone();
                __replacement.path = {
                    let mut __replacement = ((plan).path.clone()).clone();
                    __replacement.steps = steps.clone();
                    __replacement
                };
                __replacement
            })
        } else {
            None
        }),
        movement: Some(result),
    })
}
