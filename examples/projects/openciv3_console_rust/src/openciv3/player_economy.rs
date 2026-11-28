use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct UnitSupport {
    pub(crate) total: i64,
    pub(crate) allowed: i64,
    pub(crate) cost: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct PlayerCommerce {
    pub(crate) corrupted: i64,
    pub(crate) taxes: i64,
    pub(crate) specialist_taxes: i64,
    pub(crate) beakers: i64,
    pub(crate) happiness: i64,
    pub(crate) interest: i64,
    pub(crate) maintenance: i64,
    pub(crate) unit_support: i64,
    pub(crate) wealth: i64,
    pub(crate) from_other_civilizations: i64,
    pub(crate) to_other_civilizations: i64,
}

// Python: openciv3/player_economy.py:25
pub(crate) fn requires_unit_support(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<bool> {
    Ok((((unit).nationality == (unit).owner)
        && ({
            let __source = &(&(&(game).scenario).rules).units;
            let __key = (unit).prototype;
            &__source[rt::index(__source.len(), __key)?]
        })
        .require_support))
}

// Python: openciv3/player_economy.py:29
pub(crate) fn unit_support(
    game: &crate::openciv3::game_state::GameState,
    player: &crate::openciv3::players::Player,
) -> rt::Result<UnitSupport> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut government: crate::openciv3::government_rules::Government =
        rt::at(&(rules).governments, (player).government)?;
    let mut difficulty: crate::openciv3::scenario_model::Difficulty =
        rt::at(&(&(game).scenario).difficulties, (game).difficulty)?;
    let mut sizes: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(rules).global_rules, 0i64)?;
    let mut units: Vec<crate::openciv3::units::Unit> = {
        let mut __comprehension_result_807: Vec<crate::openciv3::units::Unit> = Vec::new();
        let __comprehension_source_806 = ((game).units.clone());
        for unit in __comprehension_source_806.iter().cloned() {
            if ((unit).owner == (player).civilization) {
                __comprehension_result_807.push(unit.clone());
            }
        }
        __comprehension_result_807
    };
    let mut allowed: i64 = (if (player).human {
        0i64
    } else {
        (difficulty).additional_free_support
    });
    for mut city in (&(game).cities).iter() {
        if ((city).owner != (player).civilization) {
            continue;
        }
        if !((player).human) {
            allowed = (allowed)
                .checked_add((difficulty).support_per_settlement)
                .ok_or("integer overflow")?;
        }
        if (crate::openciv3::cities::City__size(city)? <= (sizes).maximum_level1_city_size) {
            allowed = (allowed)
                .checked_add((government).free_units_per_town)
                .ok_or("integer overflow")?;
        } else {
            if (crate::openciv3::cities::City__size(city)? <= (sizes).maximum_level2_city_size) {
                allowed = (allowed)
                    .checked_add((government).free_units_per_city)
                    .ok_or("integer overflow")?;
            } else {
                allowed = (allowed)
                    .checked_add((government).free_units_per_metropolis)
                    .ok_or("integer overflow")?;
            }
        }
    }
    allowed = (allowed)
        .checked_add(
            ({
                let mut __comprehension_result_809: Vec<bool> = Vec::new();
                let __comprehension_source_808 = (units.clone());
                for unit in __comprehension_source_808.iter().cloned() {
                    __comprehension_result_809.push(!(requires_unit_support(game, &unit)?));
                }
                __comprehension_result_809
            })
            .into_iter()
            .map(|value| value as i64)
            .sum::<i64>(),
        )
        .ok_or("integer overflow")?;
    if ((government).free_units == (1i64).checked_neg().ok_or("integer overflow")?) {
        allowed = ((units).len() as i64);
    }
    Ok(UnitSupport {
        total: ((units).len() as i64),
        allowed: allowed,
        cost: (0i64).max(
            (((units).len() as i64)
                .checked_sub(allowed)
                .ok_or("integer overflow")?)
            .checked_mul((government).unit_cost)
            .ok_or("integer overflow")?,
        ),
    })
}

// Python: openciv3/player_economy.py:70
pub(crate) fn PlayerCommerce__net_gold(self_: &PlayerCommerce) -> rt::Result<i64> {
    Ok(((((((((self_).taxes)
        .checked_add((self_).specialist_taxes)
        .ok_or("integer overflow")?)
    .checked_add((self_).interest)
    .ok_or("integer overflow")?)
    .checked_add((self_).wealth)
    .ok_or("integer overflow")?)
    .checked_add((self_).from_other_civilizations)
    .ok_or("integer overflow")?)
    .checked_sub((self_).to_other_civilizations)
    .ok_or("integer overflow")?)
    .checked_sub((self_).maintenance)
    .ok_or("integer overflow")?)
    .checked_sub((self_).unit_support)
    .ok_or("integer overflow")?)
}

/// Aggregate current income and expenses.
// Python: openciv3/player_economy.py:76
pub(crate) fn player_commerce(
    game: &crate::openciv3::game_state::GameState,
    player: &crate::openciv3::players::Player,
    mut interest_rate: Option<f64>,
    mut max_interest: Option<i64>,
) -> rt::Result<PlayerCommerce> {
    let mut result: PlayerCommerce = PlayerCommerce {
        corrupted: 0i64,
        taxes: 0i64,
        specialist_taxes: 0i64,
        beakers: 0i64,
        happiness: 0i64,
        interest: 0i64,
        maintenance: 0i64,
        unit_support: 0i64,
        wealth: 0i64,
        from_other_civilizations: 0i64,
        to_other_civilizations: 0i64,
    };
    let mut diplomatic: crate::openciv3::recurring_deals::DiplomaticPayments =
        crate::openciv3::recurring_deals::payments(
            &({
                let mut __comprehension_result_812: Vec<
                    crate::openciv3::recurring_deals::RecurringDeal,
                > = Vec::new();
                let __comprehension_source_810 = (((&(game).diplomacy).relationships.clone())
                    .iter()
                    .map(|(__key, __value)| (__key.clone(), __value.clone()))
                    .collect::<Vec<_>>());
                for ((owner, _), relationship) in __comprehension_source_810.iter().cloned() {
                    if (owner == (player).civilization) {
                        let __comprehension_source_811 = ((relationship).deals.clone());
                        for deal in __comprehension_source_811.iter().cloned() {
                            __comprehension_result_812.push(deal.clone());
                        }
                    }
                }
                __comprehension_result_812
            }),
        )?;
    result.from_other_civilizations = (diplomatic).incoming;
    result.to_other_civilizations = (diplomatic).outgoing;
    let mut cities: Vec<crate::openciv3::cities::City> = {
        let mut __comprehension_result_814: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_813 = ((game).cities.clone());
        for city in __comprehension_source_813.iter().cloned() {
            if ((city).owner == (player).civilization) {
                __comprehension_result_814.push(city.clone());
            }
        }
        __comprehension_result_814
    };
    if !(((cities).len() as i64) != 0i64) {
        return Ok(result);
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    if (interest_rate).is_none() {
        interest_rate = (if (((&(rules).global_rules).len() as i64) != 0i64) {
            Some(
                ({
                    let __source = &(rules).global_rules;
                    let __key = 0i64;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .treasury_interest_rate,
            )
        } else {
            Some(0.05f64)
        });
    }
    if (max_interest).is_none() {
        max_interest = (if (((&(rules).global_rules).len() as i64) != 0i64) {
            Some(
                ({
                    let __source = &(rules).global_rules;
                    let __key = 0i64;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .max_interest,
            )
        } else {
            Some(50i64)
        });
    }
    let mut corruption: indexmap::IndexMap<i64, f64> =
        crate::openciv3::corruption::corruption_levels(game)?;
    let mut hydro: crate::openciv3::hydrology::Hydrology =
        crate::openciv3::hydrology::Hydrology__from_world(&(game).world)?;
    let mut interest_buildings: i64 = 0i64;
    for mut city in cities {
        let mut commerce: crate::openciv3::city_economy::Commerce =
            crate::openciv3::city_economy::city_commerce(
                game,
                &city,
                (corruption)
                    .get(&((city).id))
                    .ok_or("missing dict key")?
                    .clone(),
                &(Some(hydro.clone())),
                &None,
                true,
            )?;
        let mut specialist_taxes: i64 = ({
            let mut __comprehension_result_816: Vec<i64> = Vec::new();
            let __comprehension_source_815 = ((city).residents.clone());
            for resident in __comprehension_source_815.iter().cloned() {
                __comprehension_result_816.push(
                    ({
                        let __source = &(rules).citizens;
                        let __key = (resident).citizen_type;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .taxes,
                );
            }
            __comprehension_result_816
        })
        .into_iter()
        .sum::<i64>();
        result.corrupted = ((result).corrupted)
            .checked_add((commerce).corrupted)
            .ok_or("integer overflow")?;
        result.taxes = ((result).taxes)
            .checked_add(
                ((commerce).taxes)
                    .checked_sub(specialist_taxes)
                    .ok_or("integer overflow")?,
            )
            .ok_or("integer overflow")?;
        result.specialist_taxes = ((result).specialist_taxes)
            .checked_add(specialist_taxes)
            .ok_or("integer overflow")?;
        result.beakers = ((result).beakers)
            .checked_add((commerce).beakers)
            .ok_or("integer overflow")?;
        result.happiness = ((result).happiness)
            .checked_add((commerce).happiness)
            .ok_or("integer overflow")?;
        result.wealth = ((result).wealth)
            .checked_add((commerce).wealth)
            .ok_or("integer overflow")?;
        result.maintenance = ((result).maintenance)
            .checked_add(crate::openciv3::city_economy::city_maintenance(
                game, &city,
            )?)
            .ok_or("integer overflow")?;
        interest_buildings = (interest_buildings)
            .checked_add(
                ({
                    let mut __comprehension_result_818: Vec<bool> = Vec::new();
                    let __comprehension_source_817 = ((city).buildings.clone());
                    for item in __comprehension_source_817.iter().cloned() {
                        __comprehension_result_818.push(
                            (({
                                let __source = &(rules).buildings;
                                let __key = (item).building;
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .effects
                                & 2199023255552i64)
                                != 0,
                        );
                    }
                    __comprehension_result_818
                })
                .into_iter()
                .map(|value| value as i64)
                .sum::<i64>(),
            )
            .ok_or("integer overflow")?;
    }
    result.unit_support = (unit_support(game, player)?).cost;
    result.interest = (interest_buildings)
        .checked_mul(
            (rt::int_float(rt::finite(
                (((player).gold) as f64)
                    * (*(interest_rate).as_ref().ok_or("expected a value")?).clone(),
            )?)?)
            .min((*(max_interest).as_ref().ok_or("expected a value")?).clone()),
        )
        .ok_or("integer overflow")?;
    Ok(result)
}
