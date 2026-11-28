use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct AirBase {
    pub(crate) name: String,
    pub(crate) carrier: Option<i64>,
}

// Python: openciv3/air_missions.py:22
pub(crate) fn can_rebase(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<bool> {
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    Ok((((kind).domain == 2i64)
        && (((kind).orders & 2199023255552i64) != 0
            && (((kind).operational_range > 0i64) && ((unit).movement_remaining > 0.0001f64)))))
}

// Python: openciv3/air_missions.py:28
pub(crate) fn rebase_destination(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<Option<AirBase>> {
    let mut point: (i64, i64) = ((tile).x, (tile).y);
    let mut origin: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if ((origin).is_none()
        || ((point.clone() == ((unit).x, (unit).y)) || !(can_rebase(game, unit)?)))
    {
        return Ok(None);
    }
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    if (crate::strategy::grid::distance(
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
            let __structural_value = (*(origin).as_ref().ok_or("expected a value")?).clone();
            crate::strategy::grid::GridPoint {
                x: (__structural_value).x.clone(),
                y: (__structural_value).y.clone(),
            }
        }),
        &({
            let __structural_value = (*tile).clone();
            crate::strategy::grid::GridPoint {
                x: (__structural_value).x.clone(),
                y: (__structural_value).y.clone(),
            }
        }),
    )? > (3i64)
        .checked_mul((kind).operational_range)
        .ok_or("integer overflow")?)
    {
        return Ok(None);
    }
    let mut city: Option<crate::openciv3::cities::City> = {
        let __find_source_56 = (game).cities.clone();
        let mut __find_result_56: Option<crate::openciv3::cities::City> = None;
        for city in __find_source_56.iter().cloned() {
            if (((city).x, (city).y) == point.clone()) {
                __find_result_56 = Some(city.clone());
                break;
            }
        }
        __find_result_56
    };
    if (city).is_some() {
        return Ok(
            (if (((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).owner
                == (unit).owner)
            {
                Some(AirBase {
                    name: ((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                        .name
                        .clone(),
                    carrier: None,
                })
            } else {
                None
            }),
        );
    }
    if {
        let __needle = point.clone();
        let __container = &((&(game).visibility)
            .get(&((unit).owner))
            .ok_or("missing dict key")?)
        .visible;
        !__container.contains(&__needle)
    } {
        return Ok(None);
    }
    let mut occupants: Vec<crate::openciv3::units::Unit> = {
        let mut __comprehension_result_58: Vec<crate::openciv3::units::Unit> = Vec::new();
        let __comprehension_source_57 = ((game).units.clone());
        for other in __comprehension_source_57.iter().cloned() {
            if ((((other).x, (other).y) == point.clone()) && ((other).hit_points > 0i64)) {
                __comprehension_result_58.push(other.clone());
            }
        }
        __comprehension_result_58
    };
    if ({
        let mut __comprehension_result_60: Vec<bool> = Vec::new();
        let __comprehension_source_59 = (occupants.clone());
        for other in __comprehension_source_59.iter().cloned() {
            __comprehension_result_60.push(((other).owner != (unit).owner));
        }
        __comprehension_result_60
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Ok(None);
    }
    let mut claim: Option<i64> = ((game).ownership.clone()).get(&(point)).cloned();
    let mut territory: Option<i64> = {
        let __find_source_61 = (game).cities.clone();
        let mut __find_result_61: Option<i64> = None;
        for city in __find_source_61.iter().cloned() {
            if (Some((city).id) == claim.clone()) {
                __find_result_61 = Some((city).owner);
                break;
            }
        }
        __find_result_61
    };
    let mut field_owner: Option<i64> = (if (&(tile).installation_owner).is_some() {
        (tile).installation_owner.clone()
    } else {
        territory.clone()
    });
    if (((tile).overlays & 536870912i64) != 0
        && ((field_owner == Some((unit).owner))
            && ((territory).is_none()
                || ((*(territory).as_ref().ok_or("expected a value")?).clone())
                    == ((((), (unit).owner)).1))))
    {
        return Ok(Some(AirBase {
            name: "airfield".to_string(),
            carrier: None,
        }));
    }
    if ({
        let mut __comprehension_result_63: Vec<bool> = Vec::new();
        let __comprehension_source_62 = ((game).units.clone());
        for other in __comprehension_source_62.iter().cloned() {
            __comprehension_result_63.push(((other).transported_by.clone() == Some((unit).id)));
        }
        __comprehension_result_63
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Ok(None);
    }
    for mut carrier in {
        let mut __decorated: Vec<(i64, crate::openciv3::units::Unit)> = Vec::new();
        for __item in (occupants).into_iter() {
            let other = __item;
            let __key = { (other).id };
            __decorated.push((__key, other));
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
    } {
        let mut carrier_kind: crate::openciv3::unit_rules::UnitPrototype =
            rt::at(&(&(&(game).scenario).rules).units, (carrier).prototype)?;
        if ((&(carrier).transported_by).is_none()
            && (crate::openciv3::unit_entry::can_carry(&carrier_kind, &kind)?
                && (((carrier_kind).orders & 256i64) != 0
                    && (crate::openciv3::unit_entry::free_capacity(game, &carrier)? > 0i64))))
        {
            return Ok(Some(AirBase {
                name: (carrier).name.clone(),
                carrier: Some((carrier).id),
            }));
        }
    }
    Ok(None)
}

// Python: openciv3/air_missions.py:59
pub(crate) fn rebase_aircraft(
    mut game: crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<AirBase> {
    let mut base: Option<AirBase> = rebase_destination(&game, &unit, tile)?;
    if (base).is_none() {
        return Err("Choose a friendly air base within rebase range"
            .to_string()
            .into());
    }
    crate::openciv3::unit_missions::clear_unit_missions(game.clone(), unit.clone())?;
    crate::openciv3::worker_jobs::cancel_worker_job(unit.clone())?;
    let mut passengers: Vec<crate::openciv3::units::Unit> =
        crate::openciv3::unit_entry::transported_units(&game, &unit)?;
    for mut moved in {
        let mut __left: Vec<crate::openciv3::units::Unit> = vec![unit.clone()];
        let __right: Vec<crate::openciv3::units::Unit> = passengers;
        __left.extend(__right);
        __left
    } {
        let mut tuple_fields_67_8: (i64, i64) = ((tile).x, (tile).y);
        moved.previous_x = (tuple_fields_67_8).0.clone();
        moved.previous_y = (tuple_fields_67_8).1.clone();
        let mut tuple_fields_68_8: (i64, i64) = ((tile).x, (tile).y);
        moved.x = (tuple_fields_68_8).0.clone();
        moved.y = (tuple_fields_68_8).1.clone();
        moved.facing_override = None;
    }
    unit.transported_by = ((*(base.clone()).as_ref().ok_or("expected a value")?).clone())
        .carrier
        .clone();
    unit.fortified = (((*(base.clone()).as_ref().ok_or("expected a value")?).clone())
        .carrier
        .clone())
    .is_some();
    unit.movement_remaining = 0.0f64;
    game.visibility = {
        let __call_64_0 = &(game).world;
        let __call_64_1 = &(game).cities;
        let __call_64_2 = &(game).units;
        let __call_64_3 = &(&(game).scenario).rules;
        let __call_64_4 = &(game).ownership;
        let __call_64_5 = (game).visibility.clone();
        let __call_64_6 = &(Some((unit).owner));
        let __call_64_default_6 = None;
        crate::openciv3::visibility::update_visibility(
            __call_64_0,
            __call_64_1,
            __call_64_2,
            __call_64_3,
            __call_64_4,
            __call_64_5,
            __call_64_default_6,
            __call_64_6,
        )
    }?;
    Ok((*(base).as_ref().ok_or("expected a value")?).clone())
}
