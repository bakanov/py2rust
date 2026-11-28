use py2rust_service_runtime as rt;

// Python: openciv3/city_growth.py:16
pub(crate) fn can_grow(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut hydro: Option<crate::openciv3::hydrology::Hydrology>,
    mut population: i64,
) -> rt::Result<bool> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut limits: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(rules).global_rules, 0i64)?;
    if ((crate::openciv3::cities::City__size(city)?)
        .checked_add(population)
        .ok_or("integer overflow")?
        <= (limits).maximum_level1_city_size)
    {
        return Ok(true);
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
    let mut known: std::collections::BTreeSet<i64> = ({
        let __source = &(game).players;
        let __key = (city).owner;
        &__source[rt::index(__source.len(), __key)?]
    })
    .known_technologies
    .clone();
    let mut buildings: Vec<crate::openciv3::building_rules::Building> = {
        let mut __comprehension_result_1000: Vec<crate::openciv3::building_rules::Building> =
            Vec::new();
        let __comprehension_source_999 = (crate::openciv3::building_effects::effective_buildings(
            city,
            &(game).cities,
            &(game).players,
            &(game).world,
            &rules,
        )?);
        for item in __comprehension_source_999.iter().cloned() {
            __comprehension_result_1000.push(rt::at(&(rules).buildings, (item).building)?);
        }
        __comprehension_result_1000
    };
    let mut effects: i64 = 0i64;
    for mut building in buildings {
        if {
            let __needle = (building).rendered_obsolete_by;
            let __container = &known;
            !__container.contains(&__needle)
        } {
            effects = (effects | (building).effects);
        }
    }
    if !(crate::openciv3::hydrology::Hydrology__fresh_access(
        &((*(hydro).as_ref().ok_or("expected a value")?).clone()),
        &(game).world,
        &((*(center).as_ref().ok_or("expected a value")?).clone()),
    )? || (effects & (2048i64 | 4096i64)) != 0)
    {
        return Ok(false);
    }
    Ok((((crate::openciv3::cities::City__size(city)?)
        .checked_add(population)
        .ok_or("integer overflow")?
        <= (limits).maximum_level2_city_size)
        || (effects & 4096i64) != 0))
}

// Python: openciv3/city_growth.py:37
pub(crate) fn can_join_city(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    city: &crate::openciv3::cities::City,
) -> rt::Result<bool> {
    let mut prototype: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    Ok((((city).owner == (unit).owner)
        && (((prototype).orders & 8589934592i64) != 0
            && ((&(unit).transported_by).is_none()
                && (!(({
                    let mut __comprehension_result_1002: Vec<bool> = Vec::new();
                    let __comprehension_source_1001 = ((game).units.clone());
                    for u in __comprehension_source_1001.iter().cloned() {
                        __comprehension_result_1002
                            .push(((u).transported_by.clone() == Some((unit).id)));
                    }
                    __comprehension_result_1002
                })
                .into_iter()
                .any(|__value| __value))
                    && {
                        let __call_1003_0 = &((*game).clone());
                        let __call_1003_1 = &((*city).clone());
                        let __call_1003_2 = (1i64).max((prototype).population_cost);
                        let __call_1003_default_2 = None;
                        can_grow(
                            __call_1003_0,
                            __call_1003_1,
                            __call_1003_default_2,
                            __call_1003_2,
                        )
                    }?)))))
}

// Python: openciv3/city_growth.py:44
pub(crate) fn join_city(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut city: crate::openciv3::cities::City,
) -> rt::Result<()> {
    if ((((unit).x, (unit).y) != ((city).x, (city).y))
        || (!(can_join_city(game, unit, &city)?)
            || (!(({
                let mut __comprehension_result_1005: Vec<bool> = Vec::new();
                let __comprehension_source_1004 = ((game).units.clone());
                for other in __comprehension_source_1004.iter().cloned() {
                    __comprehension_result_1005.push(((other).id == (unit).id));
                }
                __comprehension_result_1005
            })
            .into_iter()
            .any(|__value| __value))
                || !(({
                    let mut __comprehension_result_1007: Vec<bool> = Vec::new();
                    let __comprehension_source_1006 = ((game).cities.clone());
                    for other in __comprehension_source_1006.iter().cloned() {
                        __comprehension_result_1007.push(((other).id == (city).id));
                    }
                    __comprehension_result_1007
                })
                .into_iter()
                .any(|__value| __value)))))
    {
        return Err("This unit cannot join a city here".to_string().into());
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut citizen: Option<i64> = {
        let __find_source_1008 = ((rules).citizens.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>();
        let mut __find_result_1008: Option<i64> = None;
        for (i, kind) in __find_source_1008.iter().cloned() {
            if (kind).default_citizen {
                __find_result_1008 = Some(i);
                break;
            }
        }
        __find_result_1008
    };
    if (citizen).is_none() {
        return Err("Joining requires a default citizen type".to_string().into());
    }
    let mut count: i64 = (1i64).max(
        ({
            let __source = &(rules).units;
            let __key = (unit).prototype;
            &__source[rt::index(__source.len(), __key)?]
        })
        .population_cost,
    );
    ((city).residents).extend({
        let mut __comprehension_result_1010: Vec<crate::openciv3::cities::Resident> = Vec::new();
        let __comprehension_source_1009 = ((0i64..count).collect::<Vec<i64>>());
        for _ in __comprehension_source_1009.iter().cloned() {
            __comprehension_result_1010.push(crate::openciv3::cities::Resident {
                citizen_type: (*(citizen.clone()).as_ref().ok_or("expected a value")?).clone(),
                nationality: (unit).nationality,
                city: (city).id,
                tile_worked: None,
                mood: 0i64,
            });
        }
        __comprehension_result_1010
    });
    crate::openciv3::citizen_allocation::allocate_citizens(
        &(game).scenario,
        &(game).cities,
        &(game).players,
        &(game).ownership,
        &None,
    )?;
    crate::openciv3::unit_lifecycle::remove_unit(game, unit)?;
    {
        let __call_1011_0 = &((*game).clone());
        let __call_1011_1 = city.clone();
        let __call_1011_2 = (crate::openciv3::corruption::corruption_levels(game)?)
            .get(&((city).id))
            .ok_or("missing dict key")?
            .clone();
        let __call_1011_3 = &None;
        let __call_1011_default_3 = None;
        let __call_1011_default_4 = &None;
        crate::openciv3::citizen_moods::recalculate_moods(
            __call_1011_0,
            __call_1011_1,
            __call_1011_2,
            __call_1011_default_3,
            __call_1011_default_4,
            __call_1011_3,
        )
    }?;
    Ok(())
}

// Python: openciv3/city_growth.py:60
pub(crate) fn advance_city_growth(
    game: &crate::openciv3::game_state::GameState,
    mut city: crate::openciv3::cities::City,
    hydro: &Option<crate::openciv3::hydrology::Hydrology>,
) -> rt::Result<i64> {
    let (mut city, mut change): (crate::openciv3::cities::City, i64) =
        advance_city_growth_result((*game).clone(), city, (*hydro).clone())?;
    Ok(change)
}

/// Apply food once and return population change (-1, 0, or 1).
///
/// Refresh moods after assigning the new citizen. The round mood phase still
/// controls whether the city enters disorder.
// Python: openciv3/city_growth.py:65
pub(crate) fn advance_city_growth_result(
    mut game: crate::openciv3::game_state::GameState,
    mut city: crate::openciv3::cities::City,
    mut hydro: Option<crate::openciv3::hydrology::Hydrology>,
) -> rt::Result<(crate::openciv3::cities::City, i64)> {
    hydro = (if (hydro).is_some() {
        hydro.clone()
    } else {
        Some(crate::openciv3::hydrology::Hydrology__from_world(
            &(game).world,
        )?)
    });
    let mut food: crate::openciv3::city_economy::CityFood =
        crate::openciv3::city_economy::city_food(&game, &city, &hydro)?;
    city.food_stored = (((city).food_stored)
        .checked_add((food).surplus)
        .ok_or("integer overflow")?)
    .min((food).food_box);
    if ((city).food_stored < 0i64) {
        city.food_stored = 0i64;
        if (crate::openciv3::cities::City__size(&city)? == 0i64) {
            return Ok((city, 0i64));
        }
        {
            let __index = rt::index(((city).residents).len(), -1i64)?;
            ((city).residents).remove(__index)
        };
        return Ok((city, (1i64).checked_neg().ok_or("integer overflow")?));
    }
    if (((city).food_stored < (food).food_box) || !(can_grow(&game, &city, hydro.clone(), 1i64)?)) {
        return Ok((city, 0i64));
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut default: Option<i64> = {
        let __find_source_1012 = ((rules).citizens.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>();
        let mut __find_result_1012: Option<i64> = None;
        for (index, citizen) in __find_source_1012.iter().cloned() {
            if (citizen).default_citizen {
                __find_result_1012 = Some(index);
                break;
            }
        }
        __find_result_1012
    };
    if (default).is_none() {
        return Err("City growth needs a default citizen type"
            .to_string()
            .into());
    }
    let mut granary: bool = ({
        let mut __comprehension_result_1014: Vec<i64> = Vec::new();
        let __comprehension_source_1013 = (crate::openciv3::building_effects::effective_buildings(
            &city,
            &(game).cities,
            &(game).players,
            &(game).world,
            &rules,
        )?);
        for item in __comprehension_source_1013.iter().cloned() {
            __comprehension_result_1014.push(
                (({
                    let __source = &(rules).buildings;
                    let __key = (item).building;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .effects
                    & 512i64),
            );
        }
        __comprehension_result_1014
    })
    .into_iter()
    .any(|__value| __value != 0);
    ((city).residents).push(crate::openciv3::cities::Resident {
        citizen_type: (*(default).as_ref().ok_or("expected a value")?).clone(),
        nationality: (city).owner,
        city: (city).id,
        tile_worked: None,
        mood: 0i64,
    });
    let mut city_index: i64 = (&({
        let mut __comprehension_result_1016: Vec<i64> = Vec::new();
        let __comprehension_source_1015 = (((game).cities.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>());
        for (index, candidate) in __comprehension_source_1015.iter().cloned() {
            if ((candidate).id == (city).id) {
                __comprehension_result_1016.push(index);
            }
        }
        __comprehension_result_1016
    }))
        .iter()
        .next()
        .cloned()
        .ok_or("StopIteration")?;
    {
        let __index = rt::index(game.cities.len(), city_index)?;
        game.cities[__index] = city.clone();
    }
    game.cities = crate::openciv3::citizen_allocation::allocate_citizens_result(
        &(game).scenario,
        (game).cities.clone(),
        &(game).players,
        &(game).ownership,
        None,
    )?;
    city = (&({
        let mut __comprehension_result_1018: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_1017 = ((game).cities.clone());
        for candidate in __comprehension_source_1017.iter().cloned() {
            if ((candidate).id == (city).id) {
                __comprehension_result_1018.push(candidate.clone());
            }
        }
        __comprehension_result_1018
    }))
        .iter()
        .next()
        .cloned()
        .ok_or("StopIteration")?;
    {
        let __call_1019_0 = &(game.clone());
        let __call_1019_1 = city.clone();
        let __call_1019_2 = (crate::openciv3::corruption::corruption_levels(&game)?)
            .get(&((city).id))
            .ok_or("missing dict key")?
            .clone();
        let __call_1019_3 = &hydro;
        let __call_1019_4 = &None;
        let __call_1019_default_3 = None;
        crate::openciv3::citizen_moods::recalculate_moods(
            __call_1019_0,
            __call_1019_1,
            __call_1019_2,
            __call_1019_default_3,
            __call_1019_3,
            __call_1019_4,
        )
    }?;
    city.food_stored = (if granary {
        rt::int_floor_div((city).food_stored, 2i64)?
    } else {
        0i64
    });
    Ok((city, 1i64))
}
