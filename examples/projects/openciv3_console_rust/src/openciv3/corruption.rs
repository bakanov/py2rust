use py2rust_service_runtime as rt;

// Python: openciv3/corruption.py:8
pub(crate) fn corruption_fraction(
    mut distance: f64,
    mut max_distance: f64,
    mut rank: i64,
    mut city_count: i64,
    mut government: i64,
    mut adjusted_optimum: i64,
    mut reducers: i64,
    mut wonders: i64,
) -> rt::Result<f64> {
    if ((max_distance <= ((0i64) as f64)) || {
        let __needle = government;
        let __container = &((0i64..7i64).collect::<Vec<i64>>());
        !__container.contains(&__needle)
    }) {
        return Err("Invalid map size or government corruption type"
            .to_string()
            .into());
    }
    if (government == 5i64) {
        distance = rt::float_true_div(max_distance, ((4i64) as f64))?;
        rank = rt::int_floor_div(city_count, 2i64)?;
    }
    let mut government_factor: f64 = rt::at(
        &(vec![
            ((0.75f64, 1i64, 1i64, 1.5f64, 1i64, 1i64, 0i64)).0 as f64,
            ((0.75f64, 1i64, 1i64, 1.5f64, 1i64, 1i64, 0i64)).1 as f64,
            ((0.75f64, 1i64, 1i64, 1.5f64, 1i64, 1i64, 0i64)).2 as f64,
            ((0.75f64, 1i64, 1i64, 1.5f64, 1i64, 1i64, 0i64)).3 as f64,
            ((0.75f64, 1i64, 1i64, 1.5f64, 1i64, 1i64, 0i64)).4 as f64,
            ((0.75f64, 1i64, 1i64, 1.5f64, 1i64, 1i64, 0i64)).5 as f64,
            ((0.75f64, 1i64, 1i64, 1.5f64, 1i64, 1i64, 0i64)).6 as f64,
        ]),
        government,
    )?;
    let mut distance_part: f64 = rt::float_true_div(
        rt::finite(
            (0.5f64).powf(((reducers) as f64))
                * (rt::finite(rt::finite(government_factor * 1.25f64)? * distance)?)
                    .min(max_distance),
        )?,
        max_distance,
    )?;
    let mut optimum: f64 = (1.0f64).max(rt::finite(
        ((adjusted_optimum) as f64) + rt::finite(0.25f64 * ((reducers) as f64))?,
    )?);
    let mut rank_part: f64 = (if (((rank) as f64) < optimum) {
        rt::float_true_div(((rank) as f64), rt::finite(((2i64) as f64) * optimum)?)?
    } else {
        rt::float_true_div(
            rt::finite((((2i64).checked_mul(rank).ok_or("integer overflow")?) as f64) - optimum)?,
            rt::finite(((2i64) as f64) * optimum)?,
        )?
    });
    let mut maximum: f64 = (0.0f64).max(rt::finite(
        0.9f64
            - rt::finite(
                rt::finite(0.1f64 * ((reducers) as f64))?
                    + rt::finite(0.7f64 * ((wonders) as f64))?,
            )?,
    )?);
    Ok((maximum).min((0.0f64).max(rt::finite(distance_part + rank_part)?)))
}

// Python: openciv3/corruption.py:23
pub(crate) fn adjusted_optimal_cities(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    government: &Option<i64>,
) -> rt::Result<i64> {
    let mut size: Option<crate::openciv3::world_size::WorldSize> =
        (&(game).scenario).world_size.clone();
    if (size).is_none() {
        return Err("Adjusted city limit requires world-size rules"
            .to_string()
            .into());
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut index: i64 = (if (government).is_none() {
        ({
            let __source = &(game).players;
            let __key = owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .government
    } else {
        (*((*government).clone()).as_ref().ok_or("expected a value")?).clone()
    });
    let mut corruption: i64 = ({
        let __source = &(rules).governments;
        let __key = index;
        &__source[rt::index(__source.len(), __key)?]
    })
    .corruption;
    if {
        let __needle = corruption;
        let __container = &((0i64..7i64).collect::<Vec<i64>>());
        !__container.contains(&__needle)
    } {
        return Err("Invalid government corruption type".to_string().into());
    }
    let mut wonders: i64 = ({
        let mut __comprehension_result_631: Vec<bool> = Vec::new();
        let __comprehension_source_629 = ((game).cities.clone());
        for city in __comprehension_source_629.iter().cloned() {
            if ((city).owner == owner) {
                let __comprehension_source_630 = ((city).buildings.clone());
                for item in __comprehension_source_630.iter().cloned() {
                    __comprehension_result_631.push(
                        (({
                            let __source = &(rules).buildings;
                            let __key = (item).building;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .effects
                            & 8796093022208i64)
                            != 0,
                    );
                }
            }
        }
        __comprehension_result_631
    })
    .into_iter()
    .map(|value| value as i64)
    .sum::<i64>();
    let mut factor: f64 = rt::at(
        &(vec![
            ((0.1f64, 0.1f64, 0i64, 0i64, 0i64, 2i64, 0i64)).0 as f64,
            ((0.1f64, 0.1f64, 0i64, 0i64, 0i64, 2i64, 0i64)).1 as f64,
            ((0.1f64, 0.1f64, 0i64, 0i64, 0i64, 2i64, 0i64)).2 as f64,
            ((0.1f64, 0.1f64, 0i64, 0i64, 0i64, 2i64, 0i64)).3 as f64,
            ((0.1f64, 0.1f64, 0i64, 0i64, 0i64, 2i64, 0i64)).4 as f64,
            ((0.1f64, 0.1f64, 0i64, 0i64, 0i64, 2i64, 0i64)).5 as f64,
            ((0.1f64, 0.1f64, 0i64, 0i64, 0i64, 2i64, 0i64)).6 as f64,
        ]),
        corruption,
    )?;
    let mut wonder_factor: f64 = (if (corruption == 5i64) {
        3.0f64
    } else {
        0.375f64
    });
    rt::int_float(rt::finite(
        rt::int_true_div(
            (((*(size).as_ref().ok_or("expected a value")?).clone()).optimal_cities)
                .checked_mul(
                    ({
                        let __source = &(&(game).scenario).difficulties;
                        let __key = (game).difficulty;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .optimal_cities_percent,
                )
                .ok_or("integer overflow")?,
            100i64,
        )? * rt::finite(
            rt::finite(((1i64) as f64) + factor)? + rt::finite(wonder_factor * ((wonders) as f64))?,
        )?,
    )?)
}

// Python: openciv3/corruption.py:41
pub(crate) fn corruption_levels(
    game: &crate::openciv3::game_state::GameState,
) -> rt::Result<indexmap::IndexMap<i64, f64>> {
    let mut size: Option<crate::openciv3::world_size::WorldSize> =
        (&(game).scenario).world_size.clone();
    if (size).is_none() {
        return Err("Corruption calculation requires selected world-size rules"
            .to_string()
            .into());
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut result: indexmap::IndexMap<i64, f64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut player in (&(game).players).iter() {
        let mut cities: Vec<crate::openciv3::cities::City> = {
            let mut __comprehension_result_633: Vec<crate::openciv3::cities::City> = Vec::new();
            let __comprehension_source_632 = ((game).cities.clone());
            for city in __comprehension_source_632.iter().cloned() {
                if ((city).owner == (player).civilization) {
                    __comprehension_result_633.push(city.clone());
                }
            }
            __comprehension_result_633
        };
        if !(((cities).len() as i64) != 0i64) {
            continue;
        }
        let mut government: i64 = ({
            let __source = &(rules).governments;
            let __key = (player).government;
            &__source[rt::index(__source.len(), __key)?]
        })
        .corruption;
        if {
            let __needle = government;
            let __container = &((0i64..7i64).collect::<Vec<i64>>());
            !__container.contains(&__needle)
        } {
            return Err("Invalid government corruption type".to_string().into());
        }

        let mut capital: crate::openciv3::cities::City = {
            let __find_source_634 = cities.clone();
            let mut __find_result_634: crate::openciv3::cities::City = rt::at(&cities, 0i64)?;
            for city in __find_source_634.iter().cloned() {
                if (city).capital {
                    __find_result_634 = city.clone();
                    break;
                }
            }
            __find_result_634
        };
        let mut palaces: Vec<crate::openciv3::cities::City> = {
            let mut __comprehension_result_636: Vec<crate::openciv3::cities::City> = Vec::new();
            let __comprehension_source_635 = (cities.clone());
            for city in __comprehension_source_635.iter().cloned() {
                if ((city).capital
                    || (corruption_levels__wonder_count(&cities, &rules, (city).id)?) != 0)
                {
                    __comprehension_result_636.push(city.clone());
                }
            }
            __comprehension_result_636
        };
        if !(({
            let mut __comprehension_result_638: Vec<bool> = Vec::new();
            let __comprehension_source_637 = (cities.clone());
            for city in __comprehension_source_637.iter().cloned() {
                __comprehension_result_638.push((city).capital);
            }
            __comprehension_result_638
        })
        .into_iter()
        .any(|__value| __value))
        {
            {
                palaces.push(rt::at(&cities, 0i64)?);
            };
        }
        let mut optimum: i64 = adjusted_optimal_cities(game, (player).civilization, &None)?;

        let mut ordered: Vec<crate::openciv3::cities::City> = {
            let mut __decorated: Vec<(i64, crate::openciv3::cities::City)> = Vec::new();
            for __item in (cities.clone()).into_iter() {
                let city = __item;
                let __key = {
                    corruption_levels__distance(
                        game,
                        &(((city).x, (city).y)),
                        &(((capital).x, (capital).y)),
                    )?
                };
                __decorated.push((__key, city));
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
        for mut for_target_68_8 in (ordered)
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>()
        {
            let (mut rank, mut city): (i64, crate::openciv3::cities::City) = for_target_68_8;
            let mut buildings: Vec<crate::openciv3::cities::CityBuilding> =
                crate::openciv3::building_effects::effective_buildings(
                    &city,
                    &(game).cities,
                    &(game).players,
                    &(game).world,
                    &rules,
                )?;
            let mut reducers: i64 = ({
                let mut __comprehension_result_640: Vec<bool> = Vec::new();
                let __comprehension_source_639 = (buildings.clone());
                for item in __comprehension_source_639.iter().cloned() {
                    __comprehension_result_640.push(
                        (({
                            let __source = &(rules).buildings;
                            let __key = (item).building;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .effects
                            & 256i64)
                            != 0,
                    );
                }
                __comprehension_result_640
            })
            .into_iter()
            .map(|value| value as i64)
            .sum::<i64>();
            let mut local_wonders: i64 = ({
                let mut __comprehension_result_642: Vec<bool> = Vec::new();
                let __comprehension_source_641 = (buildings.clone());
                for item in __comprehension_source_641.iter().cloned() {
                    __comprehension_result_642.push(
                        (({
                            let __source = &(rules).buildings;
                            let __key = (item).building;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .effects
                            & 8796093022208i64)
                            != 0,
                    );
                }
                __comprehension_result_642
            })
            .into_iter()
            .map(|value| value as i64)
            .sum::<i64>();
            let mut nearest: i64 = {
                let __values = &({
                    let mut __comprehension_result_644: Vec<i64> = Vec::new();
                    let __comprehension_source_643 = (palaces.clone());
                    for palace in __comprehension_source_643.iter().cloned() {
                        __comprehension_result_644.push(corruption_levels__distance(
                            game,
                            &(((city).x, (city).y)),
                            &(((palace).x, (palace).y)),
                        )?);
                    }
                    __comprehension_result_644
                });
                let mut __items = __values.iter();
                let mut __best = __items.next().ok_or("min() arg is an empty sequence")?;
                for __candidate in __items {
                    if __candidate < __best {
                        __best = __candidate;
                    }
                }
                (*__best).clone()
            };
            {
                let __value = corruption_fraction(
                    ((nearest) as f64),
                    ((rt::int_floor_div(
                        ((&(game).world).width)
                            .checked_add((&(game).world).height)
                            .ok_or("integer overflow")?,
                        4i64,
                    )?) as f64),
                    rank,
                    ((cities).len() as i64),
                    government,
                    optimum,
                    reducers,
                    local_wonders,
                )?;
                let __key = (city).id;
                result.insert(__key, __value);
            }
        }
    }
    Ok(result)
}

// Python: openciv3/corruption.py:54
pub(crate) fn corruption_levels__wonder_count(
    cities: &[crate::openciv3::cities::City],
    rules: &crate::openciv3::rules::RuleCatalog,
    mut city_id: i64,
) -> rt::Result<i64> {
    Ok(({
        let mut __comprehension_result_647: Vec<bool> = Vec::new();
        let __comprehension_source_645 = (cities.to_vec());
        for city in __comprehension_source_645.iter().cloned() {
            if ((city).id == city_id) {
                let __comprehension_source_646 = ((city).buildings.clone());
                for item in __comprehension_source_646.iter().cloned() {
                    __comprehension_result_647.push(
                        (({
                            let __source = &(rules).buildings;
                            let __key = (item).building;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .effects
                            & 8796093022208i64)
                            != 0,
                    );
                }
            }
        }
        __comprehension_result_647
    })
    .into_iter()
    .map(|value| value as i64)
    .sum::<i64>())
}

// Python: openciv3/corruption.py:62
pub(crate) fn corruption_levels__distance(
    game: &crate::openciv3::game_state::GameState,
    first: &(i64, i64),
    second: &(i64, i64),
) -> rt::Result<i64> {
    let (mut a, mut b): (
        Option<crate::openciv3::world::Tile>,
        Option<crate::openciv3::world::Tile>,
    ) = (
        {
            let __star_args_648: Vec<i64> = {
                let __tuple_value = &((*first).clone());
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_648.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &(game).world,
                rt::at(&__star_args_648, 0 as i64)?,
                rt::at(&__star_args_648, 1 as i64)?,
            )?
        },
        {
            let __star_args_649: Vec<i64> = {
                let __tuple_value = &((*second).clone());
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_649.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &(game).world,
                rt::at(&__star_args_649, 0 as i64)?,
                rt::at(&__star_args_649, 1 as i64)?,
            )?
        },
    );
    if ((a).is_none() || (b).is_none()) {
        return Err("Corruption city lies outside the map".to_string().into());
    }
    crate::strategy::grid::rank_distance(
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
            let __structural_value = (*(a).as_ref().ok_or("expected a value")?).clone();
            crate::strategy::grid::GridPoint {
                x: (__structural_value).x.clone(),
                y: (__structural_value).y.clone(),
            }
        }),
        &({
            let __structural_value = (*(b).as_ref().ok_or("expected a value")?).clone();
            crate::strategy::grid::GridPoint {
                x: (__structural_value).x.clone(),
                y: (__structural_value).y.clone(),
            }
        }),
    )
}
