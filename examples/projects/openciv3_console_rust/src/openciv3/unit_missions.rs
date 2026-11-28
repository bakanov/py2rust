use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct SettlerMission {
    pub(crate) goal: String,
    pub(crate) destination: Option<(i64, i64)>,
    pub(crate) escort: Option<i64>,
    pub(crate) excluded: std::collections::BTreeSet<(i64, i64)>,
}

// Python: openciv3/unit_missions.py:20
pub(crate) fn reserved_settlements(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    excluding_unit: &Option<i64>,
) -> rt::Result<std::collections::BTreeSet<(i64, i64)>> {
    Ok({
        let mut __result: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        for __item in ({
            let mut __comprehension_result_341: std::collections::BTreeSet<(i64, i64)> =
                std::collections::BTreeSet::new();
            let __comprehension_source_340 = ((game).units.clone());
            for unit in __comprehension_source_340.iter().cloned() {
                if (((unit).owner == owner)
                    && ((Some((unit).id) != (*excluding_unit).clone())
                        && ((&(unit).transported_by).is_none()
                            && ((&(unit).settler_mission).is_some()
                                && (((((*((unit).settler_mission.clone())
                                    .as_ref()
                                    .ok_or("expected a value")?)
                                .clone())
                                .goal
                                .clone())
                                .as_str()
                                    == "build_city")
                                    && (((*((unit).settler_mission.clone())
                                        .as_ref()
                                        .ok_or("expected a value")?)
                                    .clone())
                                    .destination
                                    .clone())
                                    .is_some())))))
                {
                    __comprehension_result_341.insert(
                        (*(((*((unit).settler_mission.clone())
                            .as_ref()
                            .ok_or("expected a value")?)
                        .clone())
                        .destination
                        .clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                        .clone(),
                    );
                }
            }
            __comprehension_result_341
        })
        .into_iter()
        {
            __result.insert(__item);
        }
        __result
    })
}

// Python: openciv3/unit_missions.py:27
pub(crate) fn plan_settler(
    game: &crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
) -> rt::Result<SettlerMission> {
    if !((({
        let __source = &(&(&(game).scenario).rules).units;
        let __key = (unit).prototype;
        &__source[rt::index(__source.len(), __key)?]
    })
    .orders
        & 4194304i64)
        != 0i64)
    {
        return Err("Unit cannot found cities".to_string().into());
    }
    let mut old: Option<SettlerMission> = (unit).settler_mission.clone();
    let mut excluded: std::collections::BTreeSet<(i64, i64)> = (if (old).is_none() {
        std::collections::BTreeSet::new()
    } else {
        (((*(old.clone()).as_ref().ok_or("expected a value")?).clone())
            .excluded
            .clone())
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>()
    });
    let mut destination: Option<(i64, i64)> = None;
    if ({
        let __needle = ((unit).x, (unit).y);
        let __container = &excluded;
        !__container.contains(&__needle)
    } && (!(({
        let mut __comprehension_result_343: Vec<bool> = Vec::new();
        let __comprehension_source_342 = ((game).cities.clone());
        for city in __comprehension_source_342.iter().cloned() {
            __comprehension_result_343.push(((city).owner == (unit).owner));
        }
        __comprehension_result_343
    })
    .into_iter()
    .any(|__value| __value))
        && !(({
            let mut __comprehension_result_345: Vec<bool> = Vec::new();
            let __comprehension_source_344 = ((game).cities.clone());
            for city in __comprehension_source_344.iter().cloned() {
                __comprehension_result_345.push((((city).x, (city).y) == ((unit).x, (unit).y)));
            }
            __comprehension_result_345
        })
        .into_iter()
        .any(|__value| __value))))
    {
        destination = Some(((unit).x, (unit).y));
    } else {
        let mut scores: indexmap::IndexMap<(i64, i64), f64> = {
            let __call_346_0 = &((*game).clone());
            let __call_346_1 = &(rt::at(&(game).players, (unit).owner)?);
            let __call_346_2 = &(((unit).x, (unit).y));
            let __call_346_3 = &({
                let __call_347_0 = game;
                let __call_347_1 = (unit).owner;
                let __call_347_2 = &(Some((unit).id));
                reserved_settlements(__call_347_0, __call_347_1, __call_347_2)
            }?);
            let __call_346_4 = &({
                let mut __result: std::collections::BTreeSet<(i64, i64)> =
                    std::collections::BTreeSet::new();
                for __item in (excluded.clone()).into_iter() {
                    __result.insert(__item);
                }
                __result
            });
            let __call_346_default_5 = &(crate::civ3_ai::settler_locations::SettlerWeights {
                distance_radius: 4i64,
                distance_penalty: (((2i64).checked_neg().ok_or("integer overflow")?) as f64),
                food: ((5i64) as f64),
                shields: ((3i64) as f64),
                commerce: ((2i64) as f64),
                hills: ((10i64) as f64),
                luxury: ((15i64) as f64),
                strategic: ((20i64) as f64),
                water: ((10i64) as f64),
            });
            let __call_346_default_6 = None;
            crate::civ3_ai::settler_locations::settlement_scores(
                __call_346_0,
                __call_346_1,
                __call_346_2,
                __call_346_3,
                __call_346_4,
                __call_346_default_5,
                __call_346_default_6,
            )
        }?;
        destination = (if (((scores).len() as i64) != 0i64) {
            Some({
                let __values = &((scores).keys().cloned().collect::<Vec<_>>());
                let mut __items = __values.iter();
                let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
                let mut __best_key = {
                    let point = (*__best).clone();
                    (scores)
                        .get(&(point.clone()))
                        .ok_or("missing dict key")?
                        .clone()
                };
                for __candidate in __items {
                    let __key = {
                        let point = (*__candidate).clone();
                        (scores)
                            .get(&(point.clone()))
                            .ok_or("missing dict key")?
                            .clone()
                    };
                    if __key > __best_key {
                        __best = __candidate;
                        __best_key = __key;
                    }
                }
                (*__best).clone()
            })
        } else {
            None
        });
    }
    let mut mission: SettlerMission = SettlerMission {
        goal: (if (destination).is_none() {
            "join_city".to_string()
        } else {
            "build_city".to_string()
        }),
        destination: destination.clone(),
        escort: (if (old).is_none() {
            None
        } else {
            ((*(old.clone()).as_ref().ok_or("expected a value")?).clone())
                .escort
                .clone()
        }),
        excluded: excluded,
    };
    unit.settler_mission = Some(mission.clone());
    Ok(mission)
}

// Python: openciv3/unit_missions.py:48
pub(crate) fn assign_escort(
    game: &crate::openciv3::game_state::GameState,
    settler: &crate::openciv3::units::Unit,
    mut escort: crate::openciv3::units::Unit,
) -> rt::Result<()> {
    let mut mission: Option<SettlerMission> = (settler).settler_mission.clone();
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (escort).prototype)?;
    if ((mission).is_none()
        || (((settler).id == (escort).id) || ((settler).owner != (escort).owner)))
    {
        return Err("Escort requires a same-owner settler mission"
            .to_string()
            .into());
    }
    if (((kind).domain != 0i64) || ((kind).defense <= 0i64)) {
        return Err("Escort must defend on land".to_string().into());
    }
    if ((((*(mission.clone()).as_ref().ok_or("expected a value")?).clone())
        .escort
        .clone())
    .is_some()
        || (&(escort).escorting).is_some())
    {
        return Err("Unit already has an escort assignment".to_string().into());
    }
    mission.as_mut().ok_or("expected a value")?.escort = Some((escort).id);
    escort.escorting = Some((settler).id);
    Ok(())
}

/// Detach reciprocal references before removal or reassignment.
// Python: openciv3/unit_missions.py:62
pub(crate) fn clear_unit_missions(
    mut game: crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
) -> rt::Result<()> {
    for mut other in (&(game).units).iter().cloned() {
        if ((other).escorting.clone() == Some((unit).id)) {
            other.escorting = None;
        }
        if ((&(other).settler_mission).is_some()
            && (((*((other).settler_mission.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone())
            .escort
            .clone()
                == Some((unit).id)))
        {
            other
                .settler_mission
                .as_mut()
                .ok_or("expected a value")?
                .escort = None;
        }
    }
    unit.settler_mission = None;
    unit.escorting = None;
    unit.defender_destination = None;
    unit.goto_destination = None;
    (((&(game).visibility)
        .get(&((unit).owner))
        .ok_or("missing dict key")?)
    .exploration_targets
    .clone())
    .remove(&((unit).id));
    if (crate::openciv3::units::Unit__exploring(&unit)?
        || crate::openciv3::units::Unit__automating(&unit)?)
    {
        unit.action = String::new();
    }
    Ok(())
}
