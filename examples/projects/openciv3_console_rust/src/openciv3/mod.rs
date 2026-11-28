pub(crate) mod air_missions;

pub(crate) mod barbarian_spawning;

pub(crate) mod binary;

pub(crate) mod blast;

pub(crate) mod bombardment;

pub(crate) mod borders;

pub(crate) mod building_effects;

pub(crate) mod building_rules;

pub(crate) mod calendar;

pub(crate) mod cities;

pub(crate) mod citizen_allocation;

pub(crate) mod citizen_moods;

pub(crate) mod city_culture;

pub(crate) mod city_economy;

pub(crate) mod city_founding;

pub(crate) mod city_growth;

pub(crate) mod city_lifecycle;

pub(crate) mod city_names;

pub(crate) mod city_production;

pub(crate) mod city_roads;

pub(crate) mod combat;

pub(crate) mod combat_strength;

pub(crate) mod corruption;

pub(crate) mod deal_lifecycle;

pub(crate) mod diplomacy;

pub(crate) mod diplomacy_actions;

pub(crate) mod game_state;

pub(crate) mod global_rules;

pub(crate) mod government_rules;

pub(crate) mod history;

pub(crate) mod hydrology;

pub(crate) mod inflows;

pub(crate) mod json_io;

pub(crate) mod json_rules;

pub(crate) mod naval_risk;

pub(crate) mod pathfinding;

pub(crate) mod player_economy;

pub(crate) mod players;

pub(crate) mod production_cost;

pub(crate) mod production_eligibility;

pub(crate) mod recurring_deals;

pub(crate) mod research;

pub(crate) mod rules;

pub(crate) mod scenario;

pub(crate) mod scenario_model;

pub(crate) mod standalone;

pub(crate) mod starting_bonus;

pub(crate) mod trade_network;

pub(crate) mod trading;

pub(crate) mod treasury;

pub(crate) mod turn_controller;

pub(crate) mod turn_phases;

pub(crate) mod unit_animation;

pub(crate) mod unit_entry;

pub(crate) mod unit_lifecycle;

pub(crate) mod unit_missions;

pub(crate) mod unit_movement;

pub(crate) mod unit_rules;

pub(crate) mod unit_turns;

pub(crate) mod units;

pub(crate) mod victory;

pub(crate) mod visibility;

pub(crate) mod worker_jobs;

pub(crate) mod worker_rules;

pub(crate) mod world;

pub(crate) mod world_elevation;

pub(crate) mod world_size;

pub(crate) mod world_vegetation;

pub(crate) mod yields;

use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum world_biomes__Temperature {
    COOL,
    TEMPERATE,
    WARM,
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum world_shape__Landform {
    ARCHIPELAGO,
    CONTINENTS,
    PANGAEA,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct new_game__PlayerSelection {
    pub(crate) civilization: String,
    pub(crate) difficulty: String,
    pub(crate) opponents: Vec<String>,
    pub(crate) victory_flags: Option<i64>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct world_resources__ResourceTerrain {
    pub(crate) possible_resources: Vec<i64>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct world_starts__StartTerrain {
    pub(crate) allow_cities: bool,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct world_starts__StartLocations {
    pub(crate) points: Vec<(i64, i64)>,
    pub(crate) requested: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct world_generation__WorldSettings {
    pub(crate) size: crate::openciv3::world_size::WorldSize,
    pub(crate) seed: i64,
    pub(crate) landform: world_shape__Landform,
    pub(crate) ocean_percent: i64,
    pub(crate) age: i64,
    pub(crate) climate: crate::openciv3::world_vegetation::Climate,
    pub(crate) temperature: world_biomes__Temperature,
    pub(crate) barbarian_activity: i64,
    pub(crate) workable_rank: Option<i64>,
    pub(crate) camp_rank: Option<i64>,
    pub(crate) max_shape_attempts: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct world_generation__GeneratedWorld {
    pub(crate) world: crate::openciv3::world::WorldMap,
    pub(crate) shape_attempts: i64,
    pub(crate) shape_accepted: bool,
    pub(crate) requested_starts: i64,
}

#[derive(Clone, PartialEq)]
pub(crate) struct world_rivers___RiverGrowth {
    pub(crate) world: crate::openciv3::world::WorldMap,
    pub(crate) random: crate::strategy::random::MapRandom,
    pub(crate) heights: crate::strategy::height_map::HeightMap,
    pub(crate) flags: Vec<i64>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct world_shape__ShapeResult {
    pub(crate) world: crate::openciv3::world::WorldMap,
    pub(crate) attempts: i64,
    pub(crate) accepted: bool,
}

#[derive(Clone, PartialEq)]
pub(crate) struct world_resources___Placement {
    pub(crate) world: crate::openciv3::world::WorldMap,
    pub(crate) resources: Vec<crate::openciv3::rules::Resource>,
    pub(crate) terrains: Vec<world_resources__ResourceTerrain>,
    pub(crate) workable_rank: i64,
    pub(crate) allowed: Vec<std::collections::BTreeSet<i64>>,
    pub(crate) random: crate::strategy::random::MapRandom,
    pub(crate) placed: Vec<i64>,
    pub(crate) continent_sizes: indexmap::IndexMap<i64, i64>,
    pub(crate) order: Vec<i64>,
}

// Python: openciv3/new_game.py:21
pub(crate) fn new_game__select_civilizations(
    definition: &crate::openciv3::scenario_model::ScenarioDefinition,
    selection: &new_game__PlayerSelection,
    mut seed: i64,
) -> rt::Result<Vec<i64>> {
    let mut by_name: indexmap::IndexMap<String, i64> = {
        let mut __comprehension_result_1299: indexmap::IndexMap<String, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_1298 = ((definition).civilizations.clone());
        for c in __comprehension_source_1298.iter().cloned() {
            if (!(crate::openciv3::scenario_model::Civilization__is_barbarian(&c)?) && {
                let __needle = (c).index;
                let __container = &(&(definition).options).allowed_civilizations;
                __container.contains(&__needle)
            }) {
                {
                    let (__key, __value) = ((c).name.clone(), (c).index);
                    __comprehension_result_1299.insert(__key, __value);
                }
            }
        }
        __comprehension_result_1299
    };
    if ({
        let __needle = (selection).civilization.clone();
        let __container = &({
            let mut __comprehension_result_1301: std::collections::BTreeSet<String> =
                std::collections::BTreeSet::new();
            let __comprehension_source_1300 = ((definition).playable.clone());
            for c in __comprehension_source_1300.iter().cloned() {
                __comprehension_result_1301.insert((c).name.clone());
            }
            __comprehension_result_1301
        });
        !__container.contains(&__needle)
    } || {
        let __needle: &str = AsRef::<str>::as_ref(&(selection).civilization);
        let __container = &by_name;
        !__container.contains_key(__needle)
    }) {
        return Err("Select a playable human civilization".to_string().into());
    }
    if {
        let __needle = (selection).difficulty.clone();
        let __container = &({
            let mut __comprehension_result_1303: std::collections::BTreeSet<String> =
                std::collections::BTreeSet::new();
            let __comprehension_source_1302 = ((definition).difficulties.clone());
            for d in __comprehension_source_1302.iter().cloned() {
                __comprehension_result_1303.insert((d).name.clone());
            }
            __comprehension_result_1303
        });
        !__container.contains(&__needle)
    } {
        return Err("Unknown difficulty".to_string().into());
    }
    let mut active: Vec<String> = {
        let mut __comprehension_result_1305: Vec<String> = Vec::new();
        let __comprehension_source_1304 = ((selection).opponents.clone());
        for name in __comprehension_source_1304.iter().cloned() {
            if (name.as_str() != "NONE") {
                __comprehension_result_1305.push(name.clone());
            }
        }
        __comprehension_result_1305
    };
    if (((active).len() as i64)
        .checked_add(1i64)
        .ok_or("integer overflow")?
        > ((by_name).len() as i64))
    {
        return Err(
            "Not enough distinct civilizations for the selected opponents"
                .to_string()
                .into(),
        );
    }
    let mut random: crate::strategy::random::MapRandom =
        crate::strategy::random::MapRandom____post_init__(crate::strategy::random::MapRandom {
            seed: crate::strategy::random::seed32(
                (seed).checked_add(1329i64).ok_or("integer overflow")?,
            )?,
            _values: vec![],
            _index: 0i64,
            _other: 21i64,
        })?;
    let mut selected: Vec<i64> = vec![(by_name)
        .get(&(selection).civilization)
        .ok_or("missing dict key")?
        .clone()];
    let mut available: std::collections::BTreeSet<i64> =
        ((by_name.clone()).values().cloned().collect::<Vec<_>>())
            .into_iter()
            .collect::<std::collections::BTreeSet<_>>();
    for mut name in active {
        let mut civilization: Option<i64> = (by_name.clone()).get(&(name)).cloned();
        if ((civilization).is_none()
            || match (civilization.clone()) {
                Some(__value) => {
                    let __needle = __value;
                    let __container = &selected;
                    __container.contains(&__needle)
                }
                None => false,
            })
        {
            loop {
                civilization = Some({
                    let __minimum = 1i64;
                    let __maximum = ((&(definition).civilizations).len() as i64);
                    if !(-2147483648i64 <= __minimum
                        && __minimum <= __maximum
                        && __maximum <= 2147483647i64)
                    {
                        return Err("Invalid Int32 random range".into());
                    }
                    let __span = __maximum - __minimum;
                    if __span <= 2147483647i64 {
                        let mut __map_random = random.clone();
                        __map_random._index = if __map_random._index < 55 {
                            __map_random._index + 1
                        } else {
                            1
                        };
                        __map_random._other = if __map_random._other < 55 {
                            __map_random._other + 1
                        } else {
                            1
                        };
                        let __sample_index = __map_random._index as usize;
                        let mut __value = (__map_random._values[__sample_index]
                            - __map_random._values[__map_random._other as usize]
                            + 2147483648i64)
                            .rem_euclid(4294967296i64)
                            - 2147483648i64;
                        if __value == 2147483647i64 {
                            __value -= 1;
                        }
                        if __value < 0 {
                            __value += 2147483647i64;
                        }
                        __map_random._values[__sample_index] = __value;
                        random = __map_random;
                        ((__value as f64) * (1.0 / 2147483647.0) * (__span as f64)) as i64
                            + __minimum
                    } else {
                        let mut __map_random = random.clone();
                        __map_random._index = if __map_random._index < 55 {
                            __map_random._index + 1
                        } else {
                            1
                        };
                        __map_random._other = if __map_random._other < 55 {
                            __map_random._other + 1
                        } else {
                            1
                        };
                        let __sample_index = __map_random._index as usize;
                        let mut __value = (__map_random._values[__sample_index]
                            - __map_random._values[__map_random._other as usize]
                            + 2147483648i64)
                            .rem_euclid(4294967296i64)
                            - 2147483648i64;
                        if __value == 2147483647i64 {
                            __value -= 1;
                        }
                        if __value < 0 {
                            __value += 2147483647i64;
                        }
                        __map_random._values[__sample_index] = __value;
                        random = __map_random;
                        let __first = __value;
                        let mut __map_random = random.clone();
                        __map_random._index = if __map_random._index < 55 {
                            __map_random._index + 1
                        } else {
                            1
                        };
                        __map_random._other = if __map_random._other < 55 {
                            __map_random._other + 1
                        } else {
                            1
                        };
                        let __sample_index = __map_random._index as usize;
                        let mut __value = (__map_random._values[__sample_index]
                            - __map_random._values[__map_random._other as usize]
                            + 2147483648i64)
                            .rem_euclid(4294967296i64)
                            - 2147483648i64;
                        if __value == 2147483647i64 {
                            __value -= 1;
                        }
                        if __value < 0 {
                            __value += 2147483647i64;
                        }
                        __map_random._values[__sample_index] = __value;
                        random = __map_random;
                        let __second = if __value % 2 == 0 { -__first } else { __first };
                        let __scaled = ((__second as f64) + 2147483646.0) / 4294967293.0;
                        ((__scaled * (__span as f64)) as i64) + __minimum
                    }
                });
                if (match (civilization.clone()) {
                    Some(__value) => {
                        let __needle = __value;
                        let __container = &available;
                        __container.contains(&__needle)
                    }
                    None => false,
                } && match (civilization.clone()) {
                    Some(__value) => {
                        let __needle = __value;
                        let __container = &selected;
                        !__container.contains(&__needle)
                    }
                    None => true,
                }) {
                    break;
                }
            }
        }
        {
            selected.push((*(civilization).as_ref().ok_or("expected a value")?).clone());
        };
    }
    Ok((selected).iter().cloned().collect::<Vec<_>>())
}

// Python: openciv3/new_game.py:47
pub(crate) fn new_game__initialize_generated_game(
    definition: &crate::openciv3::scenario_model::ScenarioDefinition,
    settings: &world_generation__WorldSettings,
    generated: &world_generation__GeneratedWorld,
    selection: &new_game__PlayerSelection,
) -> rt::Result<crate::openciv3::game_state::GameState> {
    world_generation__WorldSettings__validate(settings)?;
    let mut selected: Vec<i64> =
        new_game__select_civilizations(definition, selection, (&(generated).world).seed)?;
    if (((&(selection).opponents).len() as i64)
        .checked_add(1i64)
        .ok_or("integer overflow")?
        > (&(settings).size).civilization_count)
    {
        return Err("More opponent slots than this world supports"
            .to_string()
            .into());
    }
    let mut world: crate::openciv3::world::WorldMap = (generated).world.clone();
    if (!(world_generation__GeneratedWorld__complete(generated)?)
        || (((&(world).starts).len() as i64) < ((selected).len() as i64)))
    {
        return Err("Map generation could not place all starting locations"
            .to_string()
            .into());
    }
    if (!((world).units.clone()).is_empty() || !((world).cities.clone()).is_empty()) {
        return Err("Generated-game setup requires an unpopulated world"
            .to_string()
            .into());
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (definition).rules.clone();
    if ((((&(rules).global_rules).len() as i64) != 1i64)
        || (!(((&(rules).governments).len() as i64) != 0i64)
            || (((&(rules).experience_levels).len() as i64) < 2i64)))
    {
        return Err(
            "Generated-game setup needs global, government and experience rules"
                .to_string()
                .into(),
        );
    }
    let mut government: i64 = {
        let __find_source_1306 = ((rules).governments.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>();
        let mut __find_result_1306: i64 = 0i64;
        for (i, g) in __find_source_1306.iter().cloned() {
            if (g).default_type {
                __find_result_1306 = i;
                break;
            }
        }
        __find_result_1306
    };
    let mut difficulty: i64 = (&({
        let mut __comprehension_result_1308: Vec<i64> = Vec::new();
        let __comprehension_source_1307 = (((definition).difficulties.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>());
        for (i, d) in __comprehension_source_1307.iter().cloned() {
            if (AsRef::<str>::as_ref(&(d).name) == AsRef::<str>::as_ref(&(selection).difficulty)) {
                __comprehension_result_1308.push(i);
            }
        }
        __comprehension_result_1308
    }))
        .iter()
        .next()
        .cloned()
        .ok_or("StopIteration")?;
    let mut slots: Vec<crate::openciv3::scenario_model::PlayerSlot> = vec![];
    for mut civilization in (selected).iter().copied() {
        let mut prototypes: Vec<i64> = vec![
            ({
                let __source = &(rules).global_rules;
                let __key = 0i64;
                &__source[rt::index(__source.len(), __key)?]
            })
            .start_unit_type1,
            ({
                let __source = &(rules).global_rules;
                let __key = 0i64;
                &__source[rt::index(__source.len(), __key)?]
            })
            .start_unit_type2,
        ];
        if {
            let __needle = "Expansionist".to_string();
            let __container = &({
                let __source = &(definition).civilizations;
                let __key = civilization;
                &__source[rt::index(__source.len(), __key)?]
            })
            .traits;
            __container.contains(&__needle)
        } {
            {
                prototypes.push(
                    ({
                        let __source = &(rules).global_rules;
                        let __key = 0i64;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .scout,
                );
            };
        }
        prototypes = {
            let mut __comprehension_result_1310: Vec<i64> = Vec::new();
            let __comprehension_source_1309 = (prototypes.clone());
            for p in __comprehension_source_1309.iter().cloned() {
                if (p >= 0i64) {
                    __comprehension_result_1310.push(p);
                }
            }
            __comprehension_result_1310
        };
        if (!(((prototypes).len() as i64) != 0i64)
            || ({
                let mut __comprehension_result_1312: Vec<bool> = Vec::new();
                let __comprehension_source_1311 = (prototypes.clone());
                for p in __comprehension_source_1311.iter().cloned() {
                    __comprehension_result_1312.push((p >= ((&(rules).units).len() as i64)));
                }
                __comprehension_result_1312
            })
            .into_iter()
            .any(|__value| __value))
        {
            return Err("Missing or invalid starting-unit prototype"
                .to_string()
                .into());
        }
        {
            slots.push(crate::openciv3::scenario_model::PlayerSlot {
                custom_civ_data: false,
                human_allowed: true,
                name: String::new(),
                starting_units: ({
                    let mut __comprehension_result_1314: Vec<(i64, i64)> = Vec::new();
                    let __comprehension_source_1313 = (prototypes.clone());
                    for p in __comprehension_source_1313.iter().cloned() {
                        __comprehension_result_1314.push((1i64, p));
                    }
                    __comprehension_result_1314
                })
                .iter()
                .cloned()
                .collect::<Vec<_>>(),
                leader_gender: 0i64,
                starting_techs: vec![],
                difficulty: difficulty,
                era: 0i64,
                cash: 10i64,
                government: government,
                civilization: civilization,
                color: 0i64,
                skip_first_turn: false,
                start_embassies: false,
            });
        };
    }
    let mut starts: Vec<crate::openciv3::world::StartingLocation> = ({
        let mut __comprehension_result_1316: Vec<crate::openciv3::world::StartingLocation> =
            Vec::new();
        let __comprehension_source_1315 = ({
            let __left = selected.clone();
            let __right = (world).starts.clone();
            if false && __left.len() != __right.len() {
                return Err("zip() argument lengths differ".into());
            }
            let mut __result: Vec<(i64, crate::openciv3::world::StartingLocation)> = Vec::new();
            let __length = __left.len().min(__right.len());
            let mut __left_iter = __left.into_iter();
            let mut __right_iter = __right.into_iter();
            for __index in 0..__length {
                __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
            }
            __result
        });
        for (civilization, start) in __comprehension_source_1315.iter().cloned() {
            __comprehension_result_1316.push(crate::openciv3::world::StartingLocation {
                owner_kind: 2i64,
                owner: civilization,
                x: (start).x,
                y: (start).y,
            });
        }
        __comprehension_result_1316
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    world = {
        let mut __replacement = (world).clone();
        __replacement.starts = starts;
        __replacement
    };
    let mut scenario: crate::openciv3::scenario::Scenario = {
        let mut __replacement = ((definition).scenario.clone()).clone();
        __replacement.sections = {
            let mut __result: indexmap::IndexMap<String, Vec<Vec<u8>>> = indexmap::IndexMap::new();
            __result.extend((&(definition).scenario).sections.clone());
            __result.extend(
                [("SLOC".to_string(), vec![])]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>(),
            );
            __result
        };
        __replacement
    };
    let mut options: crate::openciv3::scenario_model::ScenarioOptions = {
        let mut __replacement = ((definition).options.clone()).clone();
        __replacement.allowed_civilizations = selected.clone();
        __replacement.victory_flags = (if (&(selection).victory_flags).is_none() {
            (&(definition).options).victory_flags
        } else {
            (*((selection).victory_flags.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone()
        });
        __replacement.alliance_ids = vec![];
        __replacement.alliance_wars = std::collections::BTreeSet::new();
        __replacement
    };
    let mut draft: crate::openciv3::scenario_model::ScenarioDefinition = {
        let mut __replacement = ((*definition).clone()).clone();
        __replacement.scenario = scenario;
        __replacement.options = options.clone();
        __replacement.slots = (slots).iter().cloned().collect::<Vec<_>>();
        __replacement.assigned_civilizations = selected;
        __replacement.seed = (world).seed;
        __replacement.world = Some(new_game__mark_victory_starts(
            &world,
            (options).victory_flags,
        )?);
        __replacement.world_size = Some({
            let mut __replacement = ((settings).size.clone()).clone();
            __replacement.width = (world).width;
            __replacement.height = (world).height;
            __replacement
        });
        __replacement.selected_civilization = (selection).civilization.clone();
        __replacement.selected_difficulty = (selection).difficulty.clone();
        __replacement.portrait_paths = (&(definition).portrait_paths).clone();
        __replacement
    };
    let mut game: crate::openciv3::game_state::GameState =
        crate::openciv3::game_state::GameState__from_scenario(draft)?;
    game.barbarian_activity = (settings).barbarian_activity;
    for mut unit in (&(game).units).iter().cloned() {
        let mut chained_fields_93_8: i64 = (1i64).checked_neg().ok_or("integer overflow")?;
        unit.previous_x = chained_fields_93_8;
        unit.previous_y = chained_fields_93_8;
    }
    crate::openciv3::game_state::GameState__validate(&game)?;
    Ok(game)
}

// Python: openciv3/new_game.py:98
pub(crate) fn new_game__mark_victory_starts(
    world: &crate::openciv3::world::WorldMap,
    mut flags: i64,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    if !((flags & rt::int_lshift(1i64, 13i64)?) != 0i64) {
        return Ok((*world).clone());
    }
    let mut starts: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_1318: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_1317 = ((world).starts.clone());
        for start in __comprehension_source_1317.iter().cloned() {
            __comprehension_result_1318.insert(((start).x, (start).y));
        }
        __comprehension_result_1318
    };
    Ok({
        let mut __replacement = ((*world).clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_1320: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_1319 = ((world).tiles.clone());
            for tile in __comprehension_source_1319.iter().cloned() {
                __comprehension_result_1320.push(
                    (if {
                        let __needle = ((tile).x, (tile).y);
                        let __container = &starts;
                        __container.contains(&__needle)
                    } {
                        {
                            let mut __replacement = (tile.clone()).clone();
                            __replacement.victory_point = true;
                            __replacement
                        }
                    } else {
                        tile.clone()
                    }),
                );
            }
            __comprehension_result_1320
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    })
}

// Python: openciv3/new_game.py:106
pub(crate) fn new_game__generate_new_game(
    definition: &crate::openciv3::scenario_model::ScenarioDefinition,
    settings: &world_generation__WorldSettings,
    selection: &new_game__PlayerSelection,
) -> rt::Result<crate::openciv3::game_state::GameState> {
    world_generation__WorldSettings__validate(settings)?;
    new_game__select_civilizations(definition, selection, (settings).seed)?;
    if (((&(selection).opponents).len() as i64)
        .checked_add(1i64)
        .ok_or("integer overflow")?
        > (&(settings).size).civilization_count)
    {
        return Err("More opponent slots than this world supports"
            .to_string()
            .into());
    }
    let mut generated: world_generation__GeneratedWorld =
        world_generation__generate_world(settings, &(definition).rules, None)?;
    new_game__initialize_generated_game(definition, settings, &generated, selection)
}

/// Supply a starting map for a rules-only BIQ while preserving its scenario setup.
// Python: openciv3/new_game.py:116
pub(crate) fn new_game__generate_scenario_map(
    definition: &crate::openciv3::scenario_model::ScenarioDefinition,
) -> rt::Result<crate::openciv3::scenario_model::ScenarioDefinition> {
    let mut size: Option<crate::openciv3::world_size::WorldSize> = (definition).world_size.clone();
    if (size).is_none() {
        let mut source: crate::openciv3::scenario::Scenario = (if {
            let __needle: &str = AsRef::<str>::as_ref("WSIZ");
            let __container = &(&(definition).scenario).sections;
            __container.contains_key(__needle)
        } {
            (definition).scenario.clone()
        } else {
            (definition).defaults.clone()
        });
        let mut rows: Vec<Vec<u8>> = {
            let __mapping = &(source).sections;
            let __key = "WSIZ".to_string();
            let __default = vec![];
            __mapping.get(&__key).cloned().unwrap_or(__default)
        };
        if (((rows).len() as i64) == 0i64) {
            return Err("The scenario needs a world size to generate a map"
                .to_string()
                .into());
        }
        size = Some(crate::openciv3::world_size::WorldSize__from_record(
            &(crate::openciv3::binary::Record {
                data: rt::at(&rows, rt::int_floor_div(((rows).len() as i64), 2i64)?)?,
                section: "WSIZ".to_string(),
                encoding: (source).encoding.clone(),
            }),
        )?);
    }
    let mut allowed: Vec<i64> = (&(definition).options).allowed_civilizations.clone();
    let mut participants: Vec<i64> = vec![];
    if (((&(definition).slots).len() as i64) > 0i64) {
        participants = ({
            let mut __seen = std::collections::BTreeSet::new();
            let mut __result: Vec<i64> = Vec::new();
            for __item in ({
                let mut __comprehension_result_1322: Vec<i64> = Vec::new();
                let __comprehension_source_1321 = ((definition).assigned_civilizations.clone());
                for civ in __comprehension_source_1321.iter().cloned() {
                    if ({
                        let __needle = civ;
                        let __container = &allowed;
                        __container.contains(&__needle)
                    } && (civ > 0i64))
                    {
                        __comprehension_result_1322.push(civ);
                    }
                }
                __comprehension_result_1322
            })
            .into_iter()
            {
                if __seen.insert(__item.clone()) {
                    __result.push(__item);
                }
            }
            __result
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
    } else {
        let mut opponents: Vec<String> = ({
            let mut __comprehension_result_1326: Vec<String> = Vec::new();
            let __comprehension_source_1325 = ((0i64..(0i64).max(
                ((((*(size.clone()).as_ref().ok_or("expected a value")?).clone())
                    .civilization_count)
                    .min(
                        ({
                            let mut __comprehension_result_1324: Vec<bool> = Vec::new();
                            let __comprehension_source_1323 = (allowed.clone());
                            for civ in __comprehension_source_1323.iter().cloned() {
                                __comprehension_result_1324.push((civ > 0i64));
                            }
                            __comprehension_result_1324
                        })
                        .into_iter()
                        .map(|value| value as i64)
                        .sum::<i64>(),
                    ))
                .checked_sub(1i64)
                .ok_or("integer overflow")?,
            ))
                .collect::<Vec<i64>>());
            for _ in __comprehension_source_1325.iter().cloned() {
                __comprehension_result_1326.push("Random".to_string());
            }
            __comprehension_result_1326
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        let mut selection: new_game__PlayerSelection = new_game__PlayerSelection {
            civilization: (definition).selected_civilization.clone(),
            difficulty: (definition).selected_difficulty.clone(),
            opponents: opponents,
            victory_flags: None,
        };
        participants = new_game__select_civilizations(definition, &selection, (definition).seed)?;
    }
    size = Some({
        let mut __replacement = ((*(size).as_ref().ok_or("expected a value")?).clone()).clone();
        __replacement.civilization_count = ((participants).len() as i64);
        __replacement
    });
    let mut characteristics: Vec<Vec<u8>> = {
        let __mapping = &(&(definition).scenario).sections;
        let __key = "WCHR".to_string();
        let __default = vec![];
        __mapping.get(&__key).cloned().unwrap_or(__default)
    };
    let mut settings: world_generation__WorldSettings =
        (if (((characteristics).len() as i64) > 0i64) {
            world_generation__WorldSettings__from_biq(
                &((*(size.clone()).as_ref().ok_or("expected a value")?).clone()),
                (definition).seed,
                &(crate::openciv3::binary::Record {
                    data: rt::at(&characteristics, 0i64)?,
                    section: "WCHR".to_string(),
                    encoding: "cp1252".to_string(),
                }),
            )?
        } else {
            world_generation__WorldSettings {
                size: (*(size.clone()).as_ref().ok_or("expected a value")?).clone(),
                seed: (definition).seed,
                landform: world_shape__Landform::PANGAEA,
                ocean_percent: 70i64,
                age: 4i64,
                climate: crate::openciv3::world_vegetation::Climate::NORMAL,
                temperature: world_biomes__Temperature::TEMPERATE,
                barbarian_activity: 1i64,
                workable_rank: None,
                camp_rank: None,
                max_shape_attempts: 30i64,
            }
        });
    let mut generated: world_generation__GeneratedWorld =
        world_generation__generate_world(&settings, &(definition).rules, None)?;
    if !(world_generation__GeneratedWorld__complete(&generated)?) {
        return Err(
            "Map generation could not place all scenario starting locations"
                .to_string()
                .into(),
        );
    }
    let mut starts: Vec<crate::openciv3::world::StartingLocation> = ({
        let mut __comprehension_result_1328: Vec<crate::openciv3::world::StartingLocation> =
            Vec::new();
        let __comprehension_source_1327 = ({
            let __left = participants.clone();
            let __right = (&(generated).world).starts.clone();
            if false && __left.len() != __right.len() {
                return Err("zip() argument lengths differ".into());
            }
            let mut __result: Vec<(i64, crate::openciv3::world::StartingLocation)> = Vec::new();
            let __length = __left.len().min(__right.len());
            let mut __left_iter = __left.into_iter();
            let mut __right_iter = __right.into_iter();
            for __index in 0..__length {
                __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
            }
            __result
        });
        for (civ, start) in __comprehension_source_1327.iter().cloned() {
            __comprehension_result_1328.push(crate::openciv3::world::StartingLocation {
                owner_kind: 2i64,
                owner: civ,
                x: (start).x,
                y: (start).y,
            });
        }
        __comprehension_result_1328
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut world: crate::openciv3::world::WorldMap = {
        let mut __replacement = ((generated).world.clone()).clone();
        __replacement.starts = starts;
        __replacement
    };
    let mut selected: Vec<i64> = ({
        let mut __comprehension_result_1330: Vec<i64> = Vec::new();
        let __comprehension_source_1329 = (allowed.clone());
        for civ in __comprehension_source_1329.iter().cloned() {
            if {
                let __needle = civ;
                let __container = &participants;
                __container.contains(&__needle)
            } {
                __comprehension_result_1330.push(civ);
            }
        }
        __comprehension_result_1330
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut alliances: indexmap::IndexMap<i64, i64> = ({
        let __left = allowed;
        let __right = (&(definition).options).alliance_ids.clone();
        if false && __left.len() != __right.len() {
            return Err("zip() argument lengths differ".into());
        }
        let mut __result: Vec<(i64, i64)> = Vec::new();
        let __length = __left.len().min(__right.len());
        let mut __left_iter = __left.into_iter();
        let mut __right_iter = __right.into_iter();
        for __index in 0..__length {
            __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
        }
        __result
    })
    .into_iter()
    .map(|__pair| (__pair.0, __pair.1))
    .collect::<indexmap::IndexMap<i64, i64>>();
    let mut options: crate::openciv3::scenario_model::ScenarioOptions = {
        let mut __replacement = ((definition).options.clone()).clone();
        __replacement.allowed_civilizations = selected.clone();
        __replacement.alliance_ids = (if (((alliances).len() as i64) != 0i64) {
            ({
                let mut __comprehension_result_1332: Vec<i64> = Vec::new();
                let __comprehension_source_1331 = (selected.clone());
                for civ in __comprehension_source_1331.iter().cloned() {
                    __comprehension_result_1332
                        .push((alliances).get(&(civ)).ok_or("missing dict key")?.clone());
                }
                __comprehension_result_1332
            })
            .iter()
            .cloned()
            .collect::<Vec<_>>()
        } else {
            vec![]
        });
        __replacement
    };
    let mut scenario: crate::openciv3::scenario::Scenario = {
        let mut __replacement = ((definition).scenario.clone()).clone();
        __replacement.sections = {
            let mut __result: indexmap::IndexMap<String, Vec<Vec<u8>>> = indexmap::IndexMap::new();
            __result.extend((&(definition).scenario).sections.clone());
            __result.extend(
                [("SLOC".to_string(), vec![])]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>(),
            );
            __result
        };
        __replacement
    };
    Ok({
        let mut __replacement = ((*definition).clone()).clone();
        __replacement.scenario = scenario;
        __replacement.options = options.clone();
        __replacement.world = Some(new_game__mark_victory_starts(
            &world,
            (options).victory_flags,
        )?);
        __replacement.world_size = Some({
            let mut __replacement = ((settings).size.clone()).clone();
            __replacement.width = (world).width;
            __replacement.height = (world).height;
            __replacement
        });
        __replacement
    })
}

// Python: openciv3/world_generation.py:37
pub(crate) fn world_generation__WorldSettings__from_biq(
    size: &crate::openciv3::world_size::WorldSize,
    mut seed: i64,
    record: &crate::openciv3::binary::Record,
) -> rt::Result<world_generation__WorldSettings> {
    let (mut landform, mut coverage, mut climate, mut temperature, mut age): (
        i64,
        i64,
        i64,
        i64,
        i64,
    ) = {
        let __tuple_values = {
            let mut __comprehension_result_1334: Vec<i64> = Vec::new();
            let __comprehension_source_1333 = ({
                let __tuple_value = &((8i64, 24i64, 32i64, 40i64, 48i64));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                    __tuple_value.3.clone(),
                    __tuple_value.4.clone(),
                ]
            });
            for offset in __comprehension_source_1333.iter().cloned() {
                __comprehension_result_1334
                    .push(crate::openciv3::binary::Record__integer(record, offset)?);
            }
            __comprehension_result_1334
        };
        if __tuple_values.len() != 5 {
            return Err("tuple length mismatch".into());
        }
        (
            rt::at(&__tuple_values, 0i64)?,
            rt::at(&__tuple_values, 1i64)?,
            rt::at(&__tuple_values, 2i64)?,
            rt::at(&__tuple_values, 3i64)?,
            rt::at(&__tuple_values, 4i64)?,
        )
    };
    Ok(world_generation__WorldSettings {
        size: (*size).clone(),
        seed: seed,
        landform: (if {
            let __compare_0 = 0i64;
            let __compare_1 = landform;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = 2i64;
                (__compare_1 <= __compare_2)
            } else {
                false
            }
        } {
            rt::at(
                &({
                    let __tuple_value = &((
                        world_shape__Landform::ARCHIPELAGO,
                        world_shape__Landform::CONTINENTS,
                        world_shape__Landform::PANGAEA,
                    ));
                    vec![
                        __tuple_value.0.clone(),
                        __tuple_value.1.clone(),
                        __tuple_value.2.clone(),
                    ]
                }),
                landform,
            )?
        } else {
            world_shape__Landform::PANGAEA
        }),
        ocean_percent: {
            let __mapping = [(0i64, 80i64), (1i64, 70i64), (2i64, 60i64)]
                .into_iter()
                .collect::<indexmap::IndexMap<_, _>>();
            let __key = coverage;
            let __default = 70i64;
            __mapping.get(&__key).cloned().unwrap_or(__default)
        },
        climate: (if {
            let __compare_0 = 0i64;
            let __compare_1 = climate;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = 2i64;
                (__compare_1 <= __compare_2)
            } else {
                false
            }
        } {
            rt::at(
                &({
                    let __tuple_value = &((
                        crate::openciv3::world_vegetation::Climate::ARID,
                        crate::openciv3::world_vegetation::Climate::NORMAL,
                        crate::openciv3::world_vegetation::Climate::WET,
                    ));
                    vec![
                        __tuple_value.0.clone(),
                        __tuple_value.1.clone(),
                        __tuple_value.2.clone(),
                    ]
                }),
                climate,
            )?
        } else {
            crate::openciv3::world_vegetation::Climate::NORMAL
        }),
        temperature: (if {
            let __compare_0 = 0i64;
            let __compare_1 = temperature;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = 2i64;
                (__compare_1 <= __compare_2)
            } else {
                false
            }
        } {
            rt::at(
                &({
                    let __tuple_value = &((
                        world_biomes__Temperature::COOL,
                        world_biomes__Temperature::TEMPERATE,
                        world_biomes__Temperature::WARM,
                    ));
                    vec![
                        __tuple_value.0.clone(),
                        __tuple_value.1.clone(),
                        __tuple_value.2.clone(),
                    ]
                }),
                temperature,
            )?
        } else {
            world_biomes__Temperature::TEMPERATE
        }),
        age: (if {
            let __compare_0 = 0i64;
            let __compare_1 = age;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = 2i64;
                (__compare_1 <= __compare_2)
            } else {
                false
            }
        } {
            (age).checked_add(3i64).ok_or("integer overflow")?
        } else {
            4i64
        }),
        barbarian_activity: 1i64,
        workable_rank: None,
        camp_rank: None,
        max_shape_attempts: 30i64,
    })
}

// Python: openciv3/world_generation.py:50
pub(crate) fn world_generation__WorldSettings__validate(
    self_: &world_generation__WorldSettings,
) -> rt::Result<()> {
    if ({
        let __needle = (self_).landform.clone();
        let __container = &((vec![
            world_shape__Landform::ARCHIPELAGO,
            world_shape__Landform::CONTINENTS,
            world_shape__Landform::PANGAEA,
        ])
        .iter()
        .cloned()
        .collect::<Vec<_>>());
        !__container.contains(&__needle)
    } || ({
        let __needle = (self_).age;
        let __container = &((vec![3i64, 4i64, 5i64]).iter().cloned().collect::<Vec<_>>());
        !__container.contains(&__needle)
    } || ({
        let __needle = (self_).climate.clone();
        let __container = &((vec![
            crate::openciv3::world_vegetation::Climate::ARID,
            crate::openciv3::world_vegetation::Climate::NORMAL,
            crate::openciv3::world_vegetation::Climate::WET,
        ])
        .iter()
        .cloned()
        .collect::<Vec<_>>());
        !__container.contains(&__needle)
    } || {
        let __needle = (self_).temperature.clone();
        let __container = &((vec![
            world_biomes__Temperature::COOL,
            world_biomes__Temperature::TEMPERATE,
            world_biomes__Temperature::WARM,
        ])
        .iter()
        .cloned()
        .collect::<Vec<_>>());
        !__container.contains(&__needle)
    }))) {
        return Err("Unknown world-generation setting".to_string().into());
    }
    if ({
        let __needle = (self_).ocean_percent;
        let __container = &({
            let __tuple_value = &((60i64, 70i64, 80i64));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        !__container.contains(&__needle)
    } || {
        let __needle = (self_).barbarian_activity;
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
    }) {
        return Err("Invalid ocean coverage or barbarian activity"
            .to_string()
            .into());
    }
    if (((&(self_).workable_rank).is_some()
        && ((*((self_).workable_rank.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone()
            < 1i64))
        || (((&(self_).camp_rank).is_some()
            && ((*((self_).camp_rank.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone()
                < 0i64))
            || ((self_).max_shape_attempts < 1i64)))
    {
        return Err("Invalid generation radius or attempt limit"
            .to_string()
            .into());
    }
    if (((&(self_).size).width < 2i64)
        || (((&(self_).size).height < 2i64)
            || (((&(self_).size).civilization_count < 1i64)
                || ((&(self_).size).civilization_distance < 0i64))))
    {
        return Err("Invalid generated world size".to_string().into());
    }
    Ok(())
}

/// A bounded shape fallback is usable, but missing starts are not.
// Python: openciv3/world_generation.py:72
pub(crate) fn world_generation__GeneratedWorld__complete(
    self_: &world_generation__GeneratedWorld,
) -> rt::Result<bool> {
    Ok((((&(&(self_).world).starts).len() as i64) == (self_).requested_starts))
}

// Python: openciv3/world_generation.py:77
pub(crate) fn world_generation__generate_terrain(
    settings: &world_generation__WorldSettings,
    vegetation: &crate::openciv3::world_vegetation::VegetationRules,
    mut flood_plains: bool,
) -> rt::Result<world_shape__ShapeResult> {
    let mut shape: world_shape__ShapeResult = {
        let __call_1335_0 = &(settings).size;
        let __call_1335_1 = crate::strategy::random::seed32((settings).seed)?;
        let __call_1335_2 = (settings).landform.clone();
        let __call_1335_3 = (settings).ocean_percent;
        let __call_1335_4 = (settings).max_shape_attempts;
        world_shape__generate_shape(
            __call_1335_0,
            __call_1335_1,
            __call_1335_2,
            __call_1335_3,
            __call_1335_4,
        )
    }?;
    let mut world: crate::openciv3::world::WorldMap =
        crate::openciv3::world_elevation::add_elevation(&(shape).world, (settings).age)?;
    world = world_biomes__add_biomes(
        &world,
        (settings).temperature.clone(),
        (settings).climate.clone(),
    )?;
    world = world_rivers__add_rivers(
        &(crate::openciv3::world_vegetation::add_vegetation(
            &world,
            (settings).climate.clone(),
            vegetation,
        )?),
        (settings).ocean_percent,
    )?;
    Ok({
        let mut __replacement = (shape).clone();
        __replacement.world = (if flood_plains {
            world_rivers__add_flood_plains(&world)?
        } else {
            world.clone()
        });
        __replacement
    })
}

// Python: openciv3/world_generation.py:87
pub(crate) fn world_generation__generate_world(
    settings: &world_generation__WorldSettings,
    rules: &crate::openciv3::rules::RuleCatalog,
    mut vegetation: Option<crate::openciv3::world_vegetation::VegetationRules>,
) -> rt::Result<world_generation__GeneratedWorld> {
    let mut allowed: Option<std::collections::BTreeSet<i64>>;
    world_generation__WorldSettings__validate(settings)?;
    let mut workable_rank: i64 = (if (&(settings).workable_rank).is_none() {
        crate::openciv3::rules::RuleCatalog__workable_rank(rules)?
    } else {
        (*((settings).workable_rank.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone()
    });
    let mut camp_rank: Option<i64> = (settings).camp_rank.clone();
    if (camp_rank).is_none() {
        camp_rank = (if (((&(rules).global_rules).len() as i64) != 0i64) {
            Some(
                ({
                    let __source = &(rules).global_rules;
                    let __key = 0i64;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .max_rank_of_barbarian_camp_tiles,
            )
        } else {
            Some(2i64)
        });
    }
    if ((((&(rules).terrains).len() as i64) < 14i64)
        || !(((&(rules).governments).len() as i64) != 0i64))
    {
        return Err(
            "World generation needs Conquests terrain and government rules"
                .to_string()
                .into(),
        );
    }
    let mut government: i64 = {
        let __find_source_1336 = ((rules).governments.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>();
        let mut __find_result_1336: i64 = 0i64;
        for (i, g) in __find_source_1336.iter().cloned() {
            if (g).default_type {
                __find_result_1336 = i;
                break;
            }
        }
        __find_result_1336
    };
    let mut neutral: crate::openciv3::players::Player = crate::openciv3::players::Player {
        civilization: 0i64,
        included: true,
        human: false,
        can_be_picked: false,
        government: government,
        era: 0i64,
        gold: 0i64,
        primary_color: 0i64,
        secondary_color: 0i64,
        known_technologies: {
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        },
        science_rate: 5i64,
        tax_rate: 5i64,
        luxury_rate: 0i64,
        skip_first_turn: false,
        has_played_current_turn: false,
        contacts: {
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        },
        start_embassies: false,
        defeated: false,
        anarchy_until: 0i64,
        researching: None,
        last_gold_per_turn: 0i64,
        beakers: 0i64,
        turns_researched: 0i64,
        free_technologies: 0i64,
        research_queue: vec![],
        strategic_priorities: vec![],
        turns_until_priority_reevaluation: 0i64,
        cities_lost: 0i64,
        victory_points: 0i64,
        golden_age_turns: None,
    };
    if (vegetation).is_none() {
        let mut defaults: crate::openciv3::world_vegetation::VegetationRules =
            crate::openciv3::world_vegetation::VegetationRules {
                forest: {
                    let mut __result: std::collections::BTreeSet<i64> =
                        std::collections::BTreeSet::new();
                    for __item in ({
                        let __tuple_value = &((1i64, 2i64, 3i64));
                        vec![
                            __tuple_value.0.clone(),
                            __tuple_value.1.clone(),
                            __tuple_value.2.clone(),
                        ]
                    })
                    .into_iter()
                    {
                        __result.insert(__item);
                    }
                    __result
                },
                jungle: {
                    let mut __result: std::collections::BTreeSet<i64> =
                        std::collections::BTreeSet::new();
                    for __item in ({
                        let __tuple_value = &((2i64,));
                        vec![__tuple_value.0.clone()]
                    })
                    .into_iter()
                    {
                        __result.insert(__item);
                    }
                    __result
                },
                marsh: {
                    let mut __result: std::collections::BTreeSet<i64> =
                        std::collections::BTreeSet::new();
                    for __item in ({
                        let __tuple_value = &((2i64,));
                        vec![__tuple_value.0.clone()]
                    })
                    .into_iter()
                    {
                        __result.insert(__item);
                    }
                    __result
                },
            };
        let (mut forest, mut jungle, mut marsh): (
            std::collections::BTreeSet<i64>,
            std::collections::BTreeSet<i64>,
            std::collections::BTreeSet<i64>,
        ) = {
            let __tuple_values = {
                let mut __comprehension_result_1338: Vec<std::collections::BTreeSet<i64>> =
                    Vec::new();
                let mut allowed: Option<std::collections::BTreeSet<i64>>;
                let __comprehension_source_1337 = ({
                    let __tuple_value = &((
                        (7i64, (defaults).forest.clone()),
                        (8i64, (defaults).jungle.clone()),
                        (9i64, (defaults).marsh.clone()),
                    ));
                    vec![
                        __tuple_value.0.clone(),
                        __tuple_value.1.clone(),
                        __tuple_value.2.clone(),
                    ]
                });
                for (index, default) in __comprehension_source_1337.iter().cloned() {
                    __comprehension_result_1338.push(
                        (if ({
                            allowed = ({
                                let __source = &(rules).terrains;
                                let __key = index;
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .allowed_base_terrains
                            .clone();
                            allowed.clone()
                        })
                        .is_none()
                        {
                            default.clone()
                        } else {
                            (*(allowed.clone()).as_ref().ok_or("expected a value")?).clone()
                        }),
                    );
                }
                __comprehension_result_1338
            };
            if __tuple_values.len() != 3 {
                return Err("tuple length mismatch".into());
            }
            (
                rt::at(&__tuple_values, 0i64)?,
                rt::at(&__tuple_values, 1i64)?,
                rt::at(&__tuple_values, 2i64)?,
            )
        };
        vegetation = Some(crate::openciv3::world_vegetation::VegetationRules {
            forest: forest,
            jungle: jungle,
            marsh: marsh,
        });
    }
    let mut shape: world_shape__ShapeResult = world_generation__generate_terrain(
        settings,
        &((*(vegetation).as_ref().ok_or("expected a value")?).clone()),
        true,
    )?;
    let mut world: crate::openciv3::world::WorldMap = {
        let __call_1339_0 = &(shape).world;
        let __call_1339_1 = &((rules).resources.clone());
        let __call_1339_2 = &(((rules).terrains.clone())
            .into_iter()
            .map(|__item| world_resources__ResourceTerrain {
                possible_resources: __item.possible_resources.clone(),
            })
            .collect::<Vec<_>>());
        let __call_1339_3 = workable_rank;
        world_resources__add_resources(__call_1339_0, __call_1339_1, __call_1339_2, __call_1339_3)
    }?;
    world = world_extras__add_bonus_grassland(&world)?;

    let mut starts: world_starts__StartLocations = {
        let __call_1340_0 = &world;
        let __call_1340_1 = &((rules).resources.clone());
        let __call_1340_2 = &(((rules).terrains.clone())
            .into_iter()
            .map(|__item| world_starts__StartTerrain {
                allow_cities: __item.allow_cities.clone(),
            })
            .collect::<Vec<_>>());
        let __call_1340_3 = |__arg0| {
            world_generation__generate_world__neutral_yield(neutral.clone(), rules.clone(), __arg0)
        };
        let __call_1340_4 = workable_rank;
        world_starts__choose_starts(
            __call_1340_0,
            __call_1340_1,
            __call_1340_2,
            __call_1340_3,
            __call_1340_4,
        )
    }?;
    world = {
        let mut __replacement = (world).clone();
        __replacement.starts = ({
            let mut __comprehension_result_1342: Vec<crate::openciv3::world::StartingLocation> =
                Vec::new();
            let __comprehension_source_1341 = ((starts).points.clone());
            for (x, y) in __comprehension_source_1341.iter().cloned() {
                __comprehension_result_1342.push(crate::openciv3::world::StartingLocation {
                    owner_kind: 0i64,
                    owner: (1i64).checked_neg().ok_or("integer overflow")?,
                    x: x,
                    y: y,
                });
            }
            __comprehension_result_1342
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    };
    world = {
        let __call_1343_0 = &world;
        let __call_1343_1 = &((rules).resources.clone());
        let __call_1343_2 = (settings).barbarian_activity;
        let __call_1343_3 = &((starts).points.clone());
        let __call_1343_4 = (*(camp_rank).as_ref().ok_or("expected a value")?).clone();
        world_extras__add_barbarian_camps(
            __call_1343_0,
            __call_1343_1,
            __call_1343_2,
            __call_1343_3,
            __call_1343_4,
        )
    }?;
    world = world_textures__assign_textures(&world)?;
    Ok(world_generation__GeneratedWorld {
        world: world,
        shape_attempts: (shape).attempts,
        shape_accepted: (shape).accepted,
        requested_starts: (starts).requested,
    })
}

// Python: openciv3/world_generation.py:107
pub(crate) fn world_generation__generate_world__neutral_yield(
    mut neutral: crate::openciv3::players::Player,
    mut rules: crate::openciv3::rules::RuleCatalog,
    mut tile: crate::openciv3::world::Tile,
) -> rt::Result<crate::civ::economy::Yield> {
    crate::openciv3::yields::tile_yield(
        &tile,
        &neutral,
        &None,
        &rules,
        &None,
        false,
        false,
        &(vec![]),
        &None,
    )
}

/// Return row-ordered region IDs; water and elevated tiles retain -1.
// Python: openciv3/world_biomes.py:29
pub(crate) fn world_biomes__split_regions(
    world: &crate::openciv3::world::WorldMap,
) -> rt::Result<Vec<i64>> {
    let mut random: crate::strategy::random::MapRandom =
        crate::strategy::random::MapRandom____post_init__(crate::strategy::random::MapRandom {
            seed: crate::strategy::random::seed32(
                ((world).seed)
                    .checked_add(47633i64)
                    .ok_or("integer overflow")?,
            )?,
            _values: vec![],
            _index: 0i64,
            _other: 21i64,
        })?;
    let mut order: Vec<i64> = ((0i64..((&(world).tiles).len() as i64)).collect::<Vec<i64>>())
        .iter()
        .cloned()
        .collect::<Vec<_>>();
    {
        let mut __random = random.clone();
        for __index in 0..order.len().saturating_sub(1) {
            __random._index = if __random._index < 55 {
                __random._index + 1
            } else {
                1
            };
            __random._other = if __random._other < 55 {
                __random._other + 1
            } else {
                1
            };
            let __sample_index = __random._index as usize;
            let mut __value = (__random._values[__sample_index]
                - __random._values[__random._other as usize]
                + 2147483648i64)
                .rem_euclid(4294967296i64)
                - 2147483648i64;
            if __value == 2147483647i64 {
                __value -= 1;
            }
            if __value < 0 {
                __value += 2147483647i64;
            }
            __random._values[__sample_index] = __value;
            let __other = __index
                + ((__value as f64) * (1.0 / 2147483647.0) * ((order.len() - __index) as f64))
                    as usize;
            order.swap(__index, __other);
        }
        ()
    };
    let mut regions: Vec<i64> = (vec![(1i64).checked_neg().ok_or("integer overflow")?])
        .repeat(std::cmp::max(((&(world).tiles).len() as i64), 0) as usize);
    let mut eligible: Vec<bool> = {
        let mut __comprehension_result_1345: Vec<bool> = Vec::new();
        let __comprehension_source_1344 = ((world).tiles.clone());
        for t in __comprehension_source_1344.iter().cloned() {
            __comprehension_result_1345.push(
                (!(crate::openciv3::hydrology::is_water(&t)?) && {
                    let __needle = (t).overlay_terrain;
                    let __container = &({
                        let __tuple_value = {
                            static __CONSTANT_py__openciv3__world_biomes__escaped_5f48494c4c59:
                                std::sync::OnceLock<(i64, i64, i64)> = std::sync::OnceLock::new();
                            if __CONSTANT_py__openciv3__world_biomes__escaped_5f48494c4c59
                                .get()
                                .is_none()
                            {
                                let __constant_value = (5i64, 6i64, 10i64);
                                let _ = __CONSTANT_py__openciv3__world_biomes__escaped_5f48494c4c59
                                    .set(__constant_value);
                            }
                            __CONSTANT_py__openciv3__world_biomes__escaped_5f48494c4c59
                                .get()
                                .ok_or("missing module constant")?
                        };
                        vec![
                            __tuple_value.0.clone(),
                            __tuple_value.1.clone(),
                            __tuple_value.2.clone(),
                        ]
                    });
                    !__container.contains(&__needle)
                }),
            );
        }
        __comprehension_result_1345
    };

    let mut next_region: i64 = 0i64;
    for mut start in (order).iter().copied() {
        if (!(rt::at(&eligible, start)?)
            || (rt::at(&regions, start)? != (1i64).checked_neg().ok_or("integer overflow")?))
        {
            continue;
        }
        let mut current: crate::openciv3::world::Tile = rt::at(&(world).tiles, start)?;
        let mut walked: Vec<crate::openciv3::world::Tile> = vec![];
        for _ in 0i64..16i64 {
            {
                let __value = next_region;
                let __key = world_biomes__split_regions__index(world, &current)?;
                let __index = rt::index(regions.len(), __key)?;
                regions[__index] = __value;
            }
            {
                walked.push(current.clone());
            };
            let mut directions: Vec<(i64, i64)> = vec![
                (0i64, (2i64).checked_neg().ok_or("integer overflow")?),
                (0i64, 2i64),
                (2i64, 0i64),
                ((2i64).checked_neg().ok_or("integer overflow")?, 0i64),
            ];
            {
                let mut __random = random.clone();
                for __index in 0..directions.len().saturating_sub(1) {
                    __random._index = if __random._index < 55 {
                        __random._index + 1
                    } else {
                        1
                    };
                    __random._other = if __random._other < 55 {
                        __random._other + 1
                    } else {
                        1
                    };
                    let __sample_index = __random._index as usize;
                    let mut __value = (__random._values[__sample_index]
                        - __random._values[__random._other as usize]
                        + 2147483648i64)
                        .rem_euclid(4294967296i64)
                        - 2147483648i64;
                    if __value == 2147483647i64 {
                        __value -= 1;
                    }
                    if __value < 0 {
                        __value += 2147483647i64;
                    }
                    __random._values[__sample_index] = __value;
                    let __other = __index
                        + ((__value as f64)
                            * (1.0 / 2147483647.0)
                            * ((directions.len() - __index) as f64))
                            as usize;
                    directions.swap(__index, __other);
                }
                ()
            };
            let mut found: bool = false;
            for mut for_target_55_12 in directions {
                let (mut dx, mut dy): (i64, i64) = for_target_55_12;
                let mut neighbor: Option<crate::openciv3::world::Tile> =
                    crate::openciv3::world::WorldMap__tile_at(
                        world,
                        ((current).x).checked_add(dx).ok_or("integer overflow")?,
                        ((current).y).checked_add(dy).ok_or("integer overflow")?,
                    )?;
                if ((neighbor).is_some()
                    && world_biomes__split_regions__available(
                        &eligible, world, &regions, &neighbor,
                    )?)
                {
                    current = (*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone();
                    found = true;
                    break;
                }
            }
            if !(found) {
                break;
            }
        }
        let mut expansion: Vec<i64> = vec![];
        for mut tile in walked {
            for mut neighbor in crate::openciv3::world::WorldMap__neighbors(world, &tile)? {
                if (world_biomes__split_regions__available(
                    &eligible,
                    world,
                    &regions,
                    &(Some(neighbor.clone())),
                )? && ({
                    if !(0..=2147483647i64).contains(&(100i64)) {
                        return Err("Random upper bound must be a nonnegative Int32".into());
                    }
                    let mut __map_random = random.clone();
                    __map_random._index = if __map_random._index < 55 {
                        __map_random._index + 1
                    } else {
                        1
                    };
                    __map_random._other = if __map_random._other < 55 {
                        __map_random._other + 1
                    } else {
                        1
                    };
                    let __sample_index = __map_random._index as usize;
                    let mut __value = (__map_random._values[__sample_index]
                        - __map_random._values[__map_random._other as usize]
                        + 2147483648i64)
                        .rem_euclid(4294967296i64)
                        - 2147483648i64;
                    if __value == 2147483647i64 {
                        __value -= 1;
                    }
                    if __value < 0 {
                        __value += 2147483647i64;
                    }
                    __map_random._values[__sample_index] = __value;
                    random = __map_random;
                    ((__value as f64) * (1.0 / 2147483647.0) * ((100i64) as f64)) as i64
                } < 50i64))
                {
                    {
                        expansion.push(world_biomes__split_regions__index(world, &neighbor)?);
                    };
                }
            }
        }
        for mut target in expansion {
            {
                let __value = next_region;
                let __key = target;
                let __index = rt::index(regions.len(), __key)?;
                regions[__index] = __value;
            }
        }
        next_region = (next_region).checked_add(1i64).ok_or("integer overflow")?;
    }
    for mut target in order {
        if !(rt::at(&eligible, target)?) {
            continue;
        }
        let mut tile: crate::openciv3::world::Tile = rt::at(&(world).tiles, target)?;
        let mut adjacent: Vec<i64> = {
            let mut __comprehension_result_1347: Vec<i64> = Vec::new();
            let mut neighbor: Option<crate::openciv3::world::Tile>;
            let __comprehension_source_1346 = ({
                let __tuple_value = &((
                    (
                        (1i64).checked_neg().ok_or("integer overflow")?,
                        (1i64).checked_neg().ok_or("integer overflow")?,
                    ),
                    ((1i64).checked_neg().ok_or("integer overflow")?, 1i64),
                    (1i64, (1i64).checked_neg().ok_or("integer overflow")?),
                    (1i64, 1i64),
                ));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                    __tuple_value.3.clone(),
                ]
            });
            for (dx, dy) in __comprehension_source_1346.iter().cloned() {
                if (({
                    neighbor = crate::openciv3::world::WorldMap__tile_at(
                        world,
                        ((tile).x).checked_add(dx).ok_or("integer overflow")?,
                        ((tile).y).checked_add(dy).ok_or("integer overflow")?,
                    )?;
                    neighbor.clone()
                })
                .is_some()
                    && (rt::at(
                        &(regions.clone()),
                        world_biomes__split_regions__index(
                            world,
                            &((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone()),
                        )?,
                    )? != (1i64).checked_neg().ok_or("integer overflow")?))
                {
                    __comprehension_result_1347.push(world_biomes__split_regions__index(
                        world,
                        &((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone()),
                    )?);
                }
            }
            __comprehension_result_1347
        };
        if (!(adjacent.clone()).is_empty()
            && !(({
                let mut __comprehension_result_1349: Vec<bool> = Vec::new();
                let __comprehension_source_1348 = (adjacent.clone());
                for n in __comprehension_source_1348.iter().cloned() {
                    __comprehension_result_1349
                        .push((rt::at(&regions, n)? == rt::at(&regions, target)?));
                }
                __comprehension_result_1349
            })
            .into_iter()
            .any(|__value| __value)))
        {
            {
                let __value = rt::at(
                    &(regions.clone()),
                    rt::at(&(adjacent.clone()), {
                        if !(0..=2147483647i64).contains(&((adjacent).len() as i64)) {
                            return Err("Random upper bound must be a nonnegative Int32".into());
                        }
                        let mut __map_random = random.clone();
                        __map_random._index = if __map_random._index < 55 {
                            __map_random._index + 1
                        } else {
                            1
                        };
                        __map_random._other = if __map_random._other < 55 {
                            __map_random._other + 1
                        } else {
                            1
                        };
                        let __sample_index = __map_random._index as usize;
                        let mut __value = (__map_random._values[__sample_index]
                            - __map_random._values[__map_random._other as usize]
                            + 2147483648i64)
                            .rem_euclid(4294967296i64)
                            - 2147483648i64;
                        if __value == 2147483647i64 {
                            __value -= 1;
                        }
                        if __value < 0 {
                            __value += 2147483647i64;
                        }
                        __map_random._values[__sample_index] = __value;
                        random = __map_random;
                        ((__value as f64)
                            * (1.0 / 2147483647.0)
                            * (((adjacent).len() as i64) as f64)) as i64
                    })?,
                )?;
                let __key = target;
                let __index = rt::index(regions.len(), __key)?;
                regions[__index] = __value;
            }
        }
    }
    Ok((regions).iter().cloned().collect::<Vec<_>>())
}

// Python: openciv3/world_biomes.py:86
pub(crate) fn world_biomes__assign_biomes(
    world: &crate::openciv3::world::WorldMap,
    regions: &[i64],
    mut temperature: world_biomes__Temperature,
    mut climate: crate::openciv3::world_vegetation::Climate,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    if ({
        let __needle = temperature.clone();
        let __container = {
            static __CONSTANT_py__openciv3__world_biomes__escaped_5f42414e4453:
                std::sync::OnceLock<
                    indexmap::IndexMap<world_biomes__Temperature, (i64, i64, i64, i64)>,
                > = std::sync::OnceLock::new();
            if __CONSTANT_py__openciv3__world_biomes__escaped_5f42414e4453
                .get()
                .is_none()
            {
                let __constant_value = [
                    (
                        world_biomes__Temperature::COOL,
                        (45i64, 70i64, 30i64, 60i64),
                    ),
                    (
                        world_biomes__Temperature::TEMPERATE,
                        (59i64, 77i64, 35i64, 65i64),
                    ),
                    (
                        world_biomes__Temperature::WARM,
                        (66i64, 83i64, 40i64, 70i64),
                    ),
                ]
                .into_iter()
                .collect::<indexmap::IndexMap<_, _>>();
                let _ = __CONSTANT_py__openciv3__world_biomes__escaped_5f42414e4453
                    .set(__constant_value);
            }
            __CONSTANT_py__openciv3__world_biomes__escaped_5f42414e4453
                .get()
                .ok_or("missing module constant")?
        };
        !__container.contains_key(&__needle)
    } || {
        let __needle = climate.clone();
        let __container = &((vec![
            crate::openciv3::world_vegetation::Climate::ARID,
            crate::openciv3::world_vegetation::Climate::NORMAL,
            crate::openciv3::world_vegetation::Climate::WET,
        ])
        .iter()
        .cloned()
        .collect::<Vec<_>>());
        !__container.contains(&__needle)
    }) {
        return Err("Unknown temperature or climate".to_string().into());
    }
    if ((((regions).len() as i64) != ((&(world).tiles).len() as i64)) || ({ let mut __comprehension_result_1351: Vec<bool> = Vec::new();  let __comprehension_source_1350 = ({ let __left = (world).tiles.clone(); let __right = regions.to_vec(); if false && __left.len() != __right.len() { return Err("zip() argument lengths differ".into()); } let mut __result: Vec<(crate::openciv3::world::Tile, i64,)> = Vec::new(); let __length = __left.len().min(__right.len()); let mut __left_iter = __left.into_iter(); let mut __right_iter = __right.into_iter(); for __index in 0..__length { __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap())); } __result }); for (tile, region) in __comprehension_source_1350.iter().cloned() { __comprehension_result_1351.push(((region < 0i64) != (crate::openciv3::hydrology::is_water(&tile)? || { let __needle = (tile).overlay_terrain; let __container = &({ let __tuple_value = { static __CONSTANT_py__openciv3__world_biomes__escaped_5f48494c4c59: std::sync::OnceLock<(i64, i64, i64,)> = std::sync::OnceLock::new(); if __CONSTANT_py__openciv3__world_biomes__escaped_5f48494c4c59.get().is_none() { let __constant_value = (5i64, 6i64, 10i64,); let _ = __CONSTANT_py__openciv3__world_biomes__escaped_5f48494c4c59.set(__constant_value); } __CONSTANT_py__openciv3__world_biomes__escaped_5f48494c4c59.get().ok_or("missing module constant")? }; vec![__tuple_value.0.clone(), __tuple_value.1.clone(), __tuple_value.2.clone()] }); __container.contains(&__needle) }))); } __comprehension_result_1351 }).into_iter().any(|__value| __value)) {
return Err("Biome regions must cover exactly the non-elevated land".to_string().into());
}
    let (mut latitude_limit, mut tundra_low, mut plains_high, mut desert_high): (
        i64,
        i64,
        i64,
        i64,
    ) = ({
        static __CONSTANT_py__openciv3__world_biomes__escaped_5f42414e4453: std::sync::OnceLock<
            indexmap::IndexMap<world_biomes__Temperature, (i64, i64, i64, i64)>,
        > = std::sync::OnceLock::new();
        if __CONSTANT_py__openciv3__world_biomes__escaped_5f42414e4453
            .get()
            .is_none()
        {
            let __constant_value = [
                (
                    world_biomes__Temperature::COOL,
                    (45i64, 70i64, 30i64, 60i64),
                ),
                (
                    world_biomes__Temperature::TEMPERATE,
                    (59i64, 77i64, 35i64, 65i64),
                ),
                (
                    world_biomes__Temperature::WARM,
                    (66i64, 83i64, 40i64, 70i64),
                ),
            ]
            .into_iter()
            .collect::<indexmap::IndexMap<_, _>>();
            let _ =
                __CONSTANT_py__openciv3__world_biomes__escaped_5f42414e4453.set(__constant_value);
        }
        __CONSTANT_py__openciv3__world_biomes__escaped_5f42414e4453
            .get()
            .ok_or("missing module constant")?
    })
    .get(&(temperature))
    .ok_or("missing dict key")?
    .clone();
    let mut heights: crate::strategy::height_map::HeightMap =
        crate::strategy::height_map::HeightMap____post_init__(
            crate::strategy::height_map::HeightMap {
                seed: crate::strategy::random::seed32(
                    ((world).seed)
                        .checked_add(3501i64)
                        .ok_or("integer overflow")?,
                )?,
                width: (world).width,
                height: (world).height,
                scale: 0.4f64,
                wrap_x: true,
                wrap_y: false,
                force_low_poles: true,
                _tiles_per_cell_x: 0.0f64,
                _tiles_per_cell_y: 0.0f64,
                values: vec![],
            },
        )?;
    let (mut tundra_low, mut tundra_high): (i64, i64) = (
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, tundra_low)?,
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, 93i64)?,
    );
    let mut plains_low: i64 =
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, 15i64)?;
    plains_high = crate::strategy::height_map::HeightMap__find_sea_level(
        &heights,
        (plains_high)
            .checked_add(
                (if (climate.clone() == crate::openciv3::world_vegetation::Climate::ARID) {
                    8i64
                } else {
                    0i64
                }),
            )
            .ok_or("integer overflow")?,
    )?;
    let mut desert_low: i64 =
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, 45i64)?;
    desert_high = crate::strategy::height_map::HeightMap__find_sea_level(
        &heights,
        (desert_high)
            .checked_add(
                (if (climate == crate::openciv3::world_vegetation::Climate::ARID) {
                    5i64
                } else {
                    0i64
                }),
            )
            .ok_or("integer overflow")?,
    )?;
    let mut order: Vec<i64> = ((0i64..((&(world).tiles).len() as i64)).collect::<Vec<i64>>())
        .iter()
        .cloned()
        .collect::<Vec<_>>();
    {
        let mut __random = crate::strategy::random::MapRandom____post_init__(
            crate::strategy::random::MapRandom {
                seed: crate::strategy::random::seed32(
                    ((world).seed)
                        .checked_add(47710i64)
                        .ok_or("integer overflow")?,
                )?,
                _values: vec![],
                _index: 0i64,
                _other: 21i64,
            },
        )?;
        for __index in 0..order.len().saturating_sub(1) {
            __random._index = if __random._index < 55 {
                __random._index + 1
            } else {
                1
            };
            __random._other = if __random._other < 55 {
                __random._other + 1
            } else {
                1
            };
            let __sample_index = __random._index as usize;
            let mut __value = (__random._values[__sample_index]
                - __random._values[__random._other as usize]
                + 2147483648i64)
                .rem_euclid(4294967296i64)
                - 2147483648i64;
            if __value == 2147483647i64 {
                __value -= 1;
            }
            if __value < 0 {
                __value += 2147483647i64;
            }
            __random._values[__sample_index] = __value;
            let __other = __index
                + ((__value as f64) * (1.0 / 2147483647.0) * ((order.len() - __index) as f64))
                    as usize;
            order.swap(__index, __other);
        }
        ()
    };
    let mut assignments: indexmap::IndexMap<i64, i64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut index in order {
        let mut region: i64 = rt::at(regions, index)?;
        if ((region < 0i64) || {
            let __needle = region;
            let __container = &assignments;
            __container.contains_key(&__needle)
        }) {
            continue;
        }
        let mut tile: crate::openciv3::world::Tile = rt::at(&(world).tiles, index)?;
        let mut height: i64 =
            crate::strategy::height_map::HeightMap__get_height(&heights, (tile).x, (tile).y)?;
        let mut latitude: f64 = rt::finite(
            (rt::finite(
                90.0f64
                    - rt::finite(
                        rt::float_true_div(
                            (((tile).y) as f64),
                            rt::finite((((world).height) as f64) - 1.0f64)?,
                        )? * 180.0f64,
                    )?,
            )?)
            .abs(),
        )?;
        let mut terrain: i64 = 2i64;
        if {
            let __compare_0 = plains_low;
            let __compare_1 = height;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = plains_high;
                (__compare_1 < __compare_2)
            } else {
                false
            }
        } {
            terrain = 1i64;
        } else {
            if {
                let __compare_0 = desert_low;
                let __compare_1 = height;
                if (__compare_0 <= __compare_1) {
                    let __compare_2 = desert_high;
                    (__compare_1 < __compare_2)
                } else {
                    false
                }
            } {
                terrain = 0i64;
            } else {
                if ({
                    let __compare_0 = tundra_low;
                    let __compare_1 = height;
                    if (__compare_0 <= __compare_1) {
                        let __compare_2 = tundra_high;
                        (__compare_1 < __compare_2)
                    } else {
                        false
                    }
                } && (latitude > ((latitude_limit) as f64)))
                {
                    terrain = 3i64;
                }
            }
        }
        {
            let __value = terrain;
            let __key = region;
            assignments.insert(__key, __value);
        }
    }
    let mut tiles: Vec<crate::openciv3::world::Tile> = {
        let mut __comprehension_result_1353: Vec<crate::openciv3::world::Tile> = Vec::new();
        let __comprehension_source_1352 = ({
            let __left = (world).tiles.clone();
            let __right = regions.to_vec();
            if false && __left.len() != __right.len() {
                return Err("zip() argument lengths differ".into());
            }
            let mut __result: Vec<(crate::openciv3::world::Tile, i64)> = Vec::new();
            let __length = __left.len().min(__right.len());
            let mut __left_iter = __left.into_iter();
            let mut __right_iter = __right.into_iter();
            for __index in 0..__length {
                __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
            }
            __result
        });
        for (tile, region) in __comprehension_source_1352.iter().cloned() {
            __comprehension_result_1353.push(
                (if (region >= 0i64) {
                    {
                        let mut __replacement = (tile.clone()).clone();
                        __replacement.base_terrain = (assignments)
                            .get(&(region))
                            .ok_or("missing dict key")?
                            .clone();
                        __replacement.overlay_terrain = (assignments)
                            .get(&(region))
                            .ok_or("missing dict key")?
                            .clone();
                        __replacement
                    }
                } else {
                    tile.clone()
                }),
            );
        }
        __comprehension_result_1353
    };
    for mut tile in tiles.clone() {
        if ((tile).base_terrain != 3i64) {
            continue;
        }
        for mut neighbor in crate::openciv3::world::WorldMap__neighbors(world, &tile)? {
            let mut index: i64 = (((neighbor).y)
                .checked_mul(rt::int_floor_div((world).width, 2i64)?)
                .ok_or("integer overflow")?)
            .checked_add(rt::int_floor_div((neighbor).x, 2i64)?)
            .ok_or("integer overflow")?;
            let mut current: crate::openciv3::world::Tile = rt::at(&tiles, index)?;
            if (!(crate::openciv3::hydrology::is_water(&current)?)
                && (((current).base_terrain != 3i64) && {
                    let __needle = (current).overlay_terrain;
                    let __container = &({
                        let __tuple_value = {
                            static __CONSTANT_py__openciv3__world_biomes__escaped_5f48494c4c59:
                                std::sync::OnceLock<(i64, i64, i64)> = std::sync::OnceLock::new();
                            if __CONSTANT_py__openciv3__world_biomes__escaped_5f48494c4c59
                                .get()
                                .is_none()
                            {
                                let __constant_value = (5i64, 6i64, 10i64);
                                let _ = __CONSTANT_py__openciv3__world_biomes__escaped_5f48494c4c59
                                    .set(__constant_value);
                            }
                            __CONSTANT_py__openciv3__world_biomes__escaped_5f48494c4c59
                                .get()
                                .ok_or("missing module constant")?
                        };
                        vec![
                            __tuple_value.0.clone(),
                            __tuple_value.1.clone(),
                            __tuple_value.2.clone(),
                        ]
                    });
                    !__container.contains(&__needle)
                }))
            {
                {
                    let __value = {
                        let mut __replacement = (current).clone();
                        __replacement.base_terrain = 2i64;
                        __replacement.overlay_terrain = 2i64;
                        __replacement
                    };
                    let __key = index;
                    let __index = rt::index(tiles.len(), __key)?;
                    tiles[__index] = __value;
                }
            }
        }
    }
    Ok({
        let mut __replacement = ((*world).clone()).clone();
        __replacement.tiles = (tiles).iter().cloned().collect::<Vec<_>>();
        __replacement
    })
}

// Python: openciv3/world_biomes.py:133
pub(crate) fn world_biomes__add_biomes(
    world: &crate::openciv3::world::WorldMap,
    mut temperature: world_biomes__Temperature,
    mut climate: crate::openciv3::world_vegetation::Climate,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    world_biomes__assign_biomes(
        &((*world).clone()),
        &(world_biomes__split_regions(world)?),
        temperature,
        climate,
    )
}

// Python: openciv3/world_biomes.py:37
pub(crate) fn world_biomes__split_regions__index(
    world: &crate::openciv3::world::WorldMap,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<i64> {
    Ok((((tile).y)
        .checked_mul(rt::int_floor_div((world).width, 2i64)?)
        .ok_or("integer overflow")?)
    .checked_add(rt::int_floor_div((tile).x, 2i64)?)
    .ok_or("integer overflow")?)
}

// Python: openciv3/world_biomes.py:40
pub(crate) fn world_biomes__split_regions__available(
    eligible: &[bool],
    world: &crate::openciv3::world::WorldMap,
    regions: &[i64],
    tile: &Option<crate::openciv3::world::Tile>,
) -> rt::Result<bool> {
    Ok(((tile).is_some()
        && (rt::at(
            &(eligible.to_vec()),
            world_biomes__split_regions__index(
                world,
                &((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()),
            )?,
        )? && (rt::at(
            &(regions.to_vec()),
            world_biomes__split_regions__index(
                world,
                &((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()),
            )?,
        )? == (1i64).checked_neg().ok_or("integer overflow")?))))
}

// Python: openciv3/world_extras.py:13
pub(crate) fn world_extras__add_bonus_grassland(
    world: &crate::openciv3::world::WorldMap,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    let mut random: crate::strategy::random::MapRandom =
        crate::strategy::random::MapRandom____post_init__(crate::strategy::random::MapRandom {
            seed: crate::strategy::random::seed32(
                ((world).seed)
                    .checked_add(29537i64)
                    .ok_or("integer overflow")?,
            )?,
            _values: vec![],
            _index: 0i64,
            _other: 21i64,
        })?;
    let mut order: Vec<i64> = ((0i64..((&(world).tiles).len() as i64)).collect::<Vec<i64>>())
        .iter()
        .cloned()
        .collect::<Vec<_>>();
    {
        let mut __random = random.clone();
        for __index in 0..order.len().saturating_sub(1) {
            __random._index = if __random._index < 55 {
                __random._index + 1
            } else {
                1
            };
            __random._other = if __random._other < 55 {
                __random._other + 1
            } else {
                1
            };
            let __sample_index = __random._index as usize;
            let mut __value = (__random._values[__sample_index]
                - __random._values[__random._other as usize]
                + 2147483648i64)
                .rem_euclid(4294967296i64)
                - 2147483648i64;
            if __value == 2147483647i64 {
                __value -= 1;
            }
            if __value < 0 {
                __value += 2147483647i64;
            }
            __random._values[__sample_index] = __value;
            let __other = __index
                + ((__value as f64) * (1.0 / 2147483647.0) * ((order.len() - __index) as f64))
                    as usize;
            order.swap(__index, __other);
        }
        ()
    };
    let mut tiles: Vec<crate::openciv3::world::Tile> =
        (&(world).tiles).iter().cloned().collect::<Vec<_>>();
    for mut index in order {
        let mut tile: crate::openciv3::world::Tile = rt::at(&tiles, index)?;
        if (((tile).base_terrain != 2i64)
            || ({
                if !(0..=2147483647i64).contains(&(100i64)) {
                    return Err("Random upper bound must be a nonnegative Int32".into());
                }
                let mut __map_random = random.clone();
                __map_random._index = if __map_random._index < 55 {
                    __map_random._index + 1
                } else {
                    1
                };
                __map_random._other = if __map_random._other < 55 {
                    __map_random._other + 1
                } else {
                    1
                };
                let __sample_index = __map_random._index as usize;
                let mut __value = (__map_random._values[__sample_index]
                    - __map_random._values[__map_random._other as usize]
                    + 2147483648i64)
                    .rem_euclid(4294967296i64)
                    - 2147483648i64;
                if __value == 2147483647i64 {
                    __value -= 1;
                }
                if __value < 0 {
                    __value += 2147483647i64;
                }
                __map_random._values[__sample_index] = __value;
                random = __map_random;
                ((__value as f64) * (1.0 / 2147483647.0) * ((100i64) as f64)) as i64
            } >= 25i64))
        {
            continue;
        }
        if (((tile).resource >= 0i64) || {
            let __needle = (tile).overlay_terrain;
            let __container = &({
                let __tuple_value = &((5i64, 6i64, 10i64));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                ]
            });
            __container.contains(&__needle)
        }) {
            continue;
        }
        {
            let __value = {
                let mut __replacement = (tile.clone()).clone();
                __replacement.bonuses = ((tile).bonuses | 1i64);
                __replacement
            };
            let __key = index;
            let __index = rt::index(tiles.len(), __key)?;
            tiles[__index] = __value;
        }
    }
    Ok({
        let mut __replacement = ((*world).clone()).clone();
        __replacement.tiles = (tiles).iter().cloned().collect::<Vec<_>>();
        __replacement
    })
}

// Python: openciv3/world_extras.py:28
pub(crate) fn world_extras__add_barbarian_camps(
    world: &crate::openciv3::world::WorldMap,
    resources: &[crate::openciv3::rules::Resource],
    mut activity: i64,
    starts: &[(i64, i64)],
    mut camp_rank: i64,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    if ({
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
    } || ((camp_rank < 0i64)
        || ({
            let mut __comprehension_result_1355: Vec<bool> = Vec::new();
            let __comprehension_source_1354 = ((world).tiles.clone());
            for t in __comprehension_source_1354.iter().cloned() {
                __comprehension_result_1355.push(((t).continent < 0i64));
            }
            __comprehension_result_1355
        })
        .into_iter()
        .any(|__value| __value)))
    {
        return Err("Invalid barbarian settings or missing continent labels"
            .to_string()
            .into());
    }
    let mut start_tiles: Vec<Option<crate::openciv3::world::Tile>> = {
        let mut __comprehension_result_1357: Vec<Option<crate::openciv3::world::Tile>> = Vec::new();
        let __comprehension_source_1356 = (starts.to_vec());
        for (x, y) in __comprehension_source_1356.iter().cloned() {
            __comprehension_result_1357
                .push(crate::openciv3::world::WorldMap__tile_at(world, x, y)?);
        }
        __comprehension_result_1357
    };
    if ({
        let mut __comprehension_result_1359: Vec<bool> = Vec::new();
        let __comprehension_source_1358 = (start_tiles.clone());
        for t in __comprehension_source_1358.iter().cloned() {
            __comprehension_result_1359.push((t).is_none());
        }
        __comprehension_result_1359
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("Starting location is outside the map".to_string().into());
    }
    let mut baseline: i64 = rt::int_floor_div(
        ({
            let mut __comprehension_result_1361: Vec<bool> = Vec::new();
            let __comprehension_source_1360 = ((world).tiles.clone());
            for t in __comprehension_source_1360.iter().cloned() {
                __comprehension_result_1361.push(!(crate::openciv3::hydrology::is_water(&t)?));
            }
            __comprehension_result_1361
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>(),
        100i64,
    )?;
    let mut maximum: i64 = (if (activity == (1i64).checked_neg().ok_or("integer overflow")?) {
        0i64
    } else {
        rt::round_float(rt::finite(
            ((baseline) as f64)
                * (if (activity == 2i64) {
                    1.25f64
                } else {
                    (if (activity == 3i64) {
                        1.5f64
                    } else {
                        ((1i64) as f64)
                    })
                }),
        )?)?
    });
    let mut random: crate::strategy::random::MapRandom =
        crate::strategy::random::MapRandom____post_init__(crate::strategy::random::MapRandom {
            seed: crate::strategy::random::seed32(
                ((world).seed)
                    .checked_add(763829i64)
                    .ok_or("integer overflow")?,
            )?,
            _values: vec![],
            _index: 0i64,
            _other: 21i64,
        })?;
    let mut order: Vec<i64> = ((0i64..((&(world).tiles).len() as i64)).collect::<Vec<i64>>())
        .iter()
        .cloned()
        .collect::<Vec<_>>();
    {
        let mut __random = random;
        for __index in 0..order.len().saturating_sub(1) {
            __random._index = if __random._index < 55 {
                __random._index + 1
            } else {
                1
            };
            __random._other = if __random._other < 55 {
                __random._other + 1
            } else {
                1
            };
            let __sample_index = __random._index as usize;
            let mut __value = (__random._values[__sample_index]
                - __random._values[__random._other as usize]
                + 2147483648i64)
                .rem_euclid(4294967296i64)
                - 2147483648i64;
            if __value == 2147483647i64 {
                __value -= 1;
            }
            if __value < 0 {
                __value += 2147483647i64;
            }
            __random._values[__sample_index] = __value;
            let __other = __index
                + ((__value as f64) * (1.0 / 2147483647.0) * ((order.len() - __index) as f64))
                    as usize;
            order.swap(__index, __other);
        }
        ()
    };
    let mut sizes: indexmap::IndexMap<i64, i64> = {
        let mut __counts: indexmap::IndexMap<i64, i64> = indexmap::IndexMap::new();
        for __item in ({
            let mut __comprehension_result_1363: Vec<i64> = Vec::new();
            let __comprehension_source_1362 = ((world).tiles.clone());
            for t in __comprehension_source_1362.iter().cloned() {
                __comprehension_result_1363.push((t).continent);
            }
            __comprehension_result_1363
        })
        .into_iter()
        {
            *__counts.entry(__item).or_insert(0) += 1;
        }
        __counts
    };
    let mut camps: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_1365: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_1364 = ((world).tiles.clone());
        for t in __comprehension_source_1364.iter().cloned() {
            if (((t).overlays & 128i64) != 0i64) {
                __comprehension_result_1365.insert(((t).x, (t).y));
            }
        }
        __comprehension_result_1365
    };
    let mut added: std::collections::BTreeSet<(i64, i64)> = std::collections::BTreeSet::new();
    for mut index in order {
        if (((added).len() as i64) >= maximum) {
            break;
        }
        let mut tile: crate::openciv3::world::Tile = rt::at(&(world).tiles, index)?;
        if (crate::openciv3::hydrology::is_water(&tile)?
            || ({
                let __needle = (tile).overlay_terrain;
                let __container = &({
                    let __tuple_value = &((6i64, 10i64));
                    vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                });
                __container.contains(&__needle)
            } || ((sizes.clone())
                .get(&((tile).continent))
                .cloned()
                .unwrap_or_default()
                < 15i64)))
        {
            continue;
        }
        if (((tile).resource >= 0i64) && {
            let __needle = ({
                let __source = resources;
                let __key = (tile).resource;
                &__source[rt::index(__source.len(), __key)?]
            })
            .kind;
            let __container = &({
                let __tuple_value = &((1i64, 2i64));
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            });
            __container.contains(&__needle)
        }) {
            continue;
        }
        if ({
            let mut __comprehension_result_1367: Vec<bool> = Vec::new();
            let __comprehension_source_1366 =
                (crate::strategy::grid::within_rank(world, &tile, camp_rank)?);
            for n in __comprehension_source_1366.iter().cloned() {
                __comprehension_result_1367.push({
                    let __needle = ((n).x, (n).y);
                    let __container = &camps;
                    __container.contains(&__needle)
                });
            }
            __comprehension_result_1367
        })
        .into_iter()
        .any(|__value| __value)
        {
            continue;
        }
        if ({
            let mut __comprehension_result_1369: Vec<bool> = Vec::new();
            let __comprehension_source_1368 = (start_tiles.clone());
            for start in __comprehension_source_1368.iter().cloned() {
                __comprehension_result_1369.push(
                    ((start).is_some()
                        && (crate::strategy::grid::distance(
                            &({
                                let __structural_value = (*world).clone();
                                crate::strategy::grid::DistanceMap {
                                    width: (__structural_value).width.clone(),
                                    height: (__structural_value).height.clone(),
                                    wrap_x: (__structural_value).wrap_x.clone(),
                                    wrap_y: (__structural_value).wrap_y.clone(),
                                }
                            }),
                            &({
                                let __structural_value = tile.clone();
                                crate::strategy::grid::GridPoint {
                                    x: (__structural_value).x.clone(),
                                    y: (__structural_value).y.clone(),
                                }
                            }),
                            &({
                                let __structural_value =
                                    (*(start.clone()).as_ref().ok_or("expected a value")?).clone();
                                crate::strategy::grid::GridPoint {
                                    x: (__structural_value).x.clone(),
                                    y: (__structural_value).y.clone(),
                                }
                            }),
                        )? < 6i64)),
                );
            }
            __comprehension_result_1369
        })
        .into_iter()
        .any(|__value| __value)
        {
            continue;
        }
        {
            camps.insert(((tile).x, (tile).y));
        };
        {
            added.insert(((tile).x, (tile).y));
        };
    }
    Ok({
        let mut __replacement = ((*world).clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_1371: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_1370 = ((world).tiles.clone());
            for t in __comprehension_source_1370.iter().cloned() {
                __comprehension_result_1371.push(
                    (if {
                        let __needle = ((t).x, (t).y);
                        let __container = &added;
                        __container.contains(&__needle)
                    } {
                        {
                            let mut __replacement = (t.clone()).clone();
                            __replacement.overlays = ((t).overlays | 128i64);
                            __replacement
                        }
                    } else {
                        t.clone()
                    }),
                );
            }
            __comprehension_result_1371
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    })
}

// Python: openciv3/world_resources.py:19
pub(crate) fn world_resources___default_random() -> rt::Result<crate::strategy::random::MapRandom> {
    Ok(crate::strategy::random::MapRandom____post_init__(
        crate::strategy::random::MapRandom {
            seed: 0i64,
            _values: vec![],
            _index: 0i64,
            _other: 21i64,
        },
    )?)
}

// Python: openciv3/world_resources.py:35
pub(crate) fn world_resources___Placement____post_init__(
    mut self_: world_resources___Placement,
) -> rt::Result<world_resources___Placement> {
    self_.allowed = {
        let mut __comprehension_result_1373: Vec<std::collections::BTreeSet<i64>> = Vec::new();
        let __comprehension_source_1372 = ((self_).terrains.clone());
        for terrain in __comprehension_source_1372.iter().cloned() {
            __comprehension_result_1373.push({
                let mut __result: std::collections::BTreeSet<i64> =
                    std::collections::BTreeSet::new();
                for __item in ((terrain).possible_resources.clone()).into_iter() {
                    __result.insert(__item);
                }
                __result
            });
        }
        __comprehension_result_1373
    };
    self_.random =
        crate::strategy::random::MapRandom____post_init__(crate::strategy::random::MapRandom {
            seed: crate::strategy::random::seed32(
                ((&(self_).world).seed)
                    .checked_add(29041i64)
                    .ok_or("integer overflow")?,
            )?,
            _values: vec![],
            _index: 0i64,
            _other: 21i64,
        })?;
    self_.placed = {
        let mut __comprehension_result_1375: Vec<i64> = Vec::new();
        let __comprehension_source_1374 = ((&(self_).world).tiles.clone());
        for tile in __comprehension_source_1374.iter().cloned() {
            __comprehension_result_1375.push((tile).resource);
        }
        __comprehension_result_1375
    };
    self_.continent_sizes = {
        let mut __counts: indexmap::IndexMap<i64, i64> = indexmap::IndexMap::new();
        for __item in ({
            let mut __comprehension_result_1377: Vec<i64> = Vec::new();
            let __comprehension_source_1376 = ((&(self_).world).tiles.clone());
            for tile in __comprehension_source_1376.iter().cloned() {
                __comprehension_result_1377.push((tile).continent);
            }
            __comprehension_result_1377
        })
        .into_iter()
        {
            *__counts.entry(__item).or_insert(0) += 1;
        }
        __counts
    };
    self_.order = ((0i64..((&(&(self_).world).tiles).len() as i64)).collect::<Vec<i64>>())
        .iter()
        .cloned()
        .collect::<Vec<_>>();
    Ok(self_.clone())
}

// Python: openciv3/world_resources.py:42
pub(crate) fn world_resources___Placement__index(
    self_: &world_resources___Placement,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<i64> {
    Ok((((tile).y)
        .checked_mul(rt::int_floor_div((&(self_).world).width, 2i64)?)
        .ok_or("integer overflow")?)
    .checked_add(rt::int_floor_div((tile).x, 2i64)?)
    .ok_or("integer overflow")?)
}

// Python: openciv3/world_resources.py:45
pub(crate) fn world_resources___Placement__next_to_resource(
    self_: &world_resources___Placement,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<bool> {
    Ok(({
        let mut __comprehension_result_1379: Vec<bool> = Vec::new();
        let __comprehension_source_1378 =
            (crate::openciv3::world::WorldMap__neighbors(&(self_).world, tile)?);
        for n in __comprehension_source_1378.iter().cloned() {
            __comprehension_result_1379.push(
                (rt::at(
                    &((self_).placed.clone()),
                    world_resources___Placement__index(self_, &n)?,
                )? >= 0i64),
            );
        }
        __comprehension_result_1379
    })
    .into_iter()
    .any(|__value| __value))
}

// Python: openciv3/world_resources.py:48
pub(crate) fn world_resources___Placement__coastal_enough(
    self_: &world_resources___Placement,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<bool> {
    Ok((!(crate::openciv3::hydrology::is_water(tile)?)
        || ({
            let mut __comprehension_result_1381: Vec<bool> = Vec::new();
            let __comprehension_source_1380 =
                (crate::strategy::grid::within_rank(&(self_).world, tile, (self_).workable_rank)?);
            for n in __comprehension_source_1380.iter().cloned() {
                __comprehension_result_1381.push(!(crate::openciv3::hydrology::is_water(&n)?));
            }
            __comprehension_result_1381
        })
        .into_iter()
        .any(|__value| __value)))
}

// Python: openciv3/world_resources.py:51
pub(crate) fn world_resources___Placement__appearance(
    mut self_: &mut world_resources___Placement,
    mut resource: i64,
    mut minimum: i64,
) -> rt::Result<i64> {
    let mut ratio: i64 = ({
        let __source = &(self_).resources;
        let __key = resource;
        &__source[rt::index(__source.len(), __key)?]
    })
    .appearance_ratio;
    if (ratio == 0i64) {
        ratio = (50i64)
            .checked_add(
                ({
                    let mut __comprehension_result_1383: Vec<i64> = Vec::new();
                    let __comprehension_source_1382 = ((0i64..5i64).collect::<Vec<i64>>());
                    for _ in __comprehension_source_1382.iter().cloned() {
                        __comprehension_result_1383.push({
                            if !(0..=2147483647i64).contains(&(11i64)) {
                                return Err("Random upper bound must be a nonnegative Int32".into());
                            }
                            let mut __map_random = self_.random.clone();
                            __map_random._index = if __map_random._index < 55 {
                                __map_random._index + 1
                            } else {
                                1
                            };
                            __map_random._other = if __map_random._other < 55 {
                                __map_random._other + 1
                            } else {
                                1
                            };
                            let __sample_index = __map_random._index as usize;
                            let mut __value = (__map_random._values[__sample_index]
                                - __map_random._values[__map_random._other as usize]
                                + 2147483648i64)
                                .rem_euclid(4294967296i64)
                                - 2147483648i64;
                            if __value == 2147483647i64 {
                                __value -= 1;
                            }
                            if __value < 0 {
                                __value += 2147483647i64;
                            }
                            __map_random._values[__sample_index] = __value;
                            self_.random = __map_random;
                            ((__value as f64) * (1.0 / 2147483647.0) * ((11i64) as f64)) as i64
                        });
                    }
                    __comprehension_result_1383
                })
                .into_iter()
                .sum::<i64>(),
            )
            .ok_or("integer overflow")?;
    }
    Ok((minimum).max(rt::int_floor_div(
        ((&(self_).world).civilization_count)
            .checked_mul(ratio)
            .ok_or("integer overflow")?,
        100i64,
    )?))
}

// Python: openciv3/world_resources.py:57
pub(crate) fn world_resources___Placement__place_rare(
    mut self_: world_resources___Placement,
    mut resource: i64,
    mut luxury: bool,
) -> rt::Result<()> {
    let mut target: i64 = world_resources___Placement__appearance(
        &mut self_,
        resource,
        (if luxury { 1i64 } else { 2i64 }),
    )?;
    let (mut count, mut continent): (i64, i64) =
        (0i64, (1i64).checked_neg().ok_or("integer overflow")?);
    let mut spacing: i64 = (2i64).max(
        (10i64).min(rt::int_floor_div(
            ((&(self_).world).height)
                .checked_add((&(self_).world).width)
                .ok_or("integer overflow")?,
            (if luxury { 40i64 } else { 30i64 }),
        )?),
    );
    for mut index in (self_).order.clone() {
        if (count >= target) {
            break;
        }
        let mut tile: crate::openciv3::world::Tile = rt::at(&(&(self_).world).tiles, index)?;
        if ({
            let __needle = resource;
            let __container = {
                let __source = &(self_).allowed;
                let __key = (tile).overlay_terrain;
                &__source[rt::index(__source.len(), __key)?]
            };
            !__container.contains(&__needle)
        } || world_resources___Placement__next_to_resource(&self_, &tile)?)
        {
            continue;
        }
        if (luxury
            && ((continent != (1i64).checked_neg().ok_or("integer overflow")?)
                && ((tile).continent != continent)))
        {
            continue;
        }
        if ((&(self_).continent_sizes)
            .get(&((tile).continent))
            .ok_or("missing dict key")?
            .clone()
            < (if luxury { 81i64 } else { 40i64 }))
        {
            continue;
        }
        let mut blocked: bool = false;
        for mut other in crate::strategy::grid::within_rank(&(self_).world, &tile, spacing)? {
            let mut existing: i64 = rt::at(
                &((self_).placed.clone()),
                world_resources___Placement__index(&self_, &other)?,
            )?;
            if ((existing >= 0i64)
                && ((luxury
                    && ((({
                        let __source = &(self_).resources;
                        let __key = existing;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .kind
                        == 1i64)
                        && (existing != resource)))
                    || (!(luxury) && (existing == resource))))
            {
                blocked = true;
                break;
            }
        }
        if (blocked || !(world_resources___Placement__coastal_enough(&self_, &tile)?)) {
            continue;
        }
        {
            let __index = rt::index(self_.placed.len(), index)?;
            self_.placed[__index] = resource;
        }
        count = (count).checked_add(1i64).ok_or("integer overflow")?;
        if !(luxury) {
            continue;
        }
        continent = (tile).continent;
        for _ in 0i64..4i64 {
            if ((count >= target)
                || ({
                    if !(0..=2147483647i64).contains(&(100i64)) {
                        return Err("Random upper bound must be a nonnegative Int32".into());
                    }
                    let mut __map_random = self_.random.clone();
                    __map_random._index = if __map_random._index < 55 {
                        __map_random._index + 1
                    } else {
                        1
                    };
                    __map_random._other = if __map_random._other < 55 {
                        __map_random._other + 1
                    } else {
                        1
                    };
                    let __sample_index = __map_random._index as usize;
                    let mut __value = (__map_random._values[__sample_index]
                        - __map_random._values[__map_random._other as usize]
                        + 2147483648i64)
                        .rem_euclid(4294967296i64)
                        - 2147483648i64;
                    if __value == 2147483647i64 {
                        __value -= 1;
                    }
                    if __value < 0 {
                        __value += 2147483647i64;
                    }
                    __map_random._values[__sample_index] = __value;
                    self_.random = __map_random;
                    ((__value as f64) * (1.0 / 2147483647.0) * ((100i64) as f64)) as i64
                } >= 50i64))
            {
                break;
            }
            let mut candidates: Vec<crate::openciv3::world::Tile> = {
                let mut __comprehension_result_1385: Vec<crate::openciv3::world::Tile> = Vec::new();
                let __comprehension_source_1384 =
                    (crate::openciv3::world::WorldMap__neighbors(&(self_).world, &tile)?);
                for n in __comprehension_source_1384.iter().cloned() {
                    if ({
                        let __needle = resource;
                        let __container = {
                            let __source = &(self_).allowed;
                            let __key = (n).overlay_terrain;
                            &__source[rt::index(__source.len(), __key)?]
                        };
                        __container.contains(&__needle)
                    } && ((n).continent == (tile).continent))
                    {
                        __comprehension_result_1385.push(n.clone());
                    }
                }
                __comprehension_result_1385
            };
            if !(((candidates).len() as i64) != 0i64) {
                break;
            }
            let mut neighbor: crate::openciv3::world::Tile = {
                let __values = &candidates;
                let mut __items = __values.iter();
                let mut __best = __items.next().ok_or("min() arg is an empty sequence")?;
                let mut __best_key = {
                    let _ = (*__best).clone();
                    {
                        let mut __map_random = self_.random.clone();
                        __map_random._index = if __map_random._index < 55 {
                            __map_random._index + 1
                        } else {
                            1
                        };
                        __map_random._other = if __map_random._other < 55 {
                            __map_random._other + 1
                        } else {
                            1
                        };
                        let __sample_index = __map_random._index as usize;
                        let mut __value = (__map_random._values[__sample_index]
                            - __map_random._values[__map_random._other as usize]
                            + 2147483648i64)
                            .rem_euclid(4294967296i64)
                            - 2147483648i64;
                        if __value == 2147483647i64 {
                            __value -= 1;
                        }
                        if __value < 0 {
                            __value += 2147483647i64;
                        }
                        __map_random._values[__sample_index] = __value;
                        self_.random = __map_random;
                        __value
                    }
                };
                for __candidate in __items {
                    let __key = {
                        let _ = (*__candidate).clone();
                        {
                            let mut __map_random = self_.random.clone();
                            __map_random._index = if __map_random._index < 55 {
                                __map_random._index + 1
                            } else {
                                1
                            };
                            __map_random._other = if __map_random._other < 55 {
                                __map_random._other + 1
                            } else {
                                1
                            };
                            let __sample_index = __map_random._index as usize;
                            let mut __value = (__map_random._values[__sample_index]
                                - __map_random._values[__map_random._other as usize]
                                + 2147483648i64)
                                .rem_euclid(4294967296i64)
                                - 2147483648i64;
                            if __value == 2147483647i64 {
                                __value -= 1;
                            }
                            if __value < 0 {
                                __value += 2147483647i64;
                            }
                            __map_random._values[__sample_index] = __value;
                            self_.random = __map_random;
                            __value
                        }
                    };
                    if __key < __best_key {
                        __best = __candidate;
                        __best_key = __key;
                    }
                }
                (*__best).clone()
            };
            {
                let __index = rt::index(
                    self_.placed.len(),
                    world_resources___Placement__index(&self_, &neighbor)?,
                )?;
                self_.placed[__index] = resource;
            }
            count = (count).checked_add(1i64).ok_or("integer overflow")?;
        }
    }
    Ok(())
}

// Python: openciv3/world_resources.py:98
pub(crate) fn world_resources___Placement__place_bonus(
    mut self_: world_resources___Placement,
    mut resource: i64,
) -> rt::Result<bool> {
    for mut index in (self_).order.clone() {
        let mut tile: crate::openciv3::world::Tile = rt::at(&(&(self_).world).tiles, index)?;
        if ({
            let __needle = resource;
            let __container = {
                let __source = &(self_).allowed;
                let __key = (tile).overlay_terrain;
                &__source[rt::index(__source.len(), __key)?]
            };
            __container.contains(&__needle)
        } && ((rt::at(&(self_).placed, index)? < 0i64)
            && (!(world_resources___Placement__next_to_resource(&self_, &tile)?)
                && world_resources___Placement__coastal_enough(&self_, &tile)?)))
        {
            {
                let __index = rt::index(self_.placed.len(), index)?;
                self_.placed[__index] = resource;
            }
            return Ok(true);
        }
    }
    Ok(false)
}

// Python: openciv3/world_resources.py:107
pub(crate) fn world_resources___Placement__generate(
    mut self_: world_resources___Placement,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    let mut resources: Vec<i64> = ((0i64..((&(self_).resources).len() as i64))
        .collect::<Vec<i64>>())
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    {
        let mut __random = (self_).random.clone();
        for __index in 0..resources.len().saturating_sub(1) {
            __random._index = if __random._index < 55 {
                __random._index + 1
            } else {
                1
            };
            __random._other = if __random._other < 55 {
                __random._other + 1
            } else {
                1
            };
            let __sample_index = __random._index as usize;
            let mut __value = (__random._values[__sample_index]
                - __random._values[__random._other as usize]
                + 2147483648i64)
                .rem_euclid(4294967296i64)
                - 2147483648i64;
            if __value == 2147483647i64 {
                __value -= 1;
            }
            if __value < 0 {
                __value += 2147483647i64;
            }
            __random._values[__sample_index] = __value;
            let __other = __index
                + ((__value as f64) * (1.0 / 2147483647.0) * ((resources.len() - __index) as f64))
                    as usize;
            resources.swap(__index, __other);
        }
        ()
    };
    let mut order: Vec<i64> = self_.order;
    {
        let mut __random = (self_).random.clone();
        for __index in 0..order.len().saturating_sub(1) {
            __random._index = if __random._index < 55 {
                __random._index + 1
            } else {
                1
            };
            __random._other = if __random._other < 55 {
                __random._other + 1
            } else {
                1
            };
            let __sample_index = __random._index as usize;
            let mut __value = (__random._values[__sample_index]
                - __random._values[__random._other as usize]
                + 2147483648i64)
                .rem_euclid(4294967296i64)
                - 2147483648i64;
            if __value == 2147483647i64 {
                __value -= 1;
            }
            if __value < 0 {
                __value += 2147483647i64;
            }
            __random._values[__sample_index] = __value;
            let __other = __index
                + ((__value as f64) * (1.0 / 2147483647.0) * ((order.len() - __index) as f64))
                    as usize;
            order.swap(__index, __other);
        }
        ()
    };
    self_.order = order;
    for mut kind in {
        let __tuple_items = (1i64, 2i64);
        [__tuple_items.0, __tuple_items.1]
    } {
        for mut resource in (resources).iter().copied() {
            if (({
                let __source = &(self_).resources;
                let __key = resource;
                &__source[rt::index(__source.len(), __key)?]
            })
            .kind
                == kind)
            {
                world_resources___Placement__place_rare(self_.clone(), resource, (kind == 1i64))?;
            }
        }
    }
    let mut bonus: Vec<i64> = {
        let mut __comprehension_result_1387: Vec<i64> = Vec::new();
        let __comprehension_source_1386 = (resources.clone());
        for r in __comprehension_source_1386.iter().cloned() {
            if (({
                let __source = &(self_).resources;
                let __key = r;
                &__source[rt::index(__source.len(), __key)?]
            })
            .kind
                == 0i64)
            {
                __comprehension_result_1387.push(r);
            }
        }
        __comprehension_result_1387
    };
    let mut scores: indexmap::IndexMap<i64, i64> = {
        let mut __comprehension_result_1391: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_1388 = (bonus.clone());
        for r in __comprehension_source_1388.iter().cloned() {
            {
                let (__key, __value) = (
                    r,
                    ({
                        let mut __comprehension_result_1390: Vec<i64> = Vec::new();
                        let __comprehension_source_1389 = (((self_).allowed.clone())
                            .into_iter()
                            .enumerate()
                            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                            .collect::<Vec<_>>());
                        for (t, allowed) in __comprehension_source_1389.iter().cloned() {
                            if {
                                let __needle = r;
                                let __container = &allowed;
                                __container.contains(&__needle)
                            } {
                                __comprehension_result_1390.push(
                                    (if {
                                        let __needle = t;
                                        let __container = &({
                                            let __tuple_value = &((11i64, 12i64, 13i64));
                                            vec![
                                                __tuple_value.0.clone(),
                                                __tuple_value.1.clone(),
                                                __tuple_value.2.clone(),
                                            ]
                                        });
                                        __container.contains(&__needle)
                                    } {
                                        4i64
                                    } else {
                                        1i64
                                    }),
                                );
                            }
                        }
                        __comprehension_result_1390
                    })
                    .into_iter()
                    .sum::<i64>(),
                );
                __comprehension_result_1391.insert(__key, __value);
            }
        }
        __comprehension_result_1391
    };
    let (mut placed, mut maximum): (i64, i64) = (
        0i64,
        rt::int_floor_div(((&(&(self_).world).tiles).len() as i64), 32i64)?,
    );
    for _ in 0i64..32i64 {
        if (placed >= maximum) {
            break;
        }
        {
            let mut __random = (self_).random.clone();
            for __index in 0..bonus.len().saturating_sub(1) {
                __random._index = if __random._index < 55 {
                    __random._index + 1
                } else {
                    1
                };
                __random._other = if __random._other < 55 {
                    __random._other + 1
                } else {
                    1
                };
                let __sample_index = __random._index as usize;
                let mut __value = (__random._values[__sample_index]
                    - __random._values[__random._other as usize]
                    + 2147483648i64)
                    .rem_euclid(4294967296i64)
                    - 2147483648i64;
                if __value == 2147483647i64 {
                    __value -= 1;
                }
                if __value < 0 {
                    __value += 2147483647i64;
                }
                __random._values[__sample_index] = __value;
                let __other = __index
                    + ((__value as f64) * (1.0 / 2147483647.0) * ((bonus.len() - __index) as f64))
                        as usize;
                bonus.swap(__index, __other);
            }
            ()
        };
        for mut resource in (bonus).iter().copied() {
            let mut score: i64 = (scores).get(&(resource)).ok_or("missing dict key")?.clone();
            if (score == 0i64) {
                continue;
            }
            let mut probability: i64 = (if (score < 2i64) {
                16i64
            } else {
                (if (score > 3i64) { 50i64 } else { 25i64 })
            });
            if (({
                if !(0..=2147483647i64).contains(&(100i64)) {
                    return Err("Random upper bound must be a nonnegative Int32".into());
                }
                let mut __map_random = self_.random.clone();
                __map_random._index = if __map_random._index < 55 {
                    __map_random._index + 1
                } else {
                    1
                };
                __map_random._other = if __map_random._other < 55 {
                    __map_random._other + 1
                } else {
                    1
                };
                let __sample_index = __map_random._index as usize;
                let mut __value = (__map_random._values[__sample_index]
                    - __map_random._values[__map_random._other as usize]
                    + 2147483648i64)
                    .rem_euclid(4294967296i64)
                    - 2147483648i64;
                if __value == 2147483647i64 {
                    __value -= 1;
                }
                if __value < 0 {
                    __value += 2147483647i64;
                }
                __map_random._values[__sample_index] = __value;
                self_.random = __map_random;
                ((__value as f64) * (1.0 / 2147483647.0) * ((100i64) as f64)) as i64
            } < probability)
                && world_resources___Placement__place_bonus(self_.clone(), resource)?)
            {
                placed = (placed).checked_add(1i64).ok_or("integer overflow")?;
            }
        }
    }
    Ok({
        let mut __replacement = ((self_).world.clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_1393: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_1392 = ({
                let __left = (&(self_).world).tiles.clone();
                let __right = (self_).placed.clone();
                if false && __left.len() != __right.len() {
                    return Err("zip() argument lengths differ".into());
                }
                let mut __result: Vec<(crate::openciv3::world::Tile, i64)> = Vec::new();
                let __length = __left.len().min(__right.len());
                let mut __left_iter = __left.into_iter();
                let mut __right_iter = __right.into_iter();
                for __index in 0..__length {
                    __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
                }
                __result
            });
            for (t, r) in __comprehension_source_1392.iter().cloned() {
                __comprehension_result_1393.push({
                    let mut __replacement = (t.clone()).clone();
                    __replacement.resource = r;
                    __replacement
                });
            }
            __comprehension_result_1393
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    })
}

// Python: openciv3/world_resources.py:135
pub(crate) fn world_resources__add_resources(
    world: &crate::openciv3::world::WorldMap,
    resources: &[crate::openciv3::rules::Resource],
    terrains: &[world_resources__ResourceTerrain],
    mut workable_rank: i64,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    if ((workable_rank < 0i64) || ((world).civilization_count < 0i64)) {
        return Err("Invalid resource placement settings".to_string().into());
    }
    if ({
        let mut __comprehension_result_1395: Vec<bool> = Vec::new();
        let __comprehension_source_1394 = ((world).tiles.clone());
        for t in __comprehension_source_1394.iter().cloned() {
            __comprehension_result_1395.push(
                (((t).continent < 0i64)
                    || (!({
                        let __compare_0 = 0i64;
                        let __compare_1 = (t).overlay_terrain;
                        if (__compare_0 <= __compare_1) {
                            let __compare_2 = ((terrains).len() as i64);
                            (__compare_1 < __compare_2)
                        } else {
                            false
                        }
                    }) || !({
                        let __compare_0 = (1i64).checked_neg().ok_or("integer overflow")?;
                        let __compare_1 = (t).resource;
                        if (__compare_0 <= __compare_1) {
                            let __compare_2 = ((resources).len() as i64);
                            (__compare_1 < __compare_2)
                        } else {
                            false
                        }
                    }))),
            );
        }
        __comprehension_result_1395
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err(
            "Resource placement requires labeled continents and valid terrain/resource IDs"
                .to_string()
                .into(),
        );
    }
    if ({
        let mut __comprehension_result_1397: Vec<bool> = Vec::new();
        let __comprehension_source_1396 = (resources.to_vec());
        for r in __comprehension_source_1396.iter().cloned() {
            __comprehension_result_1397.push(((r).appearance_ratio < 0i64));
        }
        __comprehension_result_1397
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("Resource appearance ratios must be nonnegative"
            .to_string()
            .into());
    }
    world_resources___Placement__generate(world_resources___Placement____post_init__(
        world_resources___Placement {
            world: (*world).clone(),
            resources: (resources).iter().cloned().collect::<Vec<_>>(),
            terrains: (terrains).iter().cloned().collect::<Vec<_>>(),
            workable_rank: workable_rank,
            allowed: vec![],
            random: world_resources___default_random()?,
            placed: vec![],
            continent_sizes: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
            order: vec![],
        },
    )?)
}

// Python: openciv3/world_rivers.py:14
pub(crate) fn world_rivers___default_random() -> rt::Result<crate::strategy::random::MapRandom> {
    Ok(crate::strategy::random::MapRandom____post_init__(
        crate::strategy::random::MapRandom {
            seed: 0i64,
            _values: vec![],
            _index: 0i64,
            _other: 21i64,
        },
    )?)
}

// Python: openciv3/world_rivers.py:18
pub(crate) fn world_rivers___default_heights() -> rt::Result<crate::strategy::height_map::HeightMap>
{
    Ok(crate::strategy::height_map::HeightMap____post_init__(
        crate::strategy::height_map::HeightMap {
            seed: 0i64,
            width: 2i64,
            height: 2i64,
            scale: 0.1f64,
            wrap_x: true,
            wrap_y: false,
            force_low_poles: true,
            _tiles_per_cell_x: 0.0f64,
            _tiles_per_cell_y: 0.0f64,
            values: vec![],
        },
    )?)
}

// Python: openciv3/world_rivers.py:29
pub(crate) fn world_rivers___RiverGrowth____post_init__(
    mut self_: world_rivers___RiverGrowth,
) -> rt::Result<world_rivers___RiverGrowth> {
    self_.random =
        crate::strategy::random::MapRandom____post_init__(crate::strategy::random::MapRandom {
            seed: crate::strategy::random::seed32(
                ((&(self_).world).seed)
                    .checked_add(703506i64)
                    .ok_or("integer overflow")?,
            )?,
            _values: vec![],
            _index: 0i64,
            _other: 21i64,
        })?;
    self_.heights = crate::strategy::height_map::HeightMap____post_init__(
        crate::strategy::height_map::HeightMap {
            seed: crate::strategy::random::seed32(
                ((&(self_).world).seed)
                    .checked_add(138426i64)
                    .ok_or("integer overflow")?,
            )?,
            width: (&(self_).world).width,
            height: (&(self_).world).height,
            scale: 0.1f64,
            wrap_x: true,
            wrap_y: false,
            force_low_poles: true,
            _tiles_per_cell_x: 0.0f64,
            _tiles_per_cell_y: 0.0f64,
            values: vec![],
        },
    )?;
    self_.flags = {
        let mut __comprehension_result_1399: Vec<i64> = Vec::new();
        let __comprehension_source_1398 = ((&(self_).world).tiles.clone());
        for tile in __comprehension_source_1398.iter().cloned() {
            __comprehension_result_1399.push((tile).river_connections);
        }
        __comprehension_result_1399
    };
    Ok(self_.clone())
}

// Python: openciv3/world_rivers.py:34
pub(crate) fn world_rivers___RiverGrowth__index(
    self_: &world_rivers___RiverGrowth,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<i64> {
    Ok((((tile).y)
        .checked_mul(rt::int_floor_div((&(self_).world).width, 2i64)?)
        .ok_or("integer overflow")?)
    .checked_add(rt::int_floor_div((tile).x, 2i64)?)
    .ok_or("integer overflow")?)
}

// Python: openciv3/world_rivers.py:37
pub(crate) fn world_rivers___RiverGrowth__neighbor(
    self_: &world_rivers___RiverGrowth,
    tile: &crate::openciv3::world::Tile,
    mut direction: i64,
) -> rt::Result<Option<crate::openciv3::world::Tile>> {
    let (mut dx, mut dy): (i64, i64) = rt::at(
        &({
            let __tuple_value = {
                static __CONSTANT_py__openciv3__world_rivers__escaped_5f4f464653455453:
                    std::sync::OnceLock<(
                        (i64, i64),
                        (i64, i64),
                        (i64, i64),
                        (i64, i64),
                        (i64, i64),
                        (i64, i64),
                        (i64, i64),
                        (i64, i64),
                    )> = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__world_rivers__escaped_5f4f464653455453
                    .get()
                    .is_none()
                {
                    let __constant_value = (
                        (0i64, (2i64).checked_neg().ok_or("integer overflow")?),
                        (1i64, (1i64).checked_neg().ok_or("integer overflow")?),
                        (2i64, 0i64),
                        (1i64, 1i64),
                        (0i64, 2i64),
                        ((1i64).checked_neg().ok_or("integer overflow")?, 1i64),
                        ((2i64).checked_neg().ok_or("integer overflow")?, 0i64),
                        (
                            (1i64).checked_neg().ok_or("integer overflow")?,
                            (1i64).checked_neg().ok_or("integer overflow")?,
                        ),
                    );
                    let _ = __CONSTANT_py__openciv3__world_rivers__escaped_5f4f464653455453
                        .set(__constant_value);
                }
                __CONSTANT_py__openciv3__world_rivers__escaped_5f4f464653455453
                    .get()
                    .ok_or("missing module constant")?
            };
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
                __tuple_value.3.clone(),
                __tuple_value.4.clone(),
                __tuple_value.5.clone(),
                __tuple_value.6.clone(),
                __tuple_value.7.clone(),
            ]
        }),
        direction,
    )?;
    crate::openciv3::world::WorldMap__tile_at(
        &(self_).world,
        ((tile).x).checked_add(dx).ok_or("integer overflow")?,
        ((tile).y).checked_add(dy).ok_or("integer overflow")?,
    )
}

// Python: openciv3/world_rivers.py:41
pub(crate) fn world_rivers___RiverGrowth__borders(
    self_: &world_rivers___RiverGrowth,
    tile: &Option<crate::openciv3::world::Tile>,
) -> rt::Result<bool> {
    Ok(((tile).is_some()
        && (rt::at(
            &((self_).flags.clone()),
            world_rivers___RiverGrowth__index(
                self_,
                &((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()),
            )?,
        )?) != 0))
}

// Python: openciv3/world_rivers.py:44
pub(crate) fn world_rivers___RiverGrowth__edge(
    mut self_: world_rivers___RiverGrowth,
    tile: &crate::openciv3::world::Tile,
    mut direction: i64,
) -> rt::Result<()> {
    {
        let __index = rt::index(
            self_.flags.len(),
            world_rivers___RiverGrowth__index(&self_, tile)?,
        )?;
        self_.flags[__index] = (rt::at(
            &((self_).flags.clone()),
            world_rivers___RiverGrowth__index(&self_, tile)?,
        )? | rt::int_lshift(1i64, direction)?);
    }
    let mut neighbor: Option<crate::openciv3::world::Tile> =
        world_rivers___RiverGrowth__neighbor(&self_, tile, direction)?;
    if (neighbor).is_some() {
        {
            let __index = rt::index(
                self_.flags.len(),
                world_rivers___RiverGrowth__index(
                    &self_,
                    &((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?,
            )?;
            self_.flags[__index] = (rt::at(
                &((self_).flags.clone()),
                world_rivers___RiverGrowth__index(
                    &self_,
                    &((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?,
            )? | rt::int_lshift(
                1i64,
                rt::int_modulo(
                    (direction).checked_add(4i64).ok_or("integer overflow")?,
                    8i64,
                )?,
            )?);
        }
    }
    Ok(())
}

// Python: openciv3/world_rivers.py:50
pub(crate) fn world_rivers___RiverGrowth__mark(
    self_: &world_rivers___RiverGrowth,
    tile: &crate::openciv3::world::Tile,
    mut incoming: i64,
) -> rt::Result<()> {
    if {
        let __needle = incoming;
        let __container = &({
            let __tuple_value = &((1i64, 5i64));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        __container.contains(&__needle)
    } {
        world_rivers___RiverGrowth__edge((*self_).clone(), tile, 3i64)?;
    } else {
        world_rivers___RiverGrowth__edge((*self_).clone(), tile, 5i64)?;
    }
    if (incoming == 7i64) {
        let mut neighbor: Option<crate::openciv3::world::Tile> =
            world_rivers___RiverGrowth__neighbor(self_, tile, 3i64)?;
        if ((neighbor).is_some()
            && (rt::at(
                &((self_).flags.clone()),
                world_rivers___RiverGrowth__index(
                    self_,
                    &((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?,
            )? & rt::int_lshift(1i64, 3i64)?)
                != 0)
        {
            world_rivers___RiverGrowth__edge(
                (*self_).clone(),
                &((*(neighbor).as_ref().ok_or("expected a value")?).clone()),
                5i64,
            )?;
        }
    } else {
        if (incoming == 1i64) {
            let mut neighbor: Option<crate::openciv3::world::Tile> =
                world_rivers___RiverGrowth__neighbor(self_, tile, 5i64)?;
            if ((neighbor).is_some()
                && (rt::at(
                    &((self_).flags.clone()),
                    world_rivers___RiverGrowth__index(
                        self_,
                        &((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone()),
                    )?,
                )? & rt::int_lshift(1i64, 5i64)?)
                    != 0)
            {
                world_rivers___RiverGrowth__edge(
                    (*self_).clone(),
                    &((*(neighbor).as_ref().ok_or("expected a value")?).clone()),
                    3i64,
                )?;
            }
        }
    }
    Ok(())
}

// Python: openciv3/world_rivers.py:64
pub(crate) fn world_rivers___RiverGrowth__score(
    self_: &world_rivers___RiverGrowth,
    tile: &crate::openciv3::world::Tile,
    mut direction: i64,
) -> rt::Result<i64> {
    let mut neighbor: Option<crate::openciv3::world::Tile> =
        world_rivers___RiverGrowth__neighbor(self_, tile, direction)?;
    if ((neighbor).is_none() || world_rivers___RiverGrowth__borders(self_, &neighbor)?) {
        return Ok((2147483648i64).checked_neg().ok_or("integer overflow")?);
    }
    let mut onward: Vec<Option<crate::openciv3::world::Tile>> = {
        let mut __comprehension_result_1401: Vec<Option<crate::openciv3::world::Tile>> = Vec::new();
        let __comprehension_source_1400 = ({
            let __tuple_value = &((
                rt::int_modulo(
                    (direction).checked_add(6i64).ok_or("integer overflow")?,
                    8i64,
                )?,
                rt::int_modulo(
                    (direction).checked_add(2i64).ok_or("integer overflow")?,
                    8i64,
                )?,
                direction,
            ));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        for d in __comprehension_source_1400.iter().cloned() {
            __comprehension_result_1401.push(world_rivers___RiverGrowth__neighbor(
                self_,
                &((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone()),
                d,
            )?);
        }
        __comprehension_result_1401
    };
    if ({
        let mut __comprehension_result_1403: Vec<bool> = Vec::new();
        let __comprehension_source_1402 = (onward.clone());
        for other in __comprehension_source_1402.iter().cloned() {
            __comprehension_result_1403.push(world_rivers___RiverGrowth__borders(self_, &other)?);
        }
        __comprehension_result_1403
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Ok((2147483648i64).checked_neg().ok_or("integer overflow")?);
    }
    if crate::openciv3::hydrology::is_water(
        &((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone()),
    )? {
        return Ok(1000i64);
    }
    if ({
        let mut __comprehension_result_1405: Vec<bool> = Vec::new();
        let __comprehension_source_1404 = (onward.clone());
        for other in __comprehension_source_1404.iter().cloned() {
            __comprehension_result_1405.push(
                ((other).is_some()
                    && crate::openciv3::hydrology::is_water(
                        &((*(other.clone()).as_ref().ok_or("expected a value")?).clone()),
                    )?),
            );
        }
        __comprehension_result_1405
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Ok(500i64);
    }
    Ok((crate::strategy::height_map::HeightMap__get_height(
        &(self_).heights,
        ((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone()).x,
        ((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone()).y,
    )?)
    .checked_sub(crate::strategy::height_map::HeightMap__get_height(
        &(self_).heights,
        (tile).x,
        (tile).y,
    )?)
    .ok_or("integer overflow")?)
}

// Python: openciv3/world_rivers.py:79
pub(crate) fn world_rivers___RiverGrowth__flow(
    mut self_: &mut world_rivers___RiverGrowth,
    tile: &Option<crate::openciv3::world::Tile>,
    mut incoming: i64,
    mut depth: i64,
) -> rt::Result<()> {
    if ((depth > 16i64)
        || ((tile).is_none()
            || crate::openciv3::hydrology::is_water(
                &((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()),
            )?))
    {
        return Ok(());
    }
    world_rivers___RiverGrowth__mark(
        self_,
        &((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()),
        incoming,
    )?;
    let mut directions: (i64, i64, i64) = (
        rt::int_modulo(
            (incoming).checked_add(6i64).ok_or("integer overflow")?,
            8i64,
        )?,
        rt::int_modulo(
            (incoming).checked_add(2i64).ok_or("integer overflow")?,
            8i64,
        )?,
        incoming,
    );
    let mut scores: Vec<i64> = {
        let mut __comprehension_result_1407: Vec<i64> = Vec::new();
        let __comprehension_source_1406 = ({
            let __tuple_value = &(directions.clone());
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        for direction in __comprehension_source_1406.iter().cloned() {
            __comprehension_result_1407.push(world_rivers___RiverGrowth__score(
                self_,
                &((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()),
                direction,
            )?);
        }
        __comprehension_result_1407
    };
    let mut best: i64 = {
        let __values = &((0i64..3i64).collect::<Vec<i64>>());
        let mut __items = __values.iter();
        let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
        let mut __best_key = {
            let index = (*__best).clone();
            rt::at(&scores, index)?
        };
        for __candidate in __items {
            let __key = {
                let index = (*__candidate).clone();
                rt::at(&scores, index)?
            };
            if __key > __best_key {
                __best = __candidate;
                __best_key = __key;
            }
        }
        (*__best).clone()
    };
    if (rt::at(&scores, best)? == (2147483648i64).checked_neg().ok_or("integer overflow")?) {
        return Ok(());
    }
    world_rivers___RiverGrowth__flow(
        &mut (*self_).clone(),
        &(world_rivers___RiverGrowth__neighbor(
            self_,
            &((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()),
            rt::at(
                &({
                    let __tuple_value = &directions;
                    vec![
                        __tuple_value.0.clone(),
                        __tuple_value.1.clone(),
                        __tuple_value.2.clone(),
                    ]
                }),
                best,
            )?,
        )?),
        rt::at(
            &({
                let __tuple_value = &directions;
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                ]
            }),
            best,
        )?,
        (depth).checked_add(1i64).ok_or("integer overflow")?,
    )?;
    let mut second: i64 = {
        let __values = &({
            let mut __comprehension_result_1409: Vec<i64> = Vec::new();
            let __comprehension_source_1408 = ((0i64..3i64).collect::<Vec<i64>>());
            for index in __comprehension_source_1408.iter().cloned() {
                if (index != best) {
                    __comprehension_result_1409.push(index);
                }
            }
            __comprehension_result_1409
        });
        let mut __items = __values.iter();
        let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
        let mut __best_key = {
            let index = (*__best).clone();
            rt::at(&scores, index)?
        };
        for __candidate in __items {
            let __key = {
                let index = (*__candidate).clone();
                rt::at(&scores, index)?
            };
            if __key > __best_key {
                __best = __candidate;
                __best_key = __key;
            }
        }
        (*__best).clone()
    };
    if ((rt::at(&scores, second)? != (2147483648i64).checked_neg().ok_or("integer overflow")?)
        && ((rt::at(&scores, best)?
            < (rt::at(&scores, second)?)
                .checked_add(30i64)
                .ok_or("integer overflow")?)
            && ({
                if !(0..=2147483647i64).contains(&(100i64)) {
                    return Err("Random upper bound must be a nonnegative Int32".into());
                }
                let mut __map_random = self_.random.clone();
                __map_random._index = if __map_random._index < 55 {
                    __map_random._index + 1
                } else {
                    1
                };
                __map_random._other = if __map_random._other < 55 {
                    __map_random._other + 1
                } else {
                    1
                };
                let __sample_index = __map_random._index as usize;
                let mut __value = (__map_random._values[__sample_index]
                    - __map_random._values[__map_random._other as usize]
                    + 2147483648i64)
                    .rem_euclid(4294967296i64)
                    - 2147483648i64;
                if __value == 2147483647i64 {
                    __value -= 1;
                }
                if __value < 0 {
                    __value += 2147483647i64;
                }
                __map_random._values[__sample_index] = __value;
                self_.random = __map_random;
                ((__value as f64) * (1.0 / 2147483647.0) * ((100i64) as f64)) as i64
            } < 33i64)))
    {
        world_rivers___RiverGrowth__flow(
            &mut (*self_).clone(),
            &(world_rivers___RiverGrowth__neighbor(
                self_,
                &((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()),
                rt::at(
                    &({
                        let __tuple_value = &directions;
                        vec![
                            __tuple_value.0.clone(),
                            __tuple_value.1.clone(),
                            __tuple_value.2.clone(),
                        ]
                    }),
                    second,
                )?,
            )?),
            rt::at(
                &({
                    let __tuple_value = &directions;
                    vec![
                        __tuple_value.0.clone(),
                        __tuple_value.1.clone(),
                        __tuple_value.2.clone(),
                    ]
                }),
                second,
            )?,
            (depth).checked_add(1i64).ok_or("integer overflow")?,
        )?;
    }
    Ok(())
}

// Python: openciv3/world_rivers.py:93
pub(crate) fn world_rivers___RiverGrowth__generate(
    mut self_: &mut world_rivers___RiverGrowth,
    mut ocean_percent: i64,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    let mut sources: Vec<crate::openciv3::world::Tile> = {
        let mut __comprehension_result_1413: Vec<crate::openciv3::world::Tile> = Vec::new();
        let __comprehension_source_1410 = ((&(self_).world).tiles.clone());
        for tile in __comprehension_source_1410.iter().cloned() {
            if ({
                let __needle = (tile).overlay_terrain;
                let __container = &({
                    let __tuple_value = &((5i64, 6i64, 10i64));
                    vec![
                        __tuple_value.0.clone(),
                        __tuple_value.1.clone(),
                        __tuple_value.2.clone(),
                    ]
                });
                __container.contains(&__needle)
            } && ({
                let mut __comprehension_result_1412: Vec<bool> = Vec::new();
                let __comprehension_source_1411 =
                    (crate::openciv3::world::WorldMap__neighbors(&(self_).world, &tile)?);
                for n in __comprehension_source_1411.iter().cloned() {
                    __comprehension_result_1412.push(!(crate::openciv3::hydrology::is_water(&n)?));
                }
                __comprehension_result_1412
            })
            .into_iter()
            .all(|__value| __value))
            {
                __comprehension_result_1413.push(tile.clone());
            }
        }
        __comprehension_result_1413
    };
    {
        let mut __random = (self_).random.clone();
        for __index in 0..sources.len().saturating_sub(1) {
            __random._index = if __random._index < 55 {
                __random._index + 1
            } else {
                1
            };
            __random._other = if __random._other < 55 {
                __random._other + 1
            } else {
                1
            };
            let __sample_index = __random._index as usize;
            let mut __value = (__random._values[__sample_index]
                - __random._values[__random._other as usize]
                + 2147483648i64)
                .rem_euclid(4294967296i64)
                - 2147483648i64;
            if __value == 2147483647i64 {
                __value -= 1;
            }
            if __value < 0 {
                __value += 2147483647i64;
            }
            __random._values[__sample_index] = __value;
            let __other = __index
                + ((__value as f64) * (1.0 / 2147483647.0) * ((sources.len() - __index) as f64))
                    as usize;
            sources.swap(__index, __other);
        }
        ()
    };
    let mut expected_land: i64 = rt::int_float(rt::finite(
        (((&(&(self_).world).tiles).len() as i64) as f64)
            * rt::finite(
                ((1i64) as f64) - rt::float_true_div(((ocean_percent) as f64), 100.0f64)?,
            )?,
    )?)?;
    let mut maximum: i64 = rt::int_float(rt::float_true_div(((expected_land) as f64), 100.0f64)?)?;
    let mut started: i64 = 0i64;
    for mut tile in sources {
        if (started == maximum) {
            break;
        }
        if world_rivers___RiverGrowth__borders(self_, &(Some(tile.clone())))? {
            continue;
        }
        let mut directions: (i64, i64, i64, i64) = (1i64, 7i64, 5i64, 3i64);
        let mut scores: Vec<i64> = {
            let mut __comprehension_result_1415: Vec<i64> = Vec::new();
            let __comprehension_source_1414 = ({
                let __tuple_value = &(directions.clone());
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                    __tuple_value.3.clone(),
                ]
            });
            for direction in __comprehension_source_1414.iter().cloned() {
                __comprehension_result_1415
                    .push(world_rivers___RiverGrowth__score(self_, &tile, direction)?);
            }
            __comprehension_result_1415
        };
        let mut best: i64 = {
            let __values = &((0i64..4i64).collect::<Vec<i64>>());
            let mut __items = __values.iter();
            let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
            let mut __best_key = {
                let index = (*__best).clone();
                rt::at(&scores, index)?
            };
            for __candidate in __items {
                let __key = {
                    let index = (*__candidate).clone();
                    rt::at(&scores, index)?
                };
                if __key > __best_key {
                    __best = __candidate;
                    __best_key = __key;
                }
            }
            (*__best).clone()
        };
        if (rt::at(&scores, best)? != (2147483648i64).checked_neg().ok_or("integer overflow")?) {
            started = (started).checked_add(1i64).ok_or("integer overflow")?;
            world_rivers___RiverGrowth__flow(
                &mut self_,
                &(Some(tile)),
                rt::at(
                    &({
                        let __tuple_value = &directions;
                        vec![
                            __tuple_value.0.clone(),
                            __tuple_value.1.clone(),
                            __tuple_value.2.clone(),
                            __tuple_value.3.clone(),
                        ]
                    }),
                    best,
                )?,
                0i64,
            )?;
        }
    }
    let mut world: crate::openciv3::world::WorldMap = {
        let mut __replacement = ((self_).world.clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_1417: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_1416 = ({
                let __left = (&(self_).world).tiles.clone();
                let __right = (self_).flags.clone();
                if false && __left.len() != __right.len() {
                    return Err("zip() argument lengths differ".into());
                }
                let mut __result: Vec<(crate::openciv3::world::Tile, i64)> = Vec::new();
                let __length = __left.len().min(__right.len());
                let mut __left_iter = __left.into_iter();
                let mut __right_iter = __right.into_iter();
                for __index in 0..__length {
                    __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
                }
                __result
            });
            for (t, flags) in __comprehension_source_1416.iter().cloned() {
                __comprehension_result_1417.push({
                    let mut __replacement = (t.clone()).clone();
                    __replacement.river_connections = flags;
                    __replacement
                });
            }
            __comprehension_result_1417
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    };
    Ok({
        let mut __replacement = (world.clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_1419: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_1418 = ((world).tiles.clone());
            for t in __comprehension_source_1418.iter().cloned() {
                __comprehension_result_1419.push({
                    let mut __replacement = (t.clone()).clone();
                    __replacement.river_connections =
                        crate::openciv3::hydrology::river_edges(&world, &t)?;
                    __replacement
                });
            }
            __comprehension_result_1419
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    })
}

// Python: openciv3/world_rivers.py:116
pub(crate) fn world_rivers__add_rivers(
    world: &crate::openciv3::world::WorldMap,
    mut ocean_percent: i64,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    if {
        let __needle = ocean_percent;
        let __container = &({
            let __tuple_value = &((60i64, 70i64, 80i64));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        !__container.contains(&__needle)
    } {
        return Err("Ocean coverage must be 60, 70 or 80 percent"
            .to_string()
            .into());
    }
    world_rivers___RiverGrowth__generate(
        &mut world_rivers___RiverGrowth____post_init__(world_rivers___RiverGrowth {
            world: (*world).clone(),
            random: world_rivers___default_random()?,
            heights: world_rivers___default_heights()?,
            flags: vec![],
        })?,
        ocean_percent,
    )
}

// Python: openciv3/world_rivers.py:122
pub(crate) fn world_rivers__add_flood_plains(
    world: &crate::openciv3::world::WorldMap,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    Ok({
        let mut __replacement = ((*world).clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_1421: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_1420 = ((world).tiles.clone());
            for tile in __comprehension_source_1420.iter().cloned() {
                __comprehension_result_1421.push(
                    (if (((tile).base_terrain == 0i64)
                        && (((tile).overlay_terrain == 0i64)
                            && (crate::openciv3::hydrology::river_edges(world, &tile)?) != 0))
                    {
                        {
                            let mut __replacement = (tile.clone()).clone();
                            __replacement.base_terrain = 4i64;
                            __replacement.overlay_terrain = 4i64;
                            __replacement
                        }
                    } else {
                        tile.clone()
                    }),
                );
            }
            __comprehension_result_1421
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    })
}

// Python: openciv3/world_shape.py:34
pub(crate) fn world_shape__label_continents(
    world: &crate::openciv3::world::WorldMap,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    let mut labels: indexmap::IndexMap<(i64, i64), i64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    let mut identifier: i64 = 0i64;
    for mut origin in (&(world).tiles).iter() {
        let mut point: (i64, i64) = ((origin).x, (origin).y);
        if {
            let __needle = point.clone();
            let __container = &labels;
            __container.contains_key(&__needle)
        } {
            continue;
        }
        {
            let __value = identifier;
            let __key = point;
            labels.insert(__key, __value);
        }
        let mut pending: Vec<crate::openciv3::world::Tile> = vec![(*origin).clone()];
        let mut cursor: i64 = 0i64;
        while (cursor < ((pending).len() as i64)) {
            let mut tile: crate::openciv3::world::Tile = rt::at(&pending, cursor)?;
            cursor = (cursor).checked_add(1i64).ok_or("integer overflow")?;
            for mut neighbor in crate::openciv3::world::WorldMap__neighbors(world, &tile)? {
                point = ((neighbor).x, (neighbor).y);
                if ({
                    let __needle = point.clone();
                    let __container = &labels;
                    !__container.contains_key(&__needle)
                } && ((crate::openciv3::hydrology::is_water(&neighbor)?
                    == crate::openciv3::hydrology::is_water(&tile)?)
                    && !(crate::openciv3::hydrology::land_strip(world, &tile, &neighbor)?)))
                {
                    {
                        let __value = identifier;
                        let __key = point;
                        labels.insert(__key, __value);
                    }
                    {
                        pending.push(neighbor);
                    };
                }
            }
        }
        identifier = (identifier).checked_add(1i64).ok_or("integer overflow")?;
    }
    Ok({
        let mut __replacement = ((*world).clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_1423: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_1422 = ((world).tiles.clone());
            for tile in __comprehension_source_1422.iter().cloned() {
                __comprehension_result_1423.push({
                    let mut __replacement = (tile.clone()).clone();
                    __replacement.continent = (labels)
                        .get(&(((tile).x, (tile).y)))
                        .ok_or("missing dict key")?
                        .clone();
                    __replacement
                });
            }
            __comprehension_result_1423
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    })
}

// Python: openciv3/world_shape.py:57
pub(crate) fn world_shape__from_heights(
    height: &crate::strategy::height_map::HeightMap,
    size: &crate::openciv3::world_size::WorldSize,
    mut seed: i64,
    mut ocean_coverage: i64,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    if ({
        let __boolean_123705958954000 = rt::int_modulo((height).width, 2i64)?;
        if (__boolean_123705958954000) != 0 {
            __boolean_123705958954000
        } else {
            rt::int_modulo((height).height, 2i64)?
        }
    }) != 0
    {
        return Err("Generated staggered maps require even dimensions"
            .to_string()
            .into());
    }
    if {
        let __needle = ocean_coverage;
        let __container = &({
            let __tuple_value = &((60i64, 70i64, 80i64));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        !__container.contains(&__needle)
    } {
        return Err("Ocean coverage must be 60, 70 or 80 percent"
            .to_string()
            .into());
    }
    let mut shore: i64 =
        crate::strategy::height_map::HeightMap__find_sea_level(height, ocean_coverage)?;
    let mut medium: i64 = crate::strategy::height_map::HeightMap__find_sea_level(
        &((*height).clone()),
        rt::int_float(rt::finite(((ocean_coverage) as f64) * 0.9f64)?)?,
    )?;
    let mut deep: i64 = crate::strategy::height_map::HeightMap__find_sea_level(
        &((*height).clone()),
        rt::int_float(rt::finite(((ocean_coverage) as f64) * 0.7f64)?)?,
    )?;
    let mut tiles: Vec<crate::openciv3::world::Tile> = vec![];
    for mut y in 0i64..(height).height {
        for mut x in rt::integer_range(rt::int_modulo(y, 2i64)?, (height).width, 2i64)? {
            let mut value: i64 = crate::strategy::height_map::HeightMap__get_height(height, x, y)?;
            let mut terrain: i64 = (if (value > shore) {
                2i64
            } else {
                (if (value > medium) {
                    11i64
                } else {
                    (if (value > deep) { 12i64 } else { 13i64 })
                })
            });
            {
                tiles.push(crate::openciv3::world::Tile {
                    x: x,
                    y: y,
                    resource: (1i64).checked_neg().ok_or("integer overflow")?,
                    texture_index: (1i64).checked_neg().ok_or("integer overflow")?,
                    texture_file: (1i64).checked_neg().ok_or("integer overflow")?,
                    base_terrain: terrain,
                    overlay_terrain: terrain,
                    continent: (1i64).checked_neg().ok_or("integer overflow")?,
                    river_connections: 0i64,
                    overlays: 0i64,
                    bonuses: 0i64,
                    fog_of_war: 0i64,
                    city: (1i64).checked_neg().ok_or("integer overflow")?,
                    colony: (1i64).checked_neg().ok_or("integer overflow")?,
                    barbarian_tribe: (1i64).checked_neg().ok_or("integer overflow")?,
                    victory_point: false,
                    ruin: 0i64,
                    border: (1i64).checked_neg().ok_or("integer overflow")?,
                    freshwater: None,
                    installation_owner: None,
                });
            };
        }
    }
    let mut world: crate::openciv3::world::WorldMap = crate::openciv3::world::WorldMap {
        width: (height).width,
        height: (height).height,
        wrap_x: (height).wrap_x,
        wrap_y: (height).wrap_y,
        polar_ice: false,
        seed: seed,
        civilization_count: (size).civilization_count,
        civilization_distance: (size).civilization_distance,
        resources: vec![],
        tiles: (tiles).iter().cloned().collect::<Vec<_>>(),
        cities: vec![],
        units: vec![],
        starts: vec![],
    };
    world_shape__label_continents(&world)
}

// Python: openciv3/world_shape.py:77
pub(crate) fn world_shape__landmass_sizes(
    world: &crate::openciv3::world::WorldMap,
) -> rt::Result<Vec<i64>> {
    let mut counts: indexmap::IndexMap<i64, i64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut tile in (&(world).tiles).iter() {
        if !(crate::openciv3::hydrology::is_water(tile)?) {
            {
                let __value = ({
                    let __key = (tile).continent;
                    let __default = 0i64;
                    counts.get(&__key).cloned().unwrap_or(__default)
                })
                .checked_add(1i64)
                .ok_or("integer overflow")?;
                let __key = (tile).continent;
                counts.insert(__key, __value);
            }
        }
    }
    Ok(({
        let mut __sorted = (counts).values().cloned().collect::<Vec<_>>();
        let __reverse = true;
        __sorted.sort_by(|left, right| {
            if __reverse {
                right.cmp(left)
            } else {
                left.cmp(right)
            }
        });
        __sorted
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>())
}

// Python: openciv3/world_shape.py:85
pub(crate) fn world_shape__acceptable(
    world: &crate::openciv3::world::WorldMap,
    mut landform: world_shape__Landform,
    mut ocean_coverage: i64,
) -> rt::Result<bool> {
    let mut sizes: Vec<i64> = world_shape__landmass_sizes(world)?;
    if !(((sizes).len() as i64) != 0i64) {
        return Ok(false);
    }
    let mut expected_land: i64 = rt::int_float(rt::finite(
        (((&(world).tiles).len() as i64) as f64)
            * rt::finite(
                ((1i64) as f64) - rt::float_true_div(((ocean_coverage) as f64), 100.0f64)?,
            )?,
    )?)?;
    let mut polar: i64 = ({
        let mut __comprehension_result_1425: Vec<bool> = Vec::new();
        let __comprehension_source_1424 = ((world).tiles.clone());
        for tile in __comprehension_source_1424.iter().cloned() {
            __comprehension_result_1425.push(
                (!(crate::openciv3::hydrology::is_water(&tile)?)
                    && (((((tile).y) as f64) <= rt::finite(0.1f64 * (((world).height) as f64))?)
                        || ((((tile).y) as f64)
                            >= rt::finite(0.9f64 * (((world).height) as f64))?))),
            );
        }
        __comprehension_result_1425
    })
    .into_iter()
    .map(|value| value as i64)
    .sum::<i64>();
    if (landform.clone()) == (world_shape__Landform::CONTINENTS) {
        return Ok(((((sizes).len() as i64) >= 3i64)
            && ((((rt::at(&sizes, 0i64)?) as f64)
                <= rt::finite(1.3f64 * ((rt::at(&sizes, 1i64)?) as f64))?)
                && (((polar) as f64) <= rt::finite(0.1f64 * ((expected_land) as f64))?))));
    }
    if (landform) == (world_shape__Landform::PANGAEA) {
        return Ok(((((rt::at(&sizes, 0i64)?) as f64)
            >= rt::finite(0.8f64 * ((expected_land) as f64))?)
            && (((polar) as f64) <= rt::finite(0.2f64 * ((expected_land) as f64))?)));
    }
    Ok((((((sizes).len() as i64) as f64)
        >= rt::finite((((world).civilization_count) as f64) * 1.2f64)?)
        && ((rt::at(&sizes, 0i64)? <= (81i64).checked_mul(3i64).ok_or("integer overflow")?)
            && ((({
                let mut __comprehension_result_1427: Vec<i64> = Vec::new();
                let __comprehension_source_1426 = (sizes.clone());
                for size in __comprehension_source_1426.iter().cloned() {
                    __comprehension_result_1427.push(rt::int_floor_div(size, 81i64)?);
                }
                __comprehension_result_1427
            })
            .into_iter()
            .sum::<i64>()
                >= (world).civilization_count)
                && (((({
                    let mut __comprehension_result_1429: Vec<bool> = Vec::new();
                    let __comprehension_source_1428 = (sizes.clone());
                    for size in __comprehension_source_1428.iter().cloned() {
                        __comprehension_result_1429.push((rt::int_floor_div(size, 81i64)? > 1i64));
                    }
                    __comprehension_result_1429
                })
                .into_iter()
                .map(|value| value as i64)
                .sum::<i64>()) as f64)
                    <= rt::finite((((world).civilization_count) as f64) * 0.4f64)?)))))
}

// Python: openciv3/world_shape.py:101
pub(crate) fn world_shape__continental_shelf(
    world: &crate::openciv3::world::WorldMap,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    let mut coast: crate::openciv3::world::WorldMap = {
        let mut __replacement = ((*world).clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_1433: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_1430 = ((world).tiles.clone());
            for tile in __comprehension_source_1430.iter().cloned() {
                __comprehension_result_1433.push(
                    (if ({
                        let __needle = (tile).base_terrain;
                        let __container = &({
                            let __tuple_value = &((12i64, 13i64));
                            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                        });
                        __container.contains(&__needle)
                    } && ({
                        let mut __comprehension_result_1432: Vec<bool> = Vec::new();
                        let __comprehension_source_1431 =
                            (crate::openciv3::world::WorldMap__neighbors(world, &tile)?);
                        for n in __comprehension_source_1431.iter().cloned() {
                            __comprehension_result_1432
                                .push(!(crate::openciv3::hydrology::is_water(&n)?));
                        }
                        __comprehension_result_1432
                    })
                    .into_iter()
                    .any(|__value| __value))
                    {
                        {
                            let mut __replacement = (tile.clone()).clone();
                            __replacement.base_terrain = 11i64;
                            __replacement.overlay_terrain = 11i64;
                            __replacement
                        }
                    } else {
                        tile.clone()
                    }),
                );
            }
            __comprehension_result_1433
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    };
    Ok({
        let mut __replacement = (coast.clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_1437: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_1434 = ((coast).tiles.clone());
            for tile in __comprehension_source_1434.iter().cloned() {
                __comprehension_result_1437.push(
                    (if (((tile).base_terrain == 13i64)
                        && ({
                            let mut __comprehension_result_1436: Vec<bool> = Vec::new();
                            let __comprehension_source_1435 =
                                (crate::openciv3::world::WorldMap__neighbors(&coast, &tile)?);
                            for n in __comprehension_source_1435.iter().cloned() {
                                __comprehension_result_1436.push(((n).base_terrain == 11i64));
                            }
                            __comprehension_result_1436
                        })
                        .into_iter()
                        .any(|__value| __value))
                    {
                        {
                            let mut __replacement = (tile.clone()).clone();
                            __replacement.base_terrain = 12i64;
                            __replacement.overlay_terrain = 12i64;
                            __replacement
                        }
                    } else {
                        tile.clone()
                    }),
                );
            }
            __comprehension_result_1437
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    })
}

// Python: openciv3/world_shape.py:113
pub(crate) fn world_shape__generate_shape(
    size: &crate::openciv3::world_size::WorldSize,
    mut seed: i64,
    mut landform: world_shape__Landform,
    mut ocean_coverage: i64,
    mut max_attempts: i64,
) -> rt::Result<world_shape__ShapeResult> {
    let (mut width, mut height): (i64, i64) = (
        ((size).width)
            .checked_sub(rt::int_modulo((size).width, 2i64)?)
            .ok_or("integer overflow")?,
        ((size).height)
            .checked_sub(rt::int_modulo((size).height, 2i64)?)
            .ok_or("integer overflow")?,
    );
    if ((width < 2i64)
        || ((height < 2i64) || (((size).civilization_count < 0i64) || (max_attempts < 1i64))))
    {
        return Err("Invalid world size, player count or attempt limit"
            .to_string()
            .into());
    }
    if {
        let __needle = ocean_coverage;
        let __container = &({
            let __tuple_value = &((60i64, 70i64, 80i64));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        !__container.contains(&__needle)
    } {
        return Err("Ocean coverage must be 60, 70 or 80 percent"
            .to_string()
            .into());
    }
    for mut attempt in 0i64..max_attempts {
        let mut noise_seed: i64 = crate::strategy::random::seed32(
            (seed)
                .checked_add((4660i64).checked_mul(attempt).ok_or("integer overflow")?)
                .ok_or("integer overflow")?,
        )?;
        let mut heights: crate::strategy::height_map::HeightMap =
            crate::strategy::height_map::HeightMap____post_init__(
                crate::strategy::height_map::HeightMap {
                    seed: noise_seed,
                    width: width,
                    height: height,
                    scale: ({
                        static __CONSTANT_py__openciv3__world_shape__escaped_5f5343414c45:
                            std::sync::OnceLock<indexmap::IndexMap<world_shape__Landform, f64>> =
                            std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__world_shape__escaped_5f5343414c45
                            .get()
                            .is_none()
                        {
                            let __constant_value = [
                                (world_shape__Landform::ARCHIPELAGO, 0.2f64),
                                (world_shape__Landform::CONTINENTS, 0.05f64),
                                (world_shape__Landform::PANGAEA, 0.02f64),
                            ]
                            .into_iter()
                            .collect::<indexmap::IndexMap<_, _>>();
                            let _ = __CONSTANT_py__openciv3__world_shape__escaped_5f5343414c45
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__world_shape__escaped_5f5343414c45
                            .get()
                            .ok_or("missing module constant")?
                    })
                    .get(&(landform.clone()))
                    .ok_or("missing dict key")?
                    .clone(),
                    wrap_x: true,
                    wrap_y: false,
                    force_low_poles: true,
                    _tiles_per_cell_x: 0.0f64,
                    _tiles_per_cell_y: 0.0f64,
                    values: vec![],
                },
            )?;
        let mut world: crate::openciv3::world::WorldMap =
            world_shape__from_heights(&heights, size, seed, ocean_coverage)?;
        let mut accepted: bool = world_shape__acceptable(&world, landform.clone(), ocean_coverage)?;
        if (accepted || (attempt == (max_attempts).checked_sub(1i64).ok_or("integer overflow")?)) {
            return Ok(world_shape__ShapeResult {
                world: world_shape__continental_shelf(&world)?,
                attempts: (attempt).checked_add(1i64).ok_or("integer overflow")?,
                accepted: accepted,
            });
        }
    }
    return Err("Unreachable generation loop".to_string().into());
}

// Python: openciv3/world_starts.py:27
pub(crate) fn world_starts__StartLocations__complete(
    self_: &world_starts__StartLocations,
) -> rt::Result<bool> {
    Ok((((&(self_).points).len() as i64) == (self_).requested))
}

/// Score with yields supplied for the default government and no known techs.
// Python: openciv3/world_starts.py:31
pub(crate) fn world_starts__score_locations(
    world: &crate::openciv3::world::WorldMap,
    terrains: &[world_starts__StartTerrain],
    mut tile_yield: impl Fn(crate::openciv3::world::Tile) -> rt::Result<crate::civ::economy::Yield>,
    mut workable_rank: i64,
) -> rt::Result<indexmap::IndexMap<(i64, i64), i64>> {
    if (workable_rank < 1i64) {
        return Err("Workable rank must be positive".to_string().into());
    }
    let mut values: indexmap::IndexMap<(i64, i64), i64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut tile in (&(world).tiles).iter() {
        let mut value: crate::civ::economy::Yield = tile_yield((*tile).clone())?;
        {
            let __value = ((((4i64)
                .checked_mul((value).commerce)
                .ok_or("integer overflow")?)
            .checked_add(
                (12i64)
                    .checked_mul((value).shields)
                    .ok_or("integer overflow")?,
            )
            .ok_or("integer overflow")?)
            .checked_add(
                (20i64)
                    .checked_mul((value).food)
                    .ok_or("integer overflow")?,
            )
            .ok_or("integer overflow")?)
            .checked_sub(
                (if (((tile).overlays & 128i64) != 0i64) {
                    50i64
                } else {
                    0i64
                }),
            )
            .ok_or("integer overflow")?;
            let __key = ((tile).x, (tile).y);
            values.insert(__key, __value);
        }
    }
    let mut scores: indexmap::IndexMap<(i64, i64), i64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut tile in (&(world).tiles).iter() {
        if (!(({
            let __source = terrains;
            let __key = (tile).overlay_terrain;
            &__source[rt::index(__source.len(), __key)?]
        })
        .allow_cities)
            || ((tile).overlays & 128i64) != 0)
        {
            continue;
        }
        let mut immediate: Vec<crate::openciv3::world::Tile> =
            crate::strategy::grid::within_rank(world, tile, 1i64)?;
        let mut score: i64 = ({
            let mut __comprehension_result_1439: Vec<i64> = Vec::new();
            let __comprehension_source_1438 = (immediate.clone());
            for n in __comprehension_source_1438.iter().cloned() {
                __comprehension_result_1439.push(
                    ((values)
                        .get(&(((n).x, (n).y)))
                        .ok_or("missing dict key")?
                        .clone())
                    .checked_add(
                        (if crate::openciv3::hydrology::is_water(&n)? {
                            30i64
                        } else {
                            0i64
                        }),
                    )
                    .ok_or("integer overflow")?,
                );
            }
            __comprehension_result_1439
        })
        .into_iter()
        .sum::<i64>();
        score = (score)
            .checked_add(
                ({
                    let mut __comprehension_result_1441: Vec<i64> = Vec::new();
                    let __comprehension_source_1440 =
                        (crate::strategy::grid::within_rank(world, tile, workable_rank)?);
                    for n in __comprehension_source_1440.iter().cloned() {
                        __comprehension_result_1441.push(
                            (values)
                                .get(&(((n).x, (n).y)))
                                .ok_or("missing dict key")?
                                .clone(),
                        );
                    }
                    __comprehension_result_1441
                })
                .into_iter()
                .sum::<i64>(),
            )
            .ok_or("integer overflow")?;
        if (crate::openciv3::hydrology::river_edges(world, tile)? != 0i64) {
            score = (score).checked_add(35i64).ok_or("integer overflow")?;
        }
        score = (score)
            .checked_add(
                ({
                    let mut __comprehension_result_1443: Vec<bool> = Vec::new();
                    let __comprehension_source_1442 =
                        (crate::strategy::grid::within_rank(world, tile, 4i64)?);
                    for n in __comprehension_source_1442.iter().cloned() {
                        __comprehension_result_1443.push(((n).continent == (tile).continent));
                    }
                    __comprehension_result_1443
                })
                .into_iter()
                .map(|value| value as i64)
                .sum::<i64>(),
            )
            .ok_or("integer overflow")?;
        if (score > 0i64) {
            {
                let __value = score;
                let __key = ((tile).x, (tile).y);
                scores.insert(__key, __value);
            }
        }
    }
    Ok(scores)
}

// Python: openciv3/world_starts.py:56
pub(crate) fn world_starts__choose_starts(
    world: &crate::openciv3::world::WorldMap,
    resources: &[crate::openciv3::rules::Resource],
    terrains: &[world_starts__StartTerrain],
    mut tile_yield: impl Fn(crate::openciv3::world::Tile) -> rt::Result<crate::civ::economy::Yield>,
    mut workable_rank: i64,
) -> rt::Result<world_starts__StartLocations> {
    if (((world).civilization_count < 0i64)
        || (((world).civilization_distance < 0i64)
            || ({
                let mut __comprehension_result_1445: Vec<bool> = Vec::new();
                let __comprehension_source_1444 = ((world).tiles.clone());
                for t in __comprehension_source_1444.iter().cloned() {
                    __comprehension_result_1445.push(((t).continent < 0i64));
                }
                __comprehension_result_1445
            })
            .into_iter()
            .any(|__value| __value)))
    {
        return Err(
            "Starting locations require labeled continents and nonnegative settings"
                .to_string()
                .into(),
        );
    }
    let mut scores: indexmap::IndexMap<(i64, i64), i64> = {
        let __call_1446_0 = world;
        let __call_1446_1 = terrains;
        let __call_1446_2 = tile_yield;
        let __call_1446_3 = workable_rank;
        world_starts__score_locations(__call_1446_0, __call_1446_1, __call_1446_2, __call_1446_3)
    }?;
    let mut candidates: Vec<crate::openciv3::world::Tile> = {
        let mut __decorated: Vec<(i64, crate::openciv3::world::Tile)> = Vec::new();
        for __item in ({
            let mut __comprehension_result_1448: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_1447 = ((world).tiles.clone());
            for t in __comprehension_source_1447.iter().cloned() {
                if {
                    let __needle = ((t).x, (t).y);
                    let __container = &scores;
                    __container.contains_key(&__needle)
                } {
                    __comprehension_result_1448.push(t.clone());
                }
            }
            __comprehension_result_1448
        })
        .into_iter()
        {
            let t = __item;
            let __key = {
                ((scores)
                    .get(&(((t).x, (t).y)))
                    .ok_or("missing dict key")?
                    .clone())
                .checked_neg()
                .ok_or("integer overflow")?
            };
            __decorated.push((__key, t));
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
    let mut sizes: indexmap::IndexMap<i64, i64> = {
        let mut __counts: indexmap::IndexMap<i64, i64> = indexmap::IndexMap::new();
        for __item in ({
            let mut __comprehension_result_1450: Vec<i64> = Vec::new();
            let __comprehension_source_1449 = ((world).tiles.clone());
            for t in __comprehension_source_1449.iter().cloned() {
                __comprehension_result_1450.push((t).continent);
            }
            __comprehension_result_1450
        })
        .into_iter()
        {
            *__counts.entry(__item).or_insert(0) += 1;
        }
        __counts
    };
    let mut luxuries: indexmap::IndexMap<i64, i64> = {
        let mut __counts: indexmap::IndexMap<i64, i64> = indexmap::IndexMap::new();
        for __item in ({
            let mut __comprehension_result_1452: Vec<i64> = Vec::new();
            let __comprehension_source_1451 = ((world).tiles.clone());
            for t in __comprehension_source_1451.iter().cloned() {
                if (!(crate::openciv3::hydrology::is_water(&t)?)
                    && (((t).resource >= 0i64)
                        && (({
                            let __source = resources;
                            let __key = (t).resource;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .kind
                            == 1i64)))
                {
                    __comprehension_result_1452.push((t).continent);
                }
            }
            __comprehension_result_1452
        })
        .into_iter()
        {
            *__counts.entry(__item).or_insert(0) += 1;
        }
        __counts
    };
    let mut selected: Vec<crate::openciv3::world::Tile> = vec![];
    let mut selected_points: std::collections::BTreeSet<(i64, i64)> =
        std::collections::BTreeSet::new();
    let mut counts: indexmap::IndexMap<i64, i64> = indexmap::IndexMap::<i64, i64>::new();
    for mut attempt in 0i64..10i64 {
        let mut minimum_size: i64 = (if (attempt < 3i64) {
            81i64
        } else {
            (if (attempt < 6i64) {
                40i64
            } else {
                (1i64).checked_neg().ok_or("integer overflow")?
            })
        });
        let mut minimum_distance: i64 = (world).civilization_distance;
        if (attempt > 2i64) {
            minimum_distance = rt::int_floor_div(minimum_distance, 2i64)?;
        }
        if (attempt > 3i64) {
            minimum_distance = ((minimum_distance)
                .checked_sub(attempt)
                .ok_or("integer overflow")?)
            .max(3i64);
        }
        for mut tile in (candidates).iter() {
            if (((selected).len() as i64) == (world).civilization_count) {
                break;
            }
            if ({
                let __needle = ((tile).x, (tile).y);
                let __container = &selected_points;
                __container.contains(&__needle)
            } || ((sizes.clone())
                .get(&((tile).continent))
                .cloned()
                .unwrap_or_default()
                <= minimum_size))
            {
                continue;
            }
            if ((attempt < 2i64)
                && ((counts.clone())
                    .get(&((tile).continent))
                    .cloned()
                    .unwrap_or_default()
                    >= (luxuries.clone())
                        .get(&((tile).continent))
                        .cloned()
                        .unwrap_or_default()))
            {
                continue;
            }
            if ({
                let mut __comprehension_result_1454: Vec<bool> = Vec::new();
                let __comprehension_source_1453 = (selected.clone());
                for start in __comprehension_source_1453.iter().cloned() {
                    __comprehension_result_1454.push(
                        (((start).continent == (tile).continent)
                            && (crate::strategy::grid::distance(
                                &({
                                    let __structural_value = (*world).clone();
                                    crate::strategy::grid::DistanceMap {
                                        width: (__structural_value).width.clone(),
                                        height: (__structural_value).height.clone(),
                                        wrap_x: (__structural_value).wrap_x.clone(),
                                        wrap_y: (__structural_value).wrap_y.clone(),
                                    }
                                }),
                                &({
                                    let __structural_value = start.clone();
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
                            )? < minimum_distance)),
                    );
                }
                __comprehension_result_1454
            })
            .into_iter()
            .any(|__value| __value)
            {
                continue;
            }
            {
                selected.push((*tile).clone());
            };
            {
                selected_points.insert(((tile).x, (tile).y));
            };
            {
                let __value = ((counts.clone())
                    .get(&((tile).continent))
                    .cloned()
                    .unwrap_or_default())
                .checked_add(1i64)
                .ok_or("integer overflow")?;
                let __key = (tile).continent;
                counts.insert(__key, __value);
            }
        }
        if (((selected).len() as i64) == (world).civilization_count) {
            break;
        }
    }
    {
        let mut __random = crate::strategy::random::MapRandom____post_init__(
            crate::strategy::random::MapRandom {
                seed: crate::strategy::random::seed32(
                    ((world).seed)
                        .checked_add(4919i64)
                        .ok_or("integer overflow")?,
                )?,
                _values: vec![],
                _index: 0i64,
                _other: 21i64,
            },
        )?;
        for __index in 0..selected.len().saturating_sub(1) {
            __random._index = if __random._index < 55 {
                __random._index + 1
            } else {
                1
            };
            __random._other = if __random._other < 55 {
                __random._other + 1
            } else {
                1
            };
            let __sample_index = __random._index as usize;
            let mut __value = (__random._values[__sample_index]
                - __random._values[__random._other as usize]
                + 2147483648i64)
                .rem_euclid(4294967296i64)
                - 2147483648i64;
            if __value == 2147483647i64 {
                __value -= 1;
            }
            if __value < 0 {
                __value += 2147483647i64;
            }
            __random._values[__sample_index] = __value;
            let __other = __index
                + ((__value as f64) * (1.0 / 2147483647.0) * ((selected.len() - __index) as f64))
                    as usize;
            selected.swap(__index, __other);
        }
        ()
    };
    Ok(world_starts__StartLocations {
        points: ({
            let mut __comprehension_result_1456: Vec<(i64, i64)> = Vec::new();
            let __comprehension_source_1455 = (selected.clone());
            for t in __comprehension_source_1455.iter().cloned() {
                __comprehension_result_1456.push(((t).x, (t).y));
            }
            __comprehension_result_1456
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        requested: (world).civilization_count,
    })
}

/// Return sheet/index for N, NW, NE, center; flood plains render as desert.
// Python: openciv3/world_textures.py:12
pub(crate) fn world_textures__texture_for_junction(
    terrains: &(i64, i64, i64, i64),
    mut random: &mut crate::strategy::random::MapRandom,
) -> rt::Result<(i64, i64)> {
    if ({
        let mut __comprehension_result_1458: Vec<bool> = Vec::new();
        let __comprehension_source_1457 = ({
            let __tuple_value = &((*terrains).clone());
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
                __tuple_value.3.clone(),
            ]
        });
        for t in __comprehension_source_1457.iter().cloned() {
            __comprehension_result_1458.push({
                let __needle = t;
                let __container = &({
                    let __tuple_value = &((0i64, 1i64, 2i64, 3i64, 4i64, 11i64, 12i64, 13i64));
                    vec![
                        __tuple_value.0.clone(),
                        __tuple_value.1.clone(),
                        __tuple_value.2.clone(),
                        __tuple_value.3.clone(),
                        __tuple_value.4.clone(),
                        __tuple_value.5.clone(),
                        __tuple_value.6.clone(),
                        __tuple_value.7.clone(),
                    ]
                });
                !__container.contains(&__needle)
            });
        }
        __comprehension_result_1458
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("Unsupported base terrain for texture assignment"
            .to_string()
            .into());
    }
    let mut normalized: Vec<i64> = ({
        let mut __comprehension_result_1460: Vec<i64> = Vec::new();
        let __comprehension_source_1459 = ({
            let __tuple_value = &((*terrains).clone());
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
                __tuple_value.3.clone(),
            ]
        });
        for t in __comprehension_source_1459.iter().cloned() {
            __comprehension_result_1460.push((if (t == 4i64) { 0i64 } else { t }));
        }
        __comprehension_result_1460
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut kinds: std::collections::BTreeSet<i64> = (normalized.clone())
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>();
    let mut sheet: i64 = 0i64;
    if {
        let __left = &(kinds.clone());
        let __right = &({
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![11i64, 12i64, 13i64].into_iter() {
                __result.insert(__item);
            }
            __result
        });
        __left.is_subset(__right)
    } {
        if (kinds.clone() == {
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![13i64].into_iter() {
                __result.insert(__item);
            }
            __result
        }) {
            return Ok((8i64, {
                if !(0..=2147483647i64).contains(&(81i64)) {
                    return Err("Random upper bound must be a nonnegative Int32".into());
                }
                let mut __map_random = random.clone();
                __map_random._index = if __map_random._index < 55 {
                    __map_random._index + 1
                } else {
                    1
                };
                __map_random._other = if __map_random._other < 55 {
                    __map_random._other + 1
                } else {
                    1
                };
                let __sample_index = __map_random._index as usize;
                let mut __value = (__map_random._values[__sample_index]
                    - __map_random._values[__map_random._other as usize]
                    + 2147483648i64)
                    .rem_euclid(4294967296i64)
                    - 2147483648i64;
                if __value == 2147483647i64 {
                    __value -= 1;
                }
                if __value < 0 {
                    __value += 2147483647i64;
                }
                __map_random._values[__sample_index] = __value;
                *random = __map_random;
                ((__value as f64) * (1.0 / 2147483647.0) * ((81i64) as f64)) as i64
            }));
        }
        if (kinds == {
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![12i64].into_iter() {
                __result.insert(__item);
            }
            __result
        }) {
            return Ok((7i64, {
                if !(0..=2147483647i64).contains(&(81i64)) {
                    return Err("Random upper bound must be a nonnegative Int32".into());
                }
                let mut __map_random = random.clone();
                __map_random._index = if __map_random._index < 55 {
                    __map_random._index + 1
                } else {
                    1
                };
                __map_random._other = if __map_random._other < 55 {
                    __map_random._other + 1
                } else {
                    1
                };
                let __sample_index = __map_random._index as usize;
                let mut __value = (__map_random._values[__sample_index]
                    - __map_random._values[__map_random._other as usize]
                    + 2147483648i64)
                    .rem_euclid(4294967296i64)
                    - 2147483648i64;
                if __value == 2147483647i64 {
                    __value -= 1;
                }
                if __value < 0 {
                    __value += 2147483647i64;
                }
                __map_random._values[__sample_index] = __value;
                *random = __map_random;
                ((__value as f64) * (1.0 / 2147483647.0) * ((81i64) as f64)) as i64
            }));
        }
        sheet = 6i64;
    } else {
        if {
            let __needle = 3i64;
            let __container = &kinds;
            __container.contains(&__needle)
        } {
            sheet = 0i64;
        } else {
            if (((kinds).len() as i64) >= 3i64) {
                sheet = (if {
                    let __needle = 11i64;
                    let __container = &kinds;
                    !__container.contains(&__needle)
                } {
                    4i64
                } else {
                    (if {
                        let __needle = 2i64;
                        let __container = &kinds;
                        !__container.contains(&__needle)
                    } {
                        3i64
                    } else {
                        (if {
                            let __needle = 0i64;
                            let __container = &kinds;
                            !__container.contains(&__needle)
                        } {
                            1i64
                        } else {
                            2i64
                        })
                    })
                });
            } else {
                if (((kinds).len() as i64) == 2i64) {
                    if {
                        let __needle = kinds.clone();
                        let __container = &({
                            let __tuple_value = &((
                                {
                                    let mut __result = std::collections::BTreeSet::new();
                                    for __item in vec![2i64, 11i64].into_iter() {
                                        __result.insert(__item);
                                    }
                                    __result
                                },
                                {
                                    let mut __result = std::collections::BTreeSet::new();
                                    for __item in vec![1i64, 11i64].into_iter() {
                                        __result.insert(__item);
                                    }
                                    __result
                                },
                                {
                                    let mut __result = std::collections::BTreeSet::new();
                                    for __item in vec![1i64, 2i64].into_iter() {
                                        __result.insert(__item);
                                    }
                                    __result
                                },
                            ));
                            vec![
                                __tuple_value.0.clone(),
                                __tuple_value.1.clone(),
                                __tuple_value.2.clone(),
                            ]
                        });
                        __container.contains(&__needle)
                    } {
                        sheet = 1i64;
                    } else {
                        if {
                            let __needle = kinds.clone();
                            let __container = &({
                                let __tuple_value = &((
                                    {
                                        let mut __result = std::collections::BTreeSet::new();
                                        for __item in vec![0i64, 11i64].into_iter() {
                                            __result.insert(__item);
                                        }
                                        __result
                                    },
                                    {
                                        let mut __result = std::collections::BTreeSet::new();
                                        for __item in vec![0i64, 1i64].into_iter() {
                                            __result.insert(__item);
                                        }
                                        __result
                                    },
                                ));
                                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                            });
                            __container.contains(&__needle)
                        } {
                            sheet = 3i64;
                        } else {
                            if (kinds == {
                                let mut __result = std::collections::BTreeSet::new();
                                for __item in vec![0i64, 2i64].into_iter() {
                                    __result.insert(__item);
                                }
                                __result
                            }) {
                                sheet = 2i64;
                            } else {
                                return Err("Unsupported land/water texture junction"
                                    .to_string()
                                    .into());
                            }
                        }
                    }
                } else {
                    sheet = ([(2i64, 2i64), (1i64, 1i64), (0i64, 4i64)]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>())
                    .get(&(rt::at(&normalized, 0i64)?))
                    .ok_or("missing dict key")?
                    .clone();
                }
            }
        }
    }
    let (mut first, mut middle): (i64, i64) = ({
        static __CONSTANT_py__openciv3__world_textures__escaped_5f5041495253: std::sync::OnceLock<
            indexmap::IndexMap<i64, (i64, i64)>,
        > = std::sync::OnceLock::new();
        if __CONSTANT_py__openciv3__world_textures__escaped_5f5041495253
            .get()
            .is_none()
        {
            let __constant_value = [
                (0i64, (3i64, 2i64)),
                (1i64, (1i64, 2i64)),
                (2i64, (0i64, 2i64)),
                (3i64, (0i64, 1i64)),
                (4i64, (0i64, 2i64)),
                (6i64, (11i64, 12i64)),
            ]
            .into_iter()
            .collect::<indexmap::IndexMap<_, _>>();
            let _ =
                __CONSTANT_py__openciv3__world_textures__escaped_5f5041495253.set(__constant_value);
        }
        __CONSTANT_py__openciv3__world_textures__escaped_5f5041495253
            .get()
            .ok_or("missing module constant")?
    })
    .get(&(sheet))
    .ok_or("missing dict key")?
    .clone();
    let mut index: i64 = ({
        let mut __comprehension_result_1462: Vec<i64> = Vec::new();
        let __comprehension_source_1461 = ({
            let __left = normalized.clone();
            let __right = {
                let __tuple_value = &((1i64, 3i64, 9i64, 27i64));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                    __tuple_value.3.clone(),
                ]
            };
            if false && __left.len() != __right.len() {
                return Err("zip() argument lengths differ".into());
            }
            let mut __result: Vec<(i64, i64)> = Vec::new();
            let __length = __left.len().min(__right.len());
            let mut __left_iter = __left.into_iter();
            let mut __right_iter = __right.into_iter();
            for __index in 0..__length {
                __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
            }
            __result
        });
        for (terrain, weight) in __comprehension_source_1461.iter().cloned() {
            __comprehension_result_1462.push(
                (if (terrain == first) {
                    0i64
                } else {
                    (if (terrain == middle) { 1i64 } else { 2i64 })
                })
                .checked_mul(weight)
                .ok_or("integer overflow")?,
            );
        }
        __comprehension_result_1462
    })
    .into_iter()
    .sum::<i64>();
    Ok((sheet, index))
}

// Python: openciv3/world_textures.py:46
pub(crate) fn world_textures__assign_textures(
    world: &crate::openciv3::world::WorldMap,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    let mut random: crate::strategy::random::MapRandom =
        crate::strategy::random::MapRandom____post_init__(crate::strategy::random::MapRandom {
            seed: crate::strategy::random::seed32(
                ((world).seed)
                    .checked_add(60332i64)
                    .ok_or("integer overflow")?,
            )?,
            _values: vec![],
            _index: 0i64,
            _other: 21i64,
        })?;

    let mut tiles: Vec<crate::openciv3::world::Tile> = vec![];
    for mut tile in (&(world).tiles).iter() {
        let mut junction: (i64, i64, i64, i64) = (
            world_textures__assign_textures__terrain(
                &(crate::openciv3::world::WorldMap__tile_at(
                    world,
                    (tile).x,
                    ((tile).y).checked_sub(2i64).ok_or("integer overflow")?,
                )?),
            )?,
            world_textures__assign_textures__terrain(
                &(crate::openciv3::world::WorldMap__tile_at(
                    world,
                    ((tile).x).checked_sub(1i64).ok_or("integer overflow")?,
                    ((tile).y).checked_sub(1i64).ok_or("integer overflow")?,
                )?),
            )?,
            world_textures__assign_textures__terrain(
                &(crate::openciv3::world::WorldMap__tile_at(
                    world,
                    ((tile).x).checked_add(1i64).ok_or("integer overflow")?,
                    ((tile).y).checked_sub(1i64).ok_or("integer overflow")?,
                )?),
            )?,
            (tile).base_terrain,
        );
        let (mut sheet, mut index): (i64, i64) =
            world_textures__texture_for_junction(&junction, &mut random)?;
        {
            tiles.push({
                let mut __replacement = ((*tile).clone()).clone();
                __replacement.texture_file = sheet;
                __replacement.texture_index = index;
                __replacement
            });
        };
    }
    Ok({
        let mut __replacement = ((*world).clone()).clone();
        __replacement.tiles = (tiles).iter().cloned().collect::<Vec<_>>();
        __replacement
    })
}

// Python: openciv3/world_textures.py:49
pub(crate) fn world_textures__assign_textures__terrain(
    tile: &Option<crate::openciv3::world::Tile>,
) -> rt::Result<i64> {
    Ok((if (tile).is_none() {
        11i64
    } else {
        ((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()).base_terrain
    }))
}
