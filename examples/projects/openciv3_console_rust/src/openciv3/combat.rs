use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum CombatOutcome {
    IMPOSSIBLE,
    ATTACKER_KILLED,
    DEFENDER_KILLED,
    ATTACKER_RETREATED,
    DEFENDER_RETREATED,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct Promotion {
    pub(crate) unit_id: i64,
    pub(crate) owner: i64,
    pub(crate) unit_name: String,
    pub(crate) rank: String,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct CombatResult {
    pub(crate) outcome: CombatOutcome,
    pub(crate) rounds: i64,
    pub(crate) bombarder: Option<i64>,
    pub(crate) bombard_hit: bool,
    pub(crate) promotion: Option<Promotion>,
    pub(crate) removal: Option<crate::openciv3::unit_lifecycle::RemovalResult>,
    pub(crate) protection_wars: Vec<crate::openciv3::diplomacy_actions::WarDeclaration>,
    pub(crate) captured_unit: Option<i64>,
    pub(crate) golden_age_started: Option<i64>,
}

// Python: openciv3/combat.py:45
pub(crate) fn CombatResult__promoted(self_: &CombatResult) -> rt::Result<Option<i64>> {
    Ok((if (&(self_).promotion).is_none() {
        None
    } else {
        Some(
            ((*((self_).promotion.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone())
            .unit_id,
        )
    }))
}

// Python: openciv3/combat.py:49
pub(crate) fn retreat_chance(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    opponent: &crate::openciv3::units::Unit,
) -> rt::Result<f64> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    if ((({
        let __source = &(rules).units;
        let __key = (unit).prototype;
        &__source[rt::index(__source.len(), __key)?]
    })
    .movement
        <= 1i64)
        || (({
            let __source = &(rules).units;
            let __key = (opponent).prototype;
            &__source[rt::index(__source.len(), __key)?]
        })
        .movement
            > 1i64))
    {
        return Ok(0.0f64);
    }
    Ok(rt::float_true_div(
        ({
            let __source = &(rules).experience_levels;
            let __key = (unit).experience;
            &__source[rt::index(__source.len(), __key)?]
        })
        .retreat_bonus,
        ((100i64) as f64),
    )?)
}

// Python: openciv3/combat.py:56
pub(crate) fn promote(
    game: &crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
) -> rt::Result<bool> {
    if (((unit).experience)
        .checked_add(1i64)
        .ok_or("integer overflow")?
        >= ((&(&(&(game).scenario).rules).experience_levels).len() as i64))
    {
        return Ok(false);
    }
    unit.experience = ((unit).experience)
        .checked_add(1i64)
        .ok_or("integer overflow")?;
    unit.hit_points = ((unit).hit_points)
        .checked_add(1i64)
        .ok_or("integer overflow")?;
    Ok(true)
}

// Python: openciv3/combat.py:64
pub(crate) fn roll_promotion(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    opponent: &crate::openciv3::units::Unit,
    mut rng: rt::Random,
) -> rt::Result<Option<Promotion>> {
    if ((unit).owner == 0i64) {
        return Ok(None);
    }
    let mut chance: Option<f64> = ({
        let __source = &(&(&(game).scenario).rules).experience_levels;
        let __key = (unit).experience;
        &__source[rt::index(__source.len(), __key)?]
    })
    .promotion_chance
    .clone();
    if (chance).is_none() {
        let mut chances: (f64, f64, f64, f64) = (0.5f64, 0.25f64, 0.125f64, 0.0f64);
        chance = (if ((unit).experience < {
            let _ = chances;
            4i64
        }) {
            Some(rt::at(
                &(vec![
                    (chances).0 as f64,
                    (chances).1 as f64,
                    (chances).2 as f64,
                    (chances).3 as f64,
                ]),
                (unit).experience,
            )?)
        } else {
            Some(0.0f64)
        });
    }
    if ((opponent).owner == 0i64) {
        chance = Some(rt::float_true_div(
            (*(chance).as_ref().ok_or("expected a value")?).clone(),
            ((2i64) as f64),
        )?);
    }
    if {
        let __needle = "Militaristic".to_string();
        let __container = &({
            let __source = &(&(game).scenario).civilizations;
            let __key = (unit).owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .traits;
        __container.contains(&__needle)
    } {
        chance = Some(rt::finite(
            (*(chance).as_ref().ok_or("expected a value")?).clone() * ((2i64) as f64),
        )?);
    }
    if ((rt::random_random(&rng) >= (*(chance).as_ref().ok_or("expected a value")?).clone())
        || !(promote(game, (*unit).clone())?))
    {
        return Ok(None);
    }
    let mut rank: String = ({
        let __source = &(&(&(game).scenario).rules).experience_levels;
        let __key = (unit).experience;
        &__source[rt::index(__source.len(), __key)?]
    })
    .name
    .clone();
    Ok(Some(Promotion {
        unit_id: (unit).id,
        owner: (unit).owner,
        unit_name: (unit).name.clone(),
        rank: rank,
    }))
}

// Python: openciv3/combat.py:82
pub(crate) fn _capture_defeated_unit(
    mut game: crate::openciv3::game_state::GameState,
    victor: &crate::openciv3::units::Unit,
    defeated: &crate::openciv3::units::Unit,
    mut rng: rt::Random,
) -> rt::Result<Option<i64>> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut result: i64 = ({
        let __source = &(rules).units;
        let __key = (victor).prototype;
        &__source[rt::index(__source.len(), __key)?]
    })
    .enslave_result;
    if (!({
        let __compare_0 = 0i64;
        let __compare_1 = result;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = ((&(rules).units).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) || (rt::random_random(&rng) >= rt::int_true_div(1i64, 3i64)?))
    {
        return Ok(None);
    }
    let mut kind: crate::openciv3::unit_rules::UnitPrototype = rt::at(&(rules).units, result)?;
    let mut experience: i64 = (if (((&(rules).global_rules).len() as i64) != 0i64) {
        ({
            let __source = &(rules).global_rules;
            let __key = 0i64;
            &__source[rt::index(__source.len(), __key)?]
        })
        .default_unit_experience
    } else {
        0i64
    });
    let mut unit_id: i64 = crate::openciv3::game_state::GameState__allocate_unit_id(game.clone())?;
    ((game).units).push(crate::openciv3::units::Unit {
        id: unit_id,
        prototype: result,
        owner: (victor).owner,
        nationality: (defeated).nationality,
        name: (kind).name.clone(),
        x: (victor).x,
        y: (victor).y,
        previous_x: (victor).x,
        previous_y: (victor).y,
        experience: experience,
        hit_points: (({
            let __source = &(rules).experience_levels;
            let __key = experience;
            &__source[rt::index(__source.len(), __key)?]
        })
        .base_hit_points)
            .checked_add((kind).hp_bonus)
            .ok_or("integer overflow")?,
        movement_remaining: 0.0f64,
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
    });
    Ok(Some(unit_id))
}

/// Resolve an adjacent battle; movement cost and advancing belong to the caller.
///
/// A defending retreat counts only after the unit actually moves. This avoids
/// the legacy success result when its movement was exhausted or blocked.
// Python: openciv3/combat.py:96
pub(crate) fn fight(
    mut game: crate::openciv3::game_state::GameState,
    mut attacker: crate::openciv3::units::Unit,
    mut defender: crate::openciv3::units::Unit,
    mut rng: rt::Random,
) -> rt::Result<CombatResult> {
    let mut impossible: CombatResult = CombatResult {
        outcome: CombatOutcome::IMPOSSIBLE,
        rounds: 0i64,
        bombarder: None,
        bombard_hit: false,
        promotion: None,
        removal: None,
        protection_wars: vec![],
        captured_unit: None,
        golden_age_started: None,
    };
    if (!(({
        let mut __comprehension_result_651: Vec<bool> = Vec::new();
        let __comprehension_source_650 = ((game).units.clone());
        for unit in __comprehension_source_650.iter().cloned() {
            __comprehension_result_651.push(((unit).id == (attacker).id));
        }
        __comprehension_result_651
    })
    .into_iter()
    .any(|__value| __value))
        || !(({
            let mut __comprehension_result_653: Vec<bool> = Vec::new();
            let __comprehension_source_652 = ((game).units.clone());
            for unit in __comprehension_source_652.iter().cloned() {
                __comprehension_result_653.push(((unit).id == (defender).id));
            }
            __comprehension_result_653
        })
        .into_iter()
        .any(|__value| __value)))
    {
        return Ok(impossible);
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let (mut attack_kind, mut defense_kind): (
        crate::openciv3::unit_rules::UnitPrototype,
        crate::openciv3::unit_rules::UnitPrototype,
    ) = (
        rt::at(&(rules).units, (attacker).prototype)?,
        rt::at(&(rules).units, (defender).prototype)?,
    );
    let mut origin: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (attacker).x, (attacker).y)?;
    let mut target: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (defender).x, (defender).y)?;
    if ((origin).is_none()
        || ((target).is_none()
            || (match (target.clone()) {
                Some(__value) => {
                    let __needle = __value;
                    let __container = &(crate::openciv3::world::WorldMap__neighbors(
                        &(game).world,
                        &((*(origin.clone()).as_ref().ok_or("expected a value")?).clone()),
                    )?);
                    !__container.contains(&__needle)
                }
                None => true,
            } || (((attacker).hit_points <= 0i64)
                || (((defender).hit_points <= 0i64)
                    || (((attack_kind).attack <= 0i64)
                        || ((&(defender).transported_by).is_some()
                            || (((attack_kind).domain != (defense_kind).domain)
                                || !(crate::openciv3::diplomacy::Diplomacy__at_war(
                                    &(game).diplomacy,
                                    (attacker).owner,
                                    (defender).owner,
                                )?)))))))))
    {
        return Ok(impossible);
    }
    let mut attack: f64 = crate::openciv3::combat_strength::combat_strength(
        &game,
        &attacker,
        crate::openciv3::combat_strength::CombatRole::ATTACK,
        &None,
        &None,
    )?;
    let mut defense: f64 = {
        let __call_654_0 = &game;
        let __call_654_1 = &defender;
        let __call_654_2 = crate::openciv3::combat_strength::CombatRole::DEFENSE;
        let __call_654_3 = &origin;
        let __call_654_default_4 = &None;
        crate::openciv3::combat_strength::combat_strength(
            __call_654_0,
            __call_654_1,
            __call_654_2,
            __call_654_3,
            __call_654_default_4,
        )
    }?;
    if (rt::finite(attack + defense)? <= ((0i64) as f64)) {
        return Ok(impossible);
    }
    let mut wars: Vec<crate::openciv3::diplomacy_actions::WarDeclaration> = {
        let __call_655_0 = &game;
        let __call_655_1 = (attacker).owner;
        let __call_655_2 = (defender).owner;
        let __call_655_3 = &((
            ((*(target.clone()).as_ref().ok_or("expected a value")?).clone()).x,
            ((*(target.clone()).as_ref().ok_or("expected a value")?).clone()).y,
        ));
        let __call_655_4 = rng.clone();
        crate::openciv3::diplomacy_actions::honor_mutual_protection(
            __call_655_0,
            __call_655_1,
            __call_655_2,
            __call_655_3,
            __call_655_4,
        )
    }?;
    let mut odds: f64 = rt::float_true_div(attack, rt::finite(attack + defense)?)?;
    let mut bombarder: Option<crate::openciv3::units::Unit> = None;
    let mut bombard_strength: f64 = 0.0f64;
    for mut unit in (&(game).units).iter() {
        if (((unit).id == (defender).id)
            || ((&(unit).transported_by).is_some()
                || ((((unit).x, (unit).y) != ((defender).x, (defender).y))
                    || ((unit).defensive_bombards_remaining <= 0i64))))
        {
            continue;
        }
        if !(crate::openciv3::diplomacy::Diplomacy__at_war(
            &(game).diplomacy,
            (attacker).owner,
            (unit).owner,
        )?) {
            continue;
        }
        let mut strength: f64 = crate::openciv3::combat_strength::combat_strength(
            &game,
            unit,
            crate::openciv3::combat_strength::CombatRole::DEFENSIVE_BOMBARD,
            &None,
            &None,
        )?;
        if (strength > bombard_strength) {
            (bombarder, bombard_strength) = (Some((*unit).clone()), strength);
        }
    }
    let mut fired: Option<i64> = None;
    let mut hit: bool = false;
    if ((bombarder).is_some() && ((attacker).hit_points > 1i64)) {
        fired = Some(((*(bombarder.clone()).as_ref().ok_or("expected a value")?).clone()).id);
        let mut resistance: f64 = {
            let __call_656_0 = &game;
            let __call_656_1 = &attacker;
            let __call_656_2 =
                crate::openciv3::combat_strength::CombatRole::DEFENSIVE_BOMBARD_DEFENSE;
            let __call_656_3 = &target;
            let __call_656_default_4 = &None;
            crate::openciv3::combat_strength::combat_strength(
                __call_656_0,
                __call_656_1,
                __call_656_2,
                __call_656_3,
                __call_656_default_4,
            )
        }?;
        hit = (rt::random_random(&rng)
            < rt::float_true_div(bombard_strength, rt::finite(bombard_strength + resistance)?)?);
        attacker.hit_points = ((attacker).hit_points)
            .checked_sub(((hit) as i64))
            .ok_or("integer overflow")?;
        bombarder
            .as_mut()
            .ok_or("expected a value")?
            .defensive_bombards_remaining =
            (((*(bombarder.clone()).as_ref().ok_or("expected a value")?).clone())
                .defensive_bombards_remaining)
                .checked_sub(1i64)
                .ok_or("integer overflow")?;
    }
    let mut retreat_eligible: bool = (((defender).hit_points > 1i64)
        && !(({
            let mut __comprehension_result_658: Vec<bool> = Vec::new();
            let __comprehension_source_657 = ((game).cities.clone());
            for city in __comprehension_source_657.iter().cloned() {
                __comprehension_result_658
                    .push((((city).x, (city).y) == ((defender).x, (defender).y)));
            }
            __comprehension_result_658
        })
        .into_iter()
        .any(|__value| __value)));
    let mut rounds: i64 = 0i64;
    let mut outcome: CombatOutcome = CombatOutcome::DEFENDER_KILLED;
    let (mut dead, mut survivor): (crate::openciv3::units::Unit, crate::openciv3::units::Unit) =
        (defender.clone(), attacker.clone());
    loop {
        rounds = (rounds).checked_add(1i64).ok_or("integer overflow")?;
        if (rt::random_random(&rng) < odds) {
            if (retreat_eligible
                && (((defender).hit_points == 1i64)
                    && (rt::random_random(&rng) < retreat_chance(&game, &defender, &attacker)?)))
            {
                let mut dx: i64 = crate::strategy::grid::axis_delta(
                    ((*(target.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                    ((*(origin.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                    (&(game).world).width,
                    (&(game).world).wrap_x,
                )?;
                let mut dy: i64 = crate::strategy::grid::axis_delta(
                    ((*(target.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                    ((*(origin.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                    (&(game).world).height,
                    (&(game).world).wrap_y,
                )?;
                let mut destination: Option<crate::openciv3::world::Tile> =
                    crate::openciv3::world::WorldMap__tile_at(
                        &(game).world,
                        (((*(target.clone()).as_ref().ok_or("expected a value")?).clone()).x)
                            .checked_add(dx)
                            .ok_or("integer overflow")?,
                        (((*(target.clone()).as_ref().ok_or("expected a value")?).clone()).y)
                            .checked_add(dy)
                            .ok_or("integer overflow")?,
                    )?;
                if ((crate::openciv3::unit_movement::move_unit(
                    &game,
                    &defender,
                    &destination,
                    &({
                        let mut __result = std::collections::BTreeSet::new();
                        for __item in vec![].into_iter() {
                            __result.insert(__item);
                        }
                        __result
                    }),
                    None,
                    &None,
                )?)
                .status
                .clone()
                    == crate::openciv3::unit_movement::MoveStatus::MOVED)
                {
                    return Ok(CombatResult {
                        outcome: CombatOutcome::DEFENDER_RETREATED,
                        rounds: rounds,
                        bombarder: fired,
                        bombard_hit: hit,
                        protection_wars: wars,
                        promotion: None,
                        removal: None,
                        captured_unit: None,
                        golden_age_started: None,
                    });
                }
            }
            defender.hit_points = ((defender).hit_points)
                .checked_sub(1i64)
                .ok_or("integer overflow")?;
            if ((defender).hit_points <= 0i64) {
                outcome = CombatOutcome::DEFENDER_KILLED;
                (dead, survivor) = (defender, attacker);
                break;
            }
        } else {
            if (((attacker).hit_points == 1i64)
                && (rt::random_random(&rng) < retreat_chance(&game, &attacker, &defender)?))
            {
                return Ok(CombatResult {
                    outcome: CombatOutcome::ATTACKER_RETREATED,
                    rounds: rounds,
                    bombarder: fired,
                    bombard_hit: hit,
                    protection_wars: wars,
                    promotion: None,
                    removal: None,
                    captured_unit: None,
                    golden_age_started: None,
                });
            }
            attacker.hit_points = ((attacker).hit_points)
                .checked_sub(1i64)
                .ok_or("integer overflow")?;
            if ((attacker).hit_points <= 0i64) {
                outcome = CombatOutcome::ATTACKER_KILLED;
                (dead, survivor) = (attacker, defender);
                break;
            }
        }
    }
    let mut promotion: Option<Promotion> = roll_promotion(&game, &survivor, &dead, rng.clone())?;
    let mut scoring: Option<crate::openciv3::scenario_model::VictoryPointRules> =
        crate::openciv3::scenario_model::ScenarioDefinition__victory_point_rules(&(game).scenario)?;
    if ((scoring).is_some() && (((survivor).owner) != 0 && !((game).game_over))) {
        {
            let __index = rt::index(game.players.len(), (survivor).owner)?;
            game.players
                .get_mut(__index)
                .ok_or("missing record")?
                .victory_points = (({
                let __source = &(game).players;
                let __key = (survivor).owner;
                &__source[rt::index(__source.len(), __key)?]
            })
            .victory_points)
                .checked_add(rt::int_floor_div(
                    (((*(scoring).as_ref().ok_or("expected a value")?).clone()).unit)
                        .checked_mul(
                            (0i64).max(
                                ({
                                    let __source = &(&(&(game).scenario).rules).units;
                                    let __key = (dead).prototype;
                                    &__source[rt::index(__source.len(), __key)?]
                                })
                                .shield_cost,
                            ),
                        )
                        .ok_or("integer overflow")?,
                    10i64,
                )?)
                .ok_or("integer overflow")?;
        }
    }
    rules = (&(game).scenario).rules.clone();
    let mut player: crate::openciv3::players::Player = rt::at(&(game).players, (survivor).owner)?;
    let mut age_started: Option<i64> = None;
    if (!((game).game_over)
        && (!(crate::openciv3::players::Player__barbarian(&player)?)
            && (!(crate::openciv3::players::Player__barbarian({
                let __source = &(game).players;
                let __key = (dead).owner;
                &__source[rt::index(__source.len(), __key)?]
            })?) && ((&(player).golden_age_turns).is_none()
                && ((({
                    let __source = &(rules).units;
                    let __key = (survivor).prototype;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .abilities
                    & 32768i64)
                    != 0
                    && (!((rules).global_rules.clone()).is_empty()
                        && (({
                            let __source = &(rules).global_rules;
                            let __key = 0i64;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .golden_age_duration
                            > 0i64)))))))
    {
        player.golden_age_turns = Some(
            ({
                let __source = &(rules).global_rules;
                let __key = 0i64;
                &__source[rt::index(__source.len(), __key)?]
            })
            .golden_age_duration,
        );
        age_started = Some((survivor).owner);
    }
    let mut captured: Option<i64> =
        _capture_defeated_unit(game.clone(), &survivor, &dead, rng.clone())?;
    let mut removal: crate::openciv3::unit_lifecycle::RemovalResult =
        crate::openciv3::unit_lifecycle::remove_unit(&game, &dead)?;
    Ok(CombatResult {
        outcome: outcome,
        rounds: rounds,
        bombarder: fired,
        bombard_hit: hit,
        promotion: promotion,
        removal: Some(removal),
        protection_wars: wars,
        captured_unit: captured,
        golden_age_started: age_started,
    })
}
