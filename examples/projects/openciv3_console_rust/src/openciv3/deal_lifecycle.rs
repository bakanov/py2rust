use py2rust_service_runtime as rt;

/// Register an already agreed deal; negotiation is the caller's responsibility.
// Python: openciv3/deal_lifecycle.py:7
pub(crate) fn register_deal(
    mut game: crate::openciv3::game_state::GameState,
    mut left: i64,
    mut right: i64,
    deal: &crate::openciv3::recurring_deals::RecurringDeal,
) -> rt::Result<()> {
    crate::openciv3::diplomacy_actions::_validate_pair(&game, left, right)?;
    let mut at_war: bool =
        crate::openciv3::diplomacy::Diplomacy__at_war(&(game).diplomacy, left, right)?;
    let mut treaty: bool = {
        let __needle = (deal).kind.clone();
        let __container = &({
            let __tuple_value = &((
                crate::openciv3::recurring_deals::DealKind::PEACE,
                crate::openciv3::recurring_deals::DealKind::RIGHT_OF_PASSAGE,
                crate::openciv3::recurring_deals::DealKind::MUTUAL_PROTECTION,
            ));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        __container.contains(&__needle)
    };
    if (treaty
        && ((deal).direction.clone() != crate::openciv3::recurring_deals::DealDirection::EXCHANGE))
    {
        return Err("Bilateral treaties require exchange direction"
            .to_string()
            .into());
    }
    if (at_war && ((deal).kind.clone() != crate::openciv3::recurring_deals::DealKind::PEACE)) {
        return Err("Recurring deals require peace".to_string().into());
    }
    if (((deal).kind.clone() == crate::openciv3::recurring_deals::DealKind::PEACE)
        && crate::openciv3::diplomacy::Diplomacy__locked_war(&(game).diplomacy, left, right)?)
    {
        return Err("Locked enemies cannot sign peace".to_string().into());
    }
    if (((deal).start > (game).turn)
        || crate::openciv3::recurring_deals::RecurringDeal__expires(
            deal,
            (game).turn,
            false,
            false,
        )?)
    {
        return Err("Deal must be current".to_string().into());
    }
    if (&(deal).against).is_some() {
        if (match ((deal).against.clone()) {
            Some(__value) => {
                let __needle = __value;
                let __container = &({
                    let __tuple_value = &((left, right));
                    vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                });
                __container.contains(&__needle)
            }
            None => false,
        } || ((*((deal).against.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone()
            >= ((&(game).players).len() as i64)))
        {
            return Err("Invalid third-party deal target".to_string().into());
        }
    }
    let mut counterpart: crate::openciv3::recurring_deals::RecurringDeal =
        crate::openciv3::recurring_deals::RecurringDeal__counterpart(deal)?;
    crate::openciv3::diplomacy_actions::establish_contact(game.clone(), left, right)?;
    (((&(&(game).diplomacy).relationships)
        .get(&((left, right)))
        .ok_or("missing dict key")?)
    .deals
    .clone())
    .push((*deal).clone());
    (((&(&(game).diplomacy).relationships)
        .get(&((right, left)))
        .ok_or("missing dict key")?)
    .deals
    .clone())
    .push(counterpart);
    for mut pair in {
        let __tuple_items = ((left, right), (right, left));
        [__tuple_items.0, __tuple_items.1]
    } {
        let mut relationship: crate::openciv3::diplomacy::Relationship = (&(&(game).diplomacy)
            .relationships)
            .get(&(pair))
            .ok_or("missing dict key")?
            .clone();
        if at_war {
            relationship.at_war = false;
            relationship.refuse_contact_until_turn =
                (1i64).checked_neg().ok_or("integer overflow")?;
        } else {
            if ((deal).kind.clone() == crate::openciv3::recurring_deals::DealKind::RIGHT_OF_PASSAGE)
            {
                relationship.right_of_passage = true;
            } else {
                if ((deal).kind.clone()
                    == crate::openciv3::recurring_deals::DealKind::MUTUAL_PROTECTION)
                {
                    relationship.mutual_protection = true;
                }
            }
        }
    }
    Ok(())
}

/// Expire both directions before movement, without consuming turn randomness.
// Python: openciv3/deal_lifecycle.py:38
pub(crate) fn expire_deals(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<Vec<crate::openciv3::recurring_deals::RecurringDeal>> {
    let mut expired: Vec<crate::openciv3::recurring_deals::RecurringDeal> = vec![];
    for mut for_target_41_4 in (((&(game).diplomacy).relationships.clone())
        .iter()
        .map(|(__key, __value)| (__key.clone(), __value.clone()))
        .collect::<Vec<_>>())
    .iter()
    .cloned()
    .collect::<Vec<_>>()
    {
        let ((mut left, mut right), mut relationship): (
            (i64, i64),
            crate::openciv3::diplomacy::Relationship,
        ) = for_target_41_4;
        if (left != owner) {
            continue;
        }
        for mut deal in (&(relationship).deals).iter().cloned().collect::<Vec<_>>() {
            if !({
                let __call_1092_0 = &(deal.clone());
                let __call_1092_1 = (game).turn;
                let __call_1092_2 =
                    crate::openciv3::diplomacy::Diplomacy__at_war(&(game).diplomacy, left, right)?;
                let __call_1092_3 = crate::openciv3::diplomacy::Diplomacy__locked_peace(
                    &(game).diplomacy,
                    left,
                    right,
                )?;
                crate::openciv3::recurring_deals::RecurringDeal__expires(
                    __call_1092_0,
                    __call_1092_1,
                    __call_1092_2,
                    __call_1092_3,
                )
            }?) {
                continue;
            }
            {
                let __removed = deal.clone();
                let __index = ((relationship).deals)
                    .iter()
                    .position(|__item| (*__item).clone() == __removed)
                    .ok_or("list.remove: value not found")?;
                ((relationship).deals).remove(__index);
            };
            let mut reverse: Option<crate::openciv3::diplomacy::Relationship> =
                ((&(game).diplomacy).relationships.clone())
                    .get(&((right, left)))
                    .cloned();
            let mut counterpart: crate::openciv3::recurring_deals::RecurringDeal =
                crate::openciv3::recurring_deals::RecurringDeal__counterpart(&deal)?;
            if ((reverse).is_some() && {
                let __needle = counterpart.clone();
                let __container = &(((*(reverse.clone()).as_ref().ok_or("expected a value")?)
                    .clone())
                .deals
                .clone());
                __container.contains(&__needle)
            }) {
                {
                    let __removed = counterpart;
                    let __index = (((*(reverse.clone()).as_ref().ok_or("expected a value")?)
                        .clone())
                    .deals
                    .clone())
                    .iter()
                    .position(|__item| (*__item).clone() == __removed)
                    .ok_or("list.remove: value not found")?;
                    (((*(reverse.clone()).as_ref().ok_or("expected a value")?).clone())
                        .deals
                        .clone())
                    .remove(__index);
                };
            }
            if ((deal).kind.clone() == crate::openciv3::recurring_deals::DealKind::RIGHT_OF_PASSAGE)
            {
                relationship.right_of_passage = ({
                    let mut __comprehension_result_1094: Vec<bool> = Vec::new();
                    let __comprehension_source_1093 = ((relationship).deals.clone());
                    for remaining in __comprehension_source_1093.iter().cloned() {
                        __comprehension_result_1094.push(
                            ((remaining).kind.clone()
                                == crate::openciv3::recurring_deals::DealKind::RIGHT_OF_PASSAGE),
                        );
                    }
                    __comprehension_result_1094
                })
                .into_iter()
                .any(|__value| __value);
                if (reverse).is_some() {
                    reverse.as_mut().ok_or("expected a value")?.right_of_passage = ({ let mut __comprehension_result_1096: Vec<bool> = Vec::new();  let __comprehension_source_1095 = (((*(reverse.clone()).as_ref().ok_or("expected a value")?).clone()).deals.clone()); for remaining in __comprehension_source_1095.iter().cloned() { __comprehension_result_1096.push(((remaining).kind.clone() == crate::openciv3::recurring_deals::DealKind::RIGHT_OF_PASSAGE)); } __comprehension_result_1096 }).into_iter().any(|__value| __value);
                }
            }
            {
                expired.push(deal);
            };
        }
    }
    Ok((expired).iter().cloned().collect::<Vec<_>>())
}
