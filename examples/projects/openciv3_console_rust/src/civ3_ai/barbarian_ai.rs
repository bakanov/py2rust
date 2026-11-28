use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum BarbarianAction {
    SLEEP,
    DEFEND,
    ATTACK,
    EXPLORE,
}

#[derive(Clone, PartialEq)]
pub(crate) struct BarbarianTurn {
    pub(crate) unit: i64,
    pub(crate) action: BarbarianAction,
    pub(crate) moves: Vec<crate::openciv3::unit_movement::MoveResult>,
}

// Python: civ3_ai/barbarian_ai.py:32
pub(crate) fn should_wake(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<bool> {
    let mut tile: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if (tile).is_none() {
        return Err("Barbarian is outside the map".to_string().into());
    }
    let mut visible: std::collections::BTreeSet<(i64, i64)> = {
        let __call_1280_0 = &(game).world;
        let __call_1280_1 = &((*(tile).as_ref().ok_or("expected a value")?).clone());
        let __call_1280_2 = &((&(&(game).scenario).rules).terrains.clone());
        let __call_1280_default_2 = false;
        let __call_1280_default_3 = 2i64;
        crate::openciv3::visibility::unit_sight(
            __call_1280_0,
            __call_1280_1,
            __call_1280_default_2,
            __call_1280_default_3,
            __call_1280_2,
        )
    }?;
    Ok((({
        let mut __comprehension_result_1282: Vec<bool> = Vec::new();
        let __comprehension_source_1281 = (visible.clone());
        for point in __comprehension_source_1281.iter().cloned() {
            __comprehension_result_1282.push({
                let __needle = point.clone();
                let __container = &(game).ownership;
                __container.contains_key(&__needle)
            });
        }
        __comprehension_result_1282
    })
    .into_iter()
    .any(|__value| __value)
        || ({
            let mut __comprehension_result_1284: Vec<bool> = Vec::new();
            let __comprehension_source_1283 = ((game).units.clone());
            for other in __comprehension_source_1283.iter().cloned() {
                __comprehension_result_1284.push(
                    (((other).owner != (unit).owner) && {
                        let __needle = ((other).x, (other).y);
                        let __container = &visible;
                        __container.contains(&__needle)
                    }),
                );
            }
            __comprehension_result_1284
        })
        .into_iter()
        .any(|__value| __value)))
}

// Python: civ3_ai/barbarian_ai.py:41
pub(crate) fn play_barbarian_unit(
    mut game: crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut rng: rt::Random,
) -> rt::Result<BarbarianTurn> {
    if (((unit).owner != 0i64)
        || !(({
            let mut __comprehension_result_1286: Vec<bool> = Vec::new();
            let __comprehension_source_1285 = ((game).units.clone());
            for other in __comprehension_source_1285.iter().cloned() {
                __comprehension_result_1286.push(((other).id == (unit).id));
            }
            __comprehension_result_1286
        })
        .into_iter()
        .any(|__value| __value)))
    {
        return Err("Expected a live barbarian unit".to_string().into());
    }
    let mut activity: i64 = (game).barbarian_activity;
    if {
        let __needle = activity;
        let __container = &({
            let __tuple_value = &((
                (1i64).checked_neg().ok_or("integer overflow")?,
                0i64,
                1i64,
                2i64,
                3i64,
            ));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
                __tuple_value.3.clone(),
                __tuple_value.4.clone(),
            ]
        });
        !__container.contains(&__needle)
    } {
        return Err("Invalid barbarian activity".to_string().into());
    }
    if (activity == (1i64).checked_neg().ok_or("integer overflow")?) {
        return Ok(BarbarianTurn {
            unit: (unit).id,
            action: BarbarianAction::SLEEP,
            moves: vec![],
        });
    }
    if should_wake(&game, unit)? {
        crate::openciv3::unit_turns::wake_unit((*unit).clone())?;
    }
    if (unit).fortified {
        return Ok(BarbarianTurn {
            unit: (unit).id,
            action: BarbarianAction::SLEEP,
            moves: vec![],
        });
    }
    let mut tile: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if !((tile).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    let mut alone_in_camp: bool =
        ((((*(tile).as_ref().ok_or("expected a value")?).clone()).overlays & 128i64) != 0
            && (({
                let mut __comprehension_result_1288: Vec<bool> = Vec::new();
                let __comprehension_source_1287 = ((game).units.clone());
                for other in __comprehension_source_1287.iter().cloned() {
                    __comprehension_result_1288
                        .push((((other).x, (other).y) == ((unit).x, (unit).y)));
                }
                __comprehension_result_1288
            })
            .into_iter()
            .map(|value| value as i64)
            .sum::<i64>()
                == 1i64));
    (((&(game).visibility)
        .get(&((unit).owner))
        .ok_or("missing dict key")?)
    .exploration_targets
    .clone())
    .remove(&((unit).id));
    if !(alone_in_camp) {
        let mut combat: Option<crate::civ3_ai::combat_ai::CombatPlan> =
            crate::civ3_ai::combat_ai::plan_combat(&game, unit)?;
        let mut engage: bool = ((combat).is_some()
            && ((activity != 0i64)
                && ((activity == 3i64)
                    || (rt::random_randrange(&rng, 0i64, 100i64)?
                        < (if (activity == 2i64) { 75i64 } else { 50i64 })))));
        if engage {
            let mut moves: Vec<crate::openciv3::unit_movement::MoveResult> = vec![];
            while ((combat).is_some() && ((unit).movement_remaining > 0.0001f64)) {
                let mut step: crate::civ3_ai::combat_ai::CombatStep = {
                    let __call_1289_0 = &game;
                    let __call_1289_1 = unit;
                    let __call_1289_2 = (*(combat).as_ref().ok_or("expected a value")?).clone();
                    let __call_1289_3 = rng.clone();
                    crate::civ3_ai::combat_ai::advance_combat_plan(
                        __call_1289_0,
                        __call_1289_1,
                        __call_1289_2,
                        __call_1289_3,
                    )
                }?;
                combat = (step).plan.clone();
                if (&(step).movement).is_some() {
                    {
                        moves.push(
                            (*((step).movement.clone())
                                .as_ref()
                                .ok_or("expected a value")?)
                            .clone(),
                        );
                    };
                    if (((*((step).movement.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone())
                    .status
                    .clone()
                        == crate::openciv3::unit_movement::MoveStatus::EXHAUSTED)
                    {
                        break;
                    }
                }
            }
            return Ok(BarbarianTurn {
                unit: (unit).id,
                action: BarbarianAction::ATTACK,
                moves: (moves).iter().cloned().collect::<Vec<_>>(),
            });
        }
        let mut explore: bool = ((activity != 0i64)
            && (rt::random_randrange(&rng, 0i64, 100i64)?
                < (if (activity == 3i64) { 50i64 } else { 75i64 })));
        if explore {
            let mut exploration: Option<crate::civ3_ai::explorer_ai::ExplorationPlan> =
                crate::civ3_ai::explorer_ai::plan_exploration(&game, unit, true)?;
            if (exploration).is_some() {
                let mut moves: Vec<crate::openciv3::unit_movement::MoveResult> = vec![];
                while ((exploration).is_some() && ((unit).movement_remaining > 0.0001f64)) {
                    let mut result: crate::civ3_ai::explorer_ai::ExplorationStep = {
                        let __call_1290_0 = &game;
                        let __call_1290_1 = unit;
                        let __call_1290_2 =
                            &((*(exploration).as_ref().ok_or("expected a value")?).clone());
                        let __call_1290_3 = &(Some(rng.clone()));
                        crate::civ3_ai::explorer_ai::advance_exploration_plan(
                            __call_1290_0,
                            __call_1290_1,
                            __call_1290_2,
                            __call_1290_3,
                        )
                    }?;
                    exploration = (result).plan.clone();
                    if (&(result).movement).is_some() {
                        {
                            moves.push(
                                (*((result).movement.clone())
                                    .as_ref()
                                    .ok_or("expected a value")?)
                                .clone(),
                            );
                        };
                        if (((*((result).movement.clone())
                            .as_ref()
                            .ok_or("expected a value")?)
                        .clone())
                        .status
                        .clone()
                            == crate::openciv3::unit_movement::MoveStatus::EXHAUSTED)
                        {
                            break;
                        }
                    }
                }
                return Ok(BarbarianTurn {
                    unit: (unit).id,
                    action: BarbarianAction::EXPLORE,
                    moves: (moves).iter().cloned().collect::<Vec<_>>(),
                });
            }
        }
    }
    crate::openciv3::unit_turns::fortify_unit((*unit).clone())?;
    Ok(BarbarianTurn {
        unit: (unit).id,
        action: BarbarianAction::DEFEND,
        moves: vec![],
    })
}

// Python: civ3_ai/barbarian_ai.py:88
pub(crate) fn play_barbarian_turn(
    mut game: crate::openciv3::game_state::GameState,
    mut rng: rt::Random,
) -> rt::Result<Vec<BarbarianTurn>> {
    let (mut game, mut reports): (crate::openciv3::game_state::GameState, Vec<BarbarianTurn>) = {
        let __call_1291_0 = game;
        let __call_1291_1 = rng.clone();
        play_barbarian_turn_state(__call_1291_0, __call_1291_1)
    }?;
    Ok(reports)
}

/// Play the barbarian movement phase once; the initial skipped phase stays skipped.
// Python: civ3_ai/barbarian_ai.py:93
pub(crate) fn play_barbarian_turn_state(
    mut game: crate::openciv3::game_state::GameState,
    mut rng: rt::Random,
) -> rt::Result<(crate::openciv3::game_state::GameState, Vec<BarbarianTurn>)> {
    if ({
        let __source = &(game).players;
        let __key = 0i64;
        &__source[rt::index(__source.len(), __key)?]
    })
    .has_played_current_turn
    {
        return Err("Barbarian movement phase already ended".to_string().into());
    }
    let mut reports: Vec<BarbarianTurn> = ({
        let mut __comprehension_result_1296: Vec<BarbarianTurn> = Vec::new();
        let __comprehension_source_1292 = ((&(game).units).iter().cloned().collect::<Vec<_>>());
        for unit in __comprehension_source_1292.iter().cloned() {
            if (((unit).owner == 0i64)
                && ({
                    let mut __comprehension_result_1294: Vec<bool> = Vec::new();
                    let __comprehension_source_1293 = ((game).units.clone());
                    for other in __comprehension_source_1293.iter().cloned() {
                        __comprehension_result_1294.push(((other).id == (unit).id));
                    }
                    __comprehension_result_1294
                })
                .into_iter()
                .any(|__value| __value))
            {
                __comprehension_result_1296.push({
                    let __call_1295_0 = game.clone();
                    let __call_1295_1 = &unit;
                    let __call_1295_2 = rng.clone();
                    play_barbarian_unit(__call_1295_0, __call_1295_1, __call_1295_2)
                }?);
            }
        }
        __comprehension_result_1296
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let (mut game, mut movement_end): (
        crate::openciv3::game_state::GameState,
        crate::openciv3::turn_phases::MovementEnd,
    ) = {
        let __call_1297_0 = game.clone();
        let __call_1297_1 = 0i64;
        let __call_1297_2 = rng.clone();
        crate::openciv3::turn_phases::end_player_movement_state(
            __call_1297_0,
            __call_1297_1,
            __call_1297_2,
        )
    }?;
    Ok((game, reports))
}
