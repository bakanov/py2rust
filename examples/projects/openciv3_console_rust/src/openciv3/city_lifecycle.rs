use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct CityDestruction {
    pub(crate) city_id: i64,
    pub(crate) removed_units: Vec<i64>,
    pub(crate) defeated: Vec<i64>,
    pub(crate) new_capital: Option<i64>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct CityRaid {
    pub(crate) gold_taken: i64,
    pub(crate) removal: crate::openciv3::unit_lifecycle::RemovalResult,
    pub(crate) city_owner: i64,
    pub(crate) city_name: String,
}

// Python: openciv3/city_lifecycle.py:17
pub(crate) fn capital_score(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut neighbor_distance: Option<i64>,
) -> rt::Result<i64> {
    let mut score: i64 = ({
        let mut __comprehension_result_1123: Vec<i64> = Vec::new();
        let __comprehension_source_1122 = ((city).residents.clone());
        for resident in __comprehension_source_1122.iter().cloned() {
            __comprehension_result_1123.push(
                (if ((resident).nationality == (city).owner) {
                    3i64
                } else {
                    1i64
                }),
            );
        }
        __comprehension_result_1123
    })
    .into_iter()
    .sum::<i64>();
    score = (score)
        .checked_add(
            ({
                let mut __comprehension_result_1125: Vec<bool> = Vec::new();
                let __comprehension_source_1124 = ((game).units.clone());
                for unit in __comprehension_source_1124.iter().cloned() {
                    __comprehension_result_1125.push(
                        (((unit).owner == (city).owner)
                            && ((((unit).x, (unit).y) == ((city).x, (city).y))
                                && ((({
                                    let __source = &(&(&(game).scenario).rules).units;
                                    let __key = (unit).prototype;
                                    &__source[rt::index(__source.len(), __key)?]
                                })
                                .attack
                                    > 0i64)
                                    || (({
                                        let __source = &(&(&(game).scenario).rules).units;
                                        let __key = (unit).prototype;
                                        &__source[rt::index(__source.len(), __key)?]
                                    })
                                    .defense
                                        > 0i64)))),
                    );
                }
                __comprehension_result_1125
            })
            .into_iter()
            .map(|value| value as i64)
            .sum::<i64>(),
        )
        .ok_or("integer overflow")?;
    let mut center: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (city).x, (city).y)?;
    if !((center).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    let mut rules: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(&(&(game).scenario).rules).global_rules, 0i64)?;
    if (neighbor_distance).is_none() {
        neighbor_distance = Some((rules).capital_neighbor_distance);
    }
    for mut neighbor in (&(game).cities).iter() {
        if (((neighbor).id == (city).id) || ((neighbor).owner != (city).owner)) {
            continue;
        }
        let mut tile: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(&(game).world, (neighbor).x, (neighbor).y)?;
        if !((tile).is_some()) {
            rt::assertion(false, &("".to_string()))?;
        }
        if (crate::strategy::grid::distance(
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
                    (*(center.clone()).as_ref().ok_or("expected a value")?).clone();
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
            &({
                let __structural_value = (*(tile).as_ref().ok_or("expected a value")?).clone();
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
        )? <= (*(neighbor_distance.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone())
        {
            score = (score)
                .checked_add(
                    ((1i64)
                        .checked_add(
                            ((crate::openciv3::cities::City__size(neighbor)?
                                > (rules).maximum_level1_city_size)
                                as i64),
                        )
                        .ok_or("integer overflow")?)
                    .checked_add(
                        ((crate::openciv3::cities::City__size(neighbor)?
                            > (rules).maximum_level2_city_size) as i64),
                    )
                    .ok_or("integer overflow")?,
                )
                .ok_or("integer overflow")?;
        }
    }
    Ok(score)
}

// Python: openciv3/city_lifecycle.py:37
pub(crate) fn relocate_capital(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    neighbor_distance: &Option<i64>,
) -> rt::Result<Option<crate::openciv3::cities::City>> {
    let mut cities: Vec<crate::openciv3::cities::City> = {
        let mut __comprehension_result_1127: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_1126 = ((game).cities.clone());
        for city in __comprehension_source_1126.iter().cloned() {
            if ((city).owner == owner) {
                __comprehension_result_1127.push(city.clone());
            }
        }
        __comprehension_result_1127
    };
    if (!(((cities).len() as i64) != 0i64)
        || ({
            let mut __comprehension_result_1129: Vec<bool> = Vec::new();
            let __comprehension_source_1128 = (cities.clone());
            for city in __comprehension_source_1128.iter().cloned() {
                __comprehension_result_1129.push((city).capital);
            }
            __comprehension_result_1129
        })
        .into_iter()
        .any(|__value| __value))
    {
        return Ok(None);
    }
    let mut selected: crate::openciv3::cities::City = {
        let __values = &cities;
        let mut __items = __values.iter();
        let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
        let mut __best_key = {
            let city = (*__best).clone();
            {
                let __call_1130_0 = game;
                let __call_1130_1 = &city;
                let __call_1130_2 = (*neighbor_distance).clone();
                capital_score(__call_1130_0, __call_1130_1, __call_1130_2)
            }?
        };
        for __candidate in __items {
            let __key = {
                let city = (*__candidate).clone();
                {
                    let __call_1130_0 = game;
                    let __call_1130_1 = &city;
                    let __call_1130_2 = (*neighbor_distance).clone();
                    capital_score(__call_1130_0, __call_1130_1, __call_1130_2)
                }?
            };
            if __key > __best_key {
                __best = __candidate;
                __best_key = __key;
            }
        }
        (*__best).clone()
    };
    selected.capital = true;
    let mut palace: Option<i64> = {
        let __find_source_1131 = ((&(&(game).scenario).rules).buildings.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>();
        let mut __find_result_1131: Option<i64> = None;
        for (index, building) in __find_source_1131.iter().cloned() {
            if (((building).effects & 1i64) != 0i64) {
                __find_result_1131 = Some(index);
                break;
            }
        }
        __find_result_1131
    };
    if ((palace).is_some()
        && !(({
            let mut __comprehension_result_1133: Vec<bool> = Vec::new();
            let __comprehension_source_1132 = ((selected).buildings.clone());
            for item in __comprehension_source_1132.iter().cloned() {
                __comprehension_result_1133.push((Some((item).building) == palace.clone()));
            }
            __comprehension_result_1133
        })
        .into_iter()
        .any(|__value| __value)))
    {
        ((selected).buildings).push(crate::openciv3::cities::CityBuilding {
            building: (*(palace).as_ref().ok_or("expected a value")?).clone(),
            built_by: owner,
            year: (game).year,
            total_culture: 0i64,
        });
    }
    Ok(Some(selected))
}

// Python: openciv3/city_lifecycle.py:58
pub(crate) fn raze_cities(
    mut game: crate::openciv3::game_state::GameState,
    cities: &[crate::openciv3::cities::City],
) -> rt::Result<()> {
    if !(((cities).len() as i64) != 0i64) {
        return Ok(());
    }
    game.next_city_id = ((game).next_city_id).max(
        ({
            let __values = &({
                let mut __comprehension_result_1135: Vec<i64> = Vec::new();
                let __comprehension_source_1134 = ((game).cities.clone());
                for other in __comprehension_source_1134.iter().cloned() {
                    __comprehension_result_1135.push((other).id);
                }
                __comprehension_result_1135
            });
            let mut __items = __values.iter();
            let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
            for __candidate in __items {
                if __candidate > __best {
                    __best = __candidate;
                }
            }
            (*__best).clone()
        })
        .checked_add(1i64)
        .ok_or("integer overflow")?,
    );
    let mut coordinates: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_1137: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_1136 = (cities.to_vec());
        for city in __comprehension_source_1136.iter().cloned() {
            __comprehension_result_1137.insert(((city).x, (city).y));
        }
        __comprehension_result_1137
    };
    for mut city in (cities).iter().cloned() {
        ((city).residents).clear();
    }
    let mut removed_ids: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_1139: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_1138 = (cities.to_vec());
        for city in __comprehension_source_1138.iter().cloned() {
            __comprehension_result_1139.insert((city).id);
        }
        __comprehension_result_1139
    };
    ((game).cities.clone()).clear();
    ((game).cities.clone()).extend({
        let mut __comprehension_result_1141: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_1140 = ((game).cities.clone());
        for city in __comprehension_source_1140.iter().cloned() {
            if {
                let __needle = (city).id;
                let __container = &removed_ids;
                !__container.contains(&__needle)
            } {
                __comprehension_result_1141.push(city.clone());
            }
        }
        __comprehension_result_1141
    });
    game.world = {
        let mut __replacement = ((game).world.clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_1143: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_1142 = ((&(game).world).tiles.clone());
            for tile in __comprehension_source_1142.iter().cloned() {
                __comprehension_result_1143.push(
                    (if {
                        let __needle = ((tile).x, (tile).y);
                        let __container = &coordinates;
                        __container.contains(&__needle)
                    } {
                        {
                            let mut __replacement = (tile.clone()).clone();
                            __replacement.overlay_terrain = (tile).base_terrain;
                            __replacement.overlays = 0i64;
                            __replacement.ruin = 1i64;
                            __replacement.installation_owner = None;
                            __replacement
                        }
                    } else {
                        tile.clone()
                    }),
                );
            }
            __comprehension_result_1143
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    };
    game.scenario.world = Some((game).world.clone());
    crate::openciv3::city_culture::refresh_ownership(&game)?;
    Ok(())
}

/// Destroy the city and garrison, clearing space progress on enemy conquest of a capital.
// Python: openciv3/city_lifecycle.py:74
pub(crate) fn destroy_city(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut conquered: bool,
) -> rt::Result<CityDestruction> {
    if !(({
        let mut __comprehension_result_1145: Vec<bool> = Vec::new();
        let __comprehension_source_1144 = ((game).cities.clone());
        for other in __comprehension_source_1144.iter().cloned() {
            __comprehension_result_1145.push(((other).id == (city).id));
        }
        __comprehension_result_1145
    })
    .into_iter()
    .any(|__value| __value))
    {
        return Err("City is not in this game".to_string().into());
    }
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (city).owner)?;
    let mut eliminate: bool = false;
    if (conquered
        && (!(crate::openciv3::players::Player__barbarian(&player)?)
            && ((&(&(game).scenario).options).victory_flags & rt::int_lshift(1i64, 10i64)?) != 0))
    {
        player.cities_lost = ((player).cities_lost)
            .checked_add(1i64)
            .ok_or("integer overflow")?;
        eliminate = ((player).cities_lost
            >= crate::openciv3::scenario_model::ScenarioDefinition__city_elimination_limit(
                &(game).scenario,
            )?);
    }
    let mut lost: Vec<crate::openciv3::cities::City> = (if eliminate {
        {
            let mut __comprehension_result_1147: Vec<crate::openciv3::cities::City> = Vec::new();
            let __comprehension_source_1146 = ((game).cities.clone());
            for other in __comprehension_source_1146.iter().cloned() {
                if ((other).owner == (city).owner) {
                    __comprehension_result_1147.push(other.clone());
                }
            }
            __comprehension_result_1147
        }
    } else {
        vec![(*city).clone()]
    });
    let mut coordinates: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_1149: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_1148 = (lost.clone());
        for other in __comprehension_source_1148.iter().cloned() {
            __comprehension_result_1149.insert(((other).x, (other).y));
        }
        __comprehension_result_1149
    };
    raze_cities((*game).clone(), &lost)?;
    let mut garrison: crate::openciv3::unit_lifecycle::RemovalResult =
        crate::openciv3::unit_lifecycle::remove_units(
            (*game).clone(),
            &({
                let mut __comprehension_result_1151: Vec<crate::openciv3::units::Unit> = Vec::new();
                let __comprehension_source_1150 = ((game).units.clone());
                for unit in __comprehension_source_1150.iter().cloned() {
                    if (((unit).owner == (city).owner) && {
                        let __needle = ((unit).x, (unit).y);
                        let __container = &coordinates;
                        __container.contains(&__needle)
                    }) {
                        __comprehension_result_1151.push(unit.clone());
                    }
                }
                __comprehension_result_1151
            }),
        )?;
    let mut result: crate::openciv3::unit_lifecycle::RemovalResult = {
        let __call_1152_0 = (*game).clone();
        let __call_1152_1 = (city).owner;
        let __call_1152_2 = eliminate;
        crate::openciv3::unit_lifecycle::eliminate_if_needed(
            __call_1152_0,
            __call_1152_1,
            __call_1152_2,
        )
    }?;
    let mut capital: Option<crate::openciv3::cities::City> =
        relocate_capital(game, (city).owner, &None)?;
    let mut remaining: Vec<crate::openciv3::cities::City> = {
        let mut __comprehension_result_1154: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_1153 = ((game).cities.clone());
        for other in __comprehension_source_1153.iter().cloned() {
            if ((other).owner == (city).owner) {
                __comprehension_result_1154.push(other.clone());
            }
        }
        __comprehension_result_1154
    };
    let mut buildings: Vec<crate::openciv3::building_rules::Building> =
        (&(&(game).scenario).rules).buildings.clone();
    let mut launched: bool = ((&(game).winner).is_some()
        && ((((*((game).winner.clone()).as_ref().ok_or("expected a value")?).clone()).owner
            == (city).owner)
            && ((*(((*((game).winner.clone()).as_ref().ok_or("expected a value")?).clone())
                .kind
                .clone())
            .as_ref()
            .ok_or("expected a value")?)
            .clone())
                == (crate::openciv3::victory::VictoryKind::SPACE_RACE)));
    if (conquered && ((city).capital && !(launched))) {
        for mut other in remaining {
            ((other).buildings.clone()).clear();
            ((other).buildings.clone()).extend({
                let mut __comprehension_result_1156: Vec<crate::openciv3::cities::CityBuilding> =
                    Vec::new();
                let __comprehension_source_1155 = ((other).buildings.clone());
                for item in __comprehension_source_1155.iter().cloned() {
                    if (({
                        let __source = &buildings;
                        let __key = (item).building;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .spaceship_part
                        < 0i64)
                    {
                        __comprehension_result_1156.push(item.clone());
                    }
                }
                __comprehension_result_1156
            });
        }
    } else {
        let mut launch_site: Option<crate::openciv3::cities::City> = (if (capital).is_some() {
            capital.clone()
        } else {
            {
                let __find_source_1157 = remaining;
                let mut __find_result_1157: Option<crate::openciv3::cities::City> = None;
                for other in __find_source_1157.iter().cloned() {
                    if (other).capital {
                        __find_result_1157 = Some(other.clone());
                        break;
                    }
                }
                __find_result_1157
            }
        });
        if (launch_site).is_some() {
            (((*(launch_site).as_ref().ok_or("expected a value")?).clone())
                .buildings
                .clone())
            .extend({
                let mut __comprehension_result_1159: Vec<crate::openciv3::cities::CityBuilding> =
                    Vec::new();
                let __comprehension_source_1158 = ((city).buildings.clone());
                for item in __comprehension_source_1158.iter().cloned() {
                    if (({
                        let __source = &buildings;
                        let __key = (item).building;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .spaceship_part
                        >= 0i64)
                    {
                        __comprehension_result_1159.push(item.clone());
                    }
                }
                __comprehension_result_1159
            });
        }
    }
    Ok(CityDestruction {
        city_id: (city).id,
        removed_units: {
            let mut __left: Vec<i64> = (garrison).removed.clone();
            let __right: Vec<i64> = (result).removed.clone();
            __left.extend(__right);
            __left
        },
        defeated: ({
            let mut __seen = std::collections::BTreeSet::new();
            let mut __result: Vec<i64> = Vec::new();
            for __item in ({
                let mut __left: Vec<i64> = (garrison).defeated.clone();
                let __right: Vec<i64> = (result).defeated.clone();
                __left.extend(__right);
                __left
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
        .collect::<Vec<_>>(),
        new_capital: (if (capital).is_none() {
            None
        } else {
            Some(((*(capital.clone()).as_ref().ok_or("expected a value")?).clone()).id)
        }),
    })
}

/// Apply the former Lua raid reward once a barbarian has entered the city.
// Python: openciv3/city_lifecycle.py:115
pub(crate) fn ransack_city(
    game: &crate::openciv3::game_state::GameState,
    barbarian: &crate::openciv3::units::Unit,
    city: &crate::openciv3::cities::City,
) -> rt::Result<CityRaid> {
    if (((barbarian).owner != 0i64)
        || (((city).owner == 0i64) || (((barbarian).x, (barbarian).y) != ((city).x, (city).y))))
    {
        return Err("Raid requires a barbarian inside a foreign city"
            .to_string()
            .into());
    }
    if (!(({
        let mut __comprehension_result_1161: Vec<bool> = Vec::new();
        let __comprehension_source_1160 = ((game).cities.clone());
        for other in __comprehension_source_1160.iter().cloned() {
            __comprehension_result_1161.push(((other).id == (city).id));
        }
        __comprehension_result_1161
    })
    .into_iter()
    .any(|__value| __value))
        || !(({
            let mut __comprehension_result_1163: Vec<bool> = Vec::new();
            let __comprehension_source_1162 = ((game).units.clone());
            for other in __comprehension_source_1162.iter().cloned() {
                __comprehension_result_1163.push(((other).id == (barbarian).id));
            }
            __comprehension_result_1163
        })
        .into_iter()
        .any(|__value| __value)))
    {
        return Err("Raid participants are not in this game".to_string().into());
    }
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (city).owner)?;
    let mut gold: i64 = (0i64).max(rt::int_floor_div((player).gold, 4i64)?);
    let mut removal: crate::openciv3::unit_lifecycle::RemovalResult =
        crate::openciv3::unit_lifecycle::remove_unit(game, barbarian)?;
    player.gold = ((player).gold)
        .checked_sub(gold)
        .ok_or("integer overflow")?;
    Ok(CityRaid {
        gold_taken: gold,
        removal: removal,
        city_owner: (city).owner,
        city_name: (city).name.clone(),
    })
}
