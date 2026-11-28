use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct Tile {
    pub(crate) x: i64,
    pub(crate) y: i64,
    pub(crate) resource: i64,
    pub(crate) texture_index: i64,
    pub(crate) texture_file: i64,
    pub(crate) base_terrain: i64,
    pub(crate) overlay_terrain: i64,
    pub(crate) continent: i64,
    pub(crate) river_connections: i64,
    pub(crate) overlays: i64,
    pub(crate) bonuses: i64,
    pub(crate) fog_of_war: i64,
    pub(crate) city: i64,
    pub(crate) colony: i64,
    pub(crate) barbarian_tribe: i64,
    pub(crate) victory_point: bool,
    pub(crate) ruin: i64,
    pub(crate) border: i64,
    pub(crate) freshwater: Option<bool>,
    pub(crate) installation_owner: Option<i64>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct PlacedUnit {
    pub(crate) owner_kind: i64,
    pub(crate) experience: i64,
    pub(crate) owner: i64,
    pub(crate) prototype: i64,
    pub(crate) ai_strategy: i64,
    pub(crate) x: i64,
    pub(crate) y: i64,
    pub(crate) name: String,
    pub(crate) use_civilization_king: bool,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct PlacedCity {
    pub(crate) walls: bool,
    pub(crate) palace: bool,
    pub(crate) name: String,
    pub(crate) owner_kind: i64,
    pub(crate) buildings: Vec<i64>,
    pub(crate) culture: i64,
    pub(crate) owner: i64,
    pub(crate) size: i64,
    pub(crate) x: i64,
    pub(crate) y: i64,
    pub(crate) level: i64,
    pub(crate) border_level: i64,
    pub(crate) auto_name: bool,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct StartingLocation {
    pub(crate) owner_kind: i64,
    pub(crate) owner: i64,
    pub(crate) x: i64,
    pub(crate) y: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct WorldMap {
    pub(crate) width: i64,
    pub(crate) height: i64,
    pub(crate) wrap_x: bool,
    pub(crate) wrap_y: bool,
    pub(crate) polar_ice: bool,
    pub(crate) seed: i64,
    pub(crate) civilization_count: i64,
    pub(crate) civilization_distance: i64,
    pub(crate) resources: Vec<i64>,
    pub(crate) tiles: Vec<Tile>,
    pub(crate) cities: Vec<PlacedCity>,
    pub(crate) units: Vec<PlacedUnit>,
    pub(crate) starts: Vec<StartingLocation>,
}

// Python: openciv3/world.py:66
pub(crate) fn Tile__from_record(
    record: &crate::openciv3::binary::Record,
    mut index: i64,
    mut width: i64,
) -> rt::Result<Tile> {
    let mut value: Vec<u8> = crate::openciv3::binary::Record__bytes(record, 0i64, 49i64)?;
    let (mut y, mut column): (i64, i64) = rt::divmod_int(index, rt::int_floor_div(width, 2i64)?)?;

    Ok(Tile {
        x: ((column).checked_mul(2i64).ok_or("integer overflow")?)
            .checked_add(rt::int_modulo(y, 2i64)?)
            .ok_or("integer overflow")?,
        y: y,
        resource: crate::openciv3::binary::Record__integer(record, 6i64)?,
        texture_index: (rt::at(&value, 10i64)? as i64),
        texture_file: (rt::at(&value, 11i64)? as i64),
        base_terrain: ((rt::at(&value, 38i64)? as i64) & 15i64),
        overlay_terrain: rt::int_rshift((rt::at(&value, 38i64)? as i64), 4i64)?,
        continent: Tile__from_record__short(&value, 24i64)?,
        river_connections: (rt::at(&value, 4i64)? as i64),
        overlays: rt::int_from_bytes(rt::slice_view(&value, 33i64, 37i64), "little")?,
        bonuses: rt::int_from_bytes(rt::slice_view(&value, 43i64, 47i64), "little")?,
        fog_of_war: Tile__from_record__short(&value, 41i64)?,
        city: Tile__from_record__short(&value, 20i64)?,
        colony: Tile__from_record__short(&value, 22i64)?,
        barbarian_tribe: Tile__from_record__short(&value, 18i64)?,
        victory_point: (Tile__from_record__short(&value, 27i64)? == 0i64),
        ruin: crate::openciv3::binary::Record__integer(record, 29i64)?,
        border: (rt::at(&value, 5i64)? as i64),
        freshwater: None,
        installation_owner: None,
    })
}

// Python: openciv3/world.py:78
pub(crate) fn Tile__bonus_grassland(self_: &Tile) -> rt::Result<bool> {
    Ok(((self_).bonuses & 1i64) != 0)
}

// Python: openciv3/world.py:82
pub(crate) fn Tile__player_start(self_: &Tile) -> rt::Result<bool> {
    Ok(((self_).bonuses & 8i64) != 0)
}

// Python: openciv3/world.py:86
pub(crate) fn Tile__landmark(self_: &Tile) -> rt::Result<bool> {
    Ok(((self_).bonuses & rt::int_lshift(1i64, 25i64)?) != 0)
}

// Python: openciv3/world.py:103
pub(crate) fn PlacedUnit__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<PlacedUnit> {
    Ok(PlacedUnit {
        owner_kind: crate::openciv3::binary::Record__integer(record, 36i64)?,
        experience: crate::openciv3::binary::Record__integer(record, 40i64)?,
        owner: crate::openciv3::binary::Record__integer(record, 44i64)?,
        prototype: crate::openciv3::binary::Record__integer(record, 48i64)?,
        ai_strategy: crate::openciv3::binary::Record__integer(record, 52i64)?,
        x: crate::openciv3::binary::Record__integer(record, 56i64)?,
        y: crate::openciv3::binary::Record__integer(record, 60i64)?,
        name: crate::openciv3::binary::Record__text(record, 64i64, 57i64)?,
        use_civilization_king: (crate::openciv3::binary::Record__integer(record, 121i64)? == 1i64),
    })
}

// Python: openciv3/world.py:126
pub(crate) fn PlacedCity__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<PlacedCity> {
    let mut count: i64 = crate::openciv3::binary::Record__count(record, 34i64, 4i64)?;
    let mut tail: i64 = (38i64)
        .checked_add((4i64).checked_mul(count).ok_or("integer overflow")?)
        .ok_or("integer overflow")?;
    Ok(PlacedCity {
        walls: ((rt::at(
            &(crate::openciv3::binary::Record__bytes(record, 4i64, 1i64)?),
            0i64,
        )? as i64)
            != 0i64),
        palace: ((rt::at(
            &(crate::openciv3::binary::Record__bytes(record, 5i64, 1i64)?),
            0i64,
        )? as i64)
            != 0i64),
        name: crate::openciv3::binary::Record__text(record, 6i64, 24i64)?,
        owner_kind: crate::openciv3::binary::Record__integer(record, 30i64)?,
        buildings: ({
            let mut __comprehension_result_194: Vec<i64> = Vec::new();
            let __comprehension_source_193 = ((0i64..count).collect::<Vec<i64>>());
            for i in __comprehension_source_193.iter().cloned() {
                __comprehension_result_194.push(crate::openciv3::binary::Record__integer(
                    record,
                    (38i64)
                        .checked_add((4i64).checked_mul(i).ok_or("integer overflow")?)
                        .ok_or("integer overflow")?,
                )?);
            }
            __comprehension_result_194
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        culture: crate::openciv3::binary::Record__integer(record, tail)?,
        owner: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(4i64).ok_or("integer overflow")?,
        )?,
        size: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(8i64).ok_or("integer overflow")?,
        )?,
        x: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(12i64).ok_or("integer overflow")?,
        )?,
        y: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(16i64).ok_or("integer overflow")?,
        )?,
        level: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(20i64).ok_or("integer overflow")?,
        )?,
        border_level: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(24i64).ok_or("integer overflow")?,
        )?,
        auto_name: (crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(28i64).ok_or("integer overflow")?,
        )? == 1i64),
    })
}

// Python: openciv3/world.py:161
pub(crate) fn WorldMap__from_scenario(
    scenario: &crate::openciv3::scenario::Scenario,
) -> rt::Result<WorldMap> {
    let mut maps: Vec<crate::openciv3::binary::Record> =
        WorldMap__from_scenario__records(scenario, "WMAP")?;
    if (((maps).len() as i64) != 1i64) {
        return Err("A scenario with tiles must contain one WMAP record"
            .to_string()
            .into());
    }
    let mut record: crate::openciv3::binary::Record = rt::at(&maps, 0i64)?;
    let mut count: i64 = crate::openciv3::binary::Record__count(&record, 4i64, 4i64)?;
    let mut offset: i64 = (count).checked_mul(4i64).ok_or("integer overflow")?;
    let (mut width, mut height): (i64, i64) = (
        crate::openciv3::binary::Record__integer(
            &record,
            (32i64).checked_add(offset).ok_or("integer overflow")?,
        )?,
        crate::openciv3::binary::Record__integer(
            &record,
            (12i64).checked_add(offset).ok_or("integer overflow")?,
        )?,
    );
    if ((width <= 0i64) || ((rt::int_modulo(width, 2i64)?) != 0 || (height <= 0i64))) {
        return Err("Invalid staggered-grid map dimensions".to_string().into());
    }
    let mut tiles: Vec<crate::openciv3::binary::Record> =
        WorldMap__from_scenario__records(scenario, "TILE")?;
    if (((tiles).len() as i64)
        != (rt::int_floor_div(width, 2i64)?)
            .checked_mul(height)
            .ok_or("integer overflow")?)
    {
        return Err("TILE record count does not match WMAP dimensions"
            .to_string()
            .into());
    }
    let mut flags: i64 = (rt::at(
        &(crate::openciv3::binary::Record__bytes(
            &record,
            (168i64).checked_add(offset).ok_or("integer overflow")?,
            1i64,
        )?),
        0i64,
    )? as i64);
    let mut result: WorldMap = WorldMap {
        width: width,
        height: height,
        wrap_x: (flags & 1i64) != 0,
        wrap_y: (flags & 2i64) != 0,
        polar_ice: (flags & 4i64) != 0,
        seed: crate::openciv3::binary::Record__integer(
            &record,
            (164i64).checked_add(offset).ok_or("integer overflow")?,
        )?,
        civilization_count: crate::openciv3::binary::Record__integer(
            &record,
            (20i64).checked_add(offset).ok_or("integer overflow")?,
        )?,
        civilization_distance: crate::openciv3::binary::Record__integer(
            &record,
            (16i64).checked_add(offset).ok_or("integer overflow")?,
        )?,
        resources: ({
            let mut __comprehension_result_196: Vec<i64> = Vec::new();
            let __comprehension_source_195 = ((0i64..count).collect::<Vec<i64>>());
            for i in __comprehension_source_195.iter().cloned() {
                __comprehension_result_196.push(crate::openciv3::binary::Record__integer(
                    &record,
                    (8i64)
                        .checked_add((4i64).checked_mul(i).ok_or("integer overflow")?)
                        .ok_or("integer overflow")?,
                )?);
            }
            __comprehension_result_196
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        tiles: ({
            let mut __comprehension_result_198: Vec<Tile> = Vec::new();
            let __comprehension_source_197 = ((tiles.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>());
            for (i, tile) in __comprehension_source_197.iter().cloned() {
                __comprehension_result_198.push(Tile__from_record(&tile, i, width)?);
            }
            __comprehension_result_198
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        cities: ({
            let mut __comprehension_result_200: Vec<PlacedCity> = Vec::new();
            let __comprehension_source_199 = (WorldMap__from_scenario__records(scenario, "CITY")?);
            for city in __comprehension_source_199.iter().cloned() {
                __comprehension_result_200.push(PlacedCity__from_record(&city)?);
            }
            __comprehension_result_200
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        units: ({
            let mut __comprehension_result_202: Vec<PlacedUnit> = Vec::new();
            let __comprehension_source_201 = (WorldMap__from_scenario__records(scenario, "UNIT")?);
            for unit in __comprehension_source_201.iter().cloned() {
                __comprehension_result_202.push(PlacedUnit__from_record(&unit)?);
            }
            __comprehension_result_202
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        starts: ({
            let mut __comprehension_result_204: Vec<StartingLocation> = Vec::new();
            let __comprehension_source_203 = (WorldMap__from_scenario__records(scenario, "SLOC")?);
            for start in __comprehension_source_203.iter().cloned() {
                __comprehension_result_204.push(StartingLocation {
                    owner_kind: crate::openciv3::binary::Record__integer(&start, 4i64)?,
                    owner: crate::openciv3::binary::Record__integer(&start, 8i64)?,
                    x: crate::openciv3::binary::Record__integer(&start, 12i64)?,
                    y: crate::openciv3::binary::Record__integer(&start, 16i64)?,
                });
            }
            __comprehension_result_204
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
    };
    for mut city in (&(result).cities).iter() {
        if (WorldMap__tile_at(&result, (city).x, (city).y)?).is_none() {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Placement is outside the map: (".to_string(),
                    ((city).x).to_string(),
                    ", ".to_string(),
                    ((city).y).to_string(),
                    ")".to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
    }
    for mut unit in (&(result).units).iter() {
        if (WorldMap__tile_at(&result, (unit).x, (unit).y)?).is_none() {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Placement is outside the map: (".to_string(),
                    ((unit).x).to_string(),
                    ", ".to_string(),
                    ((unit).y).to_string(),
                    ")".to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
    }
    let mut claimed: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_206: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let mut tile: Option<Tile>;
        let __comprehension_source_205 = ((result).starts.clone());
        for start in __comprehension_source_205.iter().cloned() {
            if ({
                tile = WorldMap__tile_at(&result, (start).x, (start).y)?;
                tile.clone()
            })
            .is_some()
            {
                __comprehension_result_206.insert((
                    ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                    ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                ));
            }
        }
        __comprehension_result_206
    };
    let mut starts: Vec<StartingLocation> = vec![];
    for mut start in (&(result).starts).iter().cloned() {
        if (WorldMap__tile_at(&result, (start).x, (start).y)?).is_none() {
            let mut candidates: std::collections::BTreeSet<(i64, i64)> = {
                let __set_left = {
                    let mut __comprehension_result_208: std::collections::BTreeSet<(i64, i64)> =
                        std::collections::BTreeSet::new();
                    let mut tile: Option<Tile>;
                    let __comprehension_source_207 = ({
                        let __tuple_value = &((
                            ((start).x).checked_sub(1i64).ok_or("integer overflow")?,
                            ((start).x).checked_add(1i64).ok_or("integer overflow")?,
                        ));
                        vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                    });
                    for x in __comprehension_source_207.iter().cloned() {
                        if (({
                            tile = WorldMap__tile_at(&result, x, (start).y)?;
                            tile.clone()
                        })
                        .is_some()
                            && Tile__player_start(
                                &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
                            )?)
                        {
                            __comprehension_result_208.insert((
                                ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                                ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                            ));
                        }
                    }
                    __comprehension_result_208
                };
                let __set_right = claimed.clone();
                let mut __result = std::collections::BTreeSet::new();
                for __item in __set_left.difference(&__set_right) {
                    __result.insert(__item.clone());
                }
                __result
            };
            if (!({
                let __compare_0 = 0i64;
                let __compare_1 = (start).x;
                if (__compare_0 <= __compare_1) {
                    let __compare_2 = width;
                    (__compare_1 < __compare_2)
                } else {
                    false
                }
            }) || (!({
                let __compare_0 = 0i64;
                let __compare_1 = (start).y;
                if (__compare_0 <= __compare_1) {
                    let __compare_2 = height;
                    (__compare_1 < __compare_2)
                } else {
                    false
                }
            }) || (((candidates).len() as i64) != 1i64)))
            {
                return Err({
                    let __separator = &(String::new());
                    (&(vec![
                        "Placement is outside the map: (".to_string(),
                        ((start).x).to_string(),
                        ", ".to_string(),
                        ((start).y).to_string(),
                        ")".to_string(),
                    ]))
                        .join(__separator)
                }
                .into());
            }
            let (mut x, mut y): (i64, i64) =
                (candidates).pop_first().ok_or("pop from an empty set")?;
            {
                claimed.insert((x, y));
            };
            start = {
                let mut __replacement = (start).clone();
                __replacement.x = x;
                __replacement.y = y;
                __replacement
            };
        }
        {
            starts.push(start);
        };
    }
    Ok({
        let mut __replacement = (result).clone();
        __replacement.starts = (starts).iter().cloned().collect::<Vec<_>>();
        __replacement
    })
}

// Python: openciv3/world.py:212
pub(crate) fn WorldMap__tile_at(
    self_: &WorldMap,
    mut x: i64,
    mut y: i64,
) -> rt::Result<Option<Tile>> {
    if (self_).wrap_x {
        x = rt::int_modulo(x, (self_).width)?;
    }
    if (self_).wrap_y {
        y = rt::int_modulo(y, (self_).height)?;
    }
    if (!({
        let __compare_0 = 0i64;
        let __compare_1 = x;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = (self_).width;
            (__compare_1 < __compare_2)
        } else {
            false
        }
    } && {
        let __compare_0 = 0i64;
        let __compare_1 = y;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = (self_).height;
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) || (rt::int_modulo(x, 2i64)? != rt::int_modulo(y, 2i64)?))
    {
        return Ok(None);
    }
    Ok(Some(rt::at(
        &(self_).tiles,
        ((y).checked_mul(rt::int_floor_div((self_).width, 2i64)?)
            .ok_or("integer overflow")?)
        .checked_add(rt::int_floor_div(x, 2i64)?)
        .ok_or("integer overflow")?,
    )?))
}

// Python: openciv3/world.py:221
pub(crate) fn WorldMap__neighbors(self_: &WorldMap, tile: &Tile) -> rt::Result<Vec<Tile>> {
    let mut offsets: (
        (i64, i64),
        (i64, i64),
        (i64, i64),
        (i64, i64),
        (i64, i64),
        (i64, i64),
        (i64, i64),
        (i64, i64),
    ) = (
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
    );
    Ok(({
        let mut __comprehension_result_210: Vec<Tile> = Vec::new();
        let mut neighbor: Option<Tile>;
        let __comprehension_source_209 = ({
            let __tuple_value = &(offsets.clone());
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
                __tuple_value.3.clone(),
                __tuple_value.4.clone(),
                __tuple_value.5.clone(),
                __tuple_value.6.clone(),
                __tuple_value.7.clone(),
            ]
        });
        for (dx, dy) in __comprehension_source_209.iter().cloned() {
            if ({
                neighbor = WorldMap__tile_at(
                    self_,
                    ((tile).x).checked_add(dx).ok_or("integer overflow")?,
                    ((tile).y).checked_add(dy).ok_or("integer overflow")?,
                )?;
                neighbor.clone()
            })
            .is_some()
            {
                __comprehension_result_210
                    .push((*(neighbor.clone()).as_ref().ok_or("expected a value")?).clone());
            }
        }
        __comprehension_result_210
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>())
}

// Python: openciv3/world.py:226
pub(crate) fn resolve_owner(
    mut kind: i64,
    mut owner: i64,
    assigned: &[i64],
    mut civ_count: i64,
) -> rt::Result<Option<i64>> {
    if (kind == 0i64) {
        return Ok(None);
    }
    if (kind == 1i64) {
        return Ok(Some(0i64));
    }
    if (kind == 3i64) {
        if !({
            let __compare_0 = 0i64;
            let __compare_1 = owner;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = ((assigned).len() as i64);
                (__compare_1 < __compare_2)
            } else {
                false
            }
        }) {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Invalid player-slot owner: ".to_string(),
                    (owner).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        owner = rt::at(assigned, owner)?;
    }
    if !({
        let __compare_0 = 0i64;
        let __compare_1 = owner;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = civ_count;
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Invalid civilization owner: ".to_string(),
                (owner).to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok(Some(owner))
}

// Python: openciv3/world.py:69
pub(crate) fn Tile__from_record__short(value: &[u8], mut offset: i64) -> rt::Result<i64> {
    rt::int_from_bytes_signed(
        rt::slice_view(
            value,
            offset,
            (offset).checked_add(2i64).ok_or("integer overflow")?,
        ),
        "little",
        true,
    )
}

// Python: openciv3/world.py:162
pub(crate) fn WorldMap__from_scenario__records(
    scenario: &crate::openciv3::scenario::Scenario,
    section: &str,
) -> rt::Result<Vec<crate::openciv3::binary::Record>> {
    Ok({
        let mut __comprehension_result_212: Vec<crate::openciv3::binary::Record> = Vec::new();
        let __comprehension_source_211 = ({
            let __mapping = &(scenario).sections;
            let __key = section.to_owned();
            let __default = vec![];
            __mapping.get(&__key).cloned().unwrap_or(__default)
        });
        for data in __comprehension_source_211.iter().cloned() {
            __comprehension_result_212.push(crate::openciv3::binary::Record {
                data: data.clone(),
                section: section.to_owned(),
                encoding: (scenario).encoding.clone(),
            });
        }
        __comprehension_result_212
    })
}
