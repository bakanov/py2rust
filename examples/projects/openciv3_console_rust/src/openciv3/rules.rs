use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum WorkerScore {
    DEFAULT,
    CLEAR_WETLANDS,
    RAILROAD,
    CLEAR_FOREST,
    YIELD_IMPROVEMENT,
    ROAD,
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum WorkerValidator {
    MINE,
    IRRIGATE,
    CLEAR_FOREST,
    CLEAR_WETLANDS,
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum WorkerEffect {
    CLEAR_FOREST,
    CLEAR_WETLANDS,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct Technology {
    pub(crate) name: String,
    pub(crate) civilopedia_entry: String,
    pub(crate) cost: i64,
    pub(crate) era: i64,
    pub(crate) icon: i64,
    pub(crate) x: i64,
    pub(crate) y: i64,
    pub(crate) prerequisites: Vec<i64>,
    pub(crate) effects: i64,
    pub(crate) flavors: i64,
    pub(crate) media_key: String,
    pub(crate) small_icon_path: String,
}

#[derive(Clone, PartialEq)]
pub(crate) struct ExperienceLevel {
    pub(crate) name: String,
    pub(crate) base_hit_points: i64,
    pub(crate) retreat_bonus: f64,
    pub(crate) promotion_chance: Option<f64>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct CitizenType {
    pub(crate) default_citizen: bool,
    pub(crate) singular_name: String,
    pub(crate) civilopedia_entry: String,
    pub(crate) plural_name: String,
    pub(crate) prerequisite: i64,
    pub(crate) luxuries: i64,
    pub(crate) research: i64,
    pub(crate) taxes: i64,
    pub(crate) corruption: i64,
    pub(crate) construction: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct WorkerJob {
    pub(crate) name: String,
    pub(crate) civilopedia_entry: String,
    pub(crate) turns_to_complete: i64,
    pub(crate) prerequisite: i64,
    pub(crate) required_resources: Vec<i64>,
    pub(crate) order: String,
    pub(crate) animation: String,
    pub(crate) ai_score: Option<WorkerScore>,
    pub(crate) validators: Option<Vec<WorkerValidator>>,
    pub(crate) effects: Option<Vec<WorkerEffect>>,
    pub(crate) improvement: Option<i64>,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct Resource {
    pub(crate) name: String,
    pub(crate) civilopedia_entry: String,
    pub(crate) kind: i64,
    pub(crate) appearance_ratio: i64,
    pub(crate) disappearance_probability: i64,
    pub(crate) icon: i64,
    pub(crate) prerequisite: i64,
    pub(crate) bonus: crate::civ::economy::Yield,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct ImprovementYields {
    pub(crate) irrigation: crate::civ::economy::Yield,
    pub(crate) mine: crate::civ::economy::Yield,
    pub(crate) road: crate::civ::economy::Yield,
    pub(crate) railroad: crate::civ::economy::Yield,
}

#[derive(Clone, PartialEq)]
pub(crate) struct Terrain {
    pub(crate) name: String,
    pub(crate) civilopedia_entry: String,
    pub(crate) possible_resources: Vec<i64>,
    pub(crate) irrigation_bonus: i64,
    pub(crate) mining_bonus: i64,
    pub(crate) road_bonus: i64,
    pub(crate) defense_bonus: i64,
    pub(crate) movement_cost: i64,
    pub(crate) yields: crate::civ::economy::Yield,
    pub(crate) worker_job: i64,
    pub(crate) pollution_effect: i64,
    pub(crate) allow_cities: bool,
    pub(crate) allow_colonies: bool,
    pub(crate) impassable: bool,
    pub(crate) impassable_by_wheeled: bool,
    pub(crate) allow_airfields: bool,
    pub(crate) allow_forts: bool,
    pub(crate) allow_outposts: bool,
    pub(crate) allow_radar_towers: bool,
    pub(crate) landmark_enabled: bool,
    pub(crate) landmark_yields: crate::civ::economy::Yield,
    pub(crate) landmark_irrigation_bonus: i64,
    pub(crate) landmark_mining_bonus: i64,
    pub(crate) landmark_road_bonus: i64,
    pub(crate) landmark_movement_cost: i64,
    pub(crate) landmark_defense_bonus: i64,
    pub(crate) landmark_name: String,
    pub(crate) landmark_civilopedia_entry: String,
    pub(crate) flags: i64,
    pub(crate) disease_strength: i64,
    pub(crate) improvement_yields: Option<ImprovementYields>,
    pub(crate) extra_improvement_yields: Vec<(i64, crate::civ::economy::Yield)>,
    pub(crate) impassable_to: Option<Vec<(i64, i64)>>,
    pub(crate) allowed_base_terrains: Option<std::collections::BTreeSet<i64>>,
    pub(crate) sight_height: Option<i64>,
}

#[derive(Clone, PartialEq)]
pub(crate) struct RuleCatalog {
    pub(crate) technologies: Vec<Technology>,
    pub(crate) resources: Vec<Resource>,
    pub(crate) terrains: Vec<Terrain>,
    pub(crate) units: Vec<crate::openciv3::unit_rules::UnitPrototype>,
    pub(crate) experience_levels: Vec<ExperienceLevel>,
    pub(crate) citizens: Vec<CitizenType>,
    pub(crate) worker_jobs: Vec<WorkerJob>,
    pub(crate) governments: Vec<crate::openciv3::government_rules::Government>,
    pub(crate) buildings: Vec<crate::openciv3::building_rules::Building>,
    pub(crate) global_rules: Vec<crate::openciv3::global_rules::GlobalRules>,
}

// Python: openciv3/rules.py:59
pub(crate) fn Technology__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<Technology> {
    Ok(Technology {
        name: crate::openciv3::binary::Record__text(record, 4i64, 32i64)?,
        civilopedia_entry: crate::openciv3::binary::Record__text(record, 36i64, 32i64)?,
        cost: crate::openciv3::binary::Record__integer(record, 68i64)?,
        era: crate::openciv3::binary::Record__integer(record, 72i64)?,
        icon: crate::openciv3::binary::Record__integer(record, 76i64)?,
        x: crate::openciv3::binary::Record__integer(record, 80i64)?,
        y: crate::openciv3::binary::Record__integer(record, 84i64)?,
        prerequisites: ({
            let mut __comprehension_result_214: Vec<i64> = Vec::new();
            let mut value: i64;
            let __comprehension_source_213 = (rt::range_values(88i64, 104i64, 4i64)?);
            for offset in __comprehension_source_213.iter().cloned() {
                if ({
                    value = crate::openciv3::binary::Record__integer(record, offset)?;
                    value
                } >= 0i64)
                {
                    __comprehension_result_214.push(value);
                }
            }
            __comprehension_result_214
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        effects: rt::int_from_bytes(
            &(crate::openciv3::binary::Record__bytes(record, 104i64, 4i64)?),
            "little",
        )?,
        flavors: crate::openciv3::binary::Record__integer(record, 108i64)?,
        media_key: String::new(),
        small_icon_path: String::new(),
    })
}

// Python: openciv3/rules.py:87
pub(crate) fn Resource__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<Resource> {
    Ok(Resource {
        name: crate::openciv3::binary::Record__text(record, 4i64, 24i64)?,
        civilopedia_entry: crate::openciv3::binary::Record__text(record, 28i64, 32i64)?,
        kind: crate::openciv3::binary::Record__integer(record, 60i64)?,
        appearance_ratio: crate::openciv3::binary::Record__integer(record, 64i64)?,
        disappearance_probability: crate::openciv3::binary::Record__integer(record, 68i64)?,
        icon: crate::openciv3::binary::Record__integer(record, 72i64)?,
        prerequisite: crate::openciv3::binary::Record__integer(record, 76i64)?,
        bonus: crate::civ::economy::Yield {
            food: crate::openciv3::binary::Record__integer(record, 80i64)?,
            shields: crate::openciv3::binary::Record__integer(record, 84i64)?,
            commerce: crate::openciv3::binary::Record__integer(record, 88i64)?,
        },
    })
}

// Python: openciv3/rules.py:147
pub(crate) fn Terrain__improvements(self_: &Terrain) -> rt::Result<ImprovementYields> {
    if (&(self_).improvement_yields).is_some() {
        return Ok((*((self_).improvement_yields.clone())
            .as_ref()
            .ok_or("expected a value")?)
        .clone());
    }
    let mut road: crate::civ::economy::Yield = crate::civ::economy::Yield {
        food: 0i64,
        shields: 0i64,
        commerce: (0i64).max((self_).road_bonus),
    };
    Ok(ImprovementYields {
        irrigation: crate::civ::economy::Yield {
            food: (0i64).max((self_).irrigation_bonus),
            shields: 0i64,
            commerce: 0i64,
        },
        mine: crate::civ::economy::Yield {
            food: 0i64,
            shields: (0i64).max((self_).mining_bonus),
            commerce: 0i64,
        },
        road: road.clone(),
        railroad: road.clone(),
    })
}

// Python: openciv3/rules.py:155
pub(crate) fn Terrain__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<Terrain> {
    let mut count: i64 = crate::openciv3::binary::Record__integer(record, 4i64)?;
    if (count < 0i64) {
        return Err("Invalid TERR resource count".to_string().into());
    }
    let mut bitmap_size: i64 =
        rt::int_floor_div((count).checked_add(7i64).ok_or("integer overflow")?, 8i64)?;
    let mut bitmap: Vec<u8> = crate::openciv3::binary::Record__bytes(record, 8i64, bitmap_size)?;
    let mut data: crate::openciv3::binary::Record = crate::openciv3::binary::Record {
        data: crate::openciv3::binary::Record__bytes(
            record,
            (8i64).checked_add(bitmap_size).ok_or("integer overflow")?,
            225i64,
        )?,
        section: "TERR".to_string(),
        encoding: (record).encoding.clone(),
    };
    let mut permissions: Vec<u8> = crate::openciv3::binary::Record__bytes(&data, 104i64, 8i64)?;
    let mut possible: Vec<i64> = ({
        let mut __comprehension_result_216: Vec<i64> = Vec::new();
        let __comprehension_source_215 = ((0i64..count).collect::<Vec<i64>>());
        for i in __comprehension_source_215.iter().cloned() {
            if (((rt::at(&bitmap, rt::int_floor_div(i, 8i64)?)? as i64)
                & rt::int_lshift(1i64, rt::int_modulo(i, 8i64)?)?)
                != 0i64)
            {
                __comprehension_result_216.push(i);
            }
        }
        __comprehension_result_216
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    Ok(Terrain {
        name: crate::openciv3::binary::Record__text(&data, 0i64, 32i64)?,
        civilopedia_entry: crate::openciv3::binary::Record__text(&data, 32i64, 32i64)?,
        possible_resources: possible,
        irrigation_bonus: crate::openciv3::binary::Record__integer(&data, 64i64)?,
        mining_bonus: crate::openciv3::binary::Record__integer(&data, 68i64)?,
        road_bonus: crate::openciv3::binary::Record__integer(&data, 72i64)?,
        defense_bonus: crate::openciv3::binary::Record__integer(&data, 76i64)?,
        movement_cost: crate::openciv3::binary::Record__integer(&data, 80i64)?,
        yields: crate::civ::economy::Yield {
            food: crate::openciv3::binary::Record__integer(&data, 84i64)?,
            shields: crate::openciv3::binary::Record__integer(&data, 88i64)?,
            commerce: crate::openciv3::binary::Record__integer(&data, 92i64)?,
        },
        worker_job: crate::openciv3::binary::Record__integer(&data, 96i64)?,
        pollution_effect: crate::openciv3::binary::Record__integer(&data, 100i64)?,
        allow_cities: (rt::at(&permissions, 0i64)? as i64) != 0,
        allow_colonies: (rt::at(&permissions, 1i64)? as i64) != 0,
        impassable: (rt::at(&permissions, 2i64)? as i64) != 0,
        impassable_by_wheeled: (rt::at(&permissions, 3i64)? as i64) != 0,
        allow_airfields: (rt::at(&permissions, 4i64)? as i64) != 0,
        allow_forts: (rt::at(&permissions, 5i64)? as i64) != 0,
        allow_outposts: (rt::at(&permissions, 6i64)? as i64) != 0,
        allow_radar_towers: (rt::at(&permissions, 7i64)? as i64) != 0,
        landmark_enabled: (rt::at(
            &(crate::openciv3::binary::Record__bytes(&data, 116i64, 1i64)?),
            0i64,
        )? as i64)
            != 0,
        landmark_yields: crate::civ::economy::Yield {
            food: crate::openciv3::binary::Record__integer(&data, 117i64)?,
            shields: crate::openciv3::binary::Record__integer(&data, 121i64)?,
            commerce: crate::openciv3::binary::Record__integer(&data, 125i64)?,
        },
        landmark_irrigation_bonus: crate::openciv3::binary::Record__integer(&data, 129i64)?,
        landmark_mining_bonus: crate::openciv3::binary::Record__integer(&data, 133i64)?,
        landmark_road_bonus: crate::openciv3::binary::Record__integer(&data, 137i64)?,
        landmark_movement_cost: crate::openciv3::binary::Record__integer(&data, 141i64)?,
        landmark_defense_bonus: crate::openciv3::binary::Record__integer(&data, 145i64)?,
        landmark_name: crate::openciv3::binary::Record__text(&data, 149i64, 32i64)?,
        landmark_civilopedia_entry: crate::openciv3::binary::Record__text(&data, 181i64, 32i64)?,
        flags: crate::openciv3::binary::Record__integer(&data, 217i64)?,
        disease_strength: crate::openciv3::binary::Record__integer(&data, 221i64)?,
        improvement_yields: None,
        extra_improvement_yields: vec![],
        impassable_to: None,
        allowed_base_terrains: None,
        sight_height: None,
    })
}

// Python: openciv3/rules.py:185
pub(crate) fn ExperienceLevel__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<ExperienceLevel> {
    Ok(ExperienceLevel {
        name: crate::openciv3::binary::Record__text(record, 4i64, 32i64)?,
        base_hit_points: crate::openciv3::binary::Record__integer(record, 36i64)?,
        retreat_bonus: ((crate::openciv3::binary::Record__integer(record, 40i64)?) as f64),
        promotion_chance: None,
    })
}

// Python: openciv3/rules.py:203
pub(crate) fn CitizenType__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<CitizenType> {
    Ok(CitizenType {
        default_citizen: (crate::openciv3::binary::Record__integer(record, 4i64)? != 0i64),
        singular_name: crate::openciv3::binary::Record__text(record, 8i64, 32i64)?,
        civilopedia_entry: crate::openciv3::binary::Record__text(record, 40i64, 32i64)?,
        plural_name: crate::openciv3::binary::Record__text(record, 72i64, 32i64)?,
        prerequisite: crate::openciv3::binary::Record__integer(record, 104i64)?,
        luxuries: crate::openciv3::binary::Record__integer(record, 108i64)?,
        research: crate::openciv3::binary::Record__integer(record, 112i64)?,
        taxes: crate::openciv3::binary::Record__integer(record, 116i64)?,
        corruption: crate::openciv3::binary::Record__integer(record, 120i64)?,
        construction: crate::openciv3::binary::Record__integer(record, 124i64)?,
    })
}

// Python: openciv3/rules.py:245
pub(crate) fn WorkerJob__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<WorkerJob> {
    Ok(WorkerJob {
        name: crate::openciv3::binary::Record__text(record, 4i64, 32i64)?,
        civilopedia_entry: crate::openciv3::binary::Record__text(record, 36i64, 32i64)?,
        turns_to_complete: crate::openciv3::binary::Record__integer(record, 68i64)?,
        prerequisite: crate::openciv3::binary::Record__integer(record, 72i64)?,
        required_resources: ({
            let mut __comprehension_result_218: Vec<i64> = Vec::new();
            let mut value: i64;
            let __comprehension_source_217 = ({
                let __tuple_value = &((76i64, 80i64));
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            });
            for offset in __comprehension_source_217.iter().cloned() {
                if ({
                    value = crate::openciv3::binary::Record__integer(record, offset)?;
                    value
                } >= 0i64)
                {
                    __comprehension_result_218.push(value);
                }
            }
            __comprehension_result_218
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        order: crate::openciv3::binary::Record__text(record, 84i64, 32i64)?,
        animation: String::new(),
        ai_score: None,
        validators: None,
        effects: None,
        improvement: None,
    })
}

// Python: openciv3/rules.py:265
pub(crate) fn RuleCatalog__workable_rank(self_: &RuleCatalog) -> rt::Result<i64> {
    Ok((if (((&(self_).global_rules).len() as i64) != 0i64) {
        ({
            let __source = &(self_).global_rules;
            let __key = 0i64;
            &__source[rt::index(__source.len(), __key)?]
        })
        .max_rank_of_workable_tiles
    } else {
        2i64
    }))
}

// Python: openciv3/rules.py:269
pub(crate) fn RuleCatalog__food_per_citizen(self_: &RuleCatalog) -> rt::Result<i64> {
    Ok((if (((&(self_).global_rules).len() as i64) != 0i64) {
        ({
            let __source = &(self_).global_rules;
            let __key = 0i64;
            &__source[rt::index(__source.len(), __key)?]
        })
        .food_consumption_per_citizen
    } else {
        2i64
    }))
}

// Python: openciv3/rules.py:273
pub(crate) fn RuleCatalog__deal_duration(self_: &RuleCatalog) -> rt::Result<i64> {
    Ok((if (((&(self_).global_rules).len() as i64) != 0i64) {
        ({
            let __source = &(self_).global_rules;
            let __key = 0i64;
            &__source[rt::index(__source.len(), __key)?]
        })
        .default_deal_duration
    } else {
        20i64
    }))
}

/// Resolve BIQ chains across each source unit's available civilizations.
// Python: openciv3/rules.py:277
pub(crate) fn RuleCatalog__unit_upgrade_links(
    self_: &RuleCatalog,
) -> rt::Result<Vec<std::collections::BTreeSet<i64>>> {
    let mut units: Vec<crate::openciv3::unit_rules::UnitPrototype> = (self_).units.clone();
    let mut links: Vec<std::collections::BTreeSet<i64>> = vec![];
    for mut for_target_281_8 in (units.clone())
        .into_iter()
        .enumerate()
        .map(|(__index, __value)| (__index as i64 + 0i64, __value))
        .collect::<Vec<_>>()
    {
        let (mut index, mut unit): (i64, crate::openciv3::unit_rules::UnitPrototype) =
            for_target_281_8;
        if (&(unit).upgrade_branches).is_some() {
            if ({
                let mut __comprehension_result_220: Vec<bool> = Vec::new();
                let __comprehension_source_219 = ((*((unit).upgrade_branches.clone())
                    .as_ref()
                    .ok_or("expected a value")?)
                .clone());
                for target in __comprehension_source_219.iter().cloned() {
                    __comprehension_result_220.push(
                        !({
                            let __compare_0 = 0i64;
                            let __compare_1 = target;
                            if (__compare_0 <= __compare_1) {
                                let __compare_2 = ((units).len() as i64);
                                (__compare_1 < __compare_2)
                            } else {
                                false
                            }
                        }),
                    );
                }
                __comprehension_result_220
            })
            .into_iter()
            .any(|__value| __value)
            {
                return Err("Invalid unit upgrade index".to_string().into());
            }
            {
                links.push({
                    let mut __result: std::collections::BTreeSet<i64> =
                        std::collections::BTreeSet::new();
                    for __item in ((*((unit).upgrade_branches.clone())
                        .as_ref()
                        .ok_or("expected a value")?)
                    .clone())
                    .into_iter()
                    {
                        __result.insert(__item);
                    }
                    __result
                });
            };
            continue;
        }
        let mut targets: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
        for mut civilization in (&(unit).available_to).iter().copied() {
            let mut target: i64 = (unit).upgrade_to;
            let mut seen: std::collections::BTreeSet<i64> = {
                let mut __result = std::collections::BTreeSet::new();
                for __item in vec![index].into_iter() {
                    __result.insert(__item);
                }
                __result
            };
            while (target >= 0i64) {
                if (target >= ((units).len() as i64)) {
                    return Err("Invalid unit upgrade index".to_string().into());
                }
                if {
                    let __needle = target;
                    let __container = &seen;
                    __container.contains(&__needle)
                } {
                    return Err("Cyclic unit upgrade chain".to_string().into());
                }
                {
                    seen.insert(target);
                };
                if {
                    let __needle = civilization;
                    let __container = &({
                        let __source = &units;
                        let __key = target;
                        &__source[rt::index(__source.len(), __key)?]
                    })
                    .available_to;
                    __container.contains(&__needle)
                } {
                    {
                        targets.insert(target);
                    };
                    break;
                }
                target = ({
                    let __source = &units;
                    let __key = target;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .upgrade_to;
            }
        }
        {
            links.push({
                let mut __result: std::collections::BTreeSet<i64> =
                    std::collections::BTreeSet::new();
                for __item in (targets).into_iter() {
                    __result.insert(__item);
                }
                __result
            });
        };
    }
    Ok((links).iter().cloned().collect::<Vec<_>>())
}

// Python: openciv3/rules.py:305
pub(crate) fn RuleCatalog__from_scenarios(
    scenario: &crate::openciv3::scenario::Scenario,
    defaults: &crate::openciv3::scenario::Scenario,
) -> rt::Result<RuleCatalog> {
    Ok(RuleCatalog {
        technologies: ({
            let mut __comprehension_result_222: Vec<Technology> = Vec::new();
            let __comprehension_source_221 =
                (RuleCatalog__from_scenarios__records(scenario, defaults, "TECH")?);
            for record in __comprehension_source_221.iter().cloned() {
                __comprehension_result_222.push(Technology__from_record(&record)?);
            }
            __comprehension_result_222
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        resources: ({
            let mut __comprehension_result_224: Vec<Resource> = Vec::new();
            let __comprehension_source_223 =
                (RuleCatalog__from_scenarios__records(scenario, defaults, "GOOD")?);
            for record in __comprehension_source_223.iter().cloned() {
                __comprehension_result_224.push(Resource__from_record(&record)?);
            }
            __comprehension_result_224
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        terrains: ({
            let mut __comprehension_result_226: Vec<Terrain> = Vec::new();
            let __comprehension_source_225 =
                (RuleCatalog__from_scenarios__records(scenario, defaults, "TERR")?);
            for record in __comprehension_source_225.iter().cloned() {
                __comprehension_result_226.push(Terrain__from_record(&record)?);
            }
            __comprehension_result_226
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        units: ({
            let mut __comprehension_result_228: Vec<crate::openciv3::unit_rules::UnitPrototype> =
                Vec::new();
            let __comprehension_source_227 =
                (RuleCatalog__from_scenarios__records(scenario, defaults, "PRTO")?);
            for record in __comprehension_source_227.iter().cloned() {
                __comprehension_result_228.push(
                    crate::openciv3::unit_rules::UnitPrototype__from_record(&record)?,
                );
            }
            __comprehension_result_228
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        experience_levels: ({
            let mut __comprehension_result_230: Vec<ExperienceLevel> = Vec::new();
            let __comprehension_source_229 =
                (RuleCatalog__from_scenarios__records(scenario, defaults, "EXPR")?);
            for record in __comprehension_source_229.iter().cloned() {
                __comprehension_result_230.push(ExperienceLevel__from_record(&record)?);
            }
            __comprehension_result_230
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        citizens: ({
            let mut __comprehension_result_232: Vec<CitizenType> = Vec::new();
            let __comprehension_source_231 =
                (RuleCatalog__from_scenarios__records(scenario, defaults, "CTZN")?);
            for record in __comprehension_source_231.iter().cloned() {
                __comprehension_result_232.push(CitizenType__from_record(&record)?);
            }
            __comprehension_result_232
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        worker_jobs: ({
            let mut __comprehension_result_234: Vec<WorkerJob> = Vec::new();
            let __comprehension_source_233 =
                (RuleCatalog__from_scenarios__records(scenario, defaults, "TFRM")?);
            for record in __comprehension_source_233.iter().cloned() {
                __comprehension_result_234.push(WorkerJob__from_record(&record)?);
            }
            __comprehension_result_234
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        governments: ({
            let mut __comprehension_result_236: Vec<crate::openciv3::government_rules::Government> =
                Vec::new();
            let __comprehension_source_235 =
                (RuleCatalog__from_scenarios__records(scenario, defaults, "GOVT")?);
            for record in __comprehension_source_235.iter().cloned() {
                __comprehension_result_236.push(
                    crate::openciv3::government_rules::Government__from_record(&record)?,
                );
            }
            __comprehension_result_236
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        buildings: ({
            let mut __comprehension_result_238: Vec<crate::openciv3::building_rules::Building> =
                Vec::new();
            let __comprehension_source_237 =
                (RuleCatalog__from_scenarios__records(scenario, defaults, "BLDG")?);
            for record in __comprehension_source_237.iter().cloned() {
                __comprehension_result_238.push(
                    crate::openciv3::building_rules::Building__from_record(&record)?,
                );
            }
            __comprehension_result_238
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
        global_rules: ({
            let mut __comprehension_result_240: Vec<crate::openciv3::global_rules::GlobalRules> =
                Vec::new();
            let __comprehension_source_239 =
                (RuleCatalog__from_scenarios__records(scenario, defaults, "RULE")?);
            for record in __comprehension_source_239.iter().cloned() {
                __comprehension_result_240.push(
                    crate::openciv3::global_rules::GlobalRules__from_record(&record)?,
                );
            }
            __comprehension_result_240
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>(),
    })
}

// Python: openciv3/rules.py:306
pub(crate) fn RuleCatalog__from_scenarios__records(
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
        let mut __comprehension_result_242: Vec<crate::openciv3::binary::Record> = Vec::new();
        let __comprehension_source_241 = ({
            let __mapping = &(source).sections;
            let __key = section.to_owned();
            let __default = vec![];
            __mapping.get(&__key).cloned().unwrap_or(__default)
        });
        for data in __comprehension_source_241.iter().cloned() {
            __comprehension_result_242.push(crate::openciv3::binary::Record {
                data: data.clone(),
                section: section.to_owned(),
                encoding: (source).encoding.clone(),
            });
        }
        __comprehension_result_242
    })
}
