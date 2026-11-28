use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct Relationship {
    pub(crate) at_war: bool,
    pub(crate) mutual_protection: bool,
    pub(crate) war_declaration_count: i64,
    pub(crate) war_declaration_with_passage_count: i64,
    pub(crate) was_sneak_attacked: bool,
    pub(crate) refuse_contact_until_turn: i64,
    pub(crate) right_of_passage: bool,
    pub(crate) deals: Vec<crate::openciv3::recurring_deals::RecurringDeal>,
}

#[derive(Clone, PartialEq)]
pub(crate) struct Diplomacy {
    pub(crate) alliance_names: indexmap::IndexMap<i64, String>,
    pub(crate) membership: indexmap::IndexMap<i64, i64>,
    pub(crate) locked_wars: std::collections::BTreeSet<(i64, i64)>,
    pub(crate) relationships: indexmap::IndexMap<(i64, i64), Relationship>,
}

// Python: openciv3/diplomacy.py:32
pub(crate) fn Diplomacy__locked_peace(
    self_: &Diplomacy,
    mut left: i64,
    mut right: i64,
) -> rt::Result<bool> {
    let mut alliance: Option<i64> = ((self_).membership.clone()).get(&(left)).cloned();
    Ok(((left != right)
        && ((alliance).is_some()
            && (alliance.clone() == ((self_).membership.clone()).get(&(right)).cloned()))))
}

// Python: openciv3/diplomacy.py:36
pub(crate) fn Diplomacy__locked_war(
    self_: &Diplomacy,
    mut left: i64,
    mut right: i64,
) -> rt::Result<bool> {
    let (mut first, mut second): (Option<i64>, Option<i64>) = (
        ((self_).membership.clone()).get(&(left)).cloned(),
        ((self_).membership.clone()).get(&(right)).cloned(),
    );
    Ok(((left != right)
        && ((first).is_some()
            && ((second).is_some() && {
                let __needle = (
                    ((*(first.clone()).as_ref().ok_or("expected a value")?).clone())
                        .min((*(second.clone()).as_ref().ok_or("expected a value")?).clone()),
                    ((*(first.clone()).as_ref().ok_or("expected a value")?).clone())
                        .max((*(second.clone()).as_ref().ok_or("expected a value")?).clone()),
                );
                let __container = &(self_).locked_wars;
                __container.contains(&__needle)
            }))))
}

// Python: openciv3/diplomacy.py:40
pub(crate) fn Diplomacy__passage_grants(
    self_: &Diplomacy,
    mut owner: i64,
) -> rt::Result<std::collections::BTreeSet<i64>> {
    Ok({
        let mut __result: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
        for __item in ({
            let mut __comprehension_result_326: std::collections::BTreeSet<i64> =
                std::collections::BTreeSet::new();
            let __comprehension_source_325 = (((self_).relationships.clone())
                .iter()
                .map(|(__key, __value)| (__key.clone(), __value.clone()))
                .collect::<Vec<_>>());
            for ((player, other), relation) in __comprehension_source_325.iter().cloned() {
                if ((player == owner)
                    && ((relation).right_of_passage && !(Diplomacy__at_war(self_, owner, other)?)))
                {
                    __comprehension_result_326.insert(other);
                }
            }
            __comprehension_result_326
        })
        .into_iter()
        {
            __result.insert(__item);
        }
        __result
    })
}

/// Return embargoed trade pairs as sorted civilization IDs.
// Python: openciv3/diplomacy.py:44
pub(crate) fn Diplomacy__active_trade_embargoes(
    self_: &Diplomacy,
    mut turn: i64,
) -> rt::Result<std::collections::BTreeSet<(i64, i64)>> {
    let mut pairs: std::collections::BTreeSet<(i64, i64)> = std::collections::BTreeSet::new();
    for mut for_target_47_8 in ((self_).relationships.clone())
        .iter()
        .map(|(__key, __value)| (__key.clone(), __value.clone()))
        .collect::<Vec<_>>()
    {
        let ((mut left, mut right), mut relationship): ((i64, i64), Relationship) = for_target_47_8;
        if (Diplomacy__at_war(self_, left, right)? || Diplomacy__at_war(self_, right, left)?) {
            continue;
        }
        for mut deal in (&(relationship).deals).iter() {
            let mut target: Option<i64> = (deal).against.clone();
            if (((deal).kind.clone() == crate::openciv3::recurring_deals::DealKind::TRADE_EMBARGO)
                && ((target).is_some()
                    && (match (target.clone()) {
                        Some(__value) => {
                            let __needle = __value;
                            let __container = &({
                                let __tuple_value = &((left, right));
                                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                            });
                            !__container.contains(&__needle)
                        }
                        None => true,
                    } && {
                        let __compare_0 = (deal).start;
                        let __compare_1 = turn;
                        if (__compare_0 <= __compare_1) {
                            let __compare_2 =
                                crate::openciv3::recurring_deals::RecurringDeal__end(deal)?;
                            (__compare_1 < __compare_2)
                        } else {
                            false
                        }
                    })))
            {
                for mut signer in {
                    let __tuple_items = (left, right);
                    [__tuple_items.0, __tuple_items.1]
                } {
                    {
                        pairs.insert((
                            (signer).min(
                                (*(target.clone()).as_ref().ok_or("expected a value")?).clone(),
                            ),
                            (signer).max(
                                (*(target.clone()).as_ref().ok_or("expected a value")?).clone(),
                            ),
                        ));
                    };
                }
            }
        }
    }
    Ok(pairs)
}

// Python: openciv3/diplomacy.py:58
pub(crate) fn Diplomacy__at_war(
    self_: &Diplomacy,
    mut left: i64,
    mut right: i64,
) -> rt::Result<bool> {
    if (left == right) {
        return Ok(false);
    }
    if ((left == 0i64) || (right == 0i64)) {
        return Ok(true);
    }
    let mut relationship: Option<Relationship> = ((self_).relationships.clone())
        .get(&((left, right)))
        .cloned();
    Ok(((relationship).is_some()
        && ((*(relationship.clone()).as_ref().ok_or("expected a value")?).clone()).at_war))
}

// Python: openciv3/diplomacy.py:67
pub(crate) fn initialize_diplomacy(
    options: &crate::openciv3::scenario_model::ScenarioOptions,
    mut players: Vec<crate::openciv3::players::Player>,
) -> rt::Result<Diplomacy> {
    let mut state: Diplomacy = Diplomacy {
        alliance_names: {
            let mut __comprehension_result_328: indexmap::IndexMap<i64, String> =
                indexmap::IndexMap::new();
            let __comprehension_source_327 = (((options).alliance_names.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>());
            for (i, name) in __comprehension_source_327.iter().cloned() {
                if (i != 0i64) {
                    {
                        let (__key, __value) = (i, name.clone());
                        __comprehension_result_328.insert(__key, __value);
                    }
                }
            }
            __comprehension_result_328
        },
        locked_wars: ((options).alliance_wars.clone())
            .into_iter()
            .collect::<std::collections::BTreeSet<_>>(),
        membership: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
        relationships: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
    };
    if (!((options).alliance_ids.clone()).is_empty()
        && (((&(options).alliance_ids).len() as i64)
            != ((&(options).allowed_civilizations).len() as i64)))
    {
        return Err("Alliance assignments must match the GAME civilization list"
            .to_string()
            .into());
    }
    for mut for_target_72_4 in {
        let __left = (options).allowed_civilizations.clone();
        let __right = (options).alliance_ids.clone();
        if false && __left.len() != __right.len() {
            return Err("zip() argument lengths differ".into());
        }
        let mut __result: Vec<(i64, i64)> = Vec::new();
        let __length = __left.len().min(__right.len());
        let mut __left_iter = __left.into_iter();
        let mut __right_iter = __right.into_iter();
        for __index in 0..__length {
            __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
        }
        __result
    } {
        let (mut civilization, mut alliance): (i64, i64) = for_target_72_4;
        if !({
            let __compare_0 = 0i64;
            let __compare_1 = alliance;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = 4i64;
                (__compare_1 <= __compare_2)
            } else {
                false
            }
        }) {
            return Err("Invalid scenario alliance ID".to_string().into());
        }
        if ((civilization) != 0
            && ((alliance) != 0
                && ({
                    let __source = &players;
                    let __key = civilization;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .included))
        {
            state.membership.insert(civilization, alliance);
        }
    }
    for mut player in (players).iter() {
        for mut other in (&(player).contacts).iter().copied() {
            if (crate::openciv3::players::Player__barbarian(player)?
                || (!((player).included)
                    || (!(other != 0i64)
                        || !(({
                            let __source = &players;
                            let __key = other;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .included))))
            {
                continue;
            }
            let mut allied: bool = Diplomacy__locked_peace(&state, (player).civilization, other)?;
            let mut deals: Vec<crate::openciv3::recurring_deals::RecurringDeal> = vec![
                crate::openciv3::recurring_deals::RecurringDeal____post_init__(
                    &(crate::openciv3::recurring_deals::RecurringDeal {
                        deal_type: crate::openciv3::recurring_deals::DealType::DIPLOMATIC_AGREEMENT,
                        kind: crate::openciv3::recurring_deals::DealKind::PEACE,
                        direction: crate::openciv3::recurring_deals::DealDirection::EXCHANGE,
                        duration: 0i64,
                        gold: 0i64,
                        resource: String::new(),
                        start: 0i64,
                        against: None,
                    }),
                )?,
            ];
            if allied {
                {
                    deals.push(crate::openciv3::recurring_deals::RecurringDeal____post_init__(&(crate::openciv3::recurring_deals::RecurringDeal { deal_type: crate::openciv3::recurring_deals::DealType::DIPLOMATIC_AGREEMENT, kind: crate::openciv3::recurring_deals::DealKind::MUTUAL_PROTECTION, direction: crate::openciv3::recurring_deals::DealDirection::EXCHANGE, duration: 0i64, gold: 0i64, resource: String::new(), start: 0i64, against: None }))?);
                };
            }
            state.relationships.insert(
                ((player).civilization, other),
                Relationship {
                    mutual_protection: allied,
                    deals: deals,
                    at_war: false,
                    war_declaration_count: 0i64,
                    war_declaration_with_passage_count: 0i64,
                    was_sneak_attacked: false,
                    refuse_contact_until_turn: (1i64).checked_neg().ok_or("integer overflow")?,
                    right_of_passage: false,
                },
            );
        }
    }
    for mut for_target_90_4 in ((state).membership.clone())
        .iter()
        .map(|(__key, __value)| (__key.clone(), __value.clone()))
        .collect::<Vec<_>>()
    {
        let (mut left, mut left_alliance): (i64, i64) = for_target_90_4;
        for mut for_target_91_8 in ((state).membership.clone())
            .iter()
            .map(|(__key, __value)| (__key.clone(), __value.clone()))
            .collect::<Vec<_>>()
        {
            let (mut right, mut right_alliance): (i64, i64) = for_target_91_8;
            let mut pair: (i64, i64) = (
                (left_alliance).min(right_alliance),
                (left_alliance).max(right_alliance),
            );
            if ((left != right) && {
                let __needle = pair;
                let __container = &(state).locked_wars;
                __container.contains(&__needle)
            }) {
                state.relationships.insert(
                    (left, right),
                    Relationship {
                        at_war: true,
                        mutual_protection: false,
                        war_declaration_count: 0i64,
                        war_declaration_with_passage_count: 0i64,
                        was_sneak_attacked: false,
                        refuse_contact_until_turn: (1i64)
                            .checked_neg()
                            .ok_or("integer overflow")?,
                        right_of_passage: false,
                        deals: vec![],
                    },
                );
                (({
                    let __source = &players;
                    let __key = left;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .contacts
                .clone())
                .insert(right);
            }
        }
    }
    Ok(state)
}
