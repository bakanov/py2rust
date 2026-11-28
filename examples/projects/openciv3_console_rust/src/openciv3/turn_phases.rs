use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct MovementEnd {
    pub(crate) jobs: Vec<crate::openciv3::worker_jobs::JobCompletion>,
    pub(crate) shipwrecks: Vec<String>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct PlayerRound {
    pub(crate) owner: i64,
    pub(crate) treasury: crate::openciv3::treasury::TreasuryUpdate,
    pub(crate) discovery: Option<i64>,
    pub(crate) expanded: Vec<i64>,
    pub(crate) population_changes: Vec<(i64, i64)>,
    pub(crate) units_created: Vec<i64>,
    pub(crate) buildings_created: Vec<(i64, i64)>,
    pub(crate) cities_destroyed: Vec<i64>,
    pub(crate) destroyed_city_names: Vec<String>,
}

// Python: openciv3/turn_phases.py:46
pub(crate) fn _sink_exposed_ships(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    mut rng: rt::Random,
) -> rt::Result<Vec<String>> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut seafaring: bool = {
        let __needle = "Seafaring".to_string();
        let __container = &({
            let __source = &(&(game).scenario).civilizations;
            let __key = owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .traits;
        __container.contains(&__needle)
    };
    let mut chance: f64 = (if seafaring { 0.25f64 } else { 0.5f64 });
    let mut safe_sea: bool = crate::openciv3::naval_risk::safe_sea_travel(game, owner)?;
    let mut losses: Vec<crate::openciv3::units::Unit> = vec![];
    for mut ship in (&(game).units).iter() {
        if (((ship).owner != owner) || (&(ship).transported_by).is_some()) {
            continue;
        }
        let mut kind: crate::openciv3::unit_rules::UnitPrototype =
            rt::at(&(rules).units, (ship).prototype)?;
        let mut tile: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(&(game).world, (ship).x, (ship).y)?;
        if ((tile).is_some()
            && ({
                let __call_1097_0 = &kind;
                let __call_1097_1 =
                    &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone());
                let __call_1097_2 = safe_sea;
                crate::openciv3::naval_risk::hazardous_waters(
                    __call_1097_0,
                    __call_1097_1,
                    __call_1097_2,
                )
            }? && (rt::random_random(&rng) < chance)))
        {
            {
                losses.push((*ship).clone());
            };
        }
    }
    crate::openciv3::unit_lifecycle::remove_units((*game).clone(), &losses)?;
    Ok(({
        let mut __comprehension_result_1099: Vec<String> = Vec::new();
        let __comprehension_source_1098 = (losses.clone());
        for ship in __comprehension_source_1098.iter().cloned() {
            __comprehension_result_1099.push((ship).name.clone());
        }
        __comprehension_result_1099
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>())
}

// Python: openciv3/turn_phases.py:63
pub(crate) fn end_player_movement(
    mut game: crate::openciv3::game_state::GameState,
    mut owner: i64,
    mut rng: rt::Random,
) -> rt::Result<MovementEnd> {
    let (mut game, mut result): (crate::openciv3::game_state::GameState, MovementEnd) = {
        let __call_1100_0 = game;
        let __call_1100_1 = owner;
        let __call_1100_2 = rng.clone();
        end_player_movement_state(__call_1100_0, __call_1100_1, __call_1100_2)
    }?;
    Ok(result)
}

/// Commit worker contributions, resolve shipwrecks, and end movement once.
// Python: openciv3/turn_phases.py:68
pub(crate) fn end_player_movement_state(
    mut game: crate::openciv3::game_state::GameState,
    mut owner: i64,
    mut rng: rt::Random,
) -> rt::Result<(crate::openciv3::game_state::GameState, MovementEnd)> {
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, owner)?;
    if (player).has_played_current_turn {
        return Err("Player movement phase already ended".to_string().into());
    }
    let mut completed: Vec<crate::openciv3::worker_jobs::JobCompletion> = vec![];
    for mut unit in (&(game).units).iter().cloned().collect::<Vec<_>>() {
        if ((unit).owner == owner) {
            let mut result: Option<crate::openciv3::worker_jobs::JobCompletion> =
                crate::openciv3::worker_jobs::advance_worker(&game, unit)?;
            if (result).is_some() {
                {
                    completed.push((*(result).as_ref().ok_or("expected a value")?).clone());
                };
            }
        }
    }
    let mut shipwrecks: Vec<String> = _sink_exposed_ships(&game, owner, rng.clone())?;
    {
        let __index = rt::index(game.players.len(), owner)?;
        game.players
            .get_mut(__index)
            .ok_or("missing record")?
            .has_played_current_turn = true;
    }
    Ok((
        game,
        MovementEnd {
            jobs: (completed).iter().cloned().collect::<Vec<_>>(),
            shipwrecks: shipwrecks,
        },
    ))
}

// Python: openciv3/turn_phases.py:84
pub(crate) fn advance_economic_round(
    mut game: crate::openciv3::game_state::GameState,
    mut rng: rt::Random,
    year: &Option<i64>,
) -> rt::Result<Vec<PlayerRound>> {
    let (mut game, mut reports): (crate::openciv3::game_state::GameState, Vec<PlayerRound>) = {
        let __call_1101_0 = game;
        let __call_1101_1 = rng.clone();
        let __call_1101_2 = year;
        advance_economic_round_state(__call_1101_0, __call_1101_1, __call_1101_2)
    }?;
    Ok(reports)
}

/// Run one completed round's economy and reset units for the next movement.
///
/// The turn controller supplies movement; victory remains a pending phase.
/// The scenario calendar supplies the year unless explicitly overridden.
// Python: openciv3/turn_phases.py:89
pub(crate) fn advance_economic_round_state(
    mut game: crate::openciv3::game_state::GameState,
    mut rng: rt::Random,
    year: &Option<i64>,
) -> rt::Result<(crate::openciv3::game_state::GameState, Vec<PlayerRound>)> {
    for mut player in (&(game).players).iter() {
        let mut skip_first: bool = (((game).turn == 0i64)
            && (crate::openciv3::players::Player__barbarian(player)? || (player).skip_first_turn));
        if ((player).included
            && (!((player).defeated) && (!(skip_first) && !((player).has_played_current_turn))))
        {
            return Err(
                "All active movement phases must end before the economic round"
                    .to_string()
                    .into(),
            );
        }
    }
    let mut next_year: i64 = (if (year).is_none() {
        (crate::openciv3::calendar::Calendar__date(
            &(crate::openciv3::scenario_model::ScenarioOptions__calendar(
                &(&(game).scenario).options,
            )?),
            ((game).turn).checked_add(1i64).ok_or("integer overflow")?,
        )?)
        .year
    } else {
        (*((*year).clone()).as_ref().ok_or("expected a value")?).clone()
    });
    let mut barbarians: Vec<crate::openciv3::units::Unit> = {
        let __call_1102_0 = game.clone();
        let __call_1102_1 = rng.clone();
        crate::openciv3::barbarian_spawning::spawn_barbarians(__call_1102_0, __call_1102_1)
    }?;
    crate::openciv3::victory::score_victory_locations(&game)?;
    game.turn = ((game).turn).checked_add(1i64).ok_or("integer overflow")?;
    game.year = next_year;
    let mut reports: Vec<PlayerRound> = vec![];
    let mut workers: std::collections::BTreeSet<i64> =
        crate::civ3_ai::production_ai::worker_production_types(&game)?;
    for mut player in crate::openciv3::game_state::GameState__players_in_order(&game)? {
        if (!((player).included) || (player).defeated) {
            continue;
        }
        let mut cities: Vec<crate::openciv3::cities::City> = {
            let mut __comprehension_result_1104: Vec<crate::openciv3::cities::City> = Vec::new();
            let __comprehension_source_1103 = ((game).cities.clone());
            for city in __comprehension_source_1103.iter().cloned() {
                if ((city).owner == (player).civilization) {
                    __comprehension_result_1104.push(city.clone());
                }
            }
            __comprehension_result_1104
        };
        let mut created_units: Vec<i64> = {
            let mut __comprehension_result_1106: Vec<i64> = Vec::new();
            let __comprehension_source_1105 =
                (crate::openciv3::starting_bonus::spawn_starting_bonus(
                    &game,
                    (player).civilization,
                )?);
            for unit in __comprehension_source_1105.iter().cloned() {
                __comprehension_result_1106.push((unit).id);
            }
            __comprehension_result_1106
        };
        if crate::openciv3::players::Player__barbarian(&player)? {
            {
                let __values = {
                    let mut __comprehension_result_1108: Vec<i64> = Vec::new();
                    let __comprehension_source_1107 = (barbarians.clone());
                    for unit in __comprehension_source_1107.iter().cloned() {
                        __comprehension_result_1108.push((unit).id);
                    }
                    __comprehension_result_1108
                };
                created_units.extend(__values);
            };
        }
        let mut corruption: indexmap::IndexMap<i64, f64> =
            crate::openciv3::corruption::corruption_levels(&game)?;
        let mut hydro: crate::openciv3::hydrology::Hydrology =
            crate::openciv3::hydrology::Hydrology__from_world(&(game).world)?;
        let mut network: crate::openciv3::trade_network::TradeNetwork =
            crate::openciv3::trade_network::TradeNetwork____post_init__(
                crate::openciv3::trade_network::TradeNetwork {
                    game: game.clone(),
                    owner: Some((player).civilization),
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
            )?;
        for mut city in (cities).iter().cloned() {
            city.pop_rush_unhappiness_turns = (0i64).max(
                ((city).pop_rush_unhappiness_turns)
                    .checked_sub(1i64)
                    .ok_or("integer overflow")?,
            );
            {
                let __call_1109_0 = &(game.clone());
                let __call_1109_1 = city.clone();
                let __call_1109_2 = (corruption)
                    .get(&((city).id))
                    .ok_or("missing dict key")?
                    .clone();
                let __call_1109_3 = Some(
                    crate::openciv3::trade_network::TradeNetwork__luxury_count(&network, &city)?,
                );
                let __call_1109_4 = &(Some(hydro.clone()));
                let __call_1109_5 = &(Some(true));
                crate::openciv3::citizen_moods::recalculate_moods(
                    __call_1109_0,
                    __call_1109_1,
                    __call_1109_2,
                    __call_1109_3,
                    __call_1109_4,
                    __call_1109_5,
                )
            }?;
        }
        let mut treasury: crate::openciv3::treasury::TreasuryUpdate = {
            let __call_1110_0 = &game;
            let __call_1110_1 = player.clone();
            let __call_1110_2 = rng.clone();
            crate::openciv3::treasury::settle_treasury(__call_1110_0, __call_1110_1, __call_1110_2)
        }?;
        let (mut player, mut discovery): (crate::openciv3::players::Player, Option<i64>) = {
            let __call_1111_0 = &game;
            let __call_1111_1 = player.clone();
            let __call_1111_2 = Some((treasury).science_income);
            crate::openciv3::research::advance_research_result(
                __call_1111_0,
                __call_1111_1,
                __call_1111_2,
            )
        }?;
        {
            let __index = rt::index(game.players.len(), (player).civilization)?;
            game.players[__index] = player.clone();
        }
        let mut expanded: Vec<i64> = vec![];
        let mut population: Vec<(i64, i64)> = vec![];
        let mut created_buildings: Vec<(i64, i64)> = vec![];
        let mut destroyed: Vec<i64> = vec![];
        let mut destroyed_names: Vec<String> = vec![];
        for mut city in cities {
            if crate::openciv3::city_culture::advance_city_culture(&game, city.clone())? {
                {
                    expanded.push((city).id);
                };
            }
            let (mut city, mut change): (crate::openciv3::cities::City, i64) =
                crate::openciv3::city_growth::advance_city_growth_result(
                    game.clone(),
                    city.clone(),
                    Some(hydro.clone()),
                )?;
            let mut city_index: i64 = (&({
                let mut __comprehension_result_1113: Vec<i64> = Vec::new();
                let __comprehension_source_1112 = (((game).cities.clone())
                    .into_iter()
                    .enumerate()
                    .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                    .collect::<Vec<_>>());
                for (index, candidate) in __comprehension_source_1112.iter().cloned() {
                    if ((candidate).id == (city).id) {
                        __comprehension_result_1113.push(index);
                    }
                }
                __comprehension_result_1113
            }))
                .iter()
                .next()
                .cloned()
                .ok_or("StopIteration")?;
            {
                let __index = rt::index(game.cities.len(), city_index)?;
                game.cities[__index] = city.clone();
            }
            if (change != 0i64) {
                {
                    population.push(((city).id, change));
                };
            }
            if (crate::openciv3::cities::City__size(&city)? == 0i64) {
                crate::openciv3::city_lifecycle::destroy_city(&game, &city, false)?;
                {
                    destroyed.push((city).id);
                };
                {
                    destroyed_names.push((city).name.clone());
                };
                continue;
            }
            corruption = crate::openciv3::corruption::corruption_levels(&game)?;
            let mut finished: bool = false;
            if (&(city).producing_unit).is_some() {
                let mut unit: Option<crate::openciv3::units::Unit> =
                    crate::openciv3::city_production::advance_unit_production(
                        &game,
                        city.clone(),
                        (corruption)
                            .get(&((city).id))
                            .ok_or("missing dict key")?
                            .clone(),
                        &(Some(hydro.clone())),
                    )?;
                if (unit).is_some() {
                    {
                        created_units.push(
                            ((*(unit.clone()).as_ref().ok_or("expected a value")?).clone()).id,
                        );
                    };
                    finished = true;
                }
            } else {
                if (&(city).producing_building).is_some() {
                    let mut building: Option<crate::openciv3::cities::CityBuilding> =
                        crate::openciv3::city_production::advance_building_production(
                            game.clone(),
                            city.clone(),
                            (corruption)
                                .get(&((city).id))
                                .ok_or("missing dict key")?
                                .clone(),
                            &(Some(hydro.clone())),
                        )?;
                    if (building).is_some() {
                        {
                            created_buildings.push((
                                (city).id,
                                ((*(building).as_ref().ok_or("expected a value")?).clone())
                                    .building,
                            ));
                        };
                        finished = true;
                    }
                }
            }
            if (finished
                || ((&(city).producing_unit).is_none()
                    && ((&(city).producing_building).is_none()
                        && (&(city).producing_inflow).is_none())))
            {
                crate::civ3_ai::production_ai::ProductionChoice__apply(
                    &({
                        let __call_1114_0 = &game;
                        let __call_1114_1 = &city;
                        let __call_1114_2 = (corruption)
                            .get(&((city).id))
                            .ok_or("missing dict key")?
                            .clone();
                        let __call_1114_3 = rng.clone();
                        let __call_1114_4 = &workers;
                        let __call_1114_default_5 = None;
                        let __call_1114_default_6 = None;
                        crate::civ3_ai::production_ai::choose_production(
                            __call_1114_0,
                            __call_1114_1,
                            __call_1114_2,
                            __call_1114_3,
                            __call_1114_4,
                            __call_1114_default_5,
                            __call_1114_default_6,
                        )
                    }?),
                    &city,
                )?;
            }
        }
        crate::openciv3::history::record_player_history(&game, (player).civilization)?;
        if (match ((player).golden_age_turns.clone()) {
            Some(value) => value,
            None => 0i64,
        } != 0i64)
        {
            player.golden_age_turns = Some(
                ((*((player).golden_age_turns.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone())
                .checked_sub(1i64)
                .ok_or("integer overflow")?,
            );
        }
        {
            reports.push(PlayerRound {
                owner: (player).civilization,
                treasury: treasury,
                discovery: discovery.clone(),
                expanded: (expanded).iter().cloned().collect::<Vec<_>>(),
                population_changes: (population).iter().cloned().collect::<Vec<_>>(),
                units_created: (created_units).iter().cloned().collect::<Vec<_>>(),
                buildings_created: (created_buildings).iter().cloned().collect::<Vec<_>>(),
                cities_destroyed: (destroyed).iter().cloned().collect::<Vec<_>>(),
                destroyed_city_names: (destroyed_names).iter().cloned().collect::<Vec<_>>(),
            });
        };
    }
    for mut player in (game).players.clone() {
        crate::openciv3::unit_turns::begin_player_unit_turn(
            &game,
            (player).civilization,
            false,
            &None,
        )?;
        {
            let __index = rt::index(game.players.len(), (player).civilization)?;
            game.players
                .get_mut(__index)
                .ok_or("missing record")?
                .has_played_current_turn = false;
        }
    }
    Ok((game, (reports).iter().cloned().collect::<Vec<_>>()))
}
