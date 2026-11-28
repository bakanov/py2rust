use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct SettlerWeights {
    pub(crate) distance_radius: i64,
    pub(crate) distance_penalty: f64,
    pub(crate) food: f64,
    pub(crate) shields: f64,
    pub(crate) commerce: f64,
    pub(crate) hills: f64,
    pub(crate) luxury: f64,
    pub(crate) strategic: f64,
    pub(crate) water: f64,
}

/// Score sites, with this player's settler destinations supplied explicitly.
///
/// Like legacy planning, same-continent candidates are not path-tested yet.
/// Unknown surrounding tiles contribute yields; only the candidate must be known.
// Python: civ3_ai/settler_locations.py:28
pub(crate) fn settlement_scores(
    game: &crate::openciv3::game_state::GameState,
    player: &crate::openciv3::players::Player,
    start: &(i64, i64),
    reserved: &std::collections::BTreeSet<(i64, i64)>,
    excluded: &std::collections::BTreeSet<(i64, i64)>,
    weights: &SettlerWeights,
    mut workable_rank: Option<i64>,
) -> rt::Result<indexmap::IndexMap<(i64, i64), f64>> {
    let (mut world, mut rules): (
        crate::openciv3::world::WorldMap,
        crate::openciv3::rules::RuleCatalog,
    ) = ((game).world.clone(), (&(game).scenario).rules.clone());
    if (workable_rank).is_none() {
        workable_rank = Some(crate::openciv3::rules::RuleCatalog__workable_rank(&rules)?);
    }
    let mut origin: Option<crate::openciv3::world::Tile> = {
        let __star_args_985: Vec<i64> = {
            let __tuple_value = &((*start).clone());
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        };
        if !(2..=2).contains(&__star_args_985.len()) {
            return Err("wrong function argument count".into());
        }
        crate::openciv3::world::WorldMap__tile_at(
            &world,
            rt::at(&__star_args_985, 0 as i64)?,
            rt::at(&__star_args_985, 1 as i64)?,
        )?
    };
    if ((origin).is_none()
        || ((*(workable_rank.clone()).as_ref().ok_or("expected a value")?).clone() < 1i64))
    {
        return Err("Invalid settlement origin or workable radius"
            .to_string()
            .into());
    }
    let mut blocked: std::collections::BTreeSet<(i64, i64)> = ((*excluded).clone())
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>(
    );

    for mut city in (&(game).cities).iter() {
        settlement_scores__block_near(&world, blocked.clone(), &(((city).x, (city).y)), false)?;
    }
    for mut point in (reserved).iter() {
        settlement_scores__block_near(&world, blocked.clone(), point, true)?;
    }
    let mut memo: indexmap::IndexMap<(i64, i64), f64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();

    let mut scores: indexmap::IndexMap<(i64, i64), f64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut tile in (&(world).tiles).iter() {
        let mut point: (i64, i64) = ((tile).x, (tile).y);
        if ({
            let __needle = point.clone();
            let __container = &((&(game).visibility)
                .get(&((player).civilization))
                .ok_or("missing dict key")?)
            .known;
            !__container.contains(&__needle)
        } || ({
            let __needle = point.clone();
            let __container = &blocked;
            __container.contains(&__needle)
        } || (((tile).continent
            != ((*(origin.clone()).as_ref().ok_or("expected a value")?).clone()).continent)
            || (!(({
                let __source = &(rules).terrains;
                let __key = (tile).overlay_terrain;
                &__source[rt::index(__source.len(), __key)?]
            })
            .allow_cities)
                || ((tile).overlays & 128i64) != 0))))
        {
            continue;
        }
        let mut score: f64 = settlement_scores__yield_score(
            memo.clone(),
            player,
            game,
            &rules,
            &world,
            weights,
            tile,
        )?;
        for mut other in crate::strategy::grid::within_rank(
            &world,
            tile,
            (*(workable_rank.clone()).as_ref().ok_or("expected a value")?).clone(),
        )? {
            let mut rank: i64 = crate::strategy::grid::rank_distance(
                &({
                    let __structural_value = world.clone();
                    crate::strategy::grid::DistanceMap {
                        width: (__structural_value).width.clone(),
                        height: (__structural_value).height.clone(),
                        wrap_x: (__structural_value).wrap_x.clone(),
                        wrap_y: (__structural_value).wrap_y.clone(),
                    }
                }),
                &({
                    let __structural_value = (*tile).clone();
                    crate::strategy::grid::GridPoint {
                        x: (__structural_value).x.clone(),
                        y: (__structural_value).y.clone(),
                    }
                }),
                &({
                    let __structural_value = other.clone();
                    crate::strategy::grid::GridPoint {
                        x: (__structural_value).x.clone(),
                        y: (__structural_value).y.clone(),
                    }
                }),
            )?;
            if (rank > 0i64) {
                score = rt::finite(
                    score
                        + rt::finite(
                            settlement_scores__yield_score(
                                memo.clone(),
                                player,
                                game,
                                &rules,
                                &world,
                                weights,
                                &other,
                            )? * ((0i64) as f64).max(rt::int_true_div(
                                (((*(workable_rank.clone())
                                    .as_ref()
                                    .ok_or("expected a value")?)
                                .clone())
                                .checked_sub(rank)
                                .ok_or("integer overflow")?)
                                .checked_add(1i64)
                                .ok_or("integer overflow")?,
                                (*(workable_rank.clone()).as_ref().ok_or("expected a value")?)
                                    .clone(),
                            )?),
                        )?,
                )?;
            }
        }
        if ((tile).base_terrain == 5i64) {
            score = rt::finite(score + (weights).hills)?;
        }
        if ({
            let mut __comprehension_result_987: Vec<bool> = Vec::new();
            let __comprehension_source_986 =
                (crate::openciv3::world::WorldMap__neighbors(&world, tile)?);
            for other in __comprehension_source_986.iter().cloned() {
                __comprehension_result_987.push(crate::openciv3::hydrology::is_water(&other)?);
            }
            __comprehension_result_987
        })
        .into_iter()
        .any(|__value| __value)
        {
            score = rt::finite(score + (weights).water)?;
        }
        score = rt::finite(
            score
                + rt::finite(
                    rt::int_true_div(
                        ({
                            let __source = &(rules).terrains;
                            let __key = (tile).base_terrain;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .defense_bonus,
                        100i64,
                    )? * ((20i64) as f64),
                )?,
        )?;
        let mut before_distance: f64 = score;
        let mut separation: i64 = crate::strategy::grid::distance(
            &({
                let __structural_value = world.clone();
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
                let __structural_value = (*tile).clone();
                crate::strategy::grid::GridPoint {
                    x: (__structural_value).x.clone(),
                    y: (__structural_value).y.clone(),
                }
            }),
        )?;
        if (separation > (weights).distance_radius) {
            score = rt::finite(
                score + rt::finite((weights).distance_penalty * ((separation) as f64))?,
            )?;
        }
        if ((before_distance > ((0i64) as f64)) && (score <= ((0i64) as f64))) {
            score = ((1i64) as f64);
        }
        if (score > ((0i64) as f64)) {
            {
                let __value = score;
                let __key = point;
                scores.insert(__key, __value);
            }
        }
    }
    Ok(scores)
}

// Python: civ3_ai/settler_locations.py:103
pub(crate) fn count_open_sites(
    game: &crate::openciv3::game_state::GameState,
    scores: &indexmap::IndexMap<(i64, i64), f64>,
) -> rt::Result<i64> {
    let mut remaining: std::collections::BTreeSet<(i64, i64)> =
        (((*scores).clone()).keys().cloned().collect::<Vec<_>>())
            .into_iter()
            .collect::<std::collections::BTreeSet<_>>();
    let mut count: i64 = 0i64;
    for mut point in {
        let mut __decorated: Vec<(f64, (i64, i64))> = Vec::new();
        for __item in (((*scores).clone()).keys().cloned().collect::<Vec<_>>()).into_iter() {
            let point = __item;
            let __key = {
                (scores)
                    .get(&(point.clone()))
                    .ok_or("missing dict key")?
                    .clone()
            };
            __decorated.push((__key, point));
        }
        __decorated.sort_by(|left, right| {
            if true {
                right.0.total_cmp(&left.0)
            } else {
                left.0.total_cmp(&right.0)
            }
        });
        let mut __result = Vec::new();
        for (_, __item) in __decorated {
            __result.push(__item);
        }
        __result
    } {
        if {
            let __needle = point.clone();
            let __container = &remaining;
            !__container.contains(&__needle)
        } {
            continue;
        }
        count = (count).checked_add(1i64).ok_or("integer overflow")?;
        let mut tile: Option<crate::openciv3::world::Tile> = {
            let __star_args_988: Vec<i64> = {
                let __tuple_value = &point;
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_988.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &(game).world,
                rt::at(&__star_args_988, 0 as i64)?,
                rt::at(&__star_args_988, 1 as i64)?,
            )?
        };
        if (tile).is_none() {
            return Err("Invalid settlement candidate".to_string().into());
        }
        {
            let __other = {
                let mut __comprehension_result_990: Vec<(i64, i64)> = Vec::new();
                let __comprehension_source_989 = (crate::openciv3::world::WorldMap__neighbors(
                    &(game).world,
                    &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?);
                for other in __comprehension_source_989.iter().cloned() {
                    __comprehension_result_990.push(((other).x, (other).y));
                }
                __comprehension_result_990
            };
            (remaining).retain(|__item| !(__other).contains(__item));
        };
    }
    Ok(count)
}

// Python: civ3_ai/settler_locations.py:44
pub(crate) fn settlement_scores__block_near(
    world: &crate::openciv3::world::WorldMap,
    mut blocked: std::collections::BTreeSet<(i64, i64)>,
    point: &(i64, i64),
    mut land_only: bool,
) -> rt::Result<()> {
    let mut center: Option<crate::openciv3::world::Tile> = {
        let __star_args_991: Vec<i64> = {
            let __tuple_value = &((*point).clone());
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        };
        if !(2..=2).contains(&__star_args_991.len()) {
            return Err("wrong function argument count".into());
        }
        crate::openciv3::world::WorldMap__tile_at(
            world,
            rt::at(&__star_args_991, 0 as i64)?,
            rt::at(&__star_args_991, 1 as i64)?,
        )?
    };
    if (center).is_none() {
        return Err("Invalid city or reserved destination".to_string().into());
    }
    {
        blocked.insert((
            ((*(center.clone()).as_ref().ok_or("expected a value")?).clone()).x,
            ((*(center.clone()).as_ref().ok_or("expected a value")?).clone()).y,
        ));
    };
    let mut first: Vec<crate::openciv3::world::Tile> = {
        let mut __comprehension_result_993: Vec<crate::openciv3::world::Tile> = Vec::new();
        let __comprehension_source_992 = (crate::openciv3::world::WorldMap__neighbors(
            world,
            &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?);
        for tile in __comprehension_source_992.iter().cloned() {
            if (!(land_only) || !(crate::openciv3::hydrology::is_water(&tile)?)) {
                __comprehension_result_993.push(tile.clone());
            }
        }
        __comprehension_result_993
    };
    for mut tile in first {
        {
            blocked.insert(((tile).x, (tile).y));
        };
        (blocked).extend({
            let mut __comprehension_result_995: Vec<(i64, i64)> = Vec::new();
            let __comprehension_source_994 =
                (crate::openciv3::world::WorldMap__neighbors(world, &tile)?);
            for other in __comprehension_source_994.iter().cloned() {
                if (!(land_only) || !(crate::openciv3::hydrology::is_water(&other)?)) {
                    __comprehension_result_995.push(((other).x, (other).y));
                }
            }
            __comprehension_result_995
        });
    }
    Ok(())
}

// Python: civ3_ai/settler_locations.py:60
pub(crate) fn settlement_scores__yield_score(
    mut memo: indexmap::IndexMap<(i64, i64), f64>,
    player: &crate::openciv3::players::Player,
    game: &crate::openciv3::game_state::GameState,
    rules: &crate::openciv3::rules::RuleCatalog,
    world: &crate::openciv3::world::WorldMap,
    weights: &SettlerWeights,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<f64> {
    let mut point: (i64, i64) = ((tile).x, (tile).y);
    if {
        let __needle = point.clone();
        let __container = &memo;
        !__container.contains_key(&__needle)
    } {
        let mut value: crate::civ::economy::Yield = {
            let __call_996_0 = &((*tile).clone());
            let __call_996_1 = &((*player).clone());
            let __call_996_2 = &(Some(rt::at(
                &(&(game).scenario).civilizations,
                (player).civilization,
            )?));
            let __call_996_3 = &((*rules).clone());
            let __call_996_4 =
                &(Some((crate::openciv3::hydrology::river_edges(world, tile)?) != 0));
            let __call_996_default_4 = &None;
            let __call_996_default_5 = false;
            let __call_996_default_6 = false;
            let __call_996_default_7 = &(vec![]);
            crate::openciv3::yields::tile_yield(
                __call_996_0,
                __call_996_1,
                __call_996_2,
                __call_996_3,
                __call_996_default_4,
                __call_996_default_5,
                __call_996_default_6,
                __call_996_default_7,
                __call_996_4,
            )
        }?;
        let mut score: f64 = rt::finite(
            rt::finite(
                rt::finite((((value).food) as f64) * (weights).food)?
                    + rt::finite((((value).shields) as f64) * (weights).shields)?,
            )? + rt::finite((((value).commerce) as f64) * (weights).commerce)?,
        )?;
        if ((tile).resource >= 0i64) {
            let mut resource: crate::openciv3::rules::Resource =
                rt::at(&(rules).resources, (tile).resource)?;
            if (((resource).prerequisite < 0i64) || {
                let __needle = (resource).prerequisite;
                let __container = &(player).known_technologies;
                __container.contains(&__needle)
            }) {
                if ((resource).kind == 1i64) {
                    score = rt::finite(score + (weights).luxury)?;
                } else {
                    if ((resource).kind == 2i64) {
                        score = rt::finite(score + (weights).strategic)?;
                    }
                }
            }
        }
        {
            let __value = score;
            let __key = point.clone();
            memo.insert(__key, __value);
        }
    }
    Ok((memo).get(&(point)).ok_or("missing dict key")?.clone())
}
