use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct TradeNetworkSegment {
    pub(crate) network_id: i64,
    pub(crate) tiles: std::collections::BTreeSet<(i64, i64)>,
    pub(crate) resource_counts: indexmap::IndexMap<i64, i64>,
    pub(crate) has_airport: bool,
}

#[derive(Clone, PartialEq)]
pub(crate) struct TradeNetwork {
    pub(crate) game: crate::openciv3::game_state::GameState,
    pub(crate) owner: Option<i64>,
    pub(crate) trade_with: Option<i64>,
    pub(crate) segments: indexmap::IndexMap<i64, indexmap::IndexMap<i64, TradeNetworkSegment>>,
    pub(crate) _routed_deals: indexmap::IndexMap<(i64, i64, i64, i64, i64), i64>,
    pub(crate) _delivered_deals: indexmap::IndexMap<(i64, i64, i64, i64, i64), i64>,
    pub(crate) _domestic_stock: indexmap::IndexMap<i64, indexmap::IndexMap<i64, i64>>,
    pub(crate) _resource_indexes: indexmap::IndexMap<String, i64>,
    pub(crate) _embargoes: std::collections::BTreeSet<(i64, i64)>,
    pub(crate) _capitals: indexmap::IndexMap<i64, TradeNetworkSegment>,
}

// Python: openciv3/trade_network.py:42
pub(crate) fn TradeNetwork____post_init__(mut self_: TradeNetwork) -> rt::Result<TradeNetwork> {
    let mut game: crate::openciv3::game_state::GameState = (self_).game.clone();
    self_._resource_indexes = {
        let mut __comprehension_result_525: indexmap::IndexMap<String, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_523 = (((&(&(game).scenario).rules).resources.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>());
        for (index, item) in __comprehension_source_523.iter().cloned() {
            let __comprehension_source_524 = ({
                let __tuple_value = &(((item).name.clone(), (item).civilopedia_entry.clone()));
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            });
            for key in __comprehension_source_524.iter().cloned() {
                if (((key).chars().count() as i64) != 0i64) {
                    {
                        let (__key, __value) = (rt::casefold(&key), index);
                        __comprehension_result_525.insert(__key, __value);
                    }
                }
            }
        }
        __comprehension_result_525
    };
    let mut owners: indexmap::IndexMap<i64, i64> = {
        let mut __comprehension_result_527: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_526 = ((game).cities.clone());
        for city in __comprehension_source_526.iter().cloned() {
            {
                let (__key, __value) = ((city).id, (city).owner);
                __comprehension_result_527.insert(__key, __value);
            }
        }
        __comprehension_result_527
    };
    let mut center_owners: indexmap::IndexMap<(i64, i64), i64> = {
        let mut __comprehension_result_529: indexmap::IndexMap<(i64, i64), i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_528 = ((game).cities.clone());
        for city in __comprehension_source_528.iter().cloned() {
            {
                let (__key, __value) = (((city).x, (city).y), (city).owner);
                __comprehension_result_529.insert(__key, __value);
            }
        }
        __comprehension_result_529
    };
    let mut colonies: indexmap::IndexMap<(i64, i64), i64> =
        crate::openciv3::scenario_model::ScenarioDefinition__colony_owners(
            &(game).scenario,
            &(game).world,
        )?;
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut routes: i64 = (1i64 | 2i64);
    let mut requested: std::collections::BTreeSet<i64> = (if (&(self_).owner).is_none() {
        {
            let mut __comprehension_result_531: std::collections::BTreeSet<i64> =
                std::collections::BTreeSet::new();
            let __comprehension_source_530 = ((game).players.clone());
            for player in __comprehension_source_530.iter().cloned() {
                __comprehension_result_531.insert((player).civilization);
            }
            __comprehension_result_531
        }
    } else {
        {
            let mut __result = std::collections::BTreeSet::new();
            for __item in
                vec![(*((self_).owner.clone()).as_ref().ok_or("expected a value")?).clone()]
                    .into_iter()
            {
                __result.insert(__item);
            }
            __result
        }
    });
    if (&(self_).trade_with).is_some() {
        {
            requested.insert(
                (*((self_).trade_with.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone(),
            );
        };
    }
    self_._embargoes = crate::openciv3::diplomacy::Diplomacy__active_trade_embargoes(
        &(game).diplomacy,
        (game).turn,
    )?;
    let mut deals: Vec<(i64, i64, crate::openciv3::recurring_deals::RecurringDeal)> = {
        let mut __comprehension_result_534: Vec<(
            i64,
            i64,
            crate::openciv3::recurring_deals::RecurringDeal,
        )> = Vec::new();
        let __comprehension_source_532 = (((&(game).diplomacy).relationships.clone())
            .iter()
            .map(|(__key, __value)| (__key.clone(), __value.clone()))
            .collect::<Vec<_>>());
        for ((left, right), relationship) in __comprehension_source_532.iter().cloned() {
            if (!(crate::openciv3::diplomacy::Diplomacy__at_war(&(game).diplomacy, left, right)?)
                && !(TradeNetwork__embargoed(&self_, left, right)?))
            {
                let __comprehension_source_533 = ((relationship).deals.clone());
                for deal in __comprehension_source_533.iter().cloned() {
                    if ({
                        let __needle = (deal).kind.clone();
                        let __container = &({
                            let __tuple_value = &((
                                crate::openciv3::recurring_deals::DealKind::RESOURCE_PER_TURN,
                                crate::openciv3::recurring_deals::DealKind::LUXURY_PER_TURN,
                            ));
                            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                        });
                        __container.contains(&__needle)
                    } && {
                        let __compare_0 = (deal).start;
                        let __compare_1 = (game).turn;
                        if (__compare_0 <= __compare_1) {
                            let __compare_2 =
                                crate::openciv3::recurring_deals::RecurringDeal__end(&deal)?;
                            (__compare_1 < __compare_2)
                        } else {
                            false
                        }
                    }) {
                        __comprehension_result_534.push((left, right, deal.clone()));
                    }
                }
            }
        }
        __comprehension_result_534
    };
    let mut trading: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_537: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_535 = (deals.clone());
        for (left, right, _) in __comprehension_source_535.iter().cloned() {
            let __comprehension_source_536 = ({
                let __tuple_value = &((left, right));
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            });
            for party in __comprehension_source_536.iter().cloned() {
                __comprehension_result_537.insert(party);
            }
        }
        __comprehension_result_537
    };
    if (requested.clone()).is_disjoint(&(trading.clone())) {
        deals.clear();
        trading.clear();
    }
    if (&(self_).trade_with).is_some() {
        (trading).extend(requested.clone());
    }
    let mut cities_by_owner: indexmap::IndexMap<
        i64,
        indexmap::IndexMap<(i64, i64), crate::openciv3::cities::City>,
    > = [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut city in (&(game).cities).iter() {
        cities_by_owner
            .entry((city).owner)
            .or_insert([].into_iter().collect::<indexmap::IndexMap<_, _>>())
            .insert(((city).x, (city).y), (*city).clone());
    }
    for mut player in (&(game).players).iter() {
        if ({
            let __needle = (player).civilization;
            let __container = &requested;
            !__container.contains(&__needle)
        } && {
            let __needle = (player).civilization;
            let __container = &trading;
            !__container.contains(&__needle)
        }) {
            continue;
        }
        let mut networks: indexmap::IndexMap<i64, TradeNetworkSegment> =
            [].into_iter().collect::<indexmap::IndexMap<_, _>>();
        let mut seen: std::collections::BTreeSet<(i64, i64)> = std::collections::BTreeSet::new();
        let mut centers: indexmap::IndexMap<(i64, i64), crate::openciv3::cities::City> = {
            let __key = (player).civilization;
            let __default = [].into_iter().collect::<indexmap::IndexMap<_, _>>();
            cities_by_owner.get(&__key).cloned().unwrap_or(__default)
        };
        if !(((centers).len() as i64) != 0i64) {
            continue;
        }
        let mut rivals: std::collections::BTreeSet<i64> = {
            let mut __comprehension_result_539: std::collections::BTreeSet<i64> =
                std::collections::BTreeSet::new();
            let __comprehension_source_538 = ((game).players.clone());
            for other in __comprehension_source_538.iter().cloned() {
                if crate::openciv3::diplomacy::Diplomacy__at_war(
                    &(game).diplomacy,
                    (player).civilization,
                    (other).civilization,
                )? {
                    __comprehension_result_539.insert((other).civilization);
                }
            }
            __comprehension_result_539
        };
        let mut ports: std::collections::BTreeSet<(i64, i64)> = std::collections::BTreeSet::new();
        let mut airports: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        for mut for_target_82_12 in (centers.clone())
            .iter()
            .map(|(__key, __value)| (__key.clone(), __value.clone()))
            .collect::<Vec<_>>()
        {
            let (mut point, mut city): ((i64, i64), crate::openciv3::cities::City) =
                for_target_82_12;
            for mut item in (&(city).buildings).iter() {
                let mut building: crate::openciv3::building_rules::Building =
                    rt::at(&(rules).buildings, (item).building)?;
                if {
                    let __needle = (building).rendered_obsolete_by;
                    let __container = &(player).known_technologies;
                    __container.contains(&__needle)
                } {
                    continue;
                }
                if (((building).effects & 524288i64) != 0i64) {
                    {
                        ports.insert(point.clone());
                    };
                }
                if (((building).effects & 1048576i64) != 0i64) {
                    {
                        airports.insert(point.clone());
                    };
                }
            }
        }
        let mut water_types: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
        let mut blocked_water: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        if ((((ports).len() as i64) > 1i64)
            || (!(ports.clone()).is_empty() && {
                let __needle = (player).civilization;
                let __container = &trading;
                __container.contains(&__needle)
            }))
        {
            {
                water_types.insert(11i64);
            };
            for mut tech in (&(player).known_technologies).iter().copied() {
                if {
                    let __compare_0 = 0i64;
                    let __compare_1 = tech;
                    if (__compare_0 <= __compare_1) {
                        let __compare_2 = ((&(rules).technologies).len() as i64);
                        (__compare_1 < __compare_2)
                    } else {
                        false
                    }
                } {
                    let mut effects: i64 = ({
                        let __source = &(rules).technologies;
                        let __key = tech;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .effects;
                    if ((effects & 8192i64) != 0i64) {
                        {
                            water_types.insert(12i64);
                        };
                    }
                    if ((effects & 16384i64) != 0i64) {
                        {
                            water_types.insert(13i64);
                        };
                    }
                }
            }
            blocked_water = {
                let mut __comprehension_result_541: std::collections::BTreeSet<(i64, i64)> =
                    std::collections::BTreeSet::new();
                let __comprehension_source_540 = ((game).units.clone());
                for unit in __comprehension_source_540.iter().cloned() {
                    if ({
                        let __needle = (unit).owner;
                        let __container = &rivals;
                        __container.contains(&__needle)
                    } && ((&(unit).transported_by).is_none()
                        && (((unit).hit_points > 0i64)
                            && (({
                                let __source = &(rules).units;
                                let __key = (unit).prototype;
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .domain
                                == 1i64))))
                    {
                        __comprehension_result_541.insert(((unit).x, (unit).y));
                    }
                }
                __comprehension_result_541
            };
        }
        for mut city in (centers.clone()).values().cloned().collect::<Vec<_>>() {
            if {
                let __needle = (city).id;
                let __container = &networks;
                __container.contains_key(&__needle)
            } {
                continue;
            }
            let mut segment: TradeNetworkSegment = TradeNetworkSegment {
                network_id: (city).id,
                tiles: {
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in vec![].into_iter() {
                        __result.insert(__item);
                    }
                    __result
                },
                resource_counts: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                has_airport: false,
            };
            {
                let __value = segment.clone();
                let __key = (city).id;
                networks.insert(__key, __value);
            }
            let mut center: Option<crate::openciv3::world::Tile> =
                crate::openciv3::world::WorldMap__tile_at(&(game).world, (city).x, (city).y)?;
            if (center).is_none() {
                return Err({
                    let __separator = &(String::new());
                    (&(vec![
                        "City ".to_string(),
                        ((city).id).to_string(),
                        " has no map tile".to_string(),
                    ]))
                        .join(__separator)
                }
                .into());
            }
            let mut pending: Vec<crate::openciv3::world::Tile> =
                vec![(*(center.clone()).as_ref().ok_or("expected a value")?).clone()];
            {
                seen.insert((
                    ((*(center.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                    ((*(center.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                ));
            };
            while (((pending).len() as i64) != 0i64) {
                let mut tile: crate::openciv3::world::Tile = if (pending).is_empty() {
                    return Err("popleft from an empty deque".into());
                } else {
                    (pending).remove(0)
                };
                let mut point: (i64, i64) = ((tile).x, (tile).y);
                ((segment).tiles).insert(point.clone());
                let mut owner_city: Option<i64> =
                    ((game).ownership.clone()).get(&(point.clone())).cloned();
                let mut controlling_player: Option<i64> = (if (owner_city).is_some() {
                    Some(
                        (owners)
                            .get(
                                &((*(owner_city.clone()).as_ref().ok_or("expected a value")?)
                                    .clone()),
                            )
                            .ok_or("missing dict key")?
                            .clone(),
                    )
                } else {
                    (colonies.clone()).get(&(point.clone())).cloned()
                });
                if (((tile).resource >= 0i64)
                    && (controlling_player == Some((player).civilization)))
                {
                    segment.resource_counts.insert(
                        (tile).resource,
                        ({
                            let __mapping = &(segment).resource_counts;
                            let __key = (tile).resource;
                            let __default = 0i64;
                            __mapping.get(&__key).cloned().unwrap_or(__default)
                        })
                        .checked_add(1i64)
                        .ok_or("integer overflow")?,
                    );
                }
                if {
                    let __needle = point.clone();
                    let __container = &centers;
                    __container.contains_key(&__needle)
                } {
                    {
                        let __value = segment.clone();
                        let __key = ((centers).get(&(point.clone())).ok_or("missing dict key")?).id;
                        networks.insert(__key, __value);
                    }
                }
                if {
                    let __needle = point.clone();
                    let __container = &airports;
                    __container.contains(&__needle)
                } {
                    segment.has_airport = true;
                    for mut airport in {
                        let mut __sorted = ({
                            let __set_left = airports.clone();
                            let __set_right = seen.clone();
                            let mut __result = std::collections::BTreeSet::new();
                            for __item in __set_left.difference(&__set_right) {
                                __result.insert(__item.clone());
                            }
                            __result
                        })
                        .into_iter()
                        .collect::<Vec<_>>();
                        __sorted.sort();
                        __sorted
                    } {
                        let mut destination: Option<crate::openciv3::world::Tile> = {
                            let __star_args_542: Vec<i64> = {
                                let __tuple_value = &(airport.clone());
                                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                            };
                            if !(2..=2).contains(&__star_args_542.len()) {
                                return Err("wrong function argument count".into());
                            }
                            crate::openciv3::world::WorldMap__tile_at(
                                &(game).world,
                                rt::at(&__star_args_542, 0 as i64)?,
                                rt::at(&__star_args_542, 1 as i64)?,
                            )?
                        };
                        if !((destination).is_some()) {
                            rt::assertion(false, &("".to_string()))?;
                        }
                        {
                            seen.insert(airport);
                        };
                        {
                            pending
                                .push((*(destination).as_ref().ok_or("expected a value")?).clone());
                        };
                    }
                    airports.clear();
                }
                for mut neighbor in
                    crate::openciv3::world::WorldMap__neighbors(&(game).world, &tile)?
                {
                    let mut position: (i64, i64) = ((neighbor).x, (neighbor).y);
                    if {
                        let __needle = position.clone();
                        let __container = &seen;
                        __container.contains(&__needle)
                    } {
                        continue;
                    }
                    let mut claim: Option<i64> =
                        ((game).ownership.clone()).get(&(position.clone())).cloned();
                    let mut territory: Option<i64> = (if (claim).is_some() {
                        Some(
                            (owners)
                                .get(
                                    &((*(claim.clone()).as_ref().ok_or("expected a value")?)
                                        .clone()),
                                )
                                .ok_or("missing dict key")?
                                .clone(),
                        )
                    } else {
                        (center_owners.clone()).get(&(position.clone())).cloned()
                    });
                    if (match (territory) {
                        Some(__value) => {
                            let __needle = __value;
                            let __container = &rivals;
                            __container.contains(&__needle)
                        }
                        None => false,
                    } || {
                        let __needle = position.clone();
                        let __container = &blocked_water;
                        __container.contains(&__needle)
                    }) {
                        continue;
                    }
                    let mut connected: bool = false;
                    if crate::openciv3::hydrology::is_water(&tile)? {
                        connected = ({
                            let __needle = position.clone();
                            let __container = &ports;
                            __container.contains(&__needle)
                        } || ({
                            let __needle = (neighbor).base_terrain;
                            let __container = &water_types;
                            __container.contains(&__needle)
                        } && !(crate::openciv3::hydrology::land_strip(
                            &(game).world,
                            &tile,
                            &neighbor,
                        )?)));
                    } else {
                        if crate::openciv3::hydrology::is_water(&neighbor)? {
                            connected = ({
                                let __needle = point.clone();
                                let __container = &ports;
                                __container.contains(&__needle)
                            } && {
                                let __needle = (neighbor).base_terrain;
                                let __container = &water_types;
                                __container.contains(&__needle)
                            });
                        } else {
                            connected = (((neighbor).overlays & routes) != 0
                                || (((tile).overlays & routes) != 0 && {
                                    let __needle = position.clone();
                                    let __container = &centers;
                                    __container.contains_key(&__needle)
                                }));
                        }
                    }
                    if connected {
                        {
                            seen.insert(position);
                        };
                        {
                            pending.push(neighbor);
                        };
                    }
                }
            }
        }
        self_.segments.insert((player).civilization, networks);
    }
    self_._capitals = {
        let mut __comprehension_result_544: indexmap::IndexMap<i64, TradeNetworkSegment> =
            indexmap::IndexMap::new();
        let __comprehension_source_543 = ((game).cities.clone());
        for city in __comprehension_source_543.iter().cloned() {
            if ((city).capital && {
                let __needle = (city).owner;
                let __container = &(self_).segments;
                __container.contains_key(&__needle)
            }) {
                {
                    let (__key, __value) = (
                        (city).owner,
                        ((&(self_).segments)
                            .get(&((city).owner))
                            .ok_or("missing dict key")?)
                        .get(&((city).id))
                        .ok_or("missing dict key")?
                        .clone(),
                    );
                    __comprehension_result_544.insert(__key, __value);
                }
            }
        }
        __comprehension_result_544
    };
    TradeNetwork___apply_resource_deals(self_.clone(), &deals)?;
    for mut partner in {
        let __set_left = (((self_).segments.clone())
            .keys()
            .cloned()
            .collect::<Vec<_>>())
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>();
        let __set_right = requested;
        let mut __result = std::collections::BTreeSet::new();
        for __item in __set_left.difference(&__set_right) {
            __result.insert(__item.clone());
        }
        __result
    } {
        {
            let __key = partner;
            (self_)
                .segments
                .clone()
                .shift_remove(&__key)
                .ok_or("missing dict key")?;
        }
    }
    Ok(self_.clone())
}

// Python: openciv3/trade_network.py:161
pub(crate) fn TradeNetwork___apply_resource_deals(
    mut self_: TradeNetwork,
    deals: &[(i64, i64, crate::openciv3::recurring_deals::RecurringDeal)],
) -> rt::Result<()> {
    if !(((deals).len() as i64) != 0i64) {
        return Ok(());
    }
    let mut game: crate::openciv3::game_state::GameState = (self_).game.clone();
    let mut capitals: indexmap::IndexMap<i64, TradeNetworkSegment> = (self_)._capitals.clone();
    let mut inbound: indexmap::IndexMap<(i64, i64, i64, i64, i64), i64> =
        indexmap::IndexMap::<(i64, i64, i64, i64, i64), i64>::new();
    let mut outbound: indexmap::IndexMap<(i64, i64, i64, i64, i64), i64> =
        indexmap::IndexMap::<(i64, i64, i64, i64, i64), i64>::new();
    for mut for_target_168_8 in (deals).iter() {
        let (mut owner, mut partner, mut deal): (
            i64,
            i64,
            crate::openciv3::recurring_deals::RecurringDeal,
        ) = (*for_target_168_8).clone();
        let (mut origin, mut destination): (
            Option<TradeNetworkSegment>,
            Option<TradeNetworkSegment>,
        ) = (
            (capitals.clone()).get(&(owner)).cloned(),
            (capitals.clone()).get(&(partner)).cloned(),
        );
        if ((origin).is_none()
            || ((destination).is_none()
                || !(TradeNetwork___connected_segments(
                    (*(origin.clone()).as_ref().ok_or("expected a value")?).clone(),
                    &((*(destination.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?)))
        {
            continue;
        }
        let mut key: Option<(i64, i64, i64, i64, i64)> =
            TradeNetwork___resource_agreement(&self_, owner, partner, &deal)?;
        if (key).is_none() {
            continue;
        }
        if ((deal).direction.clone() == crate::openciv3::recurring_deals::DealDirection::INBOUND) {
            {
                let __value = ((inbound.clone())
                    .get(&((*(key.clone()).as_ref().ok_or("expected a value")?).clone()))
                    .cloned()
                    .unwrap_or_default())
                .checked_add(1i64)
                .ok_or("integer overflow")?;
                let __key = (*(key.clone()).as_ref().ok_or("expected a value")?).clone();
                inbound.insert(__key, __value);
            }
        } else {
            {
                let __value = ((outbound.clone())
                    .get(&((*(key.clone()).as_ref().ok_or("expected a value")?).clone()))
                    .cloned()
                    .unwrap_or_default())
                .checked_add(1i64)
                .ok_or("integer overflow")?;
                let __key = (*(key.clone()).as_ref().ok_or("expected a value")?).clone();
                outbound.insert(__key, __value);
            }
        }
    }
    let mut stock: indexmap::IndexMap<i64, indexmap::IndexMap<i64, i64>> = {
        let mut __comprehension_result_546: indexmap::IndexMap<i64, indexmap::IndexMap<i64, i64>> =
            indexmap::IndexMap::new();
        let __comprehension_source_545 = ((capitals.clone())
            .iter()
            .map(|(__key, __value)| (__key.clone(), __value.clone()))
            .collect::<Vec<_>>());
        for (owner, segment) in __comprehension_source_545.iter().cloned() {
            {
                let (__key, __value) = (owner, {
                    let mut __counts: indexmap::IndexMap<i64, i64> = indexmap::IndexMap::new();
                    for __item in (((segment).resource_counts.clone())
                        .keys()
                        .cloned()
                        .collect::<Vec<_>>())
                    .into_iter()
                    {
                        *__counts.entry(__item).or_insert(0) += 1;
                    }
                    __counts
                });
                __comprehension_result_546.insert(__key, __value);
            }
        }
        __comprehension_result_546
    };
    self_._domestic_stock = stock.clone();
    self_._routed_deals = {
        let mut __result = inbound;
        for (__key, __value) in outbound {
            *__result.entry(__key).or_insert(0) += __value;
        }
        __result
    };
    for mut for_target_185_8 in {
        let mut __sorted = ((self_)._routed_deals.clone())
            .iter()
            .map(|(__key, __value)| (__key.clone(), __value.clone()))
            .collect::<Vec<_>>();
        __sorted.sort();
        __sorted
    } {
        let (mut key, mut copies): ((i64, i64, i64, i64, i64), i64) = for_target_185_8;
        let (_, mut seller, mut buyer, mut resource, _): (i64, i64, i64, i64, i64) = key.clone();
        let mut amount: i64 = (if TradeNetwork___known(&self_, seller, resource)? {
            (copies).min(
                ((stock).get(&(seller)).ok_or("missing dict key")?)
                    .get(&(resource))
                    .ok_or("missing dict key")?
                    .clone(),
            )
        } else {
            0i64
        });
        if !(amount != 0i64) {
            continue;
        }
        self_._delivered_deals.insert(key.clone(), amount);
        let mut seller_stock: indexmap::IndexMap<i64, i64> =
            (stock).get(&(seller)).ok_or("missing dict key")?.clone();
        {
            let __value = ((seller_stock)
                .get(&(resource))
                .ok_or("missing dict key")?
                .clone())
            .checked_sub(amount)
            .ok_or("integer overflow")?;
            let __key = resource;
            seller_stock.insert(__key, __value);
        }
        let mut supplied: indexmap::IndexMap<i64, i64> =
            ((capitals).get(&(seller)).ok_or("missing dict key")?)
                .resource_counts
                .clone();
        {
            let __value = ((supplied)
                .get(&(resource))
                .ok_or("missing dict key")?
                .clone())
            .checked_sub(amount)
            .ok_or("integer overflow")?;
            let __key = resource;
            supplied.insert(__key, __value);
        }
        if ((supplied)
            .get(&(resource))
            .ok_or("missing dict key")?
            .clone()
            == 0i64)
        {
            {
                let __key = resource;
                supplied.shift_remove(&__key).ok_or("missing dict key")?;
            }
        }
        let mut received: indexmap::IndexMap<i64, i64> =
            ((capitals).get(&(buyer)).ok_or("missing dict key")?)
                .resource_counts
                .clone();
        {
            let __value = ({
                let __key = resource;
                let __default = 0i64;
                received.get(&__key).cloned().unwrap_or(__default)
            })
            .checked_add(amount)
            .ok_or("integer overflow")?;
            let __key = resource;
            received.insert(__key, __value);
        }
    }
    Ok(())
}

// Python: openciv3/trade_network.py:200
pub(crate) fn TradeNetwork___resource_agreement(
    self_: &TradeNetwork,
    mut owner: i64,
    mut partner: i64,
    deal: &crate::openciv3::recurring_deals::RecurringDeal,
) -> rt::Result<Option<(i64, i64, i64, i64, i64)>> {
    let mut resource: Option<i64> = ((self_)._resource_indexes.clone())
        .get(&(rt::casefold(&(deal).resource)))
        .cloned();
    if (resource).is_none() {
        return Ok(None);
    }
    let mut actual: i64 = ({
        let __source = &(&(&(&(self_).game).scenario).rules).resources;
        let __key = (*(resource.clone()).as_ref().ok_or("expected a value")?).clone();
        &__source[rt::index(__source.len(), __key)?]
    })
    .kind;
    let mut expected: i64 =
        (if ((deal).kind.clone() == crate::openciv3::recurring_deals::DealKind::LUXURY_PER_TURN) {
            1i64
        } else {
            2i64
        });
    if (actual != expected) {
        return Ok(None);
    }
    let (mut seller, mut buyer): (i64, i64) = (if ((deal).direction.clone()
        == crate::openciv3::recurring_deals::DealDirection::INBOUND)
    {
        (partner, owner)
    } else {
        (owner, partner)
    });
    Ok(Some((
        (deal).start,
        seller,
        buyer,
        (*(resource).as_ref().ok_or("expected a value")?).clone(),
        crate::openciv3::recurring_deals::RecurringDeal__end(deal)?,
    )))
}

// Python: openciv3/trade_network.py:211
pub(crate) fn TradeNetwork__embargoed(
    self_: &TradeNetwork,
    mut left: i64,
    mut right: i64,
) -> rt::Result<bool> {
    Ok({
        let __needle = ((left).min(right), (left).max(right));
        let __container = &(self_)._embargoes;
        __container.contains(&__needle)
    })
}

// Python: openciv3/trade_network.py:214
pub(crate) fn TradeNetwork__delivery_status(
    self_: &TradeNetwork,
    mut owner: i64,
    mut partner: i64,
    deal: &crate::openciv3::recurring_deals::RecurringDeal,
) -> rt::Result<String> {
    if crate::openciv3::diplomacy::Diplomacy__at_war(&(&(self_).game).diplomacy, owner, partner)? {
        return Ok("At war".to_string());
    }
    if ((deal).start > (&(self_).game).turn) {
        return Ok({
            let __separator = &(String::new());
            (&(vec!["Starts on turn ".to_string(), ((deal).start).to_string()])).join(__separator)
        });
    }
    if ((&(self_).game).turn >= crate::openciv3::recurring_deals::RecurringDeal__end(deal)?) {
        return Ok("Expired".to_string());
    }
    if TradeNetwork__embargoed(self_, owner, partner)? {
        return Ok("Trade embargo".to_string());
    }
    let mut key: Option<(i64, i64, i64, i64, i64)> =
        TradeNetwork___resource_agreement(self_, owner, partner, deal)?;
    if (key).is_none() {
        return Ok("Resource unavailable".to_string());
    }
    let mut expected: i64 = (&(self_)._routed_deals)
        .get(&((*(key.clone()).as_ref().ok_or("expected a value")?).clone()))
        .ok_or("missing dict key")?
        .clone();
    if !(expected != 0i64) {
        return Ok("Route interrupted".to_string());
    }
    let mut delivered: i64 = (&(self_)._delivered_deals)
        .get(&((*(key).as_ref().ok_or("expected a value")?).clone()))
        .ok_or("missing dict key")?
        .clone();
    if !(delivered != 0i64) {
        return Ok("Supply unavailable".to_string());
    }
    Ok((if (delivered == expected) {
        "Delivering".to_string()
    } else {
        {
            let __separator = &(String::new());
            (&(vec![
                (delivered).to_string(),
                " of ".to_string(),
                (expected).to_string(),
                " copies delivered".to_string(),
            ]))
                .join(__separator)
        }
    }))
}

// Python: openciv3/trade_network.py:234
pub(crate) fn TradeNetwork__exportable_resources(
    self_: &TradeNetwork,
    mut seller: i64,
    mut buyer: i64,
) -> rt::Result<std::collections::BTreeSet<i64>> {
    let (mut source, mut target): (Option<TradeNetworkSegment>, Option<TradeNetworkSegment>) = (
        ((self_)._capitals.clone()).get(&(seller)).cloned(),
        ((self_)._capitals.clone()).get(&(buyer)).cloned(),
    );
    if ((source).is_none()
        || ((target).is_none()
            || (crate::openciv3::diplomacy::Diplomacy__at_war(
                &(&(self_).game).diplomacy,
                seller,
                buyer,
            )? || (TradeNetwork__embargoed(self_, seller, buyer)?
                || !(TradeNetwork___connected_segments(
                    (*(source.clone()).as_ref().ok_or("expected a value")?).clone(),
                    &((*(target.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?)))))
    {
        return Ok(std::collections::BTreeSet::new());
    }
    let mut domestic: indexmap::IndexMap<i64, i64> = {
        let __mapping = &(self_)._domestic_stock;
        let __key = seller;
        let __default = ((*(source).as_ref().ok_or("expected a value")?).clone())
            .resource_counts
            .clone();
        __mapping.get(&__key).cloned().unwrap_or(__default)
    };
    Ok({
        let mut __comprehension_result_548: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_547 = ((domestic.clone())
            .iter()
            .map(|(__key, __value)| (__key.clone(), __value.clone()))
            .collect::<Vec<_>>());
        for (resource, copies) in __comprehension_source_547.iter().cloned() {
            if ((copies > 1i64)
                && (!({
                    let __mapping = ((*(target.clone()).as_ref().ok_or("expected a value")?)
                        .clone())
                    .resource_counts
                    .clone();
                    let __key = resource;
                    let __default = 0i64;
                    __mapping.get(&__key).cloned().unwrap_or(__default)
                } != 0i64)
                    && ((({
                        let __source = &(&(&(&(self_).game).scenario).rules).resources;
                        let __key = resource;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .kind
                        != 0i64)
                        && (TradeNetwork___known(self_, seller, resource)?
                            && TradeNetwork___known(self_, buyer, resource)?))))
            {
                __comprehension_result_548.insert(resource);
            }
        }
        __comprehension_result_548
    })
}

// Python: openciv3/trade_network.py:246
pub(crate) fn TradeNetwork___connected_segments(
    mut first: TradeNetworkSegment,
    second: &TradeNetworkSegment,
) -> rt::Result<bool> {
    Ok((((first).has_airport && (second).has_airport)
        || !(((first).tiles.clone()).is_disjoint(&((second).tiles.clone())))))
}

// Python: openciv3/trade_network.py:249
pub(crate) fn TradeNetwork___known(
    self_: &TradeNetwork,
    mut player: i64,
    mut resource: i64,
) -> rt::Result<bool> {
    let mut prerequisite: i64 = ({
        let __source = &(&(&(&(self_).game).scenario).rules).resources;
        let __key = resource;
        &__source[rt::index(__source.len(), __key)?]
    })
    .prerequisite;
    Ok(((prerequisite < 0i64) || {
        let __needle = prerequisite;
        let __container = &({
            let __source = &(&(self_).game).players;
            let __key = player;
            &__source[rt::index(__source.len(), __key)?]
        })
        .known_technologies;
        __container.contains(&__needle)
    }))
}

// Python: openciv3/trade_network.py:253
pub(crate) fn TradeNetwork__resources_available(
    self_: &TradeNetwork,
    city: &crate::openciv3::cities::City,
) -> rt::Result<indexmap::IndexMap<i64, i64>> {
    Ok({
        let mut __comprehension_result_550: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_549 = (((((&(self_).segments)
            .get(&((city).owner))
            .ok_or("missing dict key")?)
        .get(&((city).id))
        .ok_or("missing dict key")?)
        .resource_counts
        .clone())
        .iter()
        .map(|(__key, __value)| (__key.clone(), __value.clone()))
        .collect::<Vec<_>>());
        for (resource, count) in __comprehension_source_549.iter().cloned() {
            if TradeNetwork___known(self_, (city).owner, resource)? {
                {
                    let (__key, __value) = (resource, count);
                    __comprehension_result_550.insert(__key, __value);
                }
            }
        }
        __comprehension_result_550
    })
}

/// Count distinct luxury types, not the number of connected deposits.
// Python: openciv3/trade_network.py:257
pub(crate) fn TradeNetwork__luxury_count(
    self_: &TradeNetwork,
    city: &crate::openciv3::cities::City,
) -> rt::Result<i64> {
    Ok(({
        let mut __comprehension_result_552: Vec<bool> = Vec::new();
        let __comprehension_source_551 = (TradeNetwork__resources_available(self_, city)?);
        for resource in __comprehension_source_551.keys().cloned() {
            __comprehension_result_552.push(
                (({
                    let __source = &(&(&(&(self_).game).scenario).rules).resources;
                    let __key = resource;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .kind
                    == 1i64),
            );
        }
        __comprehension_result_552
    })
    .into_iter()
    .map(|value| value as i64)
    .sum::<i64>())
}

// Python: openciv3/trade_network.py:262
pub(crate) fn TradeNetwork__has_trade_access(
    self_: &TradeNetwork,
    point: &(i64, i64),
    mut player: i64,
    mut resource: i64,
) -> rt::Result<bool> {
    Ok((TradeNetwork___known(self_, player, resource)?
        && ({
            let mut __comprehension_result_554: Vec<bool> = Vec::new();
            let __comprehension_source_553 = (((&(self_).segments)
                .get(&(player))
                .ok_or("missing dict key")?
                .clone())
            .values()
            .cloned()
            .collect::<Vec<_>>());
            for segment in __comprehension_source_553.iter().cloned() {
                __comprehension_result_554.push(
                    ({
                        let __needle = (*point).clone();
                        let __container = &(segment).tiles;
                        __container.contains(&__needle)
                    } && ({
                        let __mapping = &(segment).resource_counts;
                        let __key = resource;
                        let __default = 0i64;
                        __mapping.get(&__key).cloned().unwrap_or(__default)
                    } > 0i64)),
                );
            }
            __comprehension_result_554
        })
        .into_iter()
        .any(|__value| __value)))
}

// Python: openciv3/trade_network.py:267
pub(crate) fn TradeNetwork__connected_to_capital(
    self_: &TradeNetwork,
    city: &crate::openciv3::cities::City,
) -> rt::Result<bool> {
    let mut capital: crate::openciv3::cities::City = (&({
        let mut __comprehension_result_556: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_555 = ((&(self_).game).cities.clone());
        for other in __comprehension_source_555.iter().cloned() {
            if ((other).owner == (city).owner) {
                __comprehension_result_556.push(other.clone());
            }
        }
        __comprehension_result_556
    }))
        .iter()
        .next()
        .cloned()
        .ok_or("StopIteration")?;
    let mut networks: indexmap::IndexMap<i64, TradeNetworkSegment> = (&(self_).segments)
        .get(&((city).owner))
        .ok_or("missing dict key")?
        .clone();
    Ok(
        (((networks).get(&((city).id)).ok_or("missing dict key")?).network_id
            == ((networks).get(&((capital).id)).ok_or("missing dict key")?).network_id),
    )
}
