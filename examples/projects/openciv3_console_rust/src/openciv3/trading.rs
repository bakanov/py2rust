use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct TradeOffer {
    pub(crate) gold: i64,
    pub(crate) technologies: Vec<i64>,
    pub(crate) peace: bool,
    pub(crate) resources: Vec<i64>,
    pub(crate) gold_per_turn: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct TradeDeal {
    pub(crate) proposer: i64,
    pub(crate) recipient: i64,
    pub(crate) gives: TradeOffer,
    pub(crate) receives: TradeOffer,
    pub(crate) right_of_passage: bool,
    pub(crate) embargo_target: Option<i64>,
}

// Python: openciv3/trading.py:23
pub(crate) fn TradeOffer__value_for(
    self_: &TradeOffer,
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<i64> {
    TradeOffer__validate_shape(self_, game)?;
    let mut technologies: i64 = ({
        let mut __comprehension_result_1041: Vec<i64> = Vec::new();
        let __comprehension_source_1040 = ((self_).technologies.clone());
        for tech in __comprehension_source_1040.iter().cloned() {
            __comprehension_result_1041.push(crate::openciv3::research::remaining_research_cost(
                game,
                {
                    let __source = &(game).players;
                    let __key = owner;
                    &__source[rt::index(__source.len(), __key)?]
                },
                tech,
            )?);
        }
        __comprehension_result_1041
    })
    .into_iter()
    .sum::<i64>();
    let mut resources: i64 = ({
        let mut __comprehension_result_1043: Vec<i64> = Vec::new();
        let __comprehension_source_1042 = ((self_).resources.clone());
        for index in __comprehension_source_1042.iter().cloned() {
            __comprehension_result_1043.push(
                (if (({
                    let __source = &(&(&(game).scenario).rules).resources;
                    let __key = index;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .kind
                    == 1i64)
                {
                    40i64
                } else {
                    20i64
                }),
            );
        }
        __comprehension_result_1043
    })
    .into_iter()
    .sum::<i64>();
    Ok(((((self_).gold)
        .checked_add(
            ((self_).gold_per_turn)
                .checked_mul(crate::openciv3::rules::RuleCatalog__deal_duration(
                    &(&(game).scenario).rules,
                )?)
                .ok_or("integer overflow")?,
        )
        .ok_or("integer overflow")?)
    .checked_add(technologies)
    .ok_or("integer overflow")?)
    .checked_add(resources)
    .ok_or("integer overflow")?)
}

// Python: openciv3/trading.py:30
pub(crate) fn TradeOffer__validate_shape(
    self_: &TradeOffer,
    game: &crate::openciv3::game_state::GameState,
) -> rt::Result<()> {
    if (((self_).gold < 0i64) || ((self_).gold_per_turn < 0i64)) {
        return Err("Trade gold cannot be negative".to_string().into());
    }
    if (((((self_).technologies.clone())
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>())
    .len() as i64)
        != ((&(self_).technologies).len() as i64))
    {
        return Err("Trade cannot contain duplicate technologies"
            .to_string()
            .into());
    }
    if ({
        let mut __comprehension_result_1045: Vec<bool> = Vec::new();
        let __comprehension_source_1044 = ((self_).technologies.clone());
        for technology in __comprehension_source_1044.iter().cloned() {
            __comprehension_result_1045.push(
                !({
                    let __compare_0 = 0i64;
                    let __compare_1 = technology;
                    if (__compare_0 <= __compare_1) {
                        let __compare_2 =
                            ((&(&(&(game).scenario).rules).technologies).len() as i64);
                        (__compare_1 < __compare_2)
                    } else {
                        false
                    }
                }),
            );
        }
        __comprehension_result_1045
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("Invalid trade technology".to_string().into());
    }
    if (((((self_).resources.clone())
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>())
    .len() as i64)
        != ((&(self_).resources).len() as i64))
    {
        return Err("Trade cannot contain duplicate resources"
            .to_string()
            .into());
    }
    if ({
        let mut __comprehension_result_1047: Vec<bool> = Vec::new();
        let __comprehension_source_1046 = ((self_).resources.clone());
        for index in __comprehension_source_1046.iter().cloned() {
            __comprehension_result_1047.push(
                !({
                    let __compare_0 = 0i64;
                    let __compare_1 = index;
                    if (__compare_0 <= __compare_1) {
                        let __compare_2 = ((&(&(&(game).scenario).rules).resources).len() as i64);
                        (__compare_1 < __compare_2)
                    } else {
                        false
                    }
                }),
            );
        }
        __comprehension_result_1047
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("Invalid trade resource".to_string().into());
    }
    Ok(())
}

// Python: openciv3/trading.py:53
pub(crate) fn tradable_technologies(
    game: &crate::openciv3::game_state::GameState,
    mut giver: i64,
    mut recipient: i64,
) -> rt::Result<std::collections::BTreeSet<i64>> {
    let mut difference: std::collections::BTreeSet<i64> = {
        let __set_left = ({
            let __source = &(game).players;
            let __key = giver;
            &__source[rt::index(__source.len(), __key)?]
        })
        .known_technologies
        .clone();
        let __set_right = ({
            let __source = &(game).players;
            let __key = recipient;
            &__source[rt::index(__source.len(), __key)?]
        })
        .known_technologies
        .clone();
        let mut __result = std::collections::BTreeSet::new();
        for __item in __set_left.difference(&__set_right) {
            __result.insert(__item.clone());
        }
        __result
    };
    let mut technologies: Vec<crate::openciv3::rules::Technology> =
        (&(&(game).scenario).rules).technologies.clone();
    Ok({
        let mut __comprehension_result_1049: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_1048 = (difference.clone());
        for index in __comprehension_source_1048.iter().cloned() {
            if !((({
                let __source = &technologies;
                let __key = index;
                &__source[rt::index(__source.len(), __key)?]
            })
            .effects
                & 524288i64)
                != 0i64)
            {
                __comprehension_result_1049.insert(index);
            }
        }
        __comprehension_result_1049
    })
}

// Python: openciv3/trading.py:59
pub(crate) fn affordable_gold_per_turn(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<i64> {
    if (crate::openciv3::rules::RuleCatalog__deal_duration(&(&(game).scenario).rules)? <= 0i64) {
        return Ok(0i64);
    }
    let mut commerce: crate::openciv3::player_economy::PlayerCommerce =
        crate::openciv3::player_economy::player_commerce(
            game,
            {
                let __source = &(game).players;
                let __key = owner;
                &__source[rt::index(__source.len(), __key)?]
            },
            None,
            None,
        )?;
    Ok((0i64).max(
        (crate::openciv3::player_economy::PlayerCommerce__net_gold(&commerce)?)
            .checked_sub((commerce).from_other_civilizations)
            .ok_or("integer overflow")?,
    ))
}

// Python: openciv3/trading.py:66
pub(crate) fn can_offer_right_of_passage(
    game: &crate::openciv3::game_state::GameState,
    mut left: i64,
    mut right: i64,
) -> rt::Result<bool> {
    if ((crate::openciv3::rules::RuleCatalog__deal_duration(&(&(game).scenario).rules)? <= 0i64)
        || (crate::openciv3::diplomacy::Diplomacy__at_war(&(game).diplomacy, left, right)?
            || ({
                let __needle = right;
                let __container = &(crate::openciv3::diplomacy::Diplomacy__passage_grants(
                    &(game).diplomacy,
                    left,
                )?);
                __container.contains(&__needle)
            } || {
                let __needle = left;
                let __container = &(crate::openciv3::diplomacy::Diplomacy__passage_grants(
                    &(game).diplomacy,
                    right,
                )?);
                __container.contains(&__needle)
            })))
    {
        return Ok(false);
    }
    let mut known: std::collections::BTreeSet<i64> = {
        let __set_left = ({
            let __source = &(game).players;
            let __key = left;
            &__source[rt::index(__source.len(), __key)?]
        })
        .known_technologies
        .clone();
        let __set_right = ({
            let __source = &(game).players;
            let __key = right;
            &__source[rt::index(__source.len(), __key)?]
        })
        .known_technologies
        .clone();
        let mut __result = std::collections::BTreeSet::new();
        for __item in __set_left.union(&__set_right) {
            __result.insert(__item.clone());
        }
        __result
    };
    Ok(({
        let mut __comprehension_result_1051: Vec<i64> = Vec::new();
        let __comprehension_source_1050 = (known.clone());
        for index in __comprehension_source_1050.iter().cloned() {
            __comprehension_result_1051.push(
                (({
                    let __source = &(&(&(game).scenario).rules).technologies;
                    let __key = index;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .effects
                    & 512i64),
            );
        }
        __comprehension_result_1051
    })
    .into_iter()
    .any(|__value| __value != 0))
}

// Python: openciv3/trading.py:76
pub(crate) fn embargo_targets(
    game: &crate::openciv3::game_state::GameState,
    mut left: i64,
    mut right: i64,
) -> rt::Result<std::collections::BTreeSet<i64>> {
    if ((crate::openciv3::rules::RuleCatalog__deal_duration(&(&(game).scenario).rules)? <= 0i64)
        || crate::openciv3::diplomacy::Diplomacy__at_war(&(game).diplomacy, left, right)?)
    {
        return Ok(std::collections::BTreeSet::new());
    }
    let (mut first, mut second): (
        crate::openciv3::players::Player,
        crate::openciv3::players::Player,
    ) = (
        rt::at(&(game).players, left)?,
        rt::at(&(game).players, right)?,
    );
    let mut known: std::collections::BTreeSet<i64> = {
        let __set_left = (first).known_technologies.clone();
        let __set_right = (second).known_technologies.clone();
        let mut __result = std::collections::BTreeSet::new();
        for __item in __set_left.union(&__set_right) {
            __result.insert(__item.clone());
        }
        __result
    };
    if !(({
        let mut __comprehension_result_1053: Vec<i64> = Vec::new();
        let __comprehension_source_1052 = (known.clone());
        for index in __comprehension_source_1052.iter().cloned() {
            __comprehension_result_1053.push(
                (({
                    let __source = &(&(&(game).scenario).rules).technologies;
                    let __key = index;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .effects
                    & 2048i64),
            );
        }
        __comprehension_result_1053
    })
    .into_iter()
    .any(|__value| __value != 0))
    {
        return Ok(std::collections::BTreeSet::new());
    }
    let mut existing: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
    for mut pair in {
        let __tuple_items = ((left, right), (right, left));
        [__tuple_items.0, __tuple_items.1]
    } {
        let mut relationship: Option<crate::openciv3::diplomacy::Relationship> =
            ((&(game).diplomacy).relationships.clone())
                .get(&(pair))
                .cloned();
        if (relationship).is_some() {
            (existing).extend(
                ({
                    let mut __comprehension_result_1055: Vec<Option<i64>> = Vec::new();
                    let __comprehension_source_1054 =
                        (((*(relationship.clone()).as_ref().ok_or("expected a value")?).clone())
                            .deals
                            .clone());
                    for deal in __comprehension_source_1054.iter().cloned() {
                        if (((deal).kind.clone()
                            == crate::openciv3::recurring_deals::DealKind::TRADE_EMBARGO)
                            && ((&(deal).against).is_some() && {
                                let __compare_0 = (deal).start;
                                let __compare_1 = (game).turn;
                                if (__compare_0 <= __compare_1) {
                                    let __compare_2 =
                                        crate::openciv3::recurring_deals::RecurringDeal__end(
                                            &deal,
                                        )?;
                                    (__compare_1 < __compare_2)
                                } else {
                                    false
                                }
                            }))
                        {
                            __comprehension_result_1055.push((deal).against.clone());
                        }
                    }
                    __comprehension_result_1055
                })
                .into_iter()
                .map(|__value| __value.ok_or("expected a value".into()))
                .collect::<rt::Result<Vec<_>>>()?,
            );
        }
    }
    Ok({
        let __set_left = {
            let mut __comprehension_result_1057: std::collections::BTreeSet<i64> =
                std::collections::BTreeSet::new();
            let __comprehension_source_1056 = ({
                let __set_left = (first).contacts.clone();
                let __set_right = (second).contacts.clone();
                let mut __result = std::collections::BTreeSet::new();
                for __item in __set_left.intersection(&__set_right) {
                    __result.insert(__item.clone());
                }
                __result
            });
            for target in __comprehension_source_1056.iter().cloned() {
                if ({
                    let __compare_0 = 0i64;
                    let __compare_1 = target;
                    if (__compare_0 < __compare_1) {
                        let __compare_2 = ((&(game).players).len() as i64);
                        (__compare_1 < __compare_2)
                    } else {
                        false
                    }
                } && ({
                    let __needle = target;
                    let __container = &({
                        let __tuple_value = &((left, right));
                        vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                    });
                    !__container.contains(&__needle)
                } && (({
                    let __source = &(game).players;
                    let __key = target;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .included
                    && !(({
                        let __source = &(game).players;
                        let __key = target;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .defeated))))
                {
                    __comprehension_result_1057.insert(target);
                }
            }
            __comprehension_result_1057
        };
        let __set_right = existing;
        let mut __result = std::collections::BTreeSet::new();
        for __item in __set_left.difference(&__set_right) {
            __result.insert(__item.clone());
        }
        __result
    })
}

// Python: openciv3/trading.py:96
pub(crate) fn validate_deal(
    game: &crate::openciv3::game_state::GameState,
    deal: &TradeDeal,
) -> rt::Result<()> {
    let (mut left, mut right): (i64, i64) = ((deal).proposer, (deal).recipient);
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
        return Err("Trade requires distinct nonbarbarian civilizations"
            .to_string()
            .into());
    }
    if ({
        let mut __comprehension_result_1059: Vec<bool> = Vec::new();
        let __comprehension_source_1058 = ({
            let __tuple_value = &((left, right));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        for owner in __comprehension_source_1058.iter().cloned() {
            __comprehension_result_1059.push(
                (!(({
                    let __source = &(game).players;
                    let __key = owner;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .included)
                    || ({
                        let __source = &(game).players;
                        let __key = owner;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .defeated),
            );
        }
        __comprehension_result_1059
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("Trade requires active civilizations".to_string().into());
    }
    if ((&(deal).gives).peace != (&(deal).receives).peace) {
        return Err("Both sides must agree to peace".to_string().into());
    }
    let mut at_war: bool =
        crate::openciv3::diplomacy::Diplomacy__at_war(&(game).diplomacy, left, right)?;
    if (at_war != (&(deal).gives).peace) {
        return Err(
            "Warring civilizations must include peace; peaceful ones cannot sign it again"
                .to_string()
                .into(),
        );
    }
    if ((&(deal).gives).peace
        && crate::openciv3::diplomacy::Diplomacy__locked_war(&(game).diplomacy, left, right)?)
    {
        return Err("Locked enemies cannot sign peace".to_string().into());
    }
    if ((crate::openciv3::rules::RuleCatalog__deal_duration(&(&(game).scenario).rules)? <= 0i64)
        && ((deal).right_of_passage
            || ((&(deal).embargo_target).is_some()
                || ({
                    let mut __comprehension_result_1061: Vec<bool> = Vec::new();
                    let __comprehension_source_1060 = ({
                        let __tuple_value = &(((deal).gives.clone(), (deal).receives.clone()));
                        vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                    });
                    for offer in __comprehension_source_1060.iter().cloned() {
                        __comprehension_result_1061.push(
                            (((offer).gold_per_turn) != 0
                                || !((offer).resources.clone()).is_empty()),
                        );
                    }
                    __comprehension_result_1061
                })
                .into_iter()
                .any(|__value| __value))))
    {
        return Err(
            "Recurring trade agreements are disabled by the scenario rules"
                .to_string()
                .into(),
        );
    }
    if ((deal).right_of_passage && !(can_offer_right_of_passage(game, left, right)?)) {
        return Err(
            "Right of passage requires peace, enabling technology, and no existing grant"
                .to_string()
                .into(),
        );
    }
    if ((&(deal).embargo_target).is_some()
        && match ((deal).embargo_target.clone()) {
            Some(__value) => {
                let __needle = __value;
                let __container = &(embargo_targets(game, left, right)?);
                !__container.contains(&__needle)
            }
            None => true,
        })
    {
        return Err("An embargo requires peace, enabling technology, and a known eligible third civilization".to_string().into());
    }
    let mut network: Option<crate::openciv3::trade_network::TradeNetwork> = (if !({
        let __boolean_123705967792016 = (&(deal).gives).resources.clone();
        if !(__boolean_123705967792016).is_empty() {
            __boolean_123705967792016
        } else {
            (&(deal).receives).resources.clone()
        }
    })
    .is_empty()
    {
        Some(crate::openciv3::trade_network::TradeNetwork____post_init__(
            crate::openciv3::trade_network::TradeNetwork {
                game: (*game).clone(),
                owner: Some(left),
                trade_with: Some(right),
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
        )?)
    } else {
        None
    });
    if ((network).is_some()
        && crate::openciv3::trade_network::TradeNetwork__embargoed(
            &((*(network.clone()).as_ref().ok_or("expected a value")?).clone()),
            left,
            right,
        )?)
    {
        return Err("Trade embargo prevents resource agreements"
            .to_string()
            .into());
    }
    for mut for_target_119_4 in {
        let __tuple_items = (
            (left, right, (deal).gives.clone()),
            (right, left, (deal).receives.clone()),
        );
        [__tuple_items.0, __tuple_items.1]
    } {
        let (mut owner, mut recipient, mut offer): (i64, i64, TradeOffer) = for_target_119_4;
        TradeOffer__validate_shape(&offer, game)?;
        if ((offer).gold
            > (0i64).max(
                ({
                    let __source = &(game).players;
                    let __key = owner;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .gold,
            ))
        {
            return Err("Insufficient treasury for trade".to_string().into());
        }
        if (((offer).gold_per_turn) != 0
            && ((offer).gold_per_turn > affordable_gold_per_turn(game, owner)?))
        {
            return Err("Insufficient income for the recurring gold payment"
                .to_string()
                .into());
        }
        if ({
            let mut __comprehension_result_1063: Vec<bool> = Vec::new();
            let __comprehension_source_1062 = ((offer).technologies.clone());
            for technology in __comprehension_source_1062.iter().cloned() {
                __comprehension_result_1063.push({
                    let __needle = technology;
                    let __container = &({
                        let __source = &(game).players;
                        let __key = owner;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .known_technologies;
                    !__container.contains(&__needle)
                });
            }
            __comprehension_result_1063
        })
        .into_iter()
        .any(|__value| __value)
        {
            return Err("Cannot trade an unknown technology".to_string().into());
        }
        if ({
            let mut __comprehension_result_1065: Vec<bool> = Vec::new();
            let __comprehension_source_1064 = ((offer).technologies.clone());
            for technology in __comprehension_source_1064.iter().cloned() {
                __comprehension_result_1065.push({
                    let __needle = technology;
                    let __container = &({
                        let __source = &(game).players;
                        let __key = recipient;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .known_technologies;
                    __container.contains(&__needle)
                });
            }
            __comprehension_result_1065
        })
        .into_iter()
        .any(|__value| __value)
        {
            return Err("Recipient already knows offered technology"
                .to_string()
                .into());
        }
        if !({
            let __left = &(((offer).technologies.clone())
                .into_iter()
                .collect::<std::collections::BTreeSet<_>>());
            let __right = &(tradable_technologies(game, owner, recipient)?);
            __left.is_subset(__right)
        }) {
            return Err("Offered technology cannot be traded".to_string().into());
        }
        if (!((offer).resources.clone()).is_empty()
            && ((network).is_none()
                || !({
                    let __left = &(((offer).resources.clone())
                        .into_iter()
                        .collect::<std::collections::BTreeSet<_>>());
                    let __right =
                        &(crate::openciv3::trade_network::TradeNetwork__exportable_resources(
                            &((*(network.clone()).as_ref().ok_or("expected a value")?).clone()),
                            owner,
                            recipient,
                        )?);
                    __left.is_subset(__right)
                })))
        {
            return Err(
                "Offered resources require a trade route and a surplus at the supplier"
                    .to_string()
                    .into(),
            );
        }
    }
    Ok(())
}

/// Return the AI recipient's valuations of the offered and requested terms.
// Python: openciv3/trading.py:135
pub(crate) fn proposal_values(
    game: &crate::openciv3::game_state::GameState,
    deal: &TradeDeal,
) -> rt::Result<(i64, i64)> {
    validate_deal(game, deal)?;
    if {
        let __needle = (deal).recipient;
        let __container = &({
            let __source = &(game).players;
            let __key = (deal).proposer;
            &__source[rt::index(__source.len(), __key)?]
        })
        .contacts;
        !__container.contains(&__needle)
    } {
        return Err("Trade requires diplomatic contact".to_string().into());
    }
    if !(crate::openciv3::diplomacy_actions::accepts_contact(
        game,
        (deal).recipient,
        (deal).proposer,
    )?) {
        return Err("Their leader refuses to negotiate.".to_string().into());
    }
    if ({
        let __compare_0 = (deal).gives.clone();
        let __compare_1 = (deal).receives.clone();
        if (__compare_0 == __compare_1) {
            let __compare_2 = TradeOffer {
                gold: 0i64,
                technologies: vec![],
                peace: false,
                resources: vec![],
                gold_per_turn: 0i64,
            };
            (__compare_1 == __compare_2)
        } else {
            false
        }
    } && (!((deal).right_of_passage) && (&(deal).embargo_target).is_none()))
    {
        return Err("Add a trade term or treaty to the proposal."
            .to_string()
            .into());
    }
    Ok((
        TradeOffer__value_for(&(deal).gives, game, (deal).recipient)?,
        TradeOffer__value_for(&(deal).receives, game, (deal).recipient)?,
    ))
}

/// Price the current proposal by adding gold or technologies to its terms.
// Python: openciv3/trading.py:148
pub(crate) fn suggest_terms(
    game: &crate::openciv3::game_state::GameState,
    deal: &TradeDeal,
) -> rt::Result<TradeDeal> {
    let (mut offered, mut requested): (i64, i64) = proposal_values(game, deal)?;
    let mut buyer: crate::openciv3::players::Player = rt::at(&(game).players, (deal).proposer)?;
    let mut seller: crate::openciv3::players::Player = rt::at(&(game).players, (deal).recipient)?;
    if ((requested == 0i64)
        && (!({
            let __boolean_123705967913552 = (&(deal).gives).technologies.clone();
            if !(__boolean_123705967913552).is_empty() {
                __boolean_123705967913552
            } else {
                (&(deal).gives).resources.clone()
            }
        })
        .is_empty()
            && !((&(deal).gives).gold != 0i64)))
    {
        let mut payment: i64 = ((seller).gold).min(offered);
        if (payment <= 0i64) {
            return Err("They have no gold to offer.".to_string().into());
        }
        return Ok({
            let mut __replacement = ((*deal).clone()).clone();
            __replacement.receives = {
                let mut __replacement = ((deal).receives.clone()).clone();
                __replacement.gold = payment;
                __replacement
            };
            __replacement
        });
    }
    let mut shortfall: i64 = (requested).checked_sub(offered).ok_or("integer overflow")?;
    if (shortfall <= 0i64) {
        return Ok((*deal).clone());
    }
    let mut available_gold: i64 = (if ((&(deal).receives).gold != 0i64) {
        0i64
    } else {
        (0i64).max(
            ((buyer).gold)
                .checked_sub((&(deal).gives).gold)
                .ok_or("integer overflow")?,
        )
    });
    let mut candidates: Vec<(i64, i64)> = {
        let mut __comprehension_result_1067: Vec<(i64, i64)> = Vec::new();
        let __comprehension_source_1066 = ({
            let __set_left = tradable_technologies(game, (deal).proposer, (deal).recipient)?;
            let __set_right = ((&(deal).gives).technologies.clone())
                .into_iter()
                .collect::<std::collections::BTreeSet<_>>();
            let mut __result = std::collections::BTreeSet::new();
            for __item in __set_left.difference(&__set_right) {
                __result.insert(__item.clone());
            }
            __result
        });
        for tech in __comprehension_source_1066.iter().cloned() {
            __comprehension_result_1067.push((
                crate::openciv3::research::remaining_research_cost(game, &seller, tech)?,
                tech,
            ));
        }
        __comprehension_result_1067
    };
    candidates = {
        let mut __sorted = {
            let mut __comprehension_result_1069: Vec<(i64, i64)> = Vec::new();
            let __comprehension_source_1068 = (candidates.clone());
            for (value, tech) in __comprehension_source_1068.iter().cloned() {
                if (value > 0i64) {
                    __comprehension_result_1069.push((value, tech));
                }
            }
            __comprehension_result_1069
        };
        __sorted.sort();
        __sorted
    };
    let mut technologies: Vec<i64> = (&(&(deal).gives).technologies)
        .iter()
        .cloned()
        .collect::<Vec<_>>();
    while ((shortfall > available_gold) && !(candidates.clone()).is_empty()) {
        let mut needed: i64 = (shortfall)
            .checked_sub(available_gold)
            .ok_or("integer overflow")?;
        let mut index: i64 = {
            let __find_source_1070 = (candidates.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>();
            let mut __find_result_1070: i64 = ((candidates).len() as i64)
                .checked_sub(1i64)
                .ok_or("integer overflow")?;
            for (i, (value, _)) in __find_source_1070.iter().cloned() {
                if (value >= needed) {
                    __find_result_1070 = i;
                    break;
                }
            }
            __find_result_1070
        };
        let (mut value, mut technology): (i64, i64) = {
            let __key = index;
            let __index = rt::index(candidates.len(), __key)?;
            candidates.remove(__index)
        };
        {
            technologies.push(technology);
        };
        shortfall = (shortfall).checked_sub(value).ok_or("integer overflow")?;
    }
    if (shortfall > available_gold) {
        return Err(
            "Your available gold and technologies would not cover their price."
                .to_string()
                .into(),
        );
    }
    Ok({
        let mut __replacement = ((*deal).clone()).clone();
        __replacement.gives = {
            let mut __replacement = ((deal).gives.clone()).clone();
            __replacement.gold = ((&(deal).gives).gold)
                .checked_add((0i64).max(shortfall))
                .ok_or("integer overflow")?;
            __replacement.technologies = (technologies).iter().cloned().collect::<Vec<_>>();
            __replacement
        };
        __replacement
    })
}

/// Apply an agreed offer; revalidate stale offers before changing either side.
// Python: openciv3/trading.py:178
pub(crate) fn execute_deal(
    game: &crate::openciv3::game_state::GameState,
    deal: &TradeDeal,
) -> rt::Result<()> {
    validate_deal(game, deal)?;
    let mut duration: i64 =
        crate::openciv3::rules::RuleCatalog__deal_duration(&(&(game).scenario).rules)?;
    if (&(deal).gives).peace {
        crate::openciv3::diplomacy_actions::sign_peace(game, (deal).proposer, (deal).recipient)?;
    } else {
        crate::openciv3::diplomacy_actions::establish_contact(
            (*game).clone(),
            (deal).proposer,
            (deal).recipient,
        )?;
    }
    if (deal).right_of_passage {
        crate::openciv3::deal_lifecycle::register_deal(
            (*game).clone(),
            (deal).proposer,
            (deal).recipient,
            &(crate::openciv3::recurring_deals::RecurringDeal____post_init__(
                &(crate::openciv3::recurring_deals::RecurringDeal {
                    deal_type: crate::openciv3::recurring_deals::DealType::DIPLOMATIC_AGREEMENT,
                    kind: crate::openciv3::recurring_deals::DealKind::RIGHT_OF_PASSAGE,
                    direction: crate::openciv3::recurring_deals::DealDirection::EXCHANGE,
                    duration: duration,
                    start: (game).turn,
                    gold: 0i64,
                    resource: String::new(),
                    against: None,
                }),
            )?),
        )?;
    }
    if (&(deal).embargo_target).is_some() {
        crate::openciv3::deal_lifecycle::register_deal(
            (*game).clone(),
            (deal).proposer,
            (deal).recipient,
            &(crate::openciv3::recurring_deals::RecurringDeal____post_init__(
                &(crate::openciv3::recurring_deals::RecurringDeal {
                    deal_type: crate::openciv3::recurring_deals::DealType::EMBARGO,
                    kind: crate::openciv3::recurring_deals::DealKind::TRADE_EMBARGO,
                    direction: crate::openciv3::recurring_deals::DealDirection::EXCHANGE,
                    duration: duration,
                    start: (game).turn,
                    against: (deal).embargo_target.clone(),
                    gold: 0i64,
                    resource: String::new(),
                }),
            )?),
        )?;
    }
    let (mut left, mut right): (
        crate::openciv3::players::Player,
        crate::openciv3::players::Player,
    ) = (
        rt::at(&(game).players, (deal).proposer)?,
        rt::at(&(game).players, (deal).recipient)?,
    );
    left.gold = ((left).gold)
        .checked_add(
            ((&(deal).receives).gold)
                .checked_sub((&(deal).gives).gold)
                .ok_or("integer overflow")?,
        )
        .ok_or("integer overflow")?;
    right.gold = ((right).gold)
        .checked_add(
            ((&(deal).gives).gold)
                .checked_sub((&(deal).receives).gold)
                .ok_or("integer overflow")?,
        )
        .ok_or("integer overflow")?;
    crate::openciv3::research::acquire_technologies(
        game,
        &right,
        &((&(deal).gives).technologies.clone()),
    )?;
    crate::openciv3::research::acquire_technologies(
        game,
        &left,
        &((&(deal).receives).technologies.clone()),
    )?;
    for mut for_target_199_4 in {
        let __tuple_items = (
            (left.clone(), right.clone(), (deal).gives.clone()),
            (right.clone(), left.clone(), (deal).receives.clone()),
        );
        [__tuple_items.0, __tuple_items.1]
    } {
        let (mut seller, mut buyer, mut offer): (
            crate::openciv3::players::Player,
            crate::openciv3::players::Player,
            TradeOffer,
        ) = for_target_199_4;
        if ((offer).gold_per_turn != 0i64) {
            crate::openciv3::deal_lifecycle::register_deal(
                (*game).clone(),
                (seller).civilization,
                (buyer).civilization,
                &(crate::openciv3::recurring_deals::RecurringDeal____post_init__(
                    &(crate::openciv3::recurring_deals::RecurringDeal {
                        deal_type: crate::openciv3::recurring_deals::DealType::GOLD,
                        kind: crate::openciv3::recurring_deals::DealKind::GOLD_PER_TURN,
                        direction: crate::openciv3::recurring_deals::DealDirection::OUTBOUND,
                        gold: (offer).gold_per_turn,
                        duration: duration,
                        start: (game).turn,
                        resource: String::new(),
                        against: None,
                    }),
                )?),
            )?;
        }
        for mut index in (&(offer).resources).iter().copied() {
            let mut resource: crate::openciv3::rules::Resource =
                rt::at(&(&(&(game).scenario).rules).resources, index)?;
            let mut luxury: bool = ((resource).kind == 1i64);
            crate::openciv3::deal_lifecycle::register_deal(
                (*game).clone(),
                (seller).civilization,
                (buyer).civilization,
                &(crate::openciv3::recurring_deals::RecurringDeal____post_init__(
                    &(crate::openciv3::recurring_deals::RecurringDeal {
                        deal_type: (if luxury {
                            crate::openciv3::recurring_deals::DealType::LUXURY
                        } else {
                            crate::openciv3::recurring_deals::DealType::RESOURCE
                        }),
                        kind: (if luxury {
                            crate::openciv3::recurring_deals::DealKind::LUXURY_PER_TURN
                        } else {
                            crate::openciv3::recurring_deals::DealKind::RESOURCE_PER_TURN
                        }),
                        direction: crate::openciv3::recurring_deals::DealDirection::OUTBOUND,
                        resource: (resource).name.clone(),
                        duration: duration,
                        start: (game).turn,
                        gold: 0i64,
                        against: None,
                    }),
                )?),
            )?;
        }
    }
    if (!((&(deal).gives).resources.clone()).is_empty()
        || (!((&(deal).receives).resources.clone()).is_empty()
            || (&(deal).embargo_target).is_some()))
    {
        {
            let __call_1071_0 = game;
            let __call_1071_1 = &None;
            crate::openciv3::citizen_moods::recalculate_all_moods(__call_1071_0, __call_1071_1)
        }?;
    }
    Ok(())
}

/// Legacy greedy AI negotiation; returns an offer without applying it.
// Python: openciv3/trading.py:215
pub(crate) fn propose_technology_trade(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    mut other: i64,
) -> rt::Result<Option<TradeDeal>> {
    if ((owner == other)
        || ((owner <= 0i64)
            || ((other <= 0i64) || ((owner).max(other) >= ((&(game).players).len() as i64)))))
    {
        return Ok(None);
    }
    let (mut us, mut them): (
        crate::openciv3::players::Player,
        crate::openciv3::players::Player,
    ) = (
        rt::at(&(game).players, owner)?,
        rt::at(&(game).players, other)?,
    );
    if (({
        let mut __comprehension_result_1073: Vec<bool> = Vec::new();
        let __comprehension_source_1072 = ({
            let __tuple_value = &((us.clone(), them.clone()));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        for player in __comprehension_source_1072.iter().cloned() {
            __comprehension_result_1073.push(((player).defeated || !((player).included)));
        }
        __comprehension_result_1073
    })
    .into_iter()
    .any(|__value| __value)
        || crate::openciv3::diplomacy::Diplomacy__at_war(&(game).diplomacy, owner, other)?)
    {
        return Ok(None);
    }
    if {
        let __needle = (owner, other);
        let __container = &(&(game).diplomacy).relationships;
        !__container.contains_key(&__needle)
    } {
        return Ok(None);
    }
    let mut ours_available: std::collections::BTreeSet<i64> =
        tradable_technologies(game, owner, other)?;
    let mut theirs_available: std::collections::BTreeSet<i64> =
        tradable_technologies(game, other, owner)?;
    if (!(((ours_available).len() as i64) != 0i64) && !(((theirs_available).len() as i64) != 0i64))
    {
        return Ok(None);
    }
    let mut available: std::collections::BTreeSet<i64> = {
        let __set_left = ours_available.clone();
        let __set_right = theirs_available.clone();
        let mut __result = std::collections::BTreeSet::new();
        for __item in __set_left.union(&__set_right) {
            __result.insert(__item.clone());
        }
        __result
    };
    let mut our_prices: indexmap::IndexMap<i64, i64> = {
        let mut __comprehension_result_1075: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_1074 = (available.clone());
        for tech in __comprehension_source_1074.iter().cloned() {
            {
                let (__key, __value) = (
                    tech,
                    crate::openciv3::research::remaining_research_cost(game, &us, tech)?,
                );
                __comprehension_result_1075.insert(__key, __value);
            }
        }
        __comprehension_result_1075
    };
    let mut their_prices: indexmap::IndexMap<i64, i64> = {
        let mut __comprehension_result_1077: indexmap::IndexMap<i64, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_1076 = (available.clone());
        for tech in __comprehension_source_1076.iter().cloned() {
            {
                let (__key, __value) = (
                    tech,
                    crate::openciv3::research::remaining_research_cost(game, &them, tech)?,
                );
                __comprehension_result_1077.insert(__key, __value);
            }
        }
        __comprehension_result_1077
    };
    let mut ours: Vec<i64> = {
        let mut __decorated: Vec<((i64, i64), i64)> = Vec::new();
        for __item in (ours_available).into_iter() {
            let tech = __item;
            let __key = {
                (
                    ((their_prices)
                        .get(&(tech))
                        .ok_or("missing dict key")?
                        .clone())
                    .checked_neg()
                    .ok_or("integer overflow")?,
                    tech,
                )
            };
            __decorated.push((__key, tech));
        }
        __decorated.sort_by(|left, right| {
            if false {
                right.0.cmp(&left.0)
            } else {
                left.0.cmp(&right.0)
            }
        });
        let mut __result = Vec::new();
        for (_, __item) in __decorated {
            __result.push(__item);
        }
        __result
    };
    let mut theirs: Vec<i64> = {
        let mut __decorated: Vec<((i64, i64), i64)> = Vec::new();
        for __item in (theirs_available).into_iter() {
            let tech = __item;
            let __key = {
                (
                    ((our_prices).get(&(tech)).ok_or("missing dict key")?.clone())
                        .checked_neg()
                        .ok_or("integer overflow")?,
                    tech,
                )
            };
            __decorated.push((__key, tech));
        }
        __decorated.sort_by(|left, right| {
            if false {
                right.0.cmp(&left.0)
            } else {
                left.0.cmp(&right.0)
            }
        });
        let mut __result = Vec::new();
        for (_, __item) in __decorated {
            __result.push(__item);
        }
        __result
    };
    let (mut our_treasury, mut their_treasury): (i64, i64) =
        ((0i64).max((us).gold), (0i64).max((them).gold));

    let mut budget: i64 =
        propose_technology_trade__give_value(&our_prices, &their_prices, our_treasury, &ours)?;
    let mut wanted: Vec<i64> = vec![];
    for mut technology in theirs {
        let mut cost: i64 = (our_prices)
            .get(&(technology))
            .ok_or("missing dict key")?
            .clone();
        if (cost <= budget) {
            {
                wanted.push(technology);
            };
            budget = (budget).checked_sub(cost).ok_or("integer overflow")?;
        }
    }
    let mut want_gold: i64 = (budget).min(their_treasury);
    let mut their_value: i64 =
        propose_technology_trade__want_value(&our_prices, &their_prices, want_gold, &wanted)?;
    let mut index: i64 = 0i64;
    while (index < ((ours).len() as i64)) {
        let mut without_technology: Vec<i64> = {
            let mut __left: Vec<i64> = rt::list_slice(&ours, 0i64, index);
            let __right: Vec<i64> = rt::list_slice(
                &ours,
                (index).checked_add(1i64).ok_or("integer overflow")?,
                i64::MAX,
            );
            __left.extend(__right);
            __left
        };
        if (propose_technology_trade__give_value(
            &our_prices,
            &their_prices,
            our_treasury,
            &without_technology,
        )? >= their_value)
        {
            ours = without_technology;
        } else {
            index = (index).checked_add(1i64).ok_or("integer overflow")?;
        }
    }
    let mut give_gold: i64 = (our_treasury)
        .checked_sub(
            ((0i64).max(
                (propose_technology_trade__give_value(
                    &our_prices,
                    &their_prices,
                    our_treasury,
                    &ours,
                )?)
                .checked_sub(their_value)
                .ok_or("integer overflow")?,
            ))
            .min(our_treasury),
        )
        .ok_or("integer overflow")?;
    let mut redundant: i64 = (give_gold).min(want_gold);
    let mut gives: TradeOffer = TradeOffer {
        gold: (give_gold)
            .checked_sub(redundant)
            .ok_or("integer overflow")?,
        technologies: (ours).iter().cloned().collect::<Vec<_>>(),
        peace: false,
        resources: vec![],
        gold_per_turn: 0i64,
    };
    let mut receives: TradeOffer = TradeOffer {
        gold: (want_gold)
            .checked_sub(redundant)
            .ok_or("integer overflow")?,
        technologies: (wanted).iter().cloned().collect::<Vec<_>>(),
        peace: false,
        resources: vec![],
        gold_per_turn: 0i64,
    };
    let mut trade_rate: i64 = (if (them).human {
        100i64
    } else {
        ({
            let __source = &(&(game).scenario).difficulties;
            let __key = (game).difficulty;
            &__source[rt::index(__source.len(), __key)?]
        })
        .ai_trade_rate
    });
    if ((100i64)
        .checked_mul(propose_technology_trade__give_value(
            &our_prices,
            &their_prices,
            (gives).gold,
            &ours,
        )?)
        .ok_or("integer overflow")?
        > (trade_rate)
            .checked_mul(propose_technology_trade__want_value(
                &our_prices,
                &their_prices,
                (receives).gold,
                &wanted,
            )?)
            .ok_or("integer overflow")?)
    {
        return Ok(None);
    }
    if (!(((ours).len() as i64) != 0i64) && !(((wanted).len() as i64) != 0i64)) {
        return Ok(None);
    }
    let mut result: TradeDeal = TradeDeal {
        proposer: owner,
        recipient: other,
        gives: gives,
        receives: receives,
        right_of_passage: false,
        embargo_target: None,
    };
    validate_deal(game, &result)?;
    Ok(Some(result))
}

/// Offer one affordable resource agreement at the negotiation price.
// Python: openciv3/trading.py:274
pub(crate) fn propose_resource_trade(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
    mut other: i64,
) -> rt::Result<Option<TradeDeal>> {
    if (crate::openciv3::rules::RuleCatalog__deal_duration(&(&(game).scenario).rules)? <= 0i64) {
        return Ok(None);
    }
    if ((owner == other)
        || ((owner <= 0i64)
            || ((other <= 0i64) || ((owner).max(other) >= ((&(game).players).len() as i64)))))
    {
        return Ok(None);
    }
    if ({
        let __needle = (owner, other);
        let __container = &(&(game).diplomacy).relationships;
        !__container.contains_key(&__needle)
    } || crate::openciv3::diplomacy::Diplomacy__at_war(&(game).diplomacy, owner, other)?)
    {
        return Ok(None);
    }
    if ({
        let mut __comprehension_result_1079: Vec<bool> = Vec::new();
        let __comprehension_source_1078 = ({
            let __tuple_value = &((owner, other));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        for party in __comprehension_source_1078.iter().cloned() {
            __comprehension_result_1079.push(
                (!(({
                    let __source = &(game).players;
                    let __key = party;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .included)
                    || ({
                        let __source = &(game).players;
                        let __key = party;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .defeated),
            );
        }
        __comprehension_result_1079
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Ok(None);
    }
    let mut capital_owners: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_1081: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_1080 = ((game).cities.clone());
        for city in __comprehension_source_1080.iter().cloned() {
            if (city).capital {
                __comprehension_result_1081.insert((city).owner);
            }
        }
        __comprehension_result_1081
    };
    if !({
        let __left = &({
            let mut __result = std::collections::BTreeSet::new();
            for __item in vec![owner, other].into_iter() {
                __result.insert(__item);
            }
            __result
        });
        let __right = &capital_owners;
        __left.is_subset(__right)
    }) {
        return Ok(None);
    }
    let mut network: crate::openciv3::trade_network::TradeNetwork =
        crate::openciv3::trade_network::TradeNetwork____post_init__(
            crate::openciv3::trade_network::TradeNetwork {
                game: (*game).clone(),
                owner: Some(owner),
                trade_with: Some(other),
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
    for mut for_target_288_4 in {
        let __tuple_items = ((owner, other), (other, owner));
        [__tuple_items.0, __tuple_items.1]
    } {
        let (mut buyer, mut seller): (i64, i64) = for_target_288_4;
        let mut affordable: Vec<(i64, i64)> = {
            let mut __comprehension_result_1083: Vec<(i64, i64)> = Vec::new();
            let mut price: i64;
            let __comprehension_source_1082 =
                (crate::openciv3::trade_network::TradeNetwork__exportable_resources(
                    &network, seller, buyer,
                )?);
            for index in __comprehension_source_1082.iter().cloned() {
                if ({
                    price = TradeOffer__value_for(
                        &(TradeOffer {
                            resources: vec![index],
                            gold: 0i64,
                            technologies: vec![],
                            peace: false,
                            gold_per_turn: 0i64,
                        }),
                        game,
                        buyer,
                    )?;
                    price
                } <= ({
                    let __source = &(game).players;
                    let __key = buyer;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .gold)
                {
                    __comprehension_result_1083.push((price, index));
                }
            }
            __comprehension_result_1083
        };
        if (((affordable).len() as i64) != 0i64) {
            let (mut price, mut index): (i64, i64) = {
                let __values = &affordable;
                let mut __items = __values.iter();
                let mut __best = __items.next().ok_or("max() arg is an empty sequence")?;
                let mut __best_key = {
                    let item = (*__best).clone();
                    (
                        (item).0.clone(),
                        ((item).1.clone()).checked_neg().ok_or("integer overflow")?,
                    )
                };
                for __candidate in __items {
                    let __key = {
                        let item = (*__candidate).clone();
                        (
                            (item).0.clone(),
                            ((item).1.clone()).checked_neg().ok_or("integer overflow")?,
                        )
                    };
                    if __key > __best_key {
                        __best = __candidate;
                        __best_key = __key;
                    }
                }
                (*__best).clone()
            };
            let mut payment: TradeOffer = TradeOffer {
                gold: price,
                technologies: vec![],
                peace: false,
                resources: vec![],
                gold_per_turn: 0i64,
            };
            let mut goods: TradeOffer = TradeOffer {
                resources: vec![index],
                gold: 0i64,
                technologies: vec![],
                peace: false,
                gold_per_turn: 0i64,
            };
            let (mut gives, mut receives): (TradeOffer, TradeOffer) = (if (buyer == owner) {
                (payment.clone(), goods.clone())
            } else {
                (goods.clone(), payment.clone())
            });
            return Ok(Some(TradeDeal {
                proposer: owner,
                recipient: other,
                gives: gives,
                receives: receives,
                right_of_passage: false,
                embargo_target: None,
            }));
        }
    }
    Ok(None)
}

// Python: openciv3/trading.py:236
pub(crate) fn propose_technology_trade__give_value(
    our_prices: &indexmap::IndexMap<i64, i64>,
    their_prices: &indexmap::IndexMap<i64, i64>,
    mut gold: i64,
    technologies: &[i64],
) -> rt::Result<i64> {
    Ok((gold)
        .checked_add(
            (({
                let mut __comprehension_result_1085: Vec<i64> = Vec::new();
                let __comprehension_source_1084 = (technologies.to_vec());
                for tech in __comprehension_source_1084.iter().cloned() {
                    __comprehension_result_1085
                        .push((our_prices).get(&(tech)).ok_or("missing dict key")?.clone());
                }
                __comprehension_result_1085
            })
            .into_iter()
            .sum::<i64>())
            .max(
                ({
                    let mut __comprehension_result_1087: Vec<i64> = Vec::new();
                    let __comprehension_source_1086 = (technologies.to_vec());
                    for tech in __comprehension_source_1086.iter().cloned() {
                        __comprehension_result_1087.push(
                            (their_prices)
                                .get(&(tech))
                                .ok_or("missing dict key")?
                                .clone(),
                        );
                    }
                    __comprehension_result_1087
                })
                .into_iter()
                .sum::<i64>(),
            ),
        )
        .ok_or("integer overflow")?)
}

// Python: openciv3/trading.py:240
pub(crate) fn propose_technology_trade__want_value(
    our_prices: &indexmap::IndexMap<i64, i64>,
    their_prices: &indexmap::IndexMap<i64, i64>,
    mut gold: i64,
    technologies: &[i64],
) -> rt::Result<i64> {
    Ok((gold)
        .checked_add(
            (({
                let mut __comprehension_result_1089: Vec<i64> = Vec::new();
                let __comprehension_source_1088 = (technologies.to_vec());
                for tech in __comprehension_source_1088.iter().cloned() {
                    __comprehension_result_1089
                        .push((our_prices).get(&(tech)).ok_or("missing dict key")?.clone());
                }
                __comprehension_result_1089
            })
            .into_iter()
            .sum::<i64>())
            .min(
                ({
                    let mut __comprehension_result_1091: Vec<i64> = Vec::new();
                    let __comprehension_source_1090 = (technologies.to_vec());
                    for tech in __comprehension_source_1090.iter().cloned() {
                        __comprehension_result_1091.push(
                            (their_prices)
                                .get(&(tech))
                                .ok_or("missing dict key")?
                                .clone(),
                        );
                    }
                    __comprehension_result_1091
                })
                .into_iter()
                .sum::<i64>(),
            ),
        )
        .ok_or("integer overflow")?)
}
