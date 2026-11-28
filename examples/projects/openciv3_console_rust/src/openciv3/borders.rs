use py2rust_service_runtime as rt;

// Python: openciv3/borders.py:9
pub(crate) fn expansion_level(city: &crate::openciv3::cities::City) -> rt::Result<i64> {
    let mut culture: i64 = (1i64).max({
        let __mapping = &(city).culture;
        let __key = (city).owner;
        let __default = 0i64;
        __mapping.get(&__key).cloned().unwrap_or(__default)
    });
    let mut level: i64 = 1i64;
    while (culture >= 10i64) {
        culture = rt::int_floor_div(culture, 10i64)?;
        level = (level).checked_add(1i64).ok_or("integer overflow")?;
    }
    Ok(level)
}

// Python: openciv3/borders.py:19
pub(crate) fn city_tile(
    world: &crate::openciv3::world::WorldMap,
    city: &crate::openciv3::cities::City,
) -> rt::Result<crate::openciv3::world::Tile> {
    let mut tile: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(world, (city).x, (city).y)?;
    if (tile).is_none() {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "City ".to_string(),
                ((city).id).to_string(),
                " is outside the map".to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok((*(tile).as_ref().ok_or("expected a value")?).clone())
}

// Python: openciv3/borders.py:26
pub(crate) fn natural_claims(
    world: &crate::openciv3::world::WorldMap,
    city: &crate::openciv3::cities::City,
    mut ocean_terrain: i64,
) -> rt::Result<Vec<crate::openciv3::world::Tile>> {
    let mut yield_values: Vec<crate::openciv3::world::Tile> = vec![];
    let mut center: crate::openciv3::world::Tile = city_tile(world, city)?;
    for mut tile in crate::strategy::grid::within_rank(
        &((*world).clone()),
        &(center.clone()),
        expansion_level(city)?,
    )? {
        if (((tile).base_terrain != ocean_terrain)
            || (crate::strategy::grid::rank_distance(
                &({
                    let __structural_value = (*world).clone();
                    crate::strategy::grid::DistanceMap {
                        width: (__structural_value).width.clone(),
                        height: (__structural_value).height.clone(),
                        wrap_x: (__structural_value).wrap_x.clone(),
                        wrap_y: (__structural_value).wrap_y.clone(),
                    }
                }),
                &({
                    let __structural_value = center.clone();
                    crate::strategy::grid::GridPoint {
                        x: (__structural_value).x.clone(),
                        y: (__structural_value).y.clone(),
                    }
                }),
                &({
                    let __structural_value = tile.clone();
                    crate::strategy::grid::GridPoint {
                        x: (__structural_value).x.clone(),
                        y: (__structural_value).y.clone(),
                    }
                }),
            )? <= 2i64))
        {
            {
                yield_values.push(tile);
            };
        }
    }
    Ok(yield_values)
}

/// Match GameData.ResolveTileOwnershipConflict, including north/CCW ties.
///
/// Culture rates must include effective buildings and any culture production;
/// callers supply them rather than substituting raw building totals here.
// Python: openciv3/borders.py:33
pub(crate) fn resolve_claim(
    world: &crate::openciv3::world::WorldMap,
    first: &crate::openciv3::cities::City,
    second: &crate::openciv3::cities::City,
    disputed: &crate::openciv3::world::Tile,
    culture_per_turn: &indexmap::IndexMap<i64, i64>,
) -> rt::Result<crate::openciv3::cities::City> {
    if ((first).id == (second).id) {
        return Ok((*first).clone());
    }
    let (mut a, mut b): (crate::openciv3::world::Tile, crate::openciv3::world::Tile) =
        (city_tile(world, first)?, city_tile(world, second)?);
    let (mut a_rank, mut b_rank): (i64, i64) = (
        crate::strategy::grid::rank_distance(
            &({
                let __structural_value = (*world).clone();
                crate::strategy::grid::DistanceMap {
                    width: (__structural_value).width.clone(),
                    height: (__structural_value).height.clone(),
                    wrap_x: (__structural_value).wrap_x.clone(),
                    wrap_y: (__structural_value).wrap_y.clone(),
                }
            }),
            &({
                let __structural_value = a.clone();
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
            &({
                let __structural_value = (*disputed).clone();
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
        )?,
        crate::strategy::grid::rank_distance(
            &({
                let __structural_value = (*world).clone();
                crate::strategy::grid::DistanceMap {
                    width: (__structural_value).width.clone(),
                    height: (__structural_value).height.clone(),
                    wrap_x: (__structural_value).wrap_x.clone(),
                    wrap_y: (__structural_value).wrap_y.clone(),
                }
            }),
            &({
                let __structural_value = b.clone();
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
            &({
                let __structural_value = (*disputed).clone();
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
        )?,
    );
    let mut a_in_range: bool = (a_rank
        <= (expansion_level(first)?)
            .checked_add(1i64)
            .ok_or("integer overflow")?);
    let mut b_in_range: bool = (b_rank
        <= (expansion_level(second)?)
            .checked_add(1i64)
            .ok_or("integer overflow")?);
    if (a_in_range != b_in_range) {
        return Ok((if a_in_range {
            (*first).clone()
        } else {
            (*second).clone()
        }));
    }
    if (a_rank != b_rank) {
        return Ok((if (a_rank < b_rank) {
            (*first).clone()
        } else {
            (*second).clone()
        }));
    }
    let mut a_culture: i64 = ({
        let __mapping = &(first).culture;
        let __key = (first).owner;
        let __default = 0i64;
        __mapping.get(&__key).cloned().unwrap_or(__default)
    })
    .checked_add(
        (culture_per_turn)
            .get(&((first).id))
            .ok_or("missing dict key")?
            .clone(),
    )
    .ok_or("integer overflow")?;
    let mut b_culture: i64 = ({
        let __mapping = &(second).culture;
        let __key = (second).owner;
        let __default = 0i64;
        __mapping.get(&__key).cloned().unwrap_or(__default)
    })
    .checked_add(
        (culture_per_turn)
            .get(&((second).id))
            .ok_or("missing dict key")?
            .clone(),
    )
    .ok_or("integer overflow")?;
    if (a_culture != b_culture) {
        return Ok((if (a_culture > b_culture) {
            (*first).clone()
        } else {
            (*second).clone()
        }));
    }
    let (mut a_ring, mut b_ring): (i64, i64) = (
        crate::strategy::grid::distance(
            &({
                let __structural_value = (*world).clone();
                crate::strategy::grid::DistanceMap {
                    width: (__structural_value).width.clone(),
                    height: (__structural_value).height.clone(),
                    wrap_x: (__structural_value).wrap_x.clone(),
                    wrap_y: (__structural_value).wrap_y.clone(),
                }
            }),
            &({
                let __structural_value = (*disputed).clone();
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
            &({
                let __structural_value = a.clone();
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
        )?,
        crate::strategy::grid::distance(
            &({
                let __structural_value = (*world).clone();
                crate::strategy::grid::DistanceMap {
                    width: (__structural_value).width.clone(),
                    height: (__structural_value).height.clone(),
                    wrap_x: (__structural_value).wrap_x.clone(),
                    wrap_y: (__structural_value).wrap_y.clone(),
                }
            }),
            &({
                let __structural_value = (*disputed).clone();
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
            &({
                let __structural_value = b.clone();
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
        )?,
    );
    for mut radius in (a_ring).min(b_ring)
        ..((a_ring).max(b_ring))
            .checked_add(1i64)
            .ok_or("integer overflow")?
    {
        if (radius <= 0i64) {
            continue;
        }
        for mut tile in {
            let __call_107_0 = world;
            let __call_107_1 = disputed;
            let __call_107_2 = radius;
            let __call_107_3 = false;
            crate::strategy::grid::ring(__call_107_0, __call_107_1, __call_107_2, __call_107_3)
        }? {
            if (tile.clone() == a.clone()) {
                return Ok((*first).clone());
            }
            if (tile == b.clone()) {
                return Ok((*second).clone());
            }
        }
    }
    Ok((if ((first).id < (second).id) {
        (*first).clone()
    } else {
        (*second).clone()
    }))
}

/// Initialize natural claims and opposing-edge gap claims for a fresh map.
///
/// Explored terrain and unit visibility are separate from ownership. Every gap
/// candidate is adjacent to a claim, and thus visible from claimed territory.
// Python: openciv3/borders.py:67
pub(crate) fn calculate_ownership(
    world: &crate::openciv3::world::WorldMap,
    cities: &[crate::openciv3::cities::City],
    mut ocean_terrain: i64,
    culture_per_turn: &indexmap::IndexMap<i64, i64>,
) -> rt::Result<indexmap::IndexMap<(i64, i64), i64>> {
    let mut active: indexmap::IndexMap<i64, crate::openciv3::cities::City> = {
        let mut __comprehension_result_109: indexmap::IndexMap<i64, crate::openciv3::cities::City> =
            indexmap::IndexMap::new();
        let __comprehension_source_108 = (cities.to_vec());
        for city in __comprehension_source_108.iter().cloned() {
            if (crate::openciv3::cities::City__size(&city)? > 0i64) {
                {
                    let (__key, __value) = ((city).id, city.clone());
                    __comprehension_result_109.insert(__key, __value);
                }
            }
        }
        __comprehension_result_109
    };
    let mut owners: indexmap::IndexMap<(i64, i64), i64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut city in (active.clone()).values().cloned().collect::<Vec<_>>() {
        let mut center: crate::openciv3::world::Tile = city_tile(world, &city)?;
        {
            let __value = (city).id;
            let __key = ((center).x, (center).y);
            owners.insert(__key, __value);
        }
        for mut tile in natural_claims(world, &city, ocean_terrain)? {
            let mut point: (i64, i64) = ((tile).x, (tile).y);
            let mut previous: Option<i64> = (owners.clone()).get(&(point.clone())).cloned();
            {
                let __value = (if (previous).is_none() {
                    (city).id
                } else {
                    (resolve_claim(
                        world,
                        (active)
                            .get(
                                &((*(previous.clone()).as_ref().ok_or("expected a value")?)
                                    .clone()),
                            )
                            .ok_or("missing dict key")?,
                        &city,
                        &tile,
                        culture_per_turn,
                    )?)
                    .id
                });
                let __key = point.clone();
                owners.insert(__key, __value);
            }
        }
    }
    let mut candidates: indexmap::IndexMap<(i64, i64), crate::openciv3::world::Tile> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut for_target_87_4 in (owners).keys() {
        let (mut x, mut y): (i64, i64) = (*for_target_87_4).clone();
        let mut claimed_tile: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(world, x, y)?;
        if !((claimed_tile).is_some()) {
            rt::assertion(false, &("".to_string()))?;
        }
        for mut neighbor in crate::openciv3::world::WorldMap__neighbors(
            world,
            &((*(claimed_tile).as_ref().ok_or("expected a value")?).clone()),
        )? {
            let mut point: (i64, i64) = ((neighbor).x, (neighbor).y);
            if {
                let __needle = point.clone();
                let __container = &owners;
                !__container.contains_key(&__needle)
            } {
                {
                    let __value = neighbor;
                    let __key = point.clone();
                    candidates.insert(__key, __value);
                }
            }
        }
    }
    for mut for_target_94_4 in (candidates)
        .iter()
        .map(|(__key, __value)| (__key.clone(), __value.clone()))
        .collect::<Vec<_>>()
    {
        let (mut point, mut tile): ((i64, i64), crate::openciv3::world::Tile) = for_target_94_4;
        for mut dx in {
            let __tuple_items = ((1i64).checked_neg().ok_or("integer overflow")?, 1i64);
            [__tuple_items.0, __tuple_items.1]
        } {
            let mut a: Option<crate::openciv3::world::Tile> =
                crate::openciv3::world::WorldMap__tile_at(
                    world,
                    ((tile).x).checked_add(dx).ok_or("integer overflow")?,
                    ((tile).y).checked_sub(1i64).ok_or("integer overflow")?,
                )?;
            let mut b: Option<crate::openciv3::world::Tile> =
                crate::openciv3::world::WorldMap__tile_at(
                    world,
                    ((tile).x).checked_sub(dx).ok_or("integer overflow")?,
                    ((tile).y).checked_add(1i64).ok_or("integer overflow")?,
                )?;
            if ((a).is_none() || (b).is_none()) {
                continue;
            }
            let (mut a_owner, mut b_owner): (Option<i64>, Option<i64>) = (
                (owners.clone())
                    .get(
                        &((
                            ((*(a.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                            ((*(a.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                        )),
                    )
                    .cloned(),
                (owners.clone())
                    .get(
                        &((
                            ((*(b.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                            ((*(b.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                        )),
                    )
                    .cloned(),
            );
            if ((a_owner).is_none() || (b_owner).is_none()) {
                continue;
            }
            let (mut first, mut second): (
                crate::openciv3::cities::City,
                crate::openciv3::cities::City,
            ) = (
                (active)
                    .get(&((*(a_owner.clone()).as_ref().ok_or("expected a value")?).clone()))
                    .ok_or("missing dict key")?
                    .clone(),
                (active)
                    .get(&((*(b_owner.clone()).as_ref().ok_or("expected a value")?).clone()))
                    .ok_or("missing dict key")?
                    .clone(),
            );
            if ((first).owner != (second).owner) {
                continue;
            }
            let mut winner: crate::openciv3::cities::City =
                resolve_claim(world, &first, &second, &tile, culture_per_turn)?;
            if (((tile).base_terrain == ocean_terrain)
                && (crate::strategy::grid::rank_distance(
                    &({
                        let __structural_value = (*world).clone();
                        crate::strategy::grid::DistanceMap {
                            width: (__structural_value).width.clone(),
                            height: (__structural_value).height.clone(),
                            wrap_x: (__structural_value).wrap_x.clone(),
                            wrap_y: (__structural_value).wrap_y.clone(),
                        }
                    }),
                    &({
                        let __structural_value = tile.clone();
                        crate::strategy::grid::GridPoint {
                            x: (__structural_value).x.clone(),
                            y: (__structural_value).y.clone(),
                        }
                    }),
                    &({
                        let __structural_value = city_tile(world, &winner)?;
                        crate::strategy::grid::GridPoint {
                            x: (__structural_value).x.clone(),
                            y: (__structural_value).y.clone(),
                        }
                    }),
                )? > 2i64))
            {
                continue;
            }
            {
                let __value = (winner).id;
                let __key = point.clone();
                owners.insert(__key, __value);
            }
            break;
        }
    }
    Ok(owners)
}
