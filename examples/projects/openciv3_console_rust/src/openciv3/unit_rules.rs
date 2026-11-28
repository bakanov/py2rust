use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct UnitPrototype {
    pub(crate) name: String,
    pub(crate) civilopedia_entry: String,
    pub(crate) zone_of_control: bool,
    pub(crate) bombard_strength: i64,
    pub(crate) bombard_range: i64,
    pub(crate) capacity: i64,
    pub(crate) shield_cost: i64,
    pub(crate) defense: i64,
    pub(crate) icon: i64,
    pub(crate) attack: i64,
    pub(crate) operational_range: i64,
    pub(crate) population_cost: i64,
    pub(crate) rate_of_fire: i64,
    pub(crate) movement: i64,
    pub(crate) prerequisite: i64,
    pub(crate) upgrade_to: i64,
    pub(crate) required_resources: Vec<i64>,
    pub(crate) abilities: i64,
    pub(crate) strategies: i64,
    pub(crate) available_to: Vec<i64>,
    pub(crate) domain: i64,
    pub(crate) other_strategy: i64,
    pub(crate) hp_bonus: i64,
    pub(crate) orders: i64,
    pub(crate) bombard_effects: i64,
    pub(crate) ignore_movement_cost: Vec<i64>,
    pub(crate) require_support: bool,
    pub(crate) enslave_result: i64,
    pub(crate) stealth_targets: Vec<i64>,
    pub(crate) create_craters: bool,
    pub(crate) worker_strength: f64,
    pub(crate) air_defense: i64,
    pub(crate) animation_name: String,
    pub(crate) animation_variants: Vec<(String, String)>,
    pub(crate) icon_variants: Vec<(String, i64)>,
    pub(crate) upgrade_branches: Option<Vec<i64>>,
    pub(crate) worker_jobs: Option<std::collections::BTreeSet<i64>>,
    pub(crate) unproducible: bool,
}

// Python: openciv3/unit_rules.py:159
pub(crate) fn UnitPrototype__bombardment_range(self_: &UnitPrototype) -> rt::Result<i64> {
    if ((self_).bombard_strength <= 0i64) {
        return Ok(0i64);
    }
    if (((self_).domain == 2i64) && ((self_).orders & 274877906944i64) != 0) {
        return Ok((self_).operational_range);
    }
    Ok((if (((self_).orders & 2048i64) != 0i64) {
        (self_).bombard_range
    } else {
        0i64
    }))
}

/// Barbarian availability does not disqualify a unique civilization unit.
// Python: openciv3/unit_rules.py:167
pub(crate) fn UnitPrototype__unique_civilization(self_: &UnitPrototype) -> rt::Result<Option<i64>> {
    let mut civilizations: Vec<i64> = ({
        let mut __comprehension_result_244: Vec<i64> = Vec::new();
        let __comprehension_source_243 = ((self_).available_to.clone());
        for index in __comprehension_source_243.iter().cloned() {
            if (index != 0i64) {
                __comprehension_result_244.push(index);
            }
        }
        __comprehension_result_244
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    Ok((if (((civilizations).len() as i64) == 1i64) {
        Some(rt::at(&civilizations, 0i64)?)
    } else {
        None
    }))
}

// Python: openciv3/unit_rules.py:173
pub(crate) fn UnitPrototype__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<UnitPrototype> {
    let mut count: i64 = crate::openciv3::binary::Record__count(record, 234i64, 4i64)?;
    let mut tail: i64 = (238i64)
        .checked_add((4i64).checked_mul(count).ok_or("integer overflow")?)
        .ok_or("integer overflow")?;
    let mut available: i64 = rt::int_from_bytes(
        &(crate::openciv3::binary::Record__bytes(record, 144i64, 4i64)?),
        "little",
    )?;
    let mut movement_flags: Vec<u8> =
        crate::openciv3::binary::Record__bytes(record, 192i64, 14i64)?;
    Ok(UnitPrototype {
        name: crate::openciv3::binary::Record__text(record, 8i64, 32i64)?,
        civilopedia_entry: crate::openciv3::binary::Record__text(record, 40i64, 32i64)?,
        zone_of_control: (crate::openciv3::binary::Record__integer(record, 4i64)? != 0i64),
        bombard_strength: crate::openciv3::binary::Record__integer(record, 72i64)?,
        bombard_range: crate::openciv3::binary::Record__integer(record, 76i64)?,
        capacity: crate::openciv3::binary::Record__integer(record, 80i64)?,
        shield_cost: crate::openciv3::binary::Record__integer(record, 84i64)?,
        defense: crate::openciv3::binary::Record__integer(record, 88i64)?,
        icon: crate::openciv3::binary::Record__integer(record, 92i64)?,
        attack: crate::openciv3::binary::Record__integer(record, 96i64)?,
        operational_range: crate::openciv3::binary::Record__integer(record, 100i64)?,
        population_cost: crate::openciv3::binary::Record__integer(record, 104i64)?,
        rate_of_fire: crate::openciv3::binary::Record__integer(record, 108i64)?,
        movement: crate::openciv3::binary::Record__integer(record, 112i64)?,
        prerequisite: crate::openciv3::binary::Record__integer(record, 116i64)?,
        upgrade_to: crate::openciv3::binary::Record__integer(record, 120i64)?,
        required_resources: ({
            let mut __comprehension_result_246: Vec<i64> = Vec::new();
            let mut value: i64;
            let __comprehension_source_245 = ({
                let __tuple_value = &((124i64, 128i64, 132i64));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                ]
            });
            for offset in __comprehension_source_245.iter().cloned() {
                if ({
                    value = crate::openciv3::binary::Record__integer(record, offset)?;
                    value
                } >= 0i64)
                {
                    __comprehension_result_246.push(value);
                }
            }
            __comprehension_result_246
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        abilities: rt::int_from_bytes(
            &(crate::openciv3::binary::Record__bytes(record, 136i64, 4i64)?),
            "little",
        )?,
        strategies: rt::int_from_bytes(
            &(crate::openciv3::binary::Record__bytes(record, 140i64, 4i64)?),
            "little",
        )?,
        available_to: ({
            let mut __comprehension_result_248: Vec<i64> = Vec::new();
            let __comprehension_source_247 = ((0i64..32i64).collect::<Vec<i64>>());
            for index in __comprehension_source_247.iter().cloned() {
                if ((available & rt::int_lshift(1i64, index)?) != 0i64) {
                    __comprehension_result_248.push(index);
                }
            }
            __comprehension_result_248
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        domain: crate::openciv3::binary::Record__integer(record, 156i64)?,
        other_strategy: crate::openciv3::binary::Record__integer(record, 160i64)?,
        hp_bonus: crate::openciv3::binary::Record__integer(record, 164i64)?,
        orders: rt::int_from_bytes(
            &(crate::openciv3::binary::Record__bytes(record, 168i64, 20i64)?),
            "little",
        )?,
        bombard_effects: crate::openciv3::binary::Record__integer(record, 188i64)?,
        ignore_movement_cost: ({
            let mut __comprehension_result_250: Vec<i64> = Vec::new();
            let __comprehension_source_249 = ((movement_flags.clone())
                .into_iter()
                .enumerate()
                .map(|(__index, __value)| (__index as i64 + 0i64, __value as i64))
                .collect::<Vec<_>>());
            for (index, flag) in __comprehension_source_249.iter().cloned() {
                if ((flag & 1i64) != 0i64) {
                    __comprehension_result_250.push(index);
                }
            }
            __comprehension_result_250
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        require_support: (crate::openciv3::binary::Record__integer(record, 206i64)? != 0i64),
        enslave_result: crate::openciv3::binary::Record__integer(record, 226i64)?,
        stealth_targets: ({
            let mut __comprehension_result_252: Vec<i64> = Vec::new();
            let __comprehension_source_251 = ((0i64..count).collect::<Vec<i64>>());
            for i in __comprehension_source_251.iter().cloned() {
                __comprehension_result_252.push(crate::openciv3::binary::Record__integer(
                    record,
                    (238i64)
                        .checked_add((4i64).checked_mul(i).ok_or("integer overflow")?)
                        .ok_or("integer overflow")?,
                )?);
            }
            __comprehension_result_252
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        create_craters: (rt::at(
            &(crate::openciv3::binary::Record__bytes(
                record,
                (tail).checked_add(8i64).ok_or("integer overflow")?,
                1i64,
            )?),
            0i64,
        )? as i64)
            != 0,
        worker_strength: ((rt::struct_unpack_float(
            &(crate::openciv3::binary::Record__bytes(
                record,
                (tail).checked_add(9i64).ok_or("integer overflow")?,
                4i64,
            )?),
        )?,))
            .0
            .clone(),
        air_defense: crate::openciv3::binary::Record__integer(
            record,
            (tail).checked_add(17i64).ok_or("integer overflow")?,
        )?,
        animation_name: String::new(),
        animation_variants: vec![],
        icon_variants: vec![],
        upgrade_branches: None,
        worker_jobs: None,
        unproducible: false,
    })
}
