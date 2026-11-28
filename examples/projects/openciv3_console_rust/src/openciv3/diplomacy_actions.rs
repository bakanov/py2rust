use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct WarDeclaration {
    pub(crate) aggressor: i64,
    pub(crate) defender: i64,
    pub(crate) sneak_attack: bool,
    pub(crate) broke_passage: bool,
    pub(crate) refuse_contact_until_turn: i64,
}

// Python: openciv3/diplomacy_actions.py:10
pub(crate) fn _validate_pair(
    game: &crate::openciv3::game_state::GameState,
    mut left: i64,
    mut right: i64,
) -> rt::Result<()> {
    if ((left == right)
        || (!({
            let __compare_0 = 0i64;
            let __compare_1 = left;
            if (__compare_0 < __compare_1) {
                let __compare_2 = ((&(game).players).len() as i64);
                (__compare_1 < __compare_2)
            } else {
                false
            }
        }) || !({
            let __compare_0 = 0i64;
            let __compare_1 = right;
            if (__compare_0 < __compare_1) {
                let __compare_2 = ((&(game).players).len() as i64);
                (__compare_1 < __compare_2)
            } else {
                false
            }
        })))
    {
        return Err("Diplomacy requires two distinct nonbarbarian civilizations"
            .to_string()
            .into());
    }
    if ({
        let mut __comprehension_result_669: Vec<bool> = Vec::new();
        let __comprehension_source_668 = ({
            let __tuple_value = &((left, right));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        for index in __comprehension_source_668.iter().cloned() {
            __comprehension_result_669.push(
                (({
                    let __source = &(game).players;
                    let __key = index;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .defeated
                    || !(({
                        let __source = &(game).players;
                        let __key = index;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .included)),
            );
        }
        __comprehension_result_669
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("Diplomacy requires active civilizations".to_string().into());
    }
    Ok(())
}

// Python: openciv3/diplomacy_actions.py:17
pub(crate) fn establish_contact(
    mut game: crate::openciv3::game_state::GameState,
    mut left: i64,
    mut right: i64,
) -> rt::Result<()> {
    _validate_pair(&game, left, right)?;
    let mut diplomacy: crate::openciv3::diplomacy::Diplomacy = (game).diplomacy.clone();
    let mut at_war: bool =
        (crate::openciv3::diplomacy::Diplomacy__at_war(&diplomacy, left, right)?
            || (crate::openciv3::diplomacy::Diplomacy__at_war(&diplomacy, right, left)?
                || crate::openciv3::diplomacy::Diplomacy__locked_war(&diplomacy, left, right)?));
    for mut for_target_21_4 in {
        let __tuple_items = ((left, right), (right, left));
        [__tuple_items.0, __tuple_items.1]
    } {
        let (mut first, mut second): (i64, i64) = for_target_21_4;
        (({
            let __source = &(game).players;
            let __key = first;
            &__source[rt::index(__source.len(), __key)?]
        })
        .contacts
        .clone())
        .insert(second);
        if {
            let __needle = (first, second);
            let __container = &(diplomacy).relationships;
            !__container.contains_key(&__needle)
        } {
            diplomacy.relationships.insert((first, second,), crate::openciv3::diplomacy::Relationship { at_war: at_war, deals: (if at_war { vec![] } else { vec![crate::openciv3::recurring_deals::RecurringDeal____post_init__(&(crate::openciv3::recurring_deals::RecurringDeal { deal_type: crate::openciv3::recurring_deals::DealType::DIPLOMATIC_AGREEMENT, kind: crate::openciv3::recurring_deals::DealKind::PEACE, direction: crate::openciv3::recurring_deals::DealDirection::EXCHANGE, duration: 0i64, gold: 0i64, resource: String::new(), start: 0i64, against: None }))?] }), mutual_protection: false, war_declaration_count: 0i64, war_declaration_with_passage_count: 0i64, was_sneak_attacked: false, refuse_contact_until_turn: (1i64).checked_neg().ok_or("integer overflow")?, right_of_passage: false });
        }
    }
    Ok(())
}

/// Apply an agreed two-way passage grant; negotiation/expiry is separate.
// Python: openciv3/diplomacy_actions.py:28
pub(crate) fn set_right_of_passage(
    mut game: crate::openciv3::game_state::GameState,
    mut left: i64,
    mut right: i64,
    mut enabled: bool,
) -> rt::Result<()> {
    _validate_pair(&game, left, right)?;
    if (enabled && crate::openciv3::diplomacy::Diplomacy__at_war(&(game).diplomacy, left, right)?) {
        return Err("Cannot grant passage while at war".to_string().into());
    }
    establish_contact(game.clone(), left, right)?;
    for mut pair in {
        let __tuple_items = ((left, right), (right, left));
        [__tuple_items.0, __tuple_items.1]
    } {
        game.diplomacy
            .relationships
            .get_mut(&pair)
            .ok_or("missing record")?
            .right_of_passage = enabled;
    }
    Ok(())
}

// Python: openciv3/diplomacy_actions.py:47
pub(crate) fn declare_war(
    mut game: crate::openciv3::game_state::GameState,
    mut aggressor: i64,
    mut defender: i64,
    mut rng: rt::Random,
) -> rt::Result<WarDeclaration> {
    _validate_pair(&game, aggressor, defender)?;
    let mut diplomacy: crate::openciv3::diplomacy::Diplomacy = (game).diplomacy.clone();
    if crate::openciv3::diplomacy::Diplomacy__locked_peace(&diplomacy, aggressor, defender)? {
        return Err("Locked allies cannot declare war on each other"
            .to_string()
            .into());
    }
    if crate::openciv3::diplomacy::Diplomacy__at_war(&diplomacy, aggressor, defender)? {
        return Err("Civilizations are already at war".to_string().into());
    }
    let mut owners: indexmap::IndexMap<i64, i64> = {
        let mut __comprehension_result_671: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_670 = ((game).cities.clone());
        for city in __comprehension_source_670.iter().cloned() {
            {
                let (__key, __value) = ((city).id, (city).owner);
                __comprehension_result_671.insert(__key, __value);
            }
        }
        __comprehension_result_671
    };
    let mut known: std::collections::BTreeSet<(i64, i64)> = ((&(game).visibility)
        .get(&(defender))
        .ok_or("missing dict key")?)
    .known
    .clone();
    let mut sneak: bool = ({
        let mut __comprehension_result_673: Vec<bool> = Vec::new();
        let __comprehension_source_672 = ((game).units.clone());
        for unit in __comprehension_source_672.iter().cloned() {
            __comprehension_result_673.push(
                (((unit).owner == aggressor)
                    && ({
                        let __needle = ((unit).x, (unit).y);
                        let __container = &known;
                        __container.contains(&__needle)
                    } && ((owners.clone())
                        .get(
                            &({
                                let __mapping = &(game).ownership;
                                let __key = ((unit).x, (unit).y);
                                let __default = (1i64).checked_neg().ok_or("integer overflow")?;
                                __mapping.get(&__key).cloned().unwrap_or(__default)
                            }),
                        )
                        .cloned()
                        == Some(defender)))),
            );
        }
        __comprehension_result_673
    })
    .into_iter()
    .any(|__value| __value);
    let mut refusal: i64 = ((game).turn)
        .checked_add(rt::random_randrange(
            &rng,
            5i64,
            (if sneak { 16i64 } else { 12i64 }),
        )?)
        .ok_or("integer overflow")?;
    establish_contact(game.clone(), aggressor, defender)?;
    let mut outgoing: crate::openciv3::diplomacy::Relationship = (&(diplomacy).relationships)
        .get(&((aggressor, defender)))
        .ok_or("missing dict key")?
        .clone();
    let mut incoming: crate::openciv3::diplomacy::Relationship = (&(diplomacy).relationships)
        .get(&((defender, aggressor)))
        .ok_or("missing dict key")?
        .clone();
    let mut broke_passage: bool = (outgoing).right_of_passage;
    incoming.war_declaration_count = ((incoming).war_declaration_count)
        .checked_add(1i64)
        .ok_or("integer overflow")?;
    incoming.war_declaration_with_passage_count = ((incoming).war_declaration_with_passage_count)
        .checked_add(((broke_passage) as i64))
        .ok_or("integer overflow")?;
    incoming.was_sneak_attacked = sneak;
    incoming.refuse_contact_until_turn = refusal;
    outgoing.refuse_contact_until_turn = rt::int_floor_div(refusal, 2i64)?;
    for mut relationship in {
        let __tuple_items = (outgoing, incoming);
        [__tuple_items.0, __tuple_items.1]
    } {
        ((relationship).deals).clear();
        relationship.at_war = true;
        relationship.mutual_protection = false;
        relationship.right_of_passage = false;
    }
    {
        let __index = rt::index(game.players.len(), aggressor)?;
        game.players
            .get_mut(__index)
            .ok_or("missing record")?
            .turns_until_priority_reevaluation = 0i64;
    }
    {
        let __index = rt::index(game.players.len(), defender)?;
        game.players
            .get_mut(__index)
            .ok_or("missing record")?
            .turns_until_priority_reevaluation = 0i64;
    }
    Ok(WarDeclaration {
        aggressor: aggressor,
        defender: defender,
        sneak_attack: sneak,
        broke_passage: broke_passage,
        refuse_contact_until_turn: refusal,
    })
}

/// Defensive pacts respond to attacks in the protected civilization's territory.
// Python: openciv3/diplomacy_actions.py:80
pub(crate) fn honor_mutual_protection(
    game: &crate::openciv3::game_state::GameState,
    mut aggressor: i64,
    mut defender: i64,
    point: &(i64, i64),
    mut rng: rt::Random,
) -> rt::Result<Vec<WarDeclaration>> {
    if ((aggressor == 0i64)
        || ((defender == 0i64)
            || !(crate::openciv3::diplomacy::Diplomacy__at_war(
                &(game).diplomacy,
                aggressor,
                defender,
            )?)))
    {
        return Ok(vec![]);
    }
    let mut claim: Option<i64> = ((game).ownership.clone()).get(&((*point).clone())).cloned();
    if !(({
        let mut __comprehension_result_675: Vec<bool> = Vec::new();
        let __comprehension_source_674 = ((game).cities.clone());
        for city in __comprehension_source_674.iter().cloned() {
            __comprehension_result_675.push(
                (((city).owner == defender)
                    && ((Some((city).id) == claim.clone())
                        || (((city).x, (city).y) == (*point).clone()))),
            );
        }
        __comprehension_result_675
    })
    .into_iter()
    .any(|__value| __value))
    {
        return Ok(vec![]);
    }
    let mut declarations: Vec<WarDeclaration> = vec![];
    for mut player in crate::openciv3::game_state::GameState__players_in_order(game)? {
        let mut ally: i64 = (player).civilization;
        if ({
            let __needle = ally;
            let __container = &({
                let __tuple_value = &((0i64, aggressor, defender));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                ]
            });
            __container.contains(&__needle)
        } || ((player).defeated || !((player).included)))
        {
            continue;
        }
        let mut pact: Option<crate::openciv3::diplomacy::Relationship> =
            ((&(game).diplomacy).relationships.clone())
                .get(&((defender, ally)))
                .cloned();
        if ((pact).is_none()
            || (!(((*(pact.clone()).as_ref().ok_or("expected a value")?).clone())
                .mutual_protection)
                || (crate::openciv3::diplomacy::Diplomacy__at_war(
                    &(game).diplomacy,
                    ally,
                    defender,
                )? || (crate::openciv3::diplomacy::Diplomacy__at_war(
                    &(game).diplomacy,
                    ally,
                    aggressor,
                )? || crate::openciv3::diplomacy::Diplomacy__locked_peace(
                    &(game).diplomacy,
                    ally,
                    aggressor,
                )?))))
        {
            continue;
        }
        {
            declarations.push({
                let __call_676_0 = (*game).clone();
                let __call_676_1 = ally;
                let __call_676_2 = aggressor;
                let __call_676_3 = rng.clone();
                declare_war(__call_676_0, __call_676_1, __call_676_2, __call_676_3)
            }?);
        };
    }
    Ok((declarations).iter().cloned().collect::<Vec<_>>())
}

// Python: openciv3/diplomacy_actions.py:102
pub(crate) fn accepts_contact(
    game: &crate::openciv3::game_state::GameState,
    mut receiver: i64,
    mut sender: i64,
) -> rt::Result<bool> {
    _validate_pair(game, receiver, sender)?;
    if crate::openciv3::diplomacy::Diplomacy__locked_war(&(game).diplomacy, receiver, sender)? {
        return Ok(false);
    }
    if !(crate::openciv3::diplomacy::Diplomacy__at_war(&(game).diplomacy, receiver, sender)?) {
        return Ok(true);
    }
    let mut relationship: Option<crate::openciv3::diplomacy::Relationship> =
        ((&(game).diplomacy).relationships.clone())
            .get(&((receiver, sender)))
            .cloned();
    Ok(((relationship).is_some()
        && ((game).turn
            >= ((*(relationship.clone()).as_ref().ok_or("expected a value")?).clone())
                .refuse_contact_until_turn)))
}

/// Apply an agreed peace; caller handles negotiation and refusal checks.
// Python: openciv3/diplomacy_actions.py:112
pub(crate) fn sign_peace(
    game: &crate::openciv3::game_state::GameState,
    mut left: i64,
    mut right: i64,
) -> rt::Result<()> {
    _validate_pair(game, left, right)?;
    if crate::openciv3::diplomacy::Diplomacy__locked_war(&(game).diplomacy, left, right)? {
        return Err("Locked enemies cannot sign peace".to_string().into());
    }
    if !(crate::openciv3::diplomacy::Diplomacy__at_war(&(game).diplomacy, left, right)?) {
        return Err("Civilizations are not at war".to_string().into());
    }
    let mut duration: i64 =
        crate::openciv3::rules::RuleCatalog__deal_duration(&(&(game).scenario).rules)?;
    let mut deal: crate::openciv3::recurring_deals::RecurringDeal =
        crate::openciv3::recurring_deals::RecurringDeal____post_init__(
            &(crate::openciv3::recurring_deals::RecurringDeal {
                deal_type: crate::openciv3::recurring_deals::DealType::DIPLOMATIC_AGREEMENT,
                kind: crate::openciv3::recurring_deals::DealKind::PEACE,
                direction: crate::openciv3::recurring_deals::DealDirection::EXCHANGE,
                duration: duration,
                start: (game).turn,
                gold: 0i64,
                resource: String::new(),
                against: None,
            }),
        )?;
    crate::openciv3::deal_lifecycle::register_deal((*game).clone(), left, right, &deal)?;
    Ok(())
}
