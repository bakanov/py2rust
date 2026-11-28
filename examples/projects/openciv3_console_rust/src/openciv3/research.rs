use py2rust_service_runtime as rt;

// Python: openciv3/research.py:15
pub(crate) fn acquire_technology(
    game: &crate::openciv3::game_state::GameState,
    mut player: crate::openciv3::players::Player,
    mut technology: i64,
    mut start_queued: bool,
) -> rt::Result<bool> {
    let (mut player, mut acquired): (crate::openciv3::players::Player, bool) = {
        let __call_819_0 = (*game).clone();
        let __call_819_1 = player;
        let __call_819_2 = technology;
        let __call_819_3 = start_queued;
        acquire_technology_result(__call_819_0, __call_819_1, __call_819_2, __call_819_3)
    }?;
    Ok(acquired)
}

/// Grant a discovery or traded advance; preserve unrelated research progress.
// Python: openciv3/research.py:20
pub(crate) fn acquire_technology_result(
    mut game: crate::openciv3::game_state::GameState,
    mut player: crate::openciv3::players::Player,
    mut technology: i64,
    mut start_queued: bool,
) -> rt::Result<(crate::openciv3::players::Player, bool)> {
    let mut technologies: Vec<crate::openciv3::rules::Technology> =
        (&(&(game).scenario).rules).technologies.clone();
    if !({
        let __compare_0 = 0i64;
        let __compare_1 = technology;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = ((technologies).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) {
        return Err("Invalid technology index".to_string().into());
    }
    if {
        let __needle = technology;
        let __container = &(player).known_technologies;
        __container.contains(&__needle)
    } {
        return Ok((player, false));
    }
    let mut tech: crate::openciv3::rules::Technology = rt::at(&technologies, technology)?;
    if (((tech).effects & 2097152i64) != 0
        && !(({
            let mut __comprehension_result_821: Vec<bool> = Vec::new();
            let __comprehension_source_820 = ((game).players.clone());
            for other in __comprehension_source_820.iter().cloned() {
                __comprehension_result_821.push({
                    let __needle = technology;
                    let __container = &(other).known_technologies;
                    __container.contains(&__needle)
                });
            }
            __comprehension_result_821
        })
        .into_iter()
        .any(|__value| __value)))
    {
        player.free_technologies = ((player).free_technologies)
            .checked_add(1i64)
            .ok_or("integer overflow")?;
    }
    ((player).known_technologies).insert(technology);
    if ({
        let mut __comprehension_result_823: Vec<bool> = Vec::new();
        let __comprehension_source_822 = ((&(&(game).scenario).rules).worker_jobs.clone());
        for job in __comprehension_source_822.iter().cloned() {
            __comprehension_result_823.push(
                ({
                    let __needle = crate::openciv3::worker_rules::improvement_for(&job)?;
                    let __container = &({
                        let __tuple_value = &((1i64, 2i64));
                        vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                    });
                    __container.contains(&__needle)
                } && ((job).prerequisite == technology)),
            );
        }
        __comprehension_result_823
    })
    .into_iter()
    .any(|__value| __value)
    {
        game.world = crate::openciv3::city_roads::connect_city_roads(
            &((game).world.clone()),
            &({
                let mut __comprehension_result_825: Vec<crate::openciv3::cities::City> = Vec::new();
                let __comprehension_source_824 = ((game).cities.clone());
                for city in __comprehension_source_824.iter().cloned() {
                    if ((city).owner == (player).civilization) {
                        __comprehension_result_825.push(city.clone());
                    }
                }
                __comprehension_result_825
            }),
            &(game).players,
            &(&(game).scenario).rules,
        )?;
        game.scenario.world = Some((game).world.clone());
        for mut knowledge in ((game).visibility.clone())
            .values()
            .cloned()
            .collect::<Vec<_>>()
        {
            crate::openciv3::visibility::TileKnowledge__observe(
                knowledge.clone(),
                &(game).world,
                &(knowledge).visible,
            )?;
        }
    }
    if ((((player).era).checked_add(1i64).ok_or("integer overflow")?
        < crate::openciv3::scenario_model::ScenarioDefinition__era_count(&(game).scenario)?)
        && ({
            let mut __comprehension_result_827: Vec<bool> = Vec::new();
            let __comprehension_source_826 = ((technologies.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>());
            for (index, item) in __comprehension_source_826.iter().cloned() {
                if ((item).era == (player).era) {
                    __comprehension_result_827.push(
                        ({
                            let __needle = index;
                            let __container = &(player).known_technologies;
                            __container.contains(&__needle)
                        } || ((item).effects & 131072i64) != 0),
                    );
                }
            }
            __comprehension_result_827
        })
        .into_iter()
        .all(|__value| __value))
    {
        player.era = ((player).era).checked_add(1i64).ok_or("integer overflow")?;
    }
    if ((player).researching.clone() == Some(technology)) {
        select_research(&game, player.clone(), &None)?;
    }
    player.research_queue = {
        let mut __comprehension_result_829: Vec<i64> = Vec::new();
        let __comprehension_source_828 = ((player).research_queue.clone());
        for item in __comprehension_source_828.iter().cloned() {
            if {
                let __needle = item;
                let __container = &(player).known_technologies;
                !__container.contains(&__needle)
            } {
                __comprehension_result_829.push(item);
            }
        }
        __comprehension_result_829
    };
    if start_queued {
        start_queued_research(&game, &player)?;
    }
    Ok((player, true))
}

// Python: openciv3/research.py:52
pub(crate) fn claim_free_technology(
    game: &crate::openciv3::game_state::GameState,
    mut player: crate::openciv3::players::Player,
    mut technology: i64,
) -> rt::Result<bool> {
    if !({
        let __compare_0 = 0i64;
        let __compare_1 = technology;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = ((&(&(&(game).scenario).rules).technologies).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) {
        return Err("Invalid technology index".to_string().into());
    }
    let mut tech: crate::openciv3::rules::Technology =
        rt::at(&(&(&(game).scenario).rules).technologies, technology)?;
    if (((player).free_technologies <= 0i64)
        || ({
            let __needle = technology;
            let __container = &(player).known_technologies;
            __container.contains(&__needle)
        } || ((tech).era > (player).era)))
    {
        return Ok(false);
    }
    player.free_technologies = ((player).free_technologies)
        .checked_sub(1i64)
        .ok_or("integer overflow")?;
    acquire_technology(game, player, technology, true)?;
    Ok(true)
}

/// Spend automated free advances, then choose the cheapest available technology.
// Python: openciv3/research.py:64
pub(crate) fn pick_ai_research(
    game: &crate::openciv3::game_state::GameState,
    mut player: crate::openciv3::players::Player,
    mut automated_human: bool,
) -> rt::Result<()> {
    if (((player).human && !(automated_human))
        || (crate::openciv3::players::Player__barbarian(&player)?
            || ((player).defeated || !((player).included))))
    {
        return Ok(());
    }
    while ((player).free_technologies > 0i64) {
        let mut available: Vec<i64> = available_technologies(game, &player)?;
        if (!(((available).len() as i64) != 0i64)
            || !(claim_free_technology(game, player.clone(), rt::at(&available, 0i64)?)?))
        {
            break;
        }
    }
    if ((&(player).researching).is_some()
        && match ((player).researching.clone()) {
            Some(__value) => {
                let __needle = __value;
                let __container = &(player).known_technologies;
                !__container.contains(&__needle)
            }
            None => true,
        })
    {
        return Ok(());
    }
    player.research_queue = {
        let mut __comprehension_result_831: Vec<i64> = Vec::new();
        let __comprehension_source_830 = ((player).research_queue.clone());
        for item in __comprehension_source_830.iter().cloned() {
            if {
                let __needle = item;
                let __container = &(player).known_technologies;
                !__container.contains(&__needle)
            } {
                __comprehension_result_831.push(item);
            }
        }
        __comprehension_result_831
    };
    select_research(game, player.clone(), &None)?;
    if start_queued_research(game, &player)? {
        return Ok(());
    }
    let mut available: Vec<i64> = available_technologies(game, &player)?;
    if (((available).len() as i64) != 0i64) {
        let mut target: i64 = rt::at(&available, 0i64)?;
        player.research_queue = {
            let mut __left: Vec<i64> = vec![target];
            let __right: Vec<i64> = {
                let mut __comprehension_result_833: Vec<i64> = Vec::new();
                let __comprehension_source_832 = ((player).research_queue.clone());
                for item in __comprehension_source_832.iter().cloned() {
                    if (item != target) {
                        __comprehension_result_833.push(item);
                    }
                }
                __comprehension_result_833
            };
            __left.extend(__right);
            __left
        };
        select_research(game, player, &(Some(target)))?;
    }
    Ok(())
}

/// Grant a trade's advances before spending AI bonuses or choosing research.
// Python: openciv3/research.py:86
pub(crate) fn acquire_technologies(
    game: &crate::openciv3::game_state::GameState,
    player: &crate::openciv3::players::Player,
    technologies: &[i64],
) -> rt::Result<()> {
    let mut targets: Vec<i64> = (technologies).iter().cloned().collect::<Vec<_>>();
    if ({
        let mut __comprehension_result_835: Vec<bool> = Vec::new();
        let __comprehension_source_834 = (targets.clone());
        for item in __comprehension_source_834.iter().cloned() {
            __comprehension_result_835.push(
                !({
                    let __compare_0 = 0i64;
                    let __compare_1 = item;
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
        __comprehension_result_835
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("Invalid technology index".to_string().into());
    }
    for mut target in targets {
        {
            let __call_836_0 = game;
            let __call_836_1 = (*player).clone();
            let __call_836_2 = target;
            let __call_836_3 = false;
            acquire_technology(__call_836_0, __call_836_1, __call_836_2, __call_836_3)
        }?;
    }
    start_queued_research(game, player)?;
    pick_ai_research(game, (*player).clone(), false)?;
    Ok(())
}

// Python: openciv3/research.py:97
pub(crate) fn advance_research(
    game: &crate::openciv3::game_state::GameState,
    mut player: crate::openciv3::players::Player,
    income: &Option<i64>,
) -> rt::Result<Option<i64>> {
    let (mut player, mut technology): (crate::openciv3::players::Player, Option<i64>) = {
        let __call_837_0 = game;
        let __call_837_1 = player;
        let __call_837_2 = (*income).clone();
        advance_research_result(__call_837_0, __call_837_1, __call_837_2)
    }?;
    Ok(technology)
}

/// Apply one science-income/update phase; return a completed technology ID.
///
/// The future turn coordinator must call this once, before city growth.
/// Completed human research waits for the selection popup; AI picks immediately.
// Python: openciv3/research.py:102
pub(crate) fn advance_research_result(
    game: &crate::openciv3::game_state::GameState,
    mut player: crate::openciv3::players::Player,
    mut income: Option<i64>,
) -> rt::Result<(crate::openciv3::players::Player, Option<i64>)> {
    if crate::openciv3::players::Player__barbarian(&player)? {
        return Ok((player, None));
    }
    let mut current_income: i64 =
        (crate::openciv3::player_economy::player_commerce(game, &player, None, None)?).beakers;
    if (income).is_none() {
        income = Some(current_income);
    }
    if ((*(income.clone()).as_ref().ok_or("expected a value")?).clone() < 0i64) {
        return Err("Research income cannot be negative".to_string().into());
    }
    player.beakers = ((player).beakers)
        .checked_add((*(income).as_ref().ok_or("expected a value")?).clone())
        .ok_or("integer overflow")?;
    let mut technology: Option<i64> = (player).researching.clone();
    if (technology).is_none() {
        return Ok((player, None));
    }
    player.turns_researched = ((player).turns_researched)
        .checked_add(1i64)
        .ok_or("integer overflow")?;
    if (current_income == 0i64) {
        return Ok((player, None));
    }
    let mut rules: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(&(&(game).scenario).rules).global_rules, 0i64)?;
    if ((player).turns_researched < (rules).minimum_research_time) {
        return Ok((player, None));
    }
    if ((remaining_research_cost(
        game,
        &player,
        (*(technology.clone()).as_ref().ok_or("expected a value")?).clone(),
    )? > 0i64)
        && ((player).turns_researched < (rules).maximum_research_time))
    {
        return Ok((player, None));
    }
    let (mut player, mut acquired): (crate::openciv3::players::Player, bool) = {
        let __call_838_0 = (*game).clone();
        let __call_838_1 = player.clone();
        let __call_838_2 = (*(technology.clone()).as_ref().ok_or("expected a value")?).clone();
        let __call_838_3 = false;
        acquire_technology_result(__call_838_0, __call_838_1, __call_838_2, __call_838_3)
    }?;
    player.researching = None;
    let mut scoring: Option<crate::openciv3::scenario_model::VictoryPointRules> =
        crate::openciv3::scenario_model::ScenarioDefinition__victory_point_rules(&(game).scenario)?;
    if ((scoring).is_some() && !((game).game_over)) {
        player.victory_points = ((player).victory_points)
            .checked_add(rt::int_floor_div(
                (((*(scoring).as_ref().ok_or("expected a value")?).clone()).research)
                    .checked_mul(
                        (0i64).max(
                            ({
                                let __source = &(&(&(game).scenario).rules).technologies;
                                let __key =
                                    (*(technology.clone()).as_ref().ok_or("expected a value")?)
                                        .clone();
                                &__source[rt::index(__source.len(), __key)?]
                            })
                            .cost,
                        ),
                    )
                    .ok_or("integer overflow")?,
                10i64,
            )?)
            .ok_or("integer overflow")?;
    }
    pick_ai_research(game, player.clone(), false)?;
    Ok((player, technology))
}

/// Build a prerequisite-first path, rejecting cycles and bad references.
// Python: openciv3/research.py:137
pub(crate) fn research_path(
    game: &crate::openciv3::game_state::GameState,
    player: &crate::openciv3::players::Player,
    mut technology: i64,
) -> rt::Result<Vec<i64>> {
    let mut technologies: Vec<crate::openciv3::rules::Technology> =
        (&(&(game).scenario).rules).technologies.clone();
    let mut result: Vec<i64> = vec![];
    let mut visiting: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
    let mut visited: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
    let mut pending: Vec<(i64, bool)> = vec![(technology, false)];
    while (((pending).len() as i64) != 0i64) {
        let (mut index, mut expanded): (i64, bool) = {
            let __key = -1i64;
            let __index = rt::index(pending.len(), __key)?;
            pending.remove(__index)
        };
        if !({
            let __compare_0 = 0i64;
            let __compare_1 = index;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = ((technologies).len() as i64);
                (__compare_1 < __compare_2)
            } else {
                false
            }
        }) {
            return Err("Invalid technology index in research path"
                .to_string()
                .into());
        }
        if ({
            let __needle = index;
            let __container = &(player).known_technologies;
            __container.contains(&__needle)
        } || {
            let __needle = index;
            let __container = &visited;
            __container.contains(&__needle)
        }) {
            continue;
        }
        if expanded {
            if !(visiting).remove(&(index)) {
                return Err("set.remove: missing item".into());
            };
            {
                visited.insert(index);
            };
            {
                result.push(index);
            };
            continue;
        }
        if {
            let __needle = index;
            let __container = &visiting;
            __container.contains(&__needle)
        } {
            return Err("Cyclic research prerequisites".to_string().into());
        }
        {
            visiting.insert(index);
        };
        {
            pending.push((index, true));
        };
        let mut prerequisites: Vec<i64> = ({
            let __source = &technologies;
            let __key = index;
            &__source[rt::index(__source.len(), __key)?]
        })
        .prerequisites
        .clone();
        if ({
            let mut __comprehension_result_840: Vec<bool> = Vec::new();
            let __comprehension_source_839 = (prerequisites.clone());
            for item in __comprehension_source_839.iter().cloned() {
                __comprehension_result_840.push(
                    !({
                        let __compare_0 = 0i64;
                        let __compare_1 = item;
                        if (__compare_0 <= __compare_1) {
                            let __compare_2 = ((technologies).len() as i64);
                            (__compare_1 < __compare_2)
                        } else {
                            false
                        }
                    }),
                );
            }
            __comprehension_result_840
        })
        .into_iter()
        .any(|__value| __value)
        {
            return Err("Invalid technology index in research path"
                .to_string()
                .into());
        }
        for mut prerequisite in {
            let mut __decorated: Vec<(i64, i64)> = Vec::new();
            for __item in (prerequisites).into_iter() {
                let item = __item;
                let __key = {
                    ({
                        let __source = &technologies;
                        let __key = item;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .cost
                };
                __decorated.push((__key, item));
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
        } {
            {
                pending.push((prerequisite, false));
            };
        }
    }
    Ok(result)
}

// Python: openciv3/research.py:169
pub(crate) fn start_queued_research(
    game: &crate::openciv3::game_state::GameState,
    player: &crate::openciv3::players::Player,
) -> rt::Result<bool> {
    if ((&(player).researching).is_some() || !(((&(player).research_queue).len() as i64) != 0i64)) {
        return Ok(false);
    }
    let mut head: i64 = rt::at(&(player).research_queue, 0i64)?;
    if {
        let __needle = head;
        let __container = &(available_technologies(game, player)?);
        !__container.contains(&__needle)
    } {
        return Ok(false);
    }
    select_research(game, (*player).clone(), &(Some(head)))?;
    Ok(true)
}

// Python: openciv3/research.py:179
pub(crate) fn queue_research(
    game: &crate::openciv3::game_state::GameState,
    mut player: crate::openciv3::players::Player,
    mut technology: i64,
    mut append: bool,
) -> rt::Result<()> {
    let mut path: Vec<i64> = research_path(game, &player, technology)?;
    if append {
        let mut queue: Vec<i64> = (&(player).research_queue)
            .iter()
            .cloned()
            .collect::<Vec<_>>();
        if ((&(player).researching).is_some()
            && match ((player).researching.clone()) {
                Some(__value) => {
                    let __needle = __value;
                    let __container = &queue;
                    !__container.contains(&__needle)
                }
                None => true,
            })
        {
            {
                let __key = 0i64;
                let __value = (*((player).researching.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone();
                let __length = queue.len() as i128;
                let __index = if __key < 0 {
                    (__length + __key as i128).max(0)
                } else {
                    (__key as i128).min(__length)
                };
                queue.insert(__index as usize, __value);
            };
        }
        {
            let __values = {
                let mut __comprehension_result_842: Vec<i64> = Vec::new();
                let __comprehension_source_841 = (path.clone());
                for item in __comprehension_source_841.iter().cloned() {
                    if {
                        let __needle = item;
                        let __container = &queue;
                        !__container.contains(&__needle)
                    } {
                        __comprehension_result_842.push(item);
                    }
                }
                __comprehension_result_842
            };
            queue.extend(__values);
        };
        player.research_queue = queue;
    } else {
        player.research_queue = path;
        select_research(game, player.clone(), &None)?;
    }
    start_queued_research(game, &player)?;
    Ok(())
}

// Python: openciv3/research.py:193
pub(crate) fn available_technologies(
    game: &crate::openciv3::game_state::GameState,
    player: &crate::openciv3::players::Player,
) -> rt::Result<Vec<i64>> {
    let mut technologies: Vec<crate::openciv3::rules::Technology> =
        (&(&(game).scenario).rules).technologies.clone();
    Ok({
        let mut __decorated: Vec<(i64, i64)> = Vec::new();
        for __item in ({
            let mut __comprehension_result_846: Vec<i64> = Vec::new();
            let __comprehension_source_843 = ((technologies.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>());
            for (index, tech) in __comprehension_source_843.iter().cloned() {
                if ({
                    let __needle = index;
                    let __container = &(player).known_technologies;
                    !__container.contains(&__needle)
                } && (((tech).era <= (player).era)
                    && ({
                        let mut __comprehension_result_845: Vec<bool> = Vec::new();
                        let __comprehension_source_844 = ((tech).prerequisites.clone());
                        for prerequisite in __comprehension_source_844.iter().cloned() {
                            __comprehension_result_845.push({
                                let __needle = prerequisite;
                                let __container = &(player).known_technologies;
                                __container.contains(&__needle)
                            });
                        }
                        __comprehension_result_845
                    })
                    .into_iter()
                    .all(|__value| __value)))
                {
                    __comprehension_result_846.push(index);
                }
            }
            __comprehension_result_846
        })
        .into_iter()
        {
            let index = __item;
            let __key = {
                ({
                    let __source = &technologies;
                    let __key = index;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .cost
            };
            __decorated.push((__key, index));
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
    })
}

// Python: openciv3/research.py:201
pub(crate) fn select_research(
    game: &crate::openciv3::game_state::GameState,
    mut player: crate::openciv3::players::Player,
    technology: &Option<i64>,
) -> rt::Result<()> {
    if ((technology).is_some()
        && match ((*technology).clone()) {
            Some(__value) => {
                let __needle = __value;
                let __container = &(available_technologies(game, &player)?);
                !__container.contains(&__needle)
            }
            None => true,
        })
    {
        return Err("Technology is not available to research".to_string().into());
    }
    player.researching = (*technology).clone();
    player.beakers = 0i64;
    player.turns_researched = 0i64;
    Ok(())
}

/// Preserve C# float intermediate rounding before flooring the cost.
// Python: openciv3/research.py:209
pub(crate) fn _single(mut value: f64) -> rt::Result<f64> {
    Ok(
        ((rt::struct_unpack_float(&(rt::struct_pack_float(value)?))?,))
            .0
            .clone(),
    )
}

// Python: openciv3/research.py:214
pub(crate) fn remaining_research_cost(
    game: &crate::openciv3::game_state::GameState,
    player: &crate::openciv3::players::Player,
    mut technology: i64,
) -> rt::Result<i64> {
    if !({
        let __compare_0 = 0i64;
        let __compare_1 = technology;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = ((&(&(&(game).scenario).rules).technologies).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) {
        return Err("Invalid technology index".to_string().into());
    }
    let mut size: Option<crate::openciv3::world_size::WorldSize> =
        (&(game).scenario).world_size.clone();
    if (size).is_none() {
        return Err("Research requires selected world-size rules"
            .to_string()
            .into());
    }
    let mut living: i64 = ({
        let mut __comprehension_result_848: Vec<bool> = Vec::new();
        let __comprehension_source_847 = ((game).players.clone());
        for other in __comprehension_source_847.iter().cloned() {
            __comprehension_result_848.push(
                ((other).included
                    && (!(crate::openciv3::players::Player__barbarian(&other)?)
                        && !((other).defeated))),
            );
        }
        __comprehension_result_848
    })
    .into_iter()
    .map(|value| value as i64)
    .sum::<i64>();
    if !(living != 0i64) {
        return Err("Research requires a living civilization".to_string().into());
    }
    let mut known: i64 = ({
        let mut __comprehension_result_850: Vec<bool> = Vec::new();
        let __comprehension_source_849 = ((game).players.clone());
        for other in __comprehension_source_849.iter().cloned() {
            __comprehension_result_850.push(
                ({
                    let __needle = ((player).civilization, (other).civilization);
                    let __container = &(&(game).diplomacy).relationships;
                    __container.contains_key(&__needle)
                } && {
                    let __needle = technology;
                    let __container = &(other).known_technologies;
                    __container.contains(&__needle)
                }),
            );
        }
        __comprehension_result_850
    })
    .into_iter()
    .map(|value| value as i64)
    .sum::<i64>();
    let mut difficulty: crate::openciv3::scenario_model::Difficulty =
        rt::at(&(&(game).scenario).difficulties, (game).difficulty)?;
    let mut factor: i64 = (if (player).human {
        (difficulty).human_cost_factor
    } else {
        (difficulty).ai_cost_factor
    });
    if (factor <= 0i64) {
        return Err("Research difficulty cost factor must be positive"
            .to_string()
            .into());
    }
    let mut knowledge: f64 = _single(rt::finite(
        ((1i64) as f64)
            - _single(rt::float_true_div(
                ((known) as f64),
                _single(rt::finite(((living) as f64) * 1.75f64)?)?,
            )?)?,
    )?)?;
    let mut base: i64 = ((((*(size).as_ref().ok_or("expected a value")?).clone()).tech_rate)
        .checked_mul(10i64)
        .ok_or("integer overflow")?)
    .checked_mul(
        ({
            let __source = &(&(&(game).scenario).rules).technologies;
            let __key = technology;
            &__source[rt::index(__source.len(), __key)?]
        })
        .cost,
    )
    .ok_or("integer overflow")?;
    let mut cost: f64 = _single(rt::float_true_div(
        _single(rt::finite(_single(((base) as f64))? * knowledge)?)?,
        (((factor).checked_mul(10i64).ok_or("integer overflow")?) as f64),
    )?)?;
    if ((player).researching.clone() == Some(technology)) {
        cost = _single(rt::finite(cost - (((player).beakers) as f64))?)?;
    }
    Ok((0i64).max(rt::floor(cost)?))
}

// Python: openciv3/research.py:237
pub(crate) fn estimate_research_turns(
    game: &crate::openciv3::game_state::GameState,
    player: &crate::openciv3::players::Player,
    mut technology: i64,
) -> rt::Result<Option<i64>> {
    let mut income: i64 =
        (crate::openciv3::player_economy::player_commerce(game, player, None, None)?).beakers;
    if (income == 0i64) {
        return Ok(None);
    }
    let mut rules: crate::openciv3::global_rules::GlobalRules =
        rt::at(&(&(&(game).scenario).rules).global_rules, 0i64)?;
    let mut remaining: i64 = remaining_research_cost(game, player, technology)?;
    let mut turns: i64 = rt::int_floor_div(
        ((remaining).checked_add(income).ok_or("integer overflow")?)
            .checked_sub(1i64)
            .ok_or("integer overflow")?,
        income,
    )?;
    Ok(Some(
        ((turns).min(
            ((rules).maximum_research_time)
                .checked_sub((player).turns_researched)
                .ok_or("integer overflow")?,
        ))
        .max(
            ((rules).minimum_research_time)
                .checked_sub((player).turns_researched)
                .ok_or("integer overflow")?,
        ),
    ))
}
