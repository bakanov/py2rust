use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct Unit {
    pub(crate) id: i64,
    pub(crate) prototype: i64,
    pub(crate) owner: i64,
    pub(crate) nationality: i64,
    pub(crate) name: String,
    pub(crate) x: i64,
    pub(crate) y: i64,
    pub(crate) previous_x: i64,
    pub(crate) previous_y: i64,
    pub(crate) experience: i64,
    pub(crate) hit_points: i64,
    pub(crate) movement_remaining: f64,
    pub(crate) ai_strategy: i64,
    pub(crate) action: String,
    pub(crate) transported_by: Option<i64>,
    pub(crate) settler_mission: Option<crate::openciv3::unit_missions::SettlerMission>,
    pub(crate) escorting: Option<i64>,
    pub(crate) worker_job: Option<i64>,
    pub(crate) worker_progress: f64,
    pub(crate) fortified: bool,
    pub(crate) skipped_with_full_movement: bool,
    pub(crate) defensive_bombards_remaining: i64,
    pub(crate) defender_destination: Option<(i64, i64)>,
    pub(crate) goto_destination: Option<(i64, i64)>,
    pub(crate) facing_override: Option<String>,
}

// Python: openciv3/units.py:44
pub(crate) fn Unit__exploring(self_: &Unit) -> rt::Result<bool> {
    Ok((AsRef::<str>::as_ref(&(self_).action) == "explore"))
}

// Python: openciv3/units.py:48
pub(crate) fn Unit__automating(self_: &Unit) -> rt::Result<bool> {
    Ok((AsRef::<str>::as_ref(&(self_).action) == "automate"))
}

// Python: openciv3/units.py:52
pub(crate) fn initialize_units(
    definition: &crate::openciv3::scenario_model::ScenarioDefinition,
) -> rt::Result<Vec<Unit>> {
    let mut world: Option<crate::openciv3::world::WorldMap> = (definition).world.clone();
    if (world).is_none() {
        return Err("Generate a map before initializing units"
            .to_string()
            .into());
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (definition).rules.clone();
    if (((&(rules).global_rules).len() as i64) != 1i64) {
        return Err("Unit initialization needs one global rules record"
            .to_string()
            .into());
    }
    let mut units: Vec<Unit> = vec![];

    for mut placed in ((*(world.clone()).as_ref().ok_or("expected a value")?).clone())
        .units
        .clone()
    {
        let mut civilization: Option<i64> =
            initialize_units__owner(definition, (placed).owner_kind, (placed).owner)?;
        if (civilization).is_none() {
            return Err("Placed unit has no owner".to_string().into());
        }
        let mut prototype: i64 = (if (placed).use_civilization_king {
            ({
                let __source = &(definition).civilizations;
                let __key = (*(civilization.clone()).as_ref().ok_or("expected a value")?).clone();
                &__source[rt::index(__source.len(), __key)?]
            })
            .king_unit
        } else {
            (placed).prototype
        });
        {
            units.push(initialize_units__create(
                &rules,
                &world,
                &units,
                (*(civilization.clone()).as_ref().ok_or("expected a value")?).clone(),
                prototype,
                (placed).experience,
                (placed).x,
                (placed).y,
                &(placed).name,
                (placed).ai_strategy,
            )?);
        };
    }
    let mut starts: Vec<crate::openciv3::world::StartingLocation> = (if {
        let __needle: &str = AsRef::<str>::as_ref("SLOC");
        let __container = &(&(definition).scenario).sections;
        __container.contains_key(__needle)
    } {
        ((*(world.clone()).as_ref().ok_or("expected a value")?).clone())
            .starts
            .clone()
    } else {
        ({
            let mut __comprehension_result_330: Vec<crate::openciv3::world::StartingLocation> =
                Vec::new();
            let __comprehension_source_329 =
                (((*(world.clone()).as_ref().ok_or("expected a value")?).clone())
                    .tiles
                    .clone());
            for tile in __comprehension_source_329.iter().cloned() {
                if crate::openciv3::world::Tile__player_start(&tile)? {
                    __comprehension_result_330.push(crate::openciv3::world::StartingLocation {
                        owner_kind: 0i64,
                        owner: (1i64).checked_neg().ok_or("integer overflow")?,
                        x: (tile).x,
                        y: (tile).y,
                    });
                }
            }
            __comprehension_result_330
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>()
    });
    let mut assigned_starts: std::collections::BTreeSet<Option<i64>> = {
        let mut __comprehension_result_332: std::collections::BTreeSet<Option<i64>> =
            std::collections::BTreeSet::new();
        let __comprehension_source_331 = (starts.clone());
        for start in __comprehension_source_331.iter().cloned() {
            if {
                let __needle = (start).owner_kind;
                let __container = &({
                    let __tuple_value = &((2i64, 3i64));
                    vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                });
                __container.contains(&__needle)
            } {
                __comprehension_result_332.insert(initialize_units__owner(
                    definition,
                    (start).owner_kind,
                    (start).owner,
                )?);
            }
        }
        __comprehension_result_332
    };
    let mut available: Vec<i64> = {
        let mut __seen = std::collections::BTreeSet::new();
        let mut __result: Vec<i64> = Vec::new();
        for __item in ({
            let mut __comprehension_result_334: Vec<i64> = Vec::new();
            let __comprehension_source_333 = ((definition).assigned_civilizations.clone());
            for civ in __comprehension_source_333.iter().cloned() {
                if ((civ > 0i64) && {
                    let __needle = Some(civ);
                    let __container = &assigned_starts;
                    !__container.contains(&__needle)
                }) {
                    __comprehension_result_334.push(civ);
                }
            }
            __comprehension_result_334
        })
        .into_iter()
        {
            if __seen.insert(__item.clone()) {
                __result.push(__item);
            }
        }
        __result
    };
    let mut global_rules: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(rules).global_rules, 0i64)?;
    let mut default_experience: i64 = (global_rules).default_unit_experience;
    let mut resolved_starts: indexmap::IndexMap<i64, (i64, i64)> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut start in starts {
        if ((start).owner_kind == 1i64) {
            continue;
        }
        let mut civilization: Option<i64> =
            (if (((start).owner_kind == 0i64) && !(available.clone()).is_empty()) {
                Some(if (available).is_empty() {
                    return Err("popleft from an empty deque".into());
                } else {
                    (available).remove(0)
                })
            } else {
                initialize_units__owner(definition, (start).owner_kind, (start).owner)?
            });
        if ((civilization).is_none() || (civilization.clone() == Some(0i64))) {
            continue;
        }
        (resolved_starts)
            .entry((*(civilization.clone()).as_ref().ok_or("expected a value")?).clone())
            .or_insert(((start).x, (start).y))
            .clone();
        let mut slot_index: i64 = {
            let __find_source_335 = ((definition).assigned_civilizations.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>();
            let mut __find_result_335: i64 = (1i64).checked_neg().ok_or("integer overflow")?;
            for (i, value) in __find_source_335.iter().cloned() {
                if (Some(value) == civilization.clone()) {
                    __find_result_335 = i;
                    break;
                }
            }
            __find_result_335
        };
        let mut starting_units: Vec<(i64, i64)> = (if {
            let __compare_0 = 0i64;
            let __compare_1 = slot_index;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = ((&(definition).slots).len() as i64);
                (__compare_1 < __compare_2)
            } else {
                false
            }
        } {
            ({
                let __source = &(definition).slots;
                let __key = slot_index;
                &__source[rt::index(__source.len(), __key)?]
            })
            .starting_units
            .clone()
        } else {
            vec![]
        });
        if (((starting_units).len() as i64) != 0i64) {
            for mut for_target_107_12 in starting_units {
                let (mut count, mut prototype): (i64, i64) = for_target_107_12;
                if (count < 0i64) {
                    return Err("Negative starting-unit count".to_string().into());
                }
                for _ in 0i64..count {
                    {
                        units.push(initialize_units__create(
                            &rules,
                            &world,
                            &units,
                            (*(civilization.clone()).as_ref().ok_or("expected a value")?).clone(),
                            prototype,
                            default_experience,
                            (start).x,
                            (start).y,
                            "",
                            (1i64).checked_neg().ok_or("integer overflow")?,
                        )?);
                    };
                }
            }
        } else {
            for mut prototype in {
                let __tuple_items = (
                    (global_rules).start_unit_type1,
                    (global_rules).start_unit_type2,
                );
                [__tuple_items.0, __tuple_items.1]
            } {
                if (prototype >= 0i64) {
                    {
                        units.push(initialize_units__create(
                            &rules,
                            &world,
                            &units,
                            (*(civilization.clone()).as_ref().ok_or("expected a value")?).clone(),
                            prototype,
                            default_experience,
                            (start).x,
                            (start).y,
                            "",
                            (1i64).checked_neg().ok_or("integer overflow")?,
                        )?);
                    };
                }
            }
        }
    }
    if (((&(definition).options).victory_flags
        & (rt::int_lshift(1i64, 11i64)? | rt::int_lshift(1i64, 12i64)?))
        != 0i64)
    {
        for mut civilization in {
            let mut __seen = std::collections::BTreeSet::new();
            let mut __result: Vec<i64> = Vec::new();
            for __item in ((definition).assigned_civilizations.clone()).into_iter() {
                if __seen.insert(__item.clone()) {
                    __result.push(__item);
                }
            }
            __result
        } {
            if ((civilization <= 0i64)
                || ({
                    let mut __comprehension_result_337: Vec<bool> = Vec::new();
                    let __comprehension_source_336 = (units.clone());
                    for unit in __comprehension_source_336.iter().cloned() {
                        __comprehension_result_337.push(
                            (((unit).owner == civilization)
                                && (({
                                    let __source = &(rules).units;
                                    let __key = (unit).prototype;
                                    &__source[rt::index(__source.len(), __key)?]
                                })
                                .abilities
                                    & 536870912i64)
                                    != 0),
                        );
                    }
                    __comprehension_result_337
                })
                .into_iter()
                .any(|__value| __value))
            {
                continue;
            }
            let mut point: Option<(i64, i64)> =
                (resolved_starts.clone()).get(&(civilization)).cloned();
            if (point).is_none() {
                point = {
                    let __find_source_338 = units.clone();
                    let mut __find_result_338: Option<(i64, i64)> = None;
                    for unit in __find_source_338.iter().cloned() {
                        if ((unit).owner == civilization) {
                            __find_result_338 = Some(((unit).x, (unit).y));
                            break;
                        }
                    }
                    __find_result_338
                };
            }
            if (point).is_none() {
                point = {
                    let __find_source_339 =
                        ((*(world.clone()).as_ref().ok_or("expected a value")?).clone())
                            .cities
                            .clone();
                    let mut __find_result_339: Option<(i64, i64)> = None;
                    for city in __find_source_339.iter().cloned() {
                        if (initialize_units__owner(definition, (city).owner_kind, (city).owner)?
                            == Some(civilization))
                        {
                            __find_result_339 = Some(((city).x, (city).y));
                            break;
                        }
                    }
                    __find_result_339
                };
            }
            if (point).is_none() {
                return Err("A Regicide civilization lacks a king or starting location"
                    .to_string()
                    .into());
            }
            let mut prototype: i64 = ({
                let __source = &(definition).civilizations;
                let __key = civilization;
                &__source[rt::index(__source.len(), __key)?]
            })
            .king_unit;
            if (!({
                let __compare_0 = 0i64;
                let __compare_1 = prototype;
                if (__compare_0 <= __compare_1) {
                    let __compare_2 = ((&(rules).units).len() as i64);
                    (__compare_1 < __compare_2)
                } else {
                    false
                }
            }) || !((({
                let __source = &(rules).units;
                let __key = prototype;
                &__source[rt::index(__source.len(), __key)?]
            })
            .abilities
                & 536870912i64)
                != 0i64))
            {
                return Err("Regicide requires a king prototype for each civilization"
                    .to_string()
                    .into());
            }
            let mut count: i64 = (if (((&(definition).options).victory_flags
                & rt::int_lshift(1i64, 12i64)?)
                != 0i64)
            {
                7i64
            } else {
                1i64
            });
            for _ in 0i64..count {
                {
                    units.push(initialize_units__create(
                        &rules,
                        &world,
                        &units,
                        civilization,
                        prototype,
                        default_experience,
                        ((*(point).as_ref().ok_or("expected a value")?).clone())
                            .0
                            .clone(),
                        ((*(point).as_ref().ok_or("expected a value")?).clone())
                            .1
                            .clone(),
                        "",
                        (1i64).checked_neg().ok_or("integer overflow")?,
                    )?);
                };
            }
        }
    }
    Ok(units)
}

// Python: openciv3/units.py:61
pub(crate) fn initialize_units__owner(
    definition: &crate::openciv3::scenario_model::ScenarioDefinition,
    mut kind: i64,
    mut value: i64,
) -> rt::Result<Option<i64>> {
    crate::openciv3::world::resolve_owner(
        kind,
        value,
        &((definition).assigned_civilizations.clone()),
        ((&(definition).civilizations).len() as i64),
    )
}

// Python: openciv3/units.py:64
pub(crate) fn initialize_units__create(
    rules: &crate::openciv3::rules::RuleCatalog,
    world: &Option<crate::openciv3::world::WorldMap>,
    units: &[Unit],
    mut civilization: i64,
    mut prototype: i64,
    mut experience: i64,
    mut x: i64,
    mut y: i64,
    name: &str,
    mut ai_strategy: i64,
) -> rt::Result<Unit> {
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
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Invalid unit prototype: ".to_string(),
                (prototype).to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    if !({
        let __compare_0 = 0i64;
        let __compare_1 = experience;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = ((&(rules).experience_levels).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Invalid unit experience: ".to_string(),
                (experience).to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    let mut tile: Option<crate::openciv3::world::Tile> = crate::openciv3::world::WorldMap__tile_at(
        &((*((*world).clone()).as_ref().ok_or("expected a value")?).clone()),
        x,
        y,
    )?;
    if (tile).is_none() {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Unit is outside the map: (".to_string(),
                (x).to_string(),
                ", ".to_string(),
                (y).to_string(),
                ")".to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    let mut unit_type: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(rules).units, prototype)?;
    let mut hit_points: i64 = (({
        let __source = &(rules).experience_levels;
        let __key = experience;
        &__source[rt::index(__source.len(), __key)?]
    })
    .base_hit_points)
        .checked_add((unit_type).hp_bonus)
        .ok_or("integer overflow")?;
    Ok(Unit {
        id: ((units).len() as i64),
        prototype: prototype,
        owner: civilization,
        nationality: civilization,
        name: {
            let __boolean_123706001560784 = name.to_owned();
            if !(__boolean_123706001560784).is_empty() {
                __boolean_123706001560784
            } else {
                (unit_type).name.clone()
            }
        },
        x: ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
        y: ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
        previous_x: ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
        previous_y: ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
        experience: experience,
        hit_points: hit_points,
        movement_remaining: ((unit_type).movement as f64),
        ai_strategy: ai_strategy,
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
    })
}
