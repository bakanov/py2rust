use py2rust_service_runtime as rt;

// Python: civ3_console/native_campaign.py:20
pub(crate) fn advance_to_human(
    mut controller: crate::openciv3::turn_controller::TurnController,
) -> rt::Result<crate::openciv3::turn_controller::TurnController> {
    controller = {
        let mut __replacement = (controller.clone()).clone();
        __replacement
    };
    for _ in 0i64..10i64 {
        let mut event: Box<dyn std::any::Any> =
            crate::openciv3::turn_controller::TurnController__advance(&mut controller)?;
        if (&(if let Some(__value) =
            (&(event)).downcast_ref::<crate::openciv3::turn_controller::HumanTurn>()
        {
            Box::new(__value.clone()) as Box<dyn std::any::Any>
        } else {
            if let Some(__value) =
                (&(event)).downcast_ref::<crate::openciv3::turn_controller::CivilizationMoved>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(event)).downcast_ref::<crate::openciv3::turn_controller::BarbariansMoved>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) =
                        (&(event)).downcast_ref::<crate::openciv3::turn_controller::RoundAdvanced>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) = (&(event))
                            .downcast_ref::<crate::civ3_ai::civilization_ai::AITradePause>(
                        ) {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            panic!("unsupported union value")
                        }
                    }
                }
            }
        }))
            .is::<crate::civ3_ai::civilization_ai::AITradePause>()
        {
            event = if let Some(__value) = (&({
                let __call_1_0 = &mut controller;
                let __call_1_1 = false;
                crate::openciv3::turn_controller::TurnController__respond_to_trade(
                    __call_1_0, __call_1_1,
                )
            }?))
                .downcast_ref::<crate::openciv3::turn_controller::HumanTurn>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) = (&({
                    let __call_1_0 = &mut controller;
                    let __call_1_1 = false;
                    crate::openciv3::turn_controller::TurnController__respond_to_trade(
                        __call_1_0, __call_1_1,
                    )
                }?))
                    .downcast_ref::<crate::openciv3::turn_controller::CivilizationMoved>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) = (&({
                        let __call_1_0 = &mut controller;
                        let __call_1_1 = false;
                        crate::openciv3::turn_controller::TurnController__respond_to_trade(
                            __call_1_0, __call_1_1,
                        )
                    }?))
                        .downcast_ref::<crate::openciv3::turn_controller::BarbariansMoved>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) = (&({
                            let __call_1_0 = &mut controller;
                            let __call_1_1 = false;
                            crate::openciv3::turn_controller::TurnController__respond_to_trade(
                                __call_1_0, __call_1_1,
                            )
                        }?))
                            .downcast_ref::<crate::openciv3::turn_controller::RoundAdvanced>()
                        {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            if let Some(__value) = (&({
                                let __call_1_0 = &mut controller;
                                let __call_1_1 = false;
                                crate::openciv3::turn_controller::TurnController__respond_to_trade(
                                    __call_1_0, __call_1_1,
                                )
                            }?))
                                .downcast_ref::<crate::civ3_ai::civilization_ai::AITradePause>()
                            {
                                Box::new(__value.clone()) as Box<dyn std::any::Any>
                            } else {
                                return Err("unsupported union value".into());
                            }
                        }
                    }
                }
            };
        }
        if (&(if let Some(__value) =
            (&(event)).downcast_ref::<crate::openciv3::turn_controller::HumanTurn>()
        {
            Box::new(__value.clone()) as Box<dyn std::any::Any>
        } else {
            if let Some(__value) =
                (&(event)).downcast_ref::<crate::openciv3::turn_controller::CivilizationMoved>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(event)).downcast_ref::<crate::openciv3::turn_controller::BarbariansMoved>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) =
                        (&(event)).downcast_ref::<crate::openciv3::turn_controller::RoundAdvanced>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) = (&(event))
                            .downcast_ref::<crate::civ3_ai::civilization_ai::AITradePause>(
                        ) {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            panic!("unsupported union value")
                        }
                    }
                }
            }
        }))
            .is::<crate::openciv3::turn_controller::HumanTurn>()
        {
            println!(
                "{}",
                format!(
                    "{}{}{}",
                    "Human turn ",
                    ((if let Some(__value) =
                        (&(event)).downcast_ref::<crate::openciv3::turn_controller::HumanTurn>()
                    {
                        Ok(__value.turn)
                    } else {
                        if let Some(__value) = (&(event))
                            .downcast_ref::<crate::openciv3::turn_controller::RoundAdvanced>(
                        ) {
                            Ok(__value.turn)
                        } else {
                            Err("union has no matching record field")
                        }
                    })?)
                    .to_string(),
                    " ready"
                )
            );
            return Ok(controller.clone());
        }
        if (&(if let Some(__value) =
            (&(event)).downcast_ref::<crate::openciv3::turn_controller::HumanTurn>()
        {
            Box::new(__value.clone()) as Box<dyn std::any::Any>
        } else {
            if let Some(__value) =
                (&(event)).downcast_ref::<crate::openciv3::turn_controller::CivilizationMoved>()
            {
                Box::new(__value.clone()) as Box<dyn std::any::Any>
            } else {
                if let Some(__value) =
                    (&(event)).downcast_ref::<crate::openciv3::turn_controller::BarbariansMoved>()
                {
                    Box::new(__value.clone()) as Box<dyn std::any::Any>
                } else {
                    if let Some(__value) =
                        (&(event)).downcast_ref::<crate::openciv3::turn_controller::RoundAdvanced>()
                    {
                        Box::new(__value.clone()) as Box<dyn std::any::Any>
                    } else {
                        if let Some(__value) = (&(event))
                            .downcast_ref::<crate::civ3_ai::civilization_ai::AITradePause>(
                        ) {
                            Box::new(__value.clone()) as Box<dyn std::any::Any>
                        } else {
                            panic!("unsupported union value")
                        }
                    }
                }
            }
        }))
            .is::<crate::openciv3::turn_controller::RoundAdvanced>()
        {
            println!("{}", format!("{}{}{}{}", "Round complete: turn ", ((if let Some(__value) = (&(if let Some(__value) = (&(event)).downcast_ref::<crate::openciv3::turn_controller::HumanTurn>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { if let Some(__value) = (&(event)).downcast_ref::<crate::openciv3::turn_controller::CivilizationMoved>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { if let Some(__value) = (&(event)).downcast_ref::<crate::openciv3::turn_controller::BarbariansMoved>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { if let Some(__value) = (&(event)).downcast_ref::<crate::openciv3::turn_controller::RoundAdvanced>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { if let Some(__value) = (&(event)).downcast_ref::<crate::civ3_ai::civilization_ai::AITradePause>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { panic!("unsupported union value") } } } } })).downcast_ref::<crate::openciv3::turn_controller::HumanTurn>() { Ok(__value.turn) } else { if let Some(__value) = (&(if let Some(__value) = (&(event)).downcast_ref::<crate::openciv3::turn_controller::HumanTurn>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { if let Some(__value) = (&(event)).downcast_ref::<crate::openciv3::turn_controller::CivilizationMoved>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { if let Some(__value) = (&(event)).downcast_ref::<crate::openciv3::turn_controller::BarbariansMoved>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { if let Some(__value) = (&(event)).downcast_ref::<crate::openciv3::turn_controller::RoundAdvanced>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { if let Some(__value) = (&(event)).downcast_ref::<crate::civ3_ai::civilization_ai::AITradePause>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { panic!("unsupported union value") } } } } })).downcast_ref::<crate::openciv3::turn_controller::RoundAdvanced>() { Ok(__value.turn) } else { Err("union has no matching record field") } })?).to_string(), ", year ", ((if let Some(__value) = (&(if let Some(__value) = (&(event)).downcast_ref::<crate::openciv3::turn_controller::HumanTurn>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { if let Some(__value) = (&(event)).downcast_ref::<crate::openciv3::turn_controller::CivilizationMoved>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { if let Some(__value) = (&(event)).downcast_ref::<crate::openciv3::turn_controller::BarbariansMoved>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { if let Some(__value) = (&(event)).downcast_ref::<crate::openciv3::turn_controller::RoundAdvanced>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { if let Some(__value) = (&(event)).downcast_ref::<crate::civ3_ai::civilization_ai::AITradePause>() { Box::new(__value.clone()) as Box<dyn std::any::Any> } else { panic!("unsupported union value") } } } } })).downcast_ref::<crate::openciv3::turn_controller::RoundAdvanced>() { Ok(__value.year) } else { Err("union has no matching record field") })?).to_string()));
            for mut report in (if let Some(__value) =
                (&(event)).downcast_ref::<crate::openciv3::turn_controller::RoundAdvanced>()
            {
                Ok(__value.players.clone())
            } else {
                Err("union has no matching record field")
            })? {
                if (((report).owner == (&(controller).game).human_player)
                    && (&(report).discovery).is_some())
                {
                    println!(
                        "{}",
                        format!(
                            "{}{}",
                            "Discovered ",
                            &({
                                let __source =
                                    &(&(&(&(controller).game).scenario).rules).technologies;
                                let __key = (*((report).discovery.clone())
                                    .as_ref()
                                    .ok_or("expected a value")?)
                                .clone();
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .name
                        )
                    );
                }
            }
        }
    }
    return Err("Turn processing exceeded its phase budget"
        .to_string()
        .into());
}

// Python: civ3_console/native_campaign.py:37
pub(crate) fn main() -> rt::Result<i64> {
    let mut rules_path: String = "GameModes/civ3/ruleset.json".to_string();
    let (mut definition, mut sizes): (
        crate::openciv3::scenario_model::ScenarioDefinition,
        Vec<crate::openciv3::world_size::WorldSize>,
    ) = crate::openciv3::json_rules::decode_standalone_scenario(
        &(crate::openciv3::standalone::standalone_ruleset(
            &(crate::openciv3::json_io::read_object(&rules_path)?),
        )?),
        &rules_path,
    )?;
    definition.world_size = Some(rt::at(&sizes, 0i64)?);
    definition.selected_civilization = ({
        let __source = &(definition).playable;
        let __key = 0i64;
        &__source[rt::index(__source.len(), __key)?]
    })
    .name
    .clone();
    definition.selected_difficulty = ({
        let __source = &(definition).difficulties;
        let __key = 0i64;
        &__source[rt::index(__source.len(), __key)?]
    })
    .name
    .clone();
    let mut game: crate::openciv3::game_state::GameState =
        crate::openciv3::game_state::GameState__from_scenario(definition)?;
    let mut controller: crate::openciv3::turn_controller::TurnController =
        crate::openciv3::turn_controller::TurnController {
            game: game.clone(),
            rng: rt::random_new((game).seed),
            ai: crate::civ3_ai::civilization_ai::CivilizationAI {
                plans: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                strategy_updates: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                _trade_session: None,
                last_game: None,
            },
            _human_turn: None,
            _pending_declaration: None,
        };
    controller = advance_to_human(controller.clone())?;
    for mut unit in (&(game).units).iter() {
        println!(
            "{}",
            format!(
                "{}{}{}{}{}{}{}{}{}{}{}{}",
                "Start unit ",
                ((unit).id).to_string(),
                ": ",
                (unit).name.clone(),
                " at ",
                ((unit).x).to_string(),
                ",",
                ((unit).y).to_string(),
                ", movement ",
                rt::float_to_string((unit).movement_remaining)?,
                ", fortified ",
                (if (unit).fortified {
                    "yes".to_string()
                } else {
                    "no".to_string()
                })
            )
        );
    }
    let (mut game, mut founded): (
        crate::openciv3::game_state::GameState,
        crate::openciv3::cities::City,
    ) = {
        let __call_2_0 = game.clone();
        let __call_2_1 = {
            let __source = &(game).units;
            let __key = 0i64;
            &__source[rt::index(__source.len(), __key)?]
        };
        let __call_2_2 = "Rome";
        let __call_2_3 = (controller).rng.clone();
        crate::openciv3::city_founding::found_city_state(
            __call_2_0, __call_2_1, __call_2_2, __call_2_3,
        )
    }?;
    let mut technology: i64 = (&({
        let mut __comprehension_result_4: Vec<i64> = Vec::new();
        let __comprehension_source_3 = (((&(&(game).scenario).rules).technologies.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>());
        for (index, item) in __comprehension_source_3.iter().cloned() {
            if (AsRef::<str>::as_ref(&(item).name) == "Pottery") {
                __comprehension_result_4.push(index);
            }
        }
        __comprehension_result_4
    }))
        .iter()
        .next()
        .cloned()
        .ok_or("StopIteration")?;
    {
        let __index = rt::index(game.players.len(), (game).human_player)?;
        game.players
            .get_mut(__index)
            .ok_or("missing record")?
            .researching = Some(technology);
    }
    {
        let __index = rt::index(game.players.len(), (game).human_player)?;
        game.players
            .get_mut(__index)
            .ok_or("missing record")?
            .science_rate = 10i64;
    }
    {
        let __index = rt::index(game.players.len(), (game).human_player)?;
        game.players
            .get_mut(__index)
            .ok_or("missing record")?
            .tax_rate = 0i64;
    }
    controller.game = game.clone();
    println!(
        "{}",
        format!(
            "{}{}{}",
            "Founded ",
            &(founded).name,
            "; researching Pottery"
        )
    );
    for _ in 0i64..10i64 {
        if (game).game_over {
            break;
        }
        {
            let __call_5_0 = &mut controller;
            let __call_5_1 = (game).turn;
            crate::openciv3::turn_controller::TurnController__autoplay_human_turn(
                __call_5_0, __call_5_1,
            )
        }?;
        if (((game).turn == 0i64) && (&(&(controller).ai).last_game).is_some()) {
            for mut unit in ((*((&(controller).ai).last_game.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone())
            .units
            .clone()
            {
                println!(
                    "{}",
                    format!(
                        "{}{}{}{}{}{}",
                        "After AI ",
                        ((unit).id).to_string(),
                        ": ",
                        ((unit).x).to_string(),
                        ",",
                        ((unit).y).to_string()
                    )
                );
                if ((&(unit).settler_mission).is_some()
                    && (((*((unit).settler_mission.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone())
                    .destination
                    .clone())
                    .is_some())
                {
                    println!(
                        "{}",
                        format!(
                            "{}{}{}{}",
                            "Destination ",
                            (((*(((*((unit).settler_mission.clone())
                                .as_ref()
                                .ok_or("expected a value")?)
                            .clone())
                            .destination
                            .clone())
                            .as_ref()
                            .ok_or("expected a value")?)
                            .clone())
                            .0
                            .clone())
                            .to_string(),
                            ",",
                            (((*(((*((unit).settler_mission.clone())
                                .as_ref()
                                .ok_or("expected a value")?)
                            .clone())
                            .destination
                            .clone())
                            .as_ref()
                            .ok_or("expected a value")?)
                            .clone())
                            .1
                            .clone())
                            .to_string()
                        )
                    );
                }
            }
        }
        controller = advance_to_human(controller.clone())?;
        if ((game).turn == 0i64) {
            for mut unit in (&(&(controller).game).units).iter() {
                println!(
                    "{}",
                    format!(
                        "{}{}{}{}{}{}",
                        "After round ",
                        ((unit).id).to_string(),
                        ": ",
                        ((unit).x).to_string(),
                        ",",
                        ((unit).y).to_string()
                    )
                );
                if ((&(unit).settler_mission).is_some()
                    && (((*((unit).settler_mission.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone())
                    .destination
                    .clone())
                    .is_some())
                {
                    println!(
                        "{}",
                        format!(
                            "{}{}{}{}",
                            "Destination ",
                            (((*(((*((unit).settler_mission.clone())
                                .as_ref()
                                .ok_or("expected a value")?)
                            .clone())
                            .destination
                            .clone())
                            .as_ref()
                            .ok_or("expected a value")?)
                            .clone())
                            .0
                            .clone())
                            .to_string(),
                            ",",
                            (((*(((*((unit).settler_mission.clone())
                                .as_ref()
                                .ok_or("expected a value")?)
                            .clone())
                            .destination
                            .clone())
                            .as_ref()
                            .ok_or("expected a value")?)
                            .clone())
                            .1
                            .clone())
                            .to_string()
                        )
                    );
                }
            }
        }
        game = (controller).game.clone();
    }
    let mut player: crate::openciv3::players::Player =
        rt::at(&(game).players, (game).human_player)?;
    println!("{}", format!("{}{}", "Turn: ", ((game).turn).to_string()));
    println!(
        "{}",
        format!(
            "{}{}",
            "Civilization: ",
            &({
                let __source = &(&(game).scenario).civilizations;
                let __key = (player).civilization;
                &__source[rt::index(__source.len(), __key)?]
            })
            .name
        )
    );
    println!(
        "{}",
        format!("{}{}", "Treasury: ", ((player).gold).to_string())
    );
    println!(
        "{}",
        format!(
            "{}{}{}{}{}{}",
            "Research beakers: ",
            ((player).beakers).to_string(),
            ", turns: ",
            ((player).turns_researched).to_string(),
            ", science: ",
            ((player).science_rate).to_string()
        )
    );
    if (&(player).researching).is_some() {
        println!(
            "{}",
            format!(
                "{}{}",
                "Research target: ",
                &({
                    let __source = &(&(&(game).scenario).rules).technologies;
                    let __key = (*((player).researching.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone();
                    &__source[rt::index(__source.len(), __key)?]
                })
                .name
            )
        );
    }
    println!(
        "{}",
        format!(
            "{}{}",
            "Known technologies: ",
            ((&(player).known_technologies).len() as i64).to_string()
        )
    );
    println!(
        "{}",
        format!(
            "{}{}",
            "Units: ",
            ((&(game).units).len() as i64).to_string()
        )
    );
    println!(
        "{}",
        format!(
            "{}{}",
            "Cities: ",
            ((&(game).cities).len() as i64).to_string()
        )
    );
    let mut corruption: indexmap::IndexMap<i64, f64> =
        crate::openciv3::corruption::corruption_levels(&game)?;
    for mut city in (&(game).cities).iter() {
        if ((city).owner == (game).human_player) {
            let mut food: crate::openciv3::city_economy::CityFood =
                crate::openciv3::city_economy::city_food(&game, city, &None)?;
            let mut production: crate::openciv3::city_economy::CityProduction =
                crate::openciv3::city_economy::city_production(
                    &game,
                    city,
                    (corruption)
                        .get(&((city).id))
                        .ok_or("missing dict key")?
                        .clone(),
                    &None,
                    &None,
                )?;
            println!(
                "{}",
                format!(
                    "{}{}{}{}{}{}{}",
                    (city).name.clone(),
                    ": population ",
                    (crate::openciv3::cities::City__size(city)?).to_string(),
                    ", food ",
                    ((food).surplus).to_string(),
                    ", shields ",
                    ((production).useful).to_string()
                )
            );
            println!(
                "{}",
                format!(
                    "{}{}{}{}",
                    "Food stored: ",
                    ((city).food_stored).to_string(),
                    ", owned tiles: ",
                    ((&(game).ownership).len() as i64).to_string()
                )
            );
            for mut resident in (&(city).residents).iter() {
                if (&(resident).tile_worked).is_some() {
                    println!(
                        "{}",
                        format!(
                            "{}{}{}{}",
                            "Worked tile: ",
                            (((*(&(resident).tile_worked)
                                .as_ref()
                                .ok_or("expected a value")?)
                            .clone())
                            .0
                            .clone())
                            .to_string(),
                            ",",
                            (((*(&(resident).tile_worked)
                                .as_ref()
                                .ok_or("expected a value")?)
                            .clone())
                            .1
                            .clone())
                            .to_string()
                        )
                    );
                }
            }
        }
    }
    Ok(0i64)
}
