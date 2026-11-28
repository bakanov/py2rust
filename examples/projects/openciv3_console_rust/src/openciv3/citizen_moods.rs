use py2rust_service_runtime as rt;

/// Refresh all cities using one network, hydrology, and corruption snapshot.
// Python: openciv3/citizen_moods.py:13
pub(crate) fn recalculate_all_moods(
    game: &crate::openciv3::game_state::GameState,
    enter_disorder: &Option<bool>,
) -> rt::Result<()> {
    if !(((&(game).cities).len() as i64) != 0i64) {
        return Ok(());
    }
    let mut corruption: indexmap::IndexMap<i64, f64> =
        crate::openciv3::corruption::corruption_levels(game)?;
    let mut network: crate::openciv3::trade_network::TradeNetwork =
        crate::openciv3::trade_network::TradeNetwork____post_init__(
            crate::openciv3::trade_network::TradeNetwork {
                game: (*game).clone(),
                owner: None,
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
    for mut city in (&(game).cities).iter() {
        {
            let __call_605_0 = &((*game).clone());
            let __call_605_1 = (*city).clone();
            let __call_605_2 = (corruption)
                .get(&((city).id))
                .ok_or("missing dict key")?
                .clone();
            let __call_605_3 = Some(crate::openciv3::trade_network::TradeNetwork__luxury_count(
                &network, city,
            )?);
            let __call_605_4 = &(Some(hydro.clone()));
            let __call_605_5 = enter_disorder;
            recalculate_moods(
                __call_605_0,
                __call_605_1,
                __call_605_2,
                __call_605_3,
                __call_605_4,
                __call_605_5,
            )
        }?;
    }
    Ok(())
}

// Python: openciv3/citizen_moods.py:25
pub(crate) fn resolve_moods(
    mut laborers: i64,
    mut born_content: i64,
    mut content_points: i64,
    mut happy_points: i64,
) -> rt::Result<Vec<i64>> {
    if ((laborers < 0i64) || (born_content < 0i64)) {
        return Err("Invalid citizen counts".to_string().into());
    }
    let (mut H, mut C, mut U): (i64, i64, i64) = (0i64, 1i64, 2i64);
    let mut moods: Vec<i64> = {
        let mut __left: Vec<i64> =
            (vec![C]).repeat(std::cmp::max((laborers).min(born_content), 0) as usize);
        let __right: Vec<i64> = (vec![U]).repeat(std::cmp::max(
            (0i64).max(
                (laborers)
                    .checked_sub(born_content)
                    .ok_or("integer overflow")?,
            ),
            0,
        ) as usize);
        __left.extend(__right);
        __left
    };

    if (happy_points >= 0i64) {
        if (content_points >= 0i64) {
            resolve_moods__move_residents(moods.clone(), content_points, U, C)?;
            resolve_moods__happiness(&moods, C, H, U, happy_points)?;
        } else {
            resolve_moods__happiness(
                &(moods.clone()),
                C,
                H,
                U,
                (0i64).max(
                    (happy_points)
                        .checked_add(content_points)
                        .ok_or("integer overflow")?,
                ),
            )?;
            resolve_moods__move_residents(
                moods.clone(),
                (0i64).max(
                    ((content_points).checked_neg().ok_or("integer overflow")?)
                        .checked_sub(happy_points)
                        .ok_or("integer overflow")?,
                ),
                H,
                C,
            )?;
        }
    } else {
        if (content_points >= 0i64) {
            resolve_moods__move_residents(
                moods.clone(),
                (0i64).max(
                    ((happy_points).checked_neg().ok_or("integer overflow")?)
                        .checked_sub(content_points)
                        .ok_or("integer overflow")?,
                ),
                C,
                U,
            )?;
            resolve_moods__move_residents(
                moods.clone(),
                (0i64).max(
                    (content_points)
                        .checked_add(happy_points)
                        .ok_or("integer overflow")?,
                ),
                U,
                C,
            )?;
        } else {
            resolve_moods__move_residents(
                moods.clone(),
                (happy_points).checked_neg().ok_or("integer overflow")?,
                C,
                U,
            )?;
        }
    }
    Ok(moods)
}

// Python: openciv3/citizen_moods.py:58
pub(crate) fn luxury_happiness(mut count: i64, mut marketplace: bool) -> rt::Result<i64> {
    if (count < 0i64) {
        return Err("Luxury count cannot be negative".to_string().into());
    }
    Ok((if marketplace {
        ((rt::int_floor_div(count, 2i64)?)
            .checked_mul(rt::int_floor_div(
                (count).checked_add(1i64).ok_or("integer overflow")?,
                2i64,
            )?)
            .ok_or("integer overflow")?)
        .checked_add(rt::int_floor_div(
            (count).checked_add(1i64).ok_or("integer overflow")?,
            2i64,
        )?)
        .ok_or("integer overflow")?
    } else {
        count
    }))
}

/// Update resident moods; return whether unhappy laborers outnumber happy.
///
/// Luxury access defaults to a fresh trade network. Batch callers can supply
/// the distinct luxury count from one shared snapshot. Callers choose whether an
/// unhappy result enters disorder. Pass None to leave the current disorder state intact.
// Python: openciv3/citizen_moods.py:64
pub(crate) fn recalculate_moods(
    game: &crate::openciv3::game_state::GameState,
    mut city: crate::openciv3::cities::City,
    mut corruption: f64,
    mut luxury_count: Option<i64>,
    hydro: &Option<crate::openciv3::hydrology::Hydrology>,
    enter_disorder: &Option<bool>,
) -> rt::Result<bool> {
    let (mut rules, mut world): (
        crate::openciv3::rules::RuleCatalog,
        crate::openciv3::world::WorldMap,
    ) = ((&(game).scenario).rules.clone(), (game).world.clone());
    if (luxury_count).is_none() {
        luxury_count = Some(crate::openciv3::trade_network::TradeNetwork__luxury_count(
            &(crate::openciv3::trade_network::TradeNetwork____post_init__(
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
            )?),
            &city,
        )?);
    }
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (city).owner)?;
    let mut effective: Vec<crate::openciv3::cities::CityBuilding> =
        crate::openciv3::building_effects::effective_buildings(
            &city,
            &(game).cities,
            &(game).players,
            &world,
            &rules,
        )?;
    let mut buildings: Vec<crate::openciv3::building_rules::Building> = {
        let mut __comprehension_result_607: Vec<crate::openciv3::building_rules::Building> =
            Vec::new();
        let __comprehension_source_606 = (effective.clone());
        for item in __comprehension_source_606.iter().cloned() {
            __comprehension_result_607.push(rt::at(&(rules).buildings, (item).building)?);
        }
        __comprehension_result_607
    };
    let mut content: i64 = 0i64;
    let mut doubled: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
    let mut center: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&world, (city).x, (city).y)?;
    if !((center).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    for mut source in (&(game).cities).iter() {
        if ((source).owner != (city).owner) {
            continue;
        }
        let mut tile: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(&world, (source).x, (source).y)?;
        if !((tile).is_some()) {
            rt::assertion(false, &("".to_string()))?;
        }
        for mut item in (&(source).buildings).iter() {
            let mut building: crate::openciv3::building_rules::Building =
                rt::at(&(rules).buildings, (item).building)?;
            if {
                let __needle = (building).rendered_obsolete_by;
                let __container = &(player).known_technologies;
                __container.contains(&__needle)
            } {
                continue;
            }
            if (((building).effects & 268435456i64) != 0 && ((building).doubles_happiness >= 0i64))
            {
                {
                    doubled.insert((building).doubles_happiness);
                };
            }
            if ((source).id == (city).id) {
                continue;
            }
            if (((building).effects & 1073741824i64) != 0
                && (((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).continent
                    != ((*(center.clone()).as_ref().ok_or("expected a value")?).clone()).continent))
            {
                continue;
            }
            content = (content)
                .checked_add(
                    ((building).content_faces_all_cities)
                        .checked_sub((building).unhappy_faces_all_cities)
                        .ok_or("integer overflow")?,
                )
                .ok_or("integer overflow")?;
        }
    }
    content = (content)
        .checked_add(
            ({
                let mut __comprehension_result_609: Vec<i64> = Vec::new();
                let __comprehension_source_608 = ({
                    let __left = effective.clone();
                    let __right = buildings.clone();
                    if true && __left.len() != __right.len() {
                        return Err("zip() argument lengths differ".into());
                    }
                    let mut __result: Vec<(
                        crate::openciv3::cities::CityBuilding,
                        crate::openciv3::building_rules::Building,
                    )> = Vec::new();
                    let __length = __left.len().min(__right.len());
                    let mut __left_iter = __left.into_iter();
                    let mut __right_iter = __right.into_iter();
                    for __index in 0..__length {
                        __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
                    }
                    __result
                });
                for (item, building) in __comprehension_source_608.iter().cloned() {
                    if {
                        let __needle = (building).rendered_obsolete_by;
                        let __container = &(player).known_technologies;
                        !__container.contains(&__needle)
                    } {
                        __comprehension_result_609.push(
                            (((building).content_faces)
                                .checked_mul(
                                    (if {
                                        let __needle = (item).building;
                                        let __container = &doubled;
                                        __container.contains(&__needle)
                                    } {
                                        2i64
                                    } else {
                                        1i64
                                    }),
                                )
                                .ok_or("integer overflow")?)
                            .checked_sub((building).unhappy_faces)
                            .ok_or("integer overflow")?,
                        );
                    }
                }
                __comprehension_result_609
            })
            .into_iter()
            .sum::<i64>(),
        )
        .ok_or("integer overflow")?;
    let mut police: i64 = ({
        let mut __comprehension_result_611: Vec<bool> = Vec::new();
        let __comprehension_source_610 = ((game).units.clone());
        for unit in __comprehension_source_610.iter().cloned() {
            __comprehension_result_611.push(
                (((unit).owner == (city).owner)
                    && ((((unit).x, (unit).y) == ((city).x, (city).y))
                        && crate::openciv3::unit_entry::can_defend_on_land(game, &unit)?)),
            );
        }
        __comprehension_result_611
    })
    .into_iter()
    .map(|value| value as i64)
    .sum::<i64>();
    content = (content)
        .checked_add(
            (({
                let __source = &(rules).governments;
                let __key = (player).government;
                &__source[rt::index(__source.len(), __key)?]
            })
            .military_police_limit)
                .min(police),
        )
        .ok_or("integer overflow")?;
    let mut happy: i64 = ({
        let __call_612_0 = game;
        let __call_612_1 = &city;
        let __call_612_2 = corruption;
        let __call_612_3 = hydro;
        let __call_612_4 = false;
        let __call_612_default_4 = &None;
        crate::openciv3::city_economy::city_commerce(
            __call_612_0,
            __call_612_1,
            __call_612_2,
            __call_612_3,
            __call_612_default_4,
            __call_612_4,
        )
    }?)
    .happiness;
    happy = (happy)
        .checked_add(luxury_happiness(
            (*(luxury_count).as_ref().ok_or("expected a value")?).clone(),
            ({
                let mut __comprehension_result_614: Vec<i64> = Vec::new();
                let __comprehension_source_613 = (buildings.clone());
                for b in __comprehension_source_613.iter().cloned() {
                    __comprehension_result_614.push(((b).effects & 1024i64));
                }
                __comprehension_result_614
            })
            .into_iter()
            .any(|__value| __value != 0),
        )?)
        .ok_or("integer overflow")?;
    if ((city).pop_rush_unhappiness_turns > 0i64) {
        let mut duration: i64 = ({
            let __source = &(rules).global_rules;
            let __key = 0i64;
            &__source[rt::index(__source.len(), __key)?]
        })
        .turn_penalty_for_each_hurry_sacrifice;
        if (duration <= 0i64) {
            return Err("Hurry sacrifice penalty duration must be positive"
                .to_string()
                .into());
        }
        happy = (happy)
            .checked_sub(
                (rt::int_floor_div(
                    ((city).pop_rush_unhappiness_turns)
                        .checked_sub(1i64)
                        .ok_or("integer overflow")?,
                    duration,
                )?)
                .checked_add(1i64)
                .ok_or("integer overflow")?,
            )
            .ok_or("integer overflow")?;
    }
    let mut laborers: Vec<crate::openciv3::cities::Resident> = {
        let mut __comprehension_result_616: Vec<crate::openciv3::cities::Resident> = Vec::new();
        let __comprehension_source_615 = ((city).residents.clone());
        for resident in __comprehension_source_615.iter().cloned() {
            if ({
                let __source = &(rules).citizens;
                let __key = (resident).citizen_type;
                &__source[rt::index(__source.len(), __key)?]
            })
            .default_citizen
            {
                __comprehension_result_616.push(resident.clone());
            }
        }
        __comprehension_result_616
    };
    let mut moods: Vec<i64> = resolve_moods(
        ((laborers).len() as i64),
        ({
            let __source = &(&(game).scenario).difficulties;
            let __key = (game).difficulty;
            &__source[rt::index(__source.len(), __key)?]
        })
        .content_citizens,
        content,
        happy,
    )?;
    for mut for_target_113_4 in {
        let __left = laborers;
        let __right = moods.clone();
        if false && __left.len() != __right.len() {
            return Err("zip() argument lengths differ".into());
        }
        let mut __result: Vec<(crate::openciv3::cities::Resident, i64)> = Vec::new();
        let __length = __left.len().min(__right.len());
        let mut __left_iter = __left.into_iter();
        let mut __right_iter = __right.into_iter();
        for __index in 0..__length {
            __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
        }
        __result
    } {
        let (mut resident, mut mood): (crate::openciv3::cities::Resident, i64) = for_target_113_4;
        resident.mood = mood;
    }
    let mut unhappy: bool = ((moods.clone())
        .iter()
        .filter(|__item| (*__item).clone() == 2i64)
        .count() as i64
        > (moods.clone())
            .iter()
            .filter(|__item| (*__item).clone() == 0i64)
            .count() as i64);
    if (enter_disorder).is_some() {
        city.disorder = (unhappy && ((*enter_disorder).clone()).is_some());
    }
    Ok(unhappy)
}

// Python: openciv3/citizen_moods.py:30
pub(crate) fn resolve_moods__move_residents(
    mut moods: Vec<i64>,
    mut count: i64,
    mut source: i64,
    mut target: i64,
) -> rt::Result<i64> {
    let mut moved: i64 = 0i64;
    for mut for_target_32_8 in (moods.clone())
        .into_iter()
        .enumerate()
        .map(|(__index, __value)| (__index as i64 + 0i64, __value))
        .collect::<Vec<_>>()
    {
        let (mut i, mut mood): (i64, i64) = for_target_32_8;
        if (moved >= count) {
            break;
        }
        if (mood == source) {
            {
                let __value = target;
                let __key = i;
                let __index = rt::index(moods.len(), __key)?;
                moods[__index] = __value;
            }
            moved = (moved).checked_add(1i64).ok_or("integer overflow")?;
        }
    }
    Ok(moved)
}

// Python: openciv3/citizen_moods.py:39
pub(crate) fn resolve_moods__happiness(
    moods: &[i64],
    mut C: i64,
    mut H: i64,
    mut U: i64,
    mut points: i64,
) -> rt::Result<()> {
    points = (points)
        .checked_sub(resolve_moods__move_residents(moods.to_vec(), points, C, H)?)
        .ok_or("integer overflow")?;
    points = (points)
        .checked_sub(
            (2i64)
                .checked_mul(resolve_moods__move_residents(
                    moods.to_vec(),
                    rt::int_floor_div(points, 2i64)?,
                    U,
                    H,
                )?)
                .ok_or("integer overflow")?,
        )
        .ok_or("integer overflow")?;
    resolve_moods__move_residents(moods.to_vec(), points, U, C)?;
    Ok(())
}
