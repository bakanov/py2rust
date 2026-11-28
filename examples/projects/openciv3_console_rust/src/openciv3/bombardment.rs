use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum BombardKind {
    UNIT,
    CITY,
    IMPROVEMENT,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct BombardTarget {
    pub(crate) kind: BombardKind,
    pub(crate) point: (i64, i64),
    pub(crate) unit_id: Option<i64>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct BombardResult {
    pub(crate) hits: i64,
    pub(crate) description: String,
    pub(crate) promotion: Option<crate::openciv3::combat::Promotion>,
    pub(crate) removal: Option<crate::openciv3::unit_lifecycle::RemovalResult>,
    pub(crate) protection_wars: Vec<crate::openciv3::diplomacy_actions::WarDeclaration>,
}

// Python: openciv3/bombardment.py:26
pub(crate) fn damage_improvement(
    mut game: crate::openciv3::game_state::GameState,
    tile: &crate::openciv3::world::Tile,
    mut improvement: i64,
) -> rt::Result<()> {
    let mut downgrade: indexmap::IndexMap<i64, i64> = [(2i64, 1i64), (268435456i64, 16i64)]
        .into_iter()
        .collect::<indexmap::IndexMap<_, _>>();
    let mut overlays: i64 = (((tile).overlays & !(improvement)) | {
        let __key = improvement;
        let __default = 0i64;
        downgrade.get(&__key).cloned().unwrap_or(__default)
    });
    let mut installation: i64 = (overlays & ((536870912i64 | 1073741824i64) | 2147483648i64));
    let mut revised: crate::openciv3::world::Tile = {
        let mut __replacement = ((*tile).clone()).clone();
        __replacement.overlays = overlays;
        __replacement.installation_owner = (if (installation != 0i64) {
            (tile).installation_owner.clone()
        } else {
            None
        });
        __replacement
    };
    game.world = {
        let mut __replacement = ((game).world.clone()).clone();
        __replacement.tiles = ({
            let mut __comprehension_result_581: Vec<crate::openciv3::world::Tile> = Vec::new();
            let __comprehension_source_580 = ((&(game).world).tiles.clone());
            for item in __comprehension_source_580.iter().cloned() {
                __comprehension_result_581.push(
                    (if (((item).x, (item).y) == ((tile).x, (tile).y)) {
                        revised.clone()
                    } else {
                        item.clone()
                    }),
                );
            }
            __comprehension_result_581
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        __replacement
    };
    game.scenario.world = Some((game).world.clone());
    game.visibility = crate::openciv3::visibility::update_visibility(
        &(game).world,
        &(game).cities,
        &(game).units,
        &(&(game).scenario).rules,
        &(game).ownership,
        (game).visibility.clone(),
        None,
        &None,
    )?;
    Ok(())
}

// Python: openciv3/bombardment.py:49
pub(crate) fn can_bombard(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<bool> {
    let mut prototype: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    if ((crate::openciv3::unit_rules::UnitPrototype__bombardment_range(&prototype)? <= 0i64)
        || ((unit).movement_remaining <= ((0i64) as f64)))
    {
        return Ok(false);
    }
    if (&(unit).transported_by).is_none() {
        return Ok(true);
    }
    if (((prototype).domain != 2i64) || !(((prototype).orders & 274877906944i64) != 0i64)) {
        return Ok(false);
    }
    Ok(({
        let mut __comprehension_result_583: Vec<bool> = Vec::new();
        let __comprehension_source_582 = ((game).units.clone());
        for other in __comprehension_source_582.iter().cloned() {
            __comprehension_result_583.push(
                ((Some((other).id) == (unit).transported_by.clone())
                    && (((other).owner == (unit).owner)
                        && (((other).hit_points > 0i64)
                            && ((((other).x, (other).y) == ((unit).x, (unit).y))
                                && crate::openciv3::unit_entry::can_carry(
                                    {
                                        let __source = &(&(&(game).scenario).rules).units;
                                        let __key = (other).prototype;
                                        &__source[rt::index(__source.len(), __key)?]
                                    },
                                    &prototype,
                                )?)))),
            );
        }
        __comprehension_result_583
    })
    .into_iter()
    .any(|__value| __value))
}

// Python: openciv3/bombardment.py:63
pub(crate) fn bombard_target(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    tile: &crate::openciv3::world::Tile,
    mut require_war: bool,
) -> rt::Result<Option<BombardTarget>> {
    let mut prototype: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    let mut point: (i64, i64) = ((tile).x, (tile).y);
    let mut source: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if ((source).is_none()
        || ((point.clone() == ((unit).x, (unit).y))
            || (crate::strategy::grid::distance(
                &({
                    let __structural_value = (game).world.clone();
                    crate::strategy::grid::DistanceMap {
                        width: (__structural_value).width.clone(),
                        height: (__structural_value).height.clone(),
                        wrap_x: (__structural_value).wrap_x.clone(),
                        wrap_y: (__structural_value).wrap_y.clone(),
                    }
                }),
                &({
                    let __structural_value =
                        (*(source.clone()).as_ref().ok_or("expected a value")?).clone();
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
            )? > crate::openciv3::unit_rules::UnitPrototype__bombardment_range(&prototype)?)))
    {
        return Ok(None);
    }
    if {
        let __needle = point.clone();
        let __container = &((&(game).visibility)
            .get(&((unit).owner))
            .ok_or("missing dict key")?)
        .visible;
        !__container.contains(&__needle)
    } {
        return Ok(None);
    }

    let mut city: Option<crate::openciv3::cities::City> = {
        let __find_source_584 = (game).cities.clone();
        let mut __find_result_584: Option<crate::openciv3::cities::City> = None;
        for c in __find_source_584.iter().cloned() {
            if (((c).x, (c).y) == point.clone()) {
                __find_result_584 = Some(c.clone());
                break;
            }
        }
        __find_result_584
    };
    if ((city).is_some()
        && !(bombard_target__eligible(
            unit,
            require_war,
            game,
            ((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).owner,
        )?))
    {
        return Ok(None);
    }
    let mut lethal_flag: i64 = (if ((tile).overlay_terrain >= 11i64) {
        268435456i64
    } else {
        134217728i64
    });
    let mut lethal: bool = ((prototype).abilities & lethal_flag) != 0;
    let mut targets: Vec<crate::openciv3::units::Unit> = {
        let mut __comprehension_result_586: Vec<crate::openciv3::units::Unit> = Vec::new();
        let __comprehension_source_585 = ((game).units.clone());
        for other in __comprehension_source_585.iter().cloned() {
            if ((((other).x, (other).y) == point.clone())
                && ((&(other).transported_by).is_none()
                    && (bombard_target__eligible(unit, require_war, game, (other).owner)?
                        && ((({
                            let __source = &(&(&(game).scenario).rules).units;
                            let __key = (other).prototype;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .defense
                            > 0i64)
                            && ((other).hit_points > (if lethal { 0i64 } else { 1i64 }))))))
            {
                __comprehension_result_586.push(other.clone());
            }
        }
        __comprehension_result_586
    };
    if (((targets).len() as i64) != 0i64) {
        let mut target: crate::openciv3::units::Unit = {
            let __values = &targets;
            let mut __items = __values.iter();
            let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
            let mut __best_key = {
                let other = (*__best).clone();
                rt::finite(
                    crate::openciv3::combat_strength::combat_strength(
                        game,
                        &other,
                        crate::openciv3::combat_strength::CombatRole::DEFENSE,
                        &None,
                        &None,
                    )? * (((other).hit_points) as f64),
                )?
            };
            for __candidate in __items {
                let __key = {
                    let other = (*__candidate).clone();
                    rt::finite(
                        crate::openciv3::combat_strength::combat_strength(
                            game,
                            &other,
                            crate::openciv3::combat_strength::CombatRole::DEFENSE,
                            &None,
                            &None,
                        )? * (((other).hit_points) as f64),
                    )?
                };
                if __key > __best_key {
                    __best = __candidate;
                    __best_key = __key;
                }
            }
            (*__best).clone()
        };
        return Ok(Some(BombardTarget {
            kind: BombardKind::UNIT,
            point: point,
            unit_id: Some((target).id),
        }));
    }
    let mut owner_city: Option<i64> = ((game).ownership.clone()).get(&(point.clone())).cloned();
    let mut territory: Option<i64> = {
        let __find_source_587 = (game).cities.clone();
        let mut __find_result_587: Option<i64> = None;
        for c in __find_source_587.iter().cloned() {
            if (Some((c).id) == owner_city.clone()) {
                __find_result_587 = Some((c).owner);
                break;
            }
        }
        __find_result_587
    };
    if (((tile).overlays
        & ((((((((1i64 | 2i64) | 4i64) | 8i64) | 16i64) | 268435456i64) | 536870912i64)
            | 1073741824i64)
            | 2147483648i64))
        != 0
        && (((territory).is_none() && !(require_war))
            || ((territory).is_some()
                && bombard_target__eligible(
                    unit,
                    require_war,
                    game,
                    (*(territory.clone()).as_ref().ok_or("expected a value")?).clone(),
                )?)))
    {
        return Ok(Some(BombardTarget {
            kind: BombardKind::IMPROVEMENT,
            point: point,
            unit_id: None,
        }));
    }
    Ok((if (city).is_some() {
        Some(BombardTarget {
            kind: BombardKind::CITY,
            point: point,
            unit_id: None,
        })
    } else {
        None
    }))
}

// Python: openciv3/bombardment.py:110
pub(crate) fn fire_bombardment(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    tile: &crate::openciv3::world::Tile,
    mut rng: rt::Random,
    mut require_war: bool,
) -> rt::Result<BombardResult> {
    let mut target: Option<BombardTarget> = {
        let __call_588_0 = game;
        let __call_588_1 = unit;
        let __call_588_2 = tile;
        let __call_588_3 = require_war;
        bombard_target(__call_588_0, __call_588_1, __call_588_2, __call_588_3)
    }?;
    if ((target).is_none() || !(can_bombard(game, unit)?)) {
        return Err("This unit cannot bombard that tile".to_string().into());
    }
    let mut city: Option<crate::openciv3::cities::City> = {
        let __find_source_589 = (game).cities.clone();
        let mut __find_result_589: Option<crate::openciv3::cities::City> = None;
        for item in __find_source_589.iter().cloned() {
            if (((item).x, (item).y)
                == ((*(target.clone()).as_ref().ok_or("expected a value")?).clone())
                    .point
                    .clone())
            {
                __find_result_589 = Some(item.clone());
                break;
            }
        }
        __find_result_589
    };
    let mut defender: Option<crate::openciv3::units::Unit> = {
        let __find_source_590 = (game).units.clone();
        let mut __find_result_590: Option<crate::openciv3::units::Unit> = None;
        for item in __find_source_590.iter().cloned() {
            if (Some((item).id)
                == ((*(target.clone()).as_ref().ok_or("expected a value")?).clone())
                    .unit_id
                    .clone())
            {
                __find_result_590 = Some(item.clone());
                break;
            }
        }
        __find_result_590
    };
    let mut territory: Option<crate::openciv3::cities::City> = {
        let __find_source_591 = (game).cities.clone();
        let mut __find_result_591: Option<crate::openciv3::cities::City> = None;
        for item in __find_source_591.iter().cloned() {
            if (Some((item).id)
                == ((game).ownership.clone())
                    .get(
                        &(((*(target.clone()).as_ref().ok_or("expected a value")?).clone())
                            .point
                            .clone()),
                    )
                    .cloned())
            {
                __find_result_591 = Some(item.clone());
                break;
            }
        }
        __find_result_591
    };
    let mut opponent: i64 = (if (defender).is_some() {
        ((*(defender.clone()).as_ref().ok_or("expected a value")?).clone()).owner
    } else {
        (if (city).is_some() {
            ((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).owner
        } else {
            (if (territory).is_some() {
                ((*(territory.clone()).as_ref().ok_or("expected a value")?).clone()).owner
            } else {
                (unit).owner
            })
        })
    });
    if ((opponent != (unit).owner)
        && !(crate::openciv3::diplomacy::Diplomacy__at_war(
            &(game).diplomacy,
            (unit).owner,
            opponent,
        )?))
    {
        return Err("Declare war before bombarding this target"
            .to_string()
            .into());
    }
    let mut strength: f64 = crate::openciv3::combat_strength::combat_strength(
        game,
        unit,
        crate::openciv3::combat_strength::CombatRole::BOMBARD,
        &None,
        &None,
    )?;
    if (strength <= ((0i64) as f64)) {
        return Err("This unit has no bombardment strength".to_string().into());
    }
    let mut wars: Vec<crate::openciv3::diplomacy_actions::WarDeclaration> = {
        let __call_592_0 = game;
        let __call_592_1 = (unit).owner;
        let __call_592_2 = opponent;
        let __call_592_3 = &(((*(target).as_ref().ok_or("expected a value")?).clone())
            .point
            .clone());
        let __call_592_4 = rng.clone();
        crate::openciv3::diplomacy_actions::honor_mutual_protection(
            __call_592_0,
            __call_592_1,
            __call_592_2,
            __call_592_3,
            __call_592_4,
        )
    }?;
    Ok({
        let mut __replacement = (_resolve_bombardment(
            (*game).clone(),
            (*unit).clone(),
            tile,
            city,
            defender,
            strength,
            rng.clone(),
        )?)
        .clone();
        __replacement.protection_wars = wars;
        __replacement
    })
}

// Python: openciv3/bombardment.py:128
pub(crate) fn _resolve_bombardment(
    mut game: crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
    tile: &crate::openciv3::world::Tile,
    mut city: Option<crate::openciv3::cities::City>,
    mut defender: Option<crate::openciv3::units::Unit>,
    mut strength: f64,
    mut rng: rt::Random,
) -> rt::Result<BombardResult> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut prototype: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(rules).units, (unit).prototype)?;
    if (((prototype).domain == 2i64) && ((prototype).orders & 274877906944i64) != 0) {
        unit.movement_remaining = 0.0f64;
    } else {
        unit.movement_remaining =
            (0.0f64).max(rt::finite((unit).movement_remaining - ((1i64) as f64))?);
    }
    unit.fortified = (&(unit).transported_by).is_some();
    unit.goto_destination = None;

    let mut limits: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(rules).global_rules, 0i64)?;
    if ((city).is_some()
        && (crate::openciv3::cities::City__size(
            &((*(city.clone()).as_ref().ok_or("expected a value")?).clone()),
        )? <= (limits).maximum_level1_city_size))
    {
        let mut walls: Option<crate::openciv3::cities::CityBuilding> = {
            let __find_source_593 = ((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                .buildings
                .clone();
            let mut __find_result_593: Option<crate::openciv3::cities::CityBuilding> = None;
            for building in __find_source_593.iter().cloned() {
                if (crate::openciv3::building_rules::Building__is_wall({
                    let __source = &(rules).buildings;
                    let __key = (building).building;
                    &__source[rt::index(__source.len(), __key)?]
                })? && ((({
                    let __source = &(rules).buildings;
                    let __key = (building).building;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .bombard_defense
                    > 0i64)
                    && !((({
                        let __source = &(rules).buildings;
                        let __key = (building).building;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .effects
                        & 1i64)
                        != 0i64)))
                {
                    __find_result_593 = Some(building.clone());
                    break;
                }
            }
            __find_result_593
        };
        if (walls).is_some() {
            let mut wall: crate::openciv3::building_rules::Building = rt::at(
                &(rules).buildings,
                ((*(walls.clone()).as_ref().ok_or("expected a value")?).clone()).building,
            )?;
            if !(_resolve_bombardment__hit(
                rng.clone(),
                strength,
                (((wall).bombard_defense) as f64),
            )?) {
                return Ok(BombardResult {
                    hits: 0i64,
                    description: "Bombardment missed".to_string(),
                    promotion: None,
                    removal: None,
                    protection_wars: vec![],
                });
            }
            {
                let __removed = (*(walls).as_ref().ok_or("expected a value")?).clone();
                let __index = (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                    .buildings
                    .clone())
                .iter()
                .position(|__item| (*__item).clone() == __removed)
                .ok_or("list.remove: value not found")?;
                (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                    .buildings
                    .clone())
                .remove(__index);
            };
            city.as_mut().ok_or("expected a value")?.walls = ({
                let mut __comprehension_result_595: Vec<bool> = Vec::new();
                let __comprehension_source_594 =
                    (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                        .buildings
                        .clone());
                for item in __comprehension_source_594.iter().cloned() {
                    __comprehension_result_595.push(
                        crate::openciv3::building_rules::Building__is_wall({
                            let __source = &(rules).buildings;
                            let __key = (item).building;
                            &__source[rt::index(__source.len(), __key)?]
                        })?,
                    );
                }
                __comprehension_result_595
            })
            .into_iter()
            .any(|__value| __value);
            {
                let __call_596_0 = &game;
                let __call_596_1 = &None;
                crate::openciv3::citizen_moods::recalculate_all_moods(__call_596_0, __call_596_1)
            }?;
            return Ok(BombardResult {
                hits: 1i64,
                description: {
                    let __separator = &(String::new());
                    (&(vec![
                        (((*(city).as_ref().ok_or("expected a value")?).clone())
                            .name
                            .clone())
                        .to_string(),
                        " lost ".to_string(),
                        ((wall).name.clone()).to_string(),
                    ]))
                        .join(__separator)
                },
                promotion: None,
                removal: None,
                protection_wars: vec![],
            });
        }
    }
    if (defender).is_some() {
        let mut defense: f64 = crate::openciv3::combat_strength::combat_strength(
            &game,
            &((*(defender.clone()).as_ref().ok_or("expected a value")?).clone()),
            crate::openciv3::combat_strength::CombatRole::BOMBARD_DEFENSE,
            &None,
            &None,
        )?;
        let mut lethal_flag: i64 = (if ((tile).overlay_terrain >= 11i64) {
            268435456i64
        } else {
            134217728i64
        });
        let mut minimum: i64 = (if (((prototype).abilities & lethal_flag) != 0i64) {
            0i64
        } else {
            1i64
        });
        let mut hits: i64 = 0i64;
        for _ in 0i64..(prototype).rate_of_fire {
            if (((*(defender.clone()).as_ref().ok_or("expected a value")?).clone()).hit_points
                <= minimum)
            {
                break;
            }
            if _resolve_bombardment__hit(rng.clone(), strength, defense)? {
                defender.as_mut().ok_or("expected a value")?.hit_points =
                    (((*(defender.clone()).as_ref().ok_or("expected a value")?).clone())
                        .hit_points)
                        .checked_sub(1i64)
                        .ok_or("integer overflow")?;
                hits = (hits).checked_add(1i64).ok_or("integer overflow")?;
            }
        }
        let mut promotion: Option<crate::openciv3::combat::Promotion> = None;
        let mut removal: Option<crate::openciv3::unit_lifecycle::RemovalResult> = None;
        if (((*(defender.clone()).as_ref().ok_or("expected a value")?).clone()).hit_points == 0i64)
        {
            promotion = crate::openciv3::combat::roll_promotion(
                &game,
                &unit,
                &((*(defender.clone()).as_ref().ok_or("expected a value")?).clone()),
                rng.clone(),
            )?;
            removal = Some(crate::openciv3::unit_lifecycle::remove_unit(
                &game,
                &((*(defender.clone()).as_ref().ok_or("expected a value")?).clone()),
            )?);
            game.visibility = crate::openciv3::visibility::update_visibility(
                &(game).world,
                &(game).cities,
                &(game).units,
                &rules,
                &(game).ownership,
                (game).visibility.clone(),
                None,
                &None,
            )?;
        }
        return Ok(BombardResult {
            hits: hits,
            description: (if (hits != 0i64) {
                {
                    let __separator = &(String::new());
                    (&(vec![
                        (((*(defender).as_ref().ok_or("expected a value")?).clone())
                            .name
                            .clone())
                        .to_string(),
                        " took ".to_string(),
                        (hits).to_string(),
                        " damage".to_string(),
                    ]))
                        .join(__separator)
                }
            } else {
                "Bombardment missed".to_string()
            }),
            promotion: promotion,
            removal: removal,
            protection_wars: vec![],
        });
    }
    if (city).is_some() {
        let mut buildings: Vec<crate::openciv3::cities::CityBuilding> = {
            let mut __comprehension_result_598: Vec<crate::openciv3::cities::CityBuilding> =
                Vec::new();
            let __comprehension_source_597 =
                (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                    .buildings
                    .clone());
            for building in __comprehension_source_597.iter().cloned() {
                if !((({
                    let __source = &(rules).buildings;
                    let __key = (building).building;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .effects
                    & 1i64)
                    != 0i64)
                {
                    __comprehension_result_598.push(building.clone());
                }
            }
            __comprehension_result_598
        };
        if ((rt::random_random(&rng) <= 0.5f64) && !(buildings.clone()).is_empty()) {
            if _resolve_bombardment__hit(
                rng.clone(),
                strength,
                (((limits).building_defensive_bonus) as f64),
            )? {
                let mut building: crate::openciv3::cities::CityBuilding = {
                    let __random = rng.clone();
                    let __values = buildings;
                    let __index = rt::random_randrange(&__random, 0, __values.len() as i64)?;
                    rt::at(&__values, __index)?
                };
                {
                    let __removed = building.clone();
                    let __index = (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                        .buildings
                        .clone())
                    .iter()
                    .position(|__item| (*__item).clone() == __removed)
                    .ok_or("list.remove: value not found")?;
                    (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                        .buildings
                        .clone())
                    .remove(__index);
                };
                if crate::openciv3::building_rules::Building__is_wall({
                    let __source = &(rules).buildings;
                    let __key = (building).building;
                    &__source[rt::index(__source.len(), __key)?]
                })? {
                    city.as_mut().ok_or("expected a value")?.walls = ({
                        let mut __comprehension_result_600: Vec<bool> = Vec::new();
                        let __comprehension_source_599 =
                            (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                                .buildings
                                .clone());
                        for item in __comprehension_source_599.iter().cloned() {
                            __comprehension_result_600.push(
                                crate::openciv3::building_rules::Building__is_wall({
                                    let __source = &(rules).buildings;
                                    let __key = (item).building;
                                    &__source[rt::index(__source.len(), __key)?]
                                })?,
                            );
                        }
                        __comprehension_result_600
                    })
                    .into_iter()
                    .any(|__value| __value);
                }
                {
                    let __call_601_0 = &game;
                    let __call_601_1 = &None;
                    crate::openciv3::citizen_moods::recalculate_all_moods(
                        __call_601_0,
                        __call_601_1,
                    )
                }?;
                return Ok(BombardResult {
                    hits: 1i64,
                    description: {
                        let __separator = &(String::new());
                        (&(vec![
                            (((*(city).as_ref().ok_or("expected a value")?).clone())
                                .name
                                .clone())
                            .to_string(),
                            " lost ".to_string(),
                            (({
                                let __source = &(rules).buildings;
                                let __key = (building).building;
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .name
                            .clone())
                            .to_string(),
                        ]))
                            .join(__separator)
                    },
                    promotion: None,
                    removal: None,
                    protection_wars: vec![],
                });
            }
        } else {
            if ((crate::openciv3::cities::City__size(
                &((*(city.clone()).as_ref().ok_or("expected a value")?).clone()),
            )? > 1i64)
                && _resolve_bombardment__hit(
                    rng.clone(),
                    strength,
                    (((limits).citizen_defensive_bonus) as f64),
                )?)
            {
                {
                    let __index = rt::index(
                        (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                            .residents
                            .clone())
                        .len(),
                        rt::random_randrange(
                            &(rng.clone()),
                            0i64,
                            crate::openciv3::cities::City__size(
                                &((*(city.clone()).as_ref().ok_or("expected a value")?).clone()),
                            )?,
                        )?,
                    )?;
                    (((*(city.clone()).as_ref().ok_or("expected a value")?).clone())
                        .residents
                        .clone())
                    .remove(__index)
                };
                {
                    let __call_602_0 = &game;
                    let __call_602_1 = &None;
                    crate::openciv3::citizen_moods::recalculate_all_moods(
                        __call_602_0,
                        __call_602_1,
                    )
                }?;
                return Ok(BombardResult {
                    hits: 1i64,
                    description: {
                        let __separator = &(String::new());
                        (&(vec![
                            (((*(city).as_ref().ok_or("expected a value")?).clone())
                                .name
                                .clone())
                            .to_string(),
                            " lost one resident".to_string(),
                        ]))
                            .join(__separator)
                    },
                    promotion: None,
                    removal: None,
                    protection_wars: vec![],
                });
            }
        }
        return Ok(BombardResult {
            hits: 0i64,
            description: "Bombardment caused no damage".to_string(),
            promotion: None,
            removal: None,
            protection_wars: vec![],
        });
    }
    let mut improvements: Vec<i64> = {
        let mut __comprehension_result_604: Vec<i64> = Vec::new();
        let __comprehension_source_603 = (vec![
            1i64,
            2i64,
            4i64,
            8i64,
            16i64,
            32i64,
            64i64,
            128i64,
            256i64,
            268435456i64,
            536870912i64,
            1073741824i64,
            2147483648i64,
        ]);
        for flag in __comprehension_source_603.iter().cloned() {
            if ({
                let __boolean_123705977484624 = (flag
                    & ((((((((1i64 | 2i64) | 4i64) | 8i64) | 16i64) | 268435456i64)
                        | 536870912i64)
                        | 1073741824i64)
                        | 2147483648i64));
                if (__boolean_123705977484624) != 0 {
                    ((tile).overlays & flag)
                } else {
                    __boolean_123705977484624
                }
            }) != 0
            {
                __comprehension_result_604.push(flag);
            }
        }
        __comprehension_result_604
    };
    if !(((improvements).len() as i64) != 0i64) {
        return Ok(BombardResult {
            hits: 0i64,
            description: "Bombardment caused no damage".to_string(),
            promotion: None,
            removal: None,
            protection_wars: vec![],
        });
    }
    let mut improvement: i64 = {
        let __random = rng.clone();
        let __values = improvements;
        let __index = rt::random_randrange(&__random, 0, __values.len() as i64)?;
        rt::at(&__values, __index)?
    };
    if !(_resolve_bombardment__hit(rng.clone(), strength, ((3i64) as f64))?) {
        return Ok(BombardResult {
            hits: 0i64,
            description: "Bombardment missed".to_string(),
            promotion: None,
            removal: None,
            protection_wars: vec![],
        });
    }
    damage_improvement(game, tile, improvement)?;
    Ok(BombardResult {
        hits: 1i64,
        description: {
            let __separator = &(String::new());
            (&(vec![
                "Destroyed ".to_string(),
                ((&((&({
                    let __boolean_123705977527696 = match (improvement) {
                        1 => "ROAD".to_owned(),
                        2 => "RAILROAD".to_owned(),
                        4 => "MINE".to_owned(),
                        8 => "IRRIGATION".to_owned(),
                        16 => "FORTRESS".to_owned(),
                        32 => "GOODY_HUT".to_owned(),
                        64 => "POLLUTION".to_owned(),
                        128 => "BARBARIAN_CAMP".to_owned(),
                        256 => "CRATERS".to_owned(),
                        268435456 => "BARRICADE".to_owned(),
                        536870912 => "AIRFIELD".to_owned(),
                        1073741824 => "RADAR_TOWER".to_owned(),
                        2147483648 => "OUTPOST".to_owned(),
                        _ => String::new(),
                    };
                    if !(__boolean_123705977527696).is_empty() {
                        __boolean_123705977527696
                    } else {
                        "improvement".to_string()
                    }
                }))
                    .to_lowercase()))
                    .replace("_", " "))
                .to_string(),
            ]))
                .join(__separator)
        },
        promotion: None,
        removal: None,
        protection_wars: vec![],
    })
}

// Python: openciv3/bombardment.py:73
pub(crate) fn bombard_target__eligible(
    unit: &crate::openciv3::units::Unit,
    mut require_war: bool,
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<bool> {
    if (owner == (unit).owner) {
        return Ok(false);
    }
    if require_war {
        return crate::openciv3::diplomacy::Diplomacy__at_war(
            &(game).diplomacy,
            (unit).owner,
            owner,
        );
    }
    Ok(!(crate::openciv3::diplomacy::Diplomacy__locked_peace(
        &(game).diplomacy,
        (unit).owner,
        owner,
    )?))
}

// Python: openciv3/bombardment.py:139
pub(crate) fn _resolve_bombardment__hit(
    mut rng: rt::Random,
    mut strength: f64,
    mut defense: f64,
) -> rt::Result<bool> {
    Ok((rt::random_random(&rng)
        < rt::float_true_div(strength, rt::finite(strength + (0.0f64).max(defense))?)?))
}
