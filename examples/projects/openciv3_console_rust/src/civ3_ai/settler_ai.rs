use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum SettlerStatus {
    MOVED,
    WAITING,
    RETARGETED,
    REPLAN,
    FOUNDED,
    REMOVED,
}

#[derive(Clone, PartialEq)]
pub(crate) struct SettlerStep {
    pub(crate) status: SettlerStatus,
    pub(crate) movement: Option<crate::openciv3::unit_movement::MoveResult>,
    pub(crate) city: Option<i64>,
    pub(crate) game: Option<crate::openciv3::game_state::GameState>,
}

// Python: civ3_ai/settler_ai.py:41
pub(crate) fn _retarget(
    game: &crate::openciv3::game_state::GameState,
    mut settler: crate::openciv3::units::Unit,
) -> rt::Result<SettlerStep> {
    let mut mission: Option<crate::openciv3::unit_missions::SettlerMission> =
        (settler).settler_mission.clone();
    if !((mission).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    if (((*(mission.clone()).as_ref().ok_or("expected a value")?).clone())
        .destination
        .clone())
    .is_some()
    {
        (((*(mission.clone()).as_ref().ok_or("expected a value")?).clone())
            .excluded
            .clone())
        .insert(
            (*(((*(mission.clone()).as_ref().ok_or("expected a value")?).clone())
                .destination
                .clone())
            .as_ref()
            .ok_or("expected a value")?)
            .clone(),
        );
    }
    crate::openciv3::unit_missions::plan_settler(game, settler.clone())?;
    settler.movement_remaining = 0.0f64;
    Ok(SettlerStep {
        status: SettlerStatus::RETARGETED,
        movement: None,
        city: None,
        game: None,
    })
}

// Python: civ3_ai/settler_ai.py:51
pub(crate) fn advance_settler(
    mut game: crate::openciv3::game_state::GameState,
    mut settler: crate::openciv3::units::Unit,
    mut rng: rt::Random,
) -> rt::Result<SettlerStep> {
    if !(({
        let mut __comprehension_result_852: Vec<bool> = Vec::new();
        let __comprehension_source_851 = ((game).units.clone());
        for unit in __comprehension_source_851.iter().cloned() {
            __comprehension_result_852.push(((unit).id == (settler).id));
        }
        __comprehension_result_852
    })
    .into_iter()
    .any(|__value| __value))
    {
        return Ok(SettlerStep {
            status: SettlerStatus::REMOVED,
            movement: None,
            city: None,
            game: None,
        });
    }
    if ((settler).movement_remaining <= 0.0001f64) {
        return Ok(SettlerStep {
            status: SettlerStatus::WAITING,
            movement: None,
            city: None,
            game: None,
        });
    }
    let mut mission: crate::openciv3::unit_missions::SettlerMission =
        match ((settler).settler_mission.clone()) {
            Some(__value) => __value,
            None => crate::openciv3::unit_missions::plan_settler(&game, settler.clone())?,
        };
    if (AsRef::<str>::as_ref(&(mission).goal) == "join_city") {
        let mut routes: Vec<(
            crate::openciv3::pathfinding::UnitPath,
            crate::openciv3::cities::City,
        )> = vec![];
        for mut city in (&(game).cities).iter() {
            if !(crate::openciv3::city_growth::can_join_city(&game, &settler, city)?) {
                continue;
            }
            let mut center: Option<crate::openciv3::world::Tile> =
                crate::openciv3::world::WorldMap__tile_at(&(game).world, (city).x, (city).y)?;
            if (center).is_none() {
                continue;
            }
            let mut route: crate::openciv3::pathfinding::UnitPath =
                crate::openciv3::pathfinding::find_path(
                    &game,
                    &settler,
                    &((*(center).as_ref().ok_or("expected a value")?).clone()),
                    &({
                        let mut __result = std::collections::BTreeSet::new();
                        for __item in vec![].into_iter() {
                            __result.insert(__item);
                        }
                        __result
                    }),
                )?;
            if (route).reachable {
                {
                    routes.push((route.clone(), (*city).clone()));
                };
            }
        }
        if (((routes).len() as i64) != 0i64) {
            let (mut route, mut city): (
                crate::openciv3::pathfinding::UnitPath,
                crate::openciv3::cities::City,
            ) = {
                let __values = &routes;
                let mut __items = __values.iter();
                let mut __best = __items.next().ok_or("min() arg is an empty sequence")?;
                let mut __best_key = {
                    let item = (*__best).clone();
                    (
                        (&(item).0).cost,
                        ((&(&(item).0).steps).len() as i64),
                        (&(item).1).id,
                    )
                };
                for __candidate in __items {
                    let __key = {
                        let item = (*__candidate).clone();
                        (
                            (&(item).0).cost,
                            ((&(&(item).0).steps).len() as i64),
                            (&(item).1).id,
                        )
                    };
                    if __key < __best_key {
                        __best = __candidate;
                        __best_key = __key;
                    }
                }
                (*__best).clone()
            };
            if !(((&(route).steps).len() as i64) != 0i64) {
                crate::openciv3::city_growth::join_city(&game, &settler, city.clone())?;
                return Ok(SettlerStep {
                    status: SettlerStatus::REMOVED,
                    city: Some((city).id),
                    movement: None,
                    game: None,
                });
            }
            mission.destination = Some((route).destination.clone());
            let mut movement: crate::openciv3::unit_movement::MoveResult = {
                let __call_853_0 = &(game.clone());
                let __call_853_1 = &(settler.clone());
                let __call_853_2 = &({
                    let __star_args_854: Vec<i64> = {
                        let __tuple_value = &(rt::at(&(route).steps, 0i64)?);
                        vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                    };
                    if !(2..=2).contains(&__star_args_854.len()) {
                        return Err("wrong function argument count".into());
                    }
                    crate::openciv3::world::WorldMap__tile_at(
                        &(game).world,
                        rt::at(&__star_args_854, 0 as i64)?,
                        rt::at(&__star_args_854, 1 as i64)?,
                    )?
                });
                let __call_853_3 = &(Some(rng.clone()));
                let __call_853_default_3 = &({
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in vec![].into_iter() {
                        __result.insert(__item);
                    }
                    __result
                });
                let __call_853_default_4 = None;
                crate::openciv3::unit_movement::move_unit(
                    __call_853_0,
                    __call_853_1,
                    __call_853_2,
                    __call_853_default_3,
                    __call_853_default_4,
                    __call_853_3,
                )
            }?;
            if ((movement).status.clone() == crate::openciv3::unit_movement::MoveStatus::MOVED) {
                return Ok(SettlerStep {
                    status: SettlerStatus::MOVED,
                    movement: Some(movement),
                    city: None,
                    game: None,
                });
            }
            if ((movement).status.clone() == crate::openciv3::unit_movement::MoveStatus::KILLED) {
                return Ok(SettlerStep {
                    status: SettlerStatus::REMOVED,
                    movement: Some(movement),
                    city: None,
                    game: None,
                });
            }
            settler.movement_remaining = 0.0f64;
            return Ok(SettlerStep {
                status: SettlerStatus::WAITING,
                movement: Some(movement),
                city: None,
                game: None,
            });
        }
        crate::openciv3::unit_lifecycle::remove_unit(&game, &settler)?;
        return Ok(SettlerStep {
            status: SettlerStatus::REMOVED,
            movement: None,
            city: None,
            game: None,
        });
    }
    let mut target: Option<crate::openciv3::world::Tile> = (if (&(mission).destination).is_some() {
        {
            let __star_args_855: Vec<i64> = {
                let __tuple_value = &((*((mission).destination.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone());
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_855.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &(game).world,
                rt::at(&__star_args_855, 0 as i64)?,
                rt::at(&__star_args_855, 1 as i64)?,
            )?
        }
    } else {
        None
    });
    let mut centers: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_857: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_856 = ((game).cities.clone());
        for city in __comprehension_source_856.iter().cloned() {
            __comprehension_result_857.insert(((city).x, (city).y));
        }
        __comprehension_result_857
    };
    if ((target).is_none()
        || ({
            let __needle = (
                ((*(target.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                ((*(target.clone()).as_ref().ok_or("expected a value")?).clone()).y,
            );
            let __container = &centers;
            __container.contains(&__needle)
        } || ({
            let mut __comprehension_result_859: Vec<bool> = Vec::new();
            let __comprehension_source_858 = (crate::openciv3::world::WorldMap__neighbors(
                &(game).world,
                &((*(target.clone()).as_ref().ok_or("expected a value")?).clone()),
            )?);
            for tile in __comprehension_source_858.iter().cloned() {
                __comprehension_result_859.push({
                    let __needle = ((tile).x, (tile).y);
                    let __container = &centers;
                    __container.contains(&__needle)
                });
            }
            __comprehension_result_859
        })
        .into_iter()
        .any(|__value| __value)))
    {
        crate::openciv3::unit_missions::clear_unit_missions(game, settler)?;
        return Ok(SettlerStep {
            status: SettlerStatus::REPLAN,
            movement: None,
            city: None,
            game: None,
        });
    }
    if (Some(((settler).x, (settler).y)) == (mission).destination.clone()) {
        if !(crate::openciv3::city_founding::can_found_city(&game, &settler)?) {
            return _retarget(&game, settler);
        }
        let (mut game, mut city): (
            crate::openciv3::game_state::GameState,
            crate::openciv3::cities::City,
        ) = {
            let __call_860_0 = game.clone();
            let __call_860_1 = &(settler.clone());
            let __call_860_2 =
                &(crate::openciv3::city_names::next_city_name(&game, (settler).owner)?);
            let __call_860_3 = rng.clone();
            crate::openciv3::city_founding::found_city_state(
                __call_860_0,
                __call_860_1,
                __call_860_2,
                __call_860_3,
            )
        }?;
        return Ok(SettlerStep {
            status: SettlerStatus::FOUNDED,
            city: Some((city).id),
            game: Some(game),
            movement: None,
        });
    }
    if (&(mission).escort).is_none() {
        settler.movement_remaining = 0.0f64;
        return Ok(SettlerStep {
            status: SettlerStatus::WAITING,
            movement: None,
            city: None,
            game: None,
        });
    }
    let mut path: crate::openciv3::pathfinding::UnitPath = crate::openciv3::pathfinding::find_path(
        &game,
        &settler,
        &((*(target).as_ref().ok_or("expected a value")?).clone()),
        &({
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        }),
    )?;
    if (!((path).reachable) || !(((&(path).steps).len() as i64) != 0i64)) {
        return _retarget(&game, settler);
    }
    let mut movement: crate::openciv3::unit_movement::MoveResult = {
        let __call_861_0 = &(game.clone());
        let __call_861_1 = &(settler.clone());
        let __call_861_2 = &({
            let __star_args_862: Vec<i64> = {
                let __tuple_value = &(rt::at(&(path).steps, 0i64)?);
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_862.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &(game).world,
                rt::at(&__star_args_862, 0 as i64)?,
                rt::at(&__star_args_862, 1 as i64)?,
            )?
        });
        let __call_861_3 = &(Some(rng.clone()));
        let __call_861_default_3 = &({
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        });
        let __call_861_default_4 = None;
        crate::openciv3::unit_movement::move_unit(
            __call_861_0,
            __call_861_1,
            __call_861_2,
            __call_861_default_3,
            __call_861_default_4,
            __call_861_3,
        )
    }?;
    if ((movement).status.clone() == crate::openciv3::unit_movement::MoveStatus::MOVED) {
        return Ok(SettlerStep {
            status: SettlerStatus::MOVED,
            movement: Some(movement),
            city: None,
            game: None,
        });
    }
    if ((movement).status.clone() == crate::openciv3::unit_movement::MoveStatus::KILLED) {
        return Ok(SettlerStep {
            status: SettlerStatus::REMOVED,
            movement: Some(movement),
            city: None,
            game: None,
        });
    }
    _retarget(&game, settler)
}

// Python: civ3_ai/settler_ai.py:107
pub(crate) fn recruit_escort(
    game: &crate::openciv3::game_state::GameState,
    escort: &crate::openciv3::units::Unit,
) -> rt::Result<Option<crate::openciv3::units::Unit>> {
    if ((&(escort).escorting).is_some()
        || !(crate::openciv3::unit_entry::can_defend_on_land(game, escort)?))
    {
        return Ok(None);
    }
    for mut settler in (&(game).units).iter() {
        if (((settler).id != (escort).id)
            && (((settler).owner == (escort).owner)
                && ((((settler).x, (settler).y) == ((escort).x, (escort).y))
                    && ((&(settler).transported_by).is_none()
                        && ((&(settler).settler_mission).is_some()
                            && (((((*((settler).settler_mission.clone())
                                .as_ref()
                                .ok_or("expected a value")?)
                            .clone())
                            .goal
                            .clone())
                            .as_str()
                                == "build_city")
                                && (((*((settler).settler_mission.clone())
                                    .as_ref()
                                    .ok_or("expected a value")?)
                                .clone())
                                .escort
                                .clone())
                                .is_none()))))))
        {
            crate::openciv3::unit_missions::assign_escort(game, settler, (*escort).clone())?;
            return Ok(Some((*settler).clone()));
        }
    }
    Ok(None)
}

/// Move the settler first, then catch up and consume remaining escort movement.
// Python: civ3_ai/settler_ai.py:119
pub(crate) fn play_escort(
    game: &crate::openciv3::game_state::GameState,
    mut escort: crate::openciv3::units::Unit,
    mut rng: rt::Random,
) -> rt::Result<Vec<crate::openciv3::unit_movement::MoveResult>> {
    let mut settler: Option<crate::openciv3::units::Unit> = {
        let __find_source_863 = (game).units.clone();
        let mut __find_result_863: Option<crate::openciv3::units::Unit> = None;
        for unit in __find_source_863.iter().cloned() {
            if (Some((unit).id) == (escort).escorting.clone()) {
                __find_result_863 = Some(unit.clone());
                break;
            }
        }
        __find_result_863
    };
    if ((settler).is_none()
        || (((*(settler.clone()).as_ref().ok_or("expected a value")?).clone())
            .settler_mission
            .clone())
        .is_none())
    {
        escort.escorting = None;
        return Ok(vec![]);
    }
    while ((((*(settler.clone()).as_ref().ok_or("expected a value")?).clone()).movement_remaining
        > 0.0001f64)
        && (((*(settler.clone()).as_ref().ok_or("expected a value")?).clone())
            .transported_by
            .clone())
        .is_none())
    {
        let mut result: SettlerStep = {
            let __call_864_0 = (*game).clone();
            let __call_864_1 = (*(settler.clone()).as_ref().ok_or("expected a value")?).clone();
            let __call_864_2 = rng.clone();
            advance_settler(__call_864_0, __call_864_1, __call_864_2)
        }?;
        if {
            let __needle = (result).status.clone();
            let __container = &({
                let __tuple_value = &((
                    SettlerStatus::FOUNDED,
                    SettlerStatus::REMOVED,
                    SettlerStatus::REPLAN,
                ));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                ]
            });
            __container.contains(&__needle)
        } {
            return Ok(vec![]);
        }
        if ((result).status.clone() != SettlerStatus::MOVED) {
            break;
        }
    }
    if (((escort).x, (escort).y)
        == (
            ((*(settler.clone()).as_ref().ok_or("expected a value")?).clone()).x,
            ((*(settler.clone()).as_ref().ok_or("expected a value")?).clone()).y,
        ))
    {
        escort.movement_remaining = 0.0f64;
        return Ok(vec![]);
    }
    let mut tile: Option<crate::openciv3::world::Tile> = crate::openciv3::world::WorldMap__tile_at(
        &(game).world,
        ((*(settler.clone()).as_ref().ok_or("expected a value")?).clone()).x,
        ((*(settler.clone()).as_ref().ok_or("expected a value")?).clone()).y,
    )?;
    if !((tile).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    let mut progress: crate::openciv3::unit_movement::PathProgress = {
        let __call_865_0 = &((*game).clone());
        let __call_865_1 = &(escort.clone());
        let __call_865_2 = &(crate::openciv3::pathfinding::find_path(
            game,
            &escort,
            &((*(tile).as_ref().ok_or("expected a value")?).clone()),
            &({
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![].into_iter() {
                    __result.insert(__item);
                }
                __result
            }),
        )?);
        let __call_865_3 = &(Some(rng.clone()));
        let __call_865_default_3 = &({
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        });
        let __call_865_default_4 = &None;
        crate::openciv3::unit_movement::follow_path(
            __call_865_0,
            __call_865_1,
            __call_865_2,
            __call_865_default_3,
            __call_865_default_4,
            __call_865_3,
        )
    }?;
    if (((escort).x, (escort).y)
        == (
            ((*(settler.clone()).as_ref().ok_or("expected a value")?).clone()).x,
            ((*(settler.clone()).as_ref().ok_or("expected a value")?).clone()).y,
        ))
    {
        escort.movement_remaining = 0.0f64;
    }
    let mut stopped: Option<crate::openciv3::unit_movement::MoveResult> =
        (progress).stopped.clone();
    if ((stopped).is_some()
        && match (stopped.clone()) {
            Some(__value) => {
                let __needle = __value;
                let __container = &(progress).moves;
                !__container.contains(&__needle)
            }
            None => true,
        })
    {
        if !((stopped).is_some()) {
            rt::assertion(false, &("".to_string()))?;
        }
        return Ok({
            let mut __left: Vec<crate::openciv3::unit_movement::MoveResult> =
                (progress).moves.clone();
            let __right: Vec<crate::openciv3::unit_movement::MoveResult> = ({
                let __tuple_value = &((stopped,));
                vec![__tuple_value.0.clone()]
            })
            .into_iter()
            .map(|__value| __value.ok_or("expected a value".into()))
            .collect::<rt::Result<Vec<_>>>()?;
            __left.extend(__right);
            __left
        });
    }
    Ok((progress).moves.clone())
}
