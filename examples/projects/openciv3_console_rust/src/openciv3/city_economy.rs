use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct CorruptibleYield {
    pub(crate) useful: i64,
    pub(crate) lost: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct CityFood {
    pub(crate) produced: i64,
    pub(crate) consumed: i64,
    pub(crate) surplus: i64,
    pub(crate) food_box: i64,
    pub(crate) turns: Option<i64>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct CityProduction {
    pub(crate) gross: i64,
    pub(crate) useful: i64,
    pub(crate) lost: i64,
    pub(crate) cost: Option<i64>,
    pub(crate) turns: Option<i64>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct Commerce {
    pub(crate) corrupted: i64,
    pub(crate) taxes: i64,
    pub(crate) beakers: i64,
    pub(crate) happiness: i64,
    pub(crate) wealth: i64,
}

// Python: openciv3/city_economy.py:21
pub(crate) fn after_corruption(
    mut value: i64,
    mut corruption: f64,
    mut disabled: bool,
) -> rt::Result<CorruptibleYield> {
    if ((value < 0i64)
        || !({
            let __compare_0 = 0i64;
            let __compare_1 = corruption;
            if (((__compare_0) as f64) <= __compare_1) {
                let __compare_2 = 1i64;
                (__compare_1 <= ((__compare_2) as f64))
            } else {
                false
            }
        }))
    {
        return Err("Invalid yield or corruption fraction".to_string().into());
    }
    let mut useful: i64 = (if disabled {
        0i64
    } else {
        ((value > 0i64) as i64).max(rt::round_float(rt::finite(
            ((value) as f64) * rt::finite(((1i64) as f64) - corruption)?,
        )?)?)
    });
    Ok(CorruptibleYield {
        useful: useful,
        lost: (value).checked_sub(useful).ok_or("integer overflow")?,
    })
}

/// None means stalled, -1 means starvation; nonnegative values are turns.
// Python: openciv3/city_economy.py:28
pub(crate) fn growth_turns(
    mut food_stored: i64,
    mut food_needed: i64,
    mut surplus: i64,
) -> rt::Result<Option<i64>> {
    if ((surplus == 0i64) || (food_stored > food_needed)) {
        return Ok(None);
    }
    if (surplus < 0i64) {
        return Ok(Some((1i64).checked_neg().ok_or("integer overflow")?));
    }
    Ok(Some(rt::int_floor_div(
        (((food_needed)
            .checked_sub(food_stored)
            .ok_or("integer overflow")?)
        .checked_add(surplus)
        .ok_or("integer overflow")?)
        .checked_sub(1i64)
        .ok_or("integer overflow")?,
        surplus,
    )?))
}

// Python: openciv3/city_economy.py:37
pub(crate) fn production_turns(
    mut shield_cost: i64,
    mut shields_stored: i64,
    mut useful_shields: i64,
) -> rt::Result<Option<i64>> {
    if (useful_shields < 0i64) {
        return Err("Useful shields must not be negative".to_string().into());
    }
    if (useful_shields == 0i64) {
        return Ok(None);
    }
    Ok(Some(
        (1i64).max(rt::int_floor_div(
            (((shield_cost)
                .checked_sub(shields_stored)
                .ok_or("integer overflow")?)
            .checked_add(useful_shields)
            .ok_or("integer overflow")?)
            .checked_sub(1i64)
            .ok_or("integer overflow")?,
            useful_shields,
        )?),
    ))
}

// Python: openciv3/city_economy.py:45
pub(crate) fn food_box(
    mut size: i64,
    mut town_limit: i64,
    mut city_limit: i64,
    capacities: &(i64, i64, i64),
) -> rt::Result<i64> {
    Ok((if (size <= town_limit) {
        (capacities).0.clone()
    } else {
        (if (size <= city_limit) {
            (capacities).1.clone()
        } else {
            (capacities).2.clone()
        })
    }))
}

/// Sum the free center and worked tiles; specialists have no worked tile.
// Python: openciv3/city_economy.py:50
pub(crate) fn city_tile_yields(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut hydro: Option<crate::openciv3::hydrology::Hydrology>,
) -> rt::Result<crate::civ::economy::Yield> {
    let (mut world, mut rules): (
        crate::openciv3::world::WorldMap,
        crate::openciv3::rules::RuleCatalog,
    ) = ((game).world.clone(), (&(game).scenario).rules.clone());
    hydro = (if (hydro).is_some() {
        hydro.clone()
    } else {
        Some(crate::openciv3::hydrology::Hydrology__from_world(&world)?)
    });
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (city).owner)?;
    let mut civilization: crate::openciv3::scenario_model::Civilization =
        rt::at(&(&(game).scenario).civilizations, (city).owner)?;
    let mut buildings: Vec<crate::openciv3::building_rules::Building> = {
        let mut __comprehension_result_618: Vec<crate::openciv3::building_rules::Building> =
            Vec::new();
        let __comprehension_source_617 = (crate::openciv3::building_effects::effective_buildings(
            city,
            &(game).cities,
            &(game).players,
            &world,
            &rules,
        )?);
        for item in __comprehension_source_617.iter().cloned() {
            __comprehension_result_618.push(rt::at(&(rules).buildings, (item).building)?);
        }
        __comprehension_result_618
    };
    let mut center: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&world, (city).x, (city).y)?;
    if (center).is_none() {
        return Err("City is outside the map".to_string().into());
    }
    let mut total: crate::civ::economy::Yield = {
        let __call_619_0 = &((*(center.clone()).as_ref().ok_or("expected a value")?).clone());
        let __call_619_1 = &(player.clone());
        let __call_619_2 = &(Some(civilization.clone()));
        let __call_619_3 = &(rules.clone());
        let __call_619_4 = &(Some((*city).clone()));
        let __call_619_5 = crate::openciv3::hydrology::Hydrology__fresh_access(
            &((*(hydro.clone()).as_ref().ok_or("expected a value")?).clone()),
            &world,
            &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?;
        let __call_619_6 = crate::openciv3::hydrology::Hydrology__coastal(
            &((*(hydro.clone()).as_ref().ok_or("expected a value")?).clone()),
            &world,
            &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?;
        let __call_619_7 = &(buildings.clone());
        let __call_619_8 = &(Some(
            (crate::openciv3::hydrology::river_edges(
                &world,
                &((*(center.clone()).as_ref().ok_or("expected a value")?).clone()),
            )?) != 0,
        ));
        crate::openciv3::yields::tile_yield(
            __call_619_0,
            __call_619_1,
            __call_619_2,
            __call_619_3,
            __call_619_4,
            __call_619_5,
            __call_619_6,
            __call_619_7,
            __call_619_8,
        )
    }?;
    for mut resident in (&(city).residents).iter() {
        if (&(resident).tile_worked).is_none() {
            continue;
        }
        let mut tile: Option<crate::openciv3::world::Tile> = {
            let __star_args_620: Vec<i64> = {
                let __tuple_value = &((*((resident).tile_worked.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone());
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            };
            if !(2..=2).contains(&__star_args_620.len()) {
                return Err("wrong function argument count".into());
            }
            crate::openciv3::world::WorldMap__tile_at(
                &world,
                rt::at(&__star_args_620, 0 as i64)?,
                rt::at(&__star_args_620, 1 as i64)?,
            )?
        };
        if (tile).is_none() {
            return Err("Citizen works an invalid tile".to_string().into());
        }
        let mut value: crate::civ::economy::Yield = {
            let __call_621_0 = &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone());
            let __call_621_1 = &(player.clone());
            let __call_621_2 = &(Some(civilization.clone()));
            let __call_621_3 = &(rules.clone());
            let __call_621_4 = &(buildings.clone());
            let __call_621_5 = &(Some(
                (crate::openciv3::hydrology::river_edges(
                    &world,
                    &((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?) != 0,
            ));
            let __call_621_default_4 = &None;
            let __call_621_default_5 = false;
            let __call_621_default_6 = false;
            crate::openciv3::yields::tile_yield(
                __call_621_0,
                __call_621_1,
                __call_621_2,
                __call_621_3,
                __call_621_default_4,
                __call_621_default_5,
                __call_621_default_6,
                __call_621_4,
                __call_621_5,
            )
        }?;
        total = crate::civ::economy::Yield {
            food: ((total).food)
                .checked_add((value).food)
                .ok_or("integer overflow")?,
            shields: ((total).shields)
                .checked_add((value).shields)
                .ok_or("integer overflow")?,
            commerce: ((total).commerce)
                .checked_add((value).commerce)
                .ok_or("integer overflow")?,
        };
    }
    Ok(total)
}

// Python: openciv3/city_economy.py:85
pub(crate) fn city_food(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    hydro: &Option<crate::openciv3::hydrology::Hydrology>,
) -> rt::Result<CityFood> {
    let mut total: crate::civ::economy::Yield = city_tile_yields(game, city, (*hydro).clone())?;
    let mut limits: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(&(&(game).scenario).rules).global_rules, 0i64)?;
    let mut required_food: i64 = food_box(
        crate::openciv3::cities::City__size(city)?,
        (limits).maximum_level1_city_size,
        (limits).maximum_level2_city_size,
        &(limits).food_boxes,
    )?;
    let mut consumed: i64 = (crate::openciv3::cities::City__size(city)?)
        .checked_mul((limits).food_consumption_per_citizen)
        .ok_or("integer overflow")?;
    let mut surplus: i64 = ((total).food)
        .checked_sub(consumed)
        .ok_or("integer overflow")?;
    Ok(CityFood {
        produced: (total).food,
        consumed: consumed,
        surplus: surplus,
        food_box: required_food,
        turns: growth_turns((city).food_stored, required_food, surplus)?,
    })
}

// Python: openciv3/city_economy.py:103
pub(crate) fn city_production(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut corruption: f64,
    hydro: &Option<crate::openciv3::hydrology::Hydrology>,
    disorder: &Option<bool>,
) -> rt::Result<CityProduction> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    crate::openciv3::cities::City__validate_production(
        &((*city).clone()),
        ((&(rules).units).len() as i64),
        ((&(rules).buildings).len() as i64),
    )?;
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (city).owner)?;
    let mut total: crate::civ::economy::Yield = city_tile_yields(game, city, (*hydro).clone())?;
    let mut yield_: CorruptibleYield = {
        let __call_622_0 = (total).shields;
        let __call_622_1 = corruption;
        let __call_622_2 = ((if (disorder).is_none() {
            (city).disorder
        } else {
            ((*disorder).clone()).is_some()
        }) || ({
            let __source = &(&(&(game).scenario).rules).governments;
            let __key = (player).government;
            &__source[rt::index(__source.len(), __key)?]
        })
        .transition_type);
        after_corruption(__call_622_0, __call_622_1, __call_622_2)
    }?;
    let mut cost: Option<i64> = (if (&(city).producing_unit).is_none() {
        None
    } else {
        Some(crate::openciv3::production_cost::unit_cost(
            {
                let __source = &(&(&(game).scenario).rules).units;
                let __key = (*((city).producing_unit.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone();
                &__source[rt::index(__source.len(), __key)?]
            },
            (player).human,
            {
                let __source = &(&(game).scenario).difficulties;
                let __key = (game).difficulty;
                &__source[rt::index(__source.len(), __key)?]
            },
        )?)
    });
    if (&(city).producing_building).is_some() {
        cost = Some(crate::openciv3::production_cost::city_building_cost(
            game,
            city,
            {
                let __source = &(rules).buildings;
                let __key = (*((city).producing_building.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone();
                &__source[rt::index(__source.len(), __key)?]
            },
        )?);
    }
    Ok(CityProduction {
        gross: (total).shields,
        useful: (yield_).useful,
        lost: (yield_).lost,
        cost: cost.clone(),
        turns: (if (cost).is_none() {
            None
        } else {
            production_turns(
                (*(cost.clone()).as_ref().ok_or("expected a value")?).clone(),
                (city).shields_stored,
                (yield_).useful,
            )?
        }),
    })
}

/// Return taxes/science/luxury, giving science priority on rounding ties.
// Python: openciv3/city_economy.py:129
pub(crate) fn split_commerce(
    mut useful: i64,
    mut science_rate: i64,
    mut luxury_rate: i64,
) -> rt::Result<(i64, i64, i64)> {
    if ((useful < 0i64)
        || (((science_rate).min(luxury_rate) < 0i64)
            || ((science_rate)
                .checked_add(luxury_rate)
                .ok_or("integer overflow")?
                > 10i64)))
    {
        return Err("Invalid commerce or slider allocation".to_string().into());
    }
    let mut science: i64 = rt::int_floor_div(
        ((useful)
            .checked_mul(science_rate)
            .ok_or("integer overflow")?)
        .checked_add(5i64)
        .ok_or("integer overflow")?,
        10i64,
    )?;
    let mut luxury: i64 = (rt::int_floor_div(
        ((useful)
            .checked_mul(luxury_rate)
            .ok_or("integer overflow")?)
        .checked_add(5i64)
        .ok_or("integer overflow")?,
        10i64,
    )?)
    .min((useful).checked_sub(science).ok_or("integer overflow")?);
    Ok((
        ((useful).checked_sub(science).ok_or("integer overflow")?)
            .checked_sub(luxury)
            .ok_or("integer overflow")?,
        science,
        luxury,
    ))
}

// Python: openciv3/city_economy.py:138
pub(crate) fn city_commerce(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut corruption: f64,
    hydro: &Option<crate::openciv3::hydrology::Hydrology>,
    disorder: &Option<bool>,
    mut respect_disorder: bool,
) -> rt::Result<Commerce> {
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (city).owner)?;
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut gross: i64 = (city_tile_yields(game, city, (*hydro).clone())?).commerce;
    let mut adjusted: CorruptibleYield = {
        let __call_623_0 = gross;
        let __call_623_1 = corruption;
        let __call_623_2 = (({
            let __source = &(rules).governments;
            let __key = (player).government;
            &__source[rt::index(__source.len(), __key)?]
        })
        .transition_type
            || ((if (disorder).is_none() {
                (city).disorder
            } else {
                ((*disorder).clone()).is_some()
            }) && respect_disorder));
        after_corruption(__call_623_0, __call_623_1, __call_623_2)
    }?;
    let (mut taxes, mut science, mut luxury): (i64, i64, i64) = split_commerce(
        (adjusted).useful,
        (player).science_rate,
        (player).luxury_rate,
    )?;
    let mut chained_locals_149_4: f64 = 0.0f64;
    let mut tax_bonus: f64 = chained_locals_149_4;
    let mut science_bonus: f64 = chained_locals_149_4;
    let mut happiness_bonus: f64 = chained_locals_149_4;
    for mut item in (&(city).buildings).iter() {
        let mut building: crate::openciv3::building_rules::Building =
            rt::at(&(rules).buildings, (item).building)?;
        if {
            let __needle = (building).rendered_obsolete_by;
            let __container = &(player).known_technologies;
            __container.contains(&__needle)
        } {
            continue;
        }
        let mut effects: i64 = (building).effects;
        tax_bonus = rt::finite(
            tax_bonus
                + (if (&(building).commerce_bonus).is_none() {
                    rt::finite(0.5f64 * (((effects & 16i64) != 0) as i64 as f64))?
                } else {
                    (*((building).commerce_bonus.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone()
                }),
        )?;
        happiness_bonus = rt::finite(
            happiness_bonus
                + (if (&(building).luxury_bonus).is_none() {
                    rt::finite(0.5f64 * (((effects & 8i64) != 0) as i64 as f64))?
                } else {
                    (*((building).luxury_bonus.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone()
                }),
        )?;
        science_bonus = rt::finite(
            science_bonus
                + (if (&(building).research_bonus).is_none() {
                    rt::finite(
                        rt::finite(0.5f64 * (((effects & 4i64) != 0) as i64 as f64))?
                            + (((effects & 9007199254740992i64) != 0) as i64 as f64),
                    )?
                } else {
                    (*((building).research_bonus.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone()
                }),
        )?;
    }
    taxes = rt::floor(rt::finite(
        ((taxes) as f64) * rt::finite(((1i64) as f64) + tax_bonus)?,
    )?)?;
    science = rt::floor(rt::finite(
        ((science) as f64) * rt::finite(((1i64) as f64) + science_bonus)?,
    )?)?;
    luxury = rt::floor(rt::finite(
        ((luxury) as f64) * rt::finite(((1i64) as f64) + happiness_bonus)?,
    )?)?;
    for mut resident in (&(city).residents).iter() {
        let mut specialist: crate::openciv3::rules::CitizenType =
            rt::at(&(rules).citizens, (resident).citizen_type)?;
        taxes = (taxes)
            .checked_add((specialist).taxes)
            .ok_or("integer overflow")?;
        science = (science)
            .checked_add((specialist).research)
            .ok_or("integer overflow")?;
        luxury = (luxury)
            .checked_add((specialist).luxuries)
            .ok_or("integer overflow")?;
    }
    let mut wealth: i64 = 0i64;
    if (((city).producing_inflow.clone() == Some(crate::openciv3::inflows::Inflow::WEALTH))
        && (({
            let __source = &(rules).global_rules;
            let __key = 0i64;
            &__source[rt::index(__source.len(), __key)?]
        })
        .wealth
        .clone())
            == (crate::openciv3::inflows::WealthRule::COMMERCE))
    {
        let mut shields: i64 = ({
            let __call_624_0 = game;
            let __call_624_1 = city;
            let __call_624_2 = corruption;
            let __call_624_3 = hydro;
            let __call_624_4 = disorder;
            city_production(
                __call_624_0,
                __call_624_1,
                __call_624_2,
                __call_624_3,
                __call_624_4,
            )
        }?)
        .useful;
        let mut doubled: bool = ({
            let mut __comprehension_result_626: Vec<i64> = Vec::new();
            let __comprehension_source_625 = (((rules).technologies.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>());
            for (index, technology) in __comprehension_source_625.iter().cloned() {
                if {
                    let __needle = index;
                    let __container = &(player).known_technologies;
                    __container.contains(&__needle)
                } {
                    __comprehension_result_626.push(((technology).effects & 4096i64));
                }
            }
            __comprehension_result_626
        })
        .into_iter()
        .any(|__value| __value != 0);
        wealth = crate::openciv3::inflows::wealth_commerce(
            shields,
            ({
                let __source = &(rules).global_rules;
                let __key = 0i64;
                &__source[rt::index(__source.len(), __key)?]
            })
            .shields_cost_per_gold,
            doubled,
        )?;
    }
    Ok(Commerce {
        corrupted: (adjusted).lost,
        taxes: taxes,
        beakers: science,
        happiness: luxury,
        wealth: wealth,
    })
}

/// Match the existing raw maintenance sum, including obsolete buildings.
// Python: openciv3/city_economy.py:179
pub(crate) fn city_maintenance(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
) -> rt::Result<i64> {
    Ok(({
        let mut __comprehension_result_628: Vec<i64> = Vec::new();
        let __comprehension_source_627 = ((city).buildings.clone());
        for item in __comprehension_source_627.iter().cloned() {
            __comprehension_result_628.push(
                ({
                    let __source = &(&(&(game).scenario).rules).buildings;
                    let __key = (item).building;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .maintenance_cost,
            );
        }
        __comprehension_result_628
    })
    .into_iter()
    .sum::<i64>())
}
