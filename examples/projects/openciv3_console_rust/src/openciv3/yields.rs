use py2rust_service_runtime as rt;

/// Value yields and halve the score for each unit of food shortfall.
// Python: openciv3/yields.py:13
pub(crate) fn tile_assignment_score(
    value: &crate::civ::economy::Yield,
    mut target_food: i64,
) -> rt::Result<f64> {
    let mut base: i64 = ((((value).food)
        .checked_mul(40i64)
        .ok_or("integer overflow")?)
    .checked_add(
        ((value).shields)
            .checked_mul(50i64)
            .ok_or("integer overflow")?,
    )
    .ok_or("integer overflow")?)
    .checked_add(
        ((value).commerce)
            .checked_mul(30i64)
            .ok_or("integer overflow")?,
    )
    .ok_or("integer overflow")?;
    rt::math_ldexp(
        (base as f64),
        ((0i64).max(
            (target_food)
                .checked_sub((value).food)
                .ok_or("integer overflow")?,
        ))
        .checked_neg()
        .ok_or("integer overflow")?,
    )
}

// Python: openciv3/yields.py:19
pub(crate) fn natural_tile_yield(
    tile: &crate::openciv3::world::Tile,
    terrain: &crate::civ::economy::Yield,
    resource: &crate::civ::economy::Yield,
    mut river: bool,
) -> rt::Result<crate::civ::economy::Yield> {
    if (((tile).overlays & 64i64) != 0i64) {
        return Ok(crate::civ::economy::Yield {
            food: 0i64,
            shields: 0i64,
            commerce: 0i64,
        });
    }
    Ok(crate::civ::economy::Yield {
        food: ((terrain).food)
            .checked_add((resource).food)
            .ok_or("integer overflow")?,
        shields: (((terrain).shields)
            .checked_add((resource).shields)
            .ok_or("integer overflow")?)
        .checked_add(
            ((((tile).overlay_terrain == 2i64)
                && crate::openciv3::world::Tile__bonus_grassland(tile)?) as i64),
        )
        .ok_or("integer overflow")?,
        commerce: (((terrain).commerce)
            .checked_add((resource).commerce)
            .ok_or("integer overflow")?)
        .checked_add(((river) as i64))
        .ok_or("integer overflow")?,
    })
}

// Python: openciv3/yields.py:27
pub(crate) fn apply_government_yield(
    value: &crate::civ::economy::Yield,
    mut tile_penalty: bool,
    mut trade_bonus: bool,
    mut base_commerce: i64,
    mut food_exempt: bool,
) -> rt::Result<crate::civ::economy::Yield> {
    let (mut food, mut shields, mut commerce): (i64, i64, i64) =
        ((value).food, (value).shields, (value).commerce);
    if tile_penalty {
        food = (food)
            .checked_sub(((!(food_exempt) && (food > 2i64)) as i64))
            .ok_or("integer overflow")?;
        shields = (shields)
            .checked_sub(((shields > 2i64) as i64))
            .ok_or("integer overflow")?;
        commerce = (commerce)
            .checked_sub(((commerce > 2i64) as i64))
            .ok_or("integer overflow")?;
    }
    commerce = (commerce)
        .checked_add(((trade_bonus && (base_commerce > 0i64)) as i64))
        .ok_or("integer overflow")?;
    Ok(crate::civ::economy::Yield {
        food: food,
        shields: shields,
        commerce: commerce,
    })
}

/// Calculate terrain/improvements, then city effects, then government effects.
///
/// The caller supplies freshwater/coastal classification and effective buildings
/// for city-context yields. Omitting buildings is the player's tile valuation.
// Python: openciv3/yields.py:38
pub(crate) fn tile_yield(
    tile: &crate::openciv3::world::Tile,
    player: &crate::openciv3::players::Player,
    civilization: &Option<crate::openciv3::scenario_model::Civilization>,
    rules: &crate::openciv3::rules::RuleCatalog,
    center: &Option<crate::openciv3::cities::City>,
    mut freshwater: bool,
    mut coastal: bool,
    city_buildings: &[crate::openciv3::building_rules::Building],
    river: &Option<bool>,
) -> rt::Result<crate::civ::economy::Yield> {
    let mut river_border: bool = (if (river).is_none() {
        ({
            let __boolean_123705988560016 = ((tile).river_connections & 170i64);
            if (__boolean_123705988560016) != 0 {
                __boolean_123705988560016
            } else {
                ((tile).bonuses & 3840i64)
            }
        }) != 0
    } else {
        ((*river).clone()).is_some()
    });
    let mut terrain: crate::openciv3::rules::Terrain =
        rt::at(&(rules).terrains, (tile).overlay_terrain)?;
    let mut government: crate::openciv3::government_rules::Government =
        rt::at(&(rules).governments, (player).government)?;
    let mut traits: Vec<String> = (if (civilization).is_some() {
        ((*((*civilization).clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone())
        .traits
        .clone()
    } else {
        vec![]
    });
    let mut agricultural: bool = {
        let __needle = "Agricultural".to_string();
        let __container = &traits;
        __container.contains(&__needle)
    };
    let mut bonus: crate::civ::economy::Yield = crate::civ::economy::Yield {
        food: 0i64,
        shields: 0i64,
        commerce: 0i64,
    };
    if ((tile).resource >= 0i64) {
        let mut resource: crate::openciv3::rules::Resource =
            rt::at(&(rules).resources, (tile).resource)?;
        if (((resource).prerequisite < 0i64) || {
            let __needle = (resource).prerequisite;
            let __container = &(player).known_technologies;
            __container.contains(&__needle)
        }) {
            bonus = (resource).bonus.clone();
        }
    }
    let mut natural: crate::civ::economy::Yield =
        natural_tile_yield(tile, &(terrain).yields, &bonus, river_border)?;
    let (mut food, mut shields, mut commerce): (i64, i64, i64) =
        ((natural).food, (natural).shields, (natural).commerce);
    if !(((tile).overlays & 64i64) != 0i64) {
        if (center).is_some() {
            let mut limits: crate::openciv3::global_rules::GlobalRules =
                rt::at(&(rules).global_rules, 0i64)?;
            let mut size_level: i64 = (if (crate::openciv3::cities::City__size(
                &((*((*center).clone()).as_ref().ok_or("expected a value")?).clone()),
            )? <= (limits).maximum_level1_city_size)
            {
                1i64
            } else {
                (if (crate::openciv3::cities::City__size(
                    &((*((*center).clone()).as_ref().ok_or("expected a value")?).clone()),
                )? <= (limits).maximum_level2_city_size)
                {
                    2i64
                } else {
                    3i64
                })
            });
            food = (if agricultural { 3i64 } else { 2i64 });
            shields = (size_level)
                .checked_add((bonus).shields)
                .ok_or("integer overflow")?;
            if ((size_level == 3i64) && {
                let __needle = "Industrious".to_string();
                let __container = &traits;
                __container.contains(&__needle)
            }) {
                shields = (shields).checked_add(1i64).ok_or("integer overflow")?;
            }
            commerce = ((size_level)
                .checked_add(((river_border) as i64))
                .ok_or("integer overflow")?)
            .checked_add((bonus).commerce)
            .ok_or("integer overflow")?;
            if ({
                let __needle = "Commercial".to_string();
                let __container = &traits;
                __container.contains(&__needle)
            } && (size_level > 1i64))
            {
                commerce = (commerce)
                    .checked_add(size_level)
                    .ok_or("integer overflow")?;
            }
            if ((*((*center).clone()).as_ref().ok_or("expected a value")?).clone()).capital {
                commerce = (4i64).max(commerce);
            }
            if (coastal && {
                let __needle = "Seafaring".to_string();
                let __container = &traits;
                __container.contains(&__needle)
            }) {
                commerce = (commerce).checked_add(1i64).ok_or("integer overflow")?;
            }
        } else {
            if (((tile).overlay_terrain == 0i64) && (((tile).overlays & 8i64) != 0 && agricultural))
            {
                food = (food).checked_add(1i64).ok_or("integer overflow")?;
            }
        }
        if (((tile).overlays & (((8i64 | 4i64) | 1i64) | 2i64)) != 0i64) {
            let mut improvements: crate::openciv3::rules::ImprovementYields =
                crate::openciv3::rules::Terrain__improvements(&terrain)?;
            let mut development: Option<crate::civ::economy::Yield> =
                (if (((tile).overlays & 8i64) != 0i64) {
                    Some((improvements).irrigation.clone())
                } else {
                    (if (((tile).overlays & 4i64) != 0i64) {
                        Some((improvements).mine.clone())
                    } else {
                        None
                    })
                });
            let mut route: Option<crate::civ::economy::Yield> =
                (if (((tile).overlays & 2i64) != 0i64) {
                    Some((improvements).railroad.clone())
                } else {
                    (if (((tile).overlays & 1i64) != 0i64) {
                        Some((improvements).road.clone())
                    } else {
                        None
                    })
                });
            for mut improvement in {
                let __tuple_items = (development, route);
                [__tuple_items.0, __tuple_items.1]
            } {
                if (improvement).is_some() {
                    food = (food)
                        .checked_add(
                            ((*(improvement.clone()).as_ref().ok_or("expected a value")?).clone())
                                .food,
                        )
                        .ok_or("integer overflow")?;
                    shields = (shields)
                        .checked_add(
                            ((*(improvement.clone()).as_ref().ok_or("expected a value")?).clone())
                                .shields,
                        )
                        .ok_or("integer overflow")?;
                    commerce = (commerce)
                        .checked_add(
                            ((*(improvement).as_ref().ok_or("expected a value")?).clone()).commerce,
                        )
                        .ok_or("integer overflow")?;
                }
            }
        }
        if (((tile).overlays & 256i64) != 0i64) {
            food = (food).checked_sub(1i64).ok_or("integer overflow")?;
        }
        for mut for_target_88_8 in (&(terrain).extra_improvement_yields).iter() {
            let (mut flag, mut bonus_yield): (i64, crate::civ::economy::Yield) =
                (*for_target_88_8).clone();
            if (((tile).overlays & flag) != 0i64) {
                food = (food)
                    .checked_add((bonus_yield).food)
                    .ok_or("integer overflow")?;
                shields = (shields)
                    .checked_add((bonus_yield).shields)
                    .ok_or("integer overflow")?;
                commerce = (commerce)
                    .checked_add((bonus_yield).commerce)
                    .ok_or("integer overflow")?;
            }
        }
    }
    let (mut base_food, mut base_commerce): (i64, i64) = (food, commerce);
    if (((tile).overlays & 2i64) != 0
        && (!(((&(rules).global_rules).len() as i64) != 0i64)
            || ({
                let __source = &(rules).global_rules;
                let __key = 0i64;
                &__source[rt::index(__source.len(), __key)?]
            })
            .railroad_development_bonus))
    {
        if (((tile).overlays & 8i64) != 0i64) {
            food = (food).checked_add(1i64).ok_or("integer overflow")?;
        } else {
            if (((tile).overlays & 4i64) != 0i64) {
                shields = (shields).checked_add(1i64).ok_or("integer overflow")?;
            }
        }
    }
    if {
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
    } {
        for mut building in (city_buildings).iter() {
            if {
                let __needle = (building).rendered_obsolete_by;
                let __container = &(player).known_technologies;
                __container.contains(&__needle)
            } {
                continue;
            }
            let mut effects: i64 = (if (&(building).water_yield_effects).is_some() {
                (*((building).water_yield_effects.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone()
            } else {
                (building).effects
            });
            if ((effects & 8388608i64) != 0 && (base_food > 0i64)) {
                food = (food).checked_add(1i64).ok_or("integer overflow")?;
            }
            if ((effects & 4194304i64) != 0i64) {
                shields = (shields).checked_add(1i64).ok_or("integer overflow")?;
            }
            if ((effects & 16777216i64) != 0 && (base_commerce > 0i64)) {
                commerce = (commerce).checked_add(1i64).ok_or("integer overflow")?;
            }
        }
    }
    if (match ((player).golden_age_turns.clone()) {
        Some(value) => value,
        None => 0i64,
    } != 0i64)
    {
        shields = (shields)
            .checked_add(((shields > 0i64) as i64))
            .ok_or("integer overflow")?;
        commerce = (commerce)
            .checked_add(((commerce > 0i64) as i64))
            .ok_or("integer overflow")?;
    }
    Ok({
        let __call_314_0 = &(crate::civ::economy::Yield {
            food: food,
            shields: shields,
            commerce: commerce,
        });
        let __call_314_1 = (government).tile_penalty;
        let __call_314_2 = (government).trade_bonus;
        let __call_314_3 = base_commerce;
        let __call_314_4 = ((center).is_some() && (agricultural && freshwater));
        apply_government_yield(
            __call_314_0,
            __call_314_1,
            __call_314_2,
            __call_314_3,
            __call_314_4,
        )
    }?)
}
