use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct HumanTurn {
    pub(crate) owner: i64,
    pub(crate) turn: i64,
    pub(crate) defeated: bool,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct RoundAdvanced {
    pub(crate) turn: i64,
    pub(crate) year: i64,
    pub(crate) players: Vec<crate::openciv3::turn_phases::PlayerRound>,
    pub(crate) victory: Option<crate::openciv3::victory::VictoryResult>,
}

#[derive(Clone, PartialEq)]
pub(crate) struct CivilizationMoved {
    pub(crate) owner: i64,
    pub(crate) units: Vec<crate::civ3_ai::civilization_ai::AIUnitTurn>,
    pub(crate) declaration: Option<crate::openciv3::diplomacy_actions::WarDeclaration>,
}

#[derive(Clone, PartialEq)]
pub(crate) struct BarbariansMoved {
    pub(crate) units: Vec<crate::civ3_ai::barbarian_ai::BarbarianTurn>,
}

#[derive(Clone, PartialEq)]
pub(crate) struct TurnController {
    pub(crate) game: crate::openciv3::game_state::GameState,
    pub(crate) rng: rt::Random,
    pub(crate) ai: crate::civ3_ai::civilization_ai::CivilizationAI,
    pub(crate) _human_turn: Option<HumanTurn>,
    pub(crate) _pending_declaration: Option<crate::openciv3::diplomacy_actions::WarDeclaration>,
}

// Python: openciv3/turn_controller.py:57
pub(crate) fn TurnController__human_turn(
    mut self_: TurnController,
) -> rt::Result<Option<HumanTurn>> {
    let mut turn: Option<HumanTurn> = (self_)._human_turn.clone();
    if ((turn).is_some()
        && (({
            let __source = &(&(self_).game).players;
            let __key = ((*(turn.clone()).as_ref().ok_or("expected a value")?).clone()).owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .defeated
            != ((*(turn.clone()).as_ref().ok_or("expected a value")?).clone()).defeated))
    {
        turn = Some({
            let mut __replacement =
                ((*(turn.clone()).as_ref().ok_or("expected a value")?).clone()).clone();
            __replacement.defeated = ({
                let __source = &(&(self_).game).players;
                let __key = ((*(turn.clone()).as_ref().ok_or("expected a value")?).clone()).owner;
                &__source[rt::index(__source.len(), __key)?]
            })
            .defeated;
            __replacement
        });
        self_._human_turn = turn.clone();
    }
    Ok(turn)
}

// Python: openciv3/turn_controller.py:64
pub(crate) fn TurnController__advance(
    mut self_: &mut TurnController,
) -> rt::Result<Box<dyn std::any::Any>> {
    let mut game: crate::openciv3::game_state::GameState = (self_).game.clone();
    let mut human: crate::openciv3::players::Player = rt::at(&(game).players, (game).human_player)?;
    if (!((human).human) || !((human).included)) {
        return Err("Turn controller requires an included human player"
            .to_string()
            .into());
    }
    let mut pending: Option<crate::civ3_ai::civilization_ai::AITradePause> =
        crate::civ3_ai::civilization_ai::CivilizationAI__pending_trade(&(self_).ai)?;
    if (pending).is_some() {
        return Ok(match (pending).as_ref() {
            Some(__value) => Box::new(__value.clone()) as Box<dyn std::any::Any>,
            None => return Err("expected a union value".into()),
        });
    }
    let mut waiting: Option<HumanTurn> = TurnController__human_turn(self_.clone())?;
    if (waiting).is_some() {
        if ((((*(waiting.clone()).as_ref().ok_or("expected a value")?).clone()).turn
            != (game).turn)
            || (human).has_played_current_turn)
        {
            return Err("Human turn changed outside the controller"
                .to_string()
                .into());
        }
        return Ok(match (waiting).as_ref() {
            Some(__value) => Box::new(__value.clone()) as Box<dyn std::any::Any>,
            None => return Err("expected a union value".into()),
        });
    }
    let mut ordered: Vec<crate::openciv3::players::Player> = {
        let mut __decorated: Vec<((bool, bool), crate::openciv3::players::Player)> = Vec::new();
        for __item in (crate::openciv3::game_state::GameState__players_in_order(&game)?).into_iter()
        {
            let player = __item;
            let __key = {
                (
                    crate::openciv3::players::Player__barbarian(&player)?,
                    !((player).human),
                )
            };
            __decorated.push((__key, player));
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
    for mut player in ordered {
        if (!((player).included) || (player).has_played_current_turn) {
            continue;
        }
        if ((player).defeated && ((player).civilization != (game).human_player)) {
            continue;
        }
        if (((game).turn == 0i64)
            && (crate::openciv3::players::Player__barbarian(&player)? || (player).skip_first_turn))
        {
            continue;
        }
        if !(crate::openciv3::players::Player__barbarian(&player)?) {
            crate::openciv3::deal_lifecycle::expire_deals(&game, (player).civilization)?;
        }
        if ((player).civilization == (game).human_player) {
            self_._human_turn = Some(HumanTurn {
                owner: (player).civilization,
                turn: (game).turn,
                defeated: (player).defeated,
            });
            return Ok(match ((self_)._human_turn.clone()).as_ref() {
                Some(__value) => Box::new(__value.clone()) as Box<dyn std::any::Any>,
                None => return Err("expected a union value".into()),
            });
        }
        if crate::openciv3::players::Player__barbarian(&player)? {
            let (mut game, mut barbarian_reports): (
                crate::openciv3::game_state::GameState,
                Vec<crate::civ3_ai::barbarian_ai::BarbarianTurn>,
            ) = {
                let __call_1274_0 = game.clone();
                let __call_1274_1 = (self_).rng.clone();
                crate::civ3_ai::barbarian_ai::play_barbarian_turn_state(
                    __call_1274_0,
                    __call_1274_1,
                )
            }?;
            self_.game = game;
            return Ok(Box::new(BarbariansMoved {
                units: barbarian_reports,
            }) as Box<dyn std::any::Any>);
        }
        let mut previous: Option<crate::civ3_ai::strategic_ai::StrategyUpdate> =
            ((&(self_).ai).strategy_updates.clone())
                .get(&((player).civilization))
                .cloned();
        let mut result: Box<dyn std::any::Any> = {
            let __call_1275_0 = &mut (self_).ai;
            let __call_1275_1 = &game;
            let __call_1275_2 = (player).civilization;
            let __call_1275_3 = (self_).rng.clone();
            let __call_1275_default_4 = false;
            crate::civ3_ai::civilization_ai::CivilizationAI__play_turn(
                __call_1275_0,
                __call_1275_1,
                __call_1275_2,
                __call_1275_3,
                __call_1275_default_4,
            )
        }?;
        if (&(&(self_).ai).last_game).is_some() {
            self_.game = (*((&(self_).ai).last_game.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone();
            game = (self_).game.clone();
        }
        let mut update: Option<crate::civ3_ai::strategic_ai::StrategyUpdate> =
            ((&(self_).ai).strategy_updates.clone())
                .get(&((player).civilization))
                .cloned();
        let mut declaration: Option<crate::openciv3::diplomacy_actions::WarDeclaration> =
            (if ((update).is_some()
                && ((((*(update.clone()).as_ref().ok_or("expected a value")?).clone())
                    .declaration
                    .clone())
                .is_some()
                    && ((previous).is_none()
                        || (((*(update.clone()).as_ref().ok_or("expected a value")?).clone())
                            .declaration
                            .clone()
                            != ((*(previous.clone()).as_ref().ok_or("expected a value")?)
                                .clone())
                            .declaration
                            .clone()))))
            {
                ((*(update.clone()).as_ref().ok_or("expected a value")?).clone())
                    .declaration
                    .clone()
            } else {
                None
            });
        if (&(if let Some(__value) =
            (&(result)).downcast_ref::<Vec<crate::civ3_ai::civilization_ai::AIUnitTurn>>()
        {
            Box::new(__value.clone()) as Box<dyn std::any::Any>
        } else {
            if let Some(__value) =
                (&(result)).downcast_ref::<crate::civ3_ai::civilization_ai::AITradePause>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                panic!("unsupported union value")
            }
        }))
            .is::<crate::civ3_ai::civilization_ai::AITradePause>()
        {
            self_._pending_declaration = declaration;
            return Ok(
                if let Some(__value) = (&(result)).downcast_ref::<HumanTurn>() {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) = (&(result)).downcast_ref::<CivilizationMoved>() {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) = (&(result)).downcast_ref::<BarbariansMoved>() {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) = (&(result)).downcast_ref::<RoundAdvanced>() {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                if let Some(__value) = (&(result))
                                    .downcast_ref::<crate::civ3_ai::civilization_ai::AITradePause>(
                                ) {
                                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                                } else {
                                    return Err("unsupported union value".into());
                                }
                            }
                        }
                    }
                },
            );
        }
        return Ok(Box::new(CivilizationMoved {
            owner: (player).civilization,
            units: (*(&(result))
                .downcast_ref::<Vec<crate::civ3_ai::civilization_ai::AIUnitTurn>>()
                .ok_or("union type mismatch")?)
            .clone(),
            declaration: declaration,
        }) as Box<dyn std::any::Any>);
    }
    let (mut game, mut reports): (
        crate::openciv3::game_state::GameState,
        Vec<crate::openciv3::turn_phases::PlayerRound>,
    ) = {
        let __call_1276_0 = game.clone();
        let __call_1276_1 = (self_).rng.clone();
        let __call_1276_default_2 = &None;
        crate::openciv3::turn_phases::advance_economic_round_state(
            __call_1276_0,
            __call_1276_1,
            __call_1276_default_2,
        )
    }?;
    self_.game = game.clone();
    Ok(Box::new(RoundAdvanced {
        turn: (game).turn,
        year: (game).year,
        players: reports,
        victory: crate::openciv3::victory::check_victory(&game)?,
    }) as Box<dyn std::any::Any>)
}

// Python: openciv3/turn_controller.py:111
pub(crate) fn TurnController__launch_human_spaceship(
    self_: &TurnController,
    mut turn: i64,
) -> rt::Result<crate::openciv3::victory::VictoryResult> {
    let mut waiting: Option<HumanTurn> = TurnController__human_turn((*self_).clone())?;
    if ((waiting).is_none()
        || ((((*(waiting.clone()).as_ref().ok_or("expected a value")?).clone()).turn != turn)
            || ((&(self_).game).turn != turn)))
    {
        return Err("A spaceship can only launch during your turn"
            .to_string()
            .into());
    }
    crate::openciv3::victory::launch_spaceship(
        &(self_).game,
        ((*(waiting).as_ref().ok_or("expected a value")?).clone()).owner,
    )
}

/// Require the presented turn token so duplicate UI commands cannot skip turns.
// Python: openciv3/turn_controller.py:117
pub(crate) fn TurnController__end_human_turn(
    mut self_: TurnController,
    mut turn: i64,
) -> rt::Result<crate::openciv3::turn_phases::MovementEnd> {
    let mut waiting: Option<HumanTurn> = (self_)._human_turn.clone();
    if ((waiting).is_none()
        || ((turn != ((*(waiting.clone()).as_ref().ok_or("expected a value")?).clone()).turn)
            || (turn != (&(self_).game).turn)))
    {
        return Err("No matching human turn is waiting to end"
            .to_string()
            .into());
    }
    let (mut updated_game, mut completed): (
        crate::openciv3::game_state::GameState,
        crate::openciv3::turn_phases::MovementEnd,
    ) = {
        let __call_1277_0 = (self_).game.clone();
        let __call_1277_1 = ((*(waiting).as_ref().ok_or("expected a value")?).clone()).owner;
        let __call_1277_2 = (self_).rng.clone();
        crate::openciv3::turn_phases::end_player_movement_state(
            __call_1277_0,
            __call_1277_1,
            __call_1277_2,
        )
    }?;
    self_.game = updated_game;
    self_._human_turn = None;
    Ok(completed)
}

/// Let the decision engine finish the active human phase explicitly.
// Python: openciv3/turn_controller.py:127
pub(crate) fn TurnController__autoplay_human_turn(
    mut self_: &mut TurnController,
    mut turn: i64,
) -> rt::Result<Vec<crate::civ3_ai::civilization_ai::AIUnitTurn>> {
    let mut waiting: Option<HumanTurn> = (self_)._human_turn.clone();
    if ((waiting).is_none()
        || (((*(waiting.clone()).as_ref().ok_or("expected a value")?).clone()).defeated
            || ((turn != ((*(waiting.clone()).as_ref().ok_or("expected a value")?).clone()).turn)
                || (turn != (&(self_).game).turn))))
    {
        return Err("No matching human turn is waiting for automation"
            .to_string()
            .into());
    }
    let mut result: Box<dyn std::any::Any> = {
        let __call_1278_0 = &mut (self_).ai;
        let __call_1278_1 = &(self_).game;
        let __call_1278_2 = ((*(waiting).as_ref().ok_or("expected a value")?).clone()).owner;
        let __call_1278_3 = (self_).rng.clone();
        let __call_1278_4 = true;
        crate::civ3_ai::civilization_ai::CivilizationAI__play_turn(
            __call_1278_0,
            __call_1278_1,
            __call_1278_2,
            __call_1278_3,
            __call_1278_4,
        )
    }?;
    if (&(&(self_).ai).last_game).is_some() {
        self_.game = (*((&(self_).ai).last_game.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone();
    }
    if (&(if let Some(__value) =
        (&(result)).downcast_ref::<Vec<crate::civ3_ai::civilization_ai::AIUnitTurn>>()
    {
        Box::new(__value.clone()) as Box<dyn std::any::Any>
    } else {
        if let Some(__value) =
            (&(result)).downcast_ref::<crate::civ3_ai::civilization_ai::AITradePause>()
        {
            Box::new(__value.clone()) as Box<dyn std::any::Any>
        } else {
            panic!("unsupported union value")
        }
    }))
        .is::<crate::civ3_ai::civilization_ai::AITradePause>()
    {
        return Err("Automated human produced an unexpected trade pause"
            .to_string()
            .into());
    }
    self_._human_turn = None;
    Ok((*(&(result))
        .downcast_ref::<Vec<crate::civ3_ai::civilization_ai::AIUnitTurn>>()
        .ok_or("union type mismatch")?)
    .clone())
}

// Python: openciv3/turn_controller.py:140
pub(crate) fn TurnController__respond_to_trade(
    mut self_: &mut TurnController,
    mut accept: bool,
) -> rt::Result<Box<dyn std::any::Any>> {
    let mut pending: Option<crate::civ3_ai::civilization_ai::AITradePause> =
        crate::civ3_ai::civilization_ai::CivilizationAI__pending_trade(&(self_).ai)?;
    if (pending).is_none() {
        return Err("No human trade offer is pending".to_string().into());
    }
    let mut owner: i64 = (((*(pending).as_ref().ok_or("expected a value")?).clone())
        .offer
        .clone())
    .proposer;
    let mut result: Box<dyn std::any::Any> = {
        let __call_1279_0 = &mut (self_).ai;
        let __call_1279_1 = &(self_).game;
        let __call_1279_2 = accept;
        crate::civ3_ai::civilization_ai::CivilizationAI__respond_to_trade(
            __call_1279_0,
            __call_1279_1,
            __call_1279_2,
        )
    }?;
    if (&(if let Some(__value) =
        (&(result)).downcast_ref::<Vec<crate::civ3_ai::civilization_ai::AIUnitTurn>>()
    {
        Box::new(__value.clone()) as Box<dyn std::any::Any>
    } else {
        if let Some(__value) =
            (&(result)).downcast_ref::<crate::civ3_ai::civilization_ai::AITradePause>()
        {
            Box::new(__value.clone()) as Box<dyn std::any::Any>
        } else {
            panic!("unsupported union value")
        }
    }))
        .is::<crate::civ3_ai::civilization_ai::AITradePause>()
    {
        return Ok(
            if let Some(__value) = (&(result)).downcast_ref::<CivilizationMoved>() {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(result)).downcast_ref::<crate::civ3_ai::civilization_ai::AITradePause>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    return Err("unsupported union value".into());
                }
            },
        );
    }
    let mut declaration: Option<crate::openciv3::diplomacy_actions::WarDeclaration> =
        (self_)._pending_declaration.clone();
    self_._pending_declaration = None;
    Ok(Box::new(CivilizationMoved {
        owner: owner,
        units: (*(&(result))
            .downcast_ref::<Vec<crate::civ3_ai::civilization_ai::AIUnitTurn>>()
            .ok_or("union type mismatch")?)
        .clone(),
        declaration: declaration,
    }) as Box<dyn std::any::Any>)
}
