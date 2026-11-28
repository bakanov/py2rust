use py2rust_service_runtime as rt;

// Python: openciv3/city_founding.py:21
pub(crate) fn can_found_city(
    game: &crate::openciv3::game_state::GameState,
    settler: &crate::openciv3::units::Unit,
) -> rt::Result<bool> {
    if ((&(settler).transported_by).is_some()
        || (!(({
            let mut __comprehension_result_867: Vec<bool> = Vec::new();
            let __comprehension_source_866 = ((game).units.clone());
            for unit in __comprehension_source_866.iter().cloned() {
                __comprehension_result_867.push(((unit).id == (settler).id));
            }
            __comprehension_result_867
        })
        .into_iter()
        .any(|__value| __value))
            || ({
                let __source = &(game).players;
                let __key = (settler).owner;
                &__source[rt::index(__source.len(), __key)?]
            })
            .defeated))
    {
        return Ok(false);
    }
    if !((({
        let __source = &(&(&(game).scenario).rules).units;
        let __key = (settler).prototype;
        &__source[rt::index(__source.len(), __key)?]
    })
    .orders
        & 4194304i64)
        != 0i64)
    {
        return Ok(false);
    }
    let mut tile: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (settler).x, (settler).y)?;
    if ((tile).is_none()
        || (!(({
            let __source = &(&(&(game).scenario).rules).terrains;
            let __key =
                ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).overlay_terrain;
            &__source[rt::index(__source.len(), __key)?]
        })
        .allow_cities)
            || (((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).overlays & 128i64)
                != 0))
    {
        return Ok(false);
    }
    let mut centers: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_869: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_868 = ((game).cities.clone());
        for city in __comprehension_source_868.iter().cloned() {
            __comprehension_result_869.insert(((city).x, (city).y));
        }
        __comprehension_result_869
    };
    Ok(({
        let __needle = (
            ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
            ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
        );
        let __container = &centers;
        !__container.contains(&__needle)
    } && !(({
        let mut __comprehension_result_871: Vec<bool> = Vec::new();
        let __comprehension_source_870 = (crate::openciv3::world::WorldMap__neighbors(
            &(game).world,
            &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?);
        for neighbor in __comprehension_source_870.iter().cloned() {
            __comprehension_result_871.push({
                let __needle = ((neighbor).x, (neighbor).y);
                let __container = &centers;
                __container.contains(&__needle)
            });
        }
        __comprehension_result_871
    })
    .into_iter()
    .any(|__value| __value))))
}

// Python: openciv3/city_founding.py:34
pub(crate) fn found_city(
    mut game: crate::openciv3::game_state::GameState,
    settler: &crate::openciv3::units::Unit,
    name: &str,
    mut rng: rt::Random,
) -> rt::Result<crate::openciv3::cities::City> {
    let (mut game, mut city): (
        crate::openciv3::game_state::GameState,
        crate::openciv3::cities::City,
    ) = {
        let __call_872_0 = game;
        let __call_872_1 = settler;
        let __call_872_2 = name;
        let __call_872_3 = rng.clone();
        found_city_state(__call_872_0, __call_872_1, __call_872_2, __call_872_3)
    }?;
    Ok(city)
}

// Python: openciv3/city_founding.py:39
pub(crate) fn found_city_state(
    mut game: crate::openciv3::game_state::GameState,
    settler: &crate::openciv3::units::Unit,
    name: &str,
    mut rng: rt::Random,
) -> rt::Result<(
    crate::openciv3::game_state::GameState,
    crate::openciv3::cities::City,
)> {
    if !(can_found_city(&game, settler)?) {
        return Err("Settler cannot found a city here".to_string().into());
    }
    if !(((rt::str_strip(name)).chars().count() as i64) != 0i64) {
        return Err("City name cannot be empty".to_string().into());
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut citizen: Option<i64> = {
        let __find_source_873 = ((rules).citizens.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>();
        let mut __find_result_873: Option<i64> = None;
        for (index, kind) in __find_source_873.iter().cloned() {
            if (kind).default_citizen {
                __find_result_873 = Some(index);
                break;
            }
        }
        __find_result_873
    };
    if (citizen).is_none() {
        return Err("City founding needs a default citizen type"
            .to_string()
            .into());
    }
    let mut tile: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (settler).x, (settler).y)?;
    if !((tile).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    let mut first: bool = !(({
        let mut __comprehension_result_875: Vec<bool> = Vec::new();
        let __comprehension_source_874 = ((game).cities.clone());
        for city in __comprehension_source_874.iter().cloned() {
            __comprehension_result_875.push(((city).owner == (settler).owner));
        }
        __comprehension_result_875
    })
    .into_iter()
    .any(|__value| __value));
    let mut city: crate::openciv3::cities::City = crate::openciv3::cities::City {
        id: crate::openciv3::game_state::GameState__allocate_city_id(game.clone())?,
        owner: (settler).owner,
        name: name.to_owned(),
        x: ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
        y: ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
        capital: first,
        walls: false,
        level: 1i64,
        border_level: 1i64,
        auto_name: false,
        producing_unit: None,
        culture: [((settler).owner, 0i64)]
            .into_iter()
            .collect::<indexmap::IndexMap<_, _>>(),
        residents: vec![],
        buildings: vec![],
        food_stored: 0i64,
        shields_stored: 0i64,
        pop_rush_unhappiness_turns: 0i64,
        disorder: false,
        producing_inflow: None,
        producing_building: None,
    };
    ((city).residents).push(crate::openciv3::cities::Resident {
        citizen_type: (*(citizen).as_ref().ok_or("expected a value")?).clone(),
        nationality: (settler).owner,
        city: (city).id,
        tile_worked: None,
        mood: 0i64,
    });
    if first {
        let mut palace: Option<i64> = {
            let __find_source_876 = ((rules).buildings.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>();
            let mut __find_result_876: Option<i64> = None;
            for (index, building) in __find_source_876.iter().cloned() {
                if (((building).effects & 1i64) != 0i64) {
                    __find_result_876 = Some(index);
                    break;
                }
            }
            __find_result_876
        };
        if (palace).is_some() {
            ((city).buildings).push(crate::openciv3::cities::CityBuilding {
                building: (*(palace).as_ref().ok_or("expected a value")?).clone(),
                built_by: (settler).owner,
                year: (game).year,
                total_culture: 0i64,
            });
        }
    }
    ((game).cities).push(city.clone());
    let mut foliage: bool = {
        let __needle = ({
            let __source = &(rules).terrains;
            let __key =
                ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).overlay_terrain;
            &__source[rt::index(__source.len(), __key)?]
        })
        .worker_job;
        let __container = &({
            let __tuple_value = &((5i64, 6i64, 7i64));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        __container.contains(&__needle)
    };
    let mut cleared: crate::openciv3::world::Tile = {
        let mut __replacement =
            ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).clone();
        __replacement.overlay_terrain = (if foliage {
            ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).base_terrain
        } else {
            ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).overlay_terrain
        });
        __replacement.overlays = (((*(tile.clone()).as_ref().ok_or("expected a value")?).clone())
            .overlays
            & (1i64 | 2i64));
        __replacement.ruin = 0i64;
        __replacement.installation_owner = None;
        __replacement
    };
    game.world = {
        let mut __replacement = ((game).world.clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_878: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_877 = ((&(game).world).tiles.clone());
            for other in __comprehension_source_877.iter().cloned() {
                __comprehension_result_878.push(
                    (if (Some(other.clone()) == tile.clone()) {
                        cleared.clone()
                    } else {
                        other.clone()
                    }),
                );
            }
            __comprehension_result_878
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    };
    game.world = crate::openciv3::city_roads::connect_city_roads(
        &(game).world,
        &(vec![city.clone()]),
        &(game).players,
        &rules,
    )?;
    game.scenario.world = Some((game).world.clone());
    for mut other in (&(game).cities).iter() {
        for mut resident in (&(other).residents).iter().cloned() {
            if ((resident).tile_worked.clone() == Some(((city).x, (city).y))) {
                resident.tile_worked = None;
            }
        }
    }
    game = crate::openciv3::city_culture::refresh_ownership_state(game)?;
    game.cities = crate::openciv3::citizen_allocation::allocate_citizens_result(
        &(game).scenario,
        (game).cities.clone(),
        &(game).players,
        &(game).ownership,
        None,
    )?;
    city = (&({
        let mut __comprehension_result_880: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_879 = ((game).cities.clone());
        for candidate in __comprehension_source_879.iter().cloned() {
            if ((candidate).id == (city).id) {
                __comprehension_result_880.push(candidate.clone());
            }
        }
        __comprehension_result_880
    }))
        .iter()
        .next()
        .cloned()
        .ok_or("StopIteration")?;
    let mut workers: std::collections::BTreeSet<i64> =
        crate::civ3_ai::production_ai::worker_production_types(&game)?;
    let mut corruption: f64 = (crate::openciv3::corruption::corruption_levels(&game)?)
        .get(&((city).id))
        .ok_or("missing dict key")?
        .clone();
    {
        let __call_881_0 = &game;
        let __call_881_1 = city.clone();
        let __call_881_2 = corruption;
        let __call_881_3 = &None;
        let __call_881_default_3 = None;
        let __call_881_default_4 = &None;
        crate::openciv3::citizen_moods::recalculate_moods(
            __call_881_0,
            __call_881_1,
            __call_881_2,
            __call_881_default_3,
            __call_881_default_4,
            __call_881_3,
        )
    }?;
    crate::civ3_ai::production_ai::ProductionChoice__apply(
        &({
            let __call_882_0 = &game;
            let __call_882_1 = &city;
            let __call_882_2 = corruption;
            let __call_882_3 = rng.clone();
            let __call_882_4 = &workers;
            let __call_882_default_5 = None;
            let __call_882_default_6 = None;
            crate::civ3_ai::production_ai::choose_production(
                __call_882_0,
                __call_882_1,
                __call_882_2,
                __call_882_3,
                __call_882_4,
                __call_882_default_5,
                __call_882_default_6,
            )
        }?),
        &city,
    )?;
    let (mut game, mut removal): (
        crate::openciv3::game_state::GameState,
        crate::openciv3::unit_lifecycle::RemovalResult,
    ) = crate::openciv3::unit_lifecycle::remove_unit_state(&game, settler)?;
    Ok((game, city))
}
