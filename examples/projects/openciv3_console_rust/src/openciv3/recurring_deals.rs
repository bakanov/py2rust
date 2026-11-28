use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum DealType {
    DIPLOMATIC_AGREEMENT,
    ALLIANCE,
    EMBARGO,
    MAP,
    COMMUNICATION,
    RESOURCE,
    LUXURY,
    GOLD,
    TECHNOLOGY,
    CITY,
    UNIT,
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum DealKind {
    PEACE,
    MUTUAL_PROTECTION,
    RIGHT_OF_PASSAGE,
    MILITARY_ALLIANCE,
    TRADE_EMBARGO,
    GOLD_PER_TURN,
    RESOURCE_PER_TURN,
    LUXURY_PER_TURN,
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum DealDirection {
    INBOUND,
    OUTBOUND,
    EXCHANGE,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct RecurringDeal {
    pub(crate) deal_type: DealType,
    pub(crate) kind: DealKind,
    pub(crate) direction: DealDirection,
    pub(crate) gold: i64,
    pub(crate) resource: String,
    pub(crate) duration: i64,
    pub(crate) start: i64,
    pub(crate) against: Option<i64>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct DiplomaticPayments {
    pub(crate) incoming: i64,
    pub(crate) outgoing: i64,
}

// Python: openciv3/recurring_deals.py:53
pub(crate) fn RecurringDeal____post_init__(self_: &RecurringDeal) -> rt::Result<RecurringDeal> {
    if (((self_).gold < 0i64) || (((self_).duration < 0i64) || ((self_).start < 0i64))) {
        return Err("Deal gold, duration and start must be nonnegative"
            .to_string()
            .into());
    }
    if ((&(self_).against).is_some()
        && ((*((self_).against.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone()
            <= 0i64))
    {
        return Err("Deal target must be a nonbarbarian civilization"
            .to_string()
            .into());
    }
    if (((self_).kind.clone() == DealKind::GOLD_PER_TURN)
        && ((self_).direction.clone() == DealDirection::EXCHANGE))
    {
        return Err("Gold payments require a direction".to_string().into());
    }
    if {
        let __needle = (self_).kind.clone();
        let __container = &({
            let __tuple_value = &((DealKind::RESOURCE_PER_TURN, DealKind::LUXURY_PER_TURN));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        __container.contains(&__needle)
    } {
        if (!(((&(self_).resource).chars().count() as i64) != 0i64)
            || ((self_).direction.clone() == DealDirection::EXCHANGE))
        {
            return Err("Resource payments require a resource and direction"
                .to_string()
                .into());
        }
    }
    Ok((*self_).clone())
}

// Python: openciv3/recurring_deals.py:65
pub(crate) fn RecurringDeal__end(self_: &RecurringDeal) -> rt::Result<i64> {
    Ok(
        (if (((self_).kind.clone() == DealKind::PEACE) && ((self_).start == 0i64)) {
            0i64
        } else {
            ((self_).start)
                .checked_add((self_).duration)
                .ok_or("integer overflow")?
        }),
    )
}

// Python: openciv3/recurring_deals.py:68
pub(crate) fn RecurringDeal__turns_remaining(
    self_: &RecurringDeal,
    mut turn: i64,
) -> rt::Result<i64> {
    Ok((0i64).max(
        (RecurringDeal__end(self_)?)
            .checked_sub(turn)
            .ok_or("integer overflow")?,
    ))
}

// Python: openciv3/recurring_deals.py:71
pub(crate) fn RecurringDeal__counterpart(self_: &RecurringDeal) -> rt::Result<RecurringDeal> {
    let mut opposite: indexmap::IndexMap<DealDirection, DealDirection> = [
        (DealDirection::INBOUND, DealDirection::OUTBOUND),
        (DealDirection::OUTBOUND, DealDirection::INBOUND),
        (DealDirection::EXCHANGE, DealDirection::EXCHANGE),
    ]
    .into_iter()
    .collect::<indexmap::IndexMap<_, _>>();
    Ok({
        let mut __replacement = ((*self_).clone()).clone();
        __replacement.direction = (opposite)
            .get(&((self_).direction.clone()))
            .ok_or("missing dict key")?
            .clone();
        __replacement
    })
}

/// Legacy expiry policy; war cancellation is a separate state transition.
// Python: openciv3/recurring_deals.py:78
pub(crate) fn RecurringDeal__expires(
    self_: &RecurringDeal,
    mut turn: i64,
    mut at_war: bool,
    mut locked_peace: bool,
) -> rt::Result<bool> {
    Ok((!(at_war)
        && (!(locked_peace)
            && ({
                let __needle = (self_).kind.clone();
                let __container = &({
                    let __tuple_value = &((DealKind::PEACE, DealKind::MUTUAL_PROTECTION));
                    vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                });
                !__container.contains(&__needle)
            } && (RecurringDeal__turns_remaining(self_, turn)? == 0i64)))))
}

// Python: openciv3/recurring_deals.py:91
pub(crate) fn DiplomaticPayments__net(self_: &DiplomaticPayments) -> rt::Result<i64> {
    Ok(((self_).incoming)
        .checked_sub((self_).outgoing)
        .ok_or("integer overflow")?)
}

/// Sum stored agreements; expiry/removal belongs to turn processing.
// Python: openciv3/recurring_deals.py:95
pub(crate) fn payments(deals: &[RecurringDeal]) -> rt::Result<DiplomaticPayments> {
    let mut chained_locals_97_4: i64 = 0i64;
    let mut incoming: i64 = chained_locals_97_4;
    let mut outgoing: i64 = chained_locals_97_4;
    for mut deal in (deals).iter() {
        if ((deal).kind.clone() == DealKind::GOLD_PER_TURN) {
            if ((deal).direction.clone() == DealDirection::INBOUND) {
                incoming = (incoming)
                    .checked_add((deal).gold)
                    .ok_or("integer overflow")?;
            } else {
                if ((deal).direction.clone() == DealDirection::OUTBOUND) {
                    outgoing = (outgoing)
                        .checked_add((deal).gold)
                        .ok_or("integer overflow")?;
                }
            }
        }
    }
    Ok(DiplomaticPayments {
        incoming: incoming,
        outgoing: outgoing,
    })
}
