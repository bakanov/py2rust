use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct UnitPath {
    pub(crate) destination: (i64, i64),
    pub(crate) steps: Vec<(i64, i64)>,
    pub(crate) reachable: bool,
    pub(crate) cost: f64,
}

#[derive(Clone, PartialEq)]
pub(crate) struct _MovementCosts {
    pub(crate) game: crate::openciv3::game_state::GameState,
    pub(crate) owner: i64,
    pub(crate) passage: std::collections::BTreeSet<i64>,
    pub(crate) prototype: Option<i64>,
    pub(crate) respect_fog: bool,
    pub(crate) preview: bool,
    pub(crate) knowledge: crate::openciv3::visibility::TileKnowledge,
    pub(crate) terrains: Vec<crate::openciv3::rules::Terrain>,
    pub(crate) exempt: std::collections::BTreeSet<i64>,
    pub(crate) all_terrain_as_roads: bool,
    pub(crate) bridges: bool,
    pub(crate) city_owners: indexmap::IndexMap<i64, i64>,
    pub(crate) city_points: std::collections::BTreeSet<(i64, i64)>,
    pub(crate) road: f64,
    pub(crate) railroad: f64,
}

/// Cost of one edge; passage lists civilizations granting right of passage.
///
/// Persistent relationship grants are included; explicit grants can supplement them.
// Python: openciv3/pathfinding.py:19
pub(crate) fn movement_cost(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    source: &crate::openciv3::world::Tile,
    target: &crate::openciv3::world::Tile,
    passage: &std::collections::BTreeSet<i64>,
    prototype: &Option<i64>,
    mut respect_fog: bool,
) -> rt::Result<f64> {
    _MovementCosts__edge(
        &(_MovementCosts____post_init__(_MovementCosts {
            game: (*game).clone(),
            owner: owner,
            passage: (*passage).clone(),
            prototype: (*prototype).clone(),
            respect_fog: respect_fog,
            preview: false,
            knowledge: crate::openciv3::visibility::TileKnowledge {
                known: {
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in vec![].into_iter() {
                        __result.insert(__item);
                    }
                    __result
                },
                visible: {
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in vec![].into_iter() {
                        __result.insert(__item);
                    }
                    __result
                },
                frontier: {
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in vec![].into_iter() {
                        __result.insert(__item);
                    }
                    __result
                },
                known_overlays: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                known_ruins: {
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in vec![].into_iter() {
                        __result.insert(__item);
                    }
                    __result
                },
                exploration_targets: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                fully_explored_oceans: false,
                known_terrain: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
            },
            terrains: vec![],
            exempt: std::collections::BTreeSet::new(),
            all_terrain_as_roads: false,
            bridges: false,
            city_owners: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
            city_points: {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![].into_iter() {
                    __result.insert(__item);
                }
                __result
            },
            road: 0.0f64,
            railroad: 0.0f64,
        })?),
        source,
        target,
    )
}

// Python: openciv3/pathfinding.py:49
pub(crate) fn _MovementCosts____post_init__(
    mut self_: _MovementCosts,
) -> rt::Result<_MovementCosts> {
    self_.passage = {
        let __set_left = (self_).passage.clone();
        let __set_right = crate::openciv3::diplomacy::Diplomacy__passage_grants(
            &(&(self_).game).diplomacy,
            (self_).owner,
        )?;
        let mut __result = std::collections::BTreeSet::new();
        for __item in __set_left.union(&__set_right) {
            __result.insert(__item.clone());
        }
        __result
    };
    let mut player: crate::openciv3::players::Player =
        rt::at(&(&(self_).game).players, (self_).owner)?;
    self_.preview = ((self_).respect_fog && (player).human);
    self_.knowledge = (&(&(self_).game).visibility)
        .get(&((self_).owner))
        .ok_or("missing dict key")?
        .clone();
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(&(self_).game).scenario).rules.clone();
    self_.terrains = (rules).terrains.clone();
    let mut kind: Option<crate::openciv3::unit_rules::UnitPrototype> =
        (if (&(self_).prototype).is_some() {
            Some(rt::at(
                &(rules).units,
                (*((self_).prototype.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone(),
            )?)
        } else {
            None
        });
    self_.exempt = (if (kind).is_some() {
        {
            let mut __result: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
            for __item in (((*(kind.clone()).as_ref().ok_or("expected a value")?).clone())
                .ignore_movement_cost
                .clone())
            .into_iter()
            {
                __result.insert(__item);
            }
            __result
        }
    } else {
        std::collections::BTreeSet::new()
    });
    self_.all_terrain_as_roads = ((kind).is_some()
        && (((*(kind.clone()).as_ref().ok_or("expected a value")?).clone()).abilities & 16i64)
            != 0);
    self_.bridges = ({
        let mut __comprehension_result_408: Vec<i64> = Vec::new();
        let __comprehension_source_407 = ((player).known_technologies.clone());
        for tech in __comprehension_source_407.iter().cloned() {
            __comprehension_result_408.push(
                (({
                    let __source = &(rules).technologies;
                    let __key = tech;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .effects
                    & 4i64),
            );
        }
        __comprehension_result_408
    })
    .into_iter()
    .any(|__value| __value != 0);
    self_.city_owners = {
        let mut __comprehension_result_410: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_409 = ((&(self_).game).cities.clone());
        for city in __comprehension_source_409.iter().cloned() {
            {
                let (__key, __value) = ((city).id, (city).owner);
                __comprehension_result_410.insert(__key, __value);
            }
        }
        __comprehension_result_410
    };
    self_.city_points = {
        let mut __comprehension_result_412: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_411 = ((&(self_).game).cities.clone());
        for city in __comprehension_source_411.iter().cloned() {
            __comprehension_result_412.insert(((city).x, (city).y));
        }
        __comprehension_result_412
    };
    self_.road = (if (((&(rules).global_rules).len() as i64) != 0i64) {
        ({
            let __source = &(rules).global_rules;
            let __key = 0i64;
            &__source[rt::index(__source.len(), __key)?]
        })
        .road_movement_cost
    } else {
        rt::int_true_div(1i64, 3i64)?
    });
    self_.railroad = (if (((&(rules).global_rules).len() as i64) != 0i64) {
        ({
            let __source = &(rules).global_rules;
            let __key = 0i64;
            &__source[rt::index(__source.len(), __key)?]
        })
        .railroad_movement_cost
    } else {
        0.0f64
    });
    Ok(self_.clone())
}

// Python: openciv3/pathfinding.py:66
pub(crate) fn _MovementCosts___improvement(
    self_: &_MovementCosts,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<Option<f64>> {
    let mut point: (i64, i64) = ((tile).x, (tile).y);
    let mut flags: i64 = (if ((self_).preview && {
        let __needle = point.clone();
        let __container = &(&(self_).knowledge).visible;
        !__container.contains(&__needle)
    }) {
        {
            let __mapping = &(&(self_).knowledge).known_overlays;
            let __key = point.clone();
            let __default = 0i64;
            __mapping.get(&__key).cloned().unwrap_or(__default)
        }
    } else {
        (tile).overlays
    });
    if ((flags & 2i64) != 0i64) {
        return Ok((if ((self_).railroad
            == (((1i64).checked_neg().ok_or("integer overflow")?) as f64))
        {
            None
        } else {
            Some((self_).railroad)
        }));
    }
    if ((flags & 1i64) != 0i64) {
        return Ok(
            (if ((self_).road == (((1i64).checked_neg().ok_or("integer overflow")?) as f64)) {
                None
            } else {
                Some((self_).road)
            }),
        );
    }
    Ok((if {
        let __needle = point;
        let __container = &(self_).city_points;
        __container.contains(&__needle)
    } {
        Some(0.0f64)
    } else {
        None
    }))
}

// Python: openciv3/pathfinding.py:76
pub(crate) fn _MovementCosts__edge(
    self_: &_MovementCosts,
    source: &crate::openciv3::world::Tile,
    target: &crate::openciv3::world::Tile,
) -> rt::Result<f64> {
    let mut claim: Option<i64>;
    let mut point: (i64, i64) = ((target).x, (target).y);
    let mut known: bool = {
        let __needle = point.clone();
        let __container = &(&(self_).knowledge).known;
        __container.contains(&__needle)
    };
    if ((self_).preview && !(known)) {
        return Ok(
            (if ((self_).all_terrain_as_roads && ((self_).road >= ((0i64) as f64))) {
                (1.0f64).min((self_).road)
            } else {
                1.0f64
            }),
        );
    }
    let mut terrain: i64 = (if ((self_).preview && {
        let __needle = point.clone();
        let __container = &(&(self_).knowledge).visible;
        !__container.contains(&__needle)
    }) {
        {
            let __mapping = &(&(self_).knowledge).known_terrain;
            let __key = point.clone();
            let __default = (target).overlay_terrain;
            __mapping.get(&__key).cloned().unwrap_or(__default)
        }
    } else {
        (target).overlay_terrain
    });
    let mut terrain_cost: f64 = (({
        let __source = &(self_).terrains;
        let __key = terrain;
        &__source[rt::index(__source.len(), __key)?]
    })
    .movement_cost as f64);
    if {
        let __needle = terrain;
        let __container = &(self_).exempt;
        __container.contains(&__needle)
    } {
        terrain_cost = (terrain_cost).min(1.0f64);
    }
    if ((self_).all_terrain_as_roads && ((self_).road >= ((0i64) as f64))) {
        terrain_cost = (terrain_cost).min((self_).road);
    }
    if !((self_).bridges) {
        let mut world: crate::openciv3::world::WorldMap = (&(self_).game).world.clone();
        let mut river: i64 = crate::openciv3::hydrology::river_edges(&world, source)?;
        if ({
            let mut __comprehension_result_414: Vec<bool> = Vec::new();
            let __comprehension_source_413 = (({
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
            .collect::<Vec<_>>());
            for (index, (dx, dy)) in __comprehension_source_413.iter().cloned() {
                __comprehension_result_414.push(
                    ((river & rt::int_lshift(1i64, index)?) != 0
                        && (crate::openciv3::world::WorldMap__tile_at(
                            &world,
                            ((source).x).checked_add(dx).ok_or("integer overflow")?,
                            ((source).y).checked_add(dy).ok_or("integer overflow")?,
                        )? == Some((*target).clone()))),
                );
            }
            __comprehension_result_414
        })
        .into_iter()
        .any(|__value| __value)
        {
            return Ok(terrain_cost);
        }
    }
    let mut owners: Vec<Option<i64>> = {
        let mut __comprehension_result_416: Vec<Option<i64>> = Vec::new();
        let mut claim: Option<i64>;
        let __comprehension_source_415 = ({
            let __tuple_value = &(((*source).clone(), (*target).clone()));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        for tile in __comprehension_source_415.iter().cloned() {
            __comprehension_result_416.push(
                (if ({
                    claim = ((&(self_).game).ownership.clone())
                        .get(&(((tile).x, (tile).y)))
                        .cloned();
                    claim.clone()
                })
                .is_some()
                {
                    Some(
                        (&(self_).city_owners)
                            .get(&((*(claim.clone()).as_ref().ok_or("expected a value")?).clone()))
                            .ok_or("missing dict key")?
                            .clone(),
                    )
                } else {
                    None
                }),
            );
        }
        __comprehension_result_416
    };
    if ((known || !((self_).respect_fog))
        && !(({
            let mut __comprehension_result_418: Vec<bool> = Vec::new();
            let __comprehension_source_417 = (owners.clone());
            for value in __comprehension_source_417.iter().cloned() {
                __comprehension_result_418.push(
                    ((value.clone()).is_none()
                        || ((*(value.clone()).as_ref().ok_or("expected a value")?).clone())
                            == ((((), (self_).owner)).1)),
                );
            }
            __comprehension_result_418
        })
        .into_iter()
        .all(|__value| __value)
            || ({
                let mut __comprehension_result_420: Vec<bool> = Vec::new();
                let __comprehension_source_419 = (owners.clone());
                for value in __comprehension_source_419.iter().cloned() {
                    __comprehension_result_420.push(
                        ((value.clone() != Some((self_).owner))
                            && match (value.clone()) {
                                Some(__value) => {
                                    let __needle = __value;
                                    let __container = &(self_).passage;
                                    __container.contains(&__needle)
                                }
                                None => false,
                            }),
                    );
                }
                __comprehension_result_420
            })
            .into_iter()
            .any(|__value| __value)))
    {
        return Ok(terrain_cost);
    }
    if (crate::openciv3::hydrology::is_water(source)? && {
        let __needle = point;
        let __container = &(self_).city_points;
        __container.contains(&__needle)
    }) {
        return Ok((if (self_).all_terrain_as_roads {
            (1.0f64).min(terrain_cost)
        } else {
            1.0f64
        }));
    }
    let (mut first, mut second): (Option<f64>, Option<f64>) = (
        _MovementCosts___improvement(self_, source)?,
        _MovementCosts___improvement(self_, target)?,
    );
    if ((first).is_none() || (second).is_none()) {
        return Ok(terrain_cost);
    }
    let mut improvement_cost: f64 = ((*(first).as_ref().ok_or("expected a value")?).clone())
        .max((*(second).as_ref().ok_or("expected a value")?).clone());
    Ok((if (self_).all_terrain_as_roads {
        (terrain_cost).min(improvement_cost)
    } else {
        improvement_cost
    }))
}

/// Legacy goto estimate; -1 means no steps, zero means all-rail travel.
// Python: openciv3/pathfinding.py:115
pub(crate) fn UnitPath__turns(
    self_: &UnitPath,
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    passage: &std::collections::BTreeSet<i64>,
) -> rt::Result<i64> {
    Ok(({
        let __call_421_0 = self_;
        let __call_421_1 = game;
        let __call_421_2 = unit;
        let __call_421_3 = passage;
        UnitPath__estimate(__call_421_0, __call_421_1, __call_421_2, __call_421_3)
    }?)
    .0
    .clone())
}

/// Return the turn estimate and the scheduled stops, including the destination.
// Python: openciv3/pathfinding.py:119
pub(crate) fn UnitPath__estimate(
    self_: &UnitPath,
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    passage: &std::collections::BTreeSet<i64>,
) -> rt::Result<(i64, Vec<(i64, i64)>)> {
    if (!((self_).reachable) || !(((&(self_).steps).len() as i64) != 0i64)) {
        return Ok(((1i64).checked_neg().ok_or("integer overflow")?, vec![]));
    }
    let mut maximum: i64 = ({
        let __source = &(&(&(game).scenario).rules).units;
        let __key = (unit).prototype;
        &__source[rt::index(__source.len(), __key)?]
    })
    .movement;
    let mut remaining: f64 = (unit).movement_remaining;
    let mut turns: i64 = 0i64;
    let mut stops: Vec<(i64, i64)> = vec![];
    let mut source: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if (source).is_none() {
        return Err("Unit is outside the map".to_string().into());
    }
    let mut costs: _MovementCosts = _MovementCosts____post_init__(_MovementCosts {
        game: (*game).clone(),
        owner: (unit).owner,
        passage: (*passage).clone(),
        prototype: Some((unit).prototype),
        respect_fog: true,
        preview: false,
        knowledge: crate::openciv3::visibility::TileKnowledge {
            known: {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![].into_iter() {
                    __result.insert(__item);
                }
                __result
            },
            visible: {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![].into_iter() {
                    __result.insert(__item);
                }
                __result
            },
            frontier: {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![].into_iter() {
                    __result.insert(__item);
                }
                __result
            },
            known_overlays: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
            known_ruins: {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![].into_iter() {
                    __result.insert(__item);
                }
                __result
            },
            exploration_targets: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
            fully_explored_oceans: false,
            known_terrain: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
        },
        terrains: vec![],
        exempt: std::collections::BTreeSet::new(),
        all_terrain_as_roads: false,
        bridges: false,
        city_owners: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
        city_points: {
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        },
        road: 0.0f64,
        railroad: 0.0f64,
    })?;
    for mut point in (&(self_).steps).iter() {
        let mut target: Option<crate::openciv3::world::Tile> = {
            let __star_args_422: Vec<i64> = {
                let __tuple_value = &((*point).clone());
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_422.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &(game).world,
                rt::at(&__star_args_422, 0 as i64)?,
                rt::at(&__star_args_422, 1 as i64)?,
            )?
        };
        if (target).is_none() {
            return Err("Path is outside the map".to_string().into());
        }
        let mut cost: f64 = _MovementCosts__edge(
            &costs,
            &((*(source).as_ref().ok_or("expected a value")?).clone()),
            &((*(target.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?;
        remaining = (0.0f64).max(rt::finite(remaining - cost)?);
        if (remaining <= 0.0001f64) {
            turns = (turns).checked_add(1i64).ok_or("integer overflow")?;
            {
                stops.push((*point).clone());
            };
            remaining = (maximum as f64);
        }
        source = target;
    }
    if (remaining
        < rt::finite(
            (if (turns == 0i64) {
                (unit).movement_remaining
            } else {
                ((maximum) as f64)
            }) - 0.0001f64,
        )?)
    {
        turns = (turns).checked_add(1i64).ok_or("integer overflow")?;
    }
    if (!(((stops).len() as i64) != 0i64)
        || (rt::at(&stops, (1i64).checked_neg().ok_or("integer overflow")?)?
            != (self_).destination.clone()))
    {
        {
            stops.push((self_).destination.clone());
        };
    }
    Ok((turns, (stops).iter().cloned().collect::<Vec<_>>()))
}

/// Shortest normalized-turn route using Dijkstra (A* with zero heuristic).
///
/// Zero-cost rail edges require a zero lower bound for an optimal route. Entry
/// intent is assessed from the unit's actual position, matching legacy goto.
// Python: openciv3/pathfinding.py:150
pub(crate) fn find_path(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    destination: &crate::openciv3::world::Tile,
    passage: &std::collections::BTreeSet<i64>,
) -> rt::Result<UnitPath> {
    let mut world: crate::openciv3::world::WorldMap = (game).world.clone();
    let mut start: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&world, (unit).x, (unit).y)?;
    if (start).is_none() {
        return Err("Unit is outside the map".to_string().into());
    }
    let (mut origin, mut goal): ((i64, i64), (i64, i64)) = (
        (
            ((*(start.clone()).as_ref().ok_or("expected a value")?).clone()).x,
            ((*(start.clone()).as_ref().ok_or("expected a value")?).clone()).y,
        ),
        ((destination).x, (destination).y),
    );
    let mut missing: UnitPath = UnitPath {
        destination: goal.clone(),
        steps: vec![],
        reachable: false,
        cost: 0.0f64,
    };
    if ({
        let __star_args_423: Vec<i64> = {
            let __tuple_value = &(goal.clone());
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        };
        if !(2..=2).contains(&__star_args_423.len()) {
            return Err("wrong function argument count".into());
        }
        crate::openciv3::world::WorldMap__tile_at(
            &world,
            rt::at(&__star_args_423, 0 as i64)?,
            rt::at(&__star_args_423, 1 as i64)?,
        )?
    } != Some((*destination).clone()))
    {
        return Err("Destination is not in this world".to_string().into());
    }
    if (origin.clone() == goal.clone()) {
        return Ok(UnitPath {
            destination: goal,
            steps: vec![],
            reachable: true,
            cost: 0.0f64,
        });
    }
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    let mut human: bool = ({
        let __source = &(game).players;
        let __key = (unit).owner;
        &__source[rt::index(__source.len(), __key)?]
    })
    .human;
    if (((kind).movement <= 0i64) || ((kind).domain == 2i64)) {
        return Ok(missing);
    }
    if (!(human)
        && (!(crate::openciv3::hydrology::is_water(
            &((*(start.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?) && (!(crate::openciv3::hydrology::is_water(destination)?)
            && (((*(start.clone()).as_ref().ok_or("expected a value")?).clone()).continent
                != (destination).continent))))
    {
        return Ok(missing);
    }
    let mut known: std::collections::BTreeSet<(i64, i64)> = ((&(game).visibility)
        .get(&((unit).owner))
        .ok_or("missing dict key")?)
    .known
    .clone();
    let mut own_cities: std::collections::BTreeSet<(i64, i64)> = {
        let mut __comprehension_result_425: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        let __comprehension_source_424 = ((game).cities.clone());
        for city in __comprehension_source_424.iter().cloned() {
            if ((city).owner == (unit).owner) {
                __comprehension_result_425.insert(((city).x, (city).y));
            }
        }
        __comprehension_result_425
    };
    let mut movement: _MovementCosts = _MovementCosts____post_init__(_MovementCosts {
        game: (*game).clone(),
        owner: (unit).owner,
        passage: (*passage).clone(),
        prototype: Some((unit).prototype),
        respect_fog: true,
        preview: false,
        knowledge: crate::openciv3::visibility::TileKnowledge {
            known: {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![].into_iter() {
                    __result.insert(__item);
                }
                __result
            },
            visible: {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![].into_iter() {
                    __result.insert(__item);
                }
                __result
            },
            frontier: {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![].into_iter() {
                    __result.insert(__item);
                }
                __result
            },
            known_overlays: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
            known_ruins: {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![].into_iter() {
                    __result.insert(__item);
                }
                __result
            },
            exploration_targets: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
            fully_explored_oceans: false,
            known_terrain: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
        },
        terrains: vec![],
        exempt: std::collections::BTreeSet::new(),
        all_terrain_as_roads: false,
        bridges: false,
        city_owners: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
        city_points: {
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![].into_iter() {
                __result.insert(__item);
            }
            __result
        },
        road: 0.0f64,
        railroad: 0.0f64,
    })?;
    let mut serial: i64 = 0i64;
    let mut pending: Vec<(f64, i64, (i64, i64))> = vec![(
        0.0f64,
        {
            let __value = serial;
            serial += 1;
            __value
        },
        origin.clone(),
    )];
    let mut costs: indexmap::IndexMap<(i64, i64), f64> = [(origin.clone(), 0.0f64)]
        .into_iter()
        .collect::<indexmap::IndexMap<_, _>>();
    let mut previous: indexmap::IndexMap<(i64, i64), (i64, i64)> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    while (((pending).len() as i64) != 0i64) {
        let (mut cost, _, mut point): (f64, i64, (i64, i64)) = rt::heap_float_pop(&mut pending)?;
        if (cost
            != (costs)
                .get(&(point.clone()))
                .ok_or("missing dict key")?
                .clone())
        {
            continue;
        }
        if (point.clone() == goal.clone()) {
            let mut steps: Vec<(i64, i64)> = vec![];
            while (point.clone() != origin.clone()) {
                {
                    steps.push(point.clone());
                };
                point = (previous).get(&(point)).ok_or("missing dict key")?.clone();
            }
            return Ok(UnitPath {
                destination: goal,
                steps: ((steps).into_iter().rev().collect::<Vec<_>>())
                    .iter()
                    .cloned()
                    .collect::<Vec<_>>(),
                reachable: true,
                cost: cost,
            });
        }
        let mut current: Option<crate::openciv3::world::Tile> = {
            let __star_args_426: Vec<i64> = {
                let __tuple_value = &(point.clone());
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_426.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &world,
                rt::at(&__star_args_426, 0 as i64)?,
                rt::at(&__star_args_426, 1 as i64)?,
            )?
        };
        if !((current).is_some()) {
            rt::assertion(false, &("".to_string()))?;
        }
        for mut neighbor in crate::openciv3::world::WorldMap__neighbors(
            &world,
            &((*(current.clone()).as_ref().ok_or("expected a value")?).clone()),
        )? {
            let mut other: (i64, i64) = ((neighbor).x, (neighbor).y);
            if !(human && {
                let __needle = other.clone();
                let __container = &known;
                !__container.contains(&__needle)
            }) {
                if (((kind).domain == 0i64)
                    && (crate::openciv3::hydrology::is_water(&neighbor)?
                        && (other.clone() != goal.clone())))
                {
                    continue;
                }
                if (((kind).domain == 1i64)
                    && (!(crate::openciv3::hydrology::is_water(&neighbor)?) && {
                        let __needle = other.clone();
                        let __container = &own_cities;
                        !__container.contains(&__needle)
                    }))
                {
                    continue;
                }
            }
            if (((kind).domain == 1i64)
                && ((!(human) || {
                    let __needle = goal.clone();
                    let __container = &known;
                    __container.contains(&__needle)
                }) && crate::openciv3::hydrology::land_strip(
                    &world,
                    &((*(current.clone()).as_ref().ok_or("expected a value")?).clone()),
                    &neighbor,
                )?))
            {
                continue;
            }
            let mut intent: crate::openciv3::unit_entry::EntryIntent =
                crate::openciv3::unit_entry::resolve_entry(
                    game,
                    unit,
                    &(Some(neighbor.clone())),
                    true,
                )?;
            if !(if (other.clone() == goal.clone()) {
                crate::openciv3::unit_entry::EntryIntent__forceable(intent.clone())?
            } else {
                (crate::openciv3::unit_entry::EntryIntent__peaceful(intent.clone())?
                    && (intent.clone() != crate::openciv3::unit_entry::EntryIntent::LOAD))
            }) {
                continue;
            }
            let mut edge: f64 = _MovementCosts__edge(
                &movement,
                &((*(current.clone()).as_ref().ok_or("expected a value")?).clone()),
                &neighbor,
            )?;
            if (edge < ((0i64) as f64)) {
                return Err("Negative movement cost".to_string().into());
            }
            let mut candidate: f64 = rt::finite(
                cost + (1.0f64).min(rt::float_true_div(edge, (((kind).movement) as f64))?),
            )?;
            if (candidate < {
                let __key = other.clone();
                let __default = 1e+300f64;
                costs.get(&__key).cloned().unwrap_or(__default)
            }) {
                {
                    let __value = candidate;
                    let __key = other.clone();
                    costs.insert(__key, __value);
                }
                {
                    let __value = point.clone();
                    let __key = other.clone();
                    previous.insert(__key, __value);
                }
                {
                    let __item = (
                        candidate,
                        {
                            let __value = serial;
                            serial += 1;
                            __value
                        },
                        other,
                    );
                    rt::heap_float_push(&mut pending, __item)
                };
            }
        }
    }
    Ok(missing)
}
