use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct HistoryRecord {
    pub(crate) date: i64,
    pub(crate) power: i64,
    pub(crate) score: i64,
    pub(crate) culture: i64,
    pub(crate) victory_points: i64,
}

// Python: openciv3/history.py:22
pub(crate) fn turn_score(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<i64> {
    let mut cities: Vec<crate::openciv3::cities::City> = {
        let mut __comprehension_result_366: Vec<crate::openciv3::cities::City> = Vec::new();
        let __comprehension_source_365 = ((game).cities.clone());
        for city in __comprehension_source_365.iter().cloned() {
            if ((city).owner == owner) {
                __comprehension_result_366.push(city.clone());
            }
        }
        __comprehension_result_366
    };
    let mut city_ids: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_368: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_367 = (cities.clone());
        for city in __comprehension_source_367.iter().cloned() {
            __comprehension_result_368.insert((city).id);
        }
        __comprehension_result_368
    };
    let mut knowledge: crate::openciv3::visibility::TileKnowledge = (&(game).visibility)
        .get(&(owner))
        .ok_or("missing dict key")?
        .clone();
    let mut territory: i64 = ({
        let mut __comprehension_result_370: Vec<bool> = Vec::new();
        let __comprehension_source_369 = ((&(game).world).tiles.clone());
        for tile in __comprehension_source_369.iter().cloned() {
            __comprehension_result_370.push(
                ({
                    let __needle = ((tile).x, (tile).y);
                    let __container = &(knowledge).known;
                    __container.contains(&__needle)
                } && (match (((game).ownership.clone())
                    .get(&(((tile).x, (tile).y)))
                    .cloned())
                {
                    Some(__value) => {
                        let __needle = __value;
                        let __container = &city_ids;
                        __container.contains(&__needle)
                    }
                    None => false,
                } && ((tile).base_terrain != 13i64))),
            );
        }
        __comprehension_result_370
    })
    .into_iter()
    .map(|value| value as i64)
    .sum::<i64>();
    let mut population: i64 = 0i64;
    for mut city in cities {
        for mut resident in (&(city).residents).iter() {
            if !(({
                let __source = &(&(&(game).scenario).rules).citizens;
                let __key = (resident).citizen_type;
                &__source[rt::index(__source.len(), __key)?]
            })
            .default_citizen)
            {
                population = (population).checked_add(1i64).ok_or("integer overflow")?;
            } else {
                if ((resident).mood == 0i64) {
                    population = (population).checked_add(2i64).ok_or("integer overflow")?;
                } else {
                    if ((resident).mood == 1i64) {
                        population = (population).checked_add(1i64).ok_or("integer overflow")?;
                    }
                }
            }
        }
    }
    Ok(((territory)
        .checked_add(population)
        .ok_or("integer overflow")?)
    .checked_mul(
        ((game).difficulty)
            .checked_add(1i64)
            .ok_or("integer overflow")?,
    )
    .ok_or("integer overflow")?)
}

// Python: openciv3/history.py:42
pub(crate) fn _single(mut value: f64) -> rt::Result<f64> {
    Ok(
        ((rt::struct_unpack_float(&(rt::struct_pack_float(value)?))?,))
            .0
            .clone(),
    )
}

/// Append the player’s score after city updates. Power retains its legacy placeholder.
// Python: openciv3/history.py:46
pub(crate) fn record_player_history(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<Option<HistoryRecord>> {
    if ((game).game_over || {
        let __needle = owner;
        let __container = &(game).history;
        !__container.contains_key(&__needle)
    }) {
        return Ok(None);
    }
    let mut records: Vec<HistoryRecord> = (&(game).history)
        .get(&(owner))
        .ok_or("missing dict key")?
        .clone();
    let mut last: Option<HistoryRecord> = (if (((records).len() as i64) != 0i64) {
        Some(rt::at(
            &records,
            (1i64).checked_neg().ok_or("integer overflow")?,
        )?)
    } else {
        None
    });
    let mut previous: i64 = (if (last).is_some() {
        ((*(last.clone()).as_ref().ok_or("expected a value")?).clone()).score
    } else {
        0i64
    });
    let mut delta: f64 = _single(rt::float_true_div(
        _single(rt::finite(
            _single((turn_score(game, owner)? as f64))? - _single((previous as f64))?,
        )?)?,
        _single(
            (((records).len() as i64)
                .checked_add(1i64)
                .ok_or("integer overflow")? as f64),
        )?,
    )?)?;
    let mut score: i64 = rt::floor(_single(rt::finite(_single((previous as f64))? + delta)?)?)?;
    let mut record: HistoryRecord = HistoryRecord {
        date: crate::openciv3::calendar::Calendar__raw(
            &(crate::openciv3::scenario_model::ScenarioOptions__calendar(
                &(&(game).scenario).options,
            )?),
            (game).turn,
        )?,
        power: (if (last).is_some() {
            ((*(last.clone()).as_ref().ok_or("expected a value")?).clone()).power
        } else {
            100i64
        }),
        score: score,
        culture: ({
            let mut __comprehension_result_372: Vec<i64> = Vec::new();
            let __comprehension_source_371 = ((game).cities.clone());
            for city in __comprehension_source_371.iter().cloned() {
                if ((city).owner == owner) {
                    __comprehension_result_372.push({
                        let __mapping = &(city).culture;
                        let __key = owner;
                        let __default = 0i64;
                        __mapping.get(&__key).cloned().unwrap_or(__default)
                    });
                }
            }
            __comprehension_result_372
        })
        .into_iter()
        .sum::<i64>(),
        victory_points: ({
            let __source = &(game).players;
            let __key = owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .victory_points,
    };
    {
        records.push(record.clone());
    };
    Ok(Some(record))
}
