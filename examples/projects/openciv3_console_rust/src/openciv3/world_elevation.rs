use py2rust_service_runtime as rt;

// Python: openciv3/world_elevation.py:26
pub(crate) fn add_elevation(
    world: &crate::openciv3::world::WorldMap,
    mut age: i64,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    if {
        let __needle = age;
        let __container = {
            static __CONSTANT_py__openciv3__world_elevation__escaped_5f42414e4453:
                std::sync::OnceLock<indexmap::IndexMap<i64, (i64, i64, i64, i64, i64)>> =
                std::sync::OnceLock::new();
            if __CONSTANT_py__openciv3__world_elevation__escaped_5f42414e4453
                .get()
                .is_none()
            {
                let __constant_value = [
                    (3i64, (15i64, 30i64, 60i64, 75i64, 5i64)),
                    (4i64, (20i64, 30i64, 65i64, 75i64, 3i64)),
                    (5i64, (23i64, 30i64, 68i64, 75i64, 1i64)),
                ]
                .into_iter()
                .collect::<indexmap::IndexMap<_, _>>();
                let _ = __CONSTANT_py__openciv3__world_elevation__escaped_5f42414e4453
                    .set(__constant_value);
            }
            __CONSTANT_py__openciv3__world_elevation__escaped_5f42414e4453
                .get()
                .ok_or("missing module constant")?
        };
        !__container.contains_key(&__needle)
    } {
        return Err("Unknown world age".to_string().into());
    }
    let mut heights: crate::strategy::height_map::HeightMap =
        crate::strategy::height_map::HeightMap____post_init__(
            crate::strategy::height_map::HeightMap {
                seed: crate::strategy::random::seed32(
                    ((world).seed)
                        .checked_add(65261i64)
                        .ok_or("integer overflow")?,
                )?,
                width: (world).width,
                height: (world).height,
                scale: 0.2f64,
                wrap_x: true,
                wrap_y: false,
                force_low_poles: true,
                _tiles_per_cell_x: 0.0f64,
                _tiles_per_cell_y: 0.0f64,
                values: vec![],
            },
        )?;
    let mut random: crate::strategy::random::MapRandom =
        crate::strategy::random::MapRandom____post_init__(crate::strategy::random::MapRandom {
            seed: crate::strategy::random::seed32(
                ((world).seed)
                    .checked_add(64206i64)
                    .ok_or("integer overflow")?,
            )?,
            _values: vec![],
            _index: 0i64,
            _other: 21i64,
        })?;
    let (mut hill_low, mut hill_high, mut mountain_low, mut mountain_high, mut volcano_percent): (
        i64,
        i64,
        i64,
        i64,
        i64,
    ) = ({
        static __CONSTANT_py__openciv3__world_elevation__escaped_5f42414e4453: std::sync::OnceLock<
            indexmap::IndexMap<i64, (i64, i64, i64, i64, i64)>,
        > = std::sync::OnceLock::new();
        if __CONSTANT_py__openciv3__world_elevation__escaped_5f42414e4453
            .get()
            .is_none()
        {
            let __constant_value = [
                (3i64, (15i64, 30i64, 60i64, 75i64, 5i64)),
                (4i64, (20i64, 30i64, 65i64, 75i64, 3i64)),
                (5i64, (23i64, 30i64, 68i64, 75i64, 1i64)),
            ]
            .into_iter()
            .collect::<indexmap::IndexMap<_, _>>();
            let _ = __CONSTANT_py__openciv3__world_elevation__escaped_5f42414e4453
                .set(__constant_value);
        }
        __CONSTANT_py__openciv3__world_elevation__escaped_5f42414e4453
            .get()
            .ok_or("missing module constant")?
    })
    .get(&(age))
    .ok_or("missing dict key")?
    .clone();
    (hill_low, hill_high) = (
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, hill_low)?,
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, hill_high)?,
    );
    (mountain_low, mountain_high) = (
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, mountain_low)?,
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, mountain_high)?,
    );
    let mut tiles: Vec<crate::openciv3::world::Tile> =
        (&(world).tiles).iter().cloned().collect::<Vec<_>>();
    for mut for_target_35_4 in (tiles.clone())
        .into_iter()
        .enumerate()
        .map(|(__index, __value)| (__index as i64 + 0i64, __value))
        .collect::<Vec<_>>()
    {
        let (mut index, mut tile): (i64, crate::openciv3::world::Tile) = for_target_35_4;
        if crate::openciv3::hydrology::is_water(&tile)? {
            continue;
        }
        let mut height: i64 =
            crate::strategy::height_map::HeightMap__get_height(&heights, (tile).x, (tile).y)?;
        if {
            let __compare_0 = hill_low;
            let __compare_1 = height;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = hill_high;
                (__compare_1 < __compare_2)
            } else {
                false
            }
        } {
            {
                let __value = {
                    let mut __replacement = (tile.clone()).clone();
                    __replacement.overlay_terrain = 5i64;
                    __replacement
                };
                let __key = index;
                let __index = rt::index(tiles.len(), __key)?;
                tiles[__index] = __value;
            }
        } else {
            if {
                let __compare_0 = mountain_low;
                let __compare_1 = height;
                if (__compare_0 <= __compare_1) {
                    let __compare_2 = mountain_high;
                    (__compare_1 < __compare_2)
                } else {
                    false
                }
            } {
                let mut nearby_volcano: bool = ({
                    let mut __comprehension_result_579: Vec<bool> = Vec::new();
                    let __comprehension_source_578 =
                        (crate::openciv3::world::WorldMap__neighbors(world, &tile)?);
                    for n in __comprehension_source_578.iter().cloned() {
                        __comprehension_result_579.push(
                            (({
                                let __source = &tiles;
                                let __key = (((n).y)
                                    .checked_mul(rt::int_floor_div((world).width, 2i64)?)
                                    .ok_or("integer overflow")?)
                                .checked_add(rt::int_floor_div((n).x, 2i64)?)
                                .ok_or("integer overflow")?;
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .overlay_terrain
                                == 10i64),
                        );
                    }
                    __comprehension_result_579
                })
                .into_iter()
                .any(|__value| __value);
                let mut terrain: i64 = (if (({
                    if !(0..=2147483647i64).contains(&(100i64)) {
                        return Err("Random upper bound must be a nonnegative Int32".into());
                    }
                    let mut __map_random = random.clone();
                    __map_random._index = if __map_random._index < 55 {
                        __map_random._index + 1
                    } else {
                        1
                    };
                    __map_random._other = if __map_random._other < 55 {
                        __map_random._other + 1
                    } else {
                        1
                    };
                    let __sample_index = __map_random._index as usize;
                    let mut __value = (__map_random._values[__sample_index]
                        - __map_random._values[__map_random._other as usize]
                        + 2147483648i64)
                        .rem_euclid(4294967296i64)
                        - 2147483648i64;
                    if __value == 2147483647i64 {
                        __value -= 1;
                    }
                    if __value < 0 {
                        __value += 2147483647i64;
                    }
                    __map_random._values[__sample_index] = __value;
                    random = __map_random;
                    ((__value as f64) * (1.0 / 2147483647.0) * ((100i64) as f64)) as i64
                } < volcano_percent)
                    && !(nearby_volcano))
                {
                    10i64
                } else {
                    6i64
                });
                {
                    let __value = {
                        let mut __replacement = (tile.clone()).clone();
                        __replacement.overlay_terrain = terrain;
                        __replacement
                    };
                    let __key = index;
                    let __index = rt::index(tiles.len(), __key)?;
                    tiles[__index] = __value;
                }
            }
        }
    }
    Ok({
        let mut __replacement = ((*world).clone()).clone();
        __replacement.tiles = (tiles).iter().cloned().collect::<Vec<_>>();
        __replacement
    })
}
