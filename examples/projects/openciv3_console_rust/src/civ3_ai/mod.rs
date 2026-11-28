pub(crate) mod barbarian_ai;

pub(crate) mod civilization_ai;

pub(crate) mod combat_ai;

pub(crate) mod defender_ai;

pub(crate) mod economic_ai;

pub(crate) mod explorer_ai;

pub(crate) mod production_ai;

pub(crate) mod settler_ai;

pub(crate) mod settler_locations;

pub(crate) mod strategic_ai;

pub(crate) mod worker_ai;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct interfaces__TurnDecisionEngine {
    pub(crate) pending_trade: Option<crate::civ3_ai::civilization_ai::AITradePause>,
}
