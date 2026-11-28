use py2rust_service_runtime as rt;

// Python: openciv3/barbarian_spawning.py:18
pub(crate) fn select_barbarian_type(
    game: &crate::openciv3::game_state::GameState,
    camp: &crate::openciv3::world::Tile,
    mut rng: rt::Random,
) -> rt::Result<i64> {
    let mut rules: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(&(&(game).scenario).rules).global_rules, 0i64)?;
    if (((rules).barbarian_sea_unit_type >= 0i64)
        && (({
            let mut __comprehension_result_1116: Vec<bool> = Vec::new();
            let __comprehension_source_1115 =
                (crate::openciv3::world::WorldMap__neighbors(&(game).world, camp)?);
            for tile in __comprehension_source_1115.iter().cloned() {
                __comprehension_result_1116.push(crate::openciv3::hydrology::is_water(&tile)?);
            }
            __comprehension_result_1116
        })
        .into_iter()
        .any(|__value| __value)
            && (rt::random_randrange(&rng, 0i64, 100i64)? < 20i64)))
    {
        return Ok((rules).barbarian_sea_unit_type);
    }
    Ok((if (rt::random_randrange(&rng, 0i64, 100i64)? < 25i64) {
        (rules).advanced_barbarian_unit_type
    } else {
        (rules).basic_barbarian_unit_type
    }))
}

// Python: openciv3/barbarian_spawning.py:27
pub(crate) fn select_spawn_tile(
    game: &crate::openciv3::game_state::GameState,
    camp: &crate::openciv3::world::Tile,
    mut prototype: i64,
    hydro: &crate::openciv3::hydrology::Hydrology,
) -> rt::Result<Option<crate::openciv3::world::Tile>> {
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, prototype)?;
    if ((kind).domain != 1i64) {
        return Ok(Some((*camp).clone()));
    }
    let mut occupied: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_1118: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_1117 = ((game).units.clone());
        for unit in __comprehension_source_1117.iter().cloned() {
            if ((unit).owner != 0i64) {
                __comprehension_result_1118.insert(((unit).x, (unit).y));
            }
        }
        __comprehension_result_1118
    };
    for mut radius in {
        let __tuple_items = (1i64, 2i64);
        [__tuple_items.0, __tuple_items.1]
    } {
        for mut tile in crate::strategy::grid::ring(&(game).world, camp, radius, true)? {
            let mut point: (i64, i64) = ((tile).x, (tile).y);
            if (((tile).base_terrain == 11i64)
                && ({
                    let __needle = point.clone();
                    let __container = &(hydro).freshwater;
                    !__container.contains(&__needle)
                } && {
                    let __needle = point.clone();
                    let __container = &occupied;
                    !__container.contains(&__needle)
                }))
            {
                return Ok(Some(tile));
            }
        }
    }
    Ok(None)
}

/// Reinforce sampled existing camps before advancing the round counter.
// Python: openciv3/barbarian_spawning.py:40
pub(crate) fn spawn_barbarians(
    mut game: crate::openciv3::game_state::GameState,
    mut rng: rt::Random,
) -> rt::Result<Vec<crate::openciv3::units::Unit>> {
    if {
        let __needle = (game).barbarian_activity;
        let __container = {
            static __CONSTANT_py__openciv3__barbarian_spawning__SPAWN_RATES: std::sync::OnceLock<
                indexmap::IndexMap<i64, f64>,
            > = std::sync::OnceLock::new();
            if __CONSTANT_py__openciv3__barbarian_spawning__SPAWN_RATES
                .get()
                .is_none()
            {
                let __constant_value = [
                    ((1i64).checked_neg().ok_or("integer overflow")?, 0.0f64),
                    (0i64, 0.03f64),
                    (1i64, 0.05f64),
                    (2i64, 0.08f64),
                    (3i64, 0.12f64),
                ]
                .into_iter()
                .collect::<indexmap::IndexMap<_, _>>();
                let _ =
                    __CONSTANT_py__openciv3__barbarian_spawning__SPAWN_RATES.set(__constant_value);
            }
            __CONSTANT_py__openciv3__barbarian_spawning__SPAWN_RATES
                .get()
                .ok_or("missing module constant")?
        };
        !__container.contains_key(&__needle)
    } {
        return Err("Invalid barbarian activity".to_string().into());
    }
    let mut camps: Vec<crate::openciv3::world::Tile> = {
        let mut __comprehension_result_1120: Vec<crate::openciv3::world::Tile> = Vec::new();
        let __comprehension_source_1119 = ((&(game).world).tiles.clone());
        for tile in __comprehension_source_1119.iter().cloned() {
            if (((tile).overlays & 128i64) != 0i64) {
                __comprehension_result_1120.push(tile.clone());
            }
        }
        __comprehension_result_1120
    };
    if (((game).barbarian_activity == (1i64).checked_neg().ok_or("integer overflow")?)
        || !(((camps).len() as i64) != 0i64))
    {
        return Ok(vec![]);
    }
    let mut rate: f64 = ((rt::struct_unpack_float(
        &(rt::struct_pack_float(
            ({
                static __CONSTANT_py__openciv3__barbarian_spawning__SPAWN_RATES:
                    std::sync::OnceLock<indexmap::IndexMap<i64, f64>> = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__barbarian_spawning__SPAWN_RATES
                    .get()
                    .is_none()
                {
                    let __constant_value = [
                        ((1i64).checked_neg().ok_or("integer overflow")?, 0.0f64),
                        (0i64, 0.03f64),
                        (1i64, 0.05f64),
                        (2i64, 0.08f64),
                        (3i64, 0.12f64),
                    ]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>();
                    let _ = __CONSTANT_py__openciv3__barbarian_spawning__SPAWN_RATES
                        .set(__constant_value);
                }
                __CONSTANT_py__openciv3__barbarian_spawning__SPAWN_RATES
                    .get()
                    .ok_or("missing module constant")?
            })
            .get(&((game).barbarian_activity))
            .ok_or("missing dict key")?
            .clone(),
        )?),
    )?,))
        .0
        .clone();
    let mut count: i64 = rt::ceil(
        ((rt::struct_unpack_float(
            &(rt::struct_pack_float(rt::finite(
                rate * ((rt::random_randrange(&(rng.clone()), 0i64, ((camps).len() as i64))?)
                    as f64),
            )?)?),
        )?,))
            .0
            .clone(),
    )?;
    {
        let __random = rng.clone();
        for __index in (1..camps.len()).rev() {
            let __other = rt::random_randrange(&__random, 0, __index as i64 + 1)? as usize;
            camps.swap(__index, __other);
        }
        ()
    };
    if !(count != 0i64) {
        return Ok(vec![]);
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut hit_points: i64 = ({
        let __source = &(rules).global_rules;
        let __key = 0i64;
        &__source[rt::index(__source.len(), __key)?]
    })
    .barbarian_spawn_hit_points;
    let mut experience: Option<i64> = {
        let __find_source_1121 = ((rules).experience_levels.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>();
        let mut __find_result_1121: Option<i64> = None;
        for (index, level) in __find_source_1121.iter().cloned() {
            if ((level).base_hit_points == hit_points) {
                __find_result_1121 = Some(index);
                break;
            }
        }
        __find_result_1121
    };
    if (experience).is_none() {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Barbarian spawning requires a ".to_string(),
                (hit_points).to_string(),
                "-hit-point experience level".to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    let mut hydro: crate::openciv3::hydrology::Hydrology =
        crate::openciv3::hydrology::Hydrology__from_world(&(game).world)?;
    let mut created: Vec<crate::openciv3::units::Unit> = vec![];
    for mut camp in (rt::slice_view(&camps, 0i64, count)).iter() {
        let mut prototype: i64 = select_barbarian_type(&game, camp, rng.clone())?;
        if !({
            let __compare_0 = 0i64;
            let __compare_1 = prototype;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = ((&(rules).units).len() as i64);
                (__compare_1 < __compare_2)
            } else {
                false
            }
        }) {
            return Err("Invalid barbarian unit prototype".to_string().into());
        }
        let mut tile: Option<crate::openciv3::world::Tile> =
            select_spawn_tile(&game, camp, prototype, &hydro)?;
        if (tile).is_none() {
            continue;
        }
        let mut kind: crate::openciv3::unit_rules::UnitPrototype =
            rt::at(&(rules).units, prototype)?;
        let mut unit: crate::openciv3::units::Unit = crate::openciv3::units::Unit {
            id: crate::openciv3::game_state::GameState__allocate_unit_id(game.clone())?,
            prototype: prototype,
            owner: 0i64,
            nationality: 0i64,
            name: (kind).name.clone(),
            x: ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
            y: ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
            previous_x: ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
            previous_y: ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
            experience: (*(experience.clone()).as_ref().ok_or("expected a value")?).clone(),
            hit_points: hit_points,
            movement_remaining: ((kind).movement as f64),
            ai_strategy: (1i64).checked_neg().ok_or("integer overflow")?,
            action: String::new(),
            transported_by: None,
            settler_mission: None,
            escorting: None,
            worker_job: None,
            worker_progress: 0.0f64,
            fortified: false,
            skipped_with_full_movement: false,
            defensive_bombards_remaining: 0i64,
            defender_destination: None,
            goto_destination: None,
            facing_override: None,
        };
        ((game).units).push(unit.clone());
        {
            created.push(unit);
        };
    }
    if (((created).len() as i64) != 0i64) {
        game.visibility = crate::openciv3::visibility::update_visibility(
            &(game).world,
            &(game).cities,
            &(game).units,
            &rules,
            &(game).ownership,
            (game).visibility.clone(),
            None,
            &None,
        )?;
    }
    Ok((created).iter().cloned().collect::<Vec<_>>())
}
