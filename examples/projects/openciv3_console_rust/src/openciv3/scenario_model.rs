use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct Civilization {
    pub(crate) index: i64,
    pub(crate) name: String,
    pub(crate) noun: String,
    pub(crate) adjective: String,
    pub(crate) leader: String,
    pub(crate) leader_title: String,
    pub(crate) civilopedia_entry: String,
    pub(crate) city_names: Vec<String>,
    pub(crate) great_leaders: Vec<String>,
    pub(crate) scientific_leaders: Vec<String>,
    pub(crate) era_animations: Vec<(String, String)>,
    pub(crate) culture_group: i64,
    pub(crate) leader_gender: i64,
    pub(crate) civilization_gender: i64,
    pub(crate) aggression: i64,
    pub(crate) shunned_government: i64,
    pub(crate) favorite_government: i64,
    pub(crate) primary_color: i64,
    pub(crate) secondary_color: i64,
    pub(crate) starting_techs: Vec<i64>,
    pub(crate) traits: Vec<String>,
    pub(crate) governor_flags: Vec<u8>,
    pub(crate) plurality: i64,
    pub(crate) king_unit: i64,
    pub(crate) flavors: i64,
    pub(crate) diplomacy_text_index: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct Difficulty {
    pub(crate) name: String,
    pub(crate) content_citizens: i64,
    pub(crate) max_ai_anarchy_turns: i64,
    pub(crate) ai_defensive_units: i64,
    pub(crate) ai_offensive_units: i64,
    pub(crate) extra_start_unit_1: i64,
    pub(crate) extra_start_unit_2: i64,
    pub(crate) additional_free_support: i64,
    pub(crate) support_per_settlement: i64,
    pub(crate) barbarian_attack_bonus: i64,
    pub(crate) ai_cost_factor: i64,
    pub(crate) optimal_cities_percent: i64,
    pub(crate) ai_trade_rate: i64,
    pub(crate) corruption_percent: i64,
    pub(crate) military_law: i64,
    pub(crate) human_cost_factor: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct PlayerSlot {
    pub(crate) custom_civ_data: bool,
    pub(crate) human_allowed: bool,
    pub(crate) name: String,
    pub(crate) starting_units: Vec<(i64, i64)>,
    pub(crate) leader_gender: i64,
    pub(crate) starting_techs: Vec<i64>,
    pub(crate) difficulty: i64,
    pub(crate) era: i64,
    pub(crate) cash: i64,
    pub(crate) government: i64,
    pub(crate) civilization: i64,
    pub(crate) color: i64,
    pub(crate) skip_first_turn: bool,
    pub(crate) start_embassies: bool,
}

#[derive(Clone, PartialEq)]
pub(crate) struct ScenarioOptions {
    pub(crate) allowed_civilizations: Vec<i64>,
    pub(crate) mod_paths: Vec<String>,
    pub(crate) victory_flags: i64,
    pub(crate) start_year: i64,
    pub(crate) time_unit: i64,
    pub(crate) turn_limit: i64,
    pub(crate) alliance_ids: Vec<i64>,
    pub(crate) alliance_names: Vec<String>,
    pub(crate) alliance_wars: std::collections::BTreeSet<(i64, i64)>,
    pub(crate) alliance_victory_type: i64,
    pub(crate) map_visible: bool,
    pub(crate) start_month: i64,
    pub(crate) start_week: i64,
    pub(crate) time_scale: Vec<(i64, i64)>,
    pub(crate) start_day: i64,
    pub(crate) start_hour: i64,
    pub(crate) negative_label: String,
    pub(crate) positive_label: String,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct VictoryPointRules {
    pub(crate) limit: i64,
    pub(crate) wonder: i64,
    pub(crate) unit: i64,
    pub(crate) research: i64,
    pub(crate) city: i64,
    pub(crate) location: i64,
}

#[derive(Clone, PartialEq)]
pub(crate) struct ScenarioDefinition {
    pub(crate) source: String,
    pub(crate) scenario: crate::openciv3::scenario::Scenario,
    pub(crate) defaults: crate::openciv3::scenario::Scenario,
    pub(crate) civilizations: Vec<Civilization>,
    pub(crate) difficulties: Vec<Difficulty>,
    pub(crate) slots: Vec<PlayerSlot>,
    pub(crate) options: ScenarioOptions,
    pub(crate) assigned_civilizations: Vec<i64>,
    pub(crate) playable: Vec<Civilization>,
    pub(crate) seed: i64,
    pub(crate) world: Option<crate::openciv3::world::WorldMap>,
    pub(crate) rules: crate::openciv3::rules::RuleCatalog,
    pub(crate) selected_civilization: String,
    pub(crate) selected_difficulty: String,
    pub(crate) portrait_paths: indexmap::IndexMap<String, String>,
    pub(crate) world_size: Option<crate::openciv3::world_size::WorldSize>,
}

// Python: openciv3/scenario_model.py:55
pub(crate) fn Civilization__is_barbarian(self_: &Civilization) -> rt::Result<bool> {
    Ok(((self_).index == 0i64))
}

// Python: openciv3/scenario_model.py:59
pub(crate) fn Civilization__from_record(
    record: &crate::openciv3::binary::Record,
    mut index: i64,
    mut eras: i64,
) -> rt::Result<Civilization> {
    let mut cities_count: i64 = crate::openciv3::binary::Record__count(record, 4i64, 24i64)?;
    let mut cities: Vec<String> = ({
        let mut __comprehension_result_121: Vec<String> = Vec::new();
        let __comprehension_source_120 = ((0i64..cities_count).collect::<Vec<i64>>());
        for i in __comprehension_source_120.iter().cloned() {
            __comprehension_result_121.push(crate::openciv3::binary::Record__text(
                record,
                (8i64)
                    .checked_add((i).checked_mul(24i64).ok_or("integer overflow")?)
                    .ok_or("integer overflow")?,
                24i64,
            )?);
        }
        __comprehension_result_121
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut offset: i64 = (8i64)
        .checked_add(
            (cities_count)
                .checked_mul(24i64)
                .ok_or("integer overflow")?,
        )
        .ok_or("integer overflow")?;
    let mut leader_count: i64 = crate::openciv3::binary::Record__count(record, offset, 32i64)?;
    let mut great_leaders: Vec<String> = ({
        let mut __comprehension_result_123: Vec<String> = Vec::new();
        let __comprehension_source_122 = ((0i64..leader_count).collect::<Vec<i64>>());
        for i in __comprehension_source_122.iter().cloned() {
            __comprehension_result_123.push(crate::openciv3::binary::Record__text(
                record,
                ((offset).checked_add(4i64).ok_or("integer overflow")?)
                    .checked_add((i).checked_mul(32i64).ok_or("integer overflow")?)
                    .ok_or("integer overflow")?,
                32i64,
            )?);
        }
        __comprehension_result_123
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut text: i64 = ((offset).checked_add(4i64).ok_or("integer overflow")?)
        .checked_add(
            (leader_count)
                .checked_mul(32i64)
                .ok_or("integer overflow")?,
        )
        .ok_or("integer overflow")?;
    let mut animations: Vec<(String, String)> = ({
        let mut __comprehension_result_125: Vec<(String, String)> = Vec::new();
        let __comprehension_source_124 = ((0i64..eras).collect::<Vec<i64>>());
        for i in __comprehension_source_124.iter().cloned() {
            __comprehension_result_125.push((
                crate::openciv3::binary::Record__text(
                    record,
                    ((text).checked_add(208i64).ok_or("integer overflow")?)
                        .checked_add((i).checked_mul(520i64).ok_or("integer overflow")?)
                        .ok_or("integer overflow")?,
                    260i64,
                )?,
                crate::openciv3::binary::Record__text(
                    record,
                    ((text).checked_add(468i64).ok_or("integer overflow")?)
                        .checked_add((i).checked_mul(520i64).ok_or("integer overflow")?)
                        .ok_or("integer overflow")?,
                    260i64,
                )?,
            ));
        }
        __comprehension_result_125
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut attributes: i64 = ((text).checked_add(208i64).ok_or("integer overflow")?)
        .checked_add((eras).checked_mul(520i64).ok_or("integer overflow")?)
        .ok_or("integer overflow")?;
    let mut values: Vec<i64> = ({
        let mut __comprehension_result_127: Vec<i64> = Vec::new();
        let __comprehension_source_126 = ((0i64..13i64).collect::<Vec<i64>>());
        for i in __comprehension_source_126.iter().cloned() {
            __comprehension_result_127.push(crate::openciv3::binary::Record__integer(
                record,
                (attributes)
                    .checked_add((i).checked_mul(4i64).ok_or("integer overflow")?)
                    .ok_or("integer overflow")?,
            )?);
        }
        __comprehension_result_127
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut trait_flags: i64 = (rt::at(
        &(crate::openciv3::binary::Record__bytes(
            record,
            (attributes).checked_add(52i64).ok_or("integer overflow")?,
            1i64,
        )?),
        0i64,
    )? as i64);
    let mut scientists_count: i64 = crate::openciv3::binary::Record__count(
        record,
        (attributes).checked_add(88i64).ok_or("integer overflow")?,
        32i64,
    )?;
    let mut scientists: Vec<String> = ({
        let mut __comprehension_result_129: Vec<String> = Vec::new();
        let __comprehension_source_128 = ((0i64..scientists_count).collect::<Vec<i64>>());
        for i in __comprehension_source_128.iter().cloned() {
            __comprehension_result_129.push(crate::openciv3::binary::Record__text(
                record,
                ((attributes).checked_add(92i64).ok_or("integer overflow")?)
                    .checked_add((i).checked_mul(32i64).ok_or("integer overflow")?)
                    .ok_or("integer overflow")?,
                32i64,
            )?);
        }
        __comprehension_result_129
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    Ok(Civilization {
        index: index,
        name: crate::openciv3::binary::Record__text(
            record,
            (text).checked_add(128i64).ok_or("integer overflow")?,
            40i64,
        )?,
        noun: crate::openciv3::binary::Record__text(
            record,
            (text).checked_add(168i64).ok_or("integer overflow")?,
            40i64,
        )?,
        adjective: crate::openciv3::binary::Record__text(
            record,
            (text).checked_add(88i64).ok_or("integer overflow")?,
            40i64,
        )?,
        leader: crate::openciv3::binary::Record__text(record, text, 32i64)?,
        leader_title: crate::openciv3::binary::Record__text(
            record,
            (text).checked_add(32i64).ok_or("integer overflow")?,
            24i64,
        )?,
        civilopedia_entry: crate::openciv3::binary::Record__text(
            record,
            (text).checked_add(56i64).ok_or("integer overflow")?,
            32i64,
        )?,
        city_names: cities,
        great_leaders: great_leaders,
        scientific_leaders: scientists,
        era_animations: animations,
        culture_group: rt::at(&values, 0i64)?,
        leader_gender: rt::at(&values, 1i64)?,
        civilization_gender: rt::at(&values, 2i64)?,
        aggression: rt::at(&values, 3i64)?,
        shunned_government: rt::at(&values, 5i64)?,
        favorite_government: rt::at(&values, 6i64)?,
        primary_color: rt::at(&values, 7i64)?,
        secondary_color: rt::at(&values, 8i64)?,
        starting_techs: ({
            let mut __comprehension_result_131: Vec<i64> = Vec::new();
            let __comprehension_source_130 = (rt::list_slice(&values, 9i64, 13i64));
            for tech in __comprehension_source_130.iter().cloned() {
                if (tech >= 0i64) {
                    __comprehension_result_131.push(tech);
                }
            }
            __comprehension_result_131
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        traits: ({
            let mut __comprehension_result_133: Vec<String> = Vec::new();
            let __comprehension_source_132 = (({
                static __CONSTANT_py__openciv3__scenario_model__TRAITS: std::sync::OnceLock<
                    Vec<String>,
                > = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__scenario_model__TRAITS
                    .get()
                    .is_none()
                {
                    let __constant_value = vec![
                        "Militaristic".to_string(),
                        "Commercial".to_string(),
                        "Expansionist".to_string(),
                        "Scientific".to_string(),
                        "Religious".to_string(),
                        "Industrious".to_string(),
                        "Agricultural".to_string(),
                        "Seafaring".to_string(),
                    ];
                    let _ = __CONSTANT_py__openciv3__scenario_model__TRAITS.set(__constant_value);
                }
                __CONSTANT_py__openciv3__scenario_model__TRAITS
                    .get()
                    .ok_or("missing module constant")?
                    .clone()
            })
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>());
            for (bit, name) in __comprehension_source_132.iter().cloned() {
                if ((trait_flags & rt::int_lshift(1i64, bit)?) != 0i64) {
                    __comprehension_result_133.push(name.clone());
                }
            }
            __comprehension_result_133
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        governor_flags: crate::openciv3::binary::Record__bytes(
            record,
            (attributes).checked_add(56i64).ok_or("integer overflow")?,
            12i64,
        )?,
        plurality: crate::openciv3::binary::Record__integer(
            record,
            (attributes).checked_add(68i64).ok_or("integer overflow")?,
        )?,
        king_unit: crate::openciv3::binary::Record__integer(
            record,
            (attributes).checked_add(72i64).ok_or("integer overflow")?,
        )?,
        flavors: crate::openciv3::binary::Record__integer(
            record,
            (attributes).checked_add(76i64).ok_or("integer overflow")?,
        )?,
        diplomacy_text_index: crate::openciv3::binary::Record__integer(
            record,
            (attributes).checked_add(84i64).ok_or("integer overflow")?,
        )?,
    })
}

// Python: openciv3/scenario_model.py:104
pub(crate) fn Difficulty__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<Difficulty> {
    Ok({
        let __record_args: Vec<i64> = {
            let mut __comprehension_result_135: Vec<i64> = Vec::new();
            let __comprehension_source_134 = ((0i64..14i64).collect::<Vec<i64>>());
            for i in __comprehension_source_134.iter().cloned() {
                __comprehension_result_135.push(crate::openciv3::binary::Record__integer(
                    record,
                    (68i64)
                        .checked_add((i).checked_mul(4i64).ok_or("integer overflow")?)
                        .ok_or("integer overflow")?,
                )?);
            }
            __comprehension_result_135
        };
        if !(0..=15).contains(&__record_args.len()) {
            return Err("wrong dataclass argument count".into());
        }
        Difficulty {
            name: crate::openciv3::binary::Record__text(record, 4i64, 64i64)?,
            content_citizens: rt::at(&__record_args, 0 as i64)?,
            max_ai_anarchy_turns: rt::at(&__record_args, 1 as i64)?,
            ai_defensive_units: rt::at(&__record_args, 2 as i64)?,
            ai_offensive_units: rt::at(&__record_args, 3 as i64)?,
            extra_start_unit_1: rt::at(&__record_args, 4 as i64)?,
            extra_start_unit_2: rt::at(&__record_args, 5 as i64)?,
            additional_free_support: rt::at(&__record_args, 6 as i64)?,
            support_per_settlement: rt::at(&__record_args, 7 as i64)?,
            barbarian_attack_bonus: rt::at(&__record_args, 8 as i64)?,
            ai_cost_factor: rt::at(&__record_args, 9 as i64)?,
            optimal_cities_percent: rt::at(&__record_args, 10 as i64)?,
            ai_trade_rate: rt::at(&__record_args, 11 as i64)?,
            corruption_percent: rt::at(&__record_args, 12 as i64)?,
            military_law: rt::at(&__record_args, 13 as i64)?,
            human_cost_factor: if 14 < __record_args.len() {
                rt::at(&__record_args, 14 as i64)?
            } else {
                10i64
            },
        }
    })
}

// Python: openciv3/scenario_model.py:126
pub(crate) fn PlayerSlot__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<PlayerSlot> {
    let mut units_count: i64 = crate::openciv3::binary::Record__count(record, 52i64, 8i64)?;
    let mut units: Vec<(i64, i64)> = ({
        let mut __comprehension_result_137: Vec<(i64, i64)> = Vec::new();
        let __comprehension_source_136 = ((0i64..units_count).collect::<Vec<i64>>());
        for i in __comprehension_source_136.iter().cloned() {
            __comprehension_result_137.push((
                crate::openciv3::binary::Record__integer(
                    record,
                    (56i64)
                        .checked_add((i).checked_mul(8i64).ok_or("integer overflow")?)
                        .ok_or("integer overflow")?,
                )?,
                crate::openciv3::binary::Record__integer(
                    record,
                    (60i64)
                        .checked_add((i).checked_mul(8i64).ok_or("integer overflow")?)
                        .ok_or("integer overflow")?,
                )?,
            ));
        }
        __comprehension_result_137
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut offset: i64 = (56i64)
        .checked_add((units_count).checked_mul(8i64).ok_or("integer overflow")?)
        .ok_or("integer overflow")?;
    let mut tech_count: i64 = crate::openciv3::binary::Record__count(
        record,
        (offset).checked_add(4i64).ok_or("integer overflow")?,
        4i64,
    )?;
    let mut techs: Vec<i64> = ({
        let mut __comprehension_result_139: Vec<i64> = Vec::new();
        let __comprehension_source_138 = ((0i64..tech_count).collect::<Vec<i64>>());
        for i in __comprehension_source_138.iter().cloned() {
            __comprehension_result_139.push(crate::openciv3::binary::Record__integer(
                record,
                ((offset).checked_add(8i64).ok_or("integer overflow")?)
                    .checked_add((i).checked_mul(4i64).ok_or("integer overflow")?)
                    .ok_or("integer overflow")?,
            )?);
        }
        __comprehension_result_139
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut tail: i64 = ((offset).checked_add(8i64).ok_or("integer overflow")?)
        .checked_add((tech_count).checked_mul(4i64).ok_or("integer overflow")?)
        .ok_or("integer overflow")?;
    Ok(PlayerSlot {
        custom_civ_data: (crate::openciv3::binary::Record__integer(record, 4i64)? == 1i64),
        human_allowed: (crate::openciv3::binary::Record__integer(record, 8i64)? == 1i64),
        name: crate::openciv3::binary::Record__text(record, 12i64, 32i64)?,
        starting_units: units,
        leader_gender: crate::openciv3::binary::Record__integer(record, offset)?,
        starting_techs: techs,
        difficulty: crate::openciv3::binary::Record__integer(record, tail)?,
        era: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(4i64).ok_or("integer overflow")?,
        )?,
        cash: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(8i64).ok_or("integer overflow")?,
        )?,
        government: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(12i64).ok_or("integer overflow")?,
        )?,
        civilization: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(16i64).ok_or("integer overflow")?,
        )?,
        color: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(20i64).ok_or("integer overflow")?,
        )?,
        skip_first_turn: (crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(24i64).ok_or("integer overflow")?,
        )? == 1i64),
        start_embassies: ((rt::at(
            &(crate::openciv3::binary::Record__bytes(
                record,
                (tail).checked_add(32i64).ok_or("integer overflow")?,
                1i64,
            )?),
            0i64,
        )? as i64)
            == 1i64),
    })
}

// Python: openciv3/scenario_model.py:140
pub(crate) fn biq_game_flags(record: &crate::openciv3::binary::Record) -> rt::Result<i64> {
    let mut offset: i64 = (crate::openciv3::binary::Record__count(record, 12i64, 4i64)?)
        .checked_mul(4i64)
        .ok_or("integer overflow")?;
    rt::int_from_bytes(
        &(crate::openciv3::binary::Record__bytes(
            record,
            (16i64).checked_add(offset).ok_or("integer overflow")?,
            3i64,
        )?),
        "little",
    )
}

// Python: openciv3/scenario_model.py:167
pub(crate) fn ScenarioOptions__calendar(
    self_: &ScenarioOptions,
) -> rt::Result<crate::openciv3::calendar::Calendar> {
    Ok(crate::openciv3::calendar::Calendar____post_init__(
        &(crate::openciv3::calendar::Calendar {
            unit: (self_).time_unit,
            start_year: (self_).start_year,
            start_month: (self_).start_month,
            start_week: (self_).start_week,
            start_day: (self_).start_day,
            start_hour: (self_).start_hour,
            scale: (self_).time_scale.clone(),
            negative_label: (self_).negative_label.clone(),
            positive_label: (self_).positive_label.clone(),
        }),
    )?)
}

// Python: openciv3/scenario_model.py:175
pub(crate) fn ScenarioOptions__from_record(
    record: &crate::openciv3::binary::Record,
    mut civilization_count: i64,
) -> rt::Result<ScenarioOptions> {
    let mut count: i64 = crate::openciv3::binary::Record__count(record, 12i64, 4i64)?;
    let mut civs: Vec<i64> = (if (count != 0i64) {
        ({
            let mut __comprehension_result_141: Vec<i64> = Vec::new();
            let __comprehension_source_140 = ((0i64..count).collect::<Vec<i64>>());
            for i in __comprehension_source_140.iter().cloned() {
                __comprehension_result_141.push(crate::openciv3::binary::Record__integer(
                    record,
                    (16i64)
                        .checked_add((i).checked_mul(4i64).ok_or("integer overflow")?)
                        .ok_or("integer overflow")?,
                )?);
            }
            __comprehension_result_141
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>()
    } else {
        ((1i64..civilization_count).collect::<Vec<i64>>())
            .iter()
            .cloned()
            .collect::<Vec<_>>()
    });
    if ({
        let mut __comprehension_result_143: Vec<bool> = Vec::new();
        let __comprehension_source_142 = (civs.clone());
        for civ in __comprehension_source_142.iter().cloned() {
            __comprehension_result_143.push(((civ < 0i64) || (civ >= civilization_count)));
        }
        __comprehension_result_143
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("GAME contains an out-of-range civilization"
            .to_string()
            .into());
    }
    let mut offset: i64 = (count).checked_mul(4i64).ok_or("integer overflow")?;
    let mut search: String = crate::openciv3::binary::Record__text(
        record,
        (120i64).checked_add(offset).ok_or("integer overflow")?,
        5200i64,
    )?;
    let mut alliances: Vec<i64> = ({
        let mut __comprehension_result_145: Vec<i64> = Vec::new();
        let __comprehension_source_144 = ((0i64..count).collect::<Vec<i64>>());
        for i in __comprehension_source_144.iter().cloned() {
            __comprehension_result_145.push(crate::openciv3::binary::Record__integer(
                record,
                ((5320i64).checked_add(offset).ok_or("integer overflow")?)
                    .checked_add((i).checked_mul(4i64).ok_or("integer overflow")?)
                    .ok_or("integer overflow")?,
            )?);
        }
        __comprehension_result_145
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    if ({
        let mut __comprehension_result_147: Vec<bool> = Vec::new();
        let __comprehension_source_146 = (alliances.clone());
        for alliance in __comprehension_source_146.iter().cloned() {
            __comprehension_result_147.push(
                !({
                    let __compare_0 = 0i64;
                    let __compare_1 = alliance;
                    if (__compare_0 <= __compare_1) {
                        let __compare_2 = 4i64;
                        (__compare_1 <= __compare_2)
                    } else {
                        false
                    }
                }),
            );
        }
        __comprehension_result_147
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("GAME contains an invalid alliance ID".to_string().into());
    }
    let mut tail: i64 = (count).checked_mul(8i64).ok_or("integer overflow")?;
    let mut names: Vec<String> = ({
        let mut __comprehension_result_149: Vec<String> = Vec::new();
        let __comprehension_source_148 = ((0i64..5i64).collect::<Vec<i64>>());
        for i in __comprehension_source_148.iter().cloned() {
            __comprehension_result_149.push(crate::openciv3::binary::Record__text(
                record,
                ((5373i64).checked_add(tail).ok_or("integer overflow")?)
                    .checked_add((i).checked_mul(256i64).ok_or("integer overflow")?)
                    .ok_or("integer overflow")?,
                256i64,
            )?);
        }
        __comprehension_result_149
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut wars: std::collections::BTreeSet<(i64, i64)> = {
        let mut __result: std::collections::BTreeSet<(i64, i64)> =
            std::collections::BTreeSet::new();
        for __item in ({
            let mut __comprehension_result_152: std::collections::BTreeSet<(i64, i64)> =
                std::collections::BTreeSet::new();
            let __comprehension_source_150 = ((1i64..5i64).collect::<Vec<i64>>());
            for a in __comprehension_source_150.iter().cloned() {
                let __comprehension_source_151 = ((1i64..5i64).collect::<Vec<i64>>());
                for b in __comprehension_source_151.iter().cloned() {
                    if ((a != b)
                        && (crate::openciv3::binary::Record__integer(
                            record,
                            ((6653i64).checked_add(tail).ok_or("integer overflow")?)
                                .checked_add(
                                    (((a).checked_mul(5i64).ok_or("integer overflow")?)
                                        .checked_add(b)
                                        .ok_or("integer overflow")?)
                                    .checked_mul(4i64)
                                    .ok_or("integer overflow")?,
                                )
                                .ok_or("integer overflow")?,
                        )?) != 0)
                    {
                        __comprehension_result_152.insert(((a).min(b), (a).max(b)));
                    }
                }
            }
            __comprehension_result_152
        })
        .into_iter()
        {
            __result.insert(__item);
        }
        __result
    };
    Ok(ScenarioOptions {
        allowed_civilizations: civs,
        mod_paths: ({
            let mut __comprehension_result_154: Vec<String> = Vec::new();
            let __comprehension_source_153 = (rt::str_split(&search, ";")?);
            for path in __comprehension_source_153.iter().cloned() {
                if (((rt::str_strip(&path)).chars().count() as i64) != 0i64) {
                    __comprehension_result_154.push(rt::str_strip(&path));
                }
            }
            __comprehension_result_154
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        victory_flags: biq_game_flags(record)?,
        start_year: crate::openciv3::binary::Record__integer(
            record,
            (52i64).checked_add(offset).ok_or("integer overflow")?,
        )?,
        time_unit: crate::openciv3::binary::Record__integer(
            record,
            (40i64).checked_add(offset).ok_or("integer overflow")?,
        )?,
        turn_limit: crate::openciv3::binary::Record__integer(
            record,
            (60i64).checked_add(offset).ok_or("integer overflow")?,
        )?,
        alliance_ids: alliances,
        alliance_names: names,
        alliance_wars: wars,
        alliance_victory_type: crate::openciv3::binary::Record__integer(
            record,
            (6753i64).checked_add(tail).ok_or("integer overflow")?,
        )?,
        map_visible: ((rt::at(
            &(crate::openciv3::binary::Record__bytes(
                record,
                (7315i64).checked_add(tail).ok_or("integer overflow")?,
                1i64,
            )?),
            0i64,
        )? as i64)
            == 1i64),
        start_month: crate::openciv3::binary::Record__integer(
            record,
            (44i64).checked_add(offset).ok_or("integer overflow")?,
        )?,
        start_week: crate::openciv3::binary::Record__integer(
            record,
            (48i64).checked_add(offset).ok_or("integer overflow")?,
        )?,
        time_scale: ({
            let mut __comprehension_result_156: Vec<(i64, i64)> = Vec::new();
            let __comprehension_source_155 = ((0i64..7i64).collect::<Vec<i64>>());
            for i in __comprehension_source_155.iter().cloned() {
                __comprehension_result_156.push((
                    crate::openciv3::binary::Record__integer(
                        record,
                        ((64i64).checked_add(offset).ok_or("integer overflow")?)
                            .checked_add((i).checked_mul(4i64).ok_or("integer overflow")?)
                            .ok_or("integer overflow")?,
                    )?,
                    crate::openciv3::binary::Record__integer(
                        record,
                        ((92i64).checked_add(offset).ok_or("integer overflow")?)
                            .checked_add((i).checked_mul(4i64).ok_or("integer overflow")?)
                            .ok_or("integer overflow")?,
                    )?,
                ));
            }
            __comprehension_result_156
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        start_day: 1i64,
        start_hour: 12i64,
        negative_label: "BC".to_string(),
        positive_label: "AD".to_string(),
    })
}

/// Resolve the owners of colonies placed in a BIQ.
// Python: openciv3/scenario_model.py:226
pub(crate) fn ScenarioDefinition__colony_owners(
    self_: &ScenarioDefinition,
    world: &crate::openciv3::world::WorldMap,
) -> rt::Result<indexmap::IndexMap<(i64, i64), i64>> {
    if ((rt::casefold(&(rt::path_suffix(&(self_).source)))).as_str() != ".biq") {
        return Ok([].into_iter().collect::<indexmap::IndexMap<_, _>>());
    }
    let mut owners: indexmap::IndexMap<(i64, i64), i64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut for_target_231_8 in ({
        let __mapping = &(&(self_).scenario).sections;
        let __key = "CLNY".to_string();
        let __default = vec![];
        __mapping.get(&__key).cloned().unwrap_or(__default)
    })
    .into_iter()
    .enumerate()
    .map(|(__index, __value)| (__index as i64 + 0i64, __value))
    .collect::<Vec<_>>()
    {
        let (mut index, mut raw): (i64, Vec<u8>) = for_target_231_8;
        let mut record: crate::openciv3::binary::Record = crate::openciv3::binary::Record {
            data: raw.clone(),
            section: "CLNY".to_string(),
            encoding: (&(self_).scenario).encoding.clone(),
        };
        let mut tile: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(
                &((*world).clone()),
                crate::openciv3::binary::Record__integer(&record, 12i64)?,
                crate::openciv3::binary::Record__integer(&record, 16i64)?,
            )?;
        if ((tile).is_none()
            || (((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).colony != index))
        {
            continue;
        }
        let mut owner: Option<i64> = crate::openciv3::world::resolve_owner(
            crate::openciv3::binary::Record__integer(&record, 4i64)?,
            crate::openciv3::binary::Record__integer(&record, 8i64)?,
            &((self_).assigned_civilizations.clone()),
            ((&(self_).civilizations).len() as i64),
        )?;
        if (owner).is_some() {
            {
                let __value = (*(owner).as_ref().ok_or("expected a value")?).clone();
                let __key = (
                    ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                    ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
                );
                owners.insert(__key, __value);
            }
        }
    }
    Ok(owners)
}

// Python: openciv3/scenario_model.py:242
pub(crate) fn ScenarioDefinition__era_identifier(
    self_: &ScenarioDefinition,
    mut era: i64,
) -> rt::Result<String> {
    let mut source: crate::openciv3::scenario::Scenario = (if {
        let __needle: &str = AsRef::<str>::as_ref("ERAS");
        let __container = &(&(self_).scenario).sections;
        __container.contains_key(__needle)
    } {
        (self_).scenario.clone()
    } else {
        (self_).defaults.clone()
    });
    let mut eras: Vec<Vec<u8>> = {
        let __mapping = &(source).sections;
        let __key = "ERAS".to_string();
        let __default = vec![];
        __mapping.get(&__key).cloned().unwrap_or(__default)
    };
    if (!(((eras).len() as i64) != 0i64) && {
        let __compare_0 = 0i64;
        let __compare_1 = era;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = {
                let _ = {
                    static __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS:
                        std::sync::OnceLock<(String, String, String, String)> =
                        std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS
                        .get()
                        .is_none()
                    {
                        let __constant_value = (
                            "ERAS_Ancient_Times".to_string(),
                            "ERAS_Middle_Ages".to_string(),
                            "ERAS_Industrial_Age".to_string(),
                            "ERAS_Modern_Era".to_string(),
                        );
                        let _ = __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS
                            .set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS
                        .get()
                        .ok_or("missing module constant")?
                };
                4i64
            };
            (__compare_1 < __compare_2)
        } else {
            false
        }
    }) {
        return Ok(rt::at(
            &({
                let __tuple_value = {
                    static __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS:
                        std::sync::OnceLock<(String, String, String, String)> =
                        std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS
                        .get()
                        .is_none()
                    {
                        let __constant_value = (
                            "ERAS_Ancient_Times".to_string(),
                            "ERAS_Middle_Ages".to_string(),
                            "ERAS_Industrial_Age".to_string(),
                            "ERAS_Modern_Era".to_string(),
                        );
                        let _ = __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS
                            .set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS
                        .get()
                        .ok_or("missing module constant")?
                };
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                    __tuple_value.3.clone(),
                ]
            }),
            era,
        )?);
    }
    Ok((if {
        let __compare_0 = 0i64;
        let __compare_1 = era;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = ((eras).len() as i64);
            (__compare_1 < __compare_2)
        } else {
            false
        }
    } {
        crate::openciv3::binary::Record__text(
            &(crate::openciv3::binary::Record {
                data: rt::at(&eras, era)?,
                section: "ERAS".to_string(),
                encoding: (source).encoding.clone(),
            }),
            68i64,
            32i64,
        )?
    } else {
        String::new()
    }))
}

// Python: openciv3/scenario_model.py:250
pub(crate) fn ScenarioDefinition__domination_limits(
    self_: &ScenarioDefinition,
) -> rt::Result<(i64, i64)> {
    let mut source: crate::openciv3::scenario::Scenario = (if {
        let __needle: &str = AsRef::<str>::as_ref("GAME");
        let __container = &(&(self_).scenario).sections;
        __container.contains_key(__needle)
    } {
        (self_).scenario.clone()
    } else {
        (self_).defaults.clone()
    });
    let mut rows: Vec<Vec<u8>> = {
        let __mapping = &(source).sections;
        let __key = "GAME".to_string();
        let __default = vec![];
        __mapping.get(&__key).cloned().unwrap_or(__default)
    };
    if !(((rows).len() as i64) != 0i64) {
        return Ok((66i64, 66i64));
    }
    let mut record: crate::openciv3::binary::Record = crate::openciv3::binary::Record {
        data: rt::at(&rows, 0i64)?,
        section: "GAME".to_string(),
        encoding: (source).encoding.clone(),
    };
    if (crate::openciv3::binary::Record__integer(&record, 8i64)? != 0i64) {
        return Ok((66i64, 66i64));
    }
    let mut offset: i64 = (crate::openciv3::binary::Record__count(&record, 12i64, 4i64)?)
        .checked_mul(8i64)
        .ok_or("integer overflow")?;
    let (mut area, mut population): (i64, i64) = (
        crate::openciv3::binary::Record__integer(
            &record,
            (5336i64).checked_add(offset).ok_or("integer overflow")?,
        )?,
        crate::openciv3::binary::Record__integer(
            &record,
            (5340i64).checked_add(offset).ok_or("integer overflow")?,
        )?,
    );
    Ok((
        (if {
            let __compare_0 = 1i64;
            let __compare_1 = area;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = 100i64;
                (__compare_1 <= __compare_2)
            } else {
                false
            }
        } {
            area
        } else {
            66i64
        }),
        (if {
            let __compare_0 = 1i64;
            let __compare_1 = population;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = 100i64;
                (__compare_1 <= __compare_2)
            } else {
                false
            }
        } {
            population
        } else {
            66i64
        }),
    ))
}

// Python: openciv3/scenario_model.py:264
pub(crate) fn ScenarioDefinition__victory_point_rules(
    self_: &ScenarioDefinition,
) -> rt::Result<Option<VictoryPointRules>> {
    if !(((&(self_).options).victory_flags
        & (rt::int_lshift(1i64, 13i64)? | rt::int_lshift(1i64, 16i64)?))
        != 0i64)
    {
        return Ok(None);
    }
    let mut source: crate::openciv3::scenario::Scenario = (if {
        let __needle: &str = AsRef::<str>::as_ref("GAME");
        let __container = &(&(self_).scenario).sections;
        __container.contains_key(__needle)
    } {
        (self_).scenario.clone()
    } else {
        (self_).defaults.clone()
    });
    let mut rows: Vec<Vec<u8>> = {
        let __mapping = &(source).sections;
        let __key = "GAME".to_string();
        let __default = vec![];
        __mapping.get(&__key).cloned().unwrap_or(__default)
    };
    if !(((rows).len() as i64) != 0i64) {
        return Ok(Some(VictoryPointRules {
            limit: 50000i64,
            wonder: 10i64,
            unit: 10i64,
            research: 5i64,
            city: 100i64,
            location: 25i64,
        }));
    }
    let mut record: crate::openciv3::binary::Record = crate::openciv3::binary::Record {
        data: rt::at(&rows, 0i64)?,
        section: "GAME".to_string(),
        encoding: (source).encoding.clone(),
    };
    if (crate::openciv3::binary::Record__integer(&record, 8i64)? != 0i64) {
        return Ok(Some(VictoryPointRules {
            limit: 50000i64,
            wonder: 10i64,
            unit: 10i64,
            research: 5i64,
            city: 100i64,
            location: 25i64,
        }));
    }
    let mut offset: i64 = (crate::openciv3::binary::Record__count(&record, 12i64, 4i64)?)
        .checked_mul(8i64)
        .ok_or("integer overflow")?;
    let mut limit: i64 = crate::openciv3::binary::Record__integer(
        &record,
        (5320i64).checked_add(offset).ok_or("integer overflow")?,
    )?;
    Ok(Some({
        let __record_args: Vec<i64> = {
            let mut __comprehension_result_158: Vec<i64> = Vec::new();
            let __comprehension_source_157 = (rt::range_values(5344i64, 5364i64, 4i64)?);
            for field in __comprehension_source_157.iter().cloned() {
                __comprehension_result_158.push((0i64).max(
                    crate::openciv3::binary::Record__integer(
                        &record,
                        (field).checked_add(offset).ok_or("integer overflow")?,
                    )?,
                ));
            }
            __comprehension_result_158
        };
        if !(0..=5).contains(&__record_args.len()) {
            return Err("wrong dataclass argument count".into());
        }
        VictoryPointRules {
            limit: (if (limit > 0i64) {
                limit
            } else {
                (VictoryPointRules {
                    limit: 50000i64,
                    wonder: 10i64,
                    unit: 10i64,
                    research: 5i64,
                    city: 100i64,
                    location: 25i64,
                })
                .limit
            }),
            wonder: if 0 < __record_args.len() {
                rt::at(&__record_args, 0 as i64)?
            } else {
                10i64
            },
            unit: if 1 < __record_args.len() {
                rt::at(&__record_args, 1 as i64)?
            } else {
                10i64
            },
            research: if 2 < __record_args.len() {
                rt::at(&__record_args, 2 as i64)?
            } else {
                5i64
            },
            city: if 3 < __record_args.len() {
                rt::at(&__record_args, 3 as i64)?
            } else {
                100i64
            },
            location: if 4 < __record_args.len() {
                rt::at(&__record_args, 4 as i64)?
            } else {
                25i64
            },
        }
    }))
}

// Python: openciv3/scenario_model.py:282
pub(crate) fn ScenarioDefinition__city_elimination_limit(
    self_: &ScenarioDefinition,
) -> rt::Result<i64> {
    let mut source: crate::openciv3::scenario::Scenario = (if {
        let __needle: &str = AsRef::<str>::as_ref("GAME");
        let __container = &(&(self_).scenario).sections;
        __container.contains_key(__needle)
    } {
        (self_).scenario.clone()
    } else {
        (self_).defaults.clone()
    });
    let mut rows: Vec<Vec<u8>> = {
        let __mapping = &(source).sections;
        let __key = "GAME".to_string();
        let __default = vec![];
        __mapping.get(&__key).cloned().unwrap_or(__default)
    };
    if !(((rows).len() as i64) != 0i64) {
        return Ok(1i64);
    }
    let mut record: crate::openciv3::binary::Record = crate::openciv3::binary::Record {
        data: rt::at(&rows, 0i64)?,
        section: "GAME".to_string(),
        encoding: (source).encoding.clone(),
    };
    if (crate::openciv3::binary::Record__integer(&record, 8i64)? != 0i64) {
        return Ok(1i64);
    }
    Ok((1i64).max(crate::openciv3::binary::Record__integer(
        &(record.clone()),
        (5324i64)
            .checked_add(
                (crate::openciv3::binary::Record__count(&record, 12i64, 4i64)?)
                    .checked_mul(8i64)
                    .ok_or("integer overflow")?,
            )
            .ok_or("integer overflow")?,
    )?))
}

/// Return the single-city and empire-wide cultural victory thresholds.
// Python: openciv3/scenario_model.py:293
pub(crate) fn ScenarioDefinition__cultural_limits(
    self_: &ScenarioDefinition,
) -> rt::Result<(i64, i64)> {
    let mut source: crate::openciv3::scenario::Scenario = (if {
        let __needle: &str = AsRef::<str>::as_ref("GAME");
        let __container = &(&(self_).scenario).sections;
        __container.contains_key(__needle)
    } {
        (self_).scenario.clone()
    } else {
        (self_).defaults.clone()
    });
    let mut rows: Vec<Vec<u8>> = {
        let __mapping = &(source).sections;
        let __key = "GAME".to_string();
        let __default = vec![];
        __mapping.get(&__key).cloned().unwrap_or(__default)
    };
    if (((rows).len() as i64) != 0i64) {
        let mut record: crate::openciv3::binary::Record = crate::openciv3::binary::Record {
            data: rt::at(&rows, 0i64)?,
            section: "GAME".to_string(),
            encoding: (source).encoding.clone(),
        };
        if !(crate::openciv3::binary::Record__integer(&record, 8i64)? != 0i64) {
            let mut offset: i64 = (crate::openciv3::binary::Record__count(&record, 12i64, 4i64)?)
                .checked_mul(8i64)
                .ok_or("integer overflow")?;
            let (mut city, mut empire): (i64, i64) = (
                crate::openciv3::binary::Record__integer(
                    &record,
                    (5328i64).checked_add(offset).ok_or("integer overflow")?,
                )?,
                crate::openciv3::binary::Record__integer(
                    &record,
                    (5332i64).checked_add(offset).ok_or("integer overflow")?,
                )?,
            );
            if ((city > 0i64) && (empire > 0i64)) {
                return Ok((city, empire));
            }
        }
    }
    source = (if {
        let __needle: &str = AsRef::<str>::as_ref("WSIZ");
        let __container = &(&(self_).scenario).sections;
        __container.contains_key(__needle)
    } {
        (self_).scenario.clone()
    } else {
        (self_).defaults.clone()
    });
    let mut sizes: Vec<Vec<u8>> = {
        let __mapping = &(source).sections;
        let __key = "WSIZ".to_string();
        let __default = vec![];
        __mapping.get(&__key).cloned().unwrap_or(__default)
    };
    if (((sizes).len() as i64) == 5i64) {
        for mut for_target_307_12 in {
            let __left = sizes;
            let __right = {
                let __tuple_value = &((60000i64, 80000i64, 100000i64, 130000i64, 160000i64));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                    __tuple_value.3.clone(),
                    __tuple_value.4.clone(),
                ]
            };
            if true && __left.len() != __right.len() {
                return Err("zip() argument lengths differ".into());
            }
            let mut __result: Vec<(Vec<u8>, i64)> = Vec::new();
            let __length = __left.len().min(__right.len());
            let mut __left_iter = __left.into_iter();
            let mut __right_iter = __right.into_iter();
            for __index in 0..__length {
                __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
            }
            __result
        } {
            let (mut row, mut limit): (Vec<u8>, i64) = for_target_307_12;
            if ((self_).world_size.clone()
                == Some(crate::openciv3::world_size::WorldSize__from_record(
                    &(crate::openciv3::binary::Record {
                        data: row.clone(),
                        section: "WSIZ".to_string(),
                        encoding: (source).encoding.clone(),
                    }),
                )?))
            {
                return Ok((20000i64, limit));
            }
        }
    }
    let mut size_name: String = (if (&(self_).world_size).is_some() {
        rt::casefold(
            &(((*((self_).world_size.clone())
                .as_ref()
                .ok_or("expected a value")?)
            .clone())
            .name
            .clone()),
        )
    } else {
        String::new()
    });
    Ok((20000i64, {
        let __mapping = [
            ("tiny".to_string(), 60000i64),
            ("small".to_string(), 80000i64),
            ("large".to_string(), 130000i64),
            ("huge".to_string(), 160000i64),
        ]
        .into_iter()
        .collect::<indexmap::IndexMap<_, _>>();
        let __key = size_name;
        let __default = 100000i64;
        __mapping.get(&__key).cloned().unwrap_or(__default)
    }))
}

// Python: openciv3/scenario_model.py:314
pub(crate) fn ScenarioDefinition__era_count(self_: &ScenarioDefinition) -> rt::Result<i64> {
    let mut eras: Option<Vec<Vec<u8>>> = ((&(self_).scenario).sections.clone())
        .get(&("ERAS".to_string()))
        .cloned();
    if (eras).is_none() {
        eras = ((&(self_).defaults).sections.clone())
            .get(&("ERAS".to_string()))
            .cloned();
    }
    if (eras).is_some() {
        return Ok((((*(eras).as_ref().ok_or("expected a value")?).clone()).len() as i64));
    }
    Ok(('__extreme: {
        let __values = &({
            let mut __comprehension_result_160: Vec<i64> = Vec::new();
            let __comprehension_source_159 = ((&(self_).rules).technologies.clone());
            for technology in __comprehension_source_159.iter().cloned() {
                __comprehension_result_160.push((technology).era);
            }
            __comprehension_result_160
        });
        let mut __items = __values.iter();
        let Some(mut __best) = __items.next() else {
            break '__extreme 0i64;
        };
        let mut __best_key = {
            let extreme_item = (*__best).clone();
            extreme_item
        };
        for __candidate in __items {
            let __key = {
                let extreme_item = (*__candidate).clone();
                extreme_item
            };
            if __key > __best_key {
                __best = __candidate;
                __best_key = __key;
            }
        }
        (*__best).clone()
    })
    .checked_add(1i64)
    .ok_or("integer overflow")?)
}

// Python: openciv3/scenario_model.py:322
pub(crate) fn ScenarioDefinition__select(
    mut self_: ScenarioDefinition,
    civilization: &str,
    difficulty: &str,
) -> rt::Result<()> {
    if {
        let __needle = civilization.to_owned();
        let __container = &({
            let mut __comprehension_result_162: std::collections::BTreeSet<String> =
                std::collections::BTreeSet::new();
            let __comprehension_source_161 = ((self_).playable.clone());
            for civ in __comprehension_source_161.iter().cloned() {
                __comprehension_result_162.insert((civ).name.clone());
            }
            __comprehension_result_162
        });
        !__container.contains(&__needle)
    } {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Civilization is not human-playable: ".to_string(),
                (civilization.to_owned()).to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    if {
        let __needle = difficulty.to_owned();
        let __container = &({
            let mut __comprehension_result_164: std::collections::BTreeSet<String> =
                std::collections::BTreeSet::new();
            let __comprehension_source_163 = ((self_).difficulties.clone());
            for level in __comprehension_source_163.iter().cloned() {
                __comprehension_result_164.insert((level).name.clone());
            }
            __comprehension_result_164
        });
        !__container.contains(&__needle)
    } {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Unknown difficulty: ".to_string(),
                (difficulty.to_owned()).to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    self_.selected_civilization = civilization.to_owned();
    self_.selected_difficulty = difficulty.to_owned();
    Ok(())
}

// Python: openciv3/scenario_model.py:331
pub(crate) fn ScenarioDefinition__load(
    path: &str,
    default_path: &str,
    mut seed: i64,
    encoding: &str,
) -> rt::Result<ScenarioDefinition> {
    let mut scenario: crate::openciv3::scenario::Scenario =
        crate::openciv3::scenario::Scenario__load(path, encoding)?;
    let mut defaults: crate::openciv3::scenario::Scenario =
        (if ((rt::path_resolve(path)?).as_str() == (rt::path_resolve(default_path)?).as_str()) {
            scenario.clone()
        } else {
            crate::openciv3::scenario::Scenario__load(default_path, encoding)?
        });
    Ok({
        let __call_165_0 = path;
        let __call_165_1 = &scenario;
        let __call_165_2 = &defaults;
        let __call_165_3 = seed;
        let __call_165_default_4 = true;
        ScenarioDefinition__from_scenarios(
            __call_165_0,
            __call_165_1,
            __call_165_2,
            __call_165_3,
            __call_165_default_4,
        )
    }?)
}

// Python: openciv3/scenario_model.py:338
pub(crate) fn ScenarioDefinition__from_scenarios(
    path: &str,
    scenario: &crate::openciv3::scenario::Scenario,
    defaults: &crate::openciv3::scenario::Scenario,
    mut seed: i64,
    mut include_map: bool,
) -> rt::Result<ScenarioDefinition> {
    let mut maps: Option<Vec<Vec<u8>>>;

    let mut eras: i64 = {
        let __boolean_123705982121808 =
            ((ScenarioDefinition__from_scenarios__records(scenario, defaults, "ERAS")?).len()
                as i64);
        if (__boolean_123705982121808) != 0 {
            __boolean_123705982121808
        } else {
            4i64
        }
    };
    let mut civilizations: Vec<Civilization> = ({
        let mut __comprehension_result_167: Vec<Civilization> = Vec::new();
        let __comprehension_source_166 =
            ((ScenarioDefinition__from_scenarios__records(scenario, defaults, "RACE")?)
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value))
                .collect::<Vec<_>>());
        for (index, record) in __comprehension_source_166.iter().cloned() {
            __comprehension_result_167.push(Civilization__from_record(&record, index, eras)?);
        }
        __comprehension_result_167
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut difficulties: Vec<Difficulty> = ({
        let mut __comprehension_result_169: Vec<Difficulty> = Vec::new();
        let __comprehension_source_168 =
            (ScenarioDefinition__from_scenarios__records(scenario, defaults, "DIFF")?);
        for record in __comprehension_source_168.iter().cloned() {
            __comprehension_result_169.push(Difficulty__from_record(&record)?);
        }
        __comprehension_result_169
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    if (!(((civilizations).len() as i64) != 0i64) || !(((difficulties).len() as i64) != 0i64)) {
        return Err("The scenario needs civilization and difficulty rules"
            .to_string()
            .into());
    }
    let mut games: Vec<crate::openciv3::binary::Record> =
        ScenarioDefinition__from_scenarios__records(scenario, defaults, "GAME")?;
    if !(((games).len() as i64) != 0i64) {
        return Err("Missing GAME section".to_string().into());
    }
    let mut options: ScenarioOptions =
        ScenarioOptions__from_record(&(rt::at(&games, 0i64)?), ((civilizations).len() as i64))?;
    let mut slots: Vec<PlayerSlot> = ({
        let mut __comprehension_result_171: Vec<PlayerSlot> = Vec::new();
        let __comprehension_source_170 =
            (ScenarioDefinition__from_scenarios__records(scenario, defaults, "LEAD")?);
        for record in __comprehension_source_170.iter().cloned() {
            __comprehension_result_171.push(PlayerSlot__from_record(&record)?);
        }
        __comprehension_result_171
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut world: Option<crate::openciv3::world::WorldMap> = (if (include_map
        && (((scenario).sections.clone())
            .get(&("TILE".to_string()))
            .cloned())
        .is_some())
    {
        Some(crate::openciv3::world::WorldMap__from_scenario(scenario)?)
    } else {
        None
    });
    if (world).is_some() {
        seed = ((*(world.clone()).as_ref().ok_or("expected a value")?).clone()).seed;
    } else {
        if (match ({
            maps = ((scenario).sections.clone())
                .get(&("WMAP".to_string()))
                .cloned();
            maps.clone()
        })
        .as_ref()
        {
            Some(value) => value.len() as i64,
            None => 0,
        } != 0i64)
        {
            let mut map_record: crate::openciv3::binary::Record = crate::openciv3::binary::Record {
                data: rt::at(
                    &((*(maps).as_ref().ok_or("expected a value")?).clone()),
                    0i64,
                )?,
                section: "WMAP".to_string(),
                encoding: (scenario).encoding.clone(),
            };
            seed = crate::openciv3::binary::Record__integer(
                &(map_record.clone()),
                (164i64)
                    .checked_add(
                        (crate::openciv3::binary::Record__count(&map_record, 4i64, 4i64)?)
                            .checked_mul(4i64)
                            .ok_or("integer overflow")?,
                    )
                    .ok_or("integer overflow")?,
            )?;
        }
    }
    let mut fixed: std::collections::BTreeSet<i64> = {
        let mut __comprehension_result_173: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_172 = (slots.clone());
        for slot in __comprehension_source_172.iter().cloned() {
            if ((slot).civilization >= 0i64) {
                __comprehension_result_173.insert((slot).civilization);
            }
        }
        __comprehension_result_173
    };
    if ({
        let mut __comprehension_result_175: Vec<bool> = Vec::new();
        let __comprehension_source_174 = (fixed.clone());
        for index in __comprehension_source_174.iter().cloned() {
            __comprehension_result_175.push((index >= ((civilizations).len() as i64)));
        }
        __comprehension_result_175
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err("LEAD contains an out-of-range civilization"
            .to_string()
            .into());
    }
    let mut available: Vec<i64> = {
        let mut __comprehension_result_177: Vec<i64> = Vec::new();
        let __comprehension_source_176 = ((options).allowed_civilizations.clone());
        for index in __comprehension_source_176.iter().cloned() {
            if {
                let __needle = index;
                let __container = &fixed;
                !__container.contains(&__needle)
            } {
                __comprehension_result_177.push(index);
            }
        }
        __comprehension_result_177
    };
    {
        let __random = rt::random_new(seed);
        for __index in (1..available.len()).rev() {
            let __other = rt::random_randrange(&__random, 0, __index as i64 + 1)? as usize;
            available.swap(__index, __other);
        }
        ()
    };
    let mut pool: Vec<i64> = available;
    let mut assigned: Vec<i64> = ({
        let mut __comprehension_result_179: Vec<i64> = Vec::new();
        let __comprehension_source_178 = (slots.clone());
        for slot in __comprehension_source_178.iter().cloned() {
            __comprehension_result_179.push(
                (if ((slot).civilization >= 0i64) {
                    (slot).civilization
                } else {
                    match (&pool).iter().next() {
                        Some(value) => (*value).clone(),
                        None => (1i64).checked_neg().ok_or("integer overflow")?,
                    }
                }),
            );
        }
        __comprehension_result_179
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut human_ids: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
    if (((slots).len() as i64) != 0i64) {
        human_ids = {
            let mut __comprehension_result_181: std::collections::BTreeSet<i64> =
                std::collections::BTreeSet::new();
            let __comprehension_source_180 = ({
                let __left = assigned.clone();
                let __right = slots.clone();
                if false && __left.len() != __right.len() {
                    return Err("zip() argument lengths differ".into());
                }
                let mut __result: Vec<(i64, PlayerSlot)> = Vec::new();
                let __length = __left.len().min(__right.len());
                let mut __left_iter = __left.into_iter();
                let mut __right_iter = __right.into_iter();
                for __index in 0..__length {
                    __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
                }
                __result
            });
            for (index, slot) in __comprehension_source_180.iter().cloned() {
                if ((index > 0i64) && (slot).human_allowed) {
                    __comprehension_result_181.insert(index);
                }
            }
            __comprehension_result_181
        };
    } else {
        human_ids = {
            let __set_left = ((options).allowed_civilizations.clone())
                .into_iter()
                .collect::<std::collections::BTreeSet<_>>();
            let __set_right = {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![0i64].into_iter() {
                    __result.insert(__item);
                }
                __result
            };
            let mut __result = std::collections::BTreeSet::new();
            for __item in __set_left.difference(&__set_right) {
                __result.insert(__item.clone());
            }
            __result
        };
        assigned = (options).allowed_civilizations.clone();
    }
    let mut playable: Vec<Civilization> = ({
        let mut __comprehension_result_183: Vec<Civilization> = Vec::new();
        let __comprehension_source_182 = (civilizations.clone());
        for civ in __comprehension_source_182.iter().cloned() {
            if {
                let __needle = (civ).index;
                let __container = &human_ids;
                __container.contains(&__needle)
            } {
                __comprehension_result_183.push(civ.clone());
            }
        }
        __comprehension_result_183
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    if !(((playable).len() as i64) != 0i64) {
        return Err("The scenario has no human-playable civilizations"
            .to_string()
            .into());
    }
    let mut sizes: Vec<crate::openciv3::world_size::WorldSize> = ({
        let mut __comprehension_result_185: Vec<crate::openciv3::world_size::WorldSize> =
            Vec::new();
        let __comprehension_source_184 =
            (ScenarioDefinition__from_scenarios__records(scenario, defaults, "WSIZ")?);
        for record in __comprehension_source_184.iter().cloned() {
            __comprehension_result_185.push(crate::openciv3::world_size::WorldSize__from_record(
                &record,
            )?);
        }
        __comprehension_result_185
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut characteristics: Vec<Vec<u8>> = {
        let __mapping = &(scenario).sections;
        let __key = "WCHR".to_string();
        let __default = vec![];
        __mapping.get(&__key).cloned().unwrap_or(__default)
    };
    let mut selected_size: Option<crate::openciv3::world_size::WorldSize> = None;
    if (!(sizes.clone()).is_empty() && !(characteristics.clone()).is_empty()) {
        let mut size_index: i64 = crate::openciv3::binary::Record__integer(
            &(crate::openciv3::binary::Record {
                data: rt::at(&characteristics, 0i64)?,
                section: "WCHR".to_string(),
                encoding: (scenario).encoding.clone(),
            }),
            52i64,
        )?;
        if !({
            let __compare_0 = 0i64;
            let __compare_1 = size_index;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = ((sizes).len() as i64);
                (__compare_1 < __compare_2)
            } else {
                false
            }
        }) {
            return Err("WCHR refers to an invalid world size".to_string().into());
        }
        selected_size = Some(rt::at(&sizes, size_index)?);
    }
    Ok(ScenarioDefinition {
        source: path.to_owned(),
        scenario: (*scenario).clone(),
        defaults: (*defaults).clone(),
        civilizations: civilizations,
        difficulties: difficulties,
        slots: slots,
        options: options,
        assigned_civilizations: assigned,
        playable: playable,
        seed: seed,
        world: world,
        rules: crate::openciv3::rules::RuleCatalog__from_scenarios(scenario, defaults)?,
        world_size: selected_size,
        selected_civilization: String::new(),
        selected_difficulty: String::new(),
        portrait_paths: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
    })
}

// Python: openciv3/scenario_model.py:340
pub(crate) fn ScenarioDefinition__from_scenarios__records(
    scenario: &crate::openciv3::scenario::Scenario,
    defaults: &crate::openciv3::scenario::Scenario,
    section: &str,
) -> rt::Result<Vec<crate::openciv3::binary::Record>> {
    let mut source: crate::openciv3::scenario::Scenario = (if {
        let __needle: &str = AsRef::<str>::as_ref(section);
        let __container = &(scenario).sections;
        __container.contains_key(__needle)
    } {
        (*scenario).clone()
    } else {
        (*defaults).clone()
    });
    Ok({
        let mut __comprehension_result_187: Vec<crate::openciv3::binary::Record> = Vec::new();
        let __comprehension_source_186 = ({
            let __mapping = &(source).sections;
            let __key = section.to_owned();
            let __default = vec![];
            __mapping.get(&__key).cloned().unwrap_or(__default)
        });
        for data in __comprehension_source_186.iter().cloned() {
            __comprehension_result_187.push(crate::openciv3::binary::Record {
                data: data.clone(),
                section: section.to_owned(),
                encoding: (source).encoding.clone(),
            });
        }
        __comprehension_result_187
    })
}
