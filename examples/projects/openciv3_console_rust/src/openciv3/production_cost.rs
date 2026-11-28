use py2rust_service_runtime as rt;

// Python: openciv3/production_cost.py:18
pub(crate) fn cost_factor(
    mut human: bool,
    difficulty: &crate::openciv3::scenario_model::Difficulty,
) -> rt::Result<f64> {
    if human {
        return Ok(1.0f64);
    }
    if (((difficulty).human_cost_factor <= 0i64) || ((difficulty).ai_cost_factor < 0i64)) {
        return Err("Invalid difficulty production cost factor"
            .to_string()
            .into());
    }
    Ok(rt::int_true_div(
        (difficulty).ai_cost_factor,
        (difficulty).human_cost_factor,
    )?)
}

// Python: openciv3/production_cost.py:26
pub(crate) fn unit_cost(
    unit: &crate::openciv3::unit_rules::UnitPrototype,
    mut human: bool,
    difficulty: &crate::openciv3::scenario_model::Difficulty,
) -> rt::Result<i64> {
    rt::int_float(rt::finite(
        (((unit).shield_cost) as f64) * cost_factor(human, difficulty)?,
    )?)
}

// Python: openciv3/production_cost.py:30
pub(crate) fn building_cost(
    building: &crate::openciv3::building_rules::Building,
    mut human: bool,
    difficulty: &crate::openciv3::scenario_model::Difficulty,
    traits: &[String],
    mut city_count: i64,
    mut optimal_cities: i64,
    mut trait_discount: f64,
) -> rt::Result<i64> {
    let mut has_matching_trait: bool = ({
        let mut __comprehension_result_467: Vec<i64> = Vec::new();
        let __comprehension_source_466 = (traits.to_vec());
        for item in __comprehension_source_466.iter().cloned() {
            if {
                let __needle: &str = AsRef::<str>::as_ref(&item);
                let __container = {
                    static __CONSTANT_py__openciv3__production_cost__TRAIT_FLAGS:
                        std::sync::OnceLock<indexmap::IndexMap<String, i64>> =
                        std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__production_cost__TRAIT_FLAGS
                        .get()
                        .is_none()
                    {
                        let __constant_value = [
                            ("Militaristic".to_string(), 134217728i64),
                            ("Commercial".to_string(), 4294967296i64),
                            ("Expansionist".to_string(), 8589934592i64),
                            ("Scientific".to_string(), 2147483648i64),
                            ("Religious".to_string(), 17179869184i64),
                            ("Industrious".to_string(), 34359738368i64),
                            ("Agricultural".to_string(), 68719476736i64),
                            ("Seafaring".to_string(), 137438953472i64),
                        ]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>();
                        let _ = __CONSTANT_py__openciv3__production_cost__TRAIT_FLAGS
                            .set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__production_cost__TRAIT_FLAGS
                        .get()
                        .ok_or("missing module constant")?
                };
                __container.contains_key(__needle)
            } {
                __comprehension_result_467.push(
                    ((building).effects
                        & ({
                            static __CONSTANT_py__openciv3__production_cost__TRAIT_FLAGS:
                                std::sync::OnceLock<indexmap::IndexMap<String, i64>> =
                                std::sync::OnceLock::new();
                            if __CONSTANT_py__openciv3__production_cost__TRAIT_FLAGS
                                .get()
                                .is_none()
                            {
                                let __constant_value = [
                                    ("Militaristic".to_string(), 134217728i64),
                                    ("Commercial".to_string(), 4294967296i64),
                                    ("Expansionist".to_string(), 8589934592i64),
                                    ("Scientific".to_string(), 2147483648i64),
                                    ("Religious".to_string(), 17179869184i64),
                                    ("Industrious".to_string(), 34359738368i64),
                                    ("Agricultural".to_string(), 68719476736i64),
                                    ("Seafaring".to_string(), 137438953472i64),
                                ]
                                .into_iter()
                                .collect::<indexmap::IndexMap<_, _>>();
                                let _ = __CONSTANT_py__openciv3__production_cost__TRAIT_FLAGS
                                    .set(__constant_value);
                            }
                            __CONSTANT_py__openciv3__production_cost__TRAIT_FLAGS
                                .get()
                                .ok_or("missing module constant")?
                        })
                        .get(&item)
                        .ok_or("missing dict key")?
                        .clone()),
                );
            }
        }
        __comprehension_result_467
    })
    .into_iter()
    .any(|__value| __value != 0);
    let mut adjustment: f64 = (if has_matching_trait {
        trait_discount
    } else {
        1.0f64
    });
    if (((building).effects & 1i64) != 0i64) {
        if (optimal_cities <= 0i64) {
            return Err(
                "Palace production cost requires a positive optimal city count"
                    .to_string()
                    .into(),
            );
        }
        adjustment = rt::finite(
            adjustment
                * (((10i64).min((3i64).max(rt::int_floor_div(
                    (6i64).checked_mul(city_count).ok_or("integer overflow")?,
                    optimal_cities,
                )?))) as f64),
        )?;
    }
    rt::round_float(rt::finite(
        rt::finite(
            ((((building).cost)
                .checked_mul(10i64)
                .ok_or("integer overflow")?) as f64)
                * cost_factor(human, difficulty)?,
        )? * adjustment,
    )?)
}

// Python: openciv3/production_cost.py:42
pub(crate) fn city_building_cost(
    game: &crate::openciv3::game_state::GameState,
    city: &crate::openciv3::cities::City,
    building: &crate::openciv3::building_rules::Building,
) -> rt::Result<i64> {
    let mut scenario: crate::openciv3::scenario_model::ScenarioDefinition = (game).scenario.clone();
    let mut rules: Vec<crate::openciv3::global_rules::GlobalRules> =
        (&(scenario).rules).global_rules.clone();
    let mut discount: f64 = (if (((rules).len() as i64) != 0i64) {
        ({
            let __source = &rules;
            let __key = 0i64;
            &__source[rt::index(__source.len(), __key)?]
        })
        .building_discount_for_civ_traits
    } else {
        0.5f64
    });
    let mut size: Option<crate::openciv3::world_size::WorldSize> = (scenario).world_size.clone();
    Ok({
        let __call_468_0 = &((*building).clone());
        let __call_468_1 = ({
            let __source = &(game).players;
            let __key = (city).owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .human;
        let __call_468_2 = &(rt::at(&(scenario).difficulties, (game).difficulty)?);
        let __call_468_3 = &(({
            let __source = &(scenario).civilizations;
            let __key = (city).owner;
            &__source[rt::index(__source.len(), __key)?]
        })
        .traits
        .clone());
        let __call_468_4 = ({
            let mut __comprehension_result_470: Vec<bool> = Vec::new();
            let __comprehension_source_469 = ((game).cities.clone());
            for other in __comprehension_source_469.iter().cloned() {
                __comprehension_result_470.push(((other).owner == (city).owner));
            }
            __comprehension_result_470
        })
        .into_iter()
        .map(|value| value as i64)
        .sum::<i64>();
        let __call_468_5 = (if (size).is_some() {
            ((*(size.clone()).as_ref().ok_or("expected a value")?).clone()).optimal_cities
        } else {
            0i64
        });
        let __call_468_6 = discount;
        building_cost(
            __call_468_0,
            __call_468_1,
            __call_468_2,
            __call_468_3,
            __call_468_4,
            __call_468_5,
            __call_468_6,
        )
    }?)
}
