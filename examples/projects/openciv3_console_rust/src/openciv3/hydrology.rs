use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct Hydrology {
    pub(crate) freshwater: std::collections::BTreeSet<(i64, i64)>,
}

// Python: openciv3/hydrology.py:10
pub(crate) fn is_water(tile: &crate::openciv3::world::Tile) -> rt::Result<bool> {
    Ok({
        let __needle = (tile).base_terrain;
        let __container = &({
            let __tuple_value = &((11i64, 12i64, 13i64));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        __container.contains(&__needle)
    })
}

// Python: openciv3/hydrology.py:14
pub(crate) fn land_strip(
    world: &crate::openciv3::world::WorldMap,
    first: &crate::openciv3::world::Tile,
    second: &crate::openciv3::world::Tile,
) -> rt::Result<bool> {
    let mut tile: Option<crate::openciv3::world::Tile>;
    if (!(is_water(first)?) || !(is_water(second)?)) {
        return Ok(false);
    }
    let mut dx: i64 =
        crate::strategy::grid::axis_delta((second).x, (first).x, (world).width, (world).wrap_x)?;
    let mut dy: i64 =
        crate::strategy::grid::axis_delta((second).y, (first).y, (world).height, (world).wrap_y)?;
    let mut sides: Vec<(i64, i64)> = vec![];
    if ((dx == 0i64) && ((dy).checked_abs().ok_or("integer overflow")? == 2i64)) {
        sides = vec![
            (
                (1i64).checked_neg().ok_or("integer overflow")?,
                rt::int_floor_div(dy, 2i64)?,
            ),
            (1i64, rt::int_floor_div(dy, 2i64)?),
        ];
    } else {
        if ((dy == 0i64) && ((dx).checked_abs().ok_or("integer overflow")? == 2i64)) {
            sides = vec![
                (
                    rt::int_floor_div(dx, 2i64)?,
                    (1i64).checked_neg().ok_or("integer overflow")?,
                ),
                (rt::int_floor_div(dx, 2i64)?, 1i64),
            ];
        } else {
            return Ok(false);
        }
    }
    Ok(({
        let mut __comprehension_result_306: Vec<bool> = Vec::new();
        let mut tile: Option<crate::openciv3::world::Tile>;
        let __comprehension_source_305 = (sides.clone());
        for (x, y) in __comprehension_source_305.iter().cloned() {
            __comprehension_result_306.push(
                (({
                    tile = crate::openciv3::world::WorldMap__tile_at(
                        world,
                        ((first).x).checked_add(x).ok_or("integer overflow")?,
                        ((first).y).checked_add(y).ok_or("integer overflow")?,
                    )?;
                    tile.clone()
                })
                .is_some()
                    && !(is_water(
                        &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
                    )?)),
            );
        }
        __comprehension_result_306
    })
    .into_iter()
    .all(|__value| __value))
}

// Python: openciv3/hydrology.py:30
pub(crate) fn river_edges(
    world: &crate::openciv3::world::WorldMap,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<i64> {
    let mut edges: i64 = ((tile).river_connections & 170i64);
    let mut checks: (
        (i64, i64, i64, i64, i64, i64, i64),
        (i64, i64, i64, i64, i64, i64, i64),
        (i64, i64, i64, i64, i64, i64, i64),
        (i64, i64, i64, i64, i64, i64, i64),
    ) = (
        (
            0i64,
            (2i64).checked_neg().ok_or("integer overflow")?,
            0i64,
            7i64,
            5i64,
            1i64,
            3i64,
        ),
        (2i64, 0i64, 2i64, 1i64, 7i64, 3i64, 5i64),
        (0i64, 2i64, 4i64, 5i64, 7i64, 3i64, 1i64),
        (
            (2i64).checked_neg().ok_or("integer overflow")?,
            0i64,
            6i64,
            7i64,
            1i64,
            5i64,
            3i64,
        ),
    );
    for mut for_target_35_4 in {
        let __tuple_items = checks;
        [
            __tuple_items.0,
            __tuple_items.1,
            __tuple_items.2,
            __tuple_items.3,
        ]
    } {
        let (mut dx, mut dy, mut bit, mut a, mut b, mut c, mut d): (
            i64,
            i64,
            i64,
            i64,
            i64,
            i64,
            i64,
        ) = for_target_35_4;
        let mut neighbor: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(
                world,
                ((tile).x).checked_add(dx).ok_or("integer overflow")?,
                ((tile).y).checked_add(dy).ok_or("integer overflow")?,
            )?;
        if ((neighbor).is_some()
            && ({
                let __boolean_123705987218448 = {
                    let __boolean_123705987287248 = (edges & rt::int_lshift(1i64, a)?);
                    if (__boolean_123705987287248) != 0 {
                        __boolean_123705987287248
                    } else {
                        (((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone())
                            .river_connections
                            & rt::int_lshift(1i64, b)?)
                    }
                };
                if (__boolean_123705987218448) != 0 {
                    {
                        let __boolean_123705987217936 = (edges & rt::int_lshift(1i64, c)?);
                        if (__boolean_123705987217936) != 0 {
                            __boolean_123705987217936
                        } else {
                            (((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone())
                                .river_connections
                                & rt::int_lshift(1i64, d)?)
                        }
                    }
                } else {
                    __boolean_123705987218448
                }
            }) != 0)
        {
            edges = (edges | rt::int_lshift(1i64, bit)?);
        }
    }
    Ok(edges)
}

// Python: openciv3/hydrology.py:48
pub(crate) fn Hydrology__from_world(
    world: &crate::openciv3::world::WorldMap,
) -> rt::Result<Hydrology> {
    let mut remaining: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_308: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_307 = ((world).tiles.clone());
        for tile in __comprehension_source_307.iter().cloned() {
            if is_water(&tile)? {
                __comprehension_result_308.insert(((tile).x, (tile).y));
            }
        }
        __comprehension_result_308
    };
    let mut fresh: std::collections::BTreeSet<(i64, i64)> = std::collections::BTreeSet::new();
    while (((remaining).len() as i64) != 0i64) {
        let mut origin: (i64, i64) = (remaining).pop_first().ok_or("pop from an empty set")?;
        let mut body: std::collections::BTreeSet<(i64, i64)> = {
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![origin.clone()].into_iter() {
                __result.insert(__item);
            }
            __result
        };
        let mut pending: Vec<(i64, i64)> = vec![origin];
        while (((pending).len() as i64) != 0i64) {
            let mut point: (i64, i64) = {
                let __key = -1i64;
                let __index = rt::index(pending.len(), __key)?;
                pending.remove(__index)
            };
            let mut tile: Option<crate::openciv3::world::Tile> = {
                let __star_args_309: Vec<i64> = {
                    let __tuple_value = &point;
                    vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                };
                if !(2..=2).contains(&__star_args_309.len()) {
                    return Err("wrong function argument count".into());
                }
                crate::openciv3::world::WorldMap__tile_at(
                    world,
                    rt::at(&__star_args_309, 0 as i64)?,
                    rt::at(&__star_args_309, 1 as i64)?,
                )?
            };
            if !((tile).is_some()) {
                rt::assertion(false, &("".to_string()))?;
            }
            for mut neighbor in crate::openciv3::world::WorldMap__neighbors(
                world,
                &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
            )? {
                let mut other: (i64, i64) = ((neighbor).x, (neighbor).y);
                if ({
                    let __needle = other.clone();
                    let __container = &remaining;
                    __container.contains(&__needle)
                } && !(land_strip(
                    world,
                    &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
                    &neighbor,
                )?)) {
                    if !(remaining).remove(&(other.clone())) {
                        return Err("set.remove: missing item".into());
                    };
                    {
                        body.insert(other.clone());
                    };
                    {
                        pending.push(other);
                    };
                }
            }
        }
        if (((body).len() as i64) <= 20i64) {
            (fresh).extend(body);
        }
    }
    for mut tile in (&(world).tiles).iter() {
        if (!(is_water(tile)?) || (&(tile).freshwater).is_none()) {
            continue;
        }
        let mut point: (i64, i64) = ((tile).x, (tile).y);
        if ((tile).freshwater.clone()).is_some() {
            {
                fresh.insert(point);
            };
        } else {
            (fresh).remove(&(point));
        }
    }
    Ok(Hydrology {
        freshwater: {
            let mut __result: std::collections::BTreeSet<(i64, i64)> =
                std::collections::BTreeSet::new();
            for __item in (fresh).into_iter() {
                __result.insert(__item);
            }
            __result
        },
    })
}

// Python: openciv3/hydrology.py:77
pub(crate) fn Hydrology__fresh_access(
    self_: &Hydrology,
    world: &crate::openciv3::world::WorldMap,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<bool> {
    Ok(((river_edges(world, tile)?) != 0
        || ({
            let mut __comprehension_result_311: Vec<bool> = Vec::new();
            let __comprehension_source_310 =
                (crate::openciv3::world::WorldMap__neighbors(world, tile)?);
            for n in __comprehension_source_310.iter().cloned() {
                __comprehension_result_311.push({
                    let __needle = ((n).x, (n).y);
                    let __container = &(self_).freshwater;
                    __container.contains(&__needle)
                });
            }
            __comprehension_result_311
        })
        .into_iter()
        .any(|__value| __value)))
}

// Python: openciv3/hydrology.py:80
pub(crate) fn Hydrology__coastal(
    self_: &Hydrology,
    world: &crate::openciv3::world::WorldMap,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<bool> {
    Ok(({
        let mut __comprehension_result_313: Vec<bool> = Vec::new();
        let __comprehension_source_312 =
            (crate::openciv3::world::WorldMap__neighbors(world, tile)?);
        for n in __comprehension_source_312.iter().cloned() {
            __comprehension_result_313.push(
                (is_water(&n)? && {
                    let __needle = ((n).x, (n).y);
                    let __container = &(self_).freshwater;
                    !__container.contains(&__needle)
                }),
            );
        }
        __comprehension_result_313
    })
    .into_iter()
    .any(|__value| __value))
}
