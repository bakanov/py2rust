use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct GameState {
    pub(crate) scenario: crate::openciv3::scenario_model::ScenarioDefinition,
    pub(crate) world: crate::openciv3::world::WorldMap,
    pub(crate) players: Vec<crate::openciv3::players::Player>,
    pub(crate) units: Vec<crate::openciv3::units::Unit>,
    pub(crate) cities: Vec<crate::openciv3::cities::City>,
    pub(crate) ownership: indexmap::IndexMap<(i64, i64), i64>,
    pub(crate) visibility: indexmap::IndexMap<i64, crate::openciv3::visibility::TileKnowledge>,
    pub(crate) great_wonders_built: std::collections::BTreeSet<i64>,
    pub(crate) diplomacy: crate::openciv3::diplomacy::Diplomacy,
    pub(crate) human_player: i64,
    pub(crate) difficulty: i64,
    pub(crate) seed: i64,
    pub(crate) year: i64,
    pub(crate) turn: i64,
    pub(crate) next_unit_id: i64,
    pub(crate) cleared_forests: std::collections::BTreeSet<(i64, i64)>,
    pub(crate) next_city_id: i64,
    pub(crate) barbarian_activity: i64,
    pub(crate) history: indexmap::IndexMap<i64, Vec<crate::openciv3::history::HistoryRecord>>,
    pub(crate) game_over: bool,
    pub(crate) winner: Option<crate::openciv3::victory::VictoryResult>,
    pub(crate) player_order: Vec<i64>,
}

// Python: openciv3/game_state.py:44
pub(crate) fn GameState__players_in_order(
    self_: &GameState,
) -> rt::Result<Vec<crate::openciv3::players::Player>> {
    if !(((&(self_).player_order).len() as i64) != 0i64) {
        return Ok((self_).players.clone());
    }
    let mut listed: std::collections::BTreeSet<i64> = ((self_).player_order.clone())
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>();
    Ok({
        let mut __left: Vec<crate::openciv3::players::Player> = {
            let mut __comprehension_result_66: Vec<crate::openciv3::players::Player> = Vec::new();
            let __comprehension_source_65 = ((self_).player_order.clone());
            for owner in __comprehension_source_65.iter().cloned() {
                __comprehension_result_66.push(rt::at(&(self_).players, owner)?);
            }
            __comprehension_result_66
        };
        let __right: Vec<crate::openciv3::players::Player> = {
            let mut __comprehension_result_68: Vec<crate::openciv3::players::Player> = Vec::new();
            let __comprehension_source_67 = ((self_).players.clone());
            for player in __comprehension_source_67.iter().cloned() {
                if {
                    let __needle = (player).civilization;
                    let __container = &listed;
                    !__container.contains(&__needle)
                } {
                    __comprehension_result_68.push(player.clone());
                }
            }
            __comprehension_result_68
        };
        __left.extend(__right);
        __left
    })
}

// Python: openciv3/game_state.py:51
pub(crate) fn GameState____post_init__(mut self_: GameState) -> rt::Result<GameState> {
    for mut player in (self_).players.clone() {
        if !(crate::openciv3::players::Player__barbarian(&player)?) {
            ((self_).history)
                .entry((player).civilization)
                .or_insert(vec![])
                .clone();
        }
    }
    self_.next_city_id = ((self_).next_city_id).max(
        ('__extreme: {
            let __values = &({
                let mut __comprehension_result_70: Vec<i64> = Vec::new();
                let __comprehension_source_69 = ((self_).cities.clone());
                for city in __comprehension_source_69.iter().cloned() {
                    __comprehension_result_70.push((city).id);
                }
                __comprehension_result_70
            });
            let mut __items = __values.iter();
            let Some(mut __best) = __items.next() else {
                break '__extreme (1i64).checked_neg().ok_or("integer overflow")?;
            };
            let mut __best_key = {
                let extreme_item = (*__best).clone();
                extreme_item
            };
            for __candidate in __items {
                let __key = {
                    let extreme_item = (*__candidate).clone();
                    extreme_item
                };
                if __key > __best_key {
                    __best = __candidate;
                    __best_key = __key;
                }
            }
            (*__best).clone()
        })
        .checked_add(1i64)
        .ok_or("integer overflow")?,
    );
    self_.next_unit_id = ((self_).next_unit_id).max(
        ('__extreme: {
            let __values = &({
                let mut __comprehension_result_72: Vec<i64> = Vec::new();
                let __comprehension_source_71 = ((self_).units.clone());
                for unit in __comprehension_source_71.iter().cloned() {
                    __comprehension_result_72.push((unit).id);
                }
                __comprehension_result_72
            });
            let mut __items = __values.iter();
            let Some(mut __best) = __items.next() else {
                break '__extreme (1i64).checked_neg().ok_or("integer overflow")?;
            };
            let mut __best_key = {
                let extreme_item = (*__best).clone();
                extreme_item
            };
            for __candidate in __items {
                let __key = {
                    let extreme_item = (*__candidate).clone();
                    extreme_item
                };
                if __key > __best_key {
                    __best = __candidate;
                    __best_key = __key;
                }
            }
            (*__best).clone()
        })
        .checked_add(1i64)
        .ok_or("integer overflow")?,
    );
    Ok(self_.clone())
}

// Python: openciv3/game_state.py:58
pub(crate) fn GameState__allocate_city_id(mut self_: GameState) -> rt::Result<i64> {
    self_.next_city_id = ((self_).next_city_id).max(
        ('__extreme: {
            let __values = &({
                let mut __comprehension_result_74: Vec<i64> = Vec::new();
                let __comprehension_source_73 = ((self_).cities.clone());
                for city in __comprehension_source_73.iter().cloned() {
                    __comprehension_result_74.push((city).id);
                }
                __comprehension_result_74
            });
            let mut __items = __values.iter();
            let Some(mut __best) = __items.next() else {
                break '__extreme (1i64).checked_neg().ok_or("integer overflow")?;
            };
            let mut __best_key = {
                let extreme_item = (*__best).clone();
                extreme_item
            };
            for __candidate in __items {
                let __key = {
                    let extreme_item = (*__candidate).clone();
                    extreme_item
                };
                if __key > __best_key {
                    __best = __candidate;
                    __best_key = __key;
                }
            }
            (*__best).clone()
        })
        .checked_add(1i64)
        .ok_or("integer overflow")?,
    );
    let mut result: i64 = (self_).next_city_id;
    self_.next_city_id = ((self_).next_city_id)
        .checked_add(1i64)
        .ok_or("integer overflow")?;
    Ok(result)
}

// Python: openciv3/game_state.py:64
pub(crate) fn GameState__allocate_unit_id(mut self_: GameState) -> rt::Result<i64> {
    self_.next_unit_id = ((self_).next_unit_id).max(
        ('__extreme: {
            let __values = &({
                let mut __comprehension_result_76: Vec<i64> = Vec::new();
                let __comprehension_source_75 = ((self_).units.clone());
                for unit in __comprehension_source_75.iter().cloned() {
                    __comprehension_result_76.push((unit).id);
                }
                __comprehension_result_76
            });
            let mut __items = __values.iter();
            let Some(mut __best) = __items.next() else {
                break '__extreme (1i64).checked_neg().ok_or("integer overflow")?;
            };
            let mut __best_key = {
                let extreme_item = (*__best).clone();
                extreme_item
            };
            for __candidate in __items {
                let __key = {
                    let extreme_item = (*__candidate).clone();
                    extreme_item
                };
                if __key > __best_key {
                    __best = __candidate;
                    __best_key = __key;
                }
            }
            (*__best).clone()
        })
        .checked_add(1i64)
        .ok_or("integer overflow")?,
    );
    let mut result: i64 = (self_).next_unit_id;
    self_.next_unit_id = ((self_).next_unit_id)
        .checked_add(1i64)
        .ok_or("integer overflow")?;
    Ok(result)
}

// Python: openciv3/game_state.py:71
pub(crate) fn GameState__from_scenario(
    mut definition: crate::openciv3::scenario_model::ScenarioDefinition,
) -> rt::Result<GameState> {
    if (&(definition).world).is_none() {
        definition = crate::openciv3::new_game__generate_scenario_map(&definition)?;
    }
    let mut world_map: Option<crate::openciv3::world::WorldMap> = (definition).world.clone();
    if !((world_map).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    let mut scenario: crate::openciv3::scenario_model::ScenarioDefinition = {
        let mut __replacement = (definition.clone()).clone();
        __replacement.portrait_paths = (&(definition).portrait_paths).clone();
        __replacement
    };
    let mut players: Vec<crate::openciv3::players::Player> =
        crate::openciv3::players::initialize_players(&scenario)?;
    let mut diplomacy: crate::openciv3::diplomacy::Diplomacy =
        crate::openciv3::diplomacy::initialize_diplomacy(&(scenario).options, players.clone())?;
    let mut units: Vec<crate::openciv3::units::Unit> =
        crate::openciv3::units::initialize_units(&scenario)?;
    let mut cities: Vec<crate::openciv3::cities::City> =
        crate::openciv3::cities::initialize_cities(&scenario)?;
    let mut world: crate::openciv3::world::WorldMap =
        crate::openciv3::city_roads::connect_city_roads(
            &((*(world_map).as_ref().ok_or("expected a value")?).clone()),
            &cities,
            &players,
            &(scenario).rules,
        )?;
    scenario.world = Some(world.clone());
    let mut rates: indexmap::IndexMap<i64, i64> = crate::openciv3::building_effects::culture_rates(
        &cities,
        &players,
        &world,
        &(scenario).rules,
        (&(scenario).options).start_year,
    )?;
    let mut ownership: indexmap::IndexMap<(i64, i64), i64> =
        crate::openciv3::borders::calculate_ownership(&world, &cities, 13i64, &rates)?;
    crate::openciv3::citizen_allocation::allocate_citizens(
        &scenario, &cities, &players, &ownership, &None,
    )?;
    let mut visibility: indexmap::IndexMap<i64, crate::openciv3::visibility::TileKnowledge> = {
        let mut __comprehension_result_78: indexmap::IndexMap<
            i64,
            crate::openciv3::visibility::TileKnowledge,
        > = indexmap::IndexMap::new();
        let __comprehension_source_77 = (players.clone());
        for player in __comprehension_source_77.iter().cloned() {
            {
                let (__key, __value) = (
                    (player).civilization,
                    crate::openciv3::visibility::TileKnowledge {
                        known: {
                            let mut __result = std::collections::BTreeSet::new();
                            for __item in vec![].into_iter() {
                                __result.insert(__item);
                            }
                            __result
                        },
                        visible: {
                            let mut __result = std::collections::BTreeSet::new();
                            for __item in vec![].into_iter() {
                                __result.insert(__item);
                            }
                            __result
                        },
                        frontier: {
                            let mut __result = std::collections::BTreeSet::new();
                            for __item in vec![].into_iter() {
                                __result.insert(__item);
                            }
                            __result
                        },
                        known_overlays: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                        known_ruins: {
                            let mut __result = std::collections::BTreeSet::new();
                            for __item in vec![].into_iter() {
                                __result.insert(__item);
                            }
                            __result
                        },
                        exploration_targets: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                        fully_explored_oceans: false,
                        known_terrain: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                    },
                );
                __comprehension_result_78.insert(__key, __value);
            }
        }
        __comprehension_result_78
    };
    let mut revealed: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_80: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_79 = ((world).tiles.clone());
        for tile in __comprehension_source_79.iter().cloned() {
            if ((&(scenario).options).map_visible || ((tile).fog_of_war != 0i64)) {
                __comprehension_result_80.insert(((tile).x, (tile).y));
            }
        }
        __comprehension_result_80
    };
    if (((revealed).len() as i64) != 0i64) {
        for mut knowledge in (visibility.clone()).values().cloned().collect::<Vec<_>>() {
            crate::openciv3::visibility::TileKnowledge__reveal(knowledge, &world, &revealed)?;
        }
    }
    visibility = crate::openciv3::visibility::update_visibility(
        &world,
        &cities,
        &units,
        &(scenario).rules,
        &ownership,
        visibility,
        None,
        &None,
    )?;
    let mut state: GameState = GameState____post_init__(GameState {
        scenario: scenario.clone(),
        world: world,
        players: players.clone(),
        units: units,
        cities: cities.clone(),
        ownership: ownership,
        visibility: visibility,
        great_wonders_built: crate::openciv3::cities::built_great_wonders(&cities, &scenario)?,
        diplomacy: diplomacy,
        human_player: (&({
            let mut __comprehension_result_82: Vec<i64> = Vec::new();
            let __comprehension_source_81 = (players.clone());
            for player in __comprehension_source_81.iter().cloned() {
                if (player).human {
                    __comprehension_result_82.push((player).civilization);
                }
            }
            __comprehension_result_82
        }))
            .iter()
            .next()
            .cloned()
            .ok_or("StopIteration")?,
        difficulty: (&({
            let mut __comprehension_result_84: Vec<i64> = Vec::new();
            let __comprehension_source_83 = (((scenario).difficulties.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>());
            for (i, level) in __comprehension_source_83.iter().cloned() {
                if (AsRef::<str>::as_ref(&(level).name)
                    == AsRef::<str>::as_ref(&(scenario).selected_difficulty))
                {
                    __comprehension_result_84.push(i);
                }
            }
            __comprehension_result_84
        }))
            .iter()
            .next()
            .cloned()
            .ok_or("StopIteration")?,
        seed: (scenario).seed,
        year: (&(scenario).options).start_year,
        turn: 0i64,
        next_unit_id: 0i64,
        cleared_forests: {
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        },
        next_city_id: 0i64,
        barbarian_activity: 1i64,
        history: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
        game_over: false,
        winner: None,
        player_order: vec![],
    })?;
    GameState__validate(&state)?;

    crate::openciv3::citizen_moods::recalculate_all_moods(&state, &(Some(false)))?;
    Ok(state)
}

// Python: openciv3/game_state.py:105
pub(crate) fn GameState__validate(self_: &GameState) -> rt::Result<()> {
    if ((((((self_).player_order.clone())
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>())
    .len() as i64)
        != ((&(self_).player_order).len() as i64))
        || ({
            let mut __comprehension_result_86: Vec<bool> = Vec::new();
            let __comprehension_source_85 = ((self_).player_order.clone());
            for owner in __comprehension_source_85.iter().cloned() {
                __comprehension_result_86.push(
                    !({
                        let __compare_0 = 0i64;
                        let __compare_1 = owner;
                        if (__compare_0 <= __compare_1) {
                            let __compare_2 = ((&(self_).players).len() as i64);
                            (__compare_1 < __compare_2)
                        } else {
                            false
                        }
                    }),
                );
            }
            __comprehension_result_86
        })
        .into_iter()
        .any(|__value| __value))
    {
        return Err("Invalid saved player order".to_string().into());
    }
    if ({
        let mut __comprehension_result_88: Vec<i64> = Vec::new();
        let __comprehension_source_87 = ((self_).players.clone());
        for player in __comprehension_source_87.iter().cloned() {
            __comprehension_result_88.push((player).civilization);
        }
        __comprehension_result_88
    } != ((0i64..((&(self_).players).len() as i64)).collect::<Vec<i64>>())
        .iter()
        .cloned()
        .collect::<Vec<_>>())
    {
        return Err("Player indices must match civilization indices"
            .to_string()
            .into());
    }
    if ({
        let mut __comprehension_result_90: Vec<i64> = Vec::new();
        let __comprehension_source_89 = ((self_).players.clone());
        for player in __comprehension_source_89.iter().cloned() {
            if (player).human {
                __comprehension_result_90.push((player).civilization);
            }
        }
        __comprehension_result_90
    } != vec![(self_).human_player])
    {
        return Err("Game must contain exactly the selected human player"
            .to_string()
            .into());
    }
    let mut winner: Option<crate::openciv3::victory::VictoryResult> = (self_).winner.clone();
    if ((winner).is_some()
        && (!((self_).game_over)
            || (!({
                let __compare_0 = 0i64;
                let __compare_1 =
                    ((*(winner.clone()).as_ref().ok_or("expected a value")?).clone()).owner;
                if (__compare_0 < __compare_1) {
                    let __compare_2 = ((&(self_).players).len() as i64);
                    (__compare_1 < __compare_2)
                } else {
                    false
                }
            }) || (!(({
                let __source = &(self_).players;
                let __key = ((*(winner.clone()).as_ref().ok_or("expected a value")?).clone()).owner;
                &__source[rt::index(__source.len(), __key)?]
            })
            .included)
                || ((((*(winner.clone()).as_ref().ok_or("expected a value")?).clone())
                    .turn
                    .clone())
                .is_some()
                    && !({
                        let __compare_0 = 0i64;
                        let __compare_1 =
                            ((*(winner.clone()).as_ref().ok_or("expected a value")?).clone())
                                .turn
                                .clone();
                        if (__compare_0
                            <= (*(__compare_1).as_ref().ok_or("expected a value")?).clone())
                        {
                            let __compare_2 = (self_).turn;
                            ((*(__compare_1).as_ref().ok_or("expected a value")?).clone()
                                <= __compare_2)
                        } else {
                            false
                        }
                    }))))))
    {
        return Err("Invalid saved victory result".to_string().into());
    }
    if ({
        let mut __comprehension_result_92: Vec<bool> = Vec::new();
        let __comprehension_source_91 = ((self_).players.clone());
        for player in __comprehension_source_91.iter().cloned() {
            __comprehension_result_92
                .push((((player).cities_lost < 0i64) || ((player).victory_points < 0i64)));
        }
        __comprehension_result_92
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err(
            "Conquered city counts and victory points must be nonnegative"
                .to_string()
                .into(),
        );
    }
    if ({
        let mut __comprehension_result_94: Vec<bool> = Vec::new();
        let __comprehension_source_93 = ((self_).players.clone());
        for player in __comprehension_source_93.iter().cloned() {
            __comprehension_result_94.push(((player).anarchy_until < 0i64));
        }
        __comprehension_result_94
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("Anarchy deadlines must be nonnegative".to_string().into());
    }
    let mut units_by_id: indexmap::IndexMap<i64, crate::openciv3::units::Unit> = {
        let mut __comprehension_result_96: indexmap::IndexMap<i64, crate::openciv3::units::Unit> =
            indexmap::IndexMap::new();
        let __comprehension_source_95 = ((self_).units.clone());
        for unit in __comprehension_source_95.iter().cloned() {
            {
                let (__key, __value) = ((unit).id, unit.clone());
                __comprehension_result_96.insert(__key, __value);
            }
        }
        __comprehension_result_96
    };
    if ((((units_by_id).len() as i64) != ((&(self_).units).len() as i64))
        || ({
            let mut __comprehension_result_98: Vec<bool> = Vec::new();
            let __comprehension_source_97 = ((self_).units.clone());
            for unit in __comprehension_source_97.iter().cloned() {
                __comprehension_result_98.push(((unit).id < 0i64));
            }
            __comprehension_result_98
        })
        .into_iter()
        .any(|__value| __value))
    {
        return Err("Unit IDs must be unique and nonnegative".to_string().into());
    }
    let mut cities_by_id: indexmap::IndexMap<i64, crate::openciv3::cities::City> = {
        let mut __comprehension_result_100: indexmap::IndexMap<i64, crate::openciv3::cities::City> =
            indexmap::IndexMap::new();
        let __comprehension_source_99 = ((self_).cities.clone());
        for city in __comprehension_source_99.iter().cloned() {
            {
                let (__key, __value) = ((city).id, city.clone());
                __comprehension_result_100.insert(__key, __value);
            }
        }
        __comprehension_result_100
    };
    if ((((cities_by_id).len() as i64) != ((&(self_).cities).len() as i64))
        || ({
            let mut __comprehension_result_102: Vec<bool> = Vec::new();
            let __comprehension_source_101 = ((self_).cities.clone());
            for city in __comprehension_source_101.iter().cloned() {
                __comprehension_result_102.push(((city).id < 0i64));
            }
            __comprehension_result_102
        })
        .into_iter()
        .any(|__value| __value))
    {
        return Err("City IDs must be unique and nonnegative".to_string().into());
    }
    let mut centers: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_104: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_103 = ((self_).cities.clone());
        for city in __comprehension_source_103.iter().cloned() {
            __comprehension_result_104.insert(((city).x, (city).y));
        }
        __comprehension_result_104
    };
    let mut worked: std::collections::BTreeSet<(i64, i64)> = std::collections::BTreeSet::new();
    for mut city in (&(self_).cities).iter() {
        crate::openciv3::cities::City__validate_production(
            &((*city).clone()),
            ((&(&(&(self_).scenario).rules).units).len() as i64),
            ((&(&(&(self_).scenario).rules).buildings).len() as i64),
        )?;
        if ((crate::openciv3::cities::City__size(city)?) != 0
            && (((self_).ownership.clone())
                .get(&(((city).x, (city).y)))
                .cloned()
                != Some((city).id)))
        {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "City ".to_string(),
                    ((city).id).to_string(),
                    " does not own its center".to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        for mut resident in (&(city).residents).iter() {
            if ((resident).city != (city).id) {
                return Err("Resident refers to the wrong city".to_string().into());
            }
            let mut point: Option<(i64, i64)> = (resident).tile_worked.clone();
            if (point).is_none() {
                if ({
                    let __source = &(&(&(self_).scenario).rules).citizens;
                    let __key = (resident).citizen_type;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .default_citizen
                {
                    return Err("Default citizen has no assigned tile".to_string().into());
                }
                continue;
            }
            if (match (point.clone()) {
                Some(__value) => {
                    let __needle = __value;
                    let __container = &worked;
                    __container.contains(&__needle)
                }
                None => false,
            } || match (point.clone()) {
                Some(__value) => {
                    let __needle = __value;
                    let __container = &centers;
                    __container.contains(&__needle)
                }
                None => false,
            }) {
                return Err("Worked tile is duplicated or contains a city"
                    .to_string()
                    .into());
            }
            let mut owner: Option<i64> = ((self_).ownership.clone())
                .get(&((*(point.clone()).as_ref().ok_or("expected a value")?).clone()))
                .cloned();
            if ((owner).is_none()
                || (match (owner.clone()) {
                    Some(__value) => {
                        let __needle = __value;
                        let __container = &cities_by_id;
                        !__container.contains_key(&__needle)
                    }
                    None => true,
                } || (((cities_by_id)
                    .get(&((*(owner.clone()).as_ref().ok_or("expected a value")?).clone()))
                    .ok_or("missing dict key")?)
                .owner
                    != (city).owner)))
            {
                return Err("Resident works foreign or unowned territory"
                    .to_string()
                    .into());
            }
            {
                worked.insert((*(point).as_ref().ok_or("expected a value")?).clone());
            };
        }
    }
    for mut unit in (&(self_).units).iter() {
        if (&(unit).transported_by).is_some() {
            let mut transport: Option<crate::openciv3::units::Unit> = (units_by_id.clone())
                .get(
                    &((*((unit).transported_by.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone()),
                )
                .cloned();
            if ((transport).is_none()
                || ((((*(transport.clone()).as_ref().ok_or("expected a value")?).clone()).id
                    == (unit).id)
                    || ((((*(transport.clone()).as_ref().ok_or("expected a value")?).clone())
                        .owner
                        != (unit).owner)
                        || ((
                            ((*(transport.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                            ((*(transport.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                        ) != ((unit).x, (unit).y)))))
            {
                return Err("Unit has invalid transport reference".to_string().into());
            }
            let mut seen: std::collections::BTreeSet<i64> = {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![(unit).id].into_iter() {
                    __result.insert(__item);
                }
                __result
            };
            let mut ancestor: crate::openciv3::units::Unit =
                (*(transport).as_ref().ok_or("expected a value")?).clone();
            loop {
                if {
                    let __needle = (ancestor).id;
                    let __container = &seen;
                    __container.contains(&__needle)
                } {
                    return Err("Transport references contain a cycle".to_string().into());
                }
                {
                    seen.insert((ancestor).id);
                };
                if (&(ancestor).transported_by).is_none() {
                    break;
                }
                let mut parent: Option<crate::openciv3::units::Unit> = (units_by_id.clone())
                    .get(
                        &((*((ancestor).transported_by.clone())
                            .as_ref()
                            .ok_or("expected a value")?)
                        .clone()),
                    )
                    .cloned();
                if (parent).is_none() {
                    return Err("Unit has invalid transport reference".to_string().into());
                }
                ancestor = (*(parent).as_ref().ok_or("expected a value")?).clone();
            }
        }
        let mut passengers: i64 = ({
            let mut __comprehension_result_106: Vec<bool> = Vec::new();
            let __comprehension_source_105 = ((self_).units.clone());
            for other in __comprehension_source_105.iter().cloned() {
                __comprehension_result_106
                    .push(((other).transported_by.clone() == Some((unit).id)));
            }
            __comprehension_result_106
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        if (passengers
            > ({
                let __source = &(&(&(self_).scenario).rules).units;
                let __key = (unit).prototype;
                &__source[rt::index(__source.len(), __key)?]
            })
            .capacity)
        {
            return Err("Transport capacity exceeded".to_string().into());
        }
        if (&(unit).escorting).is_some() {
            let mut settler: Option<crate::openciv3::units::Unit> = (units_by_id.clone())
                .get(
                    &((*((unit).escorting.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone()),
                )
                .cloned();
            if ((settler).is_none()
                || ((((*(settler.clone()).as_ref().ok_or("expected a value")?).clone()).owner
                    != (unit).owner)
                    || ((((*(settler.clone()).as_ref().ok_or("expected a value")?).clone())
                        .settler_mission
                        .clone())
                    .is_none()
                        || (((*(((*(settler.clone()).as_ref().ok_or("expected a value")?)
                            .clone())
                        .settler_mission
                        .clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                        .clone())
                        .escort
                        .clone()
                            != Some((unit).id)))))
            {
                return Err("Invalid reciprocal escort assignment".to_string().into());
            }
        }
        if ((&(unit).settler_mission).is_some()
            && (((*((unit).settler_mission.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone())
            .escort
            .clone())
            .is_some())
        {
            let mut escort: Option<crate::openciv3::units::Unit> = (units_by_id.clone())
                .get(
                    &((*(((*((unit).settler_mission.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone())
                    .escort
                    .clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                    .clone()),
                )
                .cloned();
            if ((escort).is_none()
                || ((((*(escort.clone()).as_ref().ok_or("expected a value")?).clone()).owner
                    != (unit).owner)
                    || (((*(escort.clone()).as_ref().ok_or("expected a value")?).clone())
                        .escorting
                        .clone()
                        != Some((unit).id))))
            {
                return Err("Invalid reciprocal escort assignment".to_string().into());
            }
        }
        if (!({
            let __compare_0 = 0i64;
            let __compare_1 = (unit).owner;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = ((&(self_).players).len() as i64);
                (__compare_1 < __compare_2)
            } else {
                false
            }
        }) || (crate::openciv3::world::WorldMap__tile_at(&(self_).world, (unit).x, (unit).y)?)
            .is_none())
        {
            return Err("Unit has invalid ownership or position".to_string().into());
        }
        if {
            let __needle = ((unit).x, (unit).y);
            let __container = &((&(self_).visibility)
                .get(&((unit).owner))
                .ok_or("missing dict key")?)
            .visible;
            !__container.contains(&__needle)
        } {
            return Err("Unit owner cannot see its unit".to_string().into());
        }
    }
    Ok(())
}
