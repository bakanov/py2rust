use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum EntryIntent {
    DISABLED,
    MOVE_FREELY,
    FIGHT,
    LOAD,
    UNLOAD,
    NOTICE_UNIT,
    NOTICE_CITY,
    NOTICE_ALLIANCE,
    WAR_DECLARATION,
}

// Python: openciv3/unit_entry.py:24
pub(crate) fn EntryIntent__peaceful(mut self_: EntryIntent) -> rt::Result<bool> {
    Ok({
        let __needle = self_;
        let __container = &({
            let __tuple_value = &((
                EntryIntent::MOVE_FREELY,
                EntryIntent::LOAD,
                EntryIntent::UNLOAD,
            ));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        __container.contains(&__needle)
    })
}

// Python: openciv3/unit_entry.py:28
pub(crate) fn EntryIntent__enterable(mut self_: EntryIntent) -> rt::Result<bool> {
    Ok((EntryIntent__peaceful(self_.clone())? || (self_.clone() == EntryIntent::FIGHT)))
}

// Python: openciv3/unit_entry.py:32
pub(crate) fn EntryIntent__forceable(mut self_: EntryIntent) -> rt::Result<bool> {
    Ok((EntryIntent__enterable(self_.clone())? || (self_.clone() == EntryIntent::WAR_DECLARATION)))
}

// Python: openciv3/unit_entry.py:36
pub(crate) fn can_defend_on_land(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<bool> {
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    Ok((((unit).hit_points > 0i64)
        && ((&(unit).transported_by).is_none()
            && (((kind).domain == 0i64) && ((kind).defense > 0i64)))))
}

// Python: openciv3/unit_entry.py:41
pub(crate) fn free_capacity(
    game: &crate::openciv3::game_state::GameState,
    transport: &crate::openciv3::units::Unit,
) -> rt::Result<i64> {
    Ok((({
        let __source = &(&(&(game).scenario).rules).units;
        let __key = (transport).prototype;
        &__source[rt::index(__source.len(), __key)?]
    })
    .capacity)
        .checked_sub(
            ({
                let mut __comprehension_result_428: Vec<bool> = Vec::new();
                let __comprehension_source_427 = ((game).units.clone());
                for other in __comprehension_source_427.iter().cloned() {
                    __comprehension_result_428.push(
                        (((other).transported_by.clone() == Some((transport).id))
                            && (((other).x, (other).y) == ((transport).x, (transport).y))),
                    );
                }
                __comprehension_result_428
            })
            .into_iter()
            .map(|value| value as i64)
            .sum::<i64>(),
        )
        .ok_or("integer overflow")?)
}

/// Return direct and nested passengers in parent-before-child order.
// Python: openciv3/unit_entry.py:47
pub(crate) fn transported_units(
    game: &crate::openciv3::game_state::GameState,
    carrier: &crate::openciv3::units::Unit,
) -> rt::Result<Vec<crate::openciv3::units::Unit>> {
    let mut by_carrier: indexmap::IndexMap<i64, Vec<crate::openciv3::units::Unit>> =
        indexmap::IndexMap::<i64, Vec<crate::openciv3::units::Unit>>::new();
    for mut unit in (&(game).units).iter() {
        if (&(unit).transported_by).is_some() {
            by_carrier
                .entry(
                    (*((unit).transported_by.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone(),
                )
                .or_insert_with(Vec::new)
                .push((*unit).clone());
        }
    }
    let mut pending: Vec<crate::openciv3::units::Unit> = {
        let __key = (carrier).id;
        let __default = vec![];
        by_carrier.get(&__key).cloned().unwrap_or(__default)
    };
    let mut passengers: Vec<crate::openciv3::units::Unit> = vec![];
    let mut seen: std::collections::BTreeSet<i64> = {
        let mut __result = std::collections::BTreeSet::new();
        for __item in vec![(carrier).id].into_iter() {
            __result.insert(__item);
        }
        __result
    };
    while (((pending).len() as i64) != 0i64) {
        let mut passenger: crate::openciv3::units::Unit = if (pending).is_empty() {
            return Err("popleft from an empty deque".into());
        } else {
            (pending).remove(0)
        };
        if {
            let __needle = (passenger).id;
            let __container = &seen;
            __container.contains(&__needle)
        } {
            return Err("Invalid transport chain".to_string().into());
        }
        {
            seen.insert((passenger).id);
        };
        {
            passengers.push(passenger.clone());
        };
        {
            let __values = {
                let __key = (passenger).id;
                let __default = vec![];
                by_carrier.get(&__key).cloned().unwrap_or(__default)
            };
            pending.extend(__values);
        };
    }
    Ok((passengers).iter().cloned().collect::<Vec<_>>())
}

// Python: openciv3/unit_entry.py:66
pub(crate) fn can_carry(
    transport: &crate::openciv3::unit_rules::UnitPrototype,
    passenger: &crate::openciv3::unit_rules::UnitPrototype,
) -> rt::Result<bool> {
    if (((passenger).abilities & 8388608i64) != 0i64) {
        return Ok(((transport).abilities & 16777216i64) != 0);
    }
    if ((passenger).domain == 2i64) {
        return Ok(((transport).abilities & 256i64) != 0);
    }
    if ((passenger).domain != 0i64) {
        return Ok(false);
    }
    if (((transport).abilities & 16384i64) != 0i64) {
        return Ok(((passenger).abilities & 2i64) != 0);
    }
    Ok(!(((transport).abilities & (256i64 | 16777216i64)) != 0))
}

// Python: openciv3/unit_entry.py:78
pub(crate) fn transports_to_board(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<Vec<crate::openciv3::units::Unit>> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(rules).units, (unit).prototype)?;
    if ((&(unit).transported_by).is_some()
        || (((kind).domain != 0i64)
            || (!(((kind).orders & 128i64) != 0i64)
                || ({
                    let mut __comprehension_result_430: Vec<bool> = Vec::new();
                    let __comprehension_source_429 = ((game).units.clone());
                    for other in __comprehension_source_429.iter().cloned() {
                        __comprehension_result_430
                            .push(((other).transported_by.clone() == Some((unit).id)));
                    }
                    __comprehension_result_430
                })
                .into_iter()
                .any(|__value| __value))))
    {
        return Ok(vec![]);
    }
    let mut candidates: Vec<crate::openciv3::units::Unit> = {
        let mut __comprehension_result_432: Vec<crate::openciv3::units::Unit> = Vec::new();
        let __comprehension_source_431 = ((game).units.clone());
        for other in __comprehension_source_431.iter().cloned() {
            if (((other).id != (unit).id)
                && (((other).owner == (unit).owner)
                    && (((other).hit_points > 0i64)
                        && ((&(other).transported_by).is_none()
                            && ((((other).x, (other).y) == ((tile).x, (tile).y))
                                && ((({
                                    let __source = &(rules).units;
                                    let __key = (other).prototype;
                                    &__source[rt::index(__source.len(), __key)?]
                                })
                                .capacity
                                    > 0i64)
                                    && ((({
                                        let __source = &(rules).units;
                                        let __key = (other).prototype;
                                        &__source[rt::index(__source.len(), __key)?]
                                    })
                                    .orders
                                        & 256i64)
                                        != 0
                                        && (can_carry(
                                            {
                                                let __source = &(rules).units;
                                                let __key = (other).prototype;
                                                &__source[rt::index(__source.len(), __key)?]
                                            },
                                            &kind,
                                        )? && (free_capacity(game, &other)? > 0i64)))))))))
            {
                __comprehension_result_432.push(other.clone());
            }
        }
        __comprehension_result_432
    };
    Ok({
        let mut __decorated: Vec<((bool, i64, i64), crate::openciv3::units::Unit)> = Vec::new();
        for __item in (candidates).into_iter() {
            let transport = __item;
            let __key = {
                (
                    (free_capacity(game, &transport)?
                        == ({
                            let __source = &(rules).units;
                            let __key = (transport).prototype;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .capacity),
                    (({
                        let __source = &(rules).units;
                        let __key = (transport).prototype;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .capacity)
                        .checked_neg()
                        .ok_or("integer overflow")?,
                    (free_capacity(game, &transport)?)
                        .checked_sub(
                            ({
                                let __source = &(rules).units;
                                let __key = (transport).prototype;
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .capacity,
                        )
                        .ok_or("integer overflow")?,
                )
            };
            __decorated.push((__key, transport));
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
    })
}

/// Resolve the legacy command intent, including human fog-of-war behavior.
///
/// This does not validate adjacency or available movement points: callers also
/// use it to assess distant destinations before constructing paths.
// Python: openciv3/unit_entry.py:98
pub(crate) fn resolve_entry(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    tile: &Option<crate::openciv3::world::Tile>,
    mut respect_fog: bool,
) -> rt::Result<EntryIntent> {
    if (tile).is_none() {
        return Ok(EntryIntent::DISABLED);
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(rules).units, (unit).prototype)?;
    if (((kind).abilities & 1024i64) != 0 || ((kind).domain == 2i64)) {
        return Ok(EntryIntent::DISABLED);
    }
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (unit).owner)?;
    let mut knowledge: crate::openciv3::visibility::TileKnowledge = (&(game).visibility)
        .get(&((unit).owner))
        .ok_or("missing dict key")?
        .clone();
    let mut point: (i64, i64) = (
        ((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()).x,
        ((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()).y,
    );
    if (respect_fog
        && ((player).human && {
            let __needle = point.clone();
            let __container = &(knowledge).known;
            !__container.contains(&__needle)
        }))
    {
        return Ok(EntryIntent::MOVE_FREELY);
    }
    let mut fogged: bool = (respect_fog
        && ((player).human && {
            let __needle = point.clone();
            let __container = &(knowledge).visible;
            !__container.contains(&__needle)
        }));
    let mut terrain_index: i64 = (if fogged {
        {
            let __mapping = &(knowledge).known_terrain;
            let __key = point.clone();
            let __default =
                ((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()).overlay_terrain;
            __mapping.get(&__key).cloned().unwrap_or(__default)
        }
    } else {
        ((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()).overlay_terrain
    });
    let mut terrain: crate::openciv3::rules::Terrain = rt::at(&(rules).terrains, terrain_index)?;
    let mut overlays: i64 = (if fogged {
        {
            let __mapping = &(knowledge).known_overlays;
            let __key = point.clone();
            let __default = 0i64;
            __mapping.get(&__key).cloned().unwrap_or(__default)
        }
    } else {
        ((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()).overlays
    });
    let mut camp: bool = (overlays & 128i64) != 0;
    let mut blocked_for_unit: bool = false;
    if (&(terrain).impassable_to).is_none() {
        blocked_for_unit = ((terrain).impassable_by_wheeled
            && (((kind).abilities & 1i64) != 0 && !((overlays & (1i64 | 2i64)) != 0)));
    } else {
        blocked_for_unit = {
            let __find_source_433 = (*((terrain).impassable_to.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone();
            let mut __find_result_433: bool = false;
            for (ability, allows) in __find_source_433.iter().cloned() {
                if (((kind).abilities & ability) != 0i64) {
                    __find_result_433 = !((overlays & allows) != 0);
                    break;
                }
            }
            __find_result_433
        };
    }
    let mut impassable: bool = ((terrain).impassable || blocked_for_unit);
    if (impassable && !(camp)) {
        return Ok(EntryIntent::DISABLED);
    }
    let mut city: Option<crate::openciv3::cities::City> = {
        let __find_source_434 = (game).cities.clone();
        let mut __find_result_434: Option<crate::openciv3::cities::City> = None;
        for city in __find_source_434.iter().cloned() {
            if (((city).x, (city).y) == point.clone()) {
                __find_result_434 = Some(city.clone());
                break;
            }
        }
        __find_result_434
    };
    let mut land: bool = {
        let __needle =
            ((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()).base_terrain;
        let __container = &({
            let __tuple_value = &((11i64, 12i64, 13i64));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        !__container.contains(&__needle)
    };
    if (((kind).domain == 1i64) && land) {
        return Ok((if ((city).is_some()
            && (((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).owner
                == (unit).owner))
        {
            EntryIntent::MOVE_FREELY
        } else {
            EntryIntent::DISABLED
        }));
    }
    if (!(fogged)
        && (!(land)
            && ((city).is_none()
                && !(transports_to_board(
                    game,
                    unit,
                    &((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()),
                )?)
                .is_empty())))
    {
        return Ok(EntryIntent::LOAD);
    }
    if (((kind).domain == 0i64) && !(land)) {
        return Ok(EntryIntent::DISABLED);
    }
    let mut peaceful_entry: EntryIntent = (if (land && (&(unit).transported_by).is_some()) {
        EntryIntent::UNLOAD
    } else {
        EntryIntent::MOVE_FREELY
    });
    let mut foreign_city: bool = ((city).is_some()
        && (((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).owner != (unit).owner));
    let mut active: bool = {
        let __needle = point.clone();
        let __container = &(knowledge).visible;
        __container.contains(&__needle)
    };
    if fogged {
        return Ok((if foreign_city {
            EntryIntent::DISABLED
        } else {
            peaceful_entry
        }));
    }
    let mut occupants: Vec<crate::openciv3::units::Unit> = {
        let mut __comprehension_result_436: Vec<crate::openciv3::units::Unit> = Vec::new();
        let __comprehension_source_435 = ((game).units.clone());
        for other in __comprehension_source_435.iter().cloned() {
            if (((other).x, (other).y) == point.clone()) {
                __comprehension_result_436.push(other.clone());
            }
        }
        __comprehension_result_436
    };
    let mut foreigners: Vec<crate::openciv3::units::Unit> = {
        let mut __comprehension_result_438: Vec<crate::openciv3::units::Unit> = Vec::new();
        let __comprehension_source_437 = (occupants.clone());
        for other in __comprehension_source_437.iter().cloned() {
            if ((other).owner != (unit).owner) {
                __comprehension_result_438.push(other.clone());
            }
        }
        __comprehension_result_438
    };
    let mut origin: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if (origin).is_none() {
        return Err("Unit is outside the map".to_string().into());
    }
    let mut adjacent: bool = (crate::strategy::grid::distance(
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
            let __structural_value =
                (*(origin.clone()).as_ref().ok_or("expected a value")?).clone();
            crate::strategy::grid::GridPoint {
                x: (__structural_value).x.clone(),
                y: (__structural_value).y.clone(),
            }
        }),
        &({
            let __structural_value =
                (*((*tile).clone()).as_ref().ok_or("expected a value")?).clone();
            crate::strategy::grid::GridPoint {
                x: (__structural_value).x.clone(),
                y: (__structural_value).y.clone(),
            }
        }),
    )? == 1i64);
    if ((player).human
        && ((foreign_city || !(foreigners.clone()).is_empty())
            && (crate::strategy::grid::distance(
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
                    let __structural_value =
                        (*(origin).as_ref().ok_or("expected a value")?).clone();
                    crate::strategy::grid::GridPoint {
                        x: (__structural_value).x.clone(),
                        y: (__structural_value).y.clone(),
                    }
                }),
                &({
                    let __structural_value =
                        (*((*tile).clone()).as_ref().ok_or("expected a value")?).clone();
                    crate::strategy::grid::GridPoint {
                        x: (__structural_value).x.clone(),
                        y: (__structural_value).y.clone(),
                    }
                }),
            )? > 1i64)))
    {
        return Ok(EntryIntent::DISABLED);
    }
    let mut combat: bool = (((kind).attack > 0i64) || ((kind).defense > 0i64));
    if !(combat) {
        if (((foreigners).len() as i64) != 0i64) {
            return Ok(EntryIntent::NOTICE_UNIT);
        }
        if (foreign_city || camp) {
            return Ok(EntryIntent::NOTICE_CITY);
        }
    } else {
        if (({
            let mut __comprehension_result_440: Vec<bool> = Vec::new();
            let __comprehension_source_439 = (foreigners.clone());
            for other in __comprehension_source_439.iter().cloned() {
                __comprehension_result_440.push(crate::openciv3::diplomacy::Diplomacy__at_war(
                    &(game).diplomacy,
                    (unit).owner,
                    (other).owner,
                )?);
            }
            __comprehension_result_440
        })
        .into_iter()
        .any(|__value| __value)
            || ((city).is_some()
                && crate::openciv3::diplomacy::Diplomacy__at_war(
                    &(game).diplomacy,
                    (unit).owner,
                    ((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).owner,
                )?))
        {
            return Ok(EntryIntent::FIGHT);
        }
        let mut foreign_owner: Option<i64> = (if (((foreigners).len() as i64) != 0i64) {
            Some(
                ({
                    let __source = &foreigners;
                    let __key = 0i64;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .owner,
            )
        } else {
            (if (foreign_city && (city).is_some()) {
                Some(((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).owner)
            } else {
                None
            })
        });
        if (foreign_owner).is_some() {
            if adjacent {
                if crate::openciv3::diplomacy::Diplomacy__locked_peace(
                    &(game).diplomacy,
                    (unit).owner,
                    (*(foreign_owner).as_ref().ok_or("expected a value")?).clone(),
                )? {
                    return Ok(EntryIntent::NOTICE_ALLIANCE);
                }
                return Ok(EntryIntent::WAR_DECLARATION);
            }
            if (foreign_city || active) {
                return Ok(EntryIntent::DISABLED);
            }
        }
    }
    if (land
        && ((city).is_none()
            && !({
                let __boolean_123705999055504 = occupants;
                if !(__boolean_123705999055504).is_empty() {
                    transports_to_board(
                        game,
                        unit,
                        &((*((*tile).clone()).as_ref().ok_or("expected a value")?).clone()),
                    )?
                } else {
                    __boolean_123705999055504
                }
            })
            .is_empty()))
    {
        return Ok(EntryIntent::LOAD);
    }
    Ok(peaceful_entry)
}
