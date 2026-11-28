use py2rust_service_runtime as rt;

// Python: openciv3/production_eligibility.py:16
pub(crate) fn can_train(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut index: i64,
    mut allow_lesser_units: Option<bool>,
    mut network: Option<crate::openciv3::trade_network::TradeNetwork>,
) -> rt::Result<bool> {
    let mut units: Vec<crate::openciv3::unit_rules::UnitPrototype> =
        (&(&(game).scenario).rules).units.clone();
    if !({
        let __compare_0 = 0i64;
        let __compare_1 = index;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = ((units).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) {
        return Err("Invalid unit index".to_string().into());
    }
    let mut unit: crate::openciv3::unit_rules::UnitPrototype = rt::at(&units, index)?;
    if ((unit).unproducible
        || ({
            let __needle = (city).owner;
            let __container = &(unit).available_to;
            !__container.contains(&__needle)
        } || (((unit).shield_cost < 1i64)
            || ({
                let __boolean_123705970134096 = ((unit).abilities & 262144i64);
                if (__boolean_123705970134096) != 0 {
                    __boolean_123705970134096
                } else {
                    {
                        let __boolean_123705970133904 = ((&(&(game).scenario).options)
                            .victory_flags
                            & (rt::int_lshift(1i64, 11i64)? | rt::int_lshift(1i64, 12i64)?));
                        if (__boolean_123705970133904) != 0 {
                            ((unit).abilities & 536870912i64)
                        } else {
                            __boolean_123705970133904
                        }
                    }
                }
            }) != 0)))
    {
        return Ok(false);
    }
    let mut center: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (city).x, (city).y)?;
    if (center).is_none() {
        return Err("City is outside the map".to_string().into());
    }
    let mut water: bool = ({
        let mut __comprehension_result_936: Vec<bool> = Vec::new();
        let __comprehension_source_935 = (crate::openciv3::world::WorldMap__neighbors(
            &(game).world,
            &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?);
        for tile in __comprehension_source_935.iter().cloned() {
            __comprehension_result_936.push(crate::openciv3::hydrology::is_water(&tile)?);
        }
        __comprehension_result_936
    })
    .into_iter()
    .any(|__value| __value);
    let mut known: std::collections::BTreeSet<i64> = ({
        let __source = &(game).players;
        let __key = (city).owner;
        &__source[rt::index(__source.len(), __key)?]
    })
    .known_technologies
    .clone();
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
    let mut resources: indexmap::IndexMap<i64, i64> =
        crate::openciv3::trade_network::TradeNetwork__resources_available(
            &((*(network).as_ref().ok_or("expected a value")?).clone()),
            city,
        )?;

    if !(can_train__meets_requirements(&units, &known, water, &resources, index)?) {
        return Ok(false);
    }
    if (allow_lesser_units).is_none() {
        let mut rules: Vec<crate::openciv3::global_rules::GlobalRules> =
            (&(&(game).scenario).rules).global_rules.clone();
        allow_lesser_units = Some(
            (!(rules.clone()).is_empty()
                && ({
                    let __source = &rules;
                    let __key = 0i64;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .allow_lesser_unit_production),
        );
    }
    if (allow_lesser_units).is_some() {
        return Ok(true);
    }
    Ok(!(({
        let mut __comprehension_result_938: Vec<bool> = Vec::new();
        let __comprehension_source_937 = (unit_upgrade_candidates(game, (city).owner, index)?);
        for target in __comprehension_source_937.iter().cloned() {
            __comprehension_result_938.push(
                ({
                    let __needle = (city).owner;
                    let __container = &({
                        let __source = &units;
                        let __key = target;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .available_to;
                    __container.contains(&__needle)
                } && can_train__meets_requirements(&units, &known, water, &resources, target)?),
            );
        }
        __comprehension_result_938
    })
    .into_iter()
    .any(|__value| __value)))
}

// Python: openciv3/production_eligibility.py:50
pub(crate) fn unit_upgrade_candidates(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    mut index: i64,
) -> rt::Result<std::collections::BTreeSet<i64>> {
    let mut units: Vec<crate::openciv3::unit_rules::UnitPrototype> =
        (&(&(game).scenario).rules).units.clone();
    let mut links: Vec<std::collections::BTreeSet<i64>> =
        crate::openciv3::rules::RuleCatalog__unit_upgrade_links(&(&(game).scenario).rules)?;
    let mut chain: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
    let mut current: i64 = index;
    loop {
        let mut branches: Option<Vec<i64>> = ({
            let __source = &units;
            let __key = current;
            &__source[rt::index(__source.len(), __key)?]
        })
        .upgrade_branches
        .clone();
        if (branches).is_none() {
            branches = Some(
                ({
                    let mut __decorated: Vec<(String, i64)> = Vec::new();
                    for __item in (rt::at(&links, current)?).into_iter() {
                        let target = __item;
                        let __key = {
                            ({
                                let __source = &units;
                                let __key = target;
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .name
                            .clone()
                        };
                        __decorated.push((__key, target));
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
                })
                .iter()
                .cloned()
                .collect::<Vec<_>>(),
            );
        }
        let mut targets: Vec<i64> = {
            let mut __comprehension_result_940: Vec<i64> = Vec::new();
            let __comprehension_source_939 =
                ((*(branches.clone()).as_ref().ok_or("expected a value")?).clone());
            for target in __comprehension_source_939.iter().cloned() {
                if {
                    let __needle = owner;
                    let __container = &({
                        let __source = &units;
                        let __key = target;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .available_to;
                    __container.contains(&__needle)
                } {
                    __comprehension_result_940.push(target);
                }
            }
            __comprehension_result_940
        };
        if !(((targets).len() as i64) != 0i64) {
            break;
        }
        current = rt::at(&targets, 0i64)?;
        if ((current == index) || {
            let __needle = current;
            let __container = &chain;
            __container.contains(&__needle)
        }) {
            return Err("Cyclic unit upgrade chain".to_string().into());
        }
        {
            chain.insert(current);
        };
    }
    if !(((chain).len() as i64) != 0i64) {
        return Ok(std::collections::BTreeSet::new());
    }
    let mut grandchildren: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_943: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_941 = (rt::at(&links, index)?);
        for direct in __comprehension_source_941.iter().cloned() {
            let __comprehension_source_942 = (rt::at(&links, direct)?);
            for target in __comprehension_source_942.iter().cloned() {
                __comprehension_result_943.insert(target);
            }
        }
        __comprehension_result_943
    };
    let mut siblings: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_945: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_944 = ((links.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>());
        for (target, upgrades) in __comprehension_source_944.iter().cloned() {
            if ((target != index)
                && !({
                    let __set_left = upgrades.clone();
                    let __set_right = grandchildren.clone();
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in __set_left.intersection(&__set_right) {
                        __result.insert(__item.clone());
                    }
                    __result
                })
                .is_empty())
            {
                __comprehension_result_945.insert(target);
            }
        }
        __comprehension_result_945
    };
    Ok({
        let __set_left = chain;
        let __set_right = siblings;
        let mut __result = std::collections::BTreeSet::new();
        for __item in __set_left.union(&__set_right) {
            __result.insert(__item.clone());
        }
        __result
    })
}

// Python: openciv3/production_eligibility.py:73
pub(crate) fn select_unit(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut index: i64,
    allow_lesser_units: &Option<bool>,
) -> rt::Result<()> {
    if !({
        let __call_946_0 = game;
        let __call_946_1 = city;
        let __call_946_2 = index;
        let __call_946_3 = (*allow_lesser_units).clone();
        let __call_946_default_4 = None;
        can_train(
            __call_946_0,
            __call_946_1,
            __call_946_2,
            __call_946_3,
            __call_946_default_4,
        )
    }?) {
        return Err("Unit cannot be produced in this city".to_string().into());
    }
    crate::openciv3::cities::City__select_unit((*city).clone(), index)?;
    Ok(())
}

// Python: openciv3/production_eligibility.py:79
pub(crate) fn can_build(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut index: i64,
    mut network: Option<crate::openciv3::trade_network::TradeNetwork>,
    mut hydro: Option<crate::openciv3::hydrology::Hydrology>,
) -> rt::Result<bool> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    if !({
        let __compare_0 = 0i64;
        let __compare_1 = index;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = ((&(rules).buildings).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) {
        return Err("Invalid building index".to_string().into());
    }
    let mut building: crate::openciv3::building_rules::Building =
        rt::at(&(rules).buildings, index)?;
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (city).owner)?;
    let mut known: std::collections::BTreeSet<i64> = (player).known_technologies.clone();
    if (((building).required_advance >= 0i64) && {
        let __needle = (building).required_advance;
        let __container = &known;
        !__container.contains(&__needle)
    }) {
        return Ok(false);
    }
    if {
        let __needle = (building).rendered_obsolete_by;
        let __container = &known;
        __container.contains(&__needle)
    } {
        return Ok(false);
    }
    let mut owned_cities: Vec<crate::openciv3::cities::City> = {
        let mut __comprehension_result_948: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_947 = ((game).cities.clone());
        for other in __comprehension_source_947.iter().cloned() {
            if ((other).owner == (city).owner) {
                __comprehension_result_948.push(other.clone());
            }
        }
        __comprehension_result_948
    };
    let mut local: Vec<crate::openciv3::cities::CityBuilding> =
        crate::openciv3::building_effects::effective_buildings(
            city,
            &(game).cities,
            &(game).players,
            &(game).world,
            &rules,
        )?;
    if (((building).spaceship_part < 0i64)
        && ({
            let mut __comprehension_result_950: Vec<bool> = Vec::new();
            let __comprehension_source_949 = (local.clone());
            for item in __comprehension_source_949.iter().cloned() {
                __comprehension_result_950.push(((item).building == index));
            }
            __comprehension_result_950
        })
        .into_iter()
        .any(|__value| __value))
    {
        return Ok(false);
    }
    let mut competing: bool = ({
        let mut __comprehension_result_952: Vec<bool> = Vec::new();
        let __comprehension_source_951 = (owned_cities.clone());
        for other in __comprehension_source_951.iter().cloned() {
            __comprehension_result_952.push(
                (((other).id != (city).id) && ((other).producing_building.clone() == Some(index))),
            );
        }
        __comprehension_result_952
    })
    .into_iter()
    .any(|__value| __value);
    let mut flags: i64 = (building).effects;
    if ((flags & 268435456i64) != 0
        && ({
            let __needle = index;
            let __container = &(game).great_wonders_built;
            __container.contains(&__needle)
        } || competing))
    {
        return Ok(false);
    }
    if ((flags & 536870912i64) != 0i64) {
        if (competing
            || ({
                let mut __comprehension_result_955: Vec<bool> = Vec::new();
                let __comprehension_source_953 = (owned_cities.clone());
                for other in __comprehension_source_953.iter().cloned() {
                    let __comprehension_source_954 = ((other).buildings.clone());
                    for item in __comprehension_source_954.iter().cloned() {
                        __comprehension_result_955.push(((item).building == index));
                    }
                }
                __comprehension_result_955
            })
            .into_iter()
            .any(|__value| __value))
        {
            return Ok(false);
        }
    }
    let mut part: i64 = (building).spaceship_part;
    if (part >= 0i64) {
        if !(((&(&(game).scenario).options).victory_flags & rt::int_lshift(1i64, 1i64)?) != 0i64) {
            return Ok(false);
        }
        let mut quota: i64 = {
            let __mapping = crate::openciv3::building_effects::spaceship_requirements(&rules)?;
            let __key = part;
            let __default = 0i64;
            __mapping.get(&__key).cloned().unwrap_or(__default)
        };
        let mut reserved: i64 = ({
            let mut __comprehension_result_957: Vec<bool> = Vec::new();
            let __comprehension_source_956 = (owned_cities.clone());
            for other in __comprehension_source_956.iter().cloned() {
                __comprehension_result_957.push(
                    (((other).id != (city).id)
                        && ((&(other).producing_building).is_some()
                            && (({
                                let __source = &(rules).buildings;
                                let __key = (*((other).producing_building.clone())
                                    .as_ref()
                                    .ok_or("expected a value")?)
                                .clone();
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .spaceship_part
                                == part))),
                );
            }
            __comprehension_result_957
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        if (((crate::openciv3::building_effects::spaceship_parts_built(&rules, &owned_cities)?)
            .get(&(part))
            .ok_or("missing dict key")?
            .clone())
        .checked_add(reserved)
        .ok_or("integer overflow")?
            >= quota)
        {
            return Ok(false);
        }
        if !(({
            let mut __comprehension_result_960: Vec<bool> = Vec::new();
            let __comprehension_source_958 = (owned_cities.clone());
            for other in __comprehension_source_958.iter().cloned() {
                let __comprehension_source_959 = ((other).buildings.clone());
                for item in __comprehension_source_959.iter().cloned() {
                    __comprehension_result_960.push(
                        ((({
                            let __source = &(rules).buildings;
                            let __key = (item).building;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .effects
                            & 4398046511104i64)
                            != 0
                            && {
                                let __needle = ({
                                    let __source = &(rules).buildings;
                                    let __key = (item).building;
                                    &__source[rt::index(__source.len(), __key)?]
                                })
                                .rendered_obsolete_by;
                                let __container = &known;
                                !__container.contains(&__needle)
                            }),
                    );
                }
            }
            __comprehension_result_960
        })
        .into_iter()
        .any(|__value| __value))
        {
            return Ok(false);
        }
    }
    if ((flags & (281474976710656i64 | 140737488355328i64)) != 0i64) {
        return Ok(false);
    }
    if ((flags & 1i64) != 0 && (city).capital) {
        return Ok(false);
    }
    if ((building).required_building >= 0i64) {
        if ((building).number_of_required_buildings > 1i64) {
            let mut eligible_cities: i64 = ({
                let mut __comprehension_result_964: Vec<bool> = Vec::new();
                let __comprehension_source_961 = (owned_cities.clone());
                for other in __comprehension_source_961.iter().cloned() {
                    __comprehension_result_964.push(
                        ({
                            let mut __comprehension_result_963: Vec<bool> = Vec::new();
                            let __comprehension_source_962 =
                                (crate::openciv3::building_effects::effective_buildings(
                                    &other,
                                    &(game).cities,
                                    &(game).players,
                                    &(game).world,
                                    &rules,
                                )?);
                            for item in __comprehension_source_962.iter().cloned() {
                                __comprehension_result_963
                                    .push(((item).building == (building).required_building));
                            }
                            __comprehension_result_963
                        })
                        .into_iter()
                        .any(|__value| __value),
                    );
                }
                __comprehension_result_964
            })
            .into_iter()
            .map(|value| value as i64)
            .sum::<i64>();
            if (eligible_cities < (building).number_of_required_buildings) {
                return Ok(false);
            }
        } else {
            if !(({
                let mut __comprehension_result_966: Vec<bool> = Vec::new();
                let __comprehension_source_965 = (local.clone());
                for item in __comprehension_source_965.iter().cloned() {
                    __comprehension_result_966
                        .push(((item).building == (building).required_building));
                }
                __comprehension_result_966
            })
            .into_iter()
            .any(|__value| __value))
            {
                return Ok(false);
            }
        }
    }
    if (((building).required_government >= 0i64)
        && ((building).required_government != (player).government))
    {
        return Ok(false);
    }
    let mut armies: i64 = ({
        let mut __comprehension_result_968: Vec<bool> = Vec::new();
        let __comprehension_source_967 = ((game).units.clone());
        for unit in __comprehension_source_967.iter().cloned() {
            __comprehension_result_968.push(
                (((unit).owner == (city).owner)
                    && ((({
                        let __source = &(rules).units;
                        let __key = (unit).prototype;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .domain
                        == 0i64)
                        && ((({
                            let __source = &(rules).units;
                            let __key = (unit).prototype;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .capacity
                            > 0i64)
                            && (({
                                let __source = &(rules).units;
                                let __key = (unit).prototype;
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .orders
                                & 256i64)
                                != 0))),
            );
        }
        __comprehension_result_968
    })
    .into_iter()
    .map(|value| value as i64)
    .sum::<i64>();
    if (armies < (building).number_of_armies_required) {
        return Ok(false);
    }
    let mut center: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (city).x, (city).y)?;
    if (center).is_none() {
        return Err("City is outside the map".to_string().into());
    }
    hydro = (if (hydro).is_some() {
        hydro.clone()
    } else {
        Some(crate::openciv3::hydrology::Hydrology__from_world(
            &(game).world,
        )?)
    });
    let mut centers: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_970: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_969 = ((game).cities.clone());
        for other in __comprehension_source_969.iter().cloned() {
            __comprehension_result_970.insert(((other).x, (other).y));
        }
        __comprehension_result_970
    };
    let mut owners: indexmap::IndexMap<i64, i64> = {
        let mut __comprehension_result_972: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_971 = ((game).cities.clone());
        for other in __comprehension_source_971.iter().cloned() {
            {
                let (__key, __value) = ((other).id, (other).owner);
                __comprehension_result_972.insert(__key, __value);
            }
        }
        __comprehension_result_972
    };
    let mut workable: Vec<crate::openciv3::world::Tile> = {
        let mut __comprehension_result_974: Vec<crate::openciv3::world::Tile> = Vec::new();
        let __comprehension_source_973 = (crate::strategy::grid::within_rank(
            &((game).world.clone()),
            &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
            crate::openciv3::rules::RuleCatalog__workable_rank(&rules)?,
        )?);
        for tile in __comprehension_source_973.iter().cloned() {
            if ({
                let __needle = ((tile).x, (tile).y);
                let __container = &centers;
                !__container.contains(&__needle)
            } && ((owners.clone())
                .get(
                    &({
                        let __mapping = &(game).ownership;
                        let __key = ((tile).x, (tile).y);
                        let __default = (1i64).checked_neg().ok_or("integer overflow")?;
                        __mapping.get(&__key).cloned().unwrap_or(__default)
                    }),
                )
                .cloned()
                == Some((city).owner)))
            {
                __comprehension_result_974.push(tile.clone());
            }
        }
        __comprehension_result_974
    };
    let mut resources: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_976: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_975 = ({
            let __tuple_value = &(((building).required_resource1, (building).required_resource2));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        for value in __comprehension_source_975.iter().cloned() {
            if (value >= 0i64) {
                __comprehension_result_976.insert(value);
            }
        }
        __comprehension_result_976
    };
    if ((flags & 33554432i64) != 0
        && !((resources.clone()).is_subset(
            &({
                let mut __comprehension_result_978: std::collections::BTreeSet<i64> =
                    std::collections::BTreeSet::new();
                let __comprehension_source_977 = ({
                    let mut __left: Vec<Option<crate::openciv3::world::Tile>> =
                        vec![center.clone()];
                    let __right: Vec<Option<crate::openciv3::world::Tile>> =
                        (workable.clone()).into_iter().map(Some).collect::<Vec<_>>();
                    __left.extend(__right);
                    __left
                });
                for tile in __comprehension_source_977.iter().cloned() {
                    __comprehension_result_978.insert(
                        ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).resource,
                    );
                }
                __comprehension_result_978
            }),
        )))
    {
        return Ok(false);
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
    if !((resources).is_subset(
        &((crate::openciv3::trade_network::TradeNetwork__resources_available(
            &((*(network).as_ref().ok_or("expected a value")?).clone()),
            city,
        )?)
        .into_keys()
        .collect::<std::collections::BTreeSet<_>>()),
    )) {
        return Ok(false);
    }
    let mut requirements: Option<i64> = (building).production_requirements.clone();
    if (requirements).is_none() {
        requirements = Some(
            (flags
                | (if crate::openciv3::building_rules::Building__towns_only(&building)? {
                    4611686018427387904i64
                } else {
                    0i64
                })),
        );
    }
    if (((*(requirements.clone()).as_ref().ok_or("expected a value")?).clone() & 67108864i64) != 0
        && !(crate::openciv3::hydrology::Hydrology__coastal(
            &((*(hydro.clone()).as_ref().ok_or("expected a value")?).clone()),
            &(game).world,
            &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?))
    {
        return Ok(false);
    }
    if (((*(requirements.clone()).as_ref().ok_or("expected a value")?).clone() & 32768i64) != 0
        && !(crate::openciv3::hydrology::river_edges(
            &(game).world,
            &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
        )? != 0i64))
    {
        return Ok(false);
    }
    if (((*(requirements.clone()).as_ref().ok_or("expected a value")?).clone() & 16384i64) != 0
        && !((crate::openciv3::hydrology::river_edges(
            &(game).world,
            &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?) != 0
            || ({
                let mut __comprehension_result_980: Vec<bool> = Vec::new();
                let __comprehension_source_979 = (workable.clone());
                for tile in __comprehension_source_979.iter().cloned() {
                    __comprehension_result_980.push(
                        ((crate::openciv3::hydrology::river_edges(&(game).world, &tile)?) != 0
                            || {
                                let __needle = ((tile).x, (tile).y);
                                let __container =
                                    &(((*(hydro.clone()).as_ref().ok_or("expected a value")?)
                                        .clone())
                                    .freshwater
                                    .clone());
                                __container.contains(&__needle)
                            }),
                    );
                }
                __comprehension_result_980
            })
            .into_iter()
            .any(|__value| __value)))
    {
        return Ok(false);
    }
    let mut limits: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(rules).global_rules, 0i64)?;
    if (((*(requirements.clone()).as_ref().ok_or("expected a value")?).clone()
        & 4611686018427387904i64)
        != 0
        && (crate::openciv3::cities::City__size(city)? > (limits).maximum_level1_city_size))
    {
        return Ok(false);
    }
    if (((*(requirements.clone()).as_ref().ok_or("expected a value")?).clone() & 2048i64) != 0
        && ((crate::openciv3::cities::City__size(city)? > (limits).maximum_level1_city_size)
            || crate::openciv3::hydrology::Hydrology__fresh_access(
                &((*(hydro).as_ref().ok_or("expected a value")?).clone()),
                &(game).world,
                &((*(center).as_ref().ok_or("expected a value")?).clone()),
            )?))
    {
        return Ok(false);
    }
    if (((*(requirements.clone()).as_ref().ok_or("expected a value")?).clone() & 4096i64) != 0
        && (crate::openciv3::cities::City__size(city)? > (limits).maximum_level2_city_size))
    {
        return Ok(false);
    }
    if (((*(requirements).as_ref().ok_or("expected a value")?).clone() & 8796093022208i64) != 0i64)
    {
        let mut size: Option<crate::openciv3::world_size::WorldSize> =
            (&(game).scenario).world_size.clone();
        if (size).is_none() {
            return Err("Forbidden palace requires world-size rules"
                .to_string()
                .into());
        }
        if ((((owned_cities).len() as i64)
            < rt::int_floor_div(
                ((*(size).as_ref().ok_or("expected a value")?).clone()).optimal_cities,
                2i64,
            )?)
            || ({
                let mut __comprehension_result_982: Vec<i64> = Vec::new();
                let __comprehension_source_981 = (local.clone());
                for item in __comprehension_source_981.iter().cloned() {
                    __comprehension_result_982.push(
                        (({
                            let __source = &(rules).buildings;
                            let __key = (item).building;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .effects
                            & 1i64),
                    );
                }
                __comprehension_result_982
            })
            .into_iter()
            .any(|__value| __value != 0))
        {
            return Ok(false);
        }
    }
    Ok(true)
}

// Python: openciv3/production_eligibility.py:178
pub(crate) fn select_building(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut index: i64,
) -> rt::Result<()> {
    if !(can_build(game, city, index, None, None)?) {
        return Err("Building cannot be produced in this city"
            .to_string()
            .into());
    }
    crate::openciv3::cities::City__select_building((*city).clone(), index)?;
    Ok(())
}

// Python: openciv3/production_eligibility.py:34
pub(crate) fn can_train__meets_requirements(
    units: &[crate::openciv3::unit_rules::UnitPrototype],
    known: &std::collections::BTreeSet<i64>,
    mut water: bool,
    resources: &indexmap::IndexMap<i64, i64>,
    mut target: i64,
) -> rt::Result<bool> {
    let mut candidate: crate::openciv3::unit_rules::UnitPrototype = rt::at(units, target)?;
    Ok(((((candidate).prerequisite < 0i64) || {
        let __needle = (candidate).prerequisite;
        let __container = known;
        __container.contains(&__needle)
    }) && ((((candidate).domain != 1i64) || water)
        && ({
            let mut __comprehension_result_984: Vec<bool> = Vec::new();
            let __comprehension_source_983 = ((candidate).required_resources.clone());
            for resource in __comprehension_source_983.iter().cloned() {
                __comprehension_result_984.push({
                    let __needle = resource;
                    let __container = resources;
                    __container.contains_key(&__needle)
                });
            }
            __comprehension_result_984
        })
        .into_iter()
        .all(|__value| __value))))
}
