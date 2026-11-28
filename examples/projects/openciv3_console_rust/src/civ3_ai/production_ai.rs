use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct ProductionChoice {
    pub(crate) kind: String,
    pub(crate) index: Option<i64>,
    pub(crate) score: f64,
}

// Python: civ3_ai/production_ai.py:44
pub(crate) fn ProductionChoice__apply(
    self_: &ProductionChoice,
    city: &crate::openciv3::cities::City,
) -> rt::Result<()> {
    if (AsRef::<str>::as_ref(&(self_).kind) == "wealth") {
        crate::openciv3::cities::City__select_inflow(
            (*city).clone(),
            &(Some(crate::openciv3::inflows::Inflow::WEALTH)),
        )?;
    } else {
        if (AsRef::<str>::as_ref(&(self_).kind) == "idle") {
            crate::openciv3::cities::City__select_inflow((*city).clone(), &None)?;
        } else {
            if (&(self_).index).is_none() {
                return Err("Unit/building choice requires an index".to_string().into());
            } else {
                if (AsRef::<str>::as_ref(&(self_).kind) == "unit") {
                    crate::openciv3::cities::City__select_unit(
                        (*city).clone(),
                        (*((self_).index.clone()).as_ref().ok_or("expected a value")?).clone(),
                    )?;
                } else {
                    crate::openciv3::cities::City__select_building(
                        (*city).clone(),
                        (*((self_).index.clone()).as_ref().ok_or("expected a value")?).clone(),
                    )?;
                }
            }
        }
    }
    Ok(())
}

/// Rank legal targets with legacy 90–109% random score variation.
///
/// The caller supplies this player's actual mission state and persistent RNG.
/// Selection is read-only; apply the returned choice after the caller commits.
// Python: civ3_ai/production_ai.py:57
pub(crate) fn choose_production(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut corruption: f64,
    mut rng: rt::Random,
    worker_types: &std::collections::BTreeSet<i64>,
    mut reserved_settlements: Option<std::collections::BTreeSet<(i64, i64)>>,
    mut unescorted_settler: Option<bool>,
) -> rt::Result<ProductionChoice> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (city).owner)?;
    if (reserved_settlements).is_none() {
        reserved_settlements = Some(crate::openciv3::unit_missions::reserved_settlements(
            game,
            (city).owner,
            &None,
        )?);
    }
    if (unescorted_settler).is_none() {
        unescorted_settler = Some(
            ({
                let mut __comprehension_result_893: Vec<bool> = Vec::new();
                let __comprehension_source_892 = ((game).units.clone());
                for unit in __comprehension_source_892.iter().cloned() {
                    __comprehension_result_893.push(
                        (((unit).owner == (city).owner)
                            && ((((unit).x, (unit).y) == ((city).x, (city).y))
                                && ((&(unit).settler_mission).is_some()
                                    && (((*((unit).settler_mission.clone())
                                        .as_ref()
                                        .ok_or("expected a value")?)
                                    .clone())
                                    .escort
                                    .clone())
                                    .is_none()))),
                    );
                }
                __comprehension_result_893
            })
            .into_iter()
            .any(|__value| __value),
        );
    }
    let mut network: crate::openciv3::trade_network::TradeNetwork =
        crate::openciv3::trade_network::TradeNetwork____post_init__(
            crate::openciv3::trade_network::TradeNetwork {
                game: (*game).clone(),
                owner: Some((city).owner),
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
    let mut hydro: crate::openciv3::hydrology::Hydrology =
        crate::openciv3::hydrology::Hydrology__from_world(&(game).world)?;
    let mut units: Vec<i64> = {
        let mut __comprehension_result_896: Vec<i64> = Vec::new();
        let __comprehension_source_894 =
            ((0i64..((&(rules).units).len() as i64)).collect::<Vec<i64>>());
        for index in __comprehension_source_894.iter().cloned() {
            if {
                let __call_895_0 = game;
                let __call_895_1 = city;
                let __call_895_2 = index;
                let __call_895_3 = Some(network.clone());
                let __call_895_default_3 = None;
                crate::openciv3::production_eligibility::can_train(
                    __call_895_0,
                    __call_895_1,
                    __call_895_2,
                    __call_895_default_3,
                    __call_895_3,
                )
            }? {
                __comprehension_result_896.push(index);
            }
        }
        __comprehension_result_896
    };
    let mut buildings: Vec<i64> = {
        let mut __comprehension_result_899: Vec<i64> = Vec::new();
        let __comprehension_source_897 =
            ((0i64..((&(rules).buildings).len() as i64)).collect::<Vec<i64>>());
        for index in __comprehension_source_897.iter().cloned() {
            if {
                let __call_898_0 = game;
                let __call_898_1 = city;
                let __call_898_2 = index;
                let __call_898_3 = Some(network.clone());
                let __call_898_4 = Some(hydro.clone());
                crate::openciv3::production_eligibility::can_build(
                    __call_898_0,
                    __call_898_1,
                    __call_898_2,
                    __call_898_3,
                    __call_898_4,
                )
            }? {
                __comprehension_result_899.push(index);
            }
        }
        __comprehension_result_899
    };
    let mut sites: indexmap::IndexMap<(i64, i64), f64> = {
        let __call_900_0 = game;
        let __call_900_1 = &player;
        let __call_900_2 = &(((city).x, (city).y));
        let __call_900_3 = &((*(reserved_settlements).as_ref().ok_or("expected a value")?).clone());
        let __call_900_default_4 = &({
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        });
        let __call_900_default_5 = &(crate::civ3_ai::settler_locations::SettlerWeights {
            distance_radius: 4i64,
            distance_penalty: (((2i64).checked_neg().ok_or("integer overflow")?) as f64),
            food: ((5i64) as f64),
            shields: ((3i64) as f64),
            commerce: ((2i64) as f64),
            hills: ((10i64) as f64),
            luxury: ((15i64) as f64),
            strategic: ((20i64) as f64),
            water: ((10i64) as f64),
        });
        let __call_900_default_6 = None;
        crate::civ3_ai::settler_locations::settlement_scores(
            __call_900_0,
            __call_900_1,
            __call_900_2,
            __call_900_3,
            __call_900_default_4,
            __call_900_default_5,
            __call_900_default_6,
        )
    }?;
    let mut open_sites: i64 = crate::civ3_ai::settler_locations::count_open_sites(game, &sites)?;
    let mut cities: i64 = ({
        let mut __comprehension_result_902: Vec<bool> = Vec::new();
        let __comprehension_source_901 = ((game).cities.clone());
        for other in __comprehension_source_901.iter().cloned() {
            __comprehension_result_902.push(((other).owner == (city).owner));
        }
        __comprehension_result_902
    })
    .into_iter()
    .map(|value| value as i64)
    .sum::<i64>();
    let mut expanding: bool =
        ((cities < 5i64) || (open_sites > (cities).checked_mul(2i64).ok_or("integer overflow")?));
    let mut best_attack: i64 = '__extreme: {
        let __values = &({
            let mut __comprehension_result_904: Vec<i64> = Vec::new();
            let __comprehension_source_903 = (units.clone());
            for index in __comprehension_source_903.iter().cloned() {
                __comprehension_result_904.push(
                    ({
                        let __source = &(rules).units;
                        let __key = index;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .attack,
                );
            }
            __comprehension_result_904
        });
        let mut __items = __values.iter();
        let Some(mut __best) = __items.next() else {
            break '__extreme 0i64;
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
    };
    let mut best_defense: i64 = '__extreme: {
        let __values = &({
            let mut __comprehension_result_906: Vec<i64> = Vec::new();
            let __comprehension_source_905 = (units.clone());
            for index in __comprehension_source_905.iter().cloned() {
                __comprehension_result_906.push(
                    ({
                        let __source = &(rules).units;
                        let __key = index;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .defense,
                );
            }
            __comprehension_result_906
        });
        let mut __items = __values.iter();
        let Some(mut __best) = __items.next() else {
            break '__extreme 0i64;
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
    };
    let mut choices: Vec<ProductionChoice> = vec![];
    for mut index in units {
        let mut score: f64 = {
            let __call_907_0 = game;
            let __call_907_1 = city;
            let __call_907_2 = index;
            let __call_907_3 = corruption;
            let __call_907_4 = best_attack;
            let __call_907_5 = best_defense;
            let __call_907_6 = open_sites;
            let __call_907_7 = expanding;
            let __call_907_8 = (unescorted_settler.clone()).is_some();
            let __call_907_9 = worker_types;
            let __call_907_10 = Some(network.clone());
            let __call_907_11 = Some(hydro.clone());
            score_unit(
                __call_907_0,
                __call_907_1,
                __call_907_2,
                __call_907_3,
                __call_907_4,
                __call_907_5,
                __call_907_6,
                __call_907_7,
                __call_907_8,
                __call_907_9,
                __call_907_10,
                __call_907_11,
            )
        }?;
        {
            choices.push(ProductionChoice {
                kind: "unit".to_string(),
                index: Some(index),
                score: rt::float_true_div(
                    rt::finite(score * ((rt::random_randrange(&rng, 90i64, 110i64)?) as f64))?,
                    ((100i64) as f64),
                )?,
            });
        };
    }
    for mut index in buildings {
        let mut score: f64 = {
            let __call_908_0 = game;
            let __call_908_1 = city;
            let __call_908_2 = index;
            let __call_908_3 = corruption;
            let __call_908_4 = expanding;
            let __call_908_5 = Some(network.clone());
            let __call_908_6 = Some(hydro.clone());
            score_building(
                __call_908_0,
                __call_908_1,
                __call_908_2,
                __call_908_3,
                __call_908_4,
                __call_908_5,
                __call_908_6,
            )
        }?;
        {
            choices.push(ProductionChoice {
                kind: "building".to_string(),
                index: Some(index),
                score: rt::float_true_div(
                    rt::finite(score * ((rt::random_randrange(&rng, 90i64, 110i64)?) as f64))?,
                    ((100i64) as f64),
                )?,
            });
        };
    }
    let mut wealth_rule: crate::openciv3::inflows::WealthRule = ({
        let __source = &(rules).global_rules;
        let __key = 0i64;
        &__source[rt::index(__source.len(), __key)?]
    })
    .wealth
    .clone();
    if (wealth_rule.clone()) != (crate::openciv3::inflows::WealthRule::UNAVAILABLE) {
        let mut wealth: i64 = (if ((wealth_rule)
            == (crate::openciv3::inflows::WealthRule::COMMERCE)
            && weak_economy(&player)?)
        {
            (100i64)
                .checked_sub((player).gold)
                .ok_or("integer overflow")?
        } else {
            (1000i64).checked_neg().ok_or("integer overflow")?
        });
        {
            choices.push(ProductionChoice {
                kind: "wealth".to_string(),
                index: None,
                score: rt::int_true_div(
                    (wealth)
                        .checked_mul(rt::random_randrange(&rng, 90i64, 110i64)?)
                        .ok_or("integer overflow")?,
                    100i64,
                )?,
            });
        };
    }
    Ok('__extreme: {
        let __values = &choices;
        let mut __items = __values.iter();
        let Some(mut __best) = __items.next() else {
            break '__extreme ProductionChoice {
                kind: "idle".to_string(),
                index: None,
                score: ((0i64) as f64),
            };
        };
        let mut __best_key = {
            let choice = (*__best).clone();
            (choice).score
        };
        for __candidate in __items {
            let __key = {
                let choice = (*__candidate).clone();
                (choice).score
            };
            if __key > __best_key {
                __best = __candidate;
                __best_key = __key;
            }
        }
        (*__best).clone()
    })
}

/// Score a legal unit against the city and the player’s active missions.
// Python: civ3_ai/production_ai.py:99
pub(crate) fn score_unit(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut index: i64,
    mut corruption: f64,
    mut best_attack: i64,
    mut best_defense: i64,
    mut open_city_spots: i64,
    mut expanding: bool,
    mut unescorted_settler: bool,
    worker_types: &std::collections::BTreeSet<i64>,
    mut network: Option<crate::openciv3::trade_network::TradeNetwork>,
    mut hydro: Option<crate::openciv3::hydrology::Hydrology>,
) -> rt::Result<f64> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut unit: crate::openciv3::unit_rules::UnitPrototype = rt::at(&(rules).units, index)?;
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (city).owner)?;
    let mut own_cities: Vec<crate::openciv3::cities::City> = {
        let mut __comprehension_result_910: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_909 = ((game).cities.clone());
        for other in __comprehension_source_909.iter().cloned() {
            if ((other).owner == (city).owner) {
                __comprehension_result_910.push(other.clone());
            }
        }
        __comprehension_result_910
    };
    let mut at_war: bool = ({
        let mut __comprehension_result_912: Vec<bool> = Vec::new();
        let __comprehension_source_911 = ((game).players.clone());
        for other in __comprehension_source_911.iter().cloned() {
            __comprehension_result_912.push(
                ((other).included
                    && (!(crate::openciv3::players::Player__barbarian(&other)?)
                        && (!((other).defeated)
                            && crate::openciv3::diplomacy::Diplomacy__at_war(
                                &(game).diplomacy,
                                (city).owner,
                                (other).civilization,
                            )?))),
            );
        }
        __comprehension_result_912
    })
    .into_iter()
    .any(|__value| __value);
    let mut guarded: bool = ({
        let mut __comprehension_result_914: Vec<bool> = Vec::new();
        let __comprehension_source_913 = ((game).units.clone());
        for other in __comprehension_source_913.iter().cloned() {
            __comprehension_result_914.push(
                (((other).owner == (city).owner)
                    && ((((other).x, (other).y) == ((city).x, (city).y))
                        && crate::openciv3::unit_entry::can_defend_on_land(game, &other)?)),
            );
        }
        __comprehension_result_914
    })
    .into_iter()
    .any(|__value| __value);
    if ((!(guarded) || unescorted_settler) && ((unit).defense == 0i64)) {
        return Ok(-(1e+300f64));
    }
    hydro = (if (hydro).is_some() {
        hydro.clone()
    } else {
        Some(crate::openciv3::hydrology::Hydrology__from_world(
            &(game).world,
        )?)
    });
    let mut center: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (city).x, (city).y)?;
    if (center).is_none() {
        return Err("City is outside the map".to_string().into());
    }
    if ((unit).domain == 1i64) {
        if (at_war
            || !(crate::openciv3::hydrology::Hydrology__coastal(
                &((*(hydro.clone()).as_ref().ok_or("expected a value")?).clone()),
                &(game).world,
                &((*(center).as_ref().ok_or("expected a value")?).clone()),
            )?))
        {
            return Ok(-(1e+300f64));
        }
        let mut targets: indexmap::IndexMap<i64, (i64, i64)> = ((&(game).visibility)
            .get(&((city).owner))
            .ok_or("missing dict key")?)
        .exploration_targets
        .clone();
        let mut explorers: i64 = ({
            let mut __comprehension_result_916: Vec<bool> = Vec::new();
            let __comprehension_source_915 = ((game).units.clone());
            for other in __comprehension_source_915.iter().cloned() {
                __comprehension_result_916.push(
                    (((other).owner == (city).owner)
                        && ({
                            let __needle = (other).id;
                            let __container = &targets;
                            __container.contains_key(&__needle)
                        } && (({
                            let __source = &(rules).units;
                            let __key = (other).prototype;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .domain
                            == 1i64))),
                );
            }
            __comprehension_result_916
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        if (explorers >= 4i64) {
            return Ok(-(1e+300f64));
        }
        let mut candidate: crate::openciv3::units::Unit = crate::openciv3::units::Unit {
            id: (1i64).checked_neg().ok_or("integer overflow")?,
            prototype: index,
            owner: (city).owner,
            nationality: (city).owner,
            name: (unit).name.clone(),
            x: (city).x,
            y: (city).y,
            previous_x: (city).x,
            previous_y: (city).y,
            experience: ({
                let __source = &(rules).global_rules;
                let __key = 0i64;
                &__source[rt::index(__source.len(), __key)?]
            })
            .default_unit_experience,
            hit_points: 1i64,
            movement_remaining: ((unit).movement as f64),
            ai_strategy: (1i64).checked_neg().ok_or("integer overflow")?,
            action: String::new(),
            transported_by: None,
            settler_mission: None,
            escorting: None,
            worker_job: None,
            worker_progress: 0.0f64,
            fortified: false,
            skipped_with_full_movement: false,
            defensive_bombards_remaining: 0i64,
            defender_destination: None,
            goto_destination: None,
            facing_override: None,
        };
        if ({
            let __call_917_0 = game;
            let __call_917_1 = &candidate;
            let __call_917_2 = false;
            crate::civ3_ai::explorer_ai::plan_exploration(__call_917_0, __call_917_1, __call_917_2)
        }?)
        .is_none()
        {
            return Ok(-(1e+300f64));
        }
    }
    let mut production: crate::openciv3::city_economy::CityProduction =
        crate::openciv3::city_economy::city_production(game, city, corruption, &hydro, &None)?;
    let mut cost: i64 = crate::openciv3::production_cost::unit_cost(&unit, (player).human, {
        let __source = &(&(game).scenario).difficulties;
        let __key = (game).difficulty;
        &__source[rt::index(__source.len(), __key)?]
    })?;
    let mut turns: Option<i64> = crate::openciv3::city_economy::production_turns(
        cost,
        (city).shields_stored,
        (production).useful,
    )?;
    let mut turn_penalty: i64 = (if (turns).is_none() {
        2147483647i64
    } else {
        (*(turns.clone()).as_ref().ok_or("expected a value")?).clone()
    });
    let mut food: crate::openciv3::city_economy::CityFood =
        crate::openciv3::city_economy::city_food(game, city, &hydro)?;
    let mut growth: i64 = (if (&(food).turns).is_none() {
        2147483647i64
    } else {
        (*((food).turns.clone()).as_ref().ok_or("expected a value")?).clone()
    });
    if (((unit).population_cost >= crate::openciv3::cities::City__size(city)?)
        && !(((unit).population_cost == crate::openciv3::cities::City__size(city)?)
            && (turn_penalty >= growth)))
    {
        return Ok(-(1e+300f64));
    }
    let mut weight: i64 = (if at_war { 15i64 } else { 10i64 });
    let mut population_penalty: i64 = (10i64)
        .checked_mul((unit).population_cost)
        .ok_or("integer overflow")?;
    let mut score: f64 = rt::finite(
        (if (best_attack != 0i64) {
            rt::int_true_div((unit).attack, best_attack)?
        } else {
            0.0f64
        }) * ((weight) as f64),
    )?;
    score = rt::finite(
        score
            + rt::finite(
                (if (best_defense != 0i64) {
                    rt::int_true_div((unit).defense, best_defense)?
                } else {
                    0.0f64
                }) * ((weight) as f64),
            )?,
    )?;
    score = rt::finite(
        score
            - (((turn_penalty)
                .checked_add(population_penalty)
                .ok_or("integer overflow")?) as f64),
    )?;
    let mut support: i64 = (crate::openciv3::player_economy::unit_support(game, &player)?).cost;
    if ((support > 0i64) && (!(at_war) && !(expanding))) {
        score = rt::finite(score - ((rt::int_floor_div(support, 2i64)?) as f64))?;
        if weak_economy(&player)? {
            score = rt::finite(
                score - (((support).checked_mul(2i64).ok_or("integer overflow")?) as f64),
            )?;
        }
    }
    if (((unit).orders & 4194304i64) != 0i64) {
        let mut settlers_building: i64 = ({
            let mut __comprehension_result_919: Vec<bool> = Vec::new();
            let __comprehension_source_918 = (own_cities.clone());
            for other in __comprehension_source_918.iter().cloned() {
                __comprehension_result_919.push(
                    ((&(other).producing_unit).is_some()
                        && (({
                            let __source = &(rules).units;
                            let __key = (*((other).producing_unit.clone())
                                .as_ref()
                                .ok_or("expected a value")?)
                            .clone();
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .orders
                            & 4194304i64)
                            != 0),
                );
            }
            __comprehension_result_919
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        if (open_city_spots <= settlers_building) {
            return Ok(-(1e+300f64));
        }
        if (open_city_spots > ((own_cities).len() as i64)) {
            score = rt::finite(
                score
                    + (((population_penalty)
                        .checked_mul((3i64).min(rt::int_floor_div(
                            open_city_spots,
                            ((own_cities).len() as i64),
                        )?))
                        .ok_or("integer overflow")?) as f64),
            )?;
        }
        if ((&(&(game).scenario).world_size).is_some()
            && (((own_cities).len() as i64)
                > ((*((&(game).scenario).world_size.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone())
                .optimal_cities))
        {
            score = rt::finite(score * rt::int_true_div(2i64, 3i64)?)?;
        }
    }
    if {
        let __needle = index;
        let __container = worker_types;
        __container.contains(&__needle)
    } {
        let mut ignored: i64 = ((64i64 | 256i64) | 128i64);
        let mut unimproved: i64 = ({
            let mut __comprehension_result_922: Vec<bool> = Vec::new();
            let mut tile: Option<crate::openciv3::world::Tile>;
            let __comprehension_source_920 = ((city).residents.clone());
            for resident in __comprehension_source_920.iter().cloned() {
                if ((&(resident).tile_worked).is_some()
                    && ({
                        tile = {
                            let __star_args_921: Vec<i64> = {
                                let __tuple_value = &((*((resident).tile_worked.clone())
                                    .as_ref()
                                    .ok_or("expected a value")?)
                                .clone());
                                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                            };
                            if !(2..=2).contains(&__star_args_921.len()) {
                                return Err("wrong function argument count".into());
                            }
                            crate::openciv3::world::WorldMap__tile_at(
                                &(game).world,
                                rt::at(&__star_args_921, 0 as i64)?,
                                rt::at(&__star_args_921, 1 as i64)?,
                            )?
                        };
                        tile.clone()
                    })
                    .is_some())
                {
                    __comprehension_result_922.push(
                        !((((*(tile.clone()).as_ref().ok_or("expected a value")?).clone())
                            .overlays
                            & !(ignored))
                            != 0),
                    );
                }
            }
            __comprehension_result_922
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        let mut workers: i64 = ({
            let mut __comprehension_result_924: Vec<bool> = Vec::new();
            let __comprehension_source_923 = ((game).units.clone());
            for other in __comprehension_source_923.iter().cloned() {
                __comprehension_result_924.push(
                    (((other).owner == (city).owner) && {
                        let __needle = (other).prototype;
                        let __container = worker_types;
                        __container.contains(&__needle)
                    }),
                );
            }
            __comprehension_result_924
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        if ((unimproved > 0i64)
            && (((workers) as f64) < rt::finite((((own_cities).len() as i64) as f64) * 1.5f64)?))
        {
            score = rt::finite(
                score
                    + (((population_penalty)
                        .checked_mul(
                            (3i64).min((1i64).checked_add(unimproved).ok_or("integer overflow")?),
                        )
                        .ok_or("integer overflow")?) as f64),
            )?;
        }
        network = (if (network).is_some() {
            network.clone()
        } else {
            Some(crate::openciv3::trade_network::TradeNetwork____post_init__(
                crate::openciv3::trade_network::TradeNetwork {
                    game: (*game).clone(),
                    owner: Some((city).owner),
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
            )?)
        });
        if ((((own_cities).len() as i64) > 4i64)
            && !(crate::openciv3::trade_network::TradeNetwork__connected_to_capital(
                &((*(network).as_ref().ok_or("expected a value")?).clone()),
                city,
            )?))
        {
            score = rt::finite(score + ((10i64) as f64))?;
        }
    }
    Ok(score)
}

// Python: civ3_ai/production_ai.py:173
pub(crate) fn weak_economy(player: &crate::openciv3::players::Player) -> rt::Result<bool> {
    Ok((((player).luxury_rate == 0i64)
        && (((player).science_rate == 0i64) && ((player).gold < 100i64))))
}

// Python: civ3_ai/production_ai.py:177
pub(crate) fn score_building(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut index: i64,
    mut corruption: f64,
    mut expanding: bool,
    mut network: Option<crate::openciv3::trade_network::TradeNetwork>,
    mut hydro: Option<crate::openciv3::hydrology::Hydrology>,
) -> rt::Result<f64> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut building: crate::openciv3::building_rules::Building =
        rt::at(&(rules).buildings, index)?;
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (city).owner)?;
    let mut at_war: bool = ({
        let mut __comprehension_result_926: Vec<bool> = Vec::new();
        let __comprehension_source_925 = ((game).players.clone());
        for other in __comprehension_source_925.iter().cloned() {
            __comprehension_result_926.push(
                ((other).included
                    && (!(crate::openciv3::players::Player__barbarian(&other)?)
                        && (!((other).defeated)
                            && crate::openciv3::diplomacy::Diplomacy__at_war(
                                &(game).diplomacy,
                                (city).owner,
                                (other).civilization,
                            )?))),
            );
        }
        __comprehension_result_926
    })
    .into_iter()
    .any(|__value| __value);
    network = (if (network).is_some() {
        network.clone()
    } else {
        Some(crate::openciv3::trade_network::TradeNetwork____post_init__(
            crate::openciv3::trade_network::TradeNetwork {
                game: (*game).clone(),
                owner: Some((city).owner),
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
        )?)
    });
    hydro = (if (hydro).is_some() {
        hydro.clone()
    } else {
        Some(crate::openciv3::hydrology::Hydrology__from_world(
            &(game).world,
        )?)
    });
    let mut score: f64 = 0.0f64;
    let mut flags: i64 = (building).effects;
    if ((flags & 1024i64) != 0i64) {
        let mut luxuries: i64 = crate::openciv3::trade_network::TradeNetwork__luxury_count(
            &((*(network).as_ref().ok_or("expected a value")?).clone()),
            city,
        )?;
        score = rt::finite(
            score
                + (((((crate::openciv3::cities::City__size(city)?)
                    .checked_sub(luxuries)
                    .ok_or("integer overflow")?)
                .max(0i64))
                .checked_mul(rt::int_floor_div(luxuries, 2i64)?)
                .ok_or("integer overflow")?) as f64),
        )?;
    }
    let mut limits: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(rules).global_rules, 0i64)?;
    let mut food: crate::openciv3::city_economy::CityFood =
        crate::openciv3::city_economy::city_food(game, city, &hydro)?;
    if ((flags & 2048i64) != 0
        && ((crate::openciv3::cities::City__size(city)? == (limits).maximum_level1_city_size)
            && ((food).surplus > 0i64)))
    {
        score = rt::finite(score + ((50i64) as f64))?;
    }
    if ((flags & 4096i64) != 0
        && ((crate::openciv3::cities::City__size(city)? == (limits).maximum_level2_city_size)
            && ((food).surplus > 0i64)))
    {
        score = rt::finite(score + ((70i64) as f64))?;
    }
    if crate::openciv3::building_rules::Building__is_wall(&building)? {
        score = rt::finite(score + ((if at_war { 20i64 } else { 8i64 }) as f64))?;
    }
    let mut production: crate::openciv3::city_economy::CityProduction =
        crate::openciv3::city_economy::city_production(game, city, corruption, &hydro, &None)?;
    if ((flags & 256i64) != 0i64) {
        if (city).capital {
            return Ok(-(1e+300f64));
        }
        if (((production).useful > 0i64)
            && (rt::int_true_div((production).lost, (production).useful)? > 0.15f64))
        {
            score = rt::finite(
                score
                    + ((((production).lost)
                        .checked_mul(8i64)
                        .ok_or("integer overflow")?) as f64),
            )?;
        }
    }
    if ((building).content_faces > 0i64) {
        let mut unhappy: i64 = ({
            let mut __comprehension_result_928: Vec<bool> = Vec::new();
            let __comprehension_source_927 = ((city).residents.clone());
            for resident in __comprehension_source_927.iter().cloned() {
                __comprehension_result_928.push(((resident).mood == 2i64));
            }
            __comprehension_result_928
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        let mut entertainers: i64 = ({
            let mut __comprehension_result_930: Vec<bool> = Vec::new();
            let __comprehension_source_929 = ((city).residents.clone());
            for resident in __comprehension_source_929.iter().cloned() {
                __comprehension_result_930.push(
                    (({
                        let __source = &(rules).citizens;
                        let __key = (resident).citizen_type;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .luxuries
                        > 0i64),
                );
            }
            __comprehension_result_930
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        if ((unhappy > 0i64)
            || (((player).luxury_rate > 3i64)
                && (crate::openciv3::cities::City__size(city)? > 4i64)))
        {
            score = rt::finite(
                score
                    + (((((unhappy).min((building).content_faces))
                        .checked_add((entertainers).min((building).content_faces))
                        .ok_or("integer overflow")?)
                    .checked_mul(10i64)
                    .ok_or("integer overflow")?) as f64),
            )?;
        }
    }
    if ((building).culture > 0i64) {
        let mut center: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(&(game).world, (city).x, (city).y)?;
        if (center).is_none() {
            return Err("City is outside the map".to_string().into());
        }
        let mut owners: indexmap::IndexMap<i64, i64> = {
            let mut __comprehension_result_932: indexmap::IndexMap<i64, i64> =
                indexmap::IndexMap::new();
            let __comprehension_source_931 = ((game).cities.clone());
            for other in __comprehension_source_931.iter().cloned() {
                {
                    let (__key, __value) = ((other).id, (other).owner);
                    __comprehension_result_932.insert(__key, __value);
                }
            }
            __comprehension_result_932
        };
        let mut chained_locals_216_8: i64 = 0i64;
        let mut unclaimed: i64 = chained_locals_216_8;
        let mut foreign: i64 = chained_locals_216_8;
        for mut tile in crate::strategy::grid::within_rank(
            &((game).world.clone()),
            &((*(center).as_ref().ok_or("expected a value")?).clone()),
            crate::openciv3::rules::RuleCatalog__workable_rank(&rules)?,
        )? {
            let mut owner: Option<i64> = (owners.clone())
                .get(
                    &({
                        let __mapping = &(game).ownership;
                        let __key = ((tile).x, (tile).y);
                        let __default = (1i64).checked_neg().ok_or("integer overflow")?;
                        __mapping.get(&__key).cloned().unwrap_or(__default)
                    }),
                )
                .cloned();
            if (owner).is_none() {
                unclaimed = (unclaimed).checked_add(1i64).ok_or("integer overflow")?;
            } else {
                if (owner != Some((city).owner)) {
                    foreign = (foreign).checked_add(1i64).ok_or("integer overflow")?;
                }
            }
        }
        let mut culture: i64 = (crate::openciv3::building_effects::culture_rates(
            &(game).cities,
            &(game).players,
            &(game).world,
            &rules,
            (game).year,
        )?)
        .get(&((city).id))
        .ok_or("missing dict key")?
        .clone();
        score = rt::finite(
            score
                + rt::int_true_div(
                    ((building).culture)
                        .checked_mul(
                            (unclaimed)
                                .checked_add((foreign).checked_mul(3i64).ok_or("integer overflow")?)
                                .ok_or("integer overflow")?,
                        )
                        .ok_or("integer overflow")?,
                    (if (culture == 0i64) { 1i64 } else { 2i64 }),
                )?,
        )?;
    }
    if ((flags & 2i64) != 0i64) {
        score = rt::finite(
            score
                + (((rt::int_floor_div(crate::openciv3::cities::City__size(city)?, 5i64)?)
                    .checked_mul((if at_war { 3i64 } else { 1i64 }))
                    .ok_or("integer overflow")?) as f64),
        )?;
    }
    let mut cost: i64 =
        crate::openciv3::production_cost::city_building_cost(game, city, &building)?;
    let mut turns: Option<i64> = crate::openciv3::city_economy::production_turns(
        cost,
        (city).shields_stored,
        (production).useful,
    )?;
    score = rt::finite(
        score
            - ((rt::int_floor_div(
                (if (turns).is_none() {
                    2147483647i64
                } else {
                    (*(turns.clone()).as_ref().ok_or("expected a value")?).clone()
                }),
                (if expanding { 1i64 } else { 2i64 }),
            )?) as f64),
    )?;
    score = rt::finite(score - (((building).maintenance_cost) as f64))?;
    if (!(expanding) && !(at_war)) {
        score = rt::finite(score + ((20i64) as f64))?;
    }
    if weak_economy(&player)? {
        score = rt::finite(
            score
                - (((10i64)
                    .checked_mul((building).maintenance_cost)
                    .ok_or("integer overflow")?) as f64),
        )?;
    }
    Ok(score)
}

// Python: civ3_ai/production_ai.py:239
pub(crate) fn worker_production_types(
    game: &crate::openciv3::game_state::GameState,
) -> rt::Result<std::collections::BTreeSet<i64>> {
    Ok({
        let mut __result: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
        for __item in ({
            let mut __comprehension_result_934: std::collections::BTreeSet<i64> =
                std::collections::BTreeSet::new();
            let __comprehension_source_933 = (((&(&(game).scenario).rules).units.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>());
            for (index, kind) in __comprehension_source_933.iter().cloned() {
                if crate::openciv3::worker_rules::is_worker_prototype(&kind)? {
                    __comprehension_result_934.insert(index);
                }
            }
            __comprehension_result_934
        })
        .into_iter()
        {
            __result.insert(__item);
        }
        __result
    })
}
