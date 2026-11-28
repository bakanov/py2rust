use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum MoveStatus {
    MOVED,
    EXHAUSTED,
    BLOCKED,
    INTERACTION,
    COMBAT,
    KILLED,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct AttackCue {
    pub(crate) unit: i64,
    pub(crate) origin: (i64, i64),
    pub(crate) target: (i64, i64),
    pub(crate) defender: i64,
}

#[derive(Clone, PartialEq)]
pub(crate) struct MoveResult {
    pub(crate) status: MoveStatus,
    pub(crate) intent: crate::openciv3::unit_entry::EntryIntent,
    pub(crate) cost: f64,
    pub(crate) camp_gold: i64,
    pub(crate) contacts: Vec<i64>,
    pub(crate) combat: Option<crate::openciv3::combat::CombatResult>,
    pub(crate) city_destroyed: Option<crate::openciv3::city_lifecycle::CityDestruction>,
    pub(crate) raid: Option<crate::openciv3::city_lifecycle::CityRaid>,
    pub(crate) attack_cue: Option<AttackCue>,
    pub(crate) camp_cleared: bool,
    pub(crate) protection_wars: Vec<crate::openciv3::diplomacy_actions::WarDeclaration>,
}

#[derive(Clone, PartialEq)]
pub(crate) struct PathProgress {
    pub(crate) remaining: crate::openciv3::pathfinding::UnitPath,
    pub(crate) moves: Vec<MoveResult>,
    pub(crate) stopped: Option<MoveResult>,
    pub(crate) cancelled: bool,
}

// Python: openciv3/unit_movement.py:58
pub(crate) fn _discover_neighbors(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    tile: &crate::openciv3::world::Tile,
) -> rt::Result<Vec<i64>> {
    let mut owner: crate::openciv3::players::Player = rt::at(&(game).players, (unit).owner)?;
    if (crate::openciv3::players::Player__barbarian(&owner)?
        || ((owner).defeated || !((owner).included)))
    {
        return Ok(vec![]);
    }
    let mut discovered: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
    let mut cities: indexmap::IndexMap<i64, crate::openciv3::cities::City> = {
        let mut __comprehension_result_678: indexmap::IndexMap<i64, crate::openciv3::cities::City> =
            indexmap::IndexMap::new();
        let __comprehension_source_677 = ((game).cities.clone());
        for city in __comprehension_source_677.iter().cloned() {
            {
                let (__key, __value) = ((city).id, city.clone());
                __comprehension_result_678.insert(__key, __value);
            }
        }
        __comprehension_result_678
    };
    for mut neighbor in crate::openciv3::world::WorldMap__neighbors(&(game).world, tile)? {
        let mut point: (i64, i64) = ((neighbor).x, (neighbor).y);
        let mut others: Vec<i64> = {
            let mut __comprehension_result_680: Vec<i64> = Vec::new();
            let __comprehension_source_679 = ((game).units.clone());
            for other in __comprehension_source_679.iter().cloned() {
                if (((other).x, (other).y) == point.clone()) {
                    __comprehension_result_680.push((other).owner);
                }
            }
            __comprehension_result_680
        };
        let mut claim: Option<i64> = ((game).ownership.clone()).get(&(point)).cloned();
        if (claim).is_some() {
            {
                others.push(
                    ((cities)
                        .get(&((*(claim).as_ref().ok_or("expected a value")?).clone()))
                        .ok_or("missing dict key")?)
                    .owner,
                );
            };
        }
        for mut other_id in others {
            let mut other: crate::openciv3::players::Player = rt::at(&(game).players, other_id)?;
            if ((other_id == (unit).owner)
                || (crate::openciv3::players::Player__barbarian(&other)?
                    || ((other).defeated || !((other).included))))
            {
                continue;
            }
            if {
                let __needle = other_id;
                let __container = &(owner).contacts;
                !__container.contains(&__needle)
            } {
                {
                    discovered.insert(other_id);
                };
            }
            crate::openciv3::diplomacy_actions::establish_contact(
                (*game).clone(),
                (unit).owner,
                other_id,
            )?;
        }
    }
    Ok(({
        let mut __sorted = (discovered).into_iter().collect::<Vec<_>>();
        __sorted.sort();
        __sorted
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>())
}

/// Execute an adjacent step, resolving combat when an RNG is supplied.
///
/// Without an RNG, hostile entry returns an interaction without mutation.
/// Declaring war remains a separate explicit operation.
/// Route planning can speculate through fog; execution must respect actual terrain
/// and occupants. Rejected steps never charge movement or mutate positions.
// Python: openciv3/unit_movement.py:80
pub(crate) fn move_unit(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    destination: &Option<crate::openciv3::world::Tile>,
    passage: &std::collections::BTreeSet<i64>,
    mut camp_gold: Option<i64>,
    rng: &Option<rt::Random>,
) -> rt::Result<MoveResult> {
    if !(({
        let mut __comprehension_result_682: Vec<bool> = Vec::new();
        let __comprehension_source_681 = ((game).units.clone());
        for other in __comprehension_source_681.iter().cloned() {
            __comprehension_result_682.push(((other).id == (unit).id));
        }
        __comprehension_result_682
    })
    .into_iter()
    .any(|__value| __value))
    {
        return Err("Unit is not in this game".to_string().into());
    }
    if (camp_gold).is_none() {
        let mut rules: Vec<crate::openciv3::global_rules::GlobalRules> =
            (&(&(game).scenario).rules).global_rules.clone();
        camp_gold = (if (((rules).len() as i64) != 0i64) {
            Some(
                ({
                    let __source = &rules;
                    let __key = 0i64;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .barbarian_camp_gold,
            )
        } else {
            Some(25i64)
        });
    }
    if ((*(camp_gold.clone()).as_ref().ok_or("expected a value")?).clone() < 0i64) {
        return Err("Camp reward cannot be negative".to_string().into());
    }
    let mut source: Option<crate::openciv3::world::Tile> =
        crate::openciv3::world::WorldMap__tile_at(&(game).world, (unit).x, (unit).y)?;
    if (source).is_none() {
        return Err("Unit is outside the map".to_string().into());
    }
    if ((destination).is_none()
        || match ((*destination).clone()) {
            Some(__value) => {
                let __needle = __value;
                let __container = &(crate::openciv3::world::WorldMap__neighbors(
                    &(game).world,
                    &((*(source.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?);
                !__container.contains(&__needle)
            }
            None => true,
        })
    {
        return Ok(MoveResult {
            status: MoveStatus::BLOCKED,
            intent: crate::openciv3::unit_entry::EntryIntent::DISABLED,
            cost: 0.0f64,
            camp_gold: 0i64,
            contacts: vec![],
            combat: None,
            city_destroyed: None,
            raid: None,
            attack_cue: None,
            camp_cleared: false,
            protection_wars: vec![],
        });
    }
    if ((unit).movement_remaining <= 0.0001f64) {
        return Ok(MoveResult {
            status: MoveStatus::EXHAUSTED,
            intent: crate::openciv3::unit_entry::EntryIntent::DISABLED,
            cost: 0.0f64,
            camp_gold: 0i64,
            contacts: vec![],
            combat: None,
            city_destroyed: None,
            raid: None,
            attack_cue: None,
            camp_cleared: false,
            protection_wars: vec![],
        });
    }
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    if (((kind).domain == 1i64)
        && crate::openciv3::hydrology::land_strip(
            &(game).world,
            &((*(source.clone()).as_ref().ok_or("expected a value")?).clone()),
            &((*((*destination).clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone()),
        )?)
    {
        return Ok(MoveResult {
            status: MoveStatus::BLOCKED,
            intent: crate::openciv3::unit_entry::EntryIntent::DISABLED,
            cost: 0.0f64,
            camp_gold: 0i64,
            contacts: vec![],
            combat: None,
            city_destroyed: None,
            raid: None,
            attack_cue: None,
            camp_cleared: false,
            protection_wars: vec![],
        });
    }
    let mut intent: crate::openciv3::unit_entry::EntryIntent = {
        let __call_683_0 = game;
        let __call_683_1 = unit;
        let __call_683_2 = destination;
        let __call_683_3 = false;
        crate::openciv3::unit_entry::resolve_entry(
            __call_683_0,
            __call_683_1,
            __call_683_2,
            __call_683_3,
        )
    }?;
    if ((intent.clone() == crate::openciv3::unit_entry::EntryIntent::FIGHT) && (rng).is_some()) {
        return _combat_move(
            (*game).clone(),
            (*unit).clone(),
            &((*(source).as_ref().ok_or("expected a value")?).clone()),
            &((*((*destination).clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone()),
            (*((*rng).clone()).as_ref().ok_or("expected a value")?).clone(),
            passage,
            (*(camp_gold).as_ref().ok_or("expected a value")?).clone(),
        );
    }
    if !(crate::openciv3::unit_entry::EntryIntent__peaceful(intent.clone())?) {
        let mut status: MoveStatus =
            (if (intent.clone() == crate::openciv3::unit_entry::EntryIntent::DISABLED) {
                MoveStatus::BLOCKED
            } else {
                MoveStatus::INTERACTION
            });
        return Ok(MoveResult {
            status: status,
            intent: intent,
            cost: 0.0f64,
            camp_gold: 0i64,
            contacts: vec![],
            combat: None,
            city_destroyed: None,
            raid: None,
            attack_cue: None,
            camp_cleared: false,
            protection_wars: vec![],
        });
    }
    let mut cost: f64 = {
        let __call_684_0 = game;
        let __call_684_1 = (unit).owner;
        let __call_684_2 = &((*(source).as_ref().ok_or("expected a value")?).clone());
        let __call_684_3 = &((*((*destination).clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone());
        let __call_684_4 = passage;
        let __call_684_5 = &(Some((unit).prototype));
        let __call_684_6 = false;
        crate::openciv3::pathfinding::movement_cost(
            __call_684_0,
            __call_684_1,
            __call_684_2,
            __call_684_3,
            __call_684_4,
            __call_684_5,
            __call_684_6,
        )
    }?;
    if (cost < ((0i64) as f64)) {
        return Err("Negative movement cost".to_string().into());
    }
    _enter_tile(
        (*game).clone(),
        (*unit).clone(),
        (*((*destination).clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone(),
        intent,
        cost,
        (*(camp_gold).as_ref().ok_or("expected a value")?).clone(),
    )
}

// Python: openciv3/unit_movement.py:120
pub(crate) fn _enter_tile(
    mut game: crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
    mut destination: crate::openciv3::world::Tile,
    mut intent: crate::openciv3::unit_entry::EntryIntent,
    mut cost: f64,
    mut camp_gold: i64,
) -> rt::Result<MoveResult> {
    let mut kind: crate::openciv3::unit_rules::UnitPrototype =
        rt::at(&(&(&(game).scenario).rules).units, (unit).prototype)?;
    let mut passengers: Vec<crate::openciv3::units::Unit> =
        crate::openciv3::unit_entry::transported_units(&game, &unit)?;
    if (!(passengers.clone()).is_empty()
        && (((kind).capacity <= 0i64)
            || (!(((kind).orders & 256i64) != 0i64)
                || ({
                    let mut __comprehension_result_686: Vec<bool> = Vec::new();
                    let __comprehension_source_685 = (passengers.clone());
                    for other in __comprehension_source_685.iter().cloned() {
                        __comprehension_result_686
                            .push((((other).x, (other).y) != ((unit).x, (unit).y)));
                    }
                    __comprehension_result_686
                })
                .into_iter()
                .any(|__value| __value))))
    {
        return Err("Invalid transport passengers".to_string().into());
    }
    let mut transport_id: Option<i64> = (unit).transported_by.clone();
    if (intent.clone() == crate::openciv3::unit_entry::EntryIntent::LOAD) {
        crate::openciv3::unit_missions::clear_unit_missions(game.clone(), unit.clone())?;
        transport_id = Some(
            (rt::at(
                &(crate::openciv3::unit_entry::transports_to_board(&game, &unit, &destination)?),
                0i64,
            )?)
            .id,
        );
    } else {
        if !(crate::openciv3::hydrology::is_water(&destination)?) {
            transport_id = None;
        }
    }
    for mut moved in {
        let mut __left: Vec<crate::openciv3::units::Unit> = vec![unit.clone()];
        let __right: Vec<crate::openciv3::units::Unit> = passengers;
        __left.extend(__right);
        __left
    } {
        let mut tuple_fields_134_8: (i64, i64) = ((moved).x, (moved).y);
        moved.previous_x = (tuple_fields_134_8).0.clone();
        moved.previous_y = (tuple_fields_134_8).1.clone();
        let mut tuple_fields_135_8: (i64, i64) = ((destination).x, (destination).y);
        moved.x = (tuple_fields_135_8).0.clone();
        moved.y = (tuple_fields_135_8).1.clone();
    }
    unit.worker_job = None;
    unit.worker_progress = 0.0f64;
    unit.fortified = (transport_id).is_some();
    unit.facing_override = None;
    unit.transported_by = transport_id;
    unit.movement_remaining = (0.0f64).max(rt::finite((unit).movement_remaining - cost)?);
    let mut reward: i64 = 0i64;
    let mut camp_cleared: bool = (((destination).overlays & 128i64) != 0 && ((unit).owner != 0i64));
    if camp_cleared {
        reward = camp_gold;
        {
            let __index = rt::index(game.players.len(), (unit).owner)?;
            game.players.get_mut(__index).ok_or("missing record")?.gold = (({
                let __source = &(game).players;
                let __key = (unit).owner;
                &__source[rt::index(__source.len(), __key)?]
            })
            .gold)
                .checked_add(reward)
                .ok_or("integer overflow")?;
        }
        let mut cleared: crate::openciv3::world::Tile = {
            let mut __replacement = (destination.clone()).clone();
            __replacement.overlays = ((destination).overlays & !(128i64));
            __replacement
        };
        game.world = {
            let mut __replacement = ((game).world.clone()).clone();
            __replacement.tiles = ({
                let mut __comprehension_result_688: Vec<crate::openciv3::world::Tile> = Vec::new();
                let __comprehension_source_687 = ((&(game).world).tiles.clone());
                for tile in __comprehension_source_687.iter().cloned() {
                    __comprehension_result_688.push(
                        (if (tile.clone() == destination.clone()) {
                            cleared.clone()
                        } else {
                            tile.clone()
                        }),
                    );
                }
                __comprehension_result_688
            })
            .iter()
            .cloned()
            .collect::<Vec<_>>();
            __replacement
        };
        game.scenario.world = Some((game).world.clone());
        destination = cleared.clone();
        for mut knowledge in ((game).visibility.clone())
            .values()
            .cloned()
            .collect::<Vec<_>>()
        {
            let mut point: (i64, i64) = ((cleared).x, (cleared).y);
            if {
                let __needle = point.clone();
                let __container = &(knowledge).known_overlays;
                __container.contains_key(&__needle)
            } {
                knowledge.known_overlays.insert(
                    point.clone(),
                    ((&(knowledge).known_overlays)
                        .get(&(point.clone()))
                        .ok_or("missing dict key")?
                        .clone()
                        & !(128i64)),
                );
            }
        }
    }
    let mut contacts: Vec<i64> = _discover_neighbors(&game, &unit, &destination)?;
    game.visibility = {
        let __call_689_0 = &(game).world;
        let __call_689_1 = &(game).cities;
        let __call_689_2 = &(game).units;
        let __call_689_3 = &(&(game).scenario).rules;
        let __call_689_4 = &(game).ownership;
        let __call_689_5 = (game).visibility.clone();
        let __call_689_6 = &(Some((unit).owner));
        let __call_689_default_6 = None;
        crate::openciv3::visibility::update_visibility(
            __call_689_0,
            __call_689_1,
            __call_689_2,
            __call_689_3,
            __call_689_4,
            __call_689_5,
            __call_689_default_6,
            __call_689_6,
        )
    }?;
    Ok(MoveResult {
        status: MoveStatus::MOVED,
        intent: intent,
        cost: cost,
        camp_gold: reward,
        contacts: contacts,
        camp_cleared: camp_cleared,
        combat: None,
        city_destroyed: None,
        raid: None,
        attack_cue: None,
        protection_wars: vec![],
    })
}

// Python: openciv3/unit_movement.py:163
pub(crate) fn _combat_move(
    mut game: crate::openciv3::game_state::GameState,
    mut unit: crate::openciv3::units::Unit,
    source: &crate::openciv3::world::Tile,
    destination: &crate::openciv3::world::Tile,
    mut rng: rt::Random,
    passage: &std::collections::BTreeSet<i64>,
    mut camp_gold: i64,
) -> rt::Result<MoveResult> {
    let mut defender: Option<crate::openciv3::units::Unit> =
        crate::openciv3::combat_strength::top_defender(&game, &unit, destination, &None)?;
    let mut city: Option<crate::openciv3::cities::City> = {
        let __find_source_690 = (game).cities.clone();
        let mut __find_result_690: Option<crate::openciv3::cities::City> = None;
        for city in __find_source_690.iter().cloned() {
            if ((((city).x, (city).y) == ((destination).x, (destination).y))
                && crate::openciv3::diplomacy::Diplomacy__at_war(
                    &(game).diplomacy,
                    (unit).owner,
                    (city).owner,
                )?)
            {
                __find_result_690 = Some(city.clone());
                break;
            }
        }
        __find_result_690
    };
    let mut battle: Option<crate::openciv3::combat::CombatResult> = None;
    let mut cue: Option<AttackCue> = None;
    let mut combat_cost: f64 = 0.0f64;
    if ((defender).is_some()
        && crate::openciv3::diplomacy::Diplomacy__at_war(
            &(game).diplomacy,
            (unit).owner,
            ((*(defender.clone()).as_ref().ok_or("expected a value")?).clone()).owner,
        )?)
    {
        if (({
            let __source = &(&(&(game).scenario).rules).units;
            let __key = (unit).prototype;
            &__source[rt::index(__source.len(), __key)?]
        })
        .attack
            <= 0i64)
        {
            return Ok(MoveResult {
                status: MoveStatus::BLOCKED,
                intent: crate::openciv3::unit_entry::EntryIntent::FIGHT,
                cost: 0.0f64,
                camp_gold: 0i64,
                contacts: vec![],
                combat: None,
                city_destroyed: None,
                raid: None,
                attack_cue: None,
                camp_cleared: false,
                protection_wars: vec![],
            });
        }
        unit.fortified = false;
        battle = Some({
            let __call_691_0 = game.clone();
            let __call_691_1 = unit.clone();
            let __call_691_2 = (*(defender.clone()).as_ref().ok_or("expected a value")?).clone();
            let __call_691_3 = rng.clone();
            crate::openciv3::combat::fight(__call_691_0, __call_691_1, __call_691_2, __call_691_3)
        }?);
        cue = Some(AttackCue {
            unit: (unit).id,
            origin: ((source).x, (source).y),
            target: ((destination).x, (destination).y),
            defender: ((*(defender.clone()).as_ref().ok_or("expected a value")?).clone()).id,
        });
        if (((*(battle.clone()).as_ref().ok_or("expected a value")?).clone())
            .outcome
            .clone()
            == crate::openciv3::combat::CombatOutcome::ATTACKER_KILLED)
        {
            return Ok(MoveResult {
                status: MoveStatus::KILLED,
                intent: crate::openciv3::unit_entry::EntryIntent::FIGHT,
                combat: battle,
                attack_cue: cue,
                cost: 0.0f64,
                camp_gold: 0i64,
                contacts: vec![],
                city_destroyed: None,
                raid: None,
                camp_cleared: false,
                protection_wars: vec![],
            });
        }
        if (((*(battle.clone()).as_ref().ok_or("expected a value")?).clone())
            .outcome
            .clone()
            == crate::openciv3::combat::CombatOutcome::IMPOSSIBLE)
        {
            return Ok(MoveResult {
                status: MoveStatus::BLOCKED,
                intent: crate::openciv3::unit_entry::EntryIntent::FIGHT,
                combat: battle,
                cost: 0.0f64,
                camp_gold: 0i64,
                contacts: vec![],
                city_destroyed: None,
                raid: None,
                attack_cue: None,
                camp_cleared: false,
                protection_wars: vec![],
            });
        }
        combat_cost = 1.0f64;
        unit.movement_remaining =
            (0.0f64).max(rt::finite((unit).movement_remaining - combat_cost)?);
        if ((((*(battle.clone()).as_ref().ok_or("expected a value")?).clone())
            .outcome
            .clone()
            == crate::openciv3::combat::CombatOutcome::ATTACKER_RETREATED)
            || (crate::openciv3::combat_strength::top_defender(&game, &unit, destination, &None)?)
                .is_some())
        {
            unit.facing_override = Some(crate::openciv3::unit_animation::facing_toward(
                &(game).world,
                &(((*(cue.clone()).as_ref().ok_or("expected a value")?).clone())
                    .target
                    .clone()),
                &(((*(cue.clone()).as_ref().ok_or("expected a value")?).clone())
                    .origin
                    .clone()),
                false,
            )?);
            return Ok(MoveResult {
                status: MoveStatus::COMBAT,
                intent: crate::openciv3::unit_entry::EntryIntent::FIGHT,
                cost: combat_cost,
                combat: battle,
                attack_cue: cue,
                camp_gold: 0i64,
                contacts: vec![],
                city_destroyed: None,
                raid: None,
                camp_cleared: false,
                protection_wars: vec![],
            });
        }
    }
    let mut cost: f64 = {
        let __call_692_0 = &game;
        let __call_692_1 = (unit).owner;
        let __call_692_2 = source;
        let __call_692_3 = destination;
        let __call_692_4 = passage;
        let __call_692_5 = &(Some((unit).prototype));
        let __call_692_6 = false;
        crate::openciv3::pathfinding::movement_cost(
            __call_692_0,
            __call_692_1,
            __call_692_2,
            __call_692_3,
            __call_692_4,
            __call_692_5,
            __call_692_6,
        )
    }?;
    let mut result: MoveResult = _enter_tile(
        game.clone(),
        unit.clone(),
        (*destination).clone(),
        crate::openciv3::unit_entry::EntryIntent::FIGHT,
        cost,
        camp_gold,
    )?;
    let mut destroyed: Option<crate::openciv3::city_lifecycle::CityDestruction> = None;
    let mut raid: Option<crate::openciv3::city_lifecycle::CityRaid> = None;
    let mut wars: Vec<crate::openciv3::diplomacy_actions::WarDeclaration> = vec![];
    if ((city).is_some()
        && ({
            let mut __comprehension_result_694: Vec<bool> = Vec::new();
            let __comprehension_source_693 = ((game).cities.clone());
            for other in __comprehension_source_693.iter().cloned() {
                __comprehension_result_694.push(
                    ((other).id
                        == ((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).id),
                );
            }
            __comprehension_result_694
        })
        .into_iter()
        .any(|__value| __value))
    {
        if ((unit).owner == 0i64) {
            raid = Some(crate::openciv3::city_lifecycle::ransack_city(
                &game,
                &unit,
                &((*(city).as_ref().ok_or("expected a value")?).clone()),
            )?);
        } else {
            if ((battle).is_none()
                || ((defender).is_none()
                    || (((*(defender.clone()).as_ref().ok_or("expected a value")?).clone()).owner
                        != ((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).owner)))
            {
                wars = {
                    let __call_695_0 = &game;
                    let __call_695_1 = (unit).owner;
                    let __call_695_2 =
                        ((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).owner;
                    let __call_695_3 = &((
                        ((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                        ((*(city.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                    ));
                    let __call_695_4 = rng.clone();
                    crate::openciv3::diplomacy_actions::honor_mutual_protection(
                        __call_695_0,
                        __call_695_1,
                        __call_695_2,
                        __call_695_3,
                        __call_695_4,
                    )
                }?;
            }
            let mut scoring: Option<crate::openciv3::scenario_model::VictoryPointRules> =
                crate::openciv3::scenario_model::ScenarioDefinition__victory_point_rules(
                    &(game).scenario,
                )?;
            if ((scoring).is_some() && !((game).game_over)) {
                {
                    let __index = rt::index(game.players.len(), (unit).owner)?;
                    game.players
                        .get_mut(__index)
                        .ok_or("missing record")?
                        .victory_points = (({
                        let __source = &(game).players;
                        let __key = (unit).owner;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .victory_points)
                        .checked_add(
                            (((*(scoring).as_ref().ok_or("expected a value")?).clone()).city)
                                .checked_mul(crate::openciv3::cities::City__size(
                                    &((*(city.clone()).as_ref().ok_or("expected a value")?)
                                        .clone()),
                                )?)
                                .ok_or("integer overflow")?,
                        )
                        .ok_or("integer overflow")?;
                }
            }
            destroyed = Some({
                let __call_696_0 = &game;
                let __call_696_1 = &((*(city).as_ref().ok_or("expected a value")?).clone());
                let __call_696_2 = true;
                crate::openciv3::city_lifecycle::destroy_city(
                    __call_696_0,
                    __call_696_1,
                    __call_696_2,
                )
            }?);
        }
    }
    Ok({
        let mut __replacement = (result).clone();
        __replacement.status = (if (raid).is_some() {
            MoveStatus::KILLED
        } else {
            MoveStatus::MOVED
        });
        __replacement.cost = rt::finite(cost + combat_cost)?;
        __replacement.combat = battle;
        __replacement.city_destroyed = destroyed;
        __replacement.raid = raid.clone();
        __replacement.attack_cue = cue;
        __replacement.protection_wars = wars;
        __replacement
    })
}

/// Run available steps, preserving a blocked or exhausted step for the caller.
// Python: openciv3/unit_movement.py:221
pub(crate) fn follow_path(
    game: &crate::openciv3::game_state::GameState,
    unit: &crate::openciv3::units::Unit,
    path: &crate::openciv3::pathfinding::UnitPath,
    passage: &std::collections::BTreeSet<i64>,
    camp_gold: &Option<i64>,
    rng: &Option<rt::Random>,
) -> rt::Result<PathProgress> {
    let mut moves: Vec<MoveResult> = vec![];
    if !((path).reachable) {
        return Ok(PathProgress {
            remaining: (*path).clone(),
            moves: vec![],
            stopped: Some(MoveResult {
                status: MoveStatus::BLOCKED,
                intent: crate::openciv3::unit_entry::EntryIntent::DISABLED,
                cost: 0.0f64,
                camp_gold: 0i64,
                contacts: vec![],
                combat: None,
                city_destroyed: None,
                raid: None,
                attack_cue: None,
                camp_cleared: false,
                protection_wars: vec![],
            }),
            cancelled: false,
        });
    }
    for mut for_target_228_4 in ((path).steps.clone())
        .into_iter()
        .enumerate()
        .map(|(__index, __value)| (__index as i64 + 0i64, __value))
        .collect::<Vec<_>>()
    {
        let (mut index, mut point): (i64, (i64, i64)) = for_target_228_4;
        let mut result: MoveResult = {
            let __call_697_0 = &((*game).clone());
            let __call_697_1 = &((*unit).clone());
            let __call_697_2 = &({
                let __star_args_698: Vec<i64> = {
                    let __tuple_value = &(point.clone());
                    vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                };
                if !(2..=2).contains(&__star_args_698.len()) {
                    return Err("wrong function argument count".into());
                }
                crate::openciv3::world::WorldMap__tile_at(
                    &(game).world,
                    rt::at(&__star_args_698, 0 as i64)?,
                    rt::at(&__star_args_698, 1 as i64)?,
                )?
            });
            let __call_697_3 = passage;
            let __call_697_4 = (*camp_gold).clone();
            let __call_697_5 = rng;
            move_unit(
                __call_697_0,
                __call_697_1,
                __call_697_2,
                __call_697_3,
                __call_697_4,
                __call_697_5,
            )
        }?;
        if ((&(result).combat).is_some() || (&(result).raid).is_some()) {
            if ((result).status.clone() == MoveStatus::MOVED) {
                {
                    moves.push(result.clone());
                };
            }
            return Ok(PathProgress {
                remaining: crate::openciv3::pathfinding::UnitPath {
                    destination: (path).destination.clone(),
                    steps: vec![],
                    reachable: false,
                    cost: 0.0f64,
                },
                moves: (moves).iter().cloned().collect::<Vec<_>>(),
                stopped: Some(result),
                cancelled: true,
            });
        }
        if ((result).status.clone() != MoveStatus::MOVED) {
            return Ok(PathProgress {
                remaining: crate::openciv3::pathfinding::UnitPath {
                    destination: (path).destination.clone(),
                    steps: rt::list_slice(&(path).steps, index, i64::MAX),
                    reachable: true,
                    cost: 0.0f64,
                },
                moves: (moves).iter().cloned().collect::<Vec<_>>(),
                stopped: Some(result),
                cancelled: false,
            });
        }
        {
            moves.push(result.clone());
        };
        if (((result).intent.clone() == crate::openciv3::unit_entry::EntryIntent::LOAD)
            && ((index).checked_add(1i64).ok_or("integer overflow")?
                < ((&(path).steps).len() as i64)))
        {
            return Ok(PathProgress {
                remaining: crate::openciv3::pathfinding::UnitPath {
                    destination: (path).destination.clone(),
                    steps: vec![],
                    reachable: false,
                    cost: 0.0f64,
                },
                moves: (moves).iter().cloned().collect::<Vec<_>>(),
                stopped: None,
                cancelled: true,
            });
        }
    }
    Ok(PathProgress {
        remaining: crate::openciv3::pathfinding::UnitPath {
            destination: (path).destination.clone(),
            steps: vec![],
            reachable: true,
            cost: 0.0f64,
        },
        moves: (moves).iter().cloned().collect::<Vec<_>>(),
        stopped: None,
        cancelled: false,
    })
}
