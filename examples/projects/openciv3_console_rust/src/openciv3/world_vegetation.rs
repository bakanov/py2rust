use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum Climate {
    ARID,
    NORMAL,
    WET,
}

#[derive(Clone, PartialEq)]
pub(crate) struct VegetationRules {
    pub(crate) forest: std::collections::BTreeSet<i64>,
    pub(crate) jungle: std::collections::BTreeSet<i64>,
    pub(crate) marsh: std::collections::BTreeSet<i64>,
}

// Python: openciv3/world_vegetation.py:37
pub(crate) fn add_vegetation(
    world: &crate::openciv3::world::WorldMap,
    mut climate: Climate,
    rules: &VegetationRules,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    if {
        let __needle = climate.clone();
        let __container = {
            static __CONSTANT_py__openciv3__world_vegetation__escaped_5f42414e4453:
                std::sync::OnceLock<indexmap::IndexMap<Climate, (i64, i64, i64, i64, i64)>> =
                std::sync::OnceLock::new();
            if __CONSTANT_py__openciv3__world_vegetation__escaped_5f42414e4453
                .get()
                .is_none()
            {
                let __constant_value = [
                    (Climate::ARID, (20i64, 70i64, 10i64, 20i64, 56i64)),
                    (Climate::NORMAL, (23i64, 65i64, 20i64, 28i64, 58i64)),
                    (Climate::WET, (30i64, 60i64, 30i64, 35i64, 60i64)),
                ]
                .into_iter()
                .collect::<indexmap::IndexMap<_, _>>();
                let _ = __CONSTANT_py__openciv3__world_vegetation__escaped_5f42414e4453
                    .set(__constant_value);
            }
            __CONSTANT_py__openciv3__world_vegetation__escaped_5f42414e4453
                .get()
                .ok_or("missing module constant")?
        };
        !__container.contains_key(&__needle)
    } {
        return Err("Unknown climate".to_string().into());
    }
    let (
        mut latitude_limit,
        mut forest_low,
        mut forest_probability,
        mut jungle_high,
        mut marsh_high,
    ): (i64, i64, i64, i64, i64) = ({
        static __CONSTANT_py__openciv3__world_vegetation__escaped_5f42414e4453:
            std::sync::OnceLock<indexmap::IndexMap<Climate, (i64, i64, i64, i64, i64)>> =
            std::sync::OnceLock::new();
        if __CONSTANT_py__openciv3__world_vegetation__escaped_5f42414e4453
            .get()
            .is_none()
        {
            let __constant_value = [
                (Climate::ARID, (20i64, 70i64, 10i64, 20i64, 56i64)),
                (Climate::NORMAL, (23i64, 65i64, 20i64, 28i64, 58i64)),
                (Climate::WET, (30i64, 60i64, 30i64, 35i64, 60i64)),
            ]
            .into_iter()
            .collect::<indexmap::IndexMap<_, _>>();
            let _ = __CONSTANT_py__openciv3__world_vegetation__escaped_5f42414e4453
                .set(__constant_value);
        }
        __CONSTANT_py__openciv3__world_vegetation__escaped_5f42414e4453
            .get()
            .ok_or("missing module constant")?
    })
    .get(&(climate))
    .ok_or("missing dict key")?
    .clone();
    let mut heights: crate::strategy::height_map::HeightMap =
        crate::strategy::height_map::HeightMap____post_init__(
            crate::strategy::height_map::HeightMap {
                seed: crate::strategy::random::seed32(
                    ((world).seed)
                        .checked_add(703710i64)
                        .ok_or("integer overflow")?,
                )?,
                width: (world).width,
                height: (world).height,
                scale: 0.3f64,
                wrap_x: true,
                wrap_y: false,
                force_low_poles: true,
                _tiles_per_cell_x: 0.0f64,
                _tiles_per_cell_y: 0.0f64,
                values: vec![],
            },
        )?;
    let (mut forest_low, mut forest_high): (i64, i64) = (
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, forest_low)?,
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, 93i64)?,
    );
    let (mut jungle_low, mut jungle_high): (i64, i64) = (
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, 15i64)?,
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, jungle_high)?,
    );
    let (mut marsh_low, mut marsh_high): (i64, i64) = (
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, 55i64)?,
        crate::strategy::height_map::HeightMap__find_sea_level(&heights, marsh_high)?,
    );
    let mut random: crate::strategy::random::MapRandom =
        crate::strategy::random::MapRandom____post_init__(crate::strategy::random::MapRandom {
            seed: crate::strategy::random::seed32(
                ((world).seed)
                    .checked_add(58795i64)
                    .ok_or("integer overflow")?,
            )?,
            _values: vec![],
            _index: 0i64,
            _other: 21i64,
        })?;
    let mut tiles: Vec<crate::openciv3::world::Tile> =
        (&(world).tiles).iter().cloned().collect::<Vec<_>>();
    for mut for_target_48_4 in (tiles.clone())
        .into_iter()
        .enumerate()
        .map(|(__index, __value)| (__index as i64 + 0i64, __value))
        .collect::<Vec<_>>()
    {
        let (mut index, mut tile): (i64, crate::openciv3::world::Tile) = for_target_48_4;
        if (crate::openciv3::hydrology::is_water(&tile)? || {
            let __needle = (tile).overlay_terrain;
            let __container = &({
                let __tuple_value = &((5i64, 6i64, 10i64));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                ]
            });
            __container.contains(&__needle)
        }) {
            continue;
        }
        let mut height: i64 =
            crate::strategy::height_map::HeightMap__get_height(&heights, (tile).x, (tile).y)?;
        let mut latitude: f64 = rt::finite(
            (rt::finite(
                90.0f64
                    - rt::finite(
                        rt::float_true_div(
                            (((tile).y) as f64),
                            rt::finite((((world).height) as f64) - 1.0f64)?,
                        )? * 180.0f64,
                    )?,
            )?)
            .abs(),
        )?;
        if ({
            let __compare_0 = forest_low;
            let __compare_1 = height;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = forest_high;
                (__compare_1 < __compare_2)
            } else {
                false
            }
        } && (({
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
        } < forest_probability)
            && {
                let __needle = (tile).base_terrain;
                let __container = &(rules).forest;
                __container.contains(&__needle)
            }))
        {
            let mut pine: bool = (((tile).base_terrain == 3i64)
                || ({
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
                    (__value as f64) * (1.0 / 2147483647.0)
                } > 0.6f64));
            {
                let __value = {
                    let mut __replacement = (tile.clone()).clone();
                    __replacement.overlay_terrain = 7i64;
                    __replacement.bonuses = ((tile).bonuses
                        | (if pine {
                            rt::int_lshift(1i64, 5i64)?
                        } else {
                            0i64
                        }));
                    __replacement
                };
                let __key = index;
                let __index = rt::index(tiles.len(), __key)?;
                tiles[__index] = __value;
            }
        } else {
            if ({
                let __compare_0 = jungle_low;
                let __compare_1 = height;
                if (__compare_0 <= __compare_1) {
                    let __compare_2 = jungle_high;
                    (__compare_1 < __compare_2)
                } else {
                    false
                }
            } && ((latitude < ((latitude_limit) as f64)) && {
                let __needle = (tile).base_terrain;
                let __container = &(rules).jungle;
                __container.contains(&__needle)
            })) {
                {
                    let __value = {
                        let mut __replacement = (tile.clone()).clone();
                        __replacement.overlay_terrain = 8i64;
                        __replacement
                    };
                    let __key = index;
                    let __index = rt::index(tiles.len(), __key)?;
                    tiles[__index] = __value;
                }
            } else {
                if ({
                    let __compare_0 = marsh_low;
                    let __compare_1 = height;
                    if (__compare_0 <= __compare_1) {
                        let __compare_2 = marsh_high;
                        (__compare_1 < __compare_2)
                    } else {
                        false
                    }
                } && {
                    let __needle = (tile).base_terrain;
                    let __container = &(rules).marsh;
                    __container.contains(&__needle)
                }) {
                    {
                        let __value = {
                            let mut __replacement = (tile.clone()).clone();
                            __replacement.overlay_terrain = 9i64;
                            __replacement
                        };
                        let __key = index;
                        let __index = rt::index(tiles.len(), __key)?;
                        tiles[__index] = __value;
                    }
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
