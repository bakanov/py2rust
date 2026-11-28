use py2rust_service_runtime as rt;

// Python: civ3_ai/economic_ai.py:17
pub(crate) fn budget_is_tolerable(
    game: &crate::openciv3::game_state::GameState,
    player: &crate::openciv3::players::Player,
) -> rt::Result<bool> {
    let mut income: i64 = crate::openciv3::player_economy::PlayerCommerce__net_gold(
        &(crate::openciv3::player_economy::player_commerce(game, player, None, None)?),
    )?;
    Ok(((income > 0i64)
        || (((income) as f64)
            > rt::finite(
                ((((player).gold).checked_neg().ok_or("integer overflow")?) as f64) * 0.1f64,
            )?)))
}

/// Rebuild assignments one citizen at a time, retaining nationalities.
// Python: civ3_ai/economic_ai.py:22
pub(crate) fn reassign_city_citizens(
    game: &crate::openciv3::game_state::GameState,
    mut city: crate::openciv3::cities::City,
    mut corruption: f64,
    mut luxury_count: i64,
    hydro: &crate::openciv3::hydrology::Hydrology,
) -> rt::Result<()> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (city).owner)?;
    let mut default: Option<i64> = {
        let __find_source_781 = ((rules).citizens.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>();
        let mut __find_result_781: Option<i64> = None;
        for (i, kind) in __find_source_781.iter().cloned() {
            if (kind).default_citizen {
                __find_result_781 = Some(i);
                break;
            }
        }
        __find_result_781
    };
    let mut specialists: Vec<i64> = {
        let mut __comprehension_result_783: Vec<i64> = Vec::new();
        let __comprehension_source_782 = (((rules).citizens.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>());
        for (i, kind) in __comprehension_source_782.iter().cloned() {
            if (!((kind).default_citizen)
                && (((kind).prerequisite < 0i64) || {
                    let __needle = (kind).prerequisite;
                    let __container = &(player).known_technologies;
                    __container.contains(&__needle)
                }))
            {
                __comprehension_result_783.push(i);
            }
        }
        __comprehension_result_783
    };
    if ((default).is_none() || !(((specialists).len() as i64) != 0i64)) {
        return Err(
            "AI citizen management needs laborers and an unlocked specialist"
                .to_string()
                .into(),
        );
    }
    let mut entertainer: i64 = {
        let __values = &specialists;
        let mut __items = __values.iter();
        let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
        let mut __best_key = {
            let index = (*__best).clone();
            ({
                let __source = &(rules).citizens;
                let __key = index;
                &__source[rt::index(__source.len(), __key)?]
            })
            .luxuries
        };
        for __candidate in __items {
            let __key = {
                let index = (*__candidate).clone();
                ({
                    let __source = &(rules).citizens;
                    let __key = index;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .luxuries
            };
            if __key > __best_key {
                __best = __candidate;
                __best_key = __key;
            }
        }
        (*__best).clone()
    };
    let mut center: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (city).x, (city).y)?;
    if !((center).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    let mut centers: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_785: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_784 = ((game).cities.clone());
        for other in __comprehension_source_784.iter().cloned() {
            __comprehension_result_785.insert(((other).x, (other).y));
        }
        __comprehension_result_785
    };
    let mut occupied: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_788: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_786 = ((game).cities.clone());
        for other in __comprehension_source_786.iter().cloned() {
            if ((other).id != (city).id) {
                let __comprehension_source_787 = ((other).residents.clone());
                for resident in __comprehension_source_787.iter().cloned() {
                    if (&(resident).tile_worked).is_some() {
                        __comprehension_result_788.insert(
                            (*((resident).tile_worked.clone())
                                .as_ref()
                                .ok_or("expected a value")?)
                            .clone(),
                        );
                    }
                }
            }
        }
        __comprehension_result_788
    };
    let mut owned: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_790: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_789 = ((game).cities.clone());
        for other in __comprehension_source_789.iter().cloned() {
            if ((other).owner == (city).owner) {
                __comprehension_result_790.insert((other).id);
            }
        }
        __comprehension_result_790
    };
    let mut candidates: Vec<crate::openciv3::world::Tile> = {
        let mut __comprehension_result_792: Vec<crate::openciv3::world::Tile> = Vec::new();
        let __comprehension_source_791 = (crate::strategy::grid::within_rank(
            &((game).world.clone()),
            &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
            crate::openciv3::rules::RuleCatalog__workable_rank(&rules)?,
        )?);
        for tile in __comprehension_source_791.iter().cloned() {
            if ({
                let __needle = ((tile).x, (tile).y);
                let __container = &centers;
                !__container.contains(&__needle)
            } && match (((game).ownership.clone())
                .get(&(((tile).x, (tile).y)))
                .cloned())
            {
                Some(__value) => {
                    let __needle = __value;
                    let __container = &owned;
                    __container.contains(&__needle)
                }
                None => false,
            }) {
                __comprehension_result_792.push(tile.clone());
            }
        }
        __comprehension_result_792
    };
    let mut residents: Vec<crate::openciv3::cities::Resident> =
        (&(city).residents).iter().cloned().collect::<Vec<_>>();
    let mut desired_food: i64 = (((residents).len() as i64)
        .checked_mul(crate::openciv3::rules::RuleCatalog__food_per_citizen(
            &rules,
        )?)
        .ok_or("integer overflow")?)
    .checked_add(2i64)
    .ok_or("integer overflow")?;
    for mut resident in (residents).iter().cloned() {
        resident.tile_worked = None;
        resident.citizen_type = (*(default.clone()).as_ref().ok_or("expected a value")?).clone();
    }
    ((city).residents).clear();

    for mut resident in residents {
        ((city).residents).push(resident.clone());
        let mut food_target: i64 = (desired_food)
            .checked_sub(
                (crate::openciv3::city_economy::city_tile_yields(
                    game,
                    &city,
                    Some((*hydro).clone()),
                )?)
                .food,
            )
            .ok_or("integer overflow")?;
        let mut available: Vec<crate::openciv3::world::Tile> = {
            let mut __comprehension_result_794: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_793 = (candidates.clone());
            for tile in __comprehension_source_793.iter().cloned() {
                if {
                    let __needle = ((tile).x, (tile).y);
                    let __container = &occupied;
                    !__container.contains(&__needle)
                } {
                    __comprehension_result_794.push(tile.clone());
                }
            }
            __comprehension_result_794
        };
        let mut best: Option<crate::openciv3::world::Tile> = '__extreme: {
            let __values = &available;
            let mut __items = __values.iter();
            let Some(mut __best) = __items.next() else {
                break '__extreme None;
            };
            let mut __best_key = {
                let tile = (*__best).clone();
                reassign_city_citizens__resident_score(
                    &player,
                    game,
                    &city,
                    &rules,
                    &tile,
                    food_target,
                )?
            };
            for __candidate in __items {
                let __key = {
                    let tile = (*__candidate).clone();
                    reassign_city_citizens__resident_score(
                        &player,
                        game,
                        &city,
                        &rules,
                        &tile,
                        food_target,
                    )?
                };
                if __key > __best_key {
                    __best = __candidate;
                    __best_key = __key;
                }
            }
            Some((*__best).clone())
        };
        if ((best).is_none()
            || (reassign_city_citizens__resident_score(
                &player,
                game,
                &city,
                &rules,
                &((*(best.clone()).as_ref().ok_or("expected a value")?).clone()),
                food_target,
            )? <= ((0i64) as f64)))
        {
            resident.citizen_type = rt::at(&specialists, 0i64)?;
        } else {
            resident.tile_worked = Some((
                ((*(best.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                ((*(best.clone()).as_ref().ok_or("expected a value")?).clone()).y,
            ));
            {
                occupied.insert(
                    (*((resident).tile_worked.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone(),
                );
            };
        }
        if crate::openciv3::citizen_moods::recalculate_moods(
            game,
            city.clone(),
            corruption,
            Some(luxury_count),
            &(Some((*hydro).clone())),
            &(Some(false)),
        )? {
            let mut target: crate::openciv3::cities::Resident = resident.clone();
            if (&(resident).tile_worked).is_some() {
                food_target = (desired_food)
                    .checked_sub(
                        (crate::openciv3::city_economy::city_tile_yields(
                            game,
                            &city,
                            Some((*hydro).clone()),
                        )?)
                        .food,
                    )
                    .ok_or("integer overflow")?;
                let mut workers: Vec<crate::openciv3::cities::Resident> = {
                    let mut __comprehension_result_796: Vec<crate::openciv3::cities::Resident> =
                        Vec::new();
                    let __comprehension_source_795 = ((city).residents.clone());
                    for other in __comprehension_source_795.iter().cloned() {
                        if (&(other).tile_worked).is_some() {
                            __comprehension_result_796.push(other.clone());
                        }
                    }
                    __comprehension_result_796
                };

                target = rt::at(&(workers.clone()), {
                    let __values = &((0i64..((workers).len() as i64)).collect::<Vec<i64>>());
                    let mut __items = __values.iter();
                    let mut __best = __items.next().ok_or("min() arg is an empty sequence")?;
                    let mut __best_key = {
                        let index = (*__best).clone();
                        reassign_city_citizens__worker_resident_score(
                            &workers,
                            game,
                            &player,
                            &city,
                            &rules,
                            food_target,
                            index,
                        )?
                    };
                    for __candidate in __items {
                        let __key = {
                            let index = (*__candidate).clone();
                            reassign_city_citizens__worker_resident_score(
                                &workers,
                                game,
                                &player,
                                &city,
                                &rules,
                                food_target,
                                index,
                            )?
                        };
                        if __key < __best_key {
                            __best = __candidate;
                            __best_key = __key;
                        }
                    }
                    (*__best).clone()
                })?;
            }
            if (&(target).tile_worked).is_some() {
                if !(occupied).remove(
                    &((*((target).tile_worked.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone()),
                ) {
                    return Err("set.remove: missing item".into());
                };
            }
            target.tile_worked = None;
            target.citizen_type = entertainer;
        }
    }
    crate::openciv3::citizen_moods::recalculate_moods(
        game,
        city,
        corruption,
        Some(luxury_count),
        &(Some((*hydro).clone())),
        &(Some(false)),
    )?;
    Ok(())
}

// Python: civ3_ai/economic_ai.py:79
pub(crate) fn adjust_sliders(
    game: &crate::openciv3::game_state::GameState,
    mut player: crate::openciv3::players::Player,
    mut automated_human: bool,
) -> rt::Result<()> {
    if (((player).human && !(automated_human))
        || crate::openciv3::players::Player__barbarian(&player)?)
    {
        return Err("Automatic sliders require a nonhuman civilization"
            .to_string()
            .into());
    }
    let mut cities: Vec<crate::openciv3::cities::City> = {
        let mut __comprehension_result_798: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_797 = ((game).cities.clone());
        for city in __comprehension_source_797.iter().cloned() {
            if ((city).owner == (player).civilization) {
                __comprehension_result_798.push(city.clone());
            }
        }
        __comprehension_result_798
    };
    let (mut corruption, mut hydro, mut network): (
        indexmap::IndexMap<i64, f64>,
        crate::openciv3::hydrology::Hydrology,
        crate::openciv3::trade_network::TradeNetwork,
    ) = (
        crate::openciv3::corruption::corruption_levels(game)?,
        crate::openciv3::hydrology::Hydrology__from_world(&(game).world)?,
        crate::openciv3::trade_network::TradeNetwork____post_init__(
            crate::openciv3::trade_network::TradeNetwork {
                game: (*game).clone(),
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
        )?,
    );
    let mut luxuries: indexmap::IndexMap<i64, i64> = {
        let mut __comprehension_result_800: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_799 = (cities.clone());
        for city in __comprehension_source_799.iter().cloned() {
            {
                let (__key, __value) = (
                    (city).id,
                    crate::openciv3::trade_network::TradeNetwork__luxury_count(&network, &city)?,
                );
                __comprehension_result_800.insert(__key, __value);
            }
        }
        __comprehension_result_800
    };
    let mut chained_fields_85_4: i64 = 0i64;
    player.science_rate = chained_fields_85_4;
    player.luxury_rate = chained_fields_85_4;
    player.tax_rate = 10i64;
    loop {
        let mut unhappy: i64 = ({
            let mut __comprehension_result_802: Vec<bool> = Vec::new();
            let __comprehension_source_801 = (cities.clone());
            for city in __comprehension_source_801.iter().cloned() {
                __comprehension_result_802.push(crate::openciv3::citizen_moods::recalculate_moods(
                    game,
                    city.clone(),
                    (corruption)
                        .get(&((city).id))
                        .ok_or("missing dict key")?
                        .clone(),
                    Some(
                        (luxuries)
                            .get(&((city).id))
                            .ok_or("missing dict key")?
                            .clone(),
                    ),
                    &(Some(hydro.clone())),
                    &(Some(false)),
                )?);
            }
            __comprehension_result_802
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        if ((((unhappy) as f64) <= rt::finite((((cities).len() as i64) as f64) * 0.1f64)?)
            || ((player).luxury_rate >= 5i64))
        {
            break;
        }
        player.luxury_rate = ((player).luxury_rate)
            .checked_add(1i64)
            .ok_or("integer overflow")?;
        player.tax_rate = ((player).tax_rate)
            .checked_sub(1i64)
            .ok_or("integer overflow")?;
    }
    for mut city in cities {
        {
            let __call_803_0 = game;
            let __call_803_1 = city.clone();
            let __call_803_2 = (corruption)
                .get(&((city).id))
                .ok_or("missing dict key")?
                .clone();
            let __call_803_3 = (luxuries)
                .get(&((city).id))
                .ok_or("missing dict key")?
                .clone();
            let __call_803_4 = &hydro;
            reassign_city_citizens(
                __call_803_0,
                __call_803_1,
                __call_803_2,
                __call_803_3,
                __call_803_4,
            )
        }?;
    }
    player.science_rate = (10i64)
        .checked_sub((player).luxury_rate)
        .ok_or("integer overflow")?;
    player.tax_rate = 0i64;
    while (((player).science_rate > 0i64) && !(budget_is_tolerable(game, &player)?)) {
        player.science_rate = ((player).science_rate)
            .checked_sub(1i64)
            .ok_or("integer overflow")?;
        player.tax_rate = ((player).tax_rate)
            .checked_add(1i64)
            .ok_or("integer overflow")?;
    }
    Ok(())
}

// Python: civ3_ai/economic_ai.py:46
pub(crate) fn reassign_city_citizens__resident_score(
    player: &crate::openciv3::players::Player,
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    rules: &crate::openciv3::rules::RuleCatalog,
    tile: &crate::openciv3::world::Tile,
    mut target_food: i64,
) -> rt::Result<f64> {
    let mut value: crate::civ::economy::Yield = {
        let __call_804_0 = &((*tile).clone());
        let __call_804_1 = &((*player).clone());
        let __call_804_2 = &(Some(rt::at(&(&(game).scenario).civilizations, (city).owner)?));
        let __call_804_3 = &((*rules).clone());
        let __call_804_4 =
            &(Some((crate::openciv3::hydrology::river_edges(&(game).world, tile)?) != 0));
        let __call_804_default_4 = &None;
        let __call_804_default_5 = false;
        let __call_804_default_6 = false;
        let __call_804_default_7 = &(vec![]);
        crate::openciv3::yields::tile_yield(
            __call_804_0,
            __call_804_1,
            __call_804_2,
            __call_804_3,
            __call_804_default_4,
            __call_804_default_5,
            __call_804_default_6,
            __call_804_default_7,
            __call_804_4,
        )
    }?;
    crate::openciv3::yields::tile_assignment_score(&value, target_food)
}

// Python: civ3_ai/economic_ai.py:65
pub(crate) fn reassign_city_citizens__worker_resident_score(
    workers: &[crate::openciv3::cities::Resident],
    game: &crate::openciv3::game_state::GameState,
    player: &crate::openciv3::players::Player,
    city: &crate::openciv3::cities::City,
    rules: &crate::openciv3::rules::RuleCatalog,
    mut food_target: i64,
    mut index: i64,
) -> rt::Result<f64> {
    let mut point: Option<(i64, i64)> = ({
        let __source = workers;
        let __key = index;
        &__source[rt::index(__source.len(), __key)?]
    })
    .tile_worked
    .clone();
    if !((point).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    let mut tile: Option<crate::openciv3::world::Tile> = {
        let __star_args_805: Vec<i64> = {
            let __tuple_value = &((*(point).as_ref().ok_or("expected a value")?).clone());
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        };
        if !(2..=2).contains(&__star_args_805.len()) {
            return Err("wrong function argument count".into());
        }
        crate::openciv3::world::WorldMap__tile_at(
            &(game).world,
            rt::at(&__star_args_805, 0 as i64)?,
            rt::at(&__star_args_805, 1 as i64)?,
        )?
    };
    if !((tile).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    reassign_city_citizens__resident_score(
        player,
        game,
        city,
        rules,
        &((*(tile).as_ref().ok_or("expected a value")?).clone()),
        food_target,
    )
}
