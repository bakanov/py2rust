use py2rust_service_runtime as rt;

// Python: openciv3/city_culture.py:13
pub(crate) fn refresh_ownership(game: &crate::openciv3::game_state::GameState) -> rt::Result<()> {
    refresh_ownership_state((*game).clone())?;
    Ok(())
}

// Python: openciv3/city_culture.py:18
pub(crate) fn refresh_ownership_state(
    mut game: crate::openciv3::game_state::GameState,
) -> rt::Result<crate::openciv3::game_state::GameState> {
    let mut rates: indexmap::IndexMap<i64, i64> = crate::openciv3::building_effects::culture_rates(
        &(game).cities,
        &(game).players,
        &(game).world,
        &(&(game).scenario).rules,
        (game).year,
    )?;
    game.ownership = crate::openciv3::borders::calculate_ownership(
        &(game).world,
        &(game).cities,
        13i64,
        &rates,
    )?;
    let mut owners: indexmap::IndexMap<i64, i64> = {
        let mut __comprehension_result_884: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_883 = ((game).cities.clone());
        for city in __comprehension_source_883.iter().cloned() {
            {
                let (__key, __value) = ((city).id, (city).owner);
                __comprehension_result_884.insert(__key, __value);
            }
        }
        __comprehension_result_884
    };
    let mut installations: i64 = ((2147483648i64 | 1073741824i64) | 536870912i64);
    let mut airfield_jobs: Vec<crate::openciv3::rules::WorkerJob> = {
        let mut __comprehension_result_886: Vec<crate::openciv3::rules::WorkerJob> = Vec::new();
        let __comprehension_source_885 = ((&(&(game).scenario).rules).worker_jobs.clone());
        for job in __comprehension_source_885.iter().cloned() {
            if (((&(job).order).replace(" ", "")).as_str() == "BuildAirfield") {
                __comprehension_result_886.push(job.clone());
            }
        }
        __comprehension_result_886
    };
    let mut changed: indexmap::IndexMap<(i64, i64), crate::openciv3::world::Tile> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut for_target_26_4 in ((game).ownership.clone())
        .iter()
        .map(|(__key, __value)| (__key.clone(), __value.clone()))
        .collect::<Vec<_>>()
    {
        let (mut point, mut city_id): ((i64, i64), i64) = for_target_26_4;
        let mut tile: Option<crate::openciv3::world::Tile> = {
            let __star_args_887: Vec<i64> = {
                let __tuple_value = &(point.clone());
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_887.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &(game).world,
                rt::at(&__star_args_887, 0 as i64)?,
                rt::at(&__star_args_887, 1 as i64)?,
            )?
        };
        let mut owner: i64 = (owners).get(&(city_id)).ok_or("missing dict key")?.clone();
        if ((tile).is_none()
            || (!((((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).overlays
                & installations)
                != 0i64)
                || ((((*(tile.clone()).as_ref().ok_or("expected a value")?).clone())
                    .installation_owner
                    .clone())
                .is_none()
                    || ((*(((*(tile.clone()).as_ref().ok_or("expected a value")?).clone())
                        .installation_owner
                        .clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                    .clone())
                        == ((((), owner)).1))))
        {
            continue;
        }
        let mut retain_airfield: bool =
            ((((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).overlays
                & 536870912i64)
                != 0
                && ({
                    let mut __comprehension_result_889: Vec<bool> = Vec::new();
                    let __comprehension_source_888 = (airfield_jobs.clone());
                    for job in __comprehension_source_888.iter().cloned() {
                        __comprehension_result_889.push(
                            (((job).prerequisite < 0i64) || {
                                let __needle = (job).prerequisite;
                                let __container = &({
                                    let __source = &(game).players;
                                    let __key = owner;
                                    &__source[rt::index(__source.len(), __key)?]
                                })
                                .known_technologies;
                                __container.contains(&__needle)
                            }),
                        );
                    }
                    __comprehension_result_889
                })
                .into_iter()
                .any(|__value| __value));
        let mut overlays: i64 = (((*(tile.clone()).as_ref().ok_or("expected a value")?).clone())
            .overlays
            & !(installations));
        if retain_airfield {
            overlays = (overlays | 536870912i64);
        }
        {
            let __value = {
                let mut __replacement =
                    ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).clone();
                __replacement.overlays = overlays;
                __replacement.installation_owner =
                    (if retain_airfield { Some(owner) } else { None });
                __replacement
            };
            let __key = point.clone();
            changed.insert(__key, __value);
        }
    }
    if (((changed).len() as i64) != 0i64) {
        game.world = {
            let mut __replacement = ((game).world.clone()).clone();
            __replacement.tiles = ({
                let mut __comprehension_result_891: Vec<crate::openciv3::world::Tile> = Vec::new();
                let __comprehension_source_890 = ((&(game).world).tiles.clone());
                for tile in __comprehension_source_890.iter().cloned() {
                    __comprehension_result_891.push({
                        let __key = ((tile).x, (tile).y);
                        let __default = tile.clone();
                        changed.get(&__key).cloned().unwrap_or(__default)
                    });
                }
                __comprehension_result_891
            })
            .iter()
            .cloned()
            .collect::<Vec<_>>();
            __replacement
        };
        game.scenario.world = Some((game).world.clone());
    }
    let mut displaced: bool = false;
    for mut city in (&(game).cities).iter() {
        for mut resident in (&(city).residents).iter().cloned() {
            if (&(resident).tile_worked).is_none() {
                continue;
            }
            let mut owner_city: Option<i64> = ((game).ownership.clone())
                .get(
                    &((*((resident).tile_worked.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone()),
                )
                .cloned();
            if ((owner_city).is_none()
                || ((owners)
                    .get(&((*(owner_city.clone()).as_ref().ok_or("expected a value")?).clone()))
                    .ok_or("missing dict key")?
                    .clone()
                    != (city).owner))
            {
                resident.tile_worked = None;
                displaced = true;
            }
        }
    }
    if displaced {
        crate::openciv3::citizen_allocation::allocate_citizens(
            &(game).scenario,
            &(game).cities,
            &(game).players,
            &(game).ownership,
            &None,
        )?;
    }
    game.visibility = crate::openciv3::visibility::update_visibility(
        &(game).world,
        &(game).cities,
        &(game).units,
        &(&(game).scenario).rules,
        &(game).ownership,
        (game).visibility.clone(),
        None,
        &None,
    )?;
    Ok(game)
}

/// Accumulate owner culture and return whether the border level changed.
///
/// Run before growth so newborn citizens can use newly acquired territory.
/// Trade networks are fresh snapshots, so subsequent queries see new ownership.
// Python: openciv3/city_culture.py:61
pub(crate) fn advance_city_culture(
    game: &crate::openciv3::game_state::GameState,
    mut city: crate::openciv3::cities::City,
) -> rt::Result<bool> {
    let mut before: i64 = crate::openciv3::borders::expansion_level(&city)?;
    let mut rates: indexmap::IndexMap<i64, i64> = crate::openciv3::building_effects::culture_rates(
        &(game).cities,
        &(game).players,
        &(game).world,
        &(&(game).scenario).rules,
        (game).year,
    )?;
    for mut item in (&(city).buildings).iter().cloned() {
        item.total_culture = ((item).total_culture)
            .checked_add(
                ({
                    let __source = &(&(&(game).scenario).rules).buildings;
                    let __key = (item).building;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .culture,
            )
            .ok_or("integer overflow")?;
    }
    city.culture.insert(
        (city).owner,
        ({
            let __mapping = &(city).culture;
            let __key = (city).owner;
            let __default = 0i64;
            __mapping.get(&__key).cloned().unwrap_or(__default)
        })
        .checked_add((rates).get(&((city).id)).ok_or("missing dict key")?.clone())
        .ok_or("integer overflow")?,
    );
    let mut expanded: bool = (before != crate::openciv3::borders::expansion_level(&city)?);
    if expanded {
        refresh_ownership(game)?;
    }
    Ok(expanded)
}
