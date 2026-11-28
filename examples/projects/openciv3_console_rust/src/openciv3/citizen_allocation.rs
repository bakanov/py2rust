use py2rust_service_runtime as rt;

// Python: openciv3/citizen_allocation.py:15
pub(crate) fn allocate_citizens(
    definition: &crate::openciv3::scenario_model::ScenarioDefinition,
    cities: &[crate::openciv3::cities::City],
    players: &[crate::openciv3::players::Player],
    ownership: &indexmap::IndexMap<(i64, i64), i64>,
    workable_rank: &Option<i64>,
) -> rt::Result<()> {
    {
        let __call_286_0 = definition;
        let __call_286_1 = cities.to_vec();
        let __call_286_2 = players;
        let __call_286_3 = ownership;
        let __call_286_4 = (*workable_rank).clone();
        allocate_citizens_result(
            __call_286_0,
            __call_286_1,
            __call_286_2,
            __call_286_3,
            __call_286_4,
        )
    }?;
    Ok(())
}

// Python: openciv3/citizen_allocation.py:21
pub(crate) fn allocate_citizens_result(
    definition: &crate::openciv3::scenario_model::ScenarioDefinition,
    mut cities: Vec<crate::openciv3::cities::City>,
    players: &[crate::openciv3::players::Player],
    ownership: &indexmap::IndexMap<(i64, i64), i64>,
    mut workable_rank: Option<i64>,
) -> rt::Result<Vec<crate::openciv3::cities::City>> {
    let mut world: Option<crate::openciv3::world::WorldMap> = (definition).world.clone();
    if (world).is_none() {
        return Err("Citizen allocation requires a map".to_string().into());
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (definition).rules.clone();
    if (workable_rank).is_none() {
        workable_rank = Some(crate::openciv3::rules::RuleCatalog__workable_rank(&rules)?);
    }
    if !(((cities).len() as i64) != 0i64) {
        return Ok(cities);
    }
    let mut hydro: crate::openciv3::hydrology::Hydrology =
        crate::openciv3::hydrology::Hydrology__from_world(
            &((*(world.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?;
    let mut city_ids: indexmap::IndexMap<i64, crate::openciv3::cities::City> = {
        let mut __comprehension_result_288: indexmap::IndexMap<i64, crate::openciv3::cities::City> =
            indexmap::IndexMap::new();
        let __comprehension_source_287 = (cities.clone());
        for city in __comprehension_source_287.iter().cloned() {
            {
                let (__key, __value) = ((city).id, city.clone());
                __comprehension_result_288.insert(__key, __value);
            }
        }
        __comprehension_result_288
    };
    let mut centers: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_290: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_289 = (cities.clone());
        for city in __comprehension_source_289.iter().cloned() {
            __comprehension_result_290.insert(((city).x, (city).y));
        }
        __comprehension_result_290
    };
    let mut occupied: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_293: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_291 = (cities.clone());
        for city in __comprehension_source_291.iter().cloned() {
            let __comprehension_source_292 = ((city).residents.clone());
            for resident in __comprehension_source_292.iter().cloned() {
                if (&(resident).tile_worked).is_some() {
                    __comprehension_result_293.insert(
                        (*((resident).tile_worked.clone())
                            .as_ref()
                            .ok_or("expected a value")?)
                        .clone(),
                    );
                }
            }
        }
        __comprehension_result_293
    };
    for mut player in (players).iter() {
        let mut civilization: crate::openciv3::scenario_model::Civilization =
            rt::at(&(definition).civilizations, (player).civilization)?;
        let mut specialists: Vec<i64> = {
            let mut __comprehension_result_295: Vec<i64> = Vec::new();
            let __comprehension_source_294 = (((rules).citizens.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>());
            for (i, citizen) in __comprehension_source_294.iter().cloned() {
                if (!((citizen).default_citizen)
                    && (((citizen).prerequisite < 0i64) || {
                        let __needle = (citizen).prerequisite;
                        let __container = &(player).known_technologies;
                        __container.contains(&__needle)
                    }))
                {
                    __comprehension_result_295.push(i);
                }
            }
            __comprehension_result_295
        };
        for mut for_target_39_8 in (cities.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>()
        {
            let (mut city_index, mut city): (i64, crate::openciv3::cities::City) = for_target_39_8;
            if ((city).owner != (player).civilization) {
                continue;
            }
            let mut center: Option<crate::openciv3::world::Tile> =
                crate::openciv3::world::WorldMap__tile_at(
                    &((*(world.clone()).as_ref().ok_or("expected a value")?).clone()),
                    (city).x,
                    (city).y,
                )?;
            if (center).is_none() {
                return Err("City is outside the map".to_string().into());
            }
            let mut buildings: Vec<crate::openciv3::building_rules::Building> = {
                let mut __comprehension_result_297: Vec<crate::openciv3::building_rules::Building> =
                    Vec::new();
                let __comprehension_source_296 =
                    (crate::openciv3::building_effects::effective_buildings(
                        &city,
                        &cities,
                        players,
                        &((*(world.clone()).as_ref().ok_or("expected a value")?).clone()),
                        &rules,
                    )?);
                for item in __comprehension_source_296.iter().cloned() {
                    __comprehension_result_297.push(rt::at(&(rules).buildings, (item).building)?);
                }
                __comprehension_result_297
            };
            let mut food: i64 = ({
                let __call_298_0 =
                    &((*(center.clone()).as_ref().ok_or("expected a value")?).clone());
                let __call_298_1 = &((*player).clone());
                let __call_298_2 = &(Some(civilization.clone()));
                let __call_298_3 = &(rules.clone());
                let __call_298_4 = &(Some(city.clone()));
                let __call_298_5 = crate::openciv3::hydrology::Hydrology__fresh_access(
                    &hydro,
                    &((*(world.clone()).as_ref().ok_or("expected a value")?).clone()),
                    &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?;
                let __call_298_6 = crate::openciv3::hydrology::Hydrology__coastal(
                    &hydro,
                    &((*(world.clone()).as_ref().ok_or("expected a value")?).clone()),
                    &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?;
                let __call_298_7 = &(buildings.clone());
                let __call_298_8 = &(Some(
                    (crate::openciv3::hydrology::river_edges(
                        &((*(world.clone()).as_ref().ok_or("expected a value")?).clone()),
                        &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
                    )?) != 0,
                ));
                crate::openciv3::yields::tile_yield(
                    __call_298_0,
                    __call_298_1,
                    __call_298_2,
                    __call_298_3,
                    __call_298_4,
                    __call_298_5,
                    __call_298_6,
                    __call_298_7,
                    __call_298_8,
                )
            }?)
            .food;
            for mut resident in (&(city).residents).iter() {
                if (&(resident).tile_worked).is_some() {
                    let mut worked: Option<crate::openciv3::world::Tile> = {
                        let __star_args_299: Vec<i64> = {
                            let __tuple_value = &((*((resident).tile_worked.clone())
                                .as_ref()
                                .ok_or("expected a value")?)
                            .clone());
                            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                        };
                        if !(2..=2).contains(&__star_args_299.len()) {
                            return Err("wrong function argument count".into());
                        }
                        crate::openciv3::world::WorldMap__tile_at(
                            &((*(world.clone()).as_ref().ok_or("expected a value")?).clone()),
                            rt::at(&__star_args_299, 0 as i64)?,
                            rt::at(&__star_args_299, 1 as i64)?,
                        )?
                    };
                    if (worked).is_none() {
                        return Err("Resident is working an invalid tile".to_string().into());
                    }
                    food = (food)
                        .checked_add(
                            ({
                                let __call_300_0 =
                                    &((*(worked.clone()).as_ref().ok_or("expected a value")?)
                                        .clone());
                                let __call_300_1 = &((*player).clone());
                                let __call_300_2 = &(Some(civilization.clone()));
                                let __call_300_3 = &(rules.clone());
                                let __call_300_4 = &(buildings.clone());
                                let __call_300_5 = &(Some(
                                    (crate::openciv3::hydrology::river_edges(
                                        &((*(world.clone()).as_ref().ok_or("expected a value")?)
                                            .clone()),
                                        &((*(worked.clone())
                                            .as_ref()
                                            .ok_or("expected a value")?)
                                        .clone()),
                                    )?) != 0,
                                ));
                                let __call_300_default_4 = &None;
                                let __call_300_default_5 = false;
                                let __call_300_default_6 = false;
                                crate::openciv3::yields::tile_yield(
                                    __call_300_0,
                                    __call_300_1,
                                    __call_300_2,
                                    __call_300_3,
                                    __call_300_default_4,
                                    __call_300_default_5,
                                    __call_300_default_6,
                                    __call_300_4,
                                    __call_300_5,
                                )
                            }?)
                            .food,
                        )
                        .ok_or("integer overflow")?;
                }
            }
            let mut candidates: Vec<crate::openciv3::world::Tile> = {
                let mut __comprehension_result_302: Vec<crate::openciv3::world::Tile> = Vec::new();
                let mut point: (i64, i64);
                let __comprehension_source_301 = (crate::strategy::grid::within_rank(
                    &((*(world.clone()).as_ref().ok_or("expected a value")?).clone()),
                    &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
                    (*(workable_rank.clone()).as_ref().ok_or("expected a value")?).clone(),
                )?);
                for tile in __comprehension_source_301.iter().cloned() {
                    if ({
                        let __needle = {
                            point = ((tile).x, (tile).y);
                            point.clone()
                        };
                        let __container = &centers;
                        !__container.contains(&__needle)
                    } && ({
                        let __needle = point.clone();
                        let __container = ownership;
                        __container.contains_key(&__needle)
                    } && (((city_ids)
                        .get(
                            &((ownership)
                                .get(&(point.clone()))
                                .ok_or("missing dict key")?
                                .clone()),
                        )
                        .ok_or("missing dict key")?)
                    .owner
                        == (city).owner)))
                    {
                        __comprehension_result_302.push(tile.clone());
                    }
                }
                __comprehension_result_302
            };
            let mut updated_residents: Vec<crate::openciv3::cities::Resident> =
                (&(city).residents).iter().cloned().collect::<Vec<_>>();
            for mut for_target_60_12 in (updated_residents.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>()
            {
                let (mut resident_index, mut resident): (i64, crate::openciv3::cities::Resident) =
                    for_target_60_12;
                if ((&(resident).tile_worked).is_some()
                    || !(({
                        let __source = &(rules).citizens;
                        let __key = (resident).citizen_type;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .default_citizen))
                {
                    continue;
                }
                let mut target_food: i64 = (((crate::openciv3::cities::City__size(&city)?)
                    .checked_mul(crate::openciv3::rules::RuleCatalog__food_per_citizen(
                        &rules,
                    )?)
                    .ok_or("integer overflow")?)
                .checked_add(2i64)
                .ok_or("integer overflow")?)
                .checked_sub(food)
                .ok_or("integer overflow")?;
                let mut best: Option<crate::openciv3::world::Tile> = None;
                let mut best_score: f64 = 0.0f64;
                for mut tile in (candidates).iter() {
                    if {
                        let __needle = ((tile).x, (tile).y);
                        let __container = &occupied;
                        __container.contains(&__needle)
                    } {
                        continue;
                    }
                    let mut value: crate::civ::economy::Yield = {
                        let __call_303_0 = &((*tile).clone());
                        let __call_303_1 = &((*player).clone());
                        let __call_303_2 = &(Some(civilization.clone()));
                        let __call_303_3 = &(rules.clone());
                        let __call_303_4 = &(Some(
                            (crate::openciv3::hydrology::river_edges(
                                &((*(world.clone()).as_ref().ok_or("expected a value")?).clone()),
                                tile,
                            )?) != 0,
                        ));
                        let __call_303_default_4 = &None;
                        let __call_303_default_5 = false;
                        let __call_303_default_6 = false;
                        let __call_303_default_7 = &(vec![]);
                        crate::openciv3::yields::tile_yield(
                            __call_303_0,
                            __call_303_1,
                            __call_303_2,
                            __call_303_3,
                            __call_303_default_4,
                            __call_303_default_5,
                            __call_303_default_6,
                            __call_303_default_7,
                            __call_303_4,
                        )
                    }?;
                    let mut score: f64 =
                        crate::openciv3::yields::tile_assignment_score(&value, target_food)?;
                    if (score > best_score) {
                        (best, best_score) = (Some((*tile).clone()), score);
                    }
                }
                if (best).is_none() {
                    if !(((specialists).len() as i64) != 0i64) {
                        return Err({
                            let __separator = &(String::new());
                            (&(vec![
                                "City ".to_string(),
                                ((city).name.clone()).to_string(),
                                " has no available tile or unlocked specialist".to_string(),
                            ]))
                                .join(__separator)
                        }
                        .into());
                    }
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
                    food = (food)
                        .checked_add(
                            ({
                                let __call_304_0 =
                                    &((*(best.clone()).as_ref().ok_or("expected a value")?)
                                        .clone());
                                let __call_304_1 = &((*player).clone());
                                let __call_304_2 = &(Some(civilization.clone()));
                                let __call_304_3 = &(rules.clone());
                                let __call_304_4 = &(buildings.clone());
                                let __call_304_5 = &(Some(
                                    (crate::openciv3::hydrology::river_edges(
                                        &((*(world.clone()).as_ref().ok_or("expected a value")?)
                                            .clone()),
                                        &((*(best.clone()).as_ref().ok_or("expected a value")?)
                                            .clone()),
                                    )?) != 0,
                                ));
                                let __call_304_default_4 = &None;
                                let __call_304_default_5 = false;
                                let __call_304_default_6 = false;
                                crate::openciv3::yields::tile_yield(
                                    __call_304_0,
                                    __call_304_1,
                                    __call_304_2,
                                    __call_304_3,
                                    __call_304_default_4,
                                    __call_304_default_5,
                                    __call_304_default_6,
                                    __call_304_4,
                                    __call_304_5,
                                )
                            }?)
                            .food,
                        )
                        .ok_or("integer overflow")?;
                }
                {
                    let __value = resident.clone();
                    let __key = resident_index;
                    let __index = rt::index(updated_residents.len(), __key)?;
                    updated_residents[__index] = __value;
                }
            }
            {
                let __value = {
                    let mut __replacement = (city.clone()).clone();
                    __replacement.residents = updated_residents;
                    __replacement
                };
                let __key = city_index;
                let __index = rt::index(cities.len(), __key)?;
                cities[__index] = __value;
            }
        }
    }
    Ok(cities)
}
