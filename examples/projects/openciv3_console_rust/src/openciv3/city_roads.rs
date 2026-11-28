use py2rust_service_runtime as rt;

/// Apply the legacy city road callbacks in city order.
///
/// Call on initialization, founding, or discovery of a road-building technology.
/// This only updates transport overlays; clearing a newly founded city's other
/// improvements and vegetation belongs to the city lifecycle.
// Python: openciv3/city_roads.py:11
pub(crate) fn connect_city_roads(
    world: &crate::openciv3::world::WorldMap,
    cities: &[crate::openciv3::cities::City],
    players: &[crate::openciv3::players::Player],
    rules: &crate::openciv3::rules::RuleCatalog,
) -> rt::Result<crate::openciv3::world::WorldMap> {
    let mut jobs: Vec<(i64, i64)> = ({
        let mut __comprehension_result_316: Vec<(i64, i64)> = Vec::new();
        let __comprehension_source_315 = ((rules).worker_jobs.clone());
        for job in __comprehension_source_315.iter().cloned() {
            __comprehension_result_316.push((
                crate::openciv3::worker_rules::improvement_for(&job)?,
                (job).prerequisite,
            ));
        }
        __comprehension_result_316
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut tiles: Vec<crate::openciv3::world::Tile> =
        (&(world).tiles).iter().cloned().collect::<Vec<_>>();
    let mut changed: bool = false;
    for mut city in (cities).iter() {
        let mut center: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(world, (city).x, (city).y)?;
        if (center).is_none() {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "City ".to_string(),
                    ((city).id).to_string(),
                    " has no map tile".to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        let mut index: i64 = ((((*(center.clone()).as_ref().ok_or("expected a value")?).clone())
            .y)
            .checked_mul(rt::int_floor_div((world).width, 2i64)?)
            .ok_or("integer overflow")?)
        .checked_add(rt::int_floor_div(
            ((*(center.clone()).as_ref().ok_or("expected a value")?).clone()).x,
            2i64,
        )?)
        .ok_or("integer overflow")?;
        center = Some(rt::at(&tiles, index)?);
        let mut neighbors: Vec<crate::openciv3::world::Tile> = {
            let mut __comprehension_result_318: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_317 = (crate::openciv3::world::WorldMap__neighbors(
                world,
                &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
            )?);
            for t in __comprehension_source_317.iter().cloned() {
                __comprehension_result_318.push(rt::at(
                    &tiles,
                    (((t).y)
                        .checked_mul(rt::int_floor_div((world).width, 2i64)?)
                        .ok_or("integer overflow")?)
                    .checked_add(rt::int_floor_div((t).x, 2i64)?)
                    .ok_or("integer overflow")?,
                )?);
            }
            __comprehension_result_318
        };
        let mut overlays: i64 =
            ((*(center.clone()).as_ref().ok_or("expected a value")?).clone()).overlays;
        let mut known: std::collections::BTreeSet<i64> = ({
            let __source = players;
            let __key = (city).owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .known_technologies
        .clone();
        let mut available: std::collections::BTreeSet<i64> = {
            let mut __comprehension_result_320: std::collections::BTreeSet<i64> =
                std::collections::BTreeSet::new();
            let __comprehension_source_319 = (jobs.clone());
            for (improvement, tech) in __comprehension_source_319.iter().cloned() {
                if ((tech < 0i64) || {
                    let __needle = tech;
                    let __container = &known;
                    __container.contains(&__needle)
                }) {
                    __comprehension_result_320.insert(improvement);
                }
            }
            __comprehension_result_320
        };
        if ({
            let __needle = 2i64;
            let __container = &available;
            __container.contains(&__needle)
        } && ({
            let mut __comprehension_result_322: Vec<i64> = Vec::new();
            let __comprehension_source_321 = (neighbors.clone());
            for t in __comprehension_source_321.iter().cloned() {
                __comprehension_result_322.push(((t).overlays & 2i64));
            }
            __comprehension_result_322
        })
        .into_iter()
        .any(|__value| __value != 0))
        {
            overlays = ((overlays & !(1i64)) | 2i64);
        } else {
            if ({
                let __needle = 1i64;
                let __container = &available;
                __container.contains(&__needle)
            } && (!((overlays & (1i64 | 2i64)) != 0i64)
                && ({
                    let mut __comprehension_result_324: Vec<i64> = Vec::new();
                    let __comprehension_source_323 = (neighbors.clone());
                    for t in __comprehension_source_323.iter().cloned() {
                        __comprehension_result_324.push(((t).overlays & (1i64 | 2i64)));
                    }
                    __comprehension_result_324
                })
                .into_iter()
                .any(|__value| __value != 0)))
            {
                overlays = (overlays | 1i64);
            }
        }
        if (overlays != ((*(center.clone()).as_ref().ok_or("expected a value")?).clone()).overlays)
        {
            {
                let __value = {
                    let mut __replacement =
                        ((*(center).as_ref().ok_or("expected a value")?).clone()).clone();
                    __replacement.overlays = overlays;
                    __replacement
                };
                let __key = index;
                let __index = rt::index(tiles.len(), __key)?;
                tiles[__index] = __value;
            }
            changed = true;
        }
    }
    Ok((if changed {
        {
            let mut __replacement = ((*world).clone()).clone();
            __replacement.tiles = (tiles).iter().cloned().collect::<Vec<_>>();
            __replacement
        }
    } else {
        (*world).clone()
    }))
}
