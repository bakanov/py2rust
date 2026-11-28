use py2rust_service_runtime as rt;

// Python: openciv3/unit_turns.py:10
pub(crate) fn max_hit_points(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
) -> rt::Result<i64> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    Ok((({
        let __source = &(rules).experience_levels;
        let __key = (unit).experience;
        &__source[rt::index(__source.len(), __key)?]
    })
    .base_hit_points)
        .checked_add(
            ({
                let __source = &(rules).units;
                let __key = (unit).prototype;
                &__source[rt::index(__source.len(), __key)?]
            })
            .hp_bonus,
        )
        .ok_or("integer overflow")?)
}

// Python: openciv3/unit_turns.py:15
pub(crate) fn healing_rate(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    mut rates: Option<crate::openciv3::global_rules::HealingRates>,
) -> rt::Result<i64> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    if (rates).is_none() {
        rates = (if (((&(rules).global_rules).len() as i64) != 0i64) {
            Some(
                ({
                    let __source = &(rules).global_rules;
                    let __key = 0i64;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .healing_rates
                .clone(),
            )
        } else {
            Some(crate::openciv3::global_rules::HealingRates____post_init__(
                &(crate::openciv3::global_rules::HealingRates {
                    friendly: 1i64,
                    neutral: 1i64,
                    hostile: 0i64,
                    city: 2i64,
                }),
            )?)
        });
    }
    let mut known: std::collections::BTreeSet<i64> = ({
        let __source = &(game).players;
        let __key = (unit).owner;
        &__source[rt::index(__source.len(), __key)?]
    })
    .known_technologies
    .clone();
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(rules).units, (unit).prototype)?;
    let mut city: Option<crate::openciv3::cities::City> = {
        let __find_source_743 = (game).cities.clone();
        let mut __find_result_743: Option<crate::openciv3::cities::City> = None;
        for city in __find_source_743.iter().cloned() {
            if (((city).x, (city).y) == ((unit).x, (unit).y)) {
                __find_result_743 = Some(city.clone());
                break;
            }
        }
        __find_result_743
    };
    if ((city).is_some()
        && (((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).owner == (unit).owner))
    {
        let mut repair: i64 = ([(0i64, 2i64), (1i64, 131072i64), (2i64, 262144i64)]
            .into_iter()
            .collect::<indexmap::IndexMap<_, _>>())
        .get(&((kind).domain))
        .ok_or("missing dict key")?
        .clone();
        for mut item in crate::openciv3::building_effects::effective_buildings(
            &((*(city).as_ref().ok_or("expected a value")?).clone()),
            &(game).cities,
            &(game).players,
            &(game).world,
            &rules,
        )? {
            let mut building: crate::openciv3::building_rules::Building =
                rt::at(&(rules).buildings, (item).building)?;
            if (((building).effects & repair) != 0 && {
                let __needle = (building).rendered_obsolete_by;
                let __container = &known;
                !__container.contains(&__needle)
            }) {
                return Ok((0i64).max(
                    (max_hit_points(game, unit)?)
                        .checked_sub((unit).hit_points)
                        .ok_or("integer overflow")?,
                ));
            }
        }
        return Ok(((*(rates).as_ref().ok_or("expected a value")?).clone()).city);
    }
    if ((kind).domain == 1i64) {
        return Ok(0i64);
    }
    let mut claim: Option<i64> = ((game).ownership.clone())
        .get(&(((unit).x, (unit).y)))
        .cloned();
    if (claim).is_none() {
        return Ok(((*(rates).as_ref().ok_or("expected a value")?).clone()).neutral);
    }
    let mut territory: i64 = (&({
        let mut __comprehension_result_745: Vec<i64> = Vec::new();
        let __comprehension_source_744 = ((game).cities.clone());
        for city in __comprehension_source_744.iter().cloned() {
            if (Some((city).id) == claim.clone()) {
                __comprehension_result_745.push((city).owner);
            }
        }
        __comprehension_result_745
    }))
        .iter()
        .next()
        .cloned()
        .ok_or("StopIteration")?;
    if (territory == (unit).owner) {
        return Ok(((*(rates).as_ref().ok_or("expected a value")?).clone()).friendly);
    }
    for mut city in (&(game).cities).iter() {
        if ((city).owner != (unit).owner) {
            continue;
        }
        for mut item in (&(city).buildings).iter() {
            let mut building: crate::openciv3::building_rules::Building =
                rt::at(&(rules).buildings, (item).building)?;
            if (((building).effects & 70368744177664i64) != 0 && {
                let __needle = (building).rendered_obsolete_by;
                let __container = &known;
                !__container.contains(&__needle)
            }) {
                return Ok(
                    (((*(rates.clone()).as_ref().ok_or("expected a value")?).clone()).neutral).max(
                        ((*(rates.clone()).as_ref().ok_or("expected a value")?).clone()).hostile,
                    ),
                );
            }
        }
    }
    Ok(((*(rates).as_ref().ok_or("expected a value")?).clone()).hostile)
}

// Python: openciv3/unit_turns.py:49
pub(crate) fn skip_unit_turn(
    game: &crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
) -> rt::Result<()> {
    unit.skipped_with_full_movement = ((unit).skipped_with_full_movement)
        | ((unit).movement_remaining
            >= ((({
                let __source = &(&(&(game).scenario).rules).units;
                let __key = (unit).prototype;
                &__source[rt::index(__source.len(), __key)?]
            })
            .movement) as f64));
    unit.movement_remaining = 0.0f64;
    Ok(())
}

// Python: openciv3/unit_turns.py:54
pub(crate) fn fortify_unit(mut unit: crate::openciv3::units::Unit) -> rt::Result<()> {
    unit.fortified = true;
    Ok(())
}

// Python: openciv3/unit_turns.py:58
pub(crate) fn wake_unit(mut unit: crate::openciv3::units::Unit) -> rt::Result<()> {
    unit.fortified = false;
    Ok(())
}

/// Heal eligible resting units, reset movement/bombardment, return HP gained.
///
/// A forced skipped turn grants no healing. Explicitly skipping with all moves
/// preserves resting eligibility; skipping after moving does not.
// Python: openciv3/unit_turns.py:62
pub(crate) fn begin_unit_turn(
    game: &crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
    mut skip: bool,
    rates: &Option<crate::openciv3::global_rules::HealingRates>,
) -> rt::Result<i64> {
    let mut movement: i64 = ({
        let __source = &(&(&(game).scenario).rules).units;
        let __key = (unit).prototype;
        &__source[rt::index(__source.len(), __key)?]
    })
    .movement;
    let mut healed: i64 = 0i64;
    if (!(skip)
        && (((unit).movement_remaining >= ((movement) as f64))
            || (unit).skipped_with_full_movement))
    {
        let mut maximum: i64 = max_hit_points(game, &unit)?;
        if ((unit).hit_points < maximum) {
            healed = ((maximum)
                .checked_sub((unit).hit_points)
                .ok_or("integer overflow")?)
            .min(healing_rate(game, &unit, (*rates).clone())?);
            unit.hit_points = ((unit).hit_points)
                .checked_add(healed)
                .ok_or("integer overflow")?;
        }
        unit.hit_points = ((unit).hit_points).min(maximum);
    }
    unit.skipped_with_full_movement = false;
    unit.movement_remaining = (if skip { 0.0f64 } else { (movement as f64) });
    unit.defensive_bombards_remaining = 1i64;
    Ok(healed)
}

/// Reset one player's units; the turn coordinator decides first-turn skipping.
// Python: openciv3/unit_turns.py:83
pub(crate) fn begin_player_unit_turn(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    mut skip: bool,
    rates: &Option<crate::openciv3::global_rules::HealingRates>,
) -> rt::Result<i64> {
    Ok(({
        let mut __comprehension_result_748: Vec<i64> = Vec::new();
        let __comprehension_source_746 = ((game).units.clone());
        for unit in __comprehension_source_746.iter().cloned() {
            if ((unit).owner == owner) {
                __comprehension_result_748.push({
                    let __call_747_0 = game;
                    let __call_747_1 = unit.clone();
                    let __call_747_2 = skip;
                    let __call_747_3 = rates;
                    begin_unit_turn(__call_747_0, __call_747_1, __call_747_2, __call_747_3)
                }?);
            }
        }
        __comprehension_result_748
    })
    .into_iter()
    .sum::<i64>())
}
