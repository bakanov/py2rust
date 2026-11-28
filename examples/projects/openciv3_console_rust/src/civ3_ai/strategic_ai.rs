use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct StrategyUpdate {
    pub(crate) priorities: Vec<String>,
    pub(crate) weights: Vec<(String, f64)>,
    pub(crate) declaration: Option<crate::openciv3::diplomacy_actions::WarDeclaration>,
}

// Python: civ3_ai/strategic_ai.py:28
pub(crate) fn military_strength(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<i64> {
    let mut total: i64 = 4i64;
    for mut unit in (&(game).units).iter() {
        if ((unit).owner == owner) {
            let mut kind: crate::openciv3::unit_rules::UnitPrototype =
                rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
            total = (total)
                .checked_add(
                    ((crate::openciv3::unit_turns::max_hit_points(game, unit)?)
                        .checked_mul(
                            (((kind).attack)
                                .checked_mul(3i64)
                                .ok_or("integer overflow")?)
                            .checked_add(
                                ((kind).defense)
                                    .checked_mul(2i64)
                                    .ok_or("integer overflow")?,
                            )
                            .ok_or("integer overflow")?,
                        )
                        .ok_or("integer overflow")?)
                    .checked_add((kind).bombard_strength)
                    .ok_or("integer overflow")?,
                )
                .ok_or("integer overflow")?;
        }
    }
    Ok(total)
}

// Python: civ3_ai/strategic_ai.py:37
pub(crate) fn available_land_score(
    game: &crate::openciv3::game_state::GameState,
    player: &crate::openciv3::players::Player,
) -> rt::Result<f64> {
    let mut city: Option<crate::openciv3::cities::City> = {
        let __find_source_1020 = (game).cities.clone();
        let mut __find_result_1020: Option<crate::openciv3::cities::City> = None;
        for city in __find_source_1020.iter().cloned() {
            if ((city).owner == (player).civilization) {
                __find_result_1020 = Some(city.clone());
                break;
            }
        }
        __find_result_1020
    };
    if (city).is_none() {
        return Ok(0.0f64);
    }
    let mut scores: indexmap::IndexMap<(i64, i64), f64> = {
        let __call_1021_0 = &((*game).clone());
        let __call_1021_1 = &((*player).clone());
        let __call_1021_2 = &((
            ((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).x,
            ((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).y,
        ));
        let __call_1021_3 = &(crate::openciv3::unit_missions::reserved_settlements(
            game,
            (player).civilization,
            &None,
        )?);
        let __call_1021_default_4 = &({
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        });
        let __call_1021_default_5 = &(crate::civ3_ai::settler_locations::SettlerWeights {
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
        let __call_1021_default_6 = None;
        crate::civ3_ai::settler_locations::settlement_scores(
            __call_1021_0,
            __call_1021_1,
            __call_1021_2,
            __call_1021_3,
            __call_1021_default_4,
            __call_1021_default_5,
            __call_1021_default_6,
        )
    }?;
    Ok(rt::finite(
        (((2i64)
            .checked_mul(((scores).len() as i64))
            .ok_or("integer overflow")?) as f64)
            + ({
                let mut __comprehension_result_1023: Vec<f64> = Vec::new();
                let __comprehension_source_1022 =
                    ((scores.clone()).values().cloned().collect::<Vec<_>>());
                for score in __comprehension_source_1022.iter().cloned() {
                    __comprehension_result_1023.push(rt::float_true_div(score, ((10i64) as f64))?);
                }
                __comprehension_result_1023
            })
            .into_iter()
            .sum::<f64>(),
    )?)
}

// Python: civ3_ai/strategic_ai.py:45
pub(crate) fn opponent_scores(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<indexmap::IndexMap<i64, f64>> {
    let mut cities: indexmap::IndexMap<i64, crate::openciv3::cities::City> = {
        let mut __comprehension_result_1025: indexmap::IndexMap<
            i64,
            crate::openciv3::cities::City,
        > = indexmap::IndexMap::new();
        let __comprehension_source_1024 = ((game).cities.clone());
        for city in __comprehension_source_1024.iter().cloned() {
            {
                let (__key, __value) = ((city).id, city.clone());
                __comprehension_result_1025.insert(__key, __value);
            }
        }
        __comprehension_result_1025
    };
    let mut border: indexmap::IndexMap<i64, std::collections::BTreeSet<(i64, i64)>> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut tile in (&(&(game).world).tiles).iter() {
        let mut claim: Option<i64> = ((game).ownership.clone())
            .get(&(((tile).x, (tile).y)))
            .cloned();
        if ((claim).is_none()
            || (((cities)
                .get(&((*(claim.clone()).as_ref().ok_or("expected a value")?).clone()))
                .ok_or("missing dict key")?)
            .owner
                != owner))
        {
            continue;
        }
        for mut neighbor in crate::openciv3::world::WorldMap__neighbors(&(game).world, tile)? {
            let mut adjacent: Option<i64> = ((game).ownership.clone())
                .get(&(((neighbor).x, (neighbor).y)))
                .cloned();
            if (adjacent).is_some() {
                ((border)
                    .entry(
                        ((cities)
                            .get(&((*(adjacent).as_ref().ok_or("expected a value")?).clone()))
                            .ok_or("missing dict key")?)
                        .owner,
                    )
                    .or_insert(std::collections::BTreeSet::new())
                    .clone())
                .insert(((neighbor).x, (neighbor).y));
            }
        }
    }
    let mut own_centers: Vec<Option<crate::openciv3::world::Tile>> = {
        let mut __comprehension_result_1027: Vec<Option<crate::openciv3::world::Tile>> = Vec::new();
        let __comprehension_source_1026 = ((game).cities.clone());
        for city in __comprehension_source_1026.iter().cloned() {
            if ((city).owner == owner) {
                __comprehension_result_1027.push(crate::openciv3::world::WorldMap__tile_at(
                    &(game).world,
                    (city).x,
                    (city).y,
                )?);
            }
        }
        __comprehension_result_1027
    };
    let mut strength: i64 = military_strength(game, owner)?;
    let mut scores: indexmap::IndexMap<i64, f64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut player in (&(game).players).iter() {
        let mut other: i64 = (player).civilization;
        if ((other == owner)
            || (crate::openciv3::players::Player__barbarian(player)?
                || (!((player).included)
                    || ((player).defeated
                        || crate::openciv3::diplomacy::Diplomacy__locked_peace(
                            &(game).diplomacy,
                            owner,
                            other,
                        )?))))
        {
            continue;
        }
        let mut centers: Vec<Option<crate::openciv3::world::Tile>> = {
            let mut __comprehension_result_1029: Vec<Option<crate::openciv3::world::Tile>> =
                Vec::new();
            let __comprehension_source_1028 = ((game).cities.clone());
            for city in __comprehension_source_1028.iter().cloned() {
                if ((city).owner == other) {
                    __comprehension_result_1029.push(crate::openciv3::world::WorldMap__tile_at(
                        &(game).world,
                        (city).x,
                        (city).y,
                    )?);
                }
            }
            __comprehension_result_1029
        };
        let mut nearest: i64 = '__extreme: {
            let __values = &({
                let mut __comprehension_result_1032: Vec<i64> = Vec::new();
                let __comprehension_source_1030 = (own_centers.clone());
                for first in __comprehension_source_1030.iter().cloned() {
                    let __comprehension_source_1031 = (centers.clone());
                    for second in __comprehension_source_1031.iter().cloned() {
                        if ((first).is_some()
                            && ((second).is_some()
                                && (((*(first.clone()).as_ref().ok_or("expected a value")?)
                                    .clone())
                                .continent
                                    == ((*(second.clone())
                                        .as_ref()
                                        .ok_or("expected a value")?)
                                    .clone())
                                    .continent)))
                        {
                            __comprehension_result_1032.push(crate::strategy::grid::distance(
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
                                        (*(first.clone()).as_ref().ok_or("expected a value")?)
                                            .clone();
                                    crate::strategy::grid::GridPoint {
                                        x: (__structural_value).x.clone(),
                                        y: (__structural_value).y.clone(),
                                    }
                                }),
                                &({
                                    let __structural_value =
                                        (*(second.clone()).as_ref().ok_or("expected a value")?)
                                            .clone();
                                    crate::strategy::grid::GridPoint {
                                        x: (__structural_value).x.clone(),
                                        y: (__structural_value).y.clone(),
                                    }
                                }),
                            )?);
                        }
                    }
                }
                __comprehension_result_1032
            });
            let mut __items = __values.iter();
            let Some(mut __best) = __items.next() else {
                break '__extreme ({
                    let __exponent = 31i64;
                    if __exponent < 0 {
                        return Err("negative integer exponent".into());
                    }
                    (2i64)
                        .checked_pow(__exponent as u32)
                        .ok_or("integer power overflow")?
                })
                .checked_sub(1i64)
                .ok_or("integer overflow")?;
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
                if __key < __best_key {
                    __best = __candidate;
                    __best_key = __key;
                }
            }
            (*__best).clone()
        };
        {
            let __value = rt::int_true_div(
                ((({
                    let __key = other;
                    let __default = std::collections::BTreeSet::new();
                    border.get(&__key).cloned().unwrap_or(__default)
                })
                .len() as i64)
                    .checked_sub(nearest)
                    .ok_or("integer overflow")?)
                .checked_mul(strength)
                .ok_or("integer overflow")?,
                military_strength(game, other)?,
            )?;
            let __key = other;
            scores.insert(__key, __value);
        }
    }
    Ok(scores)
}

// Python: civ3_ai/strategic_ai.py:70
pub(crate) fn rank_priorities(
    weights: &[(String, f64)],
    mut rng: rt::Random,
) -> rt::Result<Vec<String>> {
    let mut pending: Vec<(String, f64)> = {
        let mut __decorated: Vec<(f64, (String, f64))> = Vec::new();
        for __item in (weights.to_vec()).into_iter() {
            let item = __item;
            let __key = { (item).1.clone() };
            __decorated.push((__key, item));
        }
        __decorated.sort_by(|left, right| {
            if false {
                right.0.total_cmp(&left.0)
            } else {
                left.0.total_cmp(&right.0)
            }
        });
        let mut __result = Vec::new();
        for (_, __item) in __decorated {
            __result.push(__item);
        }
        __result
    };
    let mut ranked: Vec<String> = vec![];
    while (((pending).len() as i64) != 0i64) {
        let mut total: Box<dyn std::any::Any> = Box::new(
            ({
                let mut __comprehension_result_1034: Vec<f64> = Vec::new();
                let __comprehension_source_1033 = (pending.clone());
                for (_, weight) in __comprehension_source_1033.iter().cloned() {
                    __comprehension_result_1034.push((0.0f64).max(weight));
                }
                __comprehension_result_1034
            })
            .into_iter()
            .sum::<f64>(),
        ) as Box<dyn std::any::Any>;
        let mut draw: f64 = rt::finite(
            rt::random_random(&rng)
                * if let Some(__value) = (&(total)).downcast_ref::<f64>() {
                    *__value
                } else if let Some(__value) = (&(total)).downcast_ref::<i64>() {
                    *__value as f64
                } else {
                    return Err("numeric union mismatch".into());
                },
        )?;
        let mut selected: i64 = ((pending).len() as i64)
            .checked_sub(1i64)
            .ok_or("integer overflow")?;
        for mut for_target_80_8 in (pending.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>()
        {
            let (mut index, (_, mut weight)): (i64, (String, f64)) = for_target_80_8;
            draw = rt::finite(draw - (0.0f64).max(weight))?;
            if (draw < ((0i64) as f64)) {
                selected = index;
                break;
            }
        }
        {
            ranked.push(
                ({
                    let __key = selected;
                    let __index = rt::index(pending.len(), __key)?;
                    pending.remove(__index)
                })
                .0
                .clone(),
            );
        };
    }
    Ok((ranked).iter().cloned().collect::<Vec<_>>())
}

// Python: civ3_ai/strategic_ai.py:89
pub(crate) fn reevaluate_priorities(
    game: &crate::openciv3::game_state::GameState,
    mut player: crate::openciv3::players::Player,
    mut rng: rt::Random,
    mut automated_human: bool,
) -> rt::Result<Option<StrategyUpdate>> {
    if (((player).human && !(automated_human))
        || (crate::openciv3::players::Player__barbarian(&player)?
            || ((player).defeated || !((player).included))))
    {
        return Err("Strategic priorities require an active AI civilization"
            .to_string()
            .into());
    }
    if ((player).turns_until_priority_reevaluation > 0i64) {
        player.turns_until_priority_reevaluation = ((player).turns_until_priority_reevaluation)
            .checked_sub(1i64)
            .ok_or("integer overflow")?;
        return Ok(None);
    }
    let mut own_cities: Vec<crate::openciv3::cities::City> = {
        let mut __comprehension_result_1036: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_1035 = ((game).cities.clone());
        for city in __comprehension_source_1035.iter().cloned() {
            if ((city).owner == (player).civilization) {
                __comprehension_result_1036.push(city.clone());
            }
        }
        __comprehension_result_1036
    };
    let mut percent: i64 = rt::int_floor_div(
        ((game).turn)
            .checked_mul(100i64)
            .ok_or("integer overflow")?,
        540i64,
    )?;
    let mut land: f64 = (if (((own_cities).len() as i64) >= 2i64) {
        available_land_score(game, &player)?
    } else {
        0.0f64
    });
    let mut expansion: f64 = (if (((own_cities).len() as i64) < 2i64) {
        1000.0f64
    } else {
        rt::finite(
            land * (if (percent < 25i64) {
                rt::int_true_div(
                    (25i64).checked_sub(percent).ok_or("integer overflow")?,
                    5i64,
                )?
            } else {
                ((1i64) as f64)
            }),
        )?
    });
    let mut war: f64 = 0.0f64;
    let mut declaration: Option<crate::openciv3::diplomacy_actions::WarDeclaration> = None;
    if (((own_cities).len() as i64) >= 2i64) {
        if ({
            let mut __comprehension_result_1038: Vec<bool> = Vec::new();
            let __comprehension_source_1037 = (((&(game).diplomacy).relationships.clone())
                .iter()
                .map(|(__key, __value)| (__key.clone(), __value.clone()))
                .collect::<Vec<_>>());
            for ((left, _), relationship) in __comprehension_source_1037.iter().cloned() {
                __comprehension_result_1038
                    .push(((left == (player).civilization) && (relationship).at_war));
            }
            __comprehension_result_1038
        })
        .into_iter()
        .any(|__value| __value)
        {
            war = 1000.0f64;
        } else {
            if ((land < ((1i64) as f64))
                && ((crate::openciv3::player_economy::unit_support(game, &player)?).cost > 0i64))
            {
                let mut opponents: indexmap::IndexMap<i64, f64> =
                    opponent_scores(game, (player).civilization)?;
                if (((opponents).len() as i64) != 0i64) {
                    let mut opponent: i64 = {
                        let __values = &((opponents).keys().cloned().collect::<Vec<_>>());
                        let mut __items = __values.iter();
                        let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
                        let mut __best_key = {
                            let other = (*__best).clone();
                            (opponents).get(&(other)).ok_or("missing dict key")?.clone()
                        };
                        for __candidate in __items {
                            let __key = {
                                let other = (*__candidate).clone();
                                (opponents).get(&(other)).ok_or("missing dict key")?.clone()
                            };
                            if __key > __best_key {
                                __best = __candidate;
                                __best_key = __key;
                            }
                        }
                        (*__best).clone()
                    };
                    declaration = Some({
                        let __call_1039_0 = (*game).clone();
                        let __call_1039_1 = (player).civilization;
                        let __call_1039_2 = opponent;
                        let __call_1039_3 = rng.clone();
                        crate::openciv3::diplomacy_actions::declare_war(
                            __call_1039_0,
                            __call_1039_1,
                            __call_1039_2,
                            __call_1039_3,
                        )
                    }?);
                    war = 1000.0f64;
                }
            }
        }
    }
    let mut weights: Vec<(String, f64)> = vec![
        ("expansion".to_string(), expansion),
        (
            "exploration".to_string(),
            ((100i64)
                .checked_sub((2i64).checked_mul(percent).ok_or("integer overflow")?)
                .ok_or("integer overflow")? as f64),
        ),
        ("war".to_string(), war),
    ];
    player.strategic_priorities = rank_priorities(&weights, rng.clone())?;
    player.turns_until_priority_reevaluation = (15i64)
        .checked_add(rt::random_randrange(&rng, 0i64, 10i64)?)
        .ok_or("integer overflow")?;
    for mut unit in (&(game).units).iter().cloned() {
        if ((unit).owner == (player).civilization) {
            unit.fortified = false;
        }
    }
    Ok(Some(StrategyUpdate {
        priorities: (player).strategic_priorities.clone(),
        weights: weights,
        declaration: declaration,
    }))
}
