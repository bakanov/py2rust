use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum VictoryKind {
    DOMINATION,
    CONQUEST,
    SPACE_RACE,
    CULTURAL,
    CITY_ELIMINATION,
    REGICIDE,
    WONDER,
    VICTORY_POINTS,
    TIME_LIMIT,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct VictoryResult {
    pub(crate) owner: i64,
    pub(crate) kind: Option<VictoryKind>,
    pub(crate) turn: Option<i64>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct VictoryStatus {
    pub(crate) owner: i64,
    pub(crate) rivals_alive: i64,
    pub(crate) area_percent: Option<i64>,
    pub(crate) population_percent: Option<i64>,
    pub(crate) score: i64,
    pub(crate) current_turn_score: i64,
    pub(crate) turn: i64,
    pub(crate) culture: i64,
    pub(crate) largest_city_culture: i64,
    pub(crate) members: Vec<i64>,
    pub(crate) victory_points: i64,
}

// Python: openciv3/victory.py:53
pub(crate) fn victory_alliance(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<Option<i64>> {
    if ((&(&(game).scenario).options).alliance_victory_type == 1i64) {
        return Ok(((&(game).diplomacy).membership.clone())
            .get(&(owner))
            .cloned());
    }
    Ok(None)
}

// Python: openciv3/victory.py:59
pub(crate) fn victory_name(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<String> {
    let mut alliance: Option<i64> = victory_alliance(game, owner)?;
    if (alliance).is_some() {
        return Ok(
            match (((&(game).diplomacy).alliance_names.clone())
                .get(&((*(alliance.clone()).as_ref().ok_or("expected a value")?).clone()))
                .cloned())
            {
                Some(__value) => __value,
                None => {
                    let __separator = &(String::new());
                    (&(vec![
                        "Alliance ".to_string(),
                        ((*(alliance.clone()).as_ref().ok_or("expected a value")?).clone())
                            .to_string(),
                    ]))
                        .join(__separator)
                }
            },
        );
    }
    Ok(({
        let __source = &(&(game).scenario).civilizations;
        let __key = owner;
        &__source[rt::index(__source.len(), __key)?]
    })
    .name
    .clone())
}

// Python: openciv3/victory.py:66
pub(crate) fn victory_statuses(
    game: &crate::openciv3::game_state::GameState,
) -> rt::Result<Vec<VictoryStatus>> {
    let mut groups: indexmap::IndexMap<i64, Vec<i64>> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut player in crate::openciv3::game_state::GameState__players_in_order(game)? {
        if ((player).included
            && (!(crate::openciv3::players::Player__barbarian(&player)?) && !((player).defeated)))
        {
            let mut owner: i64 = (player).civilization;
            let mut alliance: Option<i64> = victory_alliance(game, owner)?;
            {
                groups
                    .entry(
                        (if (alliance).is_none() {
                            owner
                        } else {
                            ((*(alliance.clone()).as_ref().ok_or("expected a value")?).clone())
                                .checked_neg()
                                .ok_or("integer overflow")?
                        }),
                    )
                    .or_insert(vec![])
                    .push(owner);
                ()
            };
        }
    }
    let mut eligible_tiles: Vec<crate::openciv3::world::Tile> = {
        let mut __comprehension_result_374: Vec<crate::openciv3::world::Tile> = Vec::new();
        let __comprehension_source_373 = ((&(game).world).tiles.clone());
        for tile in __comprehension_source_373.iter().cloned() {
            if {
                let __needle = (tile).base_terrain;
                let __container = &({
                    let __tuple_value = &((12i64, 13i64));
                    vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                });
                !__container.contains(&__needle)
            } {
                __comprehension_result_374.push(tile.clone());
            }
        }
        __comprehension_result_374
    };
    let mut total_population: i64 = ({
        let mut __comprehension_result_376: Vec<i64> = Vec::new();
        let __comprehension_source_375 = ((game).cities.clone());
        for city in __comprehension_source_375.iter().cloned() {
            __comprehension_result_376.push(crate::openciv3::cities::City__size(&city)?);
        }
        __comprehension_result_376
    })
    .into_iter()
    .sum::<i64>();
    let mut result: Vec<VictoryStatus> = vec![];
    for mut members in (groups.clone()).values().cloned().collect::<Vec<_>>() {
        let mut owner: i64 = rt::at(&members, 0i64)?;
        let mut cities: Vec<crate::openciv3::cities::City> = {
            let mut __comprehension_result_378: Vec<crate::openciv3::cities::City> = Vec::new();
            let __comprehension_source_377 = ((game).cities.clone());
            for city in __comprehension_source_377.iter().cloned() {
                if {
                    let __needle = (city).owner;
                    let __container = &members;
                    __container.contains(&__needle)
                } {
                    __comprehension_result_378.push(city.clone());
                }
            }
            __comprehension_result_378
        };
        let mut ids: std::collections::BTreeSet<i64> = {
            let mut __comprehension_result_380: std::collections::BTreeSet<i64> =
                std::collections::BTreeSet::new();
            let __comprehension_source_379 = (cities.clone());
            for city in __comprehension_source_379.iter().cloned() {
                __comprehension_result_380.insert((city).id);
            }
            __comprehension_result_380
        };
        let mut known: std::collections::BTreeSet<(i64, i64)> = std::collections::BTreeSet::new();
        for mut member in (members).iter().copied() {
            (known).extend(
                ((&(game).visibility)
                    .get(&(member))
                    .ok_or("missing dict key")?)
                .known
                .clone(),
            );
        }
        let mut area: i64 = ({
            let mut __comprehension_result_382: Vec<bool> = Vec::new();
            let __comprehension_source_381 = (eligible_tiles.clone());
            for tile in __comprehension_source_381.iter().cloned() {
                __comprehension_result_382.push(
                    ({
                        let __needle = ((tile).x, (tile).y);
                        let __container = &known;
                        __container.contains(&__needle)
                    } && match (((game).ownership.clone())
                        .get(&(((tile).x, (tile).y)))
                        .cloned())
                    {
                        Some(__value) => {
                            let __needle = __value;
                            let __container = &ids;
                            __container.contains(&__needle)
                        }
                        None => false,
                    }),
                );
            }
            __comprehension_result_382
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        let mut history: Vec<Vec<crate::openciv3::history::HistoryRecord>> = {
            let mut __comprehension_result_384: Vec<Vec<crate::openciv3::history::HistoryRecord>> =
                Vec::new();
            let __comprehension_source_383 = (members.clone());
            for member in __comprehension_source_383.iter().cloned() {
                __comprehension_result_384.push({
                    let __mapping = &(game).history;
                    let __key = member;
                    let __default = vec![];
                    __mapping.get(&__key).cloned().unwrap_or(__default)
                });
            }
            __comprehension_result_384
        };
        let mut culture: Vec<i64> = {
            let mut __comprehension_result_386: Vec<i64> = Vec::new();
            let __comprehension_source_385 = (cities.clone());
            for city in __comprehension_source_385.iter().cloned() {
                __comprehension_result_386.push({
                    let __mapping = &(city).culture;
                    let __key = (city).owner;
                    let __default = 0i64;
                    __mapping.get(&__key).cloned().unwrap_or(__default)
                });
            }
            __comprehension_result_386
        };
        {
            result.push(VictoryStatus {
                owner: owner,
                rivals_alive: ((groups).len() as i64)
                    .checked_sub(1i64)
                    .ok_or("integer overflow")?,
                area_percent: (if (((eligible_tiles).len() as i64) != 0i64) {
                    Some(rt::int_floor_div(
                        (area).checked_mul(100i64).ok_or("integer overflow")?,
                        ((eligible_tiles).len() as i64),
                    )?)
                } else {
                    None
                }),
                population_percent: (if (total_population != 0i64) {
                    Some(rt::int_floor_div(
                        (({
                            let mut __comprehension_result_388: Vec<i64> = Vec::new();
                            let __comprehension_source_387 = (cities.clone());
                            for city in __comprehension_source_387.iter().cloned() {
                                __comprehension_result_388
                                    .push(crate::openciv3::cities::City__size(&city)?);
                            }
                            __comprehension_result_388
                        })
                        .into_iter()
                        .sum::<i64>())
                        .checked_mul(100i64)
                        .ok_or("integer overflow")?,
                        total_population,
                    )?)
                } else {
                    None
                }),
                score: ({
                    let mut __comprehension_result_390: Vec<i64> = Vec::new();
                    let __comprehension_source_389 = (history.clone());
                    for records in __comprehension_source_389.iter().cloned() {
                        if (((records).len() as i64) != 0i64) {
                            __comprehension_result_390.push(
                                ({
                                    let __source = &records;
                                    let __key = (1i64).checked_neg().ok_or("integer overflow")?;
                                    &__source[rt::index(__source.len(), __key)?]
                                })
                                .score,
                            );
                        }
                    }
                    __comprehension_result_390
                })
                .into_iter()
                .sum::<i64>(),
                current_turn_score: ({
                    let mut __comprehension_result_392: Vec<i64> = Vec::new();
                    let __comprehension_source_391 = (members.clone());
                    for member in __comprehension_source_391.iter().cloned() {
                        __comprehension_result_392
                            .push(crate::openciv3::history::turn_score(game, member)?);
                    }
                    __comprehension_result_392
                })
                .into_iter()
                .sum::<i64>(),
                turn: (game).turn,
                culture: (culture.clone()).into_iter().sum::<i64>(),
                largest_city_culture: '__extreme: {
                    let __values = &culture;
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
                },
                members: (members).iter().cloned().collect::<Vec<_>>(),
                victory_points: ({
                    let mut __comprehension_result_394: Vec<i64> = Vec::new();
                    let __comprehension_source_393 = (members.clone());
                    for member in __comprehension_source_393.iter().cloned() {
                        __comprehension_result_394.push(
                            ({
                                let __source = &(game).players;
                                let __key = member;
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .victory_points,
                        );
                    }
                    __comprehension_result_394
                })
                .into_iter()
                .sum::<i64>(),
            });
        };
    }
    Ok((result).iter().cloned().collect::<Vec<_>>())
}

// Python: openciv3/victory.py:97
pub(crate) fn held_victory_locations(
    game: &crate::openciv3::game_state::GameState,
) -> rt::Result<indexmap::IndexMap<(i64, i64), i64>> {
    if !(((&(&(game).scenario).options).victory_flags & rt::int_lshift(1i64, 13i64)?) != 0i64) {
        return Ok([].into_iter().collect::<indexmap::IndexMap<_, _>>());
    }
    let mut occupants: indexmap::IndexMap<(i64, i64), std::collections::BTreeSet<i64>> =
        indexmap::IndexMap::<(i64, i64), std::collections::BTreeSet<i64>>::new();
    for mut unit in (&(game).units).iter() {
        let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (unit).owner)?;
        if (!(crate::openciv3::players::Player__barbarian(&player)?)
            && ((player).included
                && (!((player).defeated)
                    && ((&(unit).transported_by).is_none()
                        && (({
                            let __source = &(&(&(game).scenario).rules).units;
                            let __key = (unit).prototype;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .defense
                            > 0i64)))))
        {
            {
                occupants
                    .entry(((unit).x, (unit).y))
                    .or_insert_with(std::collections::BTreeSet::new)
                    .insert((unit).owner);
                ()
            };
        }
    }
    let mut city_owners: indexmap::IndexMap<i64, i64> = {
        let mut __comprehension_result_396: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_395 = ((game).cities.clone());
        for city in __comprehension_source_395.iter().cloned() {
            {
                let (__key, __value) = ((city).id, (city).owner);
                __comprehension_result_396.insert(__key, __value);
            }
        }
        __comprehension_result_396
    };
    let mut held: indexmap::IndexMap<(i64, i64), i64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut tile in (&(&(game).world).tiles).iter() {
        let mut point: (i64, i64) = ((tile).x, (tile).y);
        let mut owners: Option<std::collections::BTreeSet<i64>> =
            (occupants.clone()).get(&(point.clone())).cloned();
        if (!((tile).victory_point)
            || !(match (owners.clone()).as_ref() {
                Some(value) => value.len() as i64,
                None => 0,
            } != 0i64))
        {
            continue;
        }
        if ((((*(owners).as_ref().ok_or("expected a value")?).clone()).len() as i64) == 1i64) {
            {
                let __value = (&((*(owners).as_ref().ok_or("expected a value")?).clone()))
                    .iter()
                    .next()
                    .cloned()
                    .ok_or("StopIteration")?;
                let __key = point;
                held.insert(__key, __value);
            }
        } else {
            let mut territory_owner: Option<i64> = (city_owners.clone())
                .get(
                    &({
                        let __mapping = &(game).ownership;
                        let __key = point.clone();
                        let __default = (1i64).checked_neg().ok_or("integer overflow")?;
                        __mapping.get(&__key).cloned().unwrap_or(__default)
                    }),
                )
                .cloned();
            if ((territory_owner).is_some()
                && match (territory_owner.clone()) {
                    Some(__value) => {
                        let __needle = __value;
                        let __container =
                            &((*(owners).as_ref().ok_or("expected a value")?).clone());
                        __container.contains(&__needle)
                    }
                    None => false,
                })
            {
                {
                    let __value = (*(territory_owner).as_ref().ok_or("expected a value")?).clone();
                    let __key = point;
                    held.insert(__key, __value);
                }
            }
        }
    }
    Ok(held)
}

// Python: openciv3/victory.py:122
pub(crate) fn score_victory_locations(
    game: &crate::openciv3::game_state::GameState,
) -> rt::Result<()> {
    let mut scoring: Option<crate::openciv3::scenario_model::VictoryPointRules> =
        crate::openciv3::scenario_model::ScenarioDefinition__victory_point_rules(&(game).scenario)?;
    if (!((game).game_over)
        && ((scoring).is_some()
            && (((*(scoring.clone()).as_ref().ok_or("expected a value")?).clone()).location) != 0))
    {
        for mut owner in (held_victory_locations(game)?)
            .values()
            .cloned()
            .collect::<Vec<_>>()
        {
            let mut player: crate::openciv3::players::Player = rt::at(&(game).players, owner)?;
            player.victory_points = ((player).victory_points)
                .checked_add(
                    ((*(scoring.clone()).as_ref().ok_or("expected a value")?).clone()).location,
                )
                .ok_or("integer overflow")?;
        }
    }
    Ok(())
}

// Python: openciv3/victory.py:130
pub(crate) fn can_launch_spaceship(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<bool> {
    if ((game).game_over
        || !(((&(&(game).scenario).options).victory_flags & rt::int_lshift(1i64, 1i64)?) != 0i64))
    {
        return Ok(false);
    }
    if (!({
        let __compare_0 = 0i64;
        let __compare_1 = owner;
        if (__compare_0 < __compare_1) {
            let __compare_2 = ((&(game).players).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) || (!(({
        let __source = &(game).players;
        let __key = owner;
        &__source[rt::index(__source.len(), __key)?]
    })
    .included)
        || ({
            let __source = &(game).players;
            let __key = owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .defeated))
    {
        return Ok(false);
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut required: indexmap::IndexMap<i64, i64> =
        crate::openciv3::building_effects::spaceship_requirements(&rules)?;
    let mut cities: Vec<crate::openciv3::cities::City> = {
        let mut __comprehension_result_398: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_397 = ((game).cities.clone());
        for city in __comprehension_source_397.iter().cloned() {
            if ((city).owner == owner) {
                __comprehension_result_398.push(city.clone());
            }
        }
        __comprehension_result_398
    };
    let mut built: indexmap::IndexMap<i64, i64> =
        crate::openciv3::building_effects::spaceship_parts_built(&rules, &cities)?;
    Ok((!(required.clone()).is_empty()
        && (({
            let mut __comprehension_result_400: Vec<bool> = Vec::new();
            let __comprehension_source_399 = (cities.clone());
            for city in __comprehension_source_399.iter().cloned() {
                __comprehension_result_400.push((city).capital);
            }
            __comprehension_result_400
        })
        .into_iter()
        .any(|__value| __value)
            && ({
                let mut __comprehension_result_402: Vec<bool> = Vec::new();
                let __comprehension_source_401 = ((required.clone())
                    .iter()
                    .map(|(__key, __value)| (__key.clone(), __value.clone()))
                    .collect::<Vec<_>>());
                for (index, count) in __comprehension_source_401.iter().cloned() {
                    __comprehension_result_402
                        .push(((built).get(&(index)).ok_or("missing dict key")?.clone() >= count));
                }
                __comprehension_result_402
            })
            .into_iter()
            .all(|__value| __value))))
}

// Python: openciv3/victory.py:143
pub(crate) fn launch_spaceship(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<VictoryResult> {
    if !(can_launch_spaceship(game, owner)?) {
        return Err("This civilization cannot launch a spaceship"
            .to_string()
            .into());
    }
    _declare_victory((*game).clone(), owner, VictoryKind::SPACE_RACE)
}

// Python: openciv3/victory.py:149
pub(crate) fn _declare_victory(
    mut game: crate::openciv3::game_state::GameState,
    mut owner: i64,
    mut kind: VictoryKind,
) -> rt::Result<VictoryResult> {
    let mut result: VictoryResult = VictoryResult {
        owner: owner,
        kind: Some(kind),
        turn: Some((game).turn),
    };
    game.winner = Some(result.clone());
    game.game_over = true;
    Ok(result)
}

/// Declare at most once, after history updates; return only a new declaration.
///
/// AI civilizations launch completed ships at this checkpoint. The human
/// player launches from the advisor. Time limit is always enabled.
// Python: openciv3/victory.py:156
pub(crate) fn check_victory(
    game: &crate::openciv3::game_state::GameState,
) -> rt::Result<Option<VictoryResult>> {
    if (game).game_over {
        return Ok(None);
    }
    let mut flags: i64 = (&(&(game).scenario).options).victory_flags;
    if ((flags & rt::int_lshift(1i64, 1i64)?) != 0i64) {
        for mut player in crate::openciv3::game_state::GameState__players_in_order(game)? {
            if (!((player).human) && can_launch_spaceship(game, (player).civilization)?) {
                return Ok(Some(launch_spaceship(game, (player).civilization)?));
            }
        }
    }
    let (mut area_limit, mut population_limit): (i64, i64) = (if ((flags & 1i64) != 0i64) {
        crate::openciv3::scenario_model::ScenarioDefinition__domination_limits(&(game).scenario)?
    } else {
        (66i64, 66i64)
    });
    let mut candidates: Vec<(VictoryStatus, VictoryKind)> = vec![];
    let mut statuses: Vec<VictoryStatus> = victory_statuses(game)?;
    let mut points: Option<crate::openciv3::scenario_model::VictoryPointRules> =
        crate::openciv3::scenario_model::ScenarioDefinition__victory_point_rules(&(game).scenario)?;
    if ((points).is_some() && !(statuses.clone()).is_empty()) {
        let mut leader: VictoryStatus = {
            let __values = &statuses;
            let mut __items = __values.iter();
            let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
            let mut __best_key = {
                let status = (*__best).clone();
                ((status).victory_points, (status).score)
            };
            for __candidate in __items {
                let __key = {
                    let status = (*__candidate).clone();
                    ((status).victory_points, (status).score)
                };
                if __key > __best_key {
                    __best = __candidate;
                    __best_key = __key;
                }
            }
            (*__best).clone()
        };
        let mut wonders: std::collections::BTreeSet<i64> = {
            let mut __comprehension_result_404: std::collections::BTreeSet<i64> =
                std::collections::BTreeSet::new();
            let __comprehension_source_403 = (((&(&(game).scenario).rules).buildings.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>());
            for (index, building) in __comprehension_source_403.iter().cloned() {
                if (((building).effects & 268435456i64) != 0i64) {
                    __comprehension_result_404.insert(index);
                }
            }
            __comprehension_result_404
        };
        if ((flags & rt::int_lshift(1i64, 16i64)?) != 0
            && (!(wonders.clone()).is_empty() && {
                let __left = &(wonders.clone());
                let __right = &((game).great_wonders_built.clone());
                __left.is_subset(__right)
            }))
        {
            return Ok(Some(_declare_victory(
                (*game).clone(),
                (leader).owner,
                VictoryKind::WONDER,
            )?));
        }
        if ((flags & rt::int_lshift(1i64, 13i64)?) != 0
            && ((leader).victory_points
                >= ((*(points.clone()).as_ref().ok_or("expected a value")?).clone()).limit))
        {
            return Ok(Some(_declare_victory(
                (*game).clone(),
                (leader).owner,
                VictoryKind::VICTORY_POINTS,
            )?));
        }
    }
    let (mut city_limit, mut empire_limit): (i64, i64) =
        (if ((flags & rt::int_lshift(1i64, 4i64)?) != 0i64) {
            crate::openciv3::scenario_model::ScenarioDefinition__cultural_limits(&(game).scenario)?
        } else {
            (0i64, 0i64)
        });
    for mut status in (statuses).iter() {
        if ((flags & 1i64) != 0
            && ((&(status).area_percent).is_some()
                && ((&(status).population_percent).is_some()
                    && (((*((status).area_percent.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone()
                        >= area_limit)
                        && ((*((status).population_percent.clone())
                            .as_ref()
                            .ok_or("expected a value")?)
                        .clone()
                            >= population_limit)))))
        {
            {
                candidates.push(((*status).clone(), VictoryKind::DOMINATION));
            };
        } else {
            if ((flags & rt::int_lshift(1i64, 10i64)?) != 0 && ((status).rivals_alive == 0i64)) {
                {
                    candidates.push(((*status).clone(), VictoryKind::CITY_ELIMINATION));
                };
            } else {
                if ((flags & (rt::int_lshift(1i64, 11i64)? | rt::int_lshift(1i64, 12i64)?)) != 0
                    && ((status).rivals_alive == 0i64))
                {
                    {
                        candidates.push(((*status).clone(), VictoryKind::REGICIDE));
                    };
                } else {
                    if ((flags & rt::int_lshift(1i64, 3i64)?) != 0
                        && ((status).rivals_alive == 0i64))
                    {
                        {
                            candidates.push(((*status).clone(), VictoryKind::CONQUEST));
                        };
                    } else {
                        if ((flags & rt::int_lshift(1i64, 4i64)?) != 0
                            && (((status).largest_city_culture >= city_limit)
                                || (((status).culture >= empire_limit)
                                    && ({
                                        let mut __comprehension_result_406: Vec<bool> = Vec::new();
                                        let __comprehension_source_405 = (statuses.clone());
                                        for rival in __comprehension_source_405.iter().cloned() {
                                            if ((rival).owner != (status).owner) {
                                                __comprehension_result_406.push(
                                                    ((status).culture
                                                        >= (2i64)
                                                            .checked_mul((rival).culture)
                                                            .ok_or("integer overflow")?),
                                                );
                                            }
                                        }
                                        __comprehension_result_406
                                    })
                                    .into_iter()
                                    .all(|__value| __value))))
                        {
                            {
                                candidates.push(((*status).clone(), VictoryKind::CULTURAL));
                            };
                        } else {
                            if ((game).turn >= (&(&(game).scenario).options).turn_limit) {
                                {
                                    candidates.push(((*status).clone(), VictoryKind::TIME_LIMIT));
                                };
                            }
                        }
                    }
                }
            }
        }
    }
    if !(((candidates).len() as i64) != 0i64) {
        return Ok(None);
    }
    let (mut status, mut kind): (VictoryStatus, VictoryKind) = {
        let __values = &candidates;
        let mut __items = __values.iter();
        let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
        let mut __best_key = {
            let candidate = (*__best).clone();
            (
                (if (points).is_some() {
                    (&(candidate).0).victory_points
                } else {
                    0i64
                }),
                (&(candidate).0).score,
            )
        };
        for __candidate in __items {
            let __key = {
                let candidate = (*__candidate).clone();
                (
                    (if (points).is_some() {
                        (&(candidate).0).victory_points
                    } else {
                        0i64
                    }),
                    (&(candidate).0).score,
                )
            };
            if __key > __best_key {
                __best = __candidate;
                __best_key = __key;
            }
        }
        (*__best).clone()
    };
    Ok(Some(_declare_victory(
        (*game).clone(),
        (status).owner,
        kind,
    )?))
}
