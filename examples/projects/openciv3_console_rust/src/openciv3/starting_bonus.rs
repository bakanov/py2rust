use py2rust_service_runtime as rt;

/// Called once by the round controller, after incrementing to turn one.
// Python: openciv3/starting_bonus.py:9
pub(crate) fn spawn_starting_bonus(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<Vec<crate::openciv3::units::Unit>> {
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, owner)?;
    let mut cities: Vec<crate::openciv3::cities::City> = {
        let mut __comprehension_result_1171: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_1170 = ((game).cities.clone());
        for city in __comprehension_source_1170.iter().cloned() {
            if ((city).owner == owner) {
                __comprehension_result_1171.push(city.clone());
            }
        }
        __comprehension_result_1171
    };
    if (((game).turn != 1i64)
        || ((player).human
            || (crate::openciv3::players::Player__barbarian(&player)?
                || (((cities).len() as i64) != 1i64))))
    {
        return Ok(vec![]);
    }
    let mut city: crate::openciv3::cities::City = rt::at(&cities, 0i64)?;
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut difficulty: crate::openciv3::scenario_model::Difficulty =
        rt::at(&(&(game).scenario).difficulties, (game).difficulty)?;
    let mut global_rules: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(rules).global_rules, 0i64)?;
    let mut prototypes: Vec<i64> = vec![];
    for mut for_target_20_4 in {
        let __tuple_items = (
            (
                (difficulty).extra_start_unit_1,
                (global_rules).start_unit_type1,
            ),
            (
                (difficulty).extra_start_unit_2,
                (global_rules).start_unit_type2,
            ),
        );
        [__tuple_items.0, __tuple_items.1]
    } {
        let (mut count, mut prototype): (i64, i64) = for_target_20_4;
        if (count > 0i64) {
            if !({
                let __compare_0 = 0i64;
                let __compare_1 = prototype;
                if (__compare_0 <= __compare_1) {
                    let __compare_2 = ((&(rules).units).len() as i64);
                    (__compare_1 < __compare_2)
                } else {
                    false
                }
            }) {
                return Err("Invalid bonus starting unit prototype".to_string().into());
            }
            {
                let __values = (vec![prototype]).repeat(std::cmp::max(count, 0) as usize);
                prototypes.extend(__values);
            };
        }
    }
    if (((difficulty).ai_defensive_units > 0i64) || ((difficulty).ai_offensive_units > 0i64)) {
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
        let mut candidates: Vec<i64> = {
            let mut __comprehension_result_1174: Vec<i64> = Vec::new();
            let __comprehension_source_1172 =
                ((0i64..((&(rules).units).len() as i64)).collect::<Vec<i64>>());
            for index in __comprehension_source_1172.iter().cloned() {
                if {
                    let __call_1173_0 = game;
                    let __call_1173_1 = &city;
                    let __call_1173_2 = index;
                    let __call_1173_3 = Some(network.clone());
                    let __call_1173_default_3 = None;
                    crate::openciv3::production_eligibility::can_train(
                        __call_1173_0,
                        __call_1173_1,
                        __call_1173_2,
                        __call_1173_default_3,
                        __call_1173_3,
                    )
                }? {
                    __comprehension_result_1174.push(index);
                }
            }
            __comprehension_result_1174
        };
        if !(((candidates).len() as i64) != 0i64) {
            return Err("No eligible military starting unit".to_string().into());
        }
        let mut defender: i64 = {
            let __values = &candidates;
            let mut __items = __values.iter();
            let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
            let mut __best_key = {
                let index = (*__best).clone();
                ({
                    let __source = &(rules).units;
                    let __key = index;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .defense
            };
            for __candidate in __items {
                let __key = {
                    let index = (*__candidate).clone();
                    ({
                        let __source = &(rules).units;
                        let __key = index;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .defense
                };
                if __key > __best_key {
                    __best = __candidate;
                    __best_key = __key;
                }
            }
            (*__best).clone()
        };
        let mut attacker: i64 = {
            let __values = &candidates;
            let mut __items = __values.iter();
            let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
            let mut __best_key = {
                let index = (*__best).clone();
                ({
                    let __source = &(rules).units;
                    let __key = index;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .attack
            };
            for __candidate in __items {
                let __key = {
                    let index = (*__candidate).clone();
                    ({
                        let __source = &(rules).units;
                        let __key = index;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .attack
                };
                if __key > __best_key {
                    __best = __candidate;
                    __best_key = __key;
                }
            }
            (*__best).clone()
        };
        {
            let __values =
                (vec![defender]).repeat(std::cmp::max((difficulty).ai_defensive_units, 0) as usize);
            prototypes.extend(__values);
        };
        {
            let __values =
                (vec![attacker]).repeat(std::cmp::max((difficulty).ai_offensive_units, 0) as usize);
            prototypes.extend(__values);
        };
    }
    Ok(({
        let mut __comprehension_result_1176: Vec<crate::openciv3::units::Unit> = Vec::new();
        let __comprehension_source_1175 = (prototypes.clone());
        for prototype in __comprehension_source_1175.iter().cloned() {
            __comprehension_result_1176.push(crate::openciv3::city_production::create_city_unit(
                (*game).clone(),
                &city,
                prototype,
            )?);
        }
        __comprehension_result_1176
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>())
}
