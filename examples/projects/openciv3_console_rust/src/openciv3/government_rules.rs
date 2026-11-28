use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct GovernmentRelation {
    pub(crate) can_bribe: bool,
    pub(crate) bribery_modifier: i64,
    pub(crate) resistance_modifier: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct Government {
    pub(crate) name: String,
    pub(crate) civilopedia_entry: String,
    pub(crate) default_type: bool,
    pub(crate) transition_type: bool,
    pub(crate) requires_maintenance: bool,
    pub(crate) toggle_1: i64,
    pub(crate) tile_penalty: bool,
    pub(crate) trade_bonus: bool,
    pub(crate) ruler_titles: Vec<(String, String)>,
    pub(crate) corruption: i64,
    pub(crate) immune_to: i64,
    pub(crate) diplomats_are: i64,
    pub(crate) spies_are: i64,
    pub(crate) relations: Vec<GovernmentRelation>,
    pub(crate) hurrying: i64,
    pub(crate) assimilation_chance: i64,
    pub(crate) draft_limit: i64,
    pub(crate) military_police_limit: i64,
    pub(crate) ruler_title_pairs_used: i64,
    pub(crate) prerequisite: i64,
    pub(crate) science_rate_cap: i64,
    pub(crate) worker_rate: i64,
    pub(crate) toggle_2: i64,
    pub(crate) toggle_3: i64,
    pub(crate) free_units: i64,
    pub(crate) free_units_per_town: i64,
    pub(crate) free_units_per_city: i64,
    pub(crate) free_units_per_metropolis: i64,
    pub(crate) unit_cost: i64,
    pub(crate) war_weariness: i64,
    pub(crate) xenophobic: bool,
    pub(crate) force_resettle: bool,
}

// Python: openciv3/government_rules.py:50
pub(crate) fn Government__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<Government> {
    let mut count: i64 = crate::openciv3::binary::Record__count(record, 396i64, 12i64)?;
    let mut tail: i64 = (400i64)
        .checked_add((count).checked_mul(12i64).ok_or("integer overflow")?)
        .ok_or("integer overflow")?;
    Ok(Government {
        name: crate::openciv3::binary::Record__text(record, 28i64, 64i64)?,
        civilopedia_entry: crate::openciv3::binary::Record__text(record, 92i64, 32i64)?,
        default_type: (crate::openciv3::binary::Record__integer(record, 4i64)?) != 0,
        transition_type: (crate::openciv3::binary::Record__integer(record, 8i64)?) != 0,
        requires_maintenance: (crate::openciv3::binary::Record__integer(record, 12i64)?) != 0,
        toggle_1: crate::openciv3::binary::Record__integer(record, 16i64)?,
        tile_penalty: (crate::openciv3::binary::Record__integer(record, 20i64)?) != 0,
        trade_bonus: (crate::openciv3::binary::Record__integer(record, 24i64)?) != 0,
        ruler_titles: ({
            let mut __comprehension_result_254: Vec<(String, String)> = Vec::new();
            let __comprehension_source_253 = ((0i64..4i64).collect::<Vec<i64>>());
            for i in __comprehension_source_253.iter().cloned() {
                __comprehension_result_254.push((
                    crate::openciv3::binary::Record__text(
                        record,
                        (124i64)
                            .checked_add((i).checked_mul(64i64).ok_or("integer overflow")?)
                            .ok_or("integer overflow")?,
                        32i64,
                    )?,
                    crate::openciv3::binary::Record__text(
                        record,
                        (156i64)
                            .checked_add((i).checked_mul(64i64).ok_or("integer overflow")?)
                            .ok_or("integer overflow")?,
                        32i64,
                    )?,
                ));
            }
            __comprehension_result_254
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        corruption: crate::openciv3::binary::Record__integer(record, 380i64)?,
        immune_to: crate::openciv3::binary::Record__integer(record, 384i64)?,
        diplomats_are: crate::openciv3::binary::Record__integer(record, 388i64)?,
        spies_are: crate::openciv3::binary::Record__integer(record, 392i64)?,
        relations: ({
            let mut __comprehension_result_256: Vec<GovernmentRelation> = Vec::new();
            let __comprehension_source_255 = ((0i64..count).collect::<Vec<i64>>());
            for i in __comprehension_source_255.iter().cloned() {
                __comprehension_result_256.push(GovernmentRelation {
                    can_bribe: (crate::openciv3::binary::Record__integer(
                        record,
                        (400i64)
                            .checked_add((i).checked_mul(12i64).ok_or("integer overflow")?)
                            .ok_or("integer overflow")?,
                    )?) != 0,
                    bribery_modifier: crate::openciv3::binary::Record__integer(
                        record,
                        (404i64)
                            .checked_add((i).checked_mul(12i64).ok_or("integer overflow")?)
                            .ok_or("integer overflow")?,
                    )?,
                    resistance_modifier: crate::openciv3::binary::Record__integer(
                        record,
                        (408i64)
                            .checked_add((i).checked_mul(12i64).ok_or("integer overflow")?)
                            .ok_or("integer overflow")?,
                    )?,
                });
            }
            __comprehension_result_256
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        hurrying: crate::openciv3::binary::Record__integer(record, tail)?,
        assimilation_chance: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(4i64).ok_or("integer overflow")?,
        )?,
        draft_limit: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(8i64).ok_or("integer overflow")?,
        )?,
        military_police_limit: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(12i64).ok_or("integer overflow")?,
        )?,
        ruler_title_pairs_used: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(16i64).ok_or("integer overflow")?,
        )?,
        prerequisite: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(20i64).ok_or("integer overflow")?,
        )?,
        science_rate_cap: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(24i64).ok_or("integer overflow")?,
        )?,
        worker_rate: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(28i64).ok_or("integer overflow")?,
        )?,
        toggle_2: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(32i64).ok_or("integer overflow")?,
        )?,
        toggle_3: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(36i64).ok_or("integer overflow")?,
        )?,
        free_units: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(44i64).ok_or("integer overflow")?,
        )?,
        free_units_per_town: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(48i64).ok_or("integer overflow")?,
        )?,
        free_units_per_city: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(52i64).ok_or("integer overflow")?,
        )?,
        free_units_per_metropolis: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(56i64).ok_or("integer overflow")?,
        )?,
        unit_cost: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(60i64).ok_or("integer overflow")?,
        )?,
        war_weariness: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(64i64).ok_or("integer overflow")?,
        )?,
        xenophobic: (crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(68i64).ok_or("integer overflow")?,
        )?) != 0,
        force_resettle: (crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(72i64).ok_or("integer overflow")?,
        )?) != 0,
    })
}
