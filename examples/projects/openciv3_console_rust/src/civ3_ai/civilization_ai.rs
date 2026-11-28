use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum MissionTask {
    SETTLER,
    ESCORT,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct AITradePause {
    pub(crate) offer: crate::openciv3::trading::TradeDeal,
}

#[derive(Clone, PartialEq)]
pub(crate) struct AIUnitTurn {
    pub(crate) unit: i64,
    pub(crate) moves: Vec<crate::openciv3::unit_movement::MoveResult>,
    pub(crate) bombing: Option<crate::openciv3::bombardment::BombardResult>,
    pub(crate) rebase: Option<crate::openciv3::air_missions::AirBase>,
}

#[derive(Clone, PartialEq)]
pub(crate) struct _TradeSession {
    pub(crate) game: crate::openciv3::game_state::GameState,
    pub(crate) owner: i64,
    pub(crate) turn: i64,
    pub(crate) rng: rt::Random,
    pub(crate) next_recipient: i64,
    pub(crate) pending: Option<AITradePause>,
    pub(crate) automated_human: bool,
}

pub(crate) struct CivilizationAI {
    pub(crate) plans: indexmap::IndexMap<i64, Box<dyn std::any::Any>>,
    pub(crate) strategy_updates:
        indexmap::IndexMap<i64, crate::civ3_ai::strategic_ai::StrategyUpdate>,
    pub(crate) _trade_session: Option<_TradeSession>,
    pub(crate) last_game: Option<crate::openciv3::game_state::GameState>,
}

impl Clone for CivilizationAI {
    fn clone(&self) -> Self {
        Self {
            plans: (self.plans)
                .iter()
                .map(|(__key, __value)| {
                    (
                        __key.clone(),
                        if let Some(__value) =
                            (&(__value)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) = (&(__value))
                                .downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>(
                            ) {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (&(__value))
                                    .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>(
                                ) {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    if let Some(__value) = (&(__value))
                                        .downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>(
                                    ) {
                                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                                    } else {
                                        if let Some(__value) =
                                            (&(__value)).downcast_ref::<MissionTask>()
                                        {
                                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                                        } else {
                                            panic!("unsupported union value")
                                        }
                                    }
                                }
                            }
                        },
                    )
                })
                .collect::<indexmap::IndexMap<_, _>>(),
            strategy_updates: (self.strategy_updates).clone(),
            _trade_session: (self._trade_session).clone(),
            last_game: (self.last_game).clone(),
        }
    }
}

impl PartialEq for CivilizationAI {
    fn eq(&self, other: &Self) -> bool {
        (self.plans).len() == (other.plans).len() && (self.plans).iter().all(|(__key, __left)| {
            (other.plans)
                .get(__key)
                .map(|__right| {
                    if let Some(__left) =
                        (__left).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                    {
                        (__right).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                            == Some(__left)
                    } else {
                        if let Some(__left) =
                            (__left).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                        {
                            (__right).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                                == Some(__left)
                        } else {
                            if let Some(__left) = (__left)
                                .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>(
                            ) {
                                (__right)
                                    .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
                                    == Some(__left)
                            } else {
                                if let Some(__left) =
                                    (__left).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                                {
                                    (__right)
                                        .downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                                        == Some(__left)
                                } else {
                                    if let Some(__left) = (__left).downcast_ref::<MissionTask>() {
                                        (__right).downcast_ref::<MissionTask>() == Some(__left)
                                    } else {
                                        false
                                    }
                                }
                            }
                        }
                    }
                })
                .unwrap_or(false)
        }) && (self.strategy_updates) == (other.strategy_updates)
            && (self._trade_session) == (other._trade_session)
            && (self.last_game) == (other.last_game)
    }
}

// Python: civ3_ai/civilization_ai.py:71
pub(crate) fn _play_aircraft(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut rng: rt::Random,
) -> rt::Result<AIUnitTurn> {
    let mut prototype: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    let mut origin: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if !((origin).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    if (((prototype).orders & 274877906944i64) != 0
        && crate::openciv3::bombardment::can_bombard(game, unit)?)
    {
        let mut opponents: std::collections::BTreeSet<i64> = {
            let mut __comprehension_result_7: std::collections::BTreeSet<i64> =
                std::collections::BTreeSet::new();
            let __comprehension_source_6 = ((game).players.clone());
            for player in __comprehension_source_6.iter().cloned() {
                if crate::openciv3::diplomacy::Diplomacy__at_war(
                    &(game).diplomacy,
                    (unit).owner,
                    (player).civilization,
                )? {
                    __comprehension_result_7.insert((player).civilization);
                }
            }
            __comprehension_result_7
        };
        let mut points: std::collections::BTreeSet<(i64, i64)> = {
            let mut __comprehension_result_9: std::collections::BTreeSet<(i64, i64)> =
                std::collections::BTreeSet::new();
            let __comprehension_source_8 = ((game).cities.clone());
            for city in __comprehension_source_8.iter().cloned() {
                if {
                    let __needle = (city).owner;
                    let __container = &opponents;
                    __container.contains(&__needle)
                } {
                    __comprehension_result_9.insert(((city).x, (city).y));
                }
            }
            __comprehension_result_9
        };
        (points).extend({
            let mut __comprehension_result_11: Vec<(i64, i64)> = Vec::new();
            let __comprehension_source_10 = ((game).units.clone());
            for enemy in __comprehension_source_10.iter().cloned() {
                if ({
                    let __needle = (enemy).owner;
                    let __container = &opponents;
                    __container.contains(&__needle)
                } && (&(enemy).transported_by).is_none())
                {
                    __comprehension_result_11.push(((enemy).x, (enemy).y));
                }
            }
            __comprehension_result_11
        });
        let mut visible: std::collections::BTreeSet<(i64, i64)> = ((&(game).visibility)
            .get(&((unit).owner))
            .ok_or("missing dict key")?)
        .visible
        .clone();
        let mut targets: Vec<crate::openciv3::world::Tile> = {
            let mut __comprehension_result_14: Vec<crate::openciv3::world::Tile> = Vec::new();
            let mut tile: Option<crate::openciv3::world::Tile>;
            let __comprehension_source_12 = ({
                let __set_left = points.clone();
                let __set_right = visible.clone();
                let mut __result = std::collections::BTreeSet::new();
                for __item in __set_left.intersection(&__set_right) {
                    __result.insert(__item.clone());
                }
                __result
            });
            for point in __comprehension_source_12.iter().cloned() {
                if ({
                    tile = {
                        let __star_args_13: Vec<i64> = {
                            let __tuple_value = &(point.clone());
                            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                        };
                        if !(2..=2).contains(&__star_args_13.len()) {
                            return Err("wrong function argument count".into());
                        }
                        crate::openciv3::world::WorldMap__tile_at(
                            &(game).world,
                            rt::at(&__star_args_13, 0 as i64)?,
                            rt::at(&__star_args_13, 1 as i64)?,
                        )?
                    };
                    tile.clone()
                })
                .is_some()
                {
                    __comprehension_result_14
                        .push((*(tile.clone()).as_ref().ok_or("expected a value")?).clone());
                }
            }
            __comprehension_result_14
        };
        let mut candidates: Vec<((bool, i64, i64, i64), crate::openciv3::world::Tile)> = vec![];
        for mut tile in (targets).iter() {
            let mut target: Option<crate::openciv3::bombardment::BombardTarget> = {
                let __call_15_0 = game;
                let __call_15_1 = unit;
                let __call_15_2 = tile;
                let __call_15_3 = true;
                crate::openciv3::bombardment::bombard_target(
                    __call_15_0,
                    __call_15_1,
                    __call_15_2,
                    __call_15_3,
                )
            }?;
            if (target).is_some() {
                let mut priority: (bool, i64, i64, i64) = (
                    (((*(target).as_ref().ok_or("expected a value")?).clone())
                        .kind
                        .clone()
                        != crate::openciv3::bombardment::BombardKind::UNIT),
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
                            let __structural_value = (*tile).clone();
                            crate::strategy::grid::GridPoint {
                                x: (__structural_value).x.clone(),
                                y: (__structural_value).y.clone(),
                            }
                        }),
                    )?,
                    (tile).y,
                    (tile).x,
                );
                {
                    candidates.push((priority, (*tile).clone()));
                };
            }
        }
        if (((candidates).len() as i64) != 0i64) {
            let (_, mut tile): ((bool, i64, i64, i64), crate::openciv3::world::Tile) = {
                let __values = &candidates;
                let mut __items = __values.iter();
                let mut __best = __items.next().ok_or("min() arg is an empty sequence")?;
                let mut __best_key = {
                    let candidate = (*__best).clone();
                    (candidate).0.clone()
                };
                for __candidate in __items {
                    let __key = {
                        let candidate = (*__candidate).clone();
                        (candidate).0.clone()
                    };
                    if __key < __best_key {
                        __best = __candidate;
                        __best_key = __key;
                    }
                }
                (*__best).clone()
            };
            let mut result: crate::openciv3::bombardment::BombardResult = {
                let __call_16_0 = game;
                let __call_16_1 = unit;
                let __call_16_2 = &tile;
                let __call_16_3 = rng.clone();
                let __call_16_4 = true;
                crate::openciv3::bombardment::fire_bombardment(
                    __call_16_0,
                    __call_16_1,
                    __call_16_2,
                    __call_16_3,
                    __call_16_4,
                )
            }?;
            return Ok(AIUnitTurn {
                unit: (unit).id,
                moves: vec![],
                bombing: Some(result),
                rebase: None,
            });
        }
        if (!(targets.clone()).is_empty() && crate::openciv3::air_missions::can_rebase(game, unit)?)
        {
            let mut base: Option<crate::openciv3::world::Tile> = _forward_airbase(
                game,
                unit,
                &((*(origin).as_ref().ok_or("expected a value")?).clone()),
                &targets,
            )?;
            if (base).is_some() {
                return Ok(AIUnitTurn {
                    unit: (unit).id,
                    moves: vec![],
                    rebase: Some(crate::openciv3::air_missions::rebase_aircraft(
                        (*game).clone(),
                        (*unit).clone(),
                        &((*(base).as_ref().ok_or("expected a value")?).clone()),
                    )?),
                    bombing: None,
                });
            }
        }
    }
    crate::openciv3::unit_turns::skip_unit_turn(game, (*unit).clone())?;
    Ok(AIUnitTurn {
        unit: (unit).id,
        moves: vec![],
        bombing: None,
        rebase: None,
    })
}

// Python: civ3_ai/civilization_ai.py:101
pub(crate) fn _forward_airbase(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    origin: &crate::openciv3::world::Tile,
    targets: &[crate::openciv3::world::Tile],
) -> rt::Result<Option<crate::openciv3::world::Tile>> {
    let mut radius: i64 = crate::openciv3::unit_rules::UnitPrototype__bombardment_range({
        let __source = &(&(&(game).scenario).rules).units;
        let __key = (unit).prototype;
        &__source[rt::index(__source.len(), __key)?]
    })?;

    let mut current: (i64, i64) = _forward_airbase__airbase_score(targets, game, radius, origin)?;
    let mut bases: Vec<crate::openciv3::world::Tile> = {
        let mut __comprehension_result_18: Vec<crate::openciv3::world::Tile> = Vec::new();
        let mut tile: Option<crate::openciv3::world::Tile>;
        let __comprehension_source_17 = ((game).cities.clone());
        for city in __comprehension_source_17.iter().cloned() {
            if (((city).owner == (unit).owner)
                && (({
                    tile = crate::openciv3::world::WorldMap__tile_at(
                        &(game).world,
                        (city).x,
                        (city).y,
                    )?;
                    tile.clone()
                })
                .is_some()
                    && (crate::openciv3::air_missions::rebase_destination(
                        game,
                        unit,
                        &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
                    )?)
                    .is_some()))
            {
                __comprehension_result_18
                    .push((*(tile.clone()).as_ref().ok_or("expected a value")?).clone());
            }
        }
        __comprehension_result_18
    };
    let mut best: Option<crate::openciv3::world::Tile> = '__extreme: {
        let __values = &bases;
        let mut __items = __values.iter();
        let Some(mut __best) = __items.next() else {
            break '__extreme None;
        };
        let mut __best_key = {
            let base = (*__best).clone();
            (
                _forward_airbase__airbase_score(targets, game, radius, &base)?,
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
                        let __structural_value = (*origin).clone();
                        crate::strategy::grid::GridPoint {
                            x: (__structural_value).x.clone(),
                            y: (__structural_value).y.clone(),
                        }
                    }),
                    &({
                        let __structural_value = base.clone();
                        crate::strategy::grid::GridPoint {
                            x: (__structural_value).x.clone(),
                            y: (__structural_value).y.clone(),
                        }
                    }),
                )?)
                .checked_neg()
                .ok_or("integer overflow")?,
                ((base).y).checked_neg().ok_or("integer overflow")?,
                ((base).x).checked_neg().ok_or("integer overflow")?,
            )
        };
        for __candidate in __items {
            let __key = {
                let base = (*__candidate).clone();
                (
                    _forward_airbase__airbase_score(targets, game, radius, &base)?,
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
                            let __structural_value = (*origin).clone();
                            crate::strategy::grid::GridPoint {
                                x: (__structural_value).x.clone(),
                                y: (__structural_value).y.clone(),
                            }
                        }),
                        &({
                            let __structural_value = base.clone();
                            crate::strategy::grid::GridPoint {
                                x: (__structural_value).x.clone(),
                                y: (__structural_value).y.clone(),
                            }
                        }),
                    )?)
                    .checked_neg()
                    .ok_or("integer overflow")?,
                    ((base).y).checked_neg().ok_or("integer overflow")?,
                    ((base).x).checked_neg().ok_or("integer overflow")?,
                )
            };
            if __key > __best_key {
                __best = __candidate;
                __best_key = __key;
            }
        }
        Some((*__best).clone())
    };
    Ok((if ((best).is_some()
        && (_forward_airbase__airbase_score(
            targets,
            game,
            radius,
            &((*(best.clone()).as_ref().ok_or("expected a value")?).clone()),
        )? > current))
    {
        best.clone()
    } else {
        None
    }))
}

// Python: civ3_ai/civilization_ai.py:125
pub(crate) fn CivilizationAI__pending_trade(
    self_: &CivilizationAI,
) -> rt::Result<Option<AITradePause>> {
    Ok((if (&(self_)._trade_session).is_some() {
        ((*((self_)._trade_session.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone())
        .pending
        .clone()
    } else {
        None
    }))
}

/// Run a turn, returning a human offer when diplomacy needs a response.
// Python: civ3_ai/civilization_ai.py:128
pub(crate) fn CivilizationAI__play_turn(
    mut self_: &mut CivilizationAI,
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    mut rng: rt::Random,
    mut automated_human: bool,
) -> rt::Result<Box<dyn std::any::Any>> {
    if (&(self_)._trade_session).is_some() {
        return Err(
            "Respond to the pending trade before starting another AI turn"
                .to_string()
                .into(),
        );
    }
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, owner)?;
    if (((player).human && !(automated_human))
        || (crate::openciv3::players::Player__barbarian(&player)?
            || (!((player).included) || ((player).defeated || (player).has_played_current_turn))))
    {
        return Err(
            "AI turn requires an active civilization with an unfinished phase"
                .to_string()
                .into(),
        );
    }
    let mut update: Option<crate::civ3_ai::strategic_ai::StrategyUpdate> = {
        let __call_19_0 = game;
        let __call_19_1 = player.clone();
        let __call_19_2 = rng.clone();
        let __call_19_3 = automated_human;
        crate::civ3_ai::strategic_ai::reevaluate_priorities(
            __call_19_0,
            __call_19_1,
            __call_19_2,
            __call_19_3,
        )
    }?;
    if (update).is_some() {
        self_.strategy_updates.insert(
            owner,
            (*(update).as_ref().ok_or("expected a value")?).clone(),
        );
    }
    {
        let __call_20_0 = game;
        let __call_20_1 = player;
        let __call_20_2 = automated_human;
        crate::openciv3::research::pick_ai_research(__call_20_0, __call_20_1, __call_20_2)
    }?;
    if (rt::random_randrange(&rng, 0i64, 100i64)? < 25i64) {
        self_._trade_session = Some(_TradeSession {
            game: (*game).clone(),
            owner: owner,
            turn: (game).turn,
            rng: rng.clone(),
            automated_human: automated_human,
            next_recipient: 0i64,
            pending: None,
        });
        return CivilizationAI___continue_trading(&mut self_);
    }
    Ok(Box::new({
        let __call_21_0 = &mut self_;
        let __call_21_1 = game;
        let __call_21_2 = owner;
        let __call_21_3 = rng.clone();
        let __call_21_4 = automated_human;
        CivilizationAI___finish_turn(
            __call_21_0,
            __call_21_1,
            __call_21_2,
            __call_21_3,
            __call_21_4,
        )
    }?) as Box<dyn std::any::Any>)
}

// Python: civ3_ai/civilization_ai.py:146
pub(crate) fn CivilizationAI___finish_turn(
    mut self_: &mut CivilizationAI,
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    mut rng: rt::Random,
    mut automated_human: bool,
) -> rt::Result<Vec<AIUnitTurn>> {
    let mut reports: Vec<AIUnitTurn> = {
        let __call_22_0 = &mut self_;
        let __call_22_1 = (*game).clone();
        let __call_22_2 = owner;
        let __call_22_3 = rng.clone();
        let __call_22_4 = automated_human;
        CivilizationAI__play_movement(
            __call_22_0,
            __call_22_1,
            __call_22_2,
            __call_22_3,
            __call_22_4,
        )
    }?;
    {
        let __call_23_0 = game;
        let __call_23_1 = rt::at(&(game).players, owner)?;
        let __call_23_2 = automated_human;
        crate::civ3_ai::economic_ai::adjust_sliders(__call_23_0, __call_23_1, __call_23_2)
    }?;
    Ok(reports)
}

// Python: civ3_ai/civilization_ai.py:152
pub(crate) fn CivilizationAI___continue_trading(
    mut self_: &mut CivilizationAI,
) -> rt::Result<Box<dyn std::any::Any>> {
    let mut session: Option<_TradeSession> = (self_)._trade_session.clone();
    if !((session).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    while (((*(session.clone()).as_ref().ok_or("expected a value")?).clone()).next_recipient
        < (((((*(session.clone()).as_ref().ok_or("expected a value")?).clone())
            .game
            .clone())
        .players
        .clone())
        .len() as i64))
    {
        let mut other: i64 =
            ((*(session.clone()).as_ref().ok_or("expected a value")?).clone()).next_recipient;
        session.as_mut().ok_or("expected a value")?.next_recipient =
            (((*(session.clone()).as_ref().ok_or("expected a value")?).clone()).next_recipient)
                .checked_add(1i64)
                .ok_or("integer overflow")?;
        let mut offer: Option<crate::openciv3::trading::TradeDeal> =
            crate::openciv3::trading::propose_technology_trade(
                &(((*(session.clone()).as_ref().ok_or("expected a value")?).clone())
                    .game
                    .clone()),
                ((*(session.clone()).as_ref().ok_or("expected a value")?).clone()).owner,
                other,
            )?;
        if (offer).is_none() {
            offer = crate::openciv3::trading::propose_resource_trade(
                &(((*(session.clone()).as_ref().ok_or("expected a value")?).clone())
                    .game
                    .clone()),
                ((*(session.clone()).as_ref().ok_or("expected a value")?).clone()).owner,
                other,
            )?;
        }
        if (offer).is_none() {
            continue;
        }
        if ((rt::at(
            &((((*(session.clone()).as_ref().ok_or("expected a value")?).clone())
                .game
                .clone())
            .players
            .clone()),
            other,
        )?)
        .human
            && (other != ((*(session.clone()).as_ref().ok_or("expected a value")?).clone()).owner))
        {
            session.as_mut().ok_or("expected a value")?.pending = Some(AITradePause {
                offer: (*(offer).as_ref().ok_or("expected a value")?).clone(),
            });
            return Ok(
                match (((*(session.clone()).as_ref().ok_or("expected a value")?).clone())
                    .pending
                    .clone())
                .as_ref()
                {
                    Some(__value) => Box::new(__value.clone()) as Box<dyn std::any::Any>,
                    None => return Err("expected a union value".into()),
                },
            );
        }
        crate::openciv3::trading::execute_deal(
            &(((*(session.clone()).as_ref().ok_or("expected a value")?).clone())
                .game
                .clone()),
            &((*(offer).as_ref().ok_or("expected a value")?).clone()),
        )?;
    }
    self_._trade_session = None;
    Ok(Box::new({
        let __call_24_0 = &mut self_;
        let __call_24_1 = &(((*(session.clone()).as_ref().ok_or("expected a value")?).clone())
            .game
            .clone());
        let __call_24_2 = ((*(session.clone()).as_ref().ok_or("expected a value")?).clone()).owner;
        let __call_24_3 = ((*(session.clone()).as_ref().ok_or("expected a value")?).clone())
            .rng
            .clone();
        let __call_24_4 =
            ((*(session.clone()).as_ref().ok_or("expected a value")?).clone()).automated_human;
        CivilizationAI___finish_turn(
            __call_24_0,
            __call_24_1,
            __call_24_2,
            __call_24_3,
            __call_24_4,
        )
    }?) as Box<dyn std::any::Any>)
}

// Python: civ3_ai/civilization_ai.py:171
pub(crate) fn CivilizationAI__respond_to_trade(
    mut self_: &mut CivilizationAI,
    game: &crate::openciv3::game_state::GameState,
    mut accept: bool,
) -> rt::Result<Box<dyn std::any::Any>> {
    let mut session: Option<_TradeSession> = (self_)._trade_session.clone();
    if ((session).is_none()
        || (((*(session.clone()).as_ref().ok_or("expected a value")?).clone())
            .pending
            .clone())
        .is_none())
    {
        return Err("No human trade offer is pending".to_string().into());
    }
    if (((((*(session.clone()).as_ref().ok_or("expected a value")?).clone())
        .game
        .clone())
    .seed
        != (game).seed)
        || ((((*(session.clone()).as_ref().ok_or("expected a value")?).clone()).turn
            != (game).turn)
            || ({
                let __source = &(game).players;
                let __key =
                    ((*(session.clone()).as_ref().ok_or("expected a value")?).clone()).owner;
                &__source[rt::index(__source.len(), __key)?]
            })
            .has_played_current_turn))
    {
        return Err("Trade response belongs to a different game or turn"
            .to_string()
            .into());
    }
    if accept {
        crate::openciv3::trading::execute_deal(
            game,
            &(((*(((*(session.clone()).as_ref().ok_or("expected a value")?).clone())
                .pending
                .clone())
            .as_ref()
            .ok_or("expected a value")?)
            .clone())
            .offer
            .clone()),
        )?;
    }
    session.as_mut().ok_or("expected a value")?.pending = None;
    CivilizationAI___continue_trading(&mut self_)
}

// Python: civ3_ai/civilization_ai.py:182
pub(crate) fn CivilizationAI___clear(
    mut self_: &mut CivilizationAI,
    mut game: crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
) -> rt::Result<()> {
    ((self_).plans).remove(&((unit).id));
    unit.defender_destination = None;
    (((&(game).visibility)
        .get(&((unit).owner))
        .ok_or("missing dict key")?)
    .exploration_targets
    .clone())
    .remove(&((unit).id));
    Ok(())
}

// Python: civ3_ai/civilization_ai.py:187
pub(crate) fn CivilizationAI__choose_plan(
    mut self_: &mut CivilizationAI,
    game: &crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
) -> rt::Result<Box<dyn std::any::Any>> {
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    if ({
        let __boolean_123705985628688 = ((&(&(game).scenario).options).victory_flags
            & (rt::int_lshift(1i64, 11i64)? | rt::int_lshift(1i64, 12i64)?));
        if (__boolean_123705985628688) != 0 {
            ((kind).abilities & 536870912i64)
        } else {
            __boolean_123705985628688
        }
    }) != 0
    {
        let mut defense: Option<crate::civ3_ai::defender_ai::DefensePlan> =
            crate::civ3_ai::defender_ai::plan_city_defense(
                game,
                unit.clone(),
                ({
                    let __exponent = 31i64;
                    if __exponent < 0 {
                        return Err("negative integer exponent".into());
                    }
                    (2i64)
                        .checked_pow(__exponent as u32)
                        .ok_or("integer power overflow")?
                })
                .checked_sub(1i64)
                .ok_or("integer overflow")?,
            )?;
        return Ok((if (defense).is_some() {
            match (defense.clone()).as_ref() {
                Some(__value) => Box::new(__value.clone()) as Box<dyn std::any::Any>,
                None => return Err("expected a union value".into()),
            }
        } else {
            Box::new(crate::civ3_ai::defender_ai::defend_in_place(unit)?) as Box<dyn std::any::Any>
        }));
    }
    if (((kind).orders & 4194304i64) != 0i64) {
        if (&(unit).settler_mission).is_none() {
            unit.settler_mission = Some(crate::openciv3::unit_missions::plan_settler(
                game,
                unit.clone(),
            )?);
        }
        return Ok(Box::new(MissionTask::SETTLER) as Box<dyn std::any::Any>);
    }
    if crate::openciv3::worker_rules::is_worker_prototype(&kind)? {
        let mut worker: Option<crate::civ3_ai::worker_ai::WorkerPlan> =
            crate::civ3_ai::worker_ai::plan_worker(game, &unit)?;
        return Ok((if (worker).is_some() {
            match (worker.clone()).as_ref() {
                Some(__value) => Box::new(__value.clone()) as Box<dyn std::any::Any>,
                None => return Err("expected a union value".into()),
            }
        } else {
            Box::new(crate::civ3_ai::defender_ai::defend_in_place(unit)?) as Box<dyn std::any::Any>
        }));
    }
    if (({
        let mut __comprehension_result_26: Vec<bool> = Vec::new();
        let __comprehension_source_25 = ((game).cities.clone());
        for city in __comprehension_source_25.iter().cloned() {
            __comprehension_result_26.push((((city).x, (city).y) == ((unit).x, (unit).y)));
        }
        __comprehension_result_26
    })
    .into_iter()
    .any(|__value| __value)
        && (crate::openciv3::unit_entry::can_defend_on_land(game, &unit)?
            && !(({
                let mut __comprehension_result_28: Vec<bool> = Vec::new();
                let __comprehension_source_27 = ((game).units.clone());
                for other in __comprehension_source_27.iter().cloned() {
                    __comprehension_result_28.push(
                        (((other).id != (unit).id)
                            && (((other).owner == (unit).owner)
                                && ((((other).x, (other).y) == ((unit).x, (unit).y))
                                    && crate::openciv3::unit_entry::can_defend_on_land(
                                        game, &other,
                                    )?))),
                    );
                }
                __comprehension_result_28
            })
            .into_iter()
            .any(|__value| __value))))
    {
        return Ok(
            Box::new(crate::civ3_ai::defender_ai::defend_in_place(unit)?) as Box<dyn std::any::Any>,
        );
    }
    let mut camp_attack: Option<crate::civ3_ai::combat_ai::CombatPlan> =
        crate::civ3_ai::combat_ai::plan_camp_attack(game, &unit)?;
    if (camp_attack).is_some() {
        return Ok(match (camp_attack).as_ref() {
            Some(__value) => Box::new(__value.clone()) as Box<dyn std::any::Any>,
            None => return Err("expected a union value".into()),
        });
    }
    if (AsRef::<str>::as_ref(&(kind).name) == "Catapult") {
        return Ok(
            Box::new(crate::civ3_ai::defender_ai::defend_in_place(unit)?) as Box<dyn std::any::Any>,
        );
    }
    if ((&(unit).escorting).is_some()
        || (crate::civ3_ai::settler_ai::recruit_escort(game, &unit)?).is_some())
    {
        return Ok(Box::new(MissionTask::ESCORT) as Box<dyn std::any::Any>);
    }
    let mut war: bool = ({
        let mut __comprehension_result_30: Vec<bool> = Vec::new();
        let __comprehension_source_29 = ((game).players.clone());
        for player in __comprehension_source_29.iter().cloned() {
            __comprehension_result_30.push(
                ((player).included
                    && (!(crate::openciv3::players::Player__barbarian(&player)?)
                        && (!((player).defeated)
                            && crate::openciv3::diplomacy::Diplomacy__at_war(
                                &(game).diplomacy,
                                (unit).owner,
                                (player).civilization,
                            )?))),
            );
        }
        __comprehension_result_30
    })
    .into_iter()
    .any(|__value| __value);
    if war {
        let mut defense: Option<crate::civ3_ai::defender_ai::DefensePlan> =
            crate::civ3_ai::defender_ai::plan_city_defense(
                game,
                unit.clone(),
                (if ((kind).attack >= (kind).defense) {
                    3i64
                } else {
                    ({
                        let __exponent = 31i64;
                        if __exponent < 0 {
                            return Err("negative integer exponent".into());
                        }
                        (2i64)
                            .checked_pow(__exponent as u32)
                            .ok_or("integer power overflow")?
                    })
                    .checked_sub(1i64)
                    .ok_or("integer overflow")?
                }),
            )?;
        if (defense).is_some() {
            return Ok(match (defense).as_ref() {
                Some(__value) => Box::new(__value.clone()) as Box<dyn std::any::Any>,
                None => return Err("expected a union value".into()),
            });
        }
        let mut combat: Option<crate::civ3_ai::combat_ai::CombatPlan> =
            crate::civ3_ai::combat_ai::plan_combat(game, &unit)?;
        if (combat).is_some() {
            return Ok(match (combat).as_ref() {
                Some(__value) => Box::new(__value.clone()) as Box<dyn std::any::Any>,
                None => return Err("expected a union value".into()),
            });
        }
    } else {
        let mut land: bool = ((kind).domain == 0i64);
        let mut explorers: i64 = ({
            let mut __comprehension_result_32: Vec<bool> = Vec::new();
            let __comprehension_source_31 = ((game).units.clone());
            for other in __comprehension_source_31.iter().cloned() {
                if ((other).owner == (unit).owner) {
                    __comprehension_result_32.push(
                        (false
                            && ((({
                                let __source = &(&(&(game).scenario).rules).units;
                                let __key = (other).prototype;
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .domain
                                == 0i64)
                                == land)),
                    );
                }
            }
            __comprehension_result_32
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        if (explorers < (if land { 10i64 } else { 4i64 })) {
            let mut exploration: Option<crate::civ3_ai::explorer_ai::ExplorationPlan> =
                crate::civ3_ai::explorer_ai::plan_exploration(game, &unit, true)?;
            if (exploration).is_some() {
                return Ok(match (exploration).as_ref() {
                    Some(__value) => Box::new(__value.clone()) as Box<dyn std::any::Any>,
                    None => return Err("expected a union value".into()),
                });
            }
        }
    }
    Ok(Box::new(
        match (crate::civ3_ai::defender_ai::plan_city_defense(
            game,
            unit.clone(),
            ({
                let __exponent = 31i64;
                if __exponent < 0 {
                    return Err("negative integer exponent".into());
                }
                (2i64)
                    .checked_pow(__exponent as u32)
                    .ok_or("integer power overflow")?
            })
            .checked_sub(1i64)
            .ok_or("integer overflow")?,
        )?) {
            Some(__value) => __value,
            None => crate::civ3_ai::defender_ai::defend_in_place(unit.clone())?,
        },
    ) as Box<dyn std::any::Any>)
}

// Python: civ3_ai/civilization_ai.py:229
pub(crate) fn CivilizationAI___step(
    mut self_: &mut CivilizationAI,
    mut game: crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    plan: &Box<dyn std::any::Any>,
    mut rng: rt::Random,
) -> rt::Result<(
    crate::openciv3::game_state::GameState,
    Option<Box<dyn std::any::Any>>,
    Vec<crate::openciv3::unit_movement::MoveResult>,
)> {
    if (&(if let Some(__value) = (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>() {
        Box::new(__value.clone()) as Box<dyn std::any::Any>
    } else {
        if let Some(__value) = (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
        {
            Box::new(__value.clone()) as Box<dyn std::any::Any>
        } else {
            if let Some(__value) =
                (&(plan)).downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(plan)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        panic!("unsupported union value")
                    }
                }
            }
        }
    }))
        .is::<crate::civ3_ai::combat_ai::CombatPlan>()
    {
        let mut combat: crate::civ3_ai::combat_ai::CombatStep = {
            let __call_33_0 = &game;
            let __call_33_1 = unit;
            let __call_33_2 = (*(&(if let Some(__value) =
                (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) =
                        (&(plan)).downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) =
                            (&(plan)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                panic!("unsupported union value")
                            }
                        }
                    }
                }
            }))
                .downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                .ok_or("union type mismatch")?)
            .clone();
            let __call_33_3 = rng.clone();
            crate::civ3_ai::combat_ai::advance_combat_plan(
                __call_33_0,
                __call_33_1,
                __call_33_2,
                __call_33_3,
            )
        }?;
        return Ok((
            game,
            match ((combat).plan.clone()).as_ref() {
                Some(__value) => Some(Box::new(__value.clone()) as Box<dyn std::any::Any>),
                None => None,
            },
            (if (&(combat).movement).is_none() {
                vec![]
            } else {
                vec![(*((combat).movement.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone()]
            }),
        ));
    }
    if (&(if let Some(__value) = (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>() {
        Box::new(__value.clone()) as Box<dyn std::any::Any>
    } else {
        if let Some(__value) = (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
        {
            Box::new(__value.clone()) as Box<dyn std::any::Any>
        } else {
            if let Some(__value) =
                (&(plan)).downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(plan)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        panic!("unsupported union value")
                    }
                }
            }
        }
    }))
        .is::<crate::civ3_ai::defender_ai::DefensePlan>()
    {
        let mut defense: crate::civ3_ai::defender_ai::DefenseStep = {
            let __call_34_0 = &game;
            let __call_34_1 = (*unit).clone();
            let __call_34_2 = &((*(&(if let Some(__value) =
                (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) =
                        (&(plan)).downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) =
                            (&(plan)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                panic!("unsupported union value")
                            }
                        }
                    }
                }
            }))
                .downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                .ok_or("union type mismatch")?)
            .clone());
            let __call_34_3 = rng.clone();
            crate::civ3_ai::defender_ai::advance_defense_plan(
                __call_34_0,
                __call_34_1,
                __call_34_2,
                __call_34_3,
            )
        }?;
        return Ok((
            game,
            match ((defense).plan.clone()).as_ref() {
                Some(__value) => Some(Box::new(__value.clone()) as Box<dyn std::any::Any>),
                None => None,
            },
            (if (&(defense).movement).is_none() {
                vec![]
            } else {
                vec![(*((defense).movement.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone()]
            }),
        ));
    }
    if (&(if let Some(__value) = (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>() {
        Box::new(__value.clone()) as Box<dyn std::any::Any>
    } else {
        if let Some(__value) = (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
        {
            Box::new(__value.clone()) as Box<dyn std::any::Any>
        } else {
            if let Some(__value) =
                (&(plan)).downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(plan)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        panic!("unsupported union value")
                    }
                }
            }
        }
    }))
        .is::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
    {
        let mut exploration: crate::civ3_ai::explorer_ai::ExplorationStep = {
            let __call_35_0 = &game;
            let __call_35_1 = unit;
            let __call_35_2 = &((*(&(if let Some(__value) =
                (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) =
                        (&(plan)).downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) =
                            (&(plan)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                panic!("unsupported union value")
                            }
                        }
                    }
                }
            }))
                .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
                .ok_or("union type mismatch")?)
            .clone());
            let __call_35_3 = &(Some(rng.clone()));
            crate::civ3_ai::explorer_ai::advance_exploration_plan(
                __call_35_0,
                __call_35_1,
                __call_35_2,
                __call_35_3,
            )
        }?;
        return Ok((
            game,
            match ((exploration).plan.clone()).as_ref() {
                Some(__value) => Some(Box::new(__value.clone()) as Box<dyn std::any::Any>),
                None => None,
            },
            (if (&(exploration).movement).is_none() {
                vec![]
            } else {
                vec![(*((exploration).movement.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone()]
            }),
        ));
    }
    if (&(if let Some(__value) = (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>() {
        Box::new(__value.clone()) as Box<dyn std::any::Any>
    } else {
        if let Some(__value) = (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
        {
            Box::new(__value.clone()) as Box<dyn std::any::Any>
        } else {
            if let Some(__value) =
                (&(plan)).downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(plan)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        panic!("unsupported union value")
                    }
                }
            }
        }
    }))
        .is::<crate::civ3_ai::worker_ai::WorkerPlan>()
    {
        let mut worker: crate::civ3_ai::worker_ai::WorkerStep = {
            let __call_36_0 = &game;
            let __call_36_1 = unit;
            let __call_36_2 = &((*(&(if let Some(__value) =
                (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) =
                        (&(plan)).downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) =
                            (&(plan)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                panic!("unsupported union value")
                            }
                        }
                    }
                }
            }))
                .downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                .ok_or("union type mismatch")?)
            .clone());
            let __call_36_3 = &(Some(rng.clone()));
            let __call_36_default_4 = true;
            crate::civ3_ai::worker_ai::advance_worker_plan(
                __call_36_0,
                __call_36_1,
                __call_36_2,
                __call_36_3,
                __call_36_default_4,
            )
        }?;
        return Ok((
            game,
            match ((worker).plan.clone()).as_ref() {
                Some(__value) => Some(Box::new(__value.clone()) as Box<dyn std::any::Any>),
                None => None,
            },
            (if (&(worker).movement).is_none() {
                vec![]
            } else {
                vec![(*((worker).movement.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone()]
            }),
        ));
    }
    if ((*(&(if let Some(__value) =
        (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
    {
        Box::new(__value.clone()) as Box<dyn std::any::Any>
    } else {
        if let Some(__value) = (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
        {
            Box::new(__value.clone()) as Box<dyn std::any::Any>
        } else {
            if let Some(__value) =
                (&(plan)).downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(plan)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        panic!("unsupported union value")
                    }
                }
            }
        }
    }))
        .downcast_ref::<MissionTask>()
        .ok_or("union type mismatch")?)
    .clone()
        == MissionTask::SETTLER)
    {
        let mut settler: crate::civ3_ai::settler_ai::SettlerStep = {
            let __call_37_0 = game.clone();
            let __call_37_1 = (*unit).clone();
            let __call_37_2 = rng.clone();
            crate::civ3_ai::settler_ai::advance_settler(__call_37_0, __call_37_1, __call_37_2)
        }?;
        if (&(settler).game).is_some() {
            game = (*((settler).game.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone();
        }
        let mut done: bool = {
            let __needle = (settler).status.clone();
            let __container = &({
                let __tuple_value = &((
                    crate::civ3_ai::settler_ai::SettlerStatus::REPLAN,
                    crate::civ3_ai::settler_ai::SettlerStatus::FOUNDED,
                    crate::civ3_ai::settler_ai::SettlerStatus::REMOVED,
                ));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                ]
            });
            __container.contains(&__needle)
        };
        return Ok((
            game,
            (if done {
                None
            } else {
                Some(
                    if let Some(__value) =
                        (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) =
                            (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) = (&(plan))
                                .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>(
                            ) {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (&(plan))
                                    .downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>(
                                ) {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                                    } else {
                                        panic!("unsupported union value")
                                    }
                                }
                            }
                        }
                    },
                )
            }),
            (if (&(settler).movement).is_none() {
                vec![]
            } else {
                vec![(*((settler).movement.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone()]
            }),
        ));
    }
    let mut moves: Vec<crate::openciv3::unit_movement::MoveResult> = {
        let __call_38_0 = &game;
        let __call_38_1 = (*unit).clone();
        let __call_38_2 = rng.clone();
        crate::civ3_ai::settler_ai::play_escort(__call_38_0, __call_38_1, __call_38_2)
    }?;
    Ok((
        game,
        (if (&(unit).escorting).is_some() {
            Some(
                if let Some(__value) =
                    (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) =
                        (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) =
                            (&(plan)).downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) =
                                (&(plan)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                            {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    panic!("unsupported union value")
                                }
                            }
                        }
                    }
                },
            )
        } else {
            None
        }),
        moves,
    ))
}

// Python: civ3_ai/civilization_ai.py:251
pub(crate) fn CivilizationAI__play_movement(
    mut self_: &mut CivilizationAI,
    mut game: crate::openciv3::game_state::GameState,
    mut owner: i64,
    mut rng: rt::Random,
    mut automated_human: bool,
) -> rt::Result<Vec<AIUnitTurn>> {
    if (&(self_)._trade_session).is_some() {
        return Err("Respond to the pending trade before movement"
            .to_string()
            .into());
    }
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, owner)?;
    if (((player).human && !(automated_human))
        || (crate::openciv3::players::Player__barbarian(&player)?
            || (!((player).included) || (player).defeated)))
    {
        return Err(
            "Civilization movement requires an active nonhuman civilization"
                .to_string()
                .into(),
        );
    }
    if (player).has_played_current_turn {
        return Err("Civilization movement phase already ended"
            .to_string()
            .into());
    }
    let mut live: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_40: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_39 = ((game).units.clone());
        for unit in __comprehension_source_39.iter().cloned() {
            if (&(unit).transported_by).is_none() {
                __comprehension_result_40.insert((unit).id);
            }
        }
        __comprehension_result_40
    };
    self_.plans = {
        let mut __comprehension_result_42: indexmap::IndexMap<i64, Box<dyn std::any::Any>> =
            indexmap::IndexMap::new();
        let __comprehension_source_41 = ((((self_).plans)
            .iter()
            .map(|(__key, __value)| {
                (
                    __key.clone(),
                    if let Some(__value) =
                        (&(__value)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) =
                            (&(__value)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) = (&(__value))
                                .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>(
                            ) {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (&(__value))
                                    .downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>(
                                ) {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    if let Some(__value) =
                                        (&(__value)).downcast_ref::<MissionTask>()
                                    {
                                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                                    } else {
                                        panic!("unsupported union value")
                                    }
                                }
                            }
                        }
                    },
                )
            })
            .collect::<indexmap::IndexMap<_, _>>())
        .iter()
        .map(|(__key, __value)| {
            (
                __key.clone(),
                if let Some(__value) =
                    (&(__value)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) =
                        (&(__value)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) = (&(__value))
                            .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>(
                        ) {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) =
                                (&(__value)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                            {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (&(__value)).downcast_ref::<MissionTask>() {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    panic!("unsupported union value")
                                }
                            }
                        }
                    }
                },
            )
        })
        .collect::<Vec<_>>());
        for (index, plan) in __comprehension_source_41.into_iter() {
            if {
                let __needle = index;
                let __container = &live;
                __container.contains(&__needle)
            } {
                {
                    let (__key, __value) = (
                        index,
                        if let Some(__value) =
                            (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) =
                                (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                            {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (&(plan))
                                    .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>(
                                ) {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    if let Some(__value) = (&(plan))
                                        .downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>(
                                    ) {
                                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                                    } else {
                                        if let Some(__value) =
                                            (&(plan)).downcast_ref::<MissionTask>()
                                        {
                                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                                        } else {
                                            panic!("unsupported union value")
                                        }
                                    }
                                }
                            }
                        },
                    );
                    __comprehension_result_42.insert(__key, __value);
                }
            }
        }
        __comprehension_result_42
    };
    let mut units: Vec<crate::openciv3::units::Unit> = {
        let mut __comprehension_result_44: Vec<crate::openciv3::units::Unit> = Vec::new();
        let __comprehension_source_43 = ((game).units.clone());
        for unit in __comprehension_source_43.iter().cloned() {
            if (((unit).owner == owner)
                && ((&(unit).transported_by).is_none()
                    || (({
                        let __source = &(&(&(game).scenario).rules).units;
                        let __key = (unit).prototype;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .domain
                        == 2i64)))
            {
                __comprehension_result_44.push(unit.clone());
            }
        }
        __comprehension_result_44
    };
    for mut unit in (units).iter() {
        if ((&(unit).transported_by).is_none()
            && ((&(unit).settler_mission).is_none()
                && (({
                    let __source = &(&(&(game).scenario).rules).units;
                    let __key = (unit).prototype;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .orders
                    & 4194304i64)
                    != 0))
        {
            crate::openciv3::unit_missions::plan_settler(&game, (*unit).clone())?;
        }
    }
    let mut waiting: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_46: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_45 = (units.clone());
        for unit in __comprehension_source_45.iter().cloned() {
            if ((&(unit).settler_mission).is_some()
                && (((((*((unit).settler_mission.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone())
                .goal
                .clone())
                .as_str()
                    == "build_city")
                    && (((*((unit).settler_mission.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone())
                    .escort
                    .clone())
                    .is_none()))
            {
                __comprehension_result_46.insert(((unit).x, (unit).y));
            }
        }
        __comprehension_result_46
    };
    for mut unit in (units).iter().cloned() {
        if ((&(unit).transported_by).is_none() && {
            let __needle = ((unit).x, (unit).y);
            let __container = &waiting;
            __container.contains(&__needle)
        }) {
            unit.fortified = false;
            CivilizationAI___clear(&mut self_, game.clone(), unit)?;
        }
    }

    let mut reports: Vec<AIUnitTurn> = vec![];
    for mut unit in {
        let __values = units;
        let __reverse = false;
        rt::sorted_by_key(
            __values,
            |__item| CivilizationAI__play_movement__order(game.clone(), __item),
            __reverse,
        )?
    } {
        if !(({
            let mut __comprehension_result_48: Vec<bool> = Vec::new();
            let __comprehension_source_47 = ((game).units.clone());
            for other in __comprehension_source_47.iter().cloned() {
                __comprehension_result_48.push(((other).id == (unit).id));
            }
            __comprehension_result_48
        })
        .into_iter()
        .any(|__value| __value))
        {
            continue;
        }
        if (({
            let __source = &(&(&(game).scenario).rules).units;
            let __key = (unit).prototype;
            &__source[rt::index(__source.len(), __key)?]
        })
        .domain
            == 2i64)
        {
            CivilizationAI___clear(&mut self_, game.clone(), unit.clone())?;
            if ((unit).movement_remaining > 0.0001f64) {
                {
                    reports.push(_play_aircraft(&game, &unit, rng.clone())?);
                };
            }
            continue;
        }
        if ((unit).fortified || (&(unit).transported_by).is_some()) {
            continue;
        }
        let mut moves: Vec<crate::openciv3::unit_movement::MoveResult> = vec![];
        for _ in 0i64..2i64 {
            let mut plan: Box<dyn std::any::Any> = match ((((self_).plans)
                .iter()
                .map(|(__key, __value)| {
                    (
                        __key.clone(),
                        if let Some(__value) =
                            (&(__value)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) = (&(__value))
                                .downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>(
                            ) {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (&(__value))
                                    .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>(
                                ) {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    if let Some(__value) = (&(__value))
                                        .downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>(
                                    ) {
                                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                                    } else {
                                        if let Some(__value) =
                                            (&(__value)).downcast_ref::<MissionTask>()
                                        {
                                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                                        } else {
                                            panic!("unsupported union value")
                                        }
                                    }
                                }
                            }
                        },
                    )
                })
                .collect::<indexmap::IndexMap<_, _>>())
            .get(&((unit).id))
            .map(|__value| {
                if let Some(__value) =
                    (&(__value)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) =
                        (&(__value)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) = (&(__value))
                            .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>(
                        ) {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) =
                                (&(__value)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                            {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (&(__value)).downcast_ref::<MissionTask>() {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    panic!("unsupported union value")
                                }
                            }
                        }
                    }
                }
            })) {
                Some(__value) => __value,
                None => CivilizationAI__choose_plan(&mut self_, &game, unit.clone())?,
            };
            self_.plans.insert(
                (unit).id,
                if let Some(__value) =
                    (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) =
                        (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) =
                            (&(plan)).downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) =
                                (&(plan)).downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>()
                            {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    panic!("unsupported union value")
                                }
                            }
                        }
                    }
                },
            );
            while (((unit).movement_remaining > 0.0001f64)
                && (!((unit).fortified) && (&(unit).transported_by).is_none()))
            {
                let mut before: (i64, i64, f64, Option<i64>, bool) = (
                    (unit).x,
                    (unit).y,
                    (unit).movement_remaining,
                    (unit).worker_job.clone(),
                    (unit).fortified,
                );
                let (mut game, mut remaining, mut step_moves): (
                    crate::openciv3::game_state::GameState,
                    Option<Box<dyn std::any::Any>>,
                    Vec<crate::openciv3::unit_movement::MoveResult>,
                ) = CivilizationAI___step(&mut self_, game.clone(), &unit, &plan, rng.clone())?;
                {
                    let __values = step_moves.clone();
                    moves.extend(__values);
                };
                if ((remaining).is_none() || (&(unit).transported_by).is_some()) {
                    CivilizationAI___clear(&mut self_, game.clone(), unit.clone())?;
                    break;
                }
                plan = match ((remaining).as_ref().map(|__value| {
                    if let Some(__value) =
                        (&(__value)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) =
                            (&(__value)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) = (&(__value))
                                .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>(
                            ) {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (&(__value))
                                    .downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>(
                                ) {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    if let Some(__value) =
                                        (&(__value)).downcast_ref::<MissionTask>()
                                    {
                                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                                    } else {
                                        panic!("unsupported union value")
                                    }
                                }
                            }
                        }
                    }
                }))
                .as_ref()
                {
                    Some(__value) => {
                        if let Some(__value) =
                            (__value).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) =
                                (__value).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                            {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (__value)
                                    .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>(
                                ) {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    if let Some(__value) = (__value)
                                        .downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>(
                                    ) {
                                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                                    } else {
                                        if let Some(__value) =
                                            (__value).downcast_ref::<MissionTask>()
                                        {
                                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                                        } else {
                                            return Err("unsupported union value".into());
                                        }
                                    }
                                }
                            }
                        }
                    }
                    None => return Err("expected a union value".into()),
                };
                self_.plans.insert(
                    (unit).id,
                    if let Some(__value) =
                        (&(plan)).downcast_ref::<crate::civ3_ai::combat_ai::CombatPlan>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) =
                            (&(plan)).downcast_ref::<crate::civ3_ai::defender_ai::DefensePlan>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) = (&(plan))
                                .downcast_ref::<crate::civ3_ai::explorer_ai::ExplorationPlan>(
                            ) {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (&(plan))
                                    .downcast_ref::<crate::civ3_ai::worker_ai::WorkerPlan>(
                                ) {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    if let Some(__value) = (&(plan)).downcast_ref::<MissionTask>() {
                                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                                    } else {
                                        panic!("unsupported union value")
                                    }
                                }
                            }
                        }
                    },
                );
                if (before
                    == (
                        (unit).x,
                        (unit).y,
                        (unit).movement_remaining,
                        (unit).worker_job.clone(),
                        (unit).fortified,
                    ))
                {
                    CivilizationAI___clear(&mut self_, game.clone(), unit.clone())?;
                    break;
                }
            }
            if (!(({
                let mut __comprehension_result_50: Vec<bool> = Vec::new();
                let __comprehension_source_49 = ((game).units.clone());
                for other in __comprehension_source_49.iter().cloned() {
                    __comprehension_result_50.push(((other).id == (unit).id));
                }
                __comprehension_result_50
            })
            .into_iter()
            .any(|__value| __value))
                || ((unit).fortified || {
                    let __needle = (unit).id;
                    let __container = &(self_).plans;
                    __container.contains_key(&__needle)
                }))
            {
                break;
            }
        }
        {
            reports.push(AIUnitTurn {
                unit: (unit).id,
                moves: (moves).iter().cloned().collect::<Vec<_>>(),
                bombing: None,
                rebase: None,
            });
        };
    }
    let (mut game, mut movement_end): (
        crate::openciv3::game_state::GameState,
        crate::openciv3::turn_phases::MovementEnd,
    ) = {
        let __call_51_0 = game.clone();
        let __call_51_1 = owner;
        let __call_51_2 = rng.clone();
        crate::openciv3::turn_phases::end_player_movement_state(
            __call_51_0,
            __call_51_1,
            __call_51_2,
        )
    }?;
    self_.last_game = Some(game);
    Ok((reports).iter().cloned().collect::<Vec<_>>())
}

// Python: civ3_ai/civilization_ai.py:104
pub(crate) fn _forward_airbase__airbase_score(
    targets: &[crate::openciv3::world::Tile],
    game: &crate::openciv3::game_state::GameState,
    mut radius: i64,
    base: &crate::openciv3::world::Tile,
) -> rt::Result<(i64, i64)> {
    let mut distances: Vec<i64> = {
        let mut __comprehension_result_53: Vec<i64> = Vec::new();
        let __comprehension_source_52 = (targets.to_vec());
        for target in __comprehension_source_52.iter().cloned() {
            __comprehension_result_53.push(crate::strategy::grid::distance(
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
                    let __structural_value = (*base).clone();
                    crate::strategy::grid::GridPoint {
                        x: (__structural_value).x.clone(),
                        y: (__structural_value).y.clone(),
                    }
                }),
                &({
                    let __structural_value = target.clone();
                    crate::strategy::grid::GridPoint {
                        x: (__structural_value).x.clone(),
                        y: (__structural_value).y.clone(),
                    }
                }),
            )?);
        }
        __comprehension_result_53
    };
    Ok((
        ({
            let mut __comprehension_result_55: Vec<bool> = Vec::new();
            let __comprehension_source_54 = (distances.clone());
            for gap in __comprehension_source_54.iter().cloned() {
                __comprehension_result_55.push({
                    let __compare_0 = 0i64;
                    let __compare_1 = gap;
                    if (__compare_0 < __compare_1) {
                        let __compare_2 = radius;
                        (__compare_1 <= __compare_2)
                    } else {
                        false
                    }
                });
            }
            __comprehension_result_55
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>(),
        ({
            let __values = &distances;
            let mut __items = __values.iter();
            let mut __best = __items.next().ok_or("min() arg is an empty sequence")?;
            for __candidate in __items {
                if __candidate < __best {
                    __best = __candidate;
                }
            }
            (*__best).clone()
        })
        .checked_neg()
        .ok_or("integer overflow")?,
    ))
}

// Python: civ3_ai/civilization_ai.py:276
pub(crate) fn CivilizationAI__play_movement__order(
    mut game: crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
) -> rt::Result<i64> {
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    Ok((if (((kind).orders & 4194304i64) != 0i64) {
        1i64
    } else {
        (if crate::openciv3::worker_rules::is_worker_prototype(&kind)? {
            2i64
        } else {
            0i64
        })
    }))
}
