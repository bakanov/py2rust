use py2rust_service_runtime as rt;

/// Legacy wonder-race fallback; retain stored shields when switching.
// Python: openciv3/city_production.py:16
pub(crate) fn select_most_expensive(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
) -> rt::Result<()> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (city).owner)?;
    let mut difficulty: crate::openciv3::scenario_model::Difficulty =
        rt::at(&(&(game).scenario).difficulties, (game).difficulty)?;
    let mut network: crate::openciv3::trade_network::TradeNetwork =
        crate::openciv3::trade_network::TradeNetwork____post_init__(
            crate::openciv3::trade_network::TradeNetwork {
                game: (*game).clone(),
                owner: Some((city).owner),
                trade_with: None,
                segments: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                _routed_deals: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                _delivered_deals: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                _domestic_stock: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                _resource_indexes: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
                _embargoes: {
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in vec![].into_iter() {
                        __result.insert(__item);
                    }
                    __result
                },
                _capitals: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
            },
        )?;
    let mut hydro: crate::openciv3::hydrology::Hydrology =
        crate::openciv3::hydrology::Hydrology__from_world(&(game).world)?;
    let mut best_cost: i64 = (1i64).checked_neg().ok_or("integer overflow")?;
    let mut best_unit: Option<i64> = None;
    let mut best_building: Option<i64> = None;
    for mut for_target_26_4 in ((rules).units.clone())
        .into_iter()
        .enumerate()
        .map(|(__index, __value)| (__index as i64 + 0i64, __value))
        .collect::<Vec<_>>()
    {
        let (mut index, mut unit): (i64, crate::openciv3::unit_rules::UnitPrototype) =
            for_target_26_4;
        if {
            let __call_1164_0 = game;
            let __call_1164_1 = city;
            let __call_1164_2 = index;
            let __call_1164_3 = Some(network.clone());
            let __call_1164_default_3 = None;
            crate::openciv3::production_eligibility::can_train(
                __call_1164_0,
                __call_1164_1,
                __call_1164_2,
                __call_1164_default_3,
                __call_1164_3,
            )
        }? {
            let mut cost: i64 =
                crate::openciv3::production_cost::unit_cost(&unit, (player).human, &difficulty)?;
            if (cost > best_cost) {
                (best_cost, best_unit) = (cost, Some(index));
            }
        }
    }
    for mut for_target_31_4 in ((rules).buildings.clone())
        .into_iter()
        .enumerate()
        .map(|(__index, __value)| (__index as i64 + 0i64, __value))
        .collect::<Vec<_>>()
    {
        let (mut index, mut building): (i64, crate::openciv3::building_rules::Building) =
            for_target_31_4;
        if {
            let __call_1165_0 = game;
            let __call_1165_1 = city;
            let __call_1165_2 = index;
            let __call_1165_3 = Some(network.clone());
            let __call_1165_4 = Some(hydro.clone());
            crate::openciv3::production_eligibility::can_build(
                __call_1165_0,
                __call_1165_1,
                __call_1165_2,
                __call_1165_3,
                __call_1165_4,
            )
        }? {
            let mut cost: i64 =
                crate::openciv3::production_cost::city_building_cost(game, city, &building)?;
            if (cost > best_cost) {
                (best_cost, best_building) = (cost, Some(index));
            }
        }
    }
    if (best_building).is_some() {
        crate::openciv3::cities::City__select_building(
            (*city).clone(),
            (*(best_building).as_ref().ok_or("expected a value")?).clone(),
        )?;
    } else {
        if (best_unit).is_some() {
            crate::openciv3::cities::City__select_unit(
                (*city).clone(),
                (*(best_unit).as_ref().ok_or("expected a value")?).clone(),
            )?;
        } else {
            crate::openciv3::cities::City__select_inflow(
                (*city).clone(),
                &(if (({
                    let __source = &(rules).global_rules;
                    let __key = 0i64;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .wealth
                .clone())
                    != (crate::openciv3::inflows::WealthRule::UNAVAILABLE)
                {
                    Some(crate::openciv3::inflows::Inflow::WEALTH)
                } else {
                    None
                }),
            )?;
        }
    }
    Ok(())
}

/// Accumulate shields, construct a building, and resolve lost wonder races.
///
/// The completed city's target is cleared for the future chooser/controller.
// Python: openciv3/city_production.py:44
pub(crate) fn advance_building_production(
    mut game: crate::openciv3::game_state::GameState,
    mut city: crate::openciv3::cities::City,
    mut corruption: f64,
    hydro: &Option<crate::openciv3::hydrology::Hydrology>,
) -> rt::Result<Option<crate::openciv3::cities::CityBuilding>> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    crate::openciv3::cities::City__validate_production(
        &(city.clone()),
        ((&(rules).units).len() as i64),
        ((&(rules).buildings).len() as i64),
    )?;
    let mut index: Option<i64> = (city).producing_building.clone();
    if (index).is_none() {
        return Err("Building production requires a building target"
            .to_string()
            .into());
    }
    let mut building: crate::openciv3::building_rules::Building = rt::at(
        &(rules).buildings,
        (*(index.clone()).as_ref().ok_or("expected a value")?).clone(),
    )?;
    if ((building).population_cost < 0i64) {
        return Err("Building population cost cannot be negative"
            .to_string()
            .into());
    }
    let mut unavailable: bool = false;
    if ((building).spaceship_part >= 0i64) {
        unavailable = !({
            let __call_1166_0 = &game;
            let __call_1166_1 = &city;
            let __call_1166_2 = (*(index.clone()).as_ref().ok_or("expected a value")?).clone();
            let __call_1166_3 = (*hydro).clone();
            let __call_1166_default_3 = None;
            crate::openciv3::production_eligibility::can_build(
                __call_1166_0,
                __call_1166_1,
                __call_1166_2,
                __call_1166_default_3,
                __call_1166_3,
            )
        }?);
    } else {
        unavailable = (({
            let mut __comprehension_result_1168: Vec<bool> = Vec::new();
            let __comprehension_source_1167 = ((city).buildings.clone());
            for item in __comprehension_source_1167.iter().cloned() {
                __comprehension_result_1168.push((Some((item).building) == index.clone()));
            }
            __comprehension_result_1168
        })
        .into_iter()
        .any(|__value| __value)
            || (((building).effects & 268435456i64) != 0
                && match (index.clone()) {
                    Some(__value) => {
                        let __needle = __value;
                        let __container = &(game).great_wonders_built;
                        __container.contains(&__needle)
                    }
                    None => false,
                }));
    }
    if unavailable {
        select_most_expensive(&game, &city)?;
        return Ok(None);
    }
    let mut production: crate::openciv3::city_economy::CityProduction =
        crate::openciv3::city_economy::city_production(&game, &city, corruption, hydro, &None)?;
    if !((&(production).cost).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    let mut stored: i64 = ((city).shields_stored)
        .checked_add((production).useful)
        .ok_or("integer overflow")?;
    if ((stored
        < (*((production).cost.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone())
        || (crate::openciv3::cities::City__size(&city)? <= (building).population_cost))
    {
        city.shields_stored = (stored).min(
            (*((production).cost.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone(),
        );
        return Ok(None);
    }
    let mut completed: crate::openciv3::cities::CityBuilding =
        crate::openciv3::cities::CityBuilding {
            building: (*(index.clone()).as_ref().ok_or("expected a value")?).clone(),
            built_by: (city).owner,
            year: (game).year,
            total_culture: 0i64,
        };
    let mut destination: crate::openciv3::cities::City = city.clone();
    if ((building).spaceship_part >= 0i64) {
        destination = {
            let __find_source_1169 = (game).cities.clone();
            let mut __find_result_1169: crate::openciv3::cities::City = city.clone();
            for other in __find_source_1169.iter().cloned() {
                if (((other).owner == (city).owner) && (other).capital) {
                    __find_result_1169 = other.clone();
                    break;
                }
            }
            __find_result_1169
        };
    }
    ((destination).buildings).push(completed.clone());
    if ((building).population_cost != 0i64) {
        {
            let __start = rt::clamp_index(
                ((city).residents.clone()).len(),
                ((building).population_cost)
                    .checked_neg()
                    .ok_or("integer overflow")?,
            );
            let __stop = rt::clamp_index(
                ((city).residents.clone()).len(),
                ((city).residents.clone()).len() as i64,
            );
            ((city).residents.clone()).drain(__start..__stop);
        }
    }
    city.shields_stored = 0i64;
    city.producing_building = None;
    if (((building).effects & 268435456i64) != 0i64) {
        ((game).great_wonders_built)
            .insert((*(index.clone()).as_ref().ok_or("expected a value")?).clone());
        let mut scoring: Option<crate::openciv3::scenario_model::VictoryPointRules> =
            crate::openciv3::scenario_model::ScenarioDefinition__victory_point_rules(
                &(game).scenario,
            )?;
        if ((scoring).is_some() && !((game).game_over)) {
            {
                let __index = rt::index(game.players.len(), (city).owner)?;
                game.players
                    .get_mut(__index)
                    .ok_or("missing record")?
                    .victory_points = (({
                    let __source = &(game).players;
                    let __key = (city).owner;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .victory_points)
                    .checked_add(
                        (((*(scoring).as_ref().ok_or("expected a value")?).clone()).wonder)
                            .checked_mul((0i64).max((building).cost))
                            .ok_or("integer overflow")?,
                    )
                    .ok_or("integer overflow")?;
            }
        }
        for mut other in (&(game).cities).iter() {
            if (((other).owner != (city).owner)
                && ((other).producing_building.clone() == index.clone()))
            {
                select_most_expensive(&game, other)?;
            }
        }
    }
    Ok(Some(completed))
}

// Python: openciv3/city_production.py:93
pub(crate) fn create_city_unit(
    mut game: crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    mut prototype: i64,
) -> rt::Result<crate::openciv3::units::Unit> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    if !({
        let __compare_0 = 0i64;
        let __compare_1 = prototype;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = ((&(rules).units).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) {
        return Err("Invalid unit prototype".to_string().into());
    }
    let mut experience: i64 = ({
        let __source = &(rules).global_rules;
        let __key = 0i64;
        &__source[rt::index(__source.len(), __key)?]
    })
    .default_unit_experience;
    if !({
        let __compare_0 = 0i64;
        let __compare_1 = experience;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = ((&(rules).experience_levels).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) {
        return Err("Invalid default unit experience".to_string().into());
    }
    let mut kind: crate::openciv3::unit_rules::UnitPrototype = rt::at(&(rules).units, prototype)?;
    let mut veteran_flag: i64 = rt::at(
        &({
            let __tuple_value = &((2i64, 131072i64, 262144i64));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        }),
        (kind).domain,
    )?;
    for mut item in crate::openciv3::building_effects::effective_buildings(
        city,
        &(game).cities,
        &(game).players,
        &(game).world,
        &rules,
    )? {
        let mut building: crate::openciv3::building_rules::Building =
            rt::at(&(rules).buildings, (item).building)?;
        let mut effects: i64 = (if (&(building).unit_production_effects).is_some() {
            (*((building).unit_production_effects.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone()
        } else {
            (building).effects
        });
        if ((effects & veteran_flag) != 0i64) {
            experience = ((experience).checked_add(1i64).ok_or("integer overflow")?).min(
                ((&(rules).experience_levels).len() as i64)
                    .checked_sub(1i64)
                    .ok_or("integer overflow")?,
            );
        }
    }
    let mut unit: crate::openciv3::units::Unit = crate::openciv3::units::Unit {
        id: crate::openciv3::game_state::GameState__allocate_unit_id(game.clone())?,
        prototype: prototype,
        owner: (city).owner,
        nationality: (city).owner,
        name: (kind).name.clone(),
        x: (city).x,
        y: (city).y,
        previous_x: (city).x,
        previous_y: (city).y,
        experience: experience,
        hit_points: (({
            let __source = &(rules).experience_levels;
            let __key = experience;
            &__source[rt::index(__source.len(), __key)?]
        })
        .base_hit_points)
            .checked_add((kind).hp_bonus)
            .ok_or("integer overflow")?,
        movement_remaining: ((kind).movement as f64),
        ai_strategy: (1i64).checked_neg().ok_or("integer overflow")?,
        action: String::new(),
        transported_by: None,
        settler_mission: None,
        escorting: None,
        worker_job: None,
        worker_progress: 0.0f64,
        fortified: false,
        skipped_with_full_movement: false,
        defensive_bombards_remaining: 0i64,
        defender_destination: None,
        goto_destination: None,
        facing_override: None,
    };
    ((game).units).push(unit.clone());
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
    Ok(unit)
}

/// Apply shields to a unit target and create it when population permits.
///
/// Returns the completed unit for the future turn controller to notify the UI
/// and choose the next production target. It leaves that selection unchanged.
// Python: openciv3/city_production.py:117
pub(crate) fn advance_unit_production(
    game: &crate::openciv3::game_state::GameState,
    mut city: crate::openciv3::cities::City,
    mut corruption: f64,
    hydro: &Option<crate::openciv3::hydrology::Hydrology>,
) -> rt::Result<Option<crate::openciv3::units::Unit>> {
    crate::openciv3::cities::City__validate_production(
        &(city.clone()),
        ((&(&(&(game).scenario).rules).units).len() as i64),
        ((&(&(&(game).scenario).rules).buildings).len() as i64),
    )?;
    if (&(city).producing_unit).is_none() {
        return Err("Unit production requires a unit target".to_string().into());
    }
    let mut prototype: crate::openciv3::unit_rules::UnitPrototype = rt::at(
        &(&(&(game).scenario).rules).units,
        (*((city).producing_unit.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone(),
    )?;
    if ((prototype).population_cost < 0i64) {
        return Err("Unit population cost cannot be negative".to_string().into());
    }
    let mut production: crate::openciv3::city_economy::CityProduction =
        crate::openciv3::city_economy::city_production(game, &city, corruption, hydro, &None)?;
    if !((&(production).cost).is_some()) {
        rt::assertion(false, &("".to_string()))?;
    }
    let mut stored: i64 = ((city).shields_stored)
        .checked_add((production).useful)
        .ok_or("integer overflow")?;
    if ((stored
        < (*((production).cost.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone())
        || (crate::openciv3::cities::City__size(&city)? <= (prototype).population_cost))
    {
        city.shields_stored = (stored).min(
            (*((production).cost.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone(),
        );
        return Ok(None);
    }
    let mut unit: crate::openciv3::units::Unit = create_city_unit(
        (*game).clone(),
        &city,
        (*((city).producing_unit.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone(),
    )?;
    city.shields_stored = 0i64;
    if ((prototype).population_cost != 0i64) {
        {
            let __start = rt::clamp_index(
                ((city).residents.clone()).len(),
                ((prototype).population_cost)
                    .checked_neg()
                    .ok_or("integer overflow")?,
            );
            let __stop = rt::clamp_index(
                ((city).residents.clone()).len(),
                ((city).residents.clone()).len() as i64,
            );
            ((city).residents.clone()).drain(__start..__stop);
        }
    }
    Ok(Some(unit))
}
