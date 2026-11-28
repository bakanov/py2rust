use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct Player {
    pub(crate) civilization: i64,
    pub(crate) included: bool,
    pub(crate) human: bool,
    pub(crate) can_be_picked: bool,
    pub(crate) government: i64,
    pub(crate) era: i64,
    pub(crate) gold: i64,
    pub(crate) primary_color: i64,
    pub(crate) secondary_color: i64,
    pub(crate) known_technologies: std::collections::BTreeSet<i64>,
    pub(crate) science_rate: i64,
    pub(crate) tax_rate: i64,
    pub(crate) luxury_rate: i64,
    pub(crate) skip_first_turn: bool,
    pub(crate) has_played_current_turn: bool,
    pub(crate) contacts: std::collections::BTreeSet<i64>,
    pub(crate) start_embassies: bool,
    pub(crate) defeated: bool,
    pub(crate) anarchy_until: i64,
    pub(crate) researching: Option<i64>,
    pub(crate) last_gold_per_turn: i64,
    pub(crate) beakers: i64,
    pub(crate) turns_researched: i64,
    pub(crate) free_technologies: i64,
    pub(crate) research_queue: Vec<i64>,
    pub(crate) strategic_priorities: Vec<String>,
    pub(crate) turns_until_priority_reevaluation: i64,
    pub(crate) cities_lost: i64,
    pub(crate) victory_points: i64,
    pub(crate) golden_age_turns: Option<i64>,
}

// Python: openciv3/players.py:44
pub(crate) fn Player__barbarian(self_: &Player) -> rt::Result<bool> {
    Ok(((self_).civilization == 0i64))
}

/// Preserve civilization indices so BIQ ownership references remain stable.
// Python: openciv3/players.py:48
pub(crate) fn initialize_players(
    definition: &crate::openciv3::scenario_model::ScenarioDefinition,
) -> rt::Result<Vec<Player>> {
    let mut chosen: Option<i64> = {
        let __find_source_274 = (definition).playable.clone();
        let mut __find_result_274: Option<i64> = None;
        for civ in __find_source_274.iter().cloned() {
            if (AsRef::<str>::as_ref(&(civ).name)
                == AsRef::<str>::as_ref(&(definition).selected_civilization))
            {
                __find_result_274 = Some((civ).index);
                break;
            }
        }
        __find_result_274
    };
    if ((chosen).is_none() || {
        let __needle = (definition).selected_difficulty.clone();
        let __container = &({
            let mut __comprehension_result_276: std::collections::BTreeSet<String> =
                std::collections::BTreeSet::new();
            let __comprehension_source_275 = ((definition).difficulties.clone());
            for level in __comprehension_source_275.iter().cloned() {
                __comprehension_result_276.insert((level).name.clone());
            }
            __comprehension_result_276
        });
        !__container.contains(&__needle)
    }) {
        return Err(
            "Select a playable civilization and difficulty before initializing players"
                .to_string()
                .into(),
        );
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (definition).rules.clone();
    if (!(((&(rules).governments).len() as i64) != 0i64)
        || (((&(rules).global_rules).len() as i64) != 1i64))
    {
        return Err(
            "Player initialization needs governments and one global rules record"
                .to_string()
                .into(),
        );
    }
    let mut default_government: i64 = {
        let __find_source_277 = ((rules).governments.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>();
        let mut __find_result_277: i64 = 0i64;
        for (i, government) in __find_source_277.iter().cloned() {
            if (government).default_type {
                __find_result_277 = i;
                break;
            }
        }
        __find_result_277
    };
    let mut allowed: std::collections::BTreeSet<i64> =
        ((&(definition).options).allowed_civilizations.clone())
            .into_iter()
            .collect::<std::collections::BTreeSet<_>>();
    let mut playable: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_279: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_278 = ((definition).playable.clone());
        for civ in __comprehension_source_278.iter().cloned() {
            __comprehension_result_279.insert((civ).index);
        }
        __comprehension_result_279
    };
    let mut players: Vec<Player> = {
        let mut __comprehension_result_281: Vec<Player> = Vec::new();
        let __comprehension_source_280 = ((definition).civilizations.clone());
        for civ in __comprehension_source_280.iter().cloned() {
            __comprehension_result_281.push(Player {
                civilization: (civ).index,
                included: ({
                    let __needle = (civ).index;
                    let __container = &allowed;
                    __container.contains(&__needle)
                } || crate::openciv3::scenario_model::Civilization__is_barbarian(&civ)?),
                human: (Some((civ).index) == chosen.clone()),
                can_be_picked: {
                    let __needle = (civ).index;
                    let __container = &playable;
                    __container.contains(&__needle)
                },
                government: default_government,
                era: 0i64,
                gold: (if (!(((&(definition).slots).len() as i64) != 0i64) && {
                    let __needle = (civ).index;
                    let __container = &allowed;
                    __container.contains(&__needle)
                }) {
                    ({
                        let __source = &(rules).global_rules;
                        let __key = 0i64;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .starting_treasury
                } else {
                    0i64
                }),
                primary_color: (civ).primary_color,
                secondary_color: (civ).secondary_color,
                has_played_current_turn:
                    crate::openciv3::scenario_model::Civilization__is_barbarian(&civ)?,
                known_technologies: {
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in vec![].into_iter() {
                        __result.insert(__item);
                    }
                    __result
                },
                science_rate: 5i64,
                tax_rate: 5i64,
                luxury_rate: 0i64,
                skip_first_turn: false,
                contacts: {
                    let mut __result = std::collections::BTreeSet::new();
                    for __item in vec![].into_iter() {
                        __result.insert(__item);
                    }
                    __result
                },
                start_embassies: false,
                defeated: false,
                anarchy_until: 0i64,
                researching: None,
                last_gold_per_turn: 0i64,
                beakers: 0i64,
                turns_researched: 0i64,
                free_technologies: 0i64,
                research_queue: vec![],
                strategic_priorities: vec![],
                turns_until_priority_reevaluation: 0i64,
                cities_lost: 0i64,
                victory_points: 0i64,
                golden_age_turns: None,
            });
        }
        __comprehension_result_281
    };
    for mut for_target_66_4 in ((definition).slots.clone())
        .into_iter()
        .enumerate()
        .map(|(__index, __value)| (__index as i64 + 0i64, __value))
        .collect::<Vec<_>>()
    {
        let (mut index, mut slot): (i64, crate::openciv3::scenario_model::PlayerSlot) =
            for_target_66_4;
        let mut civilization: i64 = rt::at(&(definition).assigned_civilizations, index)?;
        if (civilization < 0i64) {
            continue;
        }
        let mut player: Player = rt::at(&players, civilization)?;
        if !({
            let __compare_0 = 0i64;
            let __compare_1 = (slot).government;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = ((&(rules).governments).len() as i64);
                (__compare_1 < __compare_2)
            } else {
                false
            }
        }) {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "LEAD[".to_string(),
                    (index).to_string(),
                    "] refers to invalid government ".to_string(),
                    ((slot).government).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        if !({
            let __compare_0 = 0i64;
            let __compare_1 = (slot).era;
            if (__compare_0 <= __compare_1) {
                let __compare_2 =
                    crate::openciv3::scenario_model::ScenarioDefinition__era_count(definition)?;
                (__compare_1 < __compare_2)
            } else {
                false
            }
        }) {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "LEAD[".to_string(),
                    (index).to_string(),
                    "] refers to invalid era ".to_string(),
                    ((slot).era).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        player.government = (slot).government;
        player.era = (slot).era;
        player.gold = (slot).cash;
        player.skip_first_turn = (slot).skip_first_turn;
        player.can_be_picked = (slot).human_allowed;
        player.start_embassies = (slot).start_embassies;
        if ((slot).color > 0i64) {
            player.primary_color = (slot).color;
        }
        ((player).known_technologies).extend(
            ({
                let __source = &(definition).civilizations;
                let __key = civilization;
                &__source[rt::index(__source.len(), __key)?]
            })
            .starting_techs
            .clone(),
        );
        ((player).known_technologies).extend((slot).starting_techs.clone());
    }
    if !(((&(definition).slots).len() as i64) != 0i64) {
        for mut player in (players).iter().cloned() {
            if ((player).included && !(Player__barbarian(&player)?)) {
                ((player).known_technologies).extend(
                    ({
                        let __source = &(definition).civilizations;
                        let __key = (player).civilization;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .starting_techs
                    .clone(),
                );
            }
        }
    }
    for mut player in (players).iter() {
        if ({
            let mut __comprehension_result_283: Vec<bool> = Vec::new();
            let __comprehension_source_282 = ((player).known_technologies.clone());
            for technology in __comprehension_source_282.iter().cloned() {
                __comprehension_result_283.push(
                    !({
                        let __compare_0 = 0i64;
                        let __compare_1 = technology;
                        if (__compare_0 <= __compare_1) {
                            let __compare_2 = ((&(rules).technologies).len() as i64);
                            (__compare_1 < __compare_2)
                        } else {
                            false
                        }
                    }),
                );
            }
            __comprehension_result_283
        })
        .into_iter()
        .any(|__value| __value)
        {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Civilization ".to_string(),
                    ((player).civilization).to_string(),
                    " has an invalid starting technology".to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
    }
    let mut with_embassies: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_285: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_284 = (players.clone());
        for player in __comprehension_source_284.iter().cloned() {
            if ((player).start_embassies && !(Player__barbarian(&player)?)) {
                __comprehension_result_285.insert((player).civilization);
            }
        }
        __comprehension_result_285
    };
    for mut civilization in (with_embassies).iter().copied() {
        (({
            let __source = &players;
            let __key = civilization;
            &__source[rt::index(__source.len(), __key)?]
        })
        .contacts
        .clone())
        .extend({
            let __set_left = with_embassies.clone();
            let __set_right = {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![civilization].into_iter() {
                    __result.insert(__item);
                }
                __result
            };
            let mut __result = std::collections::BTreeSet::new();
            for __item in __set_left.difference(&__set_right) {
                __result.insert(__item.clone());
            }
            __result
        });
    }
    Ok(players)
}
