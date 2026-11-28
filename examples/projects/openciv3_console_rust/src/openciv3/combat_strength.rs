use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum CombatRole {
    ATTACK,
    DEFENSE,
    BOMBARD,
    BOMBARD_DEFENSE,
    DEFENSIVE_BOMBARD,
    DEFENSIVE_BOMBARD_DEFENSE,
}

#[derive(Clone, PartialEq)]
pub(crate) struct StrengthBonus {
    pub(crate) description: String,
    pub(crate) amount: f64,
}

#[derive(Clone, PartialEq)]
pub(crate) struct ImprovementDefense {
    pub(crate) fortress: f64,
    pub(crate) barricade: f64,
}

// Python: openciv3/combat_strength.py:24
pub(crate) fn CombatRole__defending(mut self_: CombatRole) -> rt::Result<bool> {
    Ok({
        let __needle = self_;
        let __container = &({
            let __tuple_value = &((
                CombatRole::DEFENSE,
                CombatRole::BOMBARD_DEFENSE,
                CombatRole::DEFENSIVE_BOMBARD_DEFENSE,
            ));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        __container.contains(&__needle)
    })
}

// Python: openciv3/combat_strength.py:40
pub(crate) fn strength_bonuses(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut role: CombatRole,
    attack_from: &Option<crate::openciv3::world::Tile>,
    mut improvements: Option<ImprovementDefense>,
) -> rt::Result<Vec<StrengthBonus>> {
    if (!(CombatRole__defending(role.clone())?) && (role.clone() != CombatRole::ATTACK)) {
        return Ok(vec![]);
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut global_rules: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(rules).global_rules, 0i64)?;
    if (improvements).is_none() {
        improvements = Some(ImprovementDefense {
            fortress: (global_rules).fortress_defense,
            barricade: (global_rules).barricade_defense,
        });
    }
    let mut location: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if (location).is_none() {
        return Err("Unit is outside the map".to_string().into());
    }
    let mut result: Vec<StrengthBonus> = vec![];
    if {
        let __needle = role.clone();
        let __container = &({
            let __tuple_value = &((CombatRole::ATTACK, CombatRole::DEFENSE));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        __container.contains(&__needle)
    } {
        let mut city_owners: indexmap::IndexMap<i64, i64> = {
            let mut __comprehension_result_660: indexmap::IndexMap<i64, i64> =
                indexmap::IndexMap::new();
            let __comprehension_source_659 = ((game).cities.clone());
            for city in __comprehension_source_659.iter().cloned() {
                {
                    let (__key, __value) = ((city).id, (city).owner);
                    __comprehension_result_660.insert(__key, __value);
                }
            }
            __comprehension_result_660
        };
        for mut radius in 0i64..3i64 {
            for mut tile in crate::strategy::grid::ring(
                &(game).world,
                &((*(location.clone()).as_ref().ok_or("expected a value")?).clone()),
                radius,
                true,
            )? {
                if !(((tile).overlays & 1073741824i64) != 0i64) {
                    continue;
                }
                let mut territory: Option<i64> = (city_owners.clone())
                    .get(
                        &({
                            let __mapping = &(game).ownership;
                            let __key = ((tile).x, (tile).y);
                            let __default = (1i64).checked_neg().ok_or("integer overflow")?;
                            __mapping.get(&__key).cloned().unwrap_or(__default)
                        }),
                    )
                    .cloned();
                let mut builder: Option<i64> = (if (&(tile).installation_owner).is_some() {
                    (tile).installation_owner.clone()
                } else {
                    territory.clone()
                });
                if ((builder == Some((unit).owner))
                    && ((territory).is_none()
                        || ((*(territory).as_ref().ok_or("expected a value")?).clone())
                            == ((((), (unit).owner)).1)))
                {
                    {
                        result.push(StrengthBonus {
                            description: "Radar tower".to_string(),
                            amount: 0.25f64,
                        });
                    };
                    break;
                }
            }
            if (((result).len() as i64) != 0i64) {
                break;
            }
        }
    }
    if !(CombatRole__defending(role)?) {
        return Ok((result).iter().cloned().collect::<Vec<_>>());
    }
    if (unit).fortified {
        {
            result.push(StrengthBonus {
                description: "Fortified".to_string(),
                amount: rt::int_true_div((global_rules).fortifications_defensive_bonus, 100i64)?,
            });
        };
    }
    let mut terrain: crate::openciv3::rules::Terrain = rt::at(
        &(rules).terrains,
        ((*(location.clone()).as_ref().ok_or("expected a value")?).clone()).overlay_terrain,
    )?;
    {
        result.push(StrengthBonus {
            description: (terrain).name.clone(),
            amount: rt::int_true_div((terrain).defense_bonus, 100i64)?,
        });
    };
    if ((((*(location.clone()).as_ref().ok_or("expected a value")?).clone()).overlays
        & 268435456i64)
        != 0i64)
    {
        {
            result.push(StrengthBonus {
                description: "Barricade".to_string(),
                amount: ((*(improvements).as_ref().ok_or("expected a value")?).clone()).barricade,
            });
        };
    } else {
        if ((((*(location.clone()).as_ref().ok_or("expected a value")?).clone()).overlays & 16i64)
            != 0i64)
        {
            {
                result.push(StrengthBonus {
                    description: "Fortress".to_string(),
                    amount: ((*(improvements).as_ref().ok_or("expected a value")?).clone())
                        .fortress,
                });
            };
        }
    }
    for mut for_target_77_4 in (&(global_rules).extra_improvement_defenses).iter() {
        let (mut flag, mut description, mut amount): (i64, String, f64) =
            (*for_target_77_4).clone();
        if ((((*(location.clone()).as_ref().ok_or("expected a value")?).clone()).overlays & flag)
            != 0i64)
        {
            {
                result.push(StrengthBonus {
                    description: description.clone(),
                    amount: amount,
                });
            };
        }
    }
    if (attack_from).is_some() {
        for mut for_target_83_8 in ({
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
            let (mut index, (mut dx, mut dy)): (i64, (i64, i64)) = for_target_83_8;
            if ((crate::openciv3::world::WorldMap__tile_at(
                &(game).world,
                (((*(location.clone()).as_ref().ok_or("expected a value")?).clone()).x)
                    .checked_add(dx)
                    .ok_or("integer overflow")?,
                (((*(location.clone()).as_ref().ok_or("expected a value")?).clone()).y)
                    .checked_add(dy)
                    .ok_or("integer overflow")?,
            )? == (*attack_from).clone())
                && (crate::openciv3::hydrology::river_edges(
                    &(game).world,
                    &((*(location.clone()).as_ref().ok_or("expected a value")?).clone()),
                )? & rt::int_lshift(1i64, index)?)
                    != 0)
            {
                {
                    result.push(StrengthBonus {
                        description: "Behind river".to_string(),
                        amount: rt::int_true_div((global_rules).river_defensive_bonus, 100i64)?,
                    });
                };
                break;
            }
        }
    }
    let mut city: Option<crate::openciv3::cities::City> = {
        let __find_source_661 = (game).cities.clone();
        let mut __find_result_661: Option<crate::openciv3::cities::City> = None;
        for city in __find_source_661.iter().cloned() {
            if (((city).x, (city).y) == ((unit).x, (unit).y)) {
                __find_result_661 = Some(city.clone());
                break;
            }
        }
        __find_result_661
    };
    if (city).is_some() {
        let mut town: bool = (crate::openciv3::cities::City__size(
            &((*(city.clone()).as_ref().ok_or("expected a value")?).clone()),
        )? <= (global_rules).maximum_level1_city_size);
        if (crate::openciv3::cities::City__size(
            &((*(city.clone()).as_ref().ok_or("expected a value")?).clone()),
        )? > (global_rules).maximum_level2_city_size)
        {
            {
                result.push(StrengthBonus {
                    description: "Metropolis".to_string(),
                    amount: rt::int_true_div((global_rules).metropolis_defense_bonus, 100i64)?,
                });
            };
        } else {
            if !(town) {
                {
                    result.push(StrengthBonus {
                        description: "City".to_string(),
                        amount: rt::int_true_div((global_rules).city_defense_bonus, 100i64)?,
                    });
                };
            } else {
                {
                    result.push(StrengthBonus {
                        description: "Town".to_string(),
                        amount: rt::int_true_div((global_rules).town_defense_bonus, 100i64)?,
                    });
                };
            }
        }
        for mut item in crate::openciv3::building_effects::effective_buildings(
            &((*(city).as_ref().ok_or("expected a value")?).clone()),
            &(game).cities,
            &(game).players,
            &(game).world,
            &rules,
        )? {
            let mut building: crate::openciv3::building_rules::Building =
                rt::at(&(rules).buildings, (item).building)?;
            if (((building).defense_bonus > 0i64)
                && (town || !(crate::openciv3::building_rules::Building__towns_only(&building)?)))
            {
                {
                    result.push(StrengthBonus {
                        description: (building).name.clone(),
                        amount: rt::int_true_div((building).defense_bonus, 100i64)?,
                    });
                };
            }
        }
    }
    Ok((result).iter().cloned().collect::<Vec<_>>())
}

// Python: openciv3/combat_strength.py:105
pub(crate) fn combat_strength(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut role: CombatRole,
    attack_from: &Option<crate::openciv3::world::Tile>,
    improvements: &Option<ImprovementDefense>,
) -> rt::Result<f64> {
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    let mut base: i64 = (if CombatRole__defending(role.clone())? {
        (kind).defense
    } else {
        (if (role.clone() == CombatRole::ATTACK) {
            (kind).attack
        } else {
            (kind).bombard_strength
        })
    });
    let mut multiplier: f64 = (0.0f64).max(rt::finite(
        1.0f64
            + ({
                let mut __comprehension_result_664: Vec<f64> = Vec::new();
                let __comprehension_source_663 = ({
                    let __call_662_0 = game;
                    let __call_662_1 = unit;
                    let __call_662_2 = role.clone();
                    let __call_662_3 = attack_from;
                    let __call_662_4 = (*improvements).clone();
                    strength_bonuses(
                        __call_662_0,
                        __call_662_1,
                        __call_662_2,
                        __call_662_3,
                        __call_662_4,
                    )
                }?);
                for bonus in __comprehension_source_663.iter().cloned() {
                    __comprehension_result_664.push((bonus).amount);
                }
                __comprehension_result_664
            })
            .into_iter()
            .sum::<f64>(),
    )?);
    Ok(rt::finite(((base) as f64) * multiplier)?)
}

/// Prefer hostile matching-domain units, then defense times HP; stable ties.
// Python: openciv3/combat_strength.py:115
pub(crate) fn top_defender(
    game: &crate::openciv3::game_state::GameState,
    attacker: &crate::openciv3::units::Unit,
    tile: &crate::openciv3::world::Tile,
    improvements: &Option<ImprovementDefense>,
) -> rt::Result<Option<crate::openciv3::units::Unit>> {
    let mut domain: i64 = ({
        let __source = &(&(&(game).scenario).rules).units;
        let __key = (attacker).prototype;
        &__source[rt::index(__source.len(), __key)?]
    })
    .domain;
    let mut candidates: Vec<crate::openciv3::units::Unit> = {
        let mut __comprehension_result_666: Vec<crate::openciv3::units::Unit> = Vec::new();
        let __comprehension_source_665 = ((game).units.clone());
        for unit in __comprehension_source_665.iter().cloned() {
            if ((((unit).x, (unit).y) == ((tile).x, (tile).y))
                && (((unit).id != (attacker).id)
                    && ((&(unit).transported_by).is_none()
                        && (((unit).hit_points > 0i64)
                            && (({
                                let __source = &(&(&(game).scenario).rules).units;
                                let __key = (unit).prototype;
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .domain
                                == domain)))))
            {
                __comprehension_result_666.push(unit.clone());
            }
        }
        __comprehension_result_666
    };
    Ok('__extreme: {
        let __values = &candidates;
        let mut __items = __values.iter();
        let Some(mut __best) = __items.next() else {
            break '__extreme None;
        };
        let mut __best_key = {
            let unit = (*__best).clone();
            (
                crate::openciv3::diplomacy::Diplomacy__at_war(
                    &(game).diplomacy,
                    (attacker).owner,
                    (unit).owner,
                )?,
                rt::finite(
                    {
                        let __call_667_0 = game;
                        let __call_667_1 = &unit;
                        let __call_667_2 = CombatRole::DEFENSE;
                        let __call_667_3 = improvements;
                        let __call_667_default_3 = &None;
                        combat_strength(
                            __call_667_0,
                            __call_667_1,
                            __call_667_2,
                            __call_667_default_3,
                            __call_667_3,
                        )
                    }? * (((unit).hit_points) as f64),
                )?,
            )
        };
        for __candidate in __items {
            let __key = {
                let unit = (*__candidate).clone();
                (
                    crate::openciv3::diplomacy::Diplomacy__at_war(
                        &(game).diplomacy,
                        (attacker).owner,
                        (unit).owner,
                    )?,
                    rt::finite(
                        {
                            let __call_667_0 = game;
                            let __call_667_1 = &unit;
                            let __call_667_2 = CombatRole::DEFENSE;
                            let __call_667_3 = improvements;
                            let __call_667_default_3 = &None;
                            combat_strength(
                                __call_667_0,
                                __call_667_1,
                                __call_667_2,
                                __call_667_default_3,
                                __call_667_3,
                            )
                        }? * (((unit).hit_points) as f64),
                    )?,
                )
            };
            if __key > __best_key {
                __best = __candidate;
                __best_key = __key;
            }
        }
        Some((*__best).clone())
    })
}
