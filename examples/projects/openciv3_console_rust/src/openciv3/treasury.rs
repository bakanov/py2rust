use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct TreasuryUpdate {
    pub(crate) net_gold: i64,
    pub(crate) science_income: i64,
    pub(crate) removed_units: Vec<i64>,
    pub(crate) science_cuts: i64,
    pub(crate) luxury_cuts: i64,
}

/// Settle before production; preserve pre-cut science for the research phase.
///
/// Remove excess supported units first, then shift science and luxury spending
/// to taxes. As in the legacy engine, unaffordable maintenance after all these
/// steps is an error; building liquidation is not implemented.
// Python: openciv3/treasury.py:20
pub(crate) fn settle_treasury(
    game: &crate::openciv3::game_state::GameState,
    mut player: crate::openciv3::players::Player,
    mut rng: rt::Random,
) -> rt::Result<TreasuryUpdate> {
    if crate::openciv3::players::Player__barbarian(&player)? {
        return Ok(TreasuryUpdate {
            net_gold: 0i64,
            science_income: 0i64,
            removed_units: vec![],
            science_cuts: 0i64,
            luxury_cuts: 0i64,
        });
    }
    let mut initial: crate::openciv3::player_economy::PlayerCommerce =
        crate::openciv3::player_economy::player_commerce(game, &player, None, None)?;
    let mut commerce: crate::openciv3::player_economy::PlayerCommerce = initial.clone();
    let mut removed: Vec<i64> = vec![];
    let mut chained_locals_32_4: i64 = 0i64;
    let mut science_cuts: i64 = chained_locals_32_4;
    let mut luxury_cuts: i64 = chained_locals_32_4;
    while (((player).gold)
        .checked_add(crate::openciv3::player_economy::PlayerCommerce__net_gold(
            &commerce,
        )?)
        .ok_or("integer overflow")?
        < 0i64)
    {
        if ((commerce).unit_support > 0i64) {
            while ((crate::openciv3::player_economy::unit_support(game, &player)?).cost > 0i64) {
                let mut candidates: Vec<crate::openciv3::units::Unit> = {
                    let mut __comprehension_result_1178: Vec<crate::openciv3::units::Unit> =
                        Vec::new();
                    let __comprehension_source_1177 = ((game).units.clone());
                    for unit in __comprehension_source_1177.iter().cloned() {
                        if (((unit).owner == (player).civilization)
                            && crate::openciv3::player_economy::requires_unit_support(game, &unit)?)
                        {
                            __comprehension_result_1178.push(unit.clone());
                        }
                    }
                    __comprehension_result_1178
                };
                if !(((candidates).len() as i64) != 0i64) {
                    return Err("Treasury owes upkeep with no supported units to disband"
                        .to_string()
                        .into());
                }
                let mut result: crate::openciv3::unit_lifecycle::RemovalResult =
                    crate::openciv3::unit_lifecycle::remove_unit(
                        &((*game).clone()),
                        &(rt::at(
                            &(candidates.clone()),
                            rt::random_randrange(
                                &(rng.clone()),
                                0i64,
                                ((candidates).len() as i64),
                            )?,
                        )?),
                    )?;
                {
                    let __values = (result).removed.clone();
                    removed.extend(__values);
                };
            }
        } else {
            if ((player).science_rate > 0i64) {
                player.science_rate = ((player).science_rate)
                    .checked_sub(1i64)
                    .ok_or("integer overflow")?;
                player.tax_rate = ((player).tax_rate)
                    .checked_add(1i64)
                    .ok_or("integer overflow")?;
                science_cuts = (science_cuts).checked_add(1i64).ok_or("integer overflow")?;
            } else {
                if ((player).luxury_rate > 0i64) {
                    player.luxury_rate = ((player).luxury_rate)
                        .checked_sub(1i64)
                        .ok_or("integer overflow")?;
                    player.tax_rate = ((player).tax_rate)
                        .checked_add(1i64)
                        .ok_or("integer overflow")?;
                    luxury_cuts = (luxury_cuts).checked_add(1i64).ok_or("integer overflow")?;
                } else {
                    return Err("Treasury remains insolvent after support and spending cuts"
                        .to_string()
                        .into());
                }
            }
        }
        commerce = crate::openciv3::player_economy::player_commerce(game, &player, None, None)?;
    }
    player.last_gold_per_turn =
        crate::openciv3::player_economy::PlayerCommerce__net_gold(&commerce)?;
    player.gold = ((player).gold)
        .checked_add(crate::openciv3::player_economy::PlayerCommerce__net_gold(
            &commerce,
        )?)
        .ok_or("integer overflow")?;
    Ok(TreasuryUpdate {
        net_gold: crate::openciv3::player_economy::PlayerCommerce__net_gold(&commerce)?,
        science_income: (initial).beakers,
        removed_units: (removed).iter().cloned().collect::<Vec<_>>(),
        science_cuts: science_cuts,
        luxury_cuts: luxury_cuts,
    })
}
