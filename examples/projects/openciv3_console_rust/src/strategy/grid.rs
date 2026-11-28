use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct GridPoint {
    pub(crate) x: i64,
    pub(crate) y: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct DistanceMap {
    pub(crate) width: i64,
    pub(crate) height: i64,
    pub(crate) wrap_x: bool,
    pub(crate) wrap_y: bool,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct GridMap {
    pub(crate) width: i64,
    pub(crate) height: i64,
    pub(crate) wrap_x: bool,
    pub(crate) wrap_y: bool,
}

// Python: strategy/grid.py:51
pub(crate) fn axis_delta(
    mut first: i64,
    mut second: i64,
    mut extent: i64,
    mut wrap: bool,
) -> rt::Result<i64> {
    let mut delta: i64 = (first).checked_sub(second).ok_or("integer overflow")?;
    if wrap {
        if (delta > rt::int_floor_div(extent, 2i64)?) {
            delta = (delta).checked_sub(extent).ok_or("integer overflow")?;
        } else {
            if (delta
                < (rt::int_floor_div(extent, 2i64)?)
                    .checked_neg()
                    .ok_or("integer overflow")?)
            {
                delta = (delta).checked_add(extent).ok_or("integer overflow")?;
            }
        }
    }
    Ok(delta)
}

// Python: strategy/grid.py:61
pub(crate) fn distance(
    world: &DistanceMap,
    first: &GridPoint,
    second: &GridPoint,
) -> rt::Result<i64> {
    let mut dx: i64 = (axis_delta((first).x, (second).x, (world).width, (world).wrap_x)?)
        .checked_abs()
        .ok_or("integer overflow")?;
    let mut dy: i64 = (axis_delta((first).y, (second).y, (world).height, (world).wrap_y)?)
        .checked_abs()
        .ok_or("integer overflow")?;
    Ok(rt::int_floor_div(
        (dx).checked_add(dy).ok_or("integer overflow")?,
        2i64,
    )?)
}

// Python: strategy/grid.py:67
pub(crate) fn rank_distance(
    world: &DistanceMap,
    first: &GridPoint,
    second: &GridPoint,
) -> rt::Result<i64> {
    let mut dx: i64 = (axis_delta((first).x, (second).x, (world).width, (world).wrap_x)?)
        .checked_abs()
        .ok_or("integer overflow")?;
    let mut dy: i64 = (axis_delta((first).y, (second).y, (world).height, (world).wrap_y)?)
        .checked_abs()
        .ok_or("integer overflow")?;
    Ok(
        (rt::int_floor_div((dx).checked_add(dy).ok_or("integer overflow")?, 2i64)?)
            .checked_add(rt::int_floor_div(
                ((dx).checked_sub(dy).ok_or("integer overflow")?)
                    .checked_abs()
                    .ok_or("integer overflow")?,
                4i64,
            )?)
            .ok_or("integer overflow")?,
    )
}

// Python: strategy/grid.py:73
pub(crate) fn ring(
    world: &crate::openciv3::world::WorldMap,
    center: &crate::openciv3::world::Tile,
    mut radius: i64,
    mut clockwise: bool,
) -> rt::Result<Vec<crate::openciv3::world::Tile>> {
    let mut yield_values: Vec<crate::openciv3::world::Tile> = vec![];
    "Visit from north, including square corners; skip off-map positions.".to_string();
    if (radius < 0i64) {
        return Err("Ring radius must be nonnegative".to_string().into());
    }
    if (radius == 0i64) {
        {
            yield_values.push((*center).clone());
        };
        return Ok(yield_values);
    }
    let (mut x, mut y): (i64, i64) = (
        (center).x,
        ((center).y)
            .checked_sub((2i64).checked_mul(radius).ok_or("integer overflow")?)
            .ok_or("integer overflow")?,
    );
    let mut directions: ((i64, i64), (i64, i64), (i64, i64), (i64, i64)) = (if clockwise {
        (
            (1i64, 1i64),
            ((1i64).checked_neg().ok_or("integer overflow")?, 1i64),
            (
                (1i64).checked_neg().ok_or("integer overflow")?,
                (1i64).checked_neg().ok_or("integer overflow")?,
            ),
            (1i64, (1i64).checked_neg().ok_or("integer overflow")?),
        )
    } else {
        (
            ((1i64).checked_neg().ok_or("integer overflow")?, 1i64),
            (1i64, 1i64),
            (1i64, (1i64).checked_neg().ok_or("integer overflow")?),
            (
                (1i64).checked_neg().ok_or("integer overflow")?,
                (1i64).checked_neg().ok_or("integer overflow")?,
            ),
        )
    });
    for mut for_target_82_4 in {
        let __tuple_items = directions;
        [
            __tuple_items.0,
            __tuple_items.1,
            __tuple_items.2,
            __tuple_items.3,
        ]
    } {
        let (mut dx, mut dy): (i64, i64) = for_target_82_4;
        for _ in 0i64..(2i64).checked_mul(radius).ok_or("integer overflow")? {
            let mut tile: Option<crate::openciv3::world::Tile> =
                crate::openciv3::world::WorldMap__tile_at(world, x, y)?;
            if (tile).is_some() {
                {
                    yield_values.push((*(tile).as_ref().ok_or("expected a value")?).clone());
                };
            }
            (x, y) = (
                (x).checked_add(dx).ok_or("integer overflow")?,
                (y).checked_add(dy).ok_or("integer overflow")?,
            );
        }
    }
    Ok(yield_values)
}

// Python: strategy/grid.py:90
pub(crate) fn within_rank(
    world: &crate::openciv3::world::WorldMap,
    center: &crate::openciv3::world::Tile,
    mut rank: i64,
) -> rt::Result<Vec<crate::openciv3::world::Tile>> {
    let mut yield_values: Vec<crate::openciv3::world::Tile> = vec![];
    "Spiral order, with duplicate wrapped tiles removed on small maps.".to_string();
    if (rank < 0i64) {
        return Err("Border rank must be nonnegative".to_string().into());
    }
    let mut seen: std::collections::BTreeSet<(i64, i64)> = std::collections::BTreeSet::new();
    for mut radius in 0i64..(rank).checked_add(1i64).ok_or("integer overflow")? {
        for mut tile in ring(world, center, radius, true)? {
            let mut point: (i64, i64) = ((tile).x, (tile).y);
            if ({
                let __needle = point.clone();
                let __container = &seen;
                !__container.contains(&__needle)
            } && (rank_distance(
                &({
                    let __structural_value = (*world).clone();
                    DistanceMap {
                        width: (__structural_value).width.clone(),
                        height: (__structural_value).height.clone(),
                        wrap_x: (__structural_value).wrap_x.clone(),
                        wrap_y: (__structural_value).wrap_y.clone(),
                    }
                }),
                &({
                    let __structural_value = (*center).clone();
                    GridPoint {
                        x: (__structural_value).x.clone(),
                        y: (__structural_value).y.clone(),
                    }
                }),
                &({
                    let __structural_value = tile.clone();
                    GridPoint {
                        x: (__structural_value).x.clone(),
                        y: (__structural_value).y.clone(),
                    }
                }),
            )? <= rank))
            {
                {
                    seen.insert(point);
                };
                {
                    yield_values.push(tile);
                };
            }
        }
    }
    Ok(yield_values)
}
