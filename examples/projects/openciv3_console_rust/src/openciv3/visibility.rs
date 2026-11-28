use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct TileKnowledge {
    pub(crate) known: std::collections::BTreeSet<(i64, i64)>,
    pub(crate) visible: std::collections::BTreeSet<(i64, i64)>,
    pub(crate) frontier: std::collections::BTreeSet<(i64, i64)>,
    pub(crate) known_overlays: indexmap::IndexMap<(i64, i64), i64>,
    pub(crate) known_ruins: std::collections::BTreeSet<(i64, i64)>,
    pub(crate) exploration_targets: indexmap::IndexMap<i64, (i64, i64)>,
    pub(crate) fully_explored_oceans: bool,
    pub(crate) known_terrain: indexmap::IndexMap<(i64, i64), i64>,
}

// Python: openciv3/visibility.py:18
pub(crate) fn _height(
    tile: &crate::openciv3::world::Tile,
    terrains: &[crate::openciv3::rules::Terrain],
) -> rt::Result<i64> {
    let mut index: i64 = (tile).overlay_terrain;
    if {
        let __compare_0 = 0i64;
        let __compare_1 = index;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = ((terrains).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    } {
        let mut height: Option<i64> = ({
            let __source = terrains;
            let __key = index;
            &__source[rt::index(__source.len(), __key)?]
        })
        .sight_height
        .clone();
        if (height).is_some() {
            return Ok((*(height).as_ref().ok_or("expected a value")?).clone());
        }
    }
    Ok((if {
        let __compare_0 = 0i64;
        let __compare_1 = index;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = {
                let _ = {
                    static __CONSTANT_py__openciv3__visibility__HEIGHTS: std::sync::OnceLock<(
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                    )> = std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__visibility__HEIGHTS.get().is_none() {
                        let __constant_value = (
                            0i64,
                            0i64,
                            0i64,
                            0i64,
                            0i64,
                            2i64,
                            4i64,
                            1i64,
                            1i64,
                            (2i64).checked_neg().ok_or("integer overflow")?,
                            4i64,
                            (2i64).checked_neg().ok_or("integer overflow")?,
                            (2i64).checked_neg().ok_or("integer overflow")?,
                            (2i64).checked_neg().ok_or("integer overflow")?,
                        );
                        let _ = __CONSTANT_py__openciv3__visibility__HEIGHTS.set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__visibility__HEIGHTS
                        .get()
                        .ok_or("missing module constant")?
                };
                14i64
            };
            (__compare_1 < __compare_2)
        } else {
            false
        }
    } {
        rt::at(
            &({
                let __tuple_value = {
                    static __CONSTANT_py__openciv3__visibility__HEIGHTS: std::sync::OnceLock<(
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                        i64,
                    )> = std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__visibility__HEIGHTS.get().is_none() {
                        let __constant_value = (
                            0i64,
                            0i64,
                            0i64,
                            0i64,
                            0i64,
                            2i64,
                            4i64,
                            1i64,
                            1i64,
                            (2i64).checked_neg().ok_or("integer overflow")?,
                            4i64,
                            (2i64).checked_neg().ok_or("integer overflow")?,
                            (2i64).checked_neg().ok_or("integer overflow")?,
                            (2i64).checked_neg().ok_or("integer overflow")?,
                        );
                        let _ = __CONSTANT_py__openciv3__visibility__HEIGHTS.set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__visibility__HEIGHTS
                        .get()
                        .ok_or("missing module constant")?
                };
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                    __tuple_value.3.clone(),
                    __tuple_value.4.clone(),
                    __tuple_value.5.clone(),
                    __tuple_value.6.clone(),
                    __tuple_value.7.clone(),
                    __tuple_value.8.clone(),
                    __tuple_value.9.clone(),
                    __tuple_value.10.clone(),
                    __tuple_value.11.clone(),
                    __tuple_value.12.clone(),
                    __tuple_value.13.clone(),
                ]
            }),
            index,
        )?
    } else {
        0i64
    }))
}

/// Replace active sight while retaining explored terrain and last-seen overlays.
// Python: openciv3/visibility.py:38
pub(crate) fn TileKnowledge__observe(
    mut self_: TileKnowledge,
    world: &crate::openciv3::world::WorldMap,
    visible: &std::collections::BTreeSet<(i64, i64)>,
) -> rt::Result<()> {
    self_.visible = ((*visible).clone())
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>();
    TileKnowledge__reveal(self_, world, visible)?;
    Ok(())
}

/// Remember supplied terrain without granting active sight.
// Python: openciv3/visibility.py:43
pub(crate) fn TileKnowledge__reveal(
    mut self_: TileKnowledge,
    world: &crate::openciv3::world::WorldMap,
    points: &std::collections::BTreeSet<(i64, i64)>,
) -> rt::Result<()> {
    let mut newly_known: std::collections::BTreeSet<(i64, i64)> = {
        let __set_left = (*points).clone();
        let __set_right = (self_).known.clone();
        let mut __result = std::collections::BTreeSet::new();
        for __item in __set_left.difference(&__set_right) {
            __result.insert(__item.clone());
        }
        __result
    };
    let mut rebuild: bool = true;
    for mut point in (points).iter() {
        let mut tile: Option<crate::openciv3::world::Tile> = {
            let __star_args_348: Vec<i64> = {
                let __tuple_value = &((*point).clone());
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_348.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                world,
                rt::at(&__star_args_348, 0 as i64)?,
                rt::at(&__star_args_348, 1 as i64)?,
            )?
        };
        if (tile).is_none() {
            return Err({
                let __separator = &(String::new());
                (&(vec!["Cannot observe invalid tile ".to_string(), {
                    let mut __text = "(".to_string();
                    __text.push_str(&((((*point).clone()).0).to_string()));
                    __text.push_str(", ");
                    __text.push_str(&((((*point).clone()).1).to_string()));
                    __text.push_str(")");
                    __text
                }]))
                    .join(__separator)
            }
            .into());
        }
        ((self_).known).insert((*point).clone());
        self_.known_terrain.insert(
            (*point).clone(),
            ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).overlay_terrain,
        );
        self_.known_overlays.insert(
            (*point).clone(),
            ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).overlays,
        );
        if (((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).ruin > 0i64) {
            ((self_).known_ruins).insert((*point).clone());
        } else {
            ((self_).known_ruins).remove(&((*point).clone()));
        }
    }
    if rebuild {
        ((self_).frontier).clear();
        newly_known = (self_).known.clone();
    } else {
        {
            let __other = newly_known.clone();
            ((self_).frontier).retain(|__item| !(__other).contains(__item));
        };
    }
    ((self_).frontier).extend({
        let mut __comprehension_result_352: Vec<(i64, i64)> = Vec::new();
        let mut tile: Option<crate::openciv3::world::Tile>;
        let __comprehension_source_349 = (newly_known.clone());
        for point in __comprehension_source_349.iter().cloned() {
            if ({
                tile = {
                    let __star_args_350: Vec<i64> = {
                        let __tuple_value = &(point.clone());
                        vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                    };
                    if !(2..=2).contains(&__star_args_350.len()) {
                        return Err("wrong function argument count".into());
                    }
                    crate::openciv3::world::WorldMap__tile_at(
                        world,
                        rt::at(&__star_args_350, 0 as i64)?,
                        rt::at(&__star_args_350, 1 as i64)?,
                    )?
                };
                tile.clone()
            })
            .is_some()
            {
                let __comprehension_source_351 = (crate::openciv3::world::WorldMap__neighbors(
                    world,
                    &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?);
                for neighbor in __comprehension_source_351.iter().cloned() {
                    if {
                        let __needle = ((neighbor).x, (neighbor).y);
                        let __container = &(self_).known;
                        !__container.contains(&__needle)
                    } {
                        __comprehension_result_352.push(((neighbor).x, (neighbor).y));
                    }
                }
            }
        }
        __comprehension_result_352
    });
    Ok(())
}

// Python: openciv3/visibility.py:70
pub(crate) fn unit_sight(
    world: &crate::openciv3::world::WorldMap,
    center: &crate::openciv3::world::Tile,
    mut radar: bool,
    mut radar_radius: i64,
    terrains: &[crate::openciv3::rules::Terrain],
) -> rt::Result<std::collections::BTreeSet<(i64, i64)>> {
    if (radar_radius < 0i64) {
        return Err("Radar radius must be nonnegative".to_string().into());
    }
    let mut visible: std::collections::BTreeSet<(i64, i64)> = {
        let mut __result = std::collections::BTreeSet::new();
        for __item in vec![((center).x, (center).y)].into_iter() {
            __result.insert(__item);
        }
        __result
    };
    if radar {
        for mut radius in 0i64..(radar_radius).checked_add(1i64).ok_or("integer overflow")? {
            (visible).extend({
                let mut __comprehension_result_354: Vec<(i64, i64)> = Vec::new();
                let __comprehension_source_353 =
                    (crate::strategy::grid::ring(world, center, radius, true)?);
                for tile in __comprehension_source_353.iter().cloned() {
                    __comprehension_result_354.push(((tile).x, (tile).y));
                }
                __comprehension_result_354
            });
        }
        return Ok(visible);
    }
    let mut unit_height: i64 = _height(center, terrains)?;
    for mut for_target_80_4 in ({
        static __CONSTANT_py__openciv3__visibility__DIRECTIONS: std::sync::OnceLock<
            Vec<(i64, i64)>,
        > = std::sync::OnceLock::new();
        if __CONSTANT_py__openciv3__visibility__DIRECTIONS
            .get()
            .is_none()
        {
            let __constant_value = vec![
                (0i64, (2i64).checked_neg().ok_or("integer overflow")?),
                (1i64, (1i64).checked_neg().ok_or("integer overflow")?),
                (2i64, 0i64),
                (1i64, 1i64),
                (0i64, 2i64),
                ((1i64).checked_neg().ok_or("integer overflow")?, 1i64),
                ((2i64).checked_neg().ok_or("integer overflow")?, 0i64),
                (
                    (1i64).checked_neg().ok_or("integer overflow")?,
                    (1i64).checked_neg().ok_or("integer overflow")?,
                ),
            ];
            let _ = __CONSTANT_py__openciv3__visibility__DIRECTIONS.set(__constant_value);
        }
        __CONSTANT_py__openciv3__visibility__DIRECTIONS
            .get()
            .ok_or("missing module constant")?
            .clone()
    })
    .into_iter()
    .enumerate()
    .map(|(__index, __value)| (__index as i64 + 0i64, __value))
    .collect::<Vec<_>>()
    {
        let (mut inner_direction, (mut dx, mut dy)): (i64, (i64, i64)) = for_target_80_4;
        let mut inner: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(
                world,
                ((center).x).checked_add(dx).ok_or("integer overflow")?,
                ((center).y).checked_add(dy).ok_or("integer overflow")?,
            )?;
        if (inner).is_none() {
            continue;
        }
        {
            visible.insert((
                ((*(inner.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                ((*(inner.clone()).as_ref().ok_or("expected a value")?).clone()).y,
            ));
        };
        let mut inner_height: i64 = _height(
            &((*(inner.clone()).as_ref().ok_or("expected a value")?).clone()),
            terrains,
        )?;
        for mut for_target_86_8 in ({
            static __CONSTANT_py__openciv3__visibility__DIRECTIONS: std::sync::OnceLock<
                Vec<(i64, i64)>,
            > = std::sync::OnceLock::new();
            if __CONSTANT_py__openciv3__visibility__DIRECTIONS
                .get()
                .is_none()
            {
                let __constant_value = vec![
                    (0i64, (2i64).checked_neg().ok_or("integer overflow")?),
                    (1i64, (1i64).checked_neg().ok_or("integer overflow")?),
                    (2i64, 0i64),
                    (1i64, 1i64),
                    (0i64, 2i64),
                    ((1i64).checked_neg().ok_or("integer overflow")?, 1i64),
                    ((2i64).checked_neg().ok_or("integer overflow")?, 0i64),
                    (
                        (1i64).checked_neg().ok_or("integer overflow")?,
                        (1i64).checked_neg().ok_or("integer overflow")?,
                    ),
                ];
                let _ = __CONSTANT_py__openciv3__visibility__DIRECTIONS.set(__constant_value);
            }
            __CONSTANT_py__openciv3__visibility__DIRECTIONS
                .get()
                .ok_or("missing module constant")?
                .clone()
        })
        .into_iter()
        .enumerate()
        .map(|(__index, __value)| (__index as i64 + 0i64, __value))
        .collect::<Vec<_>>()
        {
            let (mut outer_direction, (mut ox, mut oy)): (i64, (i64, i64)) = for_target_86_8;
            if ((inner_direction != outer_direction) && {
                let __compare_0 = rt::int_modulo(inner_direction, 2i64)?;
                let __compare_1 = rt::int_modulo(outer_direction, 2i64)?;
                if (__compare_0 == __compare_1) {
                    let __compare_2 = 0i64;
                    (__compare_1 == __compare_2)
                } else {
                    false
                }
            }) {
                continue;
            }
            let mut outer: Option<crate::openciv3::world::Tile> =
                crate::openciv3::world::WorldMap__tile_at(
                    world,
                    (((*(inner.clone()).as_ref().ok_or("expected a value")?).clone()).x)
                        .checked_add(ox)
                        .ok_or("integer overflow")?,
                    (((*(inner.clone()).as_ref().ok_or("expected a value")?).clone()).y)
                        .checked_add(oy)
                        .ok_or("integer overflow")?,
                )?;
            if (outer).is_none() {
                continue;
            }
            let mut outer_height: i64 = _height(
                &((*(outer.clone()).as_ref().ok_or("expected a value")?).clone()),
                terrains,
            )?;
            if ({
                let __needle =
                    ((*(inner.clone()).as_ref().ok_or("expected a value")?).clone()).base_terrain;
                let __container = &({
                    let __tuple_value = &((11i64, 12i64, 13i64));
                    vec![
                        __tuple_value.0.clone(),
                        __tuple_value.1.clone(),
                        __tuple_value.2.clone(),
                    ]
                });
                __container.contains(&__needle)
            } || (((outer_height >= 2i64)
                && ((inner_height).checked_add(2i64).ok_or("integer overflow")? <= outer_height))
                || (((outer_height).checked_add(1i64).ok_or("integer overflow")? <= unit_height)
                    && ((inner_height).checked_add(2i64).ok_or("integer overflow")?
                        <= unit_height))))
            {
                {
                    visible.insert((
                        ((*(outer.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                        ((*(outer.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                    ));
                };
            }
        }
    }
    Ok(visible)
}

// Python: openciv3/visibility.py:100
pub(crate) fn update_visibility(
    world: &crate::openciv3::world::WorldMap,
    cities: &[crate::openciv3::cities::City],
    units: &[crate::openciv3::units::Unit],
    rules: &crate::openciv3::rules::RuleCatalog,
    ownership: &indexmap::IndexMap<(i64, i64), i64>,
    mut knowledge: indexmap::IndexMap<i64, TileKnowledge>,
    mut radar_radius: Option<i64>,
    only_owner: &Option<i64>,
) -> rt::Result<indexmap::IndexMap<i64, TileKnowledge>> {
    if (radar_radius).is_none() {
        radar_radius = (if (((&(rules).global_rules).len() as i64) != 0i64) {
            Some(
                ({
                    let __source = &(rules).global_rules;
                    let __key = 0i64;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .radar_tile_visibility,
            )
        } else {
            Some(2i64)
        });
    }
    let mut cities_by_id: indexmap::IndexMap<i64, crate::openciv3::cities::City> = {
        let mut __comprehension_result_356: indexmap::IndexMap<i64, crate::openciv3::cities::City> =
            indexmap::IndexMap::new();
        let __comprehension_source_355 = (cities.to_vec());
        for city in __comprehension_source_355.iter().cloned() {
            {
                let (__key, __value) = ((city).id, city.clone());
                __comprehension_result_356.insert(__key, __value);
            }
        }
        __comprehension_result_356
    };
    let mut owners: Vec<i64> = (if (only_owner).is_none() {
        (knowledge).keys().cloned().collect::<Vec<_>>()
    } else {
        vec![(*((*only_owner).clone()).as_ref().ok_or("expected a value")?).clone()]
    });
    let mut visible: indexmap::IndexMap<i64, std::collections::BTreeSet<(i64, i64)>> = {
        let mut __comprehension_result_358: indexmap::IndexMap<
            i64,
            std::collections::BTreeSet<(i64, i64)>,
        > = indexmap::IndexMap::new();
        let __comprehension_source_357 = (owners.clone());
        for owner in __comprehension_source_357.iter().cloned() {
            {
                let (__key, __value) = (owner, std::collections::BTreeSet::new());
                __comprehension_result_358.insert(__key, __value);
            }
        }
        __comprehension_result_358
    };
    let mut occupied: indexmap::IndexMap<(i64, (i64, i64)), bool> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut unit in (units).iter() {
        if ((&(unit).transported_by).is_some()
            || ((only_owner).is_some() && (Some((unit).owner) != (*only_owner).clone())))
        {
            continue;
        }
        if {
            let __needle = (unit).owner;
            let __container = &visible;
            !__container.contains_key(&__needle)
        } {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Missing tile knowledge for unit owner ".to_string(),
                    ((unit).owner).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        let mut key: (i64, (i64, i64)) = ((unit).owner, ((unit).x, (unit).y));
        {
            let __value = ({
                let __key = key.clone();
                let __default = false;
                occupied.get(&__key).cloned().unwrap_or(__default)
            } || (({
                let __source = &(rules).units;
                let __key = (unit).prototype;
                &__source[rt::index(__source.len(), __key)?]
            })
            .abilities
                & 32i64)
                != 0);
            let __key = key.clone();
            occupied.insert(__key, __value);
        }
    }
    for mut for_target_116_4 in (occupied.clone())
        .iter()
        .map(|(__key, __value)| (__key.clone(), __value.clone()))
        .collect::<Vec<_>>()
    {
        let ((mut owner, mut point), mut radar): ((i64, (i64, i64)), bool) = for_target_116_4;
        let mut center: Option<crate::openciv3::world::Tile> = {
            let __star_args_359: Vec<i64> = {
                let __tuple_value = &(point.clone());
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_359.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                world,
                rt::at(&__star_args_359, 0 as i64)?,
                rt::at(&__star_args_359, 1 as i64)?,
            )?
        };
        if (center).is_none() {
            return Err({
                let __separator = &(String::new());
                (&(vec!["Unit is outside the map at ".to_string(), {
                    let mut __text = "(".to_string();
                    __text.push_str(&(((point).0).to_string()));
                    __text.push_str(", ");
                    __text.push_str(&(((point).1).to_string()));
                    __text.push_str(")");
                    __text
                }]))
                    .join(__separator)
            }
            .into());
        }
        let mut sight: std::collections::BTreeSet<(i64, i64)> =
            (visible).get(&(owner)).ok_or("missing dict key")?.clone();
        (sight).extend({
            let __call_360_0 = world;
            let __call_360_1 = &((*(center).as_ref().ok_or("expected a value")?).clone());
            let __call_360_2 = radar;
            let __call_360_3 =
                (*(radar_radius.clone()).as_ref().ok_or("expected a value")?).clone();
            let __call_360_4 = &((rules).terrains.clone());
            unit_sight(
                __call_360_0,
                __call_360_1,
                __call_360_2,
                __call_360_3,
                __call_360_4,
            )
        }?);
        {
            let __value = sight.clone();
            let __key = owner;
            visible.insert(__key, __value);
        }
    }
    for mut for_target_123_4 in ((*ownership).clone())
        .iter()
        .map(|(__key, __value)| (__key.clone(), __value.clone()))
        .collect::<Vec<_>>()
    {
        let (mut point, mut city_id): ((i64, i64), i64) = for_target_123_4;
        let mut owner: i64 = ((cities_by_id).get(&(city_id)).ok_or("missing dict key")?).owner;
        if ((only_owner).is_some() && (Some(owner) != (*only_owner).clone())) {
            continue;
        }
        let mut center: Option<crate::openciv3::world::Tile> = {
            let __star_args_361: Vec<i64> = {
                let __tuple_value = &(point.clone());
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_361.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                world,
                rt::at(&__star_args_361, 0 as i64)?,
                rt::at(&__star_args_361, 1 as i64)?,
            )?
        };
        if (center).is_none() {
            return Err({
                let __separator = &(String::new());
                (&(vec!["Owned tile is outside the map at ".to_string(), {
                    let mut __text = "(".to_string();
                    __text.push_str(&(((point).0).to_string()));
                    __text.push_str(", ");
                    __text.push_str(&(((point).1).to_string()));
                    __text.push_str(")");
                    __text
                }]))
                    .join(__separator)
            }
            .into());
        }
        let mut sight: std::collections::BTreeSet<(i64, i64)> =
            (visible).get(&(owner)).ok_or("missing dict key")?.clone();
        {
            sight.insert(point.clone());
        };
        if {
            let __needle = (owner, point.clone());
            let __container = &occupied;
            !__container.contains_key(&__needle)
        } {
            (sight).extend({
                let mut __comprehension_result_363: Vec<(i64, i64)> = Vec::new();
                let __comprehension_source_362 = (crate::openciv3::world::WorldMap__neighbors(
                    world,
                    &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?);
                for neighbor in __comprehension_source_362.iter().cloned() {
                    __comprehension_result_363.push(((neighbor).x, (neighbor).y));
                }
                __comprehension_result_363
            });
        }
        {
            let __value = sight.clone();
            let __key = owner;
            visible.insert(__key, __value);
        }
    }
    for mut tile in (&(world).tiles).iter() {
        if !(((tile).overlays & 2147483648i64) != 0i64) {
            continue;
        }
        let mut point: (i64, i64) = ((tile).x, (tile).y);
        let mut claim: Option<i64> = ((*ownership).clone()).get(&(point)).cloned();
        let mut territory_owner: Option<i64> = (if (claim).is_some() {
            Some(
                ((cities_by_id)
                    .get(&((*(claim.clone()).as_ref().ok_or("expected a value")?).clone()))
                    .ok_or("missing dict key")?)
                .owner,
            )
        } else {
            None
        });
        let mut outpost_owner: Option<i64> = (if (&(tile).installation_owner).is_some() {
            (tile).installation_owner.clone()
        } else {
            territory_owner.clone()
        });
        if ((outpost_owner).is_none()
            || (match (outpost_owner.clone()) {
                Some(__value) => {
                    let __needle = __value;
                    let __container = &visible;
                    !__container.contains_key(&__needle)
                }
                None => true,
            } || !((territory_owner).is_none()
                || (territory_owner) == ((((), outpost_owner.clone())).1))))
        {
            continue;
        }
        let mut radius: i64 = (if ((tile).overlay_terrain == 6i64) {
            4i64
        } else {
            (if ((tile).overlay_terrain == 5i64) {
                3i64
            } else {
                2i64
            })
        });
        let mut sight: std::collections::BTreeSet<(i64, i64)> = (visible)
            .get(&((*(outpost_owner.clone()).as_ref().ok_or("expected a value")?).clone()))
            .ok_or("missing dict key")?
            .clone();
        (sight).extend({
            let __call_364_0 = world;
            let __call_364_1 = tile;
            let __call_364_2 = true;
            let __call_364_3 = radius;
            let __call_364_default_4 = &(vec![]);
            unit_sight(
                __call_364_0,
                __call_364_1,
                __call_364_2,
                __call_364_3,
                __call_364_default_4,
            )
        }?);
        {
            let __value = sight.clone();
            let __key = (*(outpost_owner).as_ref().ok_or("expected a value")?).clone();
            visible.insert(__key, __value);
        }
    }
    for mut for_target_149_4 in (visible)
        .iter()
        .map(|(__key, __value)| (__key.clone(), __value.clone()))
        .collect::<Vec<_>>()
    {
        let (mut owner, mut sight): (i64, std::collections::BTreeSet<(i64, i64)>) =
            for_target_149_4;
        let mut refreshed: TileKnowledge =
            (knowledge).get(&(owner)).ok_or("missing dict key")?.clone();
        refreshed.visible = (sight.clone())
            .into_iter()
            .collect::<std::collections::BTreeSet<_>>();
        TileKnowledge__reveal(refreshed.clone(), world, &sight)?;
        {
            let __value = refreshed;
            let __key = owner;
            knowledge.insert(__key, __value);
        }
    }
    Ok(knowledge)
}
