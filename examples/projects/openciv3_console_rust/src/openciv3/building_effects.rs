use py2rust_service_runtime as rt;

// Python: openciv3/building_effects.py:12
pub(crate) fn effective_buildings(
    city: &crate::openciv3::cities::City,
    cities: &[crate::openciv3::cities::City],
    players: &[crate::openciv3::players::Player],
    world: &crate::openciv3::world::WorldMap,
    rules: &crate::openciv3::rules::RuleCatalog,
) -> rt::Result<Vec<crate::openciv3::cities::CityBuilding>> {
    let mut result: Vec<crate::openciv3::cities::CityBuilding> =
        (&(city).buildings).iter().cloned().collect::<Vec<_>>();
    let mut constructed: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_262: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_261 = ((city).buildings.clone());
        for item in __comprehension_source_261.iter().cloned() {
            __comprehension_result_262.insert((item).building);
        }
        __comprehension_result_262
    };
    let mut target_tile: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(world, (city).x, (city).y)?;
    if (target_tile).is_none() {
        return Err("City is outside the map".to_string().into());
    }
    for mut source in (cities).iter() {
        if ((source).owner != (city).owner) {
            continue;
        }
        let mut source_tile: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(world, (source).x, (source).y)?;
        if (source_tile).is_none() {
            return Err("Wonder city is outside the map".to_string().into());
        }
        for mut item in (&(source).buildings).iter() {
            let mut building: crate::openciv3::building_rules::Building =
                rt::at(&(rules).buildings, (item).building)?;
            if !(((building).effects & 268435456i64) != 0i64) {
                continue;
            }
            if {
                let __needle = (building).rendered_obsolete_by;
                let __container = &({
                    let __source = players;
                    let __key = (city).owner;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .known_technologies;
                __container.contains(&__needle)
            } {
                continue;
            }
            let mut grants: Vec<i64> = vec![(building).gain_in_every_city];
            if (((*(source_tile.clone()).as_ref().ok_or("expected a value")?).clone()).continent
                == ((*(target_tile.clone()).as_ref().ok_or("expected a value")?).clone()).continent)
            {
                {
                    grants.push((building).gain_in_every_city_on_continent);
                };
            }
            for mut granted in grants {
                if ((granted < 0i64) || {
                    let __needle = granted;
                    let __container = &constructed;
                    __container.contains(&__needle)
                }) {
                    continue;
                }
                if (granted >= ((&(rules).buildings).len() as i64)) {
                    return Err({
                        let __separator = &(String::new());
                        (&(vec![
                            "Wonder grants invalid building ".to_string(),
                            (granted).to_string(),
                        ]))
                            .join(__separator)
                    }
                    .into());
                }
                {
                    result.push(crate::openciv3::cities::CityBuilding {
                        building: granted,
                        built_by: (item).built_by,
                        year: (item).year,
                        total_culture: 0i64,
                    });
                };
            }
        }
    }
    Ok(result)
}

// Python: openciv3/building_effects.py:48
pub(crate) fn spaceship_requirements(
    rules: &crate::openciv3::rules::RuleCatalog,
) -> rt::Result<indexmap::IndexMap<i64, i64>> {
    let mut configured: Vec<i64> = (if (((&(rules).global_rules).len() as i64) != 0i64) {
        ({
            let __source = &(rules).global_rules;
            let __key = 0i64;
            &__source[rt::index(__source.len(), __key)?]
        })
        .spaceship_parts
        .clone()
    } else {
        vec![]
    });
    if (((configured).len() as i64) != 0i64) {
        return Ok({
            let mut __comprehension_result_264: indexmap::IndexMap<i64, i64> =
                indexmap::IndexMap::new();
            let __comprehension_source_263 = ((configured.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>());
            for (part, count) in __comprehension_source_263.iter().cloned() {
                if (count > 0i64) {
                    {
                        let (__key, __value) = (part, count);
                        __comprehension_result_264.insert(__key, __value);
                    }
                }
            }
            __comprehension_result_264
        });
    }
    Ok({
        let mut __comprehension_result_266: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_265 = ((rules).buildings.clone());
        for building in __comprehension_source_265.iter().cloned() {
            if ((building).spaceship_part >= 0i64) {
                {
                    let (__key, __value) = ((building).spaceship_part, 1i64);
                    __comprehension_result_266.insert(__key, __value);
                }
            }
        }
        __comprehension_result_266
    })
}

// Python: openciv3/building_effects.py:56
pub(crate) fn spaceship_parts_built(
    rules: &crate::openciv3::rules::RuleCatalog,
    cities: &[crate::openciv3::cities::City],
) -> rt::Result<indexmap::IndexMap<i64, i64>> {
    Ok({
        let mut __counts: indexmap::IndexMap<i64, i64> = indexmap::IndexMap::new();
        for __item in ({
            let mut __comprehension_result_269: Vec<i64> = Vec::new();
            let mut part: i64;
            let __comprehension_source_267 = (cities.to_vec());
            for city in __comprehension_source_267.iter().cloned() {
                let __comprehension_source_268 = ((city).buildings.clone());
                for item in __comprehension_source_268.iter().cloned() {
                    if ({
                        part = ({
                            let __source = &(rules).buildings;
                            let __key = (item).building;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .spaceship_part;
                        part
                    } >= 0i64)
                    {
                        __comprehension_result_269.push(part);
                    }
                }
            }
            __comprehension_result_269
        })
        .into_iter()
        {
            *__counts.entry(__item).or_insert(0) += 1;
        }
        __counts
    })
}

/// Building culture, including wonder grants and millennial age doubling.
///
/// Wealth has no culture yield. Add custom culture inflows here when their
/// configurable behavior registration is migrated.
// Python: openciv3/building_effects.py:61
pub(crate) fn culture_rates(
    cities: &[crate::openciv3::cities::City],
    players: &[crate::openciv3::players::Player],
    world: &crate::openciv3::world::WorldMap,
    rules: &crate::openciv3::rules::RuleCatalog,
    mut year: i64,
) -> rt::Result<indexmap::IndexMap<i64, i64>> {
    Ok({
        let mut __comprehension_result_273: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_270 = (cities.to_vec());
        for city in __comprehension_source_270.iter().cloned() {
            {
                let (__key, __value) = (
                    (city).id,
                    ({
                        let mut __comprehension_result_272: Vec<i64> = Vec::new();
                        let __comprehension_source_271 =
                            (effective_buildings(&city, cities, players, world, rules)?);
                        for item in __comprehension_source_271.iter().cloned() {
                            __comprehension_result_272.push(
                                (({
                                    let __source = &(rules).buildings;
                                    let __key = (item).building;
                                    &__source[rt::index(__source.len(), __key)?]
                                })
                                .culture)
                                    .checked_mul(rt::int_lshift(
                                        1i64,
                                        (0i64).max(rt::int_floor_div(
                                            (year)
                                                .checked_sub((item).year)
                                                .ok_or("integer overflow")?,
                                            1000i64,
                                        )?),
                                    )?)
                                    .ok_or("integer overflow")?,
                            );
                        }
                        __comprehension_result_272
                    })
                    .into_iter()
                    .sum::<i64>(),
                );
                __comprehension_result_273.insert(__key, __value);
            }
        }
        __comprehension_result_273
    })
}
