use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct FoundationalRules {
    pub(crate) technologies: Vec<crate::openciv3::rules::Technology>,
    pub(crate) resources: Vec<crate::openciv3::rules::Resource>,
    pub(crate) terrains: Vec<crate::openciv3::rules::Terrain>,
    pub(crate) units: Vec<crate::openciv3::unit_rules::UnitPrototype>,
    pub(crate) buildings: Vec<crate::openciv3::building_rules::Building>,
    pub(crate) citizens: Vec<crate::openciv3::rules::CitizenType>,
    pub(crate) workers: Vec<crate::openciv3::rules::WorkerJob>,
    pub(crate) governments: Vec<crate::openciv3::government_rules::Government>,
    pub(crate) difficulties: Vec<crate::openciv3::scenario_model::Difficulty>,
    pub(crate) world_sizes: Vec<crate::openciv3::world_size::WorldSize>,
    pub(crate) experience: Vec<crate::openciv3::rules::ExperienceLevel>,
}

// Python: openciv3/json_rules.py:32
pub(crate) fn text(
    row: &indexmap::IndexMap<String, rt::Json>,
    key: &str,
    default: &str,
) -> rt::Result<String> {
    let mut value: rt::Json = {
        let __key = key.to_owned();
        let __default = serde_json::Value::from(default.to_owned());
        row.get(&__key).cloned().unwrap_or(__default)
    };
    if !(rt::json_kind(&(value.clone())) == "string") {
        return Err({
            let __separator = &(String::new());
            (&(vec![(key.to_owned()).to_string(), " must be text".to_string()])).join(__separator)
        }
        .into());
    }
    Ok(rt::json_string(&(value))?)
}

// Python: openciv3/json_rules.py:39
pub(crate) fn integer(
    row: &indexmap::IndexMap<String, rt::Json>,
    key: &str,
    mut default: i64,
) -> rt::Result<i64> {
    let mut value: rt::Json = {
        let __key = key.to_owned();
        let __default = serde_json::Value::from(default);
        row.get(&__key).cloned().unwrap_or(__default)
    };
    if rt::json_kind(&(value.clone())) != "number" {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                (key.to_owned()).to_string(),
                " must be an integer".to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    if !(rt::json_kind(&(value.clone())) == "number") {
        rt::assertion(false, &("".to_string()))?;
    }
    Ok(rt::json_int(&(value))?)
}

// Python: openciv3/json_rules.py:47
pub(crate) fn boolean(
    row: &indexmap::IndexMap<String, rt::Json>,
    key: &str,
    mut default: bool,
) -> rt::Result<bool> {
    let mut value: rt::Json = {
        let __key = key.to_owned();
        let __default = serde_json::Value::from(default);
        row.get(&__key).cloned().unwrap_or(__default)
    };
    if !(rt::json_kind(&(value.clone())) == "bool") {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                (key.to_owned()).to_string(),
                " must be a boolean".to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok(rt::json_bool(&(value))?)
}

// Python: openciv3/json_rules.py:54
pub(crate) fn strings(
    row: &indexmap::IndexMap<String, rt::Json>,
    key: &str,
) -> rt::Result<Vec<String>> {
    let mut value: rt::Json = {
        let __key = key.to_owned();
        let __default = serde_json::Value::Array(vec![]);
        row.get(&__key).cloned().unwrap_or(__default)
    };
    if (!(rt::json_kind(&(value.clone())) == "array")
        || ({
            let mut __comprehension_result_1203: Vec<bool> = Vec::new();
            let __comprehension_source_1202 = (rt::json_array(&(value.clone()))?);
            for item in __comprehension_source_1202.iter().cloned() {
                __comprehension_result_1203.push(!(rt::json_kind(&(item.clone())) == "string"));
            }
            __comprehension_result_1203
        })
        .into_iter()
        .any(|__value| __value))
    {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                (key.to_owned()).to_string(),
                " must be a text array".to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok(({
        let mut __comprehension_result_1205: Vec<String> = Vec::new();
        let __comprehension_source_1204 = (rt::json_array(&(value.clone()))?);
        for item in __comprehension_source_1204.iter().cloned() {
            if rt::json_kind(&(item.clone())) == "string" {
                __comprehension_result_1205.push(rt::json_string(&(item.clone()))?);
            }
        }
        __comprehension_result_1205
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>())
}

// Python: openciv3/json_rules.py:61
pub(crate) fn records(
    root: &indexmap::IndexMap<String, rt::Json>,
    key: &str,
) -> rt::Result<Vec<indexmap::IndexMap<String, rt::Json>>> {
    let mut value: Option<rt::Json> = ((*root).clone()).get(&(key.to_owned())).cloned();
    if (!(rt::json_kind(&((*(value.clone()).as_ref().ok_or("expected a value")?).clone()))
        == "array")
        || ({
            let mut __comprehension_result_1207: Vec<bool> = Vec::new();
            let __comprehension_source_1206 = (rt::json_array(
                &((*(value.clone()).as_ref().ok_or("expected a value")?).clone()),
            )?);
            for item in __comprehension_source_1206.iter().cloned() {
                __comprehension_result_1207.push(!(rt::json_kind(&(item.clone())) == "object"));
            }
            __comprehension_result_1207
        })
        .into_iter()
        .any(|__value| __value))
    {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                (key.to_owned()).to_string(),
                " must be an object array".to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok(({
        let mut __comprehension_result_1209: Vec<indexmap::IndexMap<String, rt::Json>> = Vec::new();
        let __comprehension_source_1208 =
            (rt::json_array(&((*(value.clone()).as_ref().ok_or("expected a value")?).clone()))?);
        for item in __comprehension_source_1208.iter().cloned() {
            if rt::json_kind(&(item.clone())) == "object" {
                __comprehension_result_1209.push(rt::json_object(&(item.clone()))?);
            }
        }
        __comprehension_result_1209
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>())
}

// Python: openciv3/json_rules.py:68
pub(crate) fn identifiers(
    rows: &[indexmap::IndexMap<String, rt::Json>],
    key: &str,
) -> rt::Result<indexmap::IndexMap<String, i64>> {
    let mut result: indexmap::IndexMap<String, i64> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut for_target_70_4 in (rows.to_vec())
        .into_iter()
        .enumerate()
        .map(|(__index, __value)| (__index as i64 + 0i64, __value))
        .collect::<Vec<_>>()
    {
        let (mut index, mut row): (i64, indexmap::IndexMap<String, rt::Json>) = for_target_70_4;
        let mut name: String = text(&row, key, "")?;
        if (!(((name).chars().count() as i64) != 0i64) || {
            let __needle: &str = AsRef::<str>::as_ref(&name);
            let __container = &result;
            __container.contains_key(__needle)
        }) {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Missing or duplicate ".to_string(),
                    (key.to_owned()).to_string(),
                    ": ".to_string(),
                    (name).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        {
            let __value = index;
            let __key = name;
            result.insert(__key, __value);
        }
    }
    Ok(result)
}

// Python: openciv3/json_rules.py:78
pub(crate) fn reference(
    row: &indexmap::IndexMap<String, rt::Json>,
    key: &str,
    indices: &indexmap::IndexMap<String, i64>,
) -> rt::Result<i64> {
    if (((*row).clone()).get(&(key.to_owned())).cloned()).is_none() {
        return Ok((1i64).checked_neg().ok_or("integer overflow")?);
    }
    let mut name: String = text(row, key, "")?;
    if {
        let __needle: &str = AsRef::<str>::as_ref(&name);
        let __container = indices;
        !__container.contains_key(__needle)
    } {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Unknown ".to_string(),
                (key.to_owned()).to_string(),
                ": ".to_string(),
                (name).to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok((indices).get(&name).ok_or("missing dict key")?.clone())
}

// Python: openciv3/json_rules.py:102
pub(crate) fn decode_foundational_rules(
    root: &indexmap::IndexMap<String, rt::Json>,
) -> rt::Result<FoundationalRules> {
    let mut tech_rows: Vec<indexmap::IndexMap<String, rt::Json>> = records(root, "techs")?;
    let mut tech_ids: indexmap::IndexMap<String, i64> = identifiers(&tech_rows, "id")?;
    let mut resource_rows: Vec<indexmap::IndexMap<String, rt::Json>> = records(root, "resources")?;
    let mut resource_ids: indexmap::IndexMap<String, i64> = identifiers(&resource_rows, "key")?;
    let mut technologies: Vec<crate::openciv3::rules::Technology> = vec![];
    for mut row in tech_rows {
        let mut effects: i64 = 0i64;
        for mut flag in strings(&row, "flags")? {
            if {
                let __needle: &str = AsRef::<str>::as_ref(&flag);
                let __container = {
                    static __CONSTANT_py__openciv3__json_rules__TECH_FLAGS: std::sync::OnceLock<
                        indexmap::IndexMap<String, i64>,
                    > = std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__json_rules__TECH_FLAGS
                        .get()
                        .is_none()
                    {
                        let __constant_value = [
                            ("bonusTechToFirstCivThatResearches".to_string(), 2097152i64),
                            ("enablesBridges".to_string(), 4i64),
                            ("doublesWealthProduction".to_string(), 4096i64),
                            ("doublesWorkerRate".to_string(), 262144i64),
                            ("cannotBeTraded".to_string(), 524288i64),
                            ("seaTrade".to_string(), 8192i64),
                            ("oceanTrade".to_string(), 16384i64),
                            ("rightOfPassage".to_string(), 512i64),
                        ]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>();
                        let _ =
                            __CONSTANT_py__openciv3__json_rules__TECH_FLAGS.set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__json_rules__TECH_FLAGS
                        .get()
                        .ok_or("missing module constant")?
                };
                !__container.contains_key(__needle)
            } {
                return Err({
                    let __separator = &(String::new());
                    (&(vec![
                        "Unsupported technology flag: ".to_string(),
                        (flag).to_string(),
                    ]))
                        .join(__separator)
                }
                .into());
            }
            effects = (effects
                | ({
                    static __CONSTANT_py__openciv3__json_rules__TECH_FLAGS: std::sync::OnceLock<
                        indexmap::IndexMap<String, i64>,
                    > = std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__json_rules__TECH_FLAGS
                        .get()
                        .is_none()
                    {
                        let __constant_value = [
                            ("bonusTechToFirstCivThatResearches".to_string(), 2097152i64),
                            ("enablesBridges".to_string(), 4i64),
                            ("doublesWealthProduction".to_string(), 4096i64),
                            ("doublesWorkerRate".to_string(), 262144i64),
                            ("cannotBeTraded".to_string(), 524288i64),
                            ("seaTrade".to_string(), 8192i64),
                            ("oceanTrade".to_string(), 16384i64),
                            ("rightOfPassage".to_string(), 512i64),
                        ]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>();
                        let _ =
                            __CONSTANT_py__openciv3__json_rules__TECH_FLAGS.set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__json_rules__TECH_FLAGS
                        .get()
                        .ok_or("missing module constant")?
                })
                .get(&flag)
                .ok_or("missing dict key")?
                .clone());
        }
        if !(boolean(&row, "requiredForEraAdvancement", false)?) {
            effects = (effects | 131072i64);
        }
        let mut era: String = text(&row, "eraCivilopediaName", "")?;
        if ((era.as_str() != "Hidden") && {
            let __needle = era.clone();
            let __container = &({
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
            });
            !__container.contains(&__needle)
        }) {
            return Err({
                let __separator = &(String::new());
                (&(vec!["Unknown era: ".to_string(), (era).to_string()])).join(__separator)
            }
            .into());
        }
        let mut prerequisites: Vec<i64> = ({
            let mut __comprehension_result_1211: Vec<i64> = Vec::new();
            let __comprehension_source_1210 = (strings(&row, "prerequisites")?);
            for key in __comprehension_source_1210.iter().cloned() {
                __comprehension_result_1211.push(reference(
                    &([(
                        "prerequisite".to_string(),
                        serde_json::Value::from(key.clone()),
                    )]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>()),
                    "prerequisite",
                    &tech_ids,
                )?);
            }
            __comprehension_result_1211
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        {
            technologies.push(crate::openciv3::rules::Technology { name: text(&row, "name", "")?, civilopedia_entry: text(&row, "civilopediaEntry", "")?, cost: integer(&row, "cost", 0i64)?, era: (if (era.as_str() == "Hidden") { (1i64).checked_neg().ok_or("integer overflow")? } else { rt::index_of(&(vec![({ static __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS: std::sync::OnceLock<(String, String, String, String,)> = std::sync::OnceLock::new(); if __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS.get().is_none() { let __constant_value = ("ERAS_Ancient_Times".to_string(), "ERAS_Middle_Ages".to_string(), "ERAS_Industrial_Age".to_string(), "ERAS_Modern_Era".to_string(),); let _ = __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS.set(__constant_value); } __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS.get().ok_or("missing module constant")?.clone() }).0.clone(), ({ static __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS: std::sync::OnceLock<(String, String, String, String,)> = std::sync::OnceLock::new(); if __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS.get().is_none() { let __constant_value = ("ERAS_Ancient_Times".to_string(), "ERAS_Middle_Ages".to_string(), "ERAS_Industrial_Age".to_string(), "ERAS_Modern_Era".to_string(),); let _ = __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS.set(__constant_value); } __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS.get().ok_or("missing module constant")?.clone() }).1.clone(), ({ static __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS: std::sync::OnceLock<(String, String, String, String,)> = std::sync::OnceLock::new(); if __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS.get().is_none() { let __constant_value = ("ERAS_Ancient_Times".to_string(), "ERAS_Middle_Ages".to_string(), "ERAS_Industrial_Age".to_string(), "ERAS_Modern_Era".to_string(),); let _ = __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS.set(__constant_value); } __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS.get().ok_or("missing module constant")?.clone() }).2.clone(), ({ static __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS: std::sync::OnceLock<(String, String, String, String,)> = std::sync::OnceLock::new(); if __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS.get().is_none() { let __constant_value = ("ERAS_Ancient_Times".to_string(), "ERAS_Middle_Ages".to_string(), "ERAS_Industrial_Age".to_string(), "ERAS_Modern_Era".to_string(),); let _ = __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS.set(__constant_value); } __CONSTANT_py__openciv3__scenario_model__DEFAULT_ERA_IDENTIFIERS.get().ok_or("missing module constant")?.clone() }).3.clone()]), &(era.clone()))? }), icon: (1i64).checked_neg().ok_or("integer overflow")?, x: integer(&row, "x", 0i64)?, y: integer(&row, "y", 0i64)?, prerequisites: prerequisites, effects: effects, flavors: 0i64, media_key: text(&row, "id", "")?, small_icon_path: text(&row, "smallIconPath", "")? });
        };
    }
    let mut kinds: indexmap::IndexMap<String, i64> = [
        ("bonus".to_string(), 0i64),
        ("luxury".to_string(), 1i64),
        ("strategic".to_string(), 2i64),
    ]
    .into_iter()
    .collect::<indexmap::IndexMap<_, _>>();
    let mut resources: Vec<crate::openciv3::rules::Resource> = vec![];
    for mut row in resource_rows {
        let mut kind: String = text(&row, "category", "")?;
        if {
            let __needle: &str = AsRef::<str>::as_ref(&kind);
            let __container = &kinds;
            !__container.contains_key(__needle)
        } {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Unknown resource category: ".to_string(),
                    (kind).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        {
            resources.push(crate::openciv3::rules::Resource {
                name: text(&row, "name", "")?,
                civilopedia_entry: text(&row, "civilopediaEntry", "")?,
                kind: (kinds).get(&kind).ok_or("missing dict key")?.clone(),
                appearance_ratio: integer(&row, "appearanceRatio", 0i64)?,
                disappearance_probability: integer(&row, "disappearanceRatio", 0i64)?,
                icon: integer(&row, "icon", 0i64)?,
                prerequisite: reference(&row, "prerequisite", &tech_ids)?,
                bonus: crate::civ::economy::Yield {
                    food: integer(&row, "foodBonus", 0i64)?,
                    shields: integer(&row, "shieldsBonus", 0i64)?,
                    commerce: integer(&row, "commerceBonus", 0i64)?,
                },
            });
        };
    }
    let mut citizens: Vec<crate::openciv3::rules::CitizenType> = ({
        let mut __comprehension_result_1213: Vec<crate::openciv3::rules::CitizenType> = Vec::new();
        let __comprehension_source_1212 = (records(root, "citizenTypes")?);
        for row in __comprehension_source_1212.iter().cloned() {
            __comprehension_result_1213.push(crate::openciv3::rules::CitizenType {
                default_citizen: boolean(&row, "isDefaultCitizen", false)?,
                singular_name: text(&row, "singularName", "")?,
                civilopedia_entry: text(&row, "civilopediaEntry", "")?,
                plural_name: text(&row, "pluralName", "")?,
                prerequisite: reference(&row, "prerequisiteTech", &tech_ids)?,
                luxuries: integer(&row, "luxuries", 0i64)?,
                research: integer(&row, "research", 0i64)?,
                taxes: integer(&row, "taxes", 0i64)?,
                corruption: integer(&row, "corruption", 0i64)?,
                construction: integer(&row, "construction", 0i64)?,
            });
        }
        __comprehension_result_1213
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut workers: Vec<crate::openciv3::rules::WorkerJob> = vec![];

    let mut supported_improvements: std::collections::BTreeSet<i64> = {
        let mut __result: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
        for __item in (({
            static __CONSTANT_py__openciv3__worker_rules__IMPROVEMENTS: std::sync::OnceLock<
                indexmap::IndexMap<String, i64>,
            > = std::sync::OnceLock::new();
            if __CONSTANT_py__openciv3__worker_rules__IMPROVEMENTS
                .get()
                .is_none()
            {
                let __constant_value = {
                    let mut __result: indexmap::IndexMap<String, i64> = indexmap::IndexMap::new();
                    __result.extend(
                        [
                            ("BuildRoad".to_string(), 1i64),
                            ("BuildRailroad".to_string(), 2i64),
                            ("BuildMine".to_string(), 4i64),
                            ("Irrigate".to_string(), 8i64),
                            ("BuildFortress".to_string(), 16i64),
                            ("BuildBarricade".to_string(), 268435456i64),
                        ]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>(),
                    );
                    __result.extend({
                        static __CONSTANT_py__openciv3__worker_rules__INSTALLATIONS:
                            std::sync::OnceLock<indexmap::IndexMap<String, i64>> =
                            std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__worker_rules__INSTALLATIONS
                            .get()
                            .is_none()
                        {
                            let __constant_value = [
                                ("BuildAirfield".to_string(), 536870912i64),
                                ("BuildRadarTower".to_string(), 1073741824i64),
                                ("BuildOutpost".to_string(), 2147483648i64),
                            ]
                            .into_iter()
                            .collect::<indexmap::IndexMap<_, _>>();
                            let _ = __CONSTANT_py__openciv3__worker_rules__INSTALLATIONS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__worker_rules__INSTALLATIONS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    });
                    __result
                };
                let _ = __CONSTANT_py__openciv3__worker_rules__IMPROVEMENTS.set(__constant_value);
            }
            __CONSTANT_py__openciv3__worker_rules__IMPROVEMENTS
                .get()
                .ok_or("missing module constant")?
                .clone()
        })
        .values()
        .cloned()
        .collect::<Vec<_>>())
        .into_iter()
        {
            __result.insert(__item);
        }
        __result
    };
    for mut row in records(root, "terraForms")? {
        let mut action: String = text(&row, "uiAction", "")?;
        let mut order: String = {
            let __separator = &(String::new());
            (&({
                let mut __comprehension_result_1215: Vec<String> = Vec::new();
                let __comprehension_source_1214 =
                    (rt::str_split(&(rt::string_remove_prefix(&action, "unit_")), "_")?);
                for part in __comprehension_source_1214.iter().cloned() {
                    __comprehension_result_1215.push(rt::string_capitalize(&part));
                }
                __comprehension_result_1215
            }))
                .join(__separator)
        };
        if (!((&action).starts_with("unit_")) || !(((order).chars().count() as i64) != 0i64)) {
            return Err({
                let __separator = &(String::new());
                (&(vec!["Unknown worker action: ".to_string(), (action).to_string()]))
                    .join(__separator)
            }
            .into());
        }
        let mut required: Vec<i64> = ({
            let mut __comprehension_result_1217: Vec<i64> = Vec::new();
            let __comprehension_source_1216 = (strings(&row, "requiredResources")?);
            for key in __comprehension_source_1216.iter().cloned() {
                __comprehension_result_1217.push(reference(
                    &([("resource".to_string(), serde_json::Value::from(key.clone()))]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>()),
                    "resource",
                    &resource_ids,
                )?);
            }
            __comprehension_result_1217
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        let mut score_path: String = text(&row, "aiScore", "")?;
        let mut score: Option<crate::openciv3::rules::WorkerScore> = None;
        if (((score_path).chars().count() as i64) != 0i64) {
            let mut prefix: String = "terraforms.ai_score.".to_string();
            if !((&score_path).starts_with(&prefix)) {
                return Err({
                    let __separator = &(String::new());
                    (&(vec![
                        "Unknown worker AI score: ".to_string(),
                        (score_path).to_string(),
                    ]))
                        .join(__separator)
                }
                .into());
            }
            score = Some(
                match (rt::string_remove_prefix(&score_path, &prefix)).as_str() {
                    "default" => crate::openciv3::rules::WorkerScore::DEFAULT,
                    "clear_wetlands" => crate::openciv3::rules::WorkerScore::CLEAR_WETLANDS,
                    "railroad" => crate::openciv3::rules::WorkerScore::RAILROAD,
                    "clear_forest" => crate::openciv3::rules::WorkerScore::CLEAR_FOREST,
                    "yield_improvement" => crate::openciv3::rules::WorkerScore::YIELD_IMPROVEMENT,
                    "road" => crate::openciv3::rules::WorkerScore::ROAD,
                    _ => return Err("unknown enum value".into()),
                },
            );
        }
        let mut validators: Vec<crate::openciv3::rules::WorkerValidator> = ({
            let mut __comprehension_result_1219: Vec<crate::openciv3::rules::WorkerValidator> =
                Vec::new();
            let __comprehension_source_1218 = (strings(&row, "validators")?);
            for path in __comprehension_source_1218.iter().cloned() {
                __comprehension_result_1219.push(
                    match (rt::string_remove_prefix(&path, "terraforms.validators.")).as_str() {
                        "mine" => crate::openciv3::rules::WorkerValidator::MINE,
                        "irrigate" => crate::openciv3::rules::WorkerValidator::IRRIGATE,
                        "clear_forest" => crate::openciv3::rules::WorkerValidator::CLEAR_FOREST,
                        "clear_wetlands" => crate::openciv3::rules::WorkerValidator::CLEAR_WETLANDS,
                        _ => return Err("unknown enum value".into()),
                    },
                );
            }
            __comprehension_result_1219
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        let mut worker_effects: Vec<crate::openciv3::rules::WorkerEffect> = ({
            let mut __comprehension_result_1221: Vec<crate::openciv3::rules::WorkerEffect> =
                Vec::new();
            let __comprehension_source_1220 = (strings(&row, "effects")?);
            for path in __comprehension_source_1220.iter().cloned() {
                __comprehension_result_1221.push(
                    match (rt::string_remove_prefix(&path, "terraforms.effects.")).as_str() {
                        "clear_forest" => crate::openciv3::rules::WorkerEffect::CLEAR_FOREST,
                        "clear_wetlands" => crate::openciv3::rules::WorkerEffect::CLEAR_WETLANDS,
                        _ => return Err("unknown enum value".into()),
                    },
                );
            }
            __comprehension_result_1221
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        let mut improvement_key: String = text(&row, "improvement", "")?;
        let mut improvement: i64 = {
            let __mapping = {
                static __CONSTANT_py__openciv3__worker_rules__INSTALLATIONS: std::sync::OnceLock<
                    indexmap::IndexMap<String, i64>,
                > = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__worker_rules__INSTALLATIONS
                    .get()
                    .is_none()
                {
                    let __constant_value = [
                        ("BuildAirfield".to_string(), 536870912i64),
                        ("BuildRadarTower".to_string(), 1073741824i64),
                        ("BuildOutpost".to_string(), 2147483648i64),
                    ]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>();
                    let _ =
                        __CONSTANT_py__openciv3__worker_rules__INSTALLATIONS.set(__constant_value);
                }
                __CONSTANT_py__openciv3__worker_rules__INSTALLATIONS
                    .get()
                    .ok_or("missing module constant")?
            };
            let __key = order.clone();
            let __default = 0i64;
            __mapping.get(&__key).cloned().unwrap_or(__default)
        };
        if (((improvement_key).chars().count() as i64) != 0i64) {
            improvement = {
                let __mapping = {
                    static __CONSTANT_py__openciv3__world__OVERLAY_KEYS: std::sync::OnceLock<
                        indexmap::IndexMap<String, i64>,
                    > = std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__world__OVERLAY_KEYS.get().is_none() {
                        let __constant_value = [
                            ("road".to_string(), 1i64),
                            ("railroad".to_string(), 2i64),
                            ("mine".to_string(), 4i64),
                            ("irrigation".to_string(), 8i64),
                            ("fortress".to_string(), 16i64),
                            ("goodyHut".to_string(), 32i64),
                            ("pollution".to_string(), 64i64),
                            ("barbarianCamp".to_string(), 128i64),
                            ("craters".to_string(), 256i64),
                            ("barricade".to_string(), 268435456i64),
                            ("airfield".to_string(), 536870912i64),
                            ("radarTower".to_string(), 1073741824i64),
                            ("outpost".to_string(), 2147483648i64),
                        ]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>();
                        let _ = __CONSTANT_py__openciv3__world__OVERLAY_KEYS.set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__world__OVERLAY_KEYS
                        .get()
                        .ok_or("missing module constant")?
                };
                let __key = improvement_key.clone();
                let __default = 0i64;
                __mapping.get(&__key).cloned().unwrap_or(__default)
            };
            if {
                let __needle = improvement;
                let __container = &supported_improvements;
                !__container.contains(&__needle)
            } {
                return Err({
                    let __separator = &(String::new());
                    (&(vec![
                        "Unknown worker improvement: ".to_string(),
                        (improvement_key).to_string(),
                    ]))
                        .join(__separator)
                }
                .into());
            }
        }
        if ({
            let __needle: &str = AsRef::<str>::as_ref(&order);
            let __container = {
                static __CONSTANT_py__openciv3__worker_rules__ORDERS: std::sync::OnceLock<
                    indexmap::IndexMap<String, i64>,
                > = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__worker_rules__ORDERS
                    .get()
                    .is_none()
                {
                    let __constant_value = [
                        ("BuildRoad".to_string(), 8388608i64),
                        ("BuildRailroad".to_string(), 16777216i64),
                        ("BuildMine".to_string(), 67108864i64),
                        ("Irrigate".to_string(), 134217728i64),
                        ("BuildFortress".to_string(), 33554432i64),
                        ("BuildBarricade".to_string(), 137438953472i64),
                        ("ClearForest".to_string(), 268435456i64),
                        ("ClearWetlands".to_string(), 536870912i64),
                        ("PlantForest".to_string(), 1073741824i64),
                        ("ClearDamage".to_string(), 2147483648i64),
                        ("BuildAirfield".to_string(), 17179869184i64),
                        ("BuildRadarTower".to_string(), 34359738368i64),
                        ("BuildOutpost".to_string(), 68719476736i64),
                    ]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>();
                    let _ = __CONSTANT_py__openciv3__worker_rules__ORDERS.set(__constant_value);
                }
                __CONSTANT_py__openciv3__worker_rules__ORDERS
                    .get()
                    .ok_or("missing module constant")?
            };
            !__container.contains_key(__needle)
        } && !((improvement) != 0 || !(worker_effects.clone()).is_empty()))
        {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Worker action has no configured effect: ".to_string(),
                    (action).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        {
            workers.push(crate::openciv3::rules::WorkerJob {
                name: text(&row, "name", "")?,
                civilopedia_entry: text(&row, "civilopediaEntry", "")?,
                turns_to_complete: integer(&row, "turnsToComplete", 0i64)?,
                prerequisite: reference(&row, "requiredTech", &tech_ids)?,
                required_resources: required,
                order: order,
                animation: (&(text(&row, "animation", "")?)).to_uppercase(),
                ai_score: score,
                validators: Some(validators),
                effects: Some(worker_effects),
                improvement: Some(improvement),
            });
        };
    }
    let mut governments: Vec<crate::openciv3::government_rules::Government> = ({
        let mut __comprehension_result_1223: Vec<crate::openciv3::government_rules::Government> =
            Vec::new();
        let __comprehension_source_1222 = (records(root, "governments")?);
        for row in __comprehension_source_1222.iter().cloned() {
            __comprehension_result_1223.push(decode_government(&row, &tech_ids)?);
        }
        __comprehension_result_1223
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut difficulties: Vec<crate::openciv3::scenario_model::Difficulty> = ({
        let mut __comprehension_result_1225: Vec<crate::openciv3::scenario_model::Difficulty> =
            Vec::new();
        let __comprehension_source_1224 = (records(root, "difficulties")?);
        for row in __comprehension_source_1224.iter().cloned() {
            __comprehension_result_1225.push(crate::openciv3::scenario_model::Difficulty {
                name: text(&row, "name", "")?,
                content_citizens: integer(&row, "numberOfCitizensBornContent", 0i64)?,
                max_ai_anarchy_turns: integer(&row, "maxAiGovernmentTransitionTime", 0i64)?,
                ai_defensive_units: integer(&row, "numberOfAIDefensiveStartingUnits", 0i64)?,
                ai_offensive_units: integer(&row, "numberOfAIOffensiveStartingUnits", 0i64)?,
                extra_start_unit_1: integer(&row, "extraStartUnit1", 0i64)?,
                extra_start_unit_2: integer(&row, "extraStartUnit2", 0i64)?,
                additional_free_support: integer(&row, "additionalFreeUnitSupport", 0i64)?,
                support_per_settlement: integer(&row, "unitSupportBonusForEachSettlement", 0i64)?,
                barbarian_attack_bonus: integer(&row, "attackBonusAgainstBarbarians", 0i64)?,
                ai_cost_factor: integer(&row, "aiCostFactor", 0i64)?,
                optimal_cities_percent: integer(&row, "percentageOfOptimalCities", 0i64)?,
                ai_trade_rate: integer(&row, "aiToAITradeRate", 0i64)?,
                corruption_percent: integer(&row, "corruptionPercentage", 0i64)?,
                military_law: integer(&row, "militaryLaw", 0i64)?,
                human_cost_factor: integer(&row, "humanCostFactor", 10i64)?,
            });
        }
        __comprehension_result_1225
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut sizes: Vec<crate::openciv3::world_size::WorldSize> = ({
        let mut __comprehension_result_1227: Vec<crate::openciv3::world_size::WorldSize> =
            Vec::new();
        let __comprehension_source_1226 = (records(root, "worldSizes")?);
        for row in __comprehension_source_1226.iter().cloned() {
            __comprehension_result_1227.push(crate::openciv3::world_size::WorldSize {
                optimal_cities: integer(&row, "optimalNumberOfCities", 0i64)?,
                tech_rate: integer(&row, "techRate", 0i64)?,
                name: text(&row, "name", "")?,
                height: integer(&row, "height", 0i64)?,
                civilization_distance: integer(&row, "distanceBetweenCivs", 0i64)?,
                civilization_count: integer(&row, "numberOfCivs", 0i64)?,
                width: integer(&row, "width", 0i64)?,
            });
        }
        __comprehension_result_1227
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut experience: Vec<crate::openciv3::rules::ExperienceLevel> = vec![];
    for mut row in records(root, "experienceLevels")? {
        let mut chance: rt::Json = {
            let __key = "retreatChance".to_string();
            let __default = serde_json::Value::from(0i64);
            row.get(&__key).cloned().unwrap_or(__default)
        };
        if (!(rt::json_kind(&(chance.clone())) == "number")
            || (rt::json_kind(&(chance.clone())) == "bool"
                || !({
                    let __compare_0 = 0i64;
                    let __compare_1 = chance.clone();
                    if (((__compare_0) as f64) <= rt::json_float(&(__compare_1))?) {
                        let __compare_2 = 1i64;
                        (rt::json_float(&(__compare_1))? <= ((__compare_2) as f64))
                    } else {
                        false
                    }
                })))
        {
            return Err("retreatChance must be a probability between 0 and 1"
                .to_string()
                .into());
        }
        let mut promotion: Option<rt::Json> =
            (row.clone()).get(&("promotionChance".to_string())).cloned();
        if ((promotion).is_some()
            && (!(rt::json_kind(
                &((*(promotion.clone()).as_ref().ok_or("expected a value")?).clone()),
            ) == "number")
                || (rt::json_kind(
                    &((*(promotion.clone()).as_ref().ok_or("expected a value")?).clone()),
                ) == "bool"
                    || !({
                        let __compare_0 = 0i64;
                        let __compare_1 = promotion.clone();
                        if (((__compare_0) as f64)
                            <= rt::json_float(
                                &((*(__compare_1).as_ref().ok_or("expected a value")?).clone()),
                            )?)
                        {
                            let __compare_2 = 1i64;
                            (rt::json_float(
                                &((*(__compare_1).as_ref().ok_or("expected a value")?).clone()),
                            )? <= ((__compare_2) as f64))
                        } else {
                            false
                        }
                    }))))
        {
            return Err("promotionChance must be a probability between 0 and 1"
                .to_string()
                .into());
        }
        {
            experience.push(crate::openciv3::rules::ExperienceLevel {
                name: text(&row, "displayName", "")?,
                base_hit_points: integer(&row, "baseHitPoints", 0i64)?,
                retreat_bonus: rt::finite(rt::json_float(&(chance))? * ((100i64) as f64))?,
                promotion_chance: (if (promotion).is_none() {
                    None
                } else {
                    Some(rt::json_float(
                        &((*(promotion.clone()).as_ref().ok_or("expected a value")?).clone()),
                    )?)
                }),
            });
        };
    }
    Ok(FoundationalRules {
        technologies: (technologies).iter().cloned().collect::<Vec<_>>(),
        resources: (resources).iter().cloned().collect::<Vec<_>>(),
        terrains: decode_terrains(root, &resource_ids)?,
        units: decode_units(
            &((*root).clone()),
            &(tech_ids.clone()),
            &(resource_ids.clone()),
            &((workers).iter().cloned().collect::<Vec<_>>()),
        )?,
        buildings: decode_buildings(root, &tech_ids, &resource_ids)?,
        citizens: citizens,
        workers: (workers).iter().cloned().collect::<Vec<_>>(),
        governments: governments,
        difficulties: difficulties,
        world_sizes: sizes,
        experience: (experience).iter().cloned().collect::<Vec<_>>(),
    })
}

// Python: openciv3/json_rules.py:200
pub(crate) fn decode_government(
    row: &indexmap::IndexMap<String, rt::Json>,
    technologies: &indexmap::IndexMap<String, i64>,
) -> rt::Result<crate::openciv3::government_rules::Government> {
    let mut corruption: (String, String, String, String, String, String, String) = (
        "minimal".to_string(),
        "nuisance".to_string(),
        "problematic".to_string(),
        "rampant".to_string(),
        "catastrophic".to_string(),
        "communal".to_string(),
        "off".to_string(),
    );
    let mut hurrying: (String, String, String) = (
        "cannotHurry".to_string(),
        "forcedLabor".to_string(),
        "paidLabor".to_string(),
    );
    Ok(crate::openciv3::government_rules::Government {
        name: text(row, "name", "")?,
        civilopedia_entry: text(row, "civilopediaEntry", "")?,
        default_type: boolean(row, "defaultType", false)?,
        transition_type: boolean(row, "transitionType", false)?,
        requires_maintenance: !(boolean(row, "transitionType", false)?),
        toggle_1: 0i64,
        tile_penalty: boolean(row, "hasTilePenalty", false)?,
        trade_bonus: boolean(row, "hasTradeBonus", false)?,
        ruler_titles: vec![],
        corruption: rt::index_of(
            &(vec![
                (corruption).0.clone(),
                (corruption).1.clone(),
                (corruption).2.clone(),
                (corruption).3.clone(),
                (corruption).4.clone(),
                (corruption).5.clone(),
                (corruption).6.clone(),
            ]),
            &(text(row, "corruptionType", "")?),
        )?,
        immune_to: (1i64).checked_neg().ok_or("integer overflow")?,
        diplomats_are: 0i64,
        spies_are: 0i64,
        relations: vec![],
        hurrying: rt::index_of(
            &(vec![
                (hurrying).0.clone(),
                (hurrying).1.clone(),
                (hurrying).2.clone(),
            ]),
            &(text(row, "hurryingType", "")?),
        )?,
        assimilation_chance: 0i64,
        draft_limit: integer(row, "draftLimit", 0i64)?,
        military_police_limit: integer(row, "militaryPoliceLimit", 0i64)?,
        ruler_title_pairs_used: 0i64,
        prerequisite: reference(row, "prerequisiteTech", technologies)?,
        science_rate_cap: 10i64,
        worker_rate: integer(row, "workerRate", 2i64)?,
        toggle_2: 0i64,
        toggle_3: 0i64,
        free_units: (if boolean(row, "allUnitsFree", false)? {
            (1i64).checked_neg().ok_or("integer overflow")?
        } else {
            0i64
        }),
        free_units_per_town: integer(row, "freeUnitsPerTown", 0i64)?,
        free_units_per_city: integer(row, "freeUnitsPerCity", 0i64)?,
        free_units_per_metropolis: integer(row, "freeUnitsPerMetropolis", 0i64)?,
        unit_cost: integer(row, "unitCost", 0i64)?,
        war_weariness: 0i64,
        xenophobic: false,
        force_resettle: false,
    })
}

// Python: openciv3/json_rules.py:224
pub(crate) fn object_field(
    row: &indexmap::IndexMap<String, rt::Json>,
    key: &str,
) -> rt::Result<indexmap::IndexMap<String, rt::Json>> {
    let mut value: rt::Json = {
        let __key = key.to_owned();
        let __default = serde_json::Value::Object([].into_iter().collect());
        row.get(&__key).cloned().unwrap_or(__default)
    };
    if !(rt::json_kind(&(value.clone())) == "object") {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                (key.to_owned()).to_string(),
                " must be an object".to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok(rt::json_object(&(value))?)
}

// Python: openciv3/json_rules.py:231
pub(crate) fn decode_terrains(
    root: &indexmap::IndexMap<String, rt::Json>,
    resources: &indexmap::IndexMap<String, i64>,
) -> rt::Result<Vec<crate::openciv3::rules::Terrain>> {
    let mut rows: Vec<indexmap::IndexMap<String, rt::Json>> = records(root, "terrainTypes")?;
    let mut indices: indexmap::IndexMap<String, i64> = identifiers(&rows, "key")?;
    if (((indices.clone()).keys().cloned().collect::<Vec<_>>())
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>()
        != ({
            let __tuple_value = &({
                static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS: std::sync::OnceLock<(
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                )> = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                    .get()
                    .is_none()
                {
                    let __constant_value = (
                        "desert".to_string(),
                        "plains".to_string(),
                        "grassland".to_string(),
                        "tundra".to_string(),
                        "flood plain".to_string(),
                        "hills".to_string(),
                        "mountains".to_string(),
                        "forest".to_string(),
                        "jungle".to_string(),
                        "marsh".to_string(),
                        "volcano".to_string(),
                        "coast".to_string(),
                        "sea".to_string(),
                        "ocean".to_string(),
                    );
                    let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS.set(__constant_value);
                }
                __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                    .get()
                    .ok_or("missing module constant")?
                    .clone()
            });
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
                __tuple_value.3.clone(),
                __tuple_value.4.clone(),
                __tuple_value.5.clone(),
                __tuple_value.6.clone(),
                __tuple_value.7.clone(),
                __tuple_value.8.clone(),
                __tuple_value.9.clone(),
                __tuple_value.10.clone(),
                __tuple_value.11.clone(),
                __tuple_value.12.clone(),
                __tuple_value.13.clone(),
            ]
        })
        .into_iter()
        .collect::<std::collections::BTreeSet<_>>())
    {
        return Err("Terrain catalog must contain the standard terrain keys"
            .to_string()
            .into());
    }
    let mut terrain_ids: indexmap::IndexMap<String, i64> = {
        let mut __comprehension_result_1229: indexmap::IndexMap<String, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_1228 = (({
            let __tuple_value = &({
                static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS: std::sync::OnceLock<(
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                    String,
                )> = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                    .get()
                    .is_none()
                {
                    let __constant_value = (
                        "desert".to_string(),
                        "plains".to_string(),
                        "grassland".to_string(),
                        "tundra".to_string(),
                        "flood plain".to_string(),
                        "hills".to_string(),
                        "mountains".to_string(),
                        "forest".to_string(),
                        "jungle".to_string(),
                        "marsh".to_string(),
                        "volcano".to_string(),
                        "coast".to_string(),
                        "sea".to_string(),
                        "ocean".to_string(),
                    );
                    let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS.set(__constant_value);
                }
                __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                    .get()
                    .ok_or("missing module constant")?
                    .clone()
            });
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
                __tuple_value.3.clone(),
                __tuple_value.4.clone(),
                __tuple_value.5.clone(),
                __tuple_value.6.clone(),
                __tuple_value.7.clone(),
                __tuple_value.8.clone(),
                __tuple_value.9.clone(),
                __tuple_value.10.clone(),
                __tuple_value.11.clone(),
                __tuple_value.12.clone(),
                __tuple_value.13.clone(),
            ]
        })
        .into_iter()
        .enumerate()
        .map(|(__index, __value)| (__index as i64 + 0i64, __value))
        .collect::<Vec<_>>());
        for (index, key) in __comprehension_source_1228.iter().cloned() {
            {
                let (__key, __value) = (key.clone(), index);
                __comprehension_result_1229.insert(__key, __value);
            }
        }
        __comprehension_result_1229
    };
    let mut improvements: Vec<indexmap::IndexMap<String, rt::Json>> =
        records(root, "terrainImprovements")?;
    let mut improvement_ids: indexmap::IndexMap<String, i64> = identifiers(&improvements, "key")?;
    let (mut irrigation, mut mine, mut road): (
        indexmap::IndexMap<String, rt::Json>,
        indexmap::IndexMap<String, rt::Json>,
        indexmap::IndexMap<String, rt::Json>,
    ) = {
        let __tuple_values = {
            let mut __comprehension_result_1231: Vec<indexmap::IndexMap<String, rt::Json>> =
                Vec::new();
            let __comprehension_source_1230 = ({
                let __tuple_value = &((
                    "irrigation".to_string(),
                    "mine".to_string(),
                    "road".to_string(),
                ));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                ]
            });
            for key in __comprehension_source_1230.iter().cloned() {
                __comprehension_result_1231.push(object_field(
                    {
                        let __source = &improvements;
                        let __key = (improvement_ids)
                            .get(&key)
                            .ok_or("missing dict key")?
                            .clone();
                        &__source[rt::index(__source.len(), __key)?]
                    },
                    "bonusYields",
                )?);
            }
            __comprehension_result_1231
        };
        if __tuple_values.len() != 3 {
            return Err("tuple length mismatch".into());
        }
        (
            rt::at(&__tuple_values, 0i64)?,
            rt::at(&__tuple_values, 1i64)?,
            rt::at(&__tuple_values, 2i64)?,
        )
    };
    let mut railroad: Option<indexmap::IndexMap<String, rt::Json>> = (if {
        let __needle: &str = AsRef::<str>::as_ref("railroad");
        let __container = &improvement_ids;
        __container.contains_key(__needle)
    } {
        Some(object_field(
            {
                let __source = &improvements;
                let __key = (improvement_ids)
                    .get("railroad")
                    .ok_or("missing dict key")?
                    .clone();
                &__source[rt::index(__source.len(), __key)?]
            },
            "bonusYields",
        )?)
    } else {
        None
    });
    let mut extra_improvements: Vec<(i64, indexmap::IndexMap<String, rt::Json>)> = {
        let mut __comprehension_result_1233: Vec<(i64, indexmap::IndexMap<String, rt::Json>)> =
            Vec::new();
        let __comprehension_source_1232 = (({
            static __CONSTANT_py__openciv3__world__OVERLAY_KEYS: std::sync::OnceLock<
                indexmap::IndexMap<String, i64>,
            > = std::sync::OnceLock::new();
            if __CONSTANT_py__openciv3__world__OVERLAY_KEYS.get().is_none() {
                let __constant_value = [
                    ("road".to_string(), 1i64),
                    ("railroad".to_string(), 2i64),
                    ("mine".to_string(), 4i64),
                    ("irrigation".to_string(), 8i64),
                    ("fortress".to_string(), 16i64),
                    ("goodyHut".to_string(), 32i64),
                    ("pollution".to_string(), 64i64),
                    ("barbarianCamp".to_string(), 128i64),
                    ("craters".to_string(), 256i64),
                    ("barricade".to_string(), 268435456i64),
                    ("airfield".to_string(), 536870912i64),
                    ("radarTower".to_string(), 1073741824i64),
                    ("outpost".to_string(), 2147483648i64),
                ]
                .into_iter()
                .collect::<indexmap::IndexMap<_, _>>();
                let _ = __CONSTANT_py__openciv3__world__OVERLAY_KEYS.set(__constant_value);
            }
            __CONSTANT_py__openciv3__world__OVERLAY_KEYS
                .get()
                .ok_or("missing module constant")?
                .clone()
        })
        .iter()
        .map(|(__key, __value)| (__key.clone(), __value.clone()))
        .collect::<Vec<_>>());
        for (name, flag) in __comprehension_source_1232.iter().cloned() {
            if ({
                let __needle = name.clone();
                let __container = &({
                    let __tuple_value = &((
                        "irrigation".to_string(),
                        "mine".to_string(),
                        "road".to_string(),
                        "railroad".to_string(),
                    ));
                    vec![
                        __tuple_value.0.clone(),
                        __tuple_value.1.clone(),
                        __tuple_value.2.clone(),
                        __tuple_value.3.clone(),
                    ]
                });
                !__container.contains(&__needle)
            } && {
                let __needle: &str = AsRef::<str>::as_ref(&name);
                let __container = &improvement_ids;
                __container.contains_key(__needle)
            }) {
                __comprehension_result_1233.push((
                    flag,
                    object_field(
                        {
                            let __source = &improvements;
                            let __key = (improvement_ids)
                                .get(&name)
                                .ok_or("missing dict key")?
                                .clone();
                            &__source[rt::index(__source.len(), __key)?]
                        },
                        "bonusYields",
                    )?,
                ));
            }
        }
        __comprehension_result_1233
    };

    static __table_foliage_actions: std::sync::OnceLock<indexmap::IndexMap<String, i64>> =
        std::sync::OnceLock::new();
    let foliage_actions: &indexmap::IndexMap<String, i64> =
        __table_foliage_actions.get_or_init(|| {
            [
                ("none".to_string(), -1i64),
                ("plantForest".to_string(), 5i64),
                ("clearForest".to_string(), 6i64),
                ("clearWetlands".to_string(), 7i64),
            ]
            .into_iter()
            .collect::<indexmap::IndexMap<_, _>>()
        });
    let mut terrains: Vec<crate::openciv3::rules::Terrain> = vec![];
    for mut for_target_261_4 in ({
        let __tuple_value = &({
            static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS: std::sync::OnceLock<(
                String,
                String,
                String,
                String,
                String,
                String,
                String,
                String,
                String,
                String,
                String,
                String,
                String,
                String,
            )> = std::sync::OnceLock::new();
            if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                .get()
                .is_none()
            {
                let __constant_value = (
                    "desert".to_string(),
                    "plains".to_string(),
                    "grassland".to_string(),
                    "tundra".to_string(),
                    "flood plain".to_string(),
                    "hills".to_string(),
                    "mountains".to_string(),
                    "forest".to_string(),
                    "jungle".to_string(),
                    "marsh".to_string(),
                    "volcano".to_string(),
                    "coast".to_string(),
                    "sea".to_string(),
                    "ocean".to_string(),
                );
                let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS.set(__constant_value);
            }
            __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                .get()
                .ok_or("missing module constant")?
                .clone()
        });
        vec![
            __tuple_value.0.clone(),
            __tuple_value.1.clone(),
            __tuple_value.2.clone(),
            __tuple_value.3.clone(),
            __tuple_value.4.clone(),
            __tuple_value.5.clone(),
            __tuple_value.6.clone(),
            __tuple_value.7.clone(),
            __tuple_value.8.clone(),
            __tuple_value.9.clone(),
            __tuple_value.10.clone(),
            __tuple_value.11.clone(),
            __tuple_value.12.clone(),
            __tuple_value.13.clone(),
        ]
    })
    .into_iter()
    .enumerate()
    .map(|(__index, __value)| (__index as i64 + 0i64, __value))
    .collect::<Vec<_>>()
    {
        let (mut index, mut key): (i64, String) = for_target_261_4;
        let mut row: indexmap::IndexMap<String, rt::Json> = rt::at(
            &rows,
            (indices).get(&key).ok_or("missing dict key")?.clone(),
        )?;
        let mut amount: rt::Json = {
            let __mapping = object_field(&row, "defenseBonus")?;
            let __key = "amount".to_string();
            let __default = serde_json::Value::from(0i64);
            __mapping.get(&__key).cloned().unwrap_or(__default)
        };
        if rt::json_kind(&(amount.clone())) != "number" {
            return Err({
                let __separator = &(String::new());
                (&(vec!["Invalid defense bonus for ".to_string(), (key).to_string()]))
                    .join(__separator)
            }
            .into());
        }
        if !(rt::json_kind(&(amount.clone())) == "number") {
            rt::assertion(false, &("".to_string()))?;
        }
        let mut land: bool = (index
            < rt::index_of(
                &(vec![
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .0
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .1
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .2
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .3
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .4
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .5
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .6
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .7
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .8
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .9
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .10
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .11
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .12
                    .clone(),
                    ({
                        static __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS:
                            std::sync::OnceLock<(
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                                String,
                            )> = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .is_none()
                        {
                            let __constant_value = (
                                "desert".to_string(),
                                "plains".to_string(),
                                "grassland".to_string(),
                                "tundra".to_string(),
                                "flood plain".to_string(),
                                "hills".to_string(),
                                "mountains".to_string(),
                                "forest".to_string(),
                                "jungle".to_string(),
                                "marsh".to_string(),
                                "volcano".to_string(),
                                "coast".to_string(),
                                "sea".to_string(),
                                "ocean".to_string(),
                            );
                            let _ = __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                                .set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__json_rules__TERRAIN_KEYS
                            .get()
                            .ok_or("missing module constant")?
                            .clone()
                    })
                    .13
                    .clone(),
                ]),
                &("coast".to_string()),
            )?);
        let mut bonuses: crate::openciv3::rules::ImprovementYields =
            crate::openciv3::rules::ImprovementYields {
                irrigation: decode_terrains__bonus_for(&irrigation, &key)?,
                mine: decode_terrains__bonus_for(&mine, &key)?,
                road: decode_terrains__bonus_for(&road, &key)?,
                railroad: decode_terrains__bonus_for(
                    &(if (railroad).is_some() {
                        (*(railroad.clone()).as_ref().ok_or("expected a value")?).clone()
                    } else {
                        road.clone()
                    }),
                    &key,
                )?,
            };
        let mut restrictions: indexmap::IndexMap<String, rt::Json> =
            object_field(&row, "impassableTo")?;
        let mut impassable_to: Vec<(i64, i64)> = vec![];
        for mut key_flag in (restrictions).keys() {
            let mut ability: Option<i64> = ({
                static __CONSTANT_py__openciv3__json_rules__UNIT_ABILITIES: std::sync::OnceLock<
                    indexmap::IndexMap<String, i64>,
                > = std::sync::OnceLock::new();
                if __CONSTANT_py__openciv3__json_rules__UNIT_ABILITIES
                    .get()
                    .is_none()
                {
                    let __constant_value = [
                        ("wheeled".to_string(), 1i64),
                        ("radar".to_string(), 32i64),
                        ("allTerrainAsRoads".to_string(), 16i64),
                        ("sinkInSea".to_string(), 2048i64),
                        ("sinkInOcean".to_string(), 4096i64),
                        ("footSoldier".to_string(), 2i64),
                        ("tacticalMissile".to_string(), 8388608i64),
                        ("canCarryFootUnitsOnly".to_string(), 16384i64),
                        ("canCarryAircraft".to_string(), 256i64),
                        ("canCarryTacticalMissiles".to_string(), 16777216i64),
                        ("rotateBeforeAttack".to_string(), 67108864i64),
                        ("lethalSeaBombardment".to_string(), 268435456i64),
                        ("lethalLandBombardment".to_string(), 134217728i64),
                    ]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>();
                    let _ =
                        __CONSTANT_py__openciv3__json_rules__UNIT_ABILITIES.set(__constant_value);
                }
                __CONSTANT_py__openciv3__json_rules__UNIT_ABILITIES
                    .get()
                    .ok_or("missing module constant")?
                    .clone()
            })
            .get(&(key_flag.to_owned()))
            .cloned();
            if (ability).is_none() {
                return Err({
                    let __separator = &(String::new());
                    (&(vec![
                        "Unknown impassable terrain unit flag: ".to_string(),
                        (key_flag.to_owned()).to_string(),
                    ]))
                        .join(__separator)
                }
                .into());
            }
            let mut allowed: i64 = 0i64;
            for mut improvement in strings(&restrictions, key_flag)? {
                if {
                    let __needle: &str = AsRef::<str>::as_ref(&improvement);
                    let __container = {
                        static __CONSTANT_py__openciv3__world__OVERLAY_KEYS: std::sync::OnceLock<
                            indexmap::IndexMap<String, i64>,
                        > = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__world__OVERLAY_KEYS.get().is_none() {
                            let __constant_value = [
                                ("road".to_string(), 1i64),
                                ("railroad".to_string(), 2i64),
                                ("mine".to_string(), 4i64),
                                ("irrigation".to_string(), 8i64),
                                ("fortress".to_string(), 16i64),
                                ("goodyHut".to_string(), 32i64),
                                ("pollution".to_string(), 64i64),
                                ("barbarianCamp".to_string(), 128i64),
                                ("craters".to_string(), 256i64),
                                ("barricade".to_string(), 268435456i64),
                                ("airfield".to_string(), 536870912i64),
                                ("radarTower".to_string(), 1073741824i64),
                                ("outpost".to_string(), 2147483648i64),
                            ]
                            .into_iter()
                            .collect::<indexmap::IndexMap<_, _>>();
                            let _ =
                                __CONSTANT_py__openciv3__world__OVERLAY_KEYS.set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__world__OVERLAY_KEYS
                            .get()
                            .ok_or("missing module constant")?
                    };
                    !__container.contains_key(__needle)
                } {
                    return Err({
                        let __separator = &(String::new());
                        (&(vec![
                            "Unknown terrain passage improvement: ".to_string(),
                            (improvement).to_string(),
                        ]))
                            .join(__separator)
                    }
                    .into());
                }
                allowed = (allowed
                    | ({
                        static __CONSTANT_py__openciv3__world__OVERLAY_KEYS: std::sync::OnceLock<
                            indexmap::IndexMap<String, i64>,
                        > = std::sync::OnceLock::new();
                        if __CONSTANT_py__openciv3__world__OVERLAY_KEYS.get().is_none() {
                            let __constant_value = [
                                ("road".to_string(), 1i64),
                                ("railroad".to_string(), 2i64),
                                ("mine".to_string(), 4i64),
                                ("irrigation".to_string(), 8i64),
                                ("fortress".to_string(), 16i64),
                                ("goodyHut".to_string(), 32i64),
                                ("pollution".to_string(), 64i64),
                                ("barbarianCamp".to_string(), 128i64),
                                ("craters".to_string(), 256i64),
                                ("barricade".to_string(), 268435456i64),
                                ("airfield".to_string(), 536870912i64),
                                ("radarTower".to_string(), 1073741824i64),
                                ("outpost".to_string(), 2147483648i64),
                            ]
                            .into_iter()
                            .collect::<indexmap::IndexMap<_, _>>();
                            let _ =
                                __CONSTANT_py__openciv3__world__OVERLAY_KEYS.set(__constant_value);
                        }
                        __CONSTANT_py__openciv3__world__OVERLAY_KEYS
                            .get()
                            .ok_or("missing module constant")?
                    })
                    .get(&improvement)
                    .ok_or("missing dict key")?
                    .clone());
            }
            {
                impassable_to.push((
                    (*(ability).as_ref().ok_or("expected a value")?).clone(),
                    allowed,
                ));
            };
        }
        {
            terrains.push(crate::openciv3::rules::Terrain {
                name: text(&row, "displayName", "")?,
                civilopedia_entry: String::new(),
                possible_resources: ({
                    let mut __comprehension_result_1235: Vec<i64> = Vec::new();
                    let __comprehension_source_1234 = (strings(&row, "allowedResources")?);
                    for name in __comprehension_source_1234.iter().cloned() {
                        __comprehension_result_1235.push(reference(
                            &([(
                                "resource".to_string(),
                                serde_json::Value::from(name.clone()),
                            )]
                            .into_iter()
                            .collect::<indexmap::IndexMap<_, _>>()),
                            "resource",
                            resources,
                        )?);
                    }
                    __comprehension_result_1235
                })
                .iter()
                .cloned()
                .collect::<Vec<_>>(),
                irrigation_bonus: (&(bonuses).irrigation).food,
                mining_bonus: (&(bonuses).mine).shields,
                road_bonus: (&(bonuses).road).commerce,
                improvement_yields: Some(bonuses.clone()),
                extra_improvement_yields: ({
                    let mut __comprehension_result_1237: Vec<(i64, crate::civ::economy::Yield)> =
                        Vec::new();
                    let __comprehension_source_1236 = (extra_improvements.clone());
                    for (flag, values) in __comprehension_source_1236.iter().cloned() {
                        if {
                            let __needle: &str = AsRef::<str>::as_ref(&key);
                            let __container = &values;
                            __container.contains_key(__needle)
                        } {
                            __comprehension_result_1237
                                .push((flag, decode_terrains__bonus_for(&values, &key)?));
                        }
                    }
                    __comprehension_result_1237
                })
                .iter()
                .cloned()
                .collect::<Vec<_>>(),
                defense_bonus: rt::round_float(rt::finite(
                    rt::json_float(&(amount))? * ((100i64) as f64),
                )?)?,
                movement_cost: integer(&row, "movementCost", 0i64)?,
                yields: crate::civ::economy::Yield {
                    food: integer(&row, "baseFoodProduction", 0i64)?,
                    shields: integer(&row, "baseShieldProduction", 0i64)?,
                    commerce: integer(&row, "baseCommerceProduction", 0i64)?,
                },
                worker_job: {
                    let __key = text(&row, "allowedFoliageAction", "")?;
                    let __default = -1i64;
                    foliage_actions.get(&__key).cloned().unwrap_or(__default)
                },
                pollution_effect: 0i64,
                allow_cities: boolean(&row, "allowCities", false)?,
                allow_colonies: land,
                impassable: boolean(&row, "impassable", false)?,
                impassable_by_wheeled: {
                    let __needle: &str = AsRef::<str>::as_ref("wheeled");
                    let __container = &restrictions;
                    __container.contains_key(__needle)
                },
                impassable_to: Some((impassable_to).iter().cloned().collect::<Vec<_>>()),
                allowed_base_terrains: (if {
                    let __needle: &str = AsRef::<str>::as_ref("allowedInTerrain");
                    let __container = &row;
                    __container.contains_key(__needle)
                } {
                    Some({
                        let mut __result: std::collections::BTreeSet<i64> =
                            std::collections::BTreeSet::new();
                        for __item in ({
                            let mut __comprehension_result_1239: Vec<i64> = Vec::new();
                            let __comprehension_source_1238 = (strings(&row, "allowedInTerrain")?);
                            for name in __comprehension_source_1238.iter().cloned() {
                                __comprehension_result_1239.push(reference(
                                    &([(
                                        "terrain".to_string(),
                                        serde_json::Value::from(name.clone()),
                                    )]
                                    .into_iter()
                                    .collect::<indexmap::IndexMap<_, _>>()),
                                    "terrain",
                                    &terrain_ids,
                                )?);
                            }
                            __comprehension_result_1239
                        })
                        .into_iter()
                        {
                            __result.insert(__item);
                        }
                        __result
                    })
                } else {
                    None
                }),
                allow_airfields: land,
                allow_forts: land,
                allow_outposts: land,
                allow_radar_towers: land,
                sight_height: (if {
                    let __needle: &str = AsRef::<str>::as_ref("height");
                    let __container = &row;
                    __container.contains_key(__needle)
                } {
                    Some(integer(&row, "height", 0i64)?)
                } else {
                    None
                }),
                landmark_enabled: false,
                landmark_yields: crate::civ::economy::Yield {
                    food: 0i64,
                    shields: 0i64,
                    commerce: 0i64,
                },
                landmark_irrigation_bonus: 0i64,
                landmark_mining_bonus: 0i64,
                landmark_road_bonus: 0i64,
                landmark_movement_cost: 0i64,
                landmark_defense_bonus: 0i64,
                landmark_name: String::new(),
                landmark_civilopedia_entry: String::new(),
                flags: 0i64,
                disease_strength: 0i64,
            });
        };
    }
    Ok((terrains).iter().cloned().collect::<Vec<_>>())
}

// Python: openciv3/json_rules.py:336
pub(crate) fn decode_units(
    root: &indexmap::IndexMap<String, rt::Json>,
    technologies: &indexmap::IndexMap<String, i64>,
    resources: &indexmap::IndexMap<String, i64>,
    workers: &[crate::openciv3::rules::WorkerJob],
) -> rt::Result<Vec<crate::openciv3::unit_rules::UnitPrototype>> {
    let mut rows: Vec<indexmap::IndexMap<String, rt::Json>> = records(root, "unitPrototypes")?;
    let mut unit_ids: indexmap::IndexMap<String, i64> = identifiers(&rows, "name")?;
    let mut civ_ids: indexmap::IndexMap<String, i64> =
        identifiers(&(records(root, "civilizations")?), "name")?;
    let mut worker_ids: indexmap::IndexMap<String, i64> =
        identifiers(&(records(root, "terraForms")?), "id")?;
    let mut result: Vec<crate::openciv3::unit_rules::UnitPrototype> = vec![];
    for mut row in (rows).iter() {
        let mut orders: i64 = 0i64;
        for mut action in strings(row, "actions")? {
            orders = (orders
                | ({
                    static __CONSTANT_py__openciv3__json_rules__UNIT_ORDERS: std::sync::OnceLock<
                        indexmap::IndexMap<String, i64>,
                    > = std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__json_rules__UNIT_ORDERS
                        .get()
                        .is_none()
                    {
                        let __constant_value = [
                            ("hold".to_string(), 1i64),
                            ("wait".to_string(), 2i64),
                            ("fortify".to_string(), 4i64),
                            ("disband".to_string(), 8i64),
                            ("goto".to_string(), 16i64),
                            ("explore".to_string(), 32i64),
                            ("load".to_string(), 128i64),
                            ("unload".to_string(), 256i64),
                            ("buildCity".to_string(), 4194304i64),
                            ("automate".to_string(), 4294967296i64),
                            ("bombard".to_string(), 2048i64),
                            ("pillage".to_string(), 1024i64),
                            ("upgradeUnit".to_string(), 32768i64),
                            ("joinCity".to_string(), 8589934592i64),
                            ("bombing".to_string(), 274877906944i64),
                            ("rebase".to_string(), 2199023255552i64),
                        ]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>();
                        let _ =
                            __CONSTANT_py__openciv3__json_rules__UNIT_ORDERS.set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__json_rules__UNIT_ORDERS
                        .get()
                        .ok_or("missing module constant")?
                })
                .get(&action)
                .ok_or("missing dict key")?
                .clone());
        }
        let mut jobs: std::collections::BTreeSet<i64> = {
            let mut __result: std::collections::BTreeSet<i64> = std::collections::BTreeSet::new();
            for __item in ({
                let mut __comprehension_result_1241: std::collections::BTreeSet<i64> =
                    std::collections::BTreeSet::new();
                let __comprehension_source_1240 = (strings(row, "terraformActions")?);
                for job in __comprehension_source_1240.iter().cloned() {
                    __comprehension_result_1241.insert(reference(
                        &([("job".to_string(), serde_json::Value::from(job.clone()))]
                            .into_iter()
                            .collect::<indexmap::IndexMap<_, _>>()),
                        "job",
                        &worker_ids,
                    )?);
                }
                __comprehension_result_1241
            })
            .into_iter()
            {
                __result.insert(__item);
            }
            __result
        };
        if {
            let __needle = (1i64).checked_neg().ok_or("integer overflow")?;
            let __container = &jobs;
            __container.contains(&__needle)
        } {
            return Err("Unit terraform action must name a worker job"
                .to_string()
                .into());
        }
        for mut job in (jobs).iter().copied() {
            orders = (orders | {
                let __mapping = {
                    static __CONSTANT_py__openciv3__worker_rules__ORDERS: std::sync::OnceLock<
                        indexmap::IndexMap<String, i64>,
                    > = std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__worker_rules__ORDERS
                        .get()
                        .is_none()
                    {
                        let __constant_value = [
                            ("BuildRoad".to_string(), 8388608i64),
                            ("BuildRailroad".to_string(), 16777216i64),
                            ("BuildMine".to_string(), 67108864i64),
                            ("Irrigate".to_string(), 134217728i64),
                            ("BuildFortress".to_string(), 33554432i64),
                            ("BuildBarricade".to_string(), 137438953472i64),
                            ("ClearForest".to_string(), 268435456i64),
                            ("ClearWetlands".to_string(), 536870912i64),
                            ("PlantForest".to_string(), 1073741824i64),
                            ("ClearDamage".to_string(), 2147483648i64),
                            ("BuildAirfield".to_string(), 17179869184i64),
                            ("BuildRadarTower".to_string(), 34359738368i64),
                            ("BuildOutpost".to_string(), 68719476736i64),
                        ]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>();
                        let _ = __CONSTANT_py__openciv3__worker_rules__ORDERS.set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__worker_rules__ORDERS
                        .get()
                        .ok_or("missing module constant")?
                        .clone()
                };
                let __key = crate::openciv3::worker_rules::order_key({
                    let __source = workers;
                    let __key = job;
                    &__source[rt::index(__source.len(), __key)?]
                })?;
                let __default = 0i64;
                __mapping.get(&__key).cloned().unwrap_or(__default)
            });
        }
        let mut abilities: i64 = 0i64;
        for mut flag in strings(row, "flags")? {
            abilities = (abilities
                | ({
                    static __CONSTANT_py__openciv3__json_rules__UNIT_ABILITIES:
                        std::sync::OnceLock<indexmap::IndexMap<String, i64>> =
                        std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__json_rules__UNIT_ABILITIES
                        .get()
                        .is_none()
                    {
                        let __constant_value = [
                            ("wheeled".to_string(), 1i64),
                            ("radar".to_string(), 32i64),
                            ("allTerrainAsRoads".to_string(), 16i64),
                            ("sinkInSea".to_string(), 2048i64),
                            ("sinkInOcean".to_string(), 4096i64),
                            ("footSoldier".to_string(), 2i64),
                            ("tacticalMissile".to_string(), 8388608i64),
                            ("canCarryFootUnitsOnly".to_string(), 16384i64),
                            ("canCarryAircraft".to_string(), 256i64),
                            ("canCarryTacticalMissiles".to_string(), 16777216i64),
                            ("rotateBeforeAttack".to_string(), 67108864i64),
                            ("lethalSeaBombardment".to_string(), 268435456i64),
                            ("lethalLandBombardment".to_string(), 134217728i64),
                        ]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>();
                        let _ = __CONSTANT_py__openciv3__json_rules__UNIT_ABILITIES
                            .set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__json_rules__UNIT_ABILITIES
                        .get()
                        .ok_or("missing module constant")?
                })
                .get(&flag)
                .ok_or("missing dict key")?
                .clone());
        }
        let mut domains: Vec<i64> = ({
            let mut __comprehension_result_1243: Vec<i64> = Vec::new();
            let __comprehension_source_1242 = (strings(row, "categories")?);
            for category in __comprehension_source_1242.iter().cloned() {
                __comprehension_result_1243.push(match ((&category).to_uppercase()).as_str() {
                    "LAND" => 0i64,
                    "SEA" => 1i64,
                    "AIR" => 2i64,
                    _ => return Err("unknown enum name".into()),
                });
            }
            __comprehension_result_1243
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        if (((domains).len() as i64) != 1i64) {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Expected one domain for ".to_string(),
                    (text(row, "name", "")?).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        let mut domain: i64 = rt::at(&domains, 0i64)?;
        let (mut attack, mut defense): (i64, i64) = (
            integer(row, "attack", 0i64)?,
            integer(row, "defense", 0i64)?,
        );
        let mut strategies: i64 = 0i64;
        if ((orders & 4194304i64) != 0i64) {
            strategies = (strategies | 8192i64);
        }
        if (((jobs).len() as i64) != 0i64) {
            strategies = (strategies | 4096i64);
        }
        if ((attack) != 0 && (domain == 0i64)) {
            strategies = (strategies | 1i64);
        }
        if ((defense) != 0 && (domain == 0i64)) {
            strategies = (strategies | 2i64);
        }
        if (domain == 1i64) {
            if (attack != 0i64) {
                strategies = (strategies | 256i64);
            }
            if (integer(row, "capacity", 0i64)? != 0i64) {
                strategies = (strategies | 1024i64);
            }
        }
        if ((orders & 2048i64) != 0 && (domain == 0i64)) {
            strategies = (strategies | 4i64);
        }
        let mut upgrades: Vec<i64> = ({
            let mut __comprehension_result_1245: Vec<i64> = Vec::new();
            let __comprehension_source_1244 = (strings(row, "upgradesTo")?);
            for name in __comprehension_source_1244.iter().cloned() {
                __comprehension_result_1245.push(reference(
                    &([("unit".to_string(), serde_json::Value::from(name.clone()))]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>()),
                    "unit",
                    &unit_ids,
                )?);
            }
            __comprehension_result_1245
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        if (((upgrades).len() as i64) != 0i64) {
            orders = (orders | 32768i64);
        }
        let mut successor: i64 = '__extreme: {
            let __values = &upgrades;
            let mut __items = __values.iter();
            let Some(mut __best) = __items.next() else {
                break '__extreme (1i64).checked_neg().ok_or("integer overflow")?;
            };
            let mut __best_key = {
                let i = (*__best).clone();
                ((strings(
                    {
                        let __source = &rows;
                        let __key = i;
                        &__source[rt::index(__source.len(), __key)?]
                    },
                    "producibleBy",
                )?)
                .len() as i64)
            };
            for __candidate in __items {
                let __key = {
                    let i = (*__candidate).clone();
                    ((strings(
                        {
                            let __source = &rows;
                            let __key = i;
                            &__source[rt::index(__source.len(), __key)?]
                        },
                        "producibleBy",
                    )?)
                    .len() as i64)
                };
                if __key > __best_key {
                    __best = __candidate;
                    __best_key = __key;
                }
            }
            (*__best).clone()
        };
        let mut unit_art: indexmap::IndexMap<String, rt::Json> = object_field(row, "art")?;
        let mut art: indexmap::IndexMap<String, rt::Json> =
            object_field(&unit_art, "thumbnailArt")?;
        let mut animation: indexmap::IndexMap<String, rt::Json> =
            object_field(&unit_art, "mainArt")?;
        let mut variants: indexmap::IndexMap<String, rt::Json> =
            object_field(&animation, "variations")?;
        let mut icons: indexmap::IndexMap<String, rt::Json> = object_field(&art, "variations")?;
        let mut availability: Vec<i64> = ({
            let mut __comprehension_result_1247: Vec<i64> = Vec::new();
            let __comprehension_source_1246 = (strings(row, "producibleBy")?);
            for name in __comprehension_source_1246.iter().cloned() {
                __comprehension_result_1247.push(reference(
                    &([("civ".to_string(), serde_json::Value::from(name.clone()))]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>()),
                    "civ",
                    &civ_ids,
                )?);
            }
            __comprehension_result_1247
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        {
            result.push(crate::openciv3::unit_rules::UnitPrototype {
                name: text(row, "name", "")?,
                civilopedia_entry: text(row, "civilopediaEntry", "")?,
                zone_of_control: false,
                bombard_strength: integer(row, "bombard", 0i64)?,
                bombard_range: integer(row, "bombardRange", 0i64)?,
                capacity: integer(row, "capacity", 0i64)?,
                shield_cost: integer(row, "shieldCost", 0i64)?,
                defense: defense,
                icon: integer(&art, "defaultIndex", 0i64)?,
                attack: attack,
                operational_range: integer(row, "operationalRange", 0i64)?,
                population_cost: integer(row, "populationCost", 0i64)?,
                rate_of_fire: integer(row, "rateOfFire", 0i64)?,
                movement: integer(row, "movement", 0i64)?,
                prerequisite: reference(row, "requiredTech", technologies)?,
                upgrade_to: successor,
                required_resources: ({
                    let mut __comprehension_result_1249: Vec<i64> = Vec::new();
                    let __comprehension_source_1248 = (strings(row, "requiredResources")?);
                    for name in __comprehension_source_1248.iter().cloned() {
                        __comprehension_result_1249.push(reference(
                            &([(
                                "resource".to_string(),
                                serde_json::Value::from(name.clone()),
                            )]
                            .into_iter()
                            .collect::<indexmap::IndexMap<_, _>>()),
                            "resource",
                            resources,
                        )?);
                    }
                    __comprehension_result_1249
                })
                .iter()
                .cloned()
                .collect::<Vec<_>>(),
                abilities: abilities,
                strategies: strategies,
                available_to: availability,
                domain: domain,
                unproducible: boolean(row, "unproducible", false)?,
                other_strategy: 0i64,
                hp_bonus: integer(row, "hpBonus", 0i64)?,
                orders: orders,
                bombard_effects: 0i64,
                ignore_movement_cost: vec![],
                require_support: boolean(row, "requireSupport", true)?,
                enslave_result: (1i64).checked_neg().ok_or("integer overflow")?,
                stealth_targets: vec![],
                create_craters: false,
                worker_strength: (if (((jobs).len() as i64) != 0i64) {
                    1.0f64
                } else {
                    0.0f64
                }),
                air_defense: 0i64,
                animation_name: text(&animation, "defaultName", "")?,
                animation_variants: ({
                    let mut __comprehension_result_1251: Vec<(String, String)> = Vec::new();
                    let __comprehension_source_1250 = (variants.clone());
                    for key in __comprehension_source_1250.keys().cloned() {
                        __comprehension_result_1251.push((key.clone(), text(&variants, &key, "")?));
                    }
                    __comprehension_result_1251
                })
                .iter()
                .cloned()
                .collect::<Vec<_>>(),
                icon_variants: ({
                    let mut __comprehension_result_1253: Vec<(String, i64)> = Vec::new();
                    let __comprehension_source_1252 = (icons.clone());
                    for key in __comprehension_source_1252.keys().cloned() {
                        __comprehension_result_1253
                            .push((key.clone(), integer(&icons, &key, 0i64)?));
                    }
                    __comprehension_result_1253
                })
                .iter()
                .cloned()
                .collect::<Vec<_>>(),
                upgrade_branches: Some(upgrades),
                worker_jobs: Some(jobs.clone()),
            });
        };
    }
    Ok((result).iter().cloned().collect::<Vec<_>>())
}

// Python: openciv3/json_rules.py:417
pub(crate) fn percentage(row: &indexmap::IndexMap<String, rt::Json>, key: &str) -> rt::Result<i64> {
    let mut value: rt::Json = {
        let __key = key.to_owned();
        let __default = serde_json::Value::from(0i64);
        row.get(&__key).cloned().unwrap_or(__default)
    };
    if (!(rt::json_kind(&(value.clone())) == "number") || rt::json_kind(&(value.clone())) == "bool")
    {
        return Err({
            let __separator = &(String::new());
            (&(vec![(key.to_owned()).to_string(), " must be numeric".to_string()]))
                .join(__separator)
        }
        .into());
    }
    rt::round_float(rt::finite(rt::json_float(&(value))? * ((100i64) as f64))?)
}

// Python: openciv3/json_rules.py:424
pub(crate) fn building_commerce_bonus(
    row: &indexmap::IndexMap<String, rt::Json>,
    key: &str,
) -> rt::Result<Option<f64>> {
    if {
        let __needle: &str = AsRef::<str>::as_ref(key);
        let __container = row;
        !__container.contains_key(__needle)
    } {
        return Ok(None);
    }
    let value: &rt::Json = (row).get(key).ok_or("missing dict key")?;
    if (rt::json_kind(&((*value).clone())) == "bool"
        || (!(rt::json_kind(&((*value).clone())) == "number")
            || !(rt::math_isfinite(rt::json_float(&((*value).clone()))?))))
    {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                (key.to_owned()).to_string(),
                " must be finite and numeric".to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok(Some(rt::json_float(&((*value).clone()))?))
}

// Python: openciv3/json_rules.py:433
pub(crate) fn decode_buildings(
    root: &indexmap::IndexMap<String, rt::Json>,
    technologies: &indexmap::IndexMap<String, i64>,
    resources: &indexmap::IndexMap<String, i64>,
) -> rt::Result<Vec<crate::openciv3::building_rules::Building>> {
    let mut rows: Vec<indexmap::IndexMap<String, rt::Json>> = records(root, "buildings")?;
    let mut building_ids: indexmap::IndexMap<String, i64> = identifiers(&rows, "name")?;
    let mut units: indexmap::IndexMap<String, i64> =
        identifiers(&(records(root, "unitPrototypes")?), "name")?;
    let mut governments: indexmap::IndexMap<String, i64> =
        identifiers(&(records(root, "governments")?), "id")?;
    static __table_aliases: std::sync::OnceLock<indexmap::IndexMap<String, i64>> =
        std::sync::OnceLock::new();
    let aliases: &indexmap::IndexMap<String, i64> = __table_aliases.get_or_init(|| {
        [
            ("isCenterOfEmpire".to_string(), 1i64),
            ("mustBeCoastal".to_string(), 67108864i64),
            ("resistantToPropaganda".to_string(), 128i64),
            ("allowsCitySize2".to_string(), 2048i64),
            ("allowsCitySize3".to_string(), 4096i64),
            (
                "cityGrowthPlusTwoCitizens".to_string(),
                288230376151711744i64,
            ),
            (
                "increasedTradeInTilesProducingCommerce".to_string(),
                18014398509481984i64,
            ),
            (
                "reducesWarWearinessAllCities".to_string(),
                1152921504606846976i64,
            ),
        ]
        .into_iter()
        .collect::<indexmap::IndexMap<_, _>>()
    });
    static __table_production_rules: std::sync::OnceLock<indexmap::IndexMap<String, i64>> =
        std::sync::OnceLock::new();
    let production_rules: &indexmap::IndexMap<String, i64> =
        __table_production_rules.get_or_init(|| {
            [
                ("must_be_coastal".to_string(), 67108864i64),
                ("must_be_near_river".to_string(), 32768i64),
                ("must_be_near_water".to_string(), 16384i64),
                (
                    "can_only_be_built_in_towns".to_string(),
                    4611686018427387904i64,
                ),
                ("allows_city_size_2".to_string(), 2048i64),
                ("allows_city_size_3".to_string(), 4096i64),
                ("forbidden_palace".to_string(), 8796093022208i64),
                ("secret_police_hq".to_string(), 8796093022208i64),
            ]
            .into_iter()
            .collect::<indexmap::IndexMap<_, _>>()
        });
    let mut unit_effects: indexmap::IndexMap<String, i64> = [
        ("veteran_ground_units".to_string(), 2i64),
        ("veteran_sea_units".to_string(), 131072i64),
        ("veteran_air_units".to_string(), 262144i64),
    ]
    .into_iter()
    .collect::<indexmap::IndexMap<_, _>>();
    let mut tile_effects: indexmap::IndexMap<String, i64> = [
        ("increases_food_in_water".to_string(), 8388608i64),
        ("increases_shields_in_water".to_string(), 4194304i64),
        ("increases_trade_in_water".to_string(), 16777216i64),
    ]
    .into_iter()
    .collect::<indexmap::IndexMap<_, _>>();

    let mut result: Vec<crate::openciv3::building_rules::Building> = vec![];
    for mut row in rows {
        let mut effects: i64 = 0i64;
        for mut group in {
            let __tuple_items = (
                "flags".to_string(),
                "traits".to_string(),
                "wonderFlags".to_string(),
            );
            [__tuple_items.0, __tuple_items.1, __tuple_items.2]
        } {
            for mut flag in strings(&row, &group)? {
                if {
                    let __needle: &str = AsRef::<str>::as_ref(&flag);
                    let __container = &({
                        let mut __result = std::collections::BTreeSet::new();
                        for __item in vec![
                            "providesWalls".to_string(),
                            "increasedArmyValue".to_string(),
                        ]
                        .into_iter()
                        {
                            __result.insert(__item);
                        }
                        __result
                    });
                    __container.contains(__needle)
                } {
                    continue;
                }
                if (flag.as_str() == "canOnlyBeBuiltInTowns") {
                    effects = (effects | 4611686018427387904i64);
                    continue;
                }
                let mut key: String = (&({
                    let __separator = &(String::new());
                    (&({
                        let mut __comprehension_result_1255: Vec<String> = Vec::new();
                        let __comprehension_source_1254 = ((flag.clone())
                            .chars()
                            .enumerate()
                            .map(|(__index, __value)| (__index as i64 + 0i64, __value.to_string()))
                            .collect::<Vec<_>>());
                        for (index, char) in __comprehension_source_1254.iter().cloned() {
                            __comprehension_result_1255.push(
                                (if ((index > 0i64) && {
                                    let __compare_0 = "A".to_string();
                                    let __compare_1 = char.clone();
                                    if (__compare_0 <= __compare_1) {
                                        let __compare_2 = "Z".to_string();
                                        (__compare_1 <= __compare_2)
                                    } else {
                                        false
                                    }
                                }) {
                                    format!("{}{}", "_", &char)
                                } else {
                                    char.clone()
                                }),
                            );
                        }
                        __comprehension_result_1255
                    }))
                        .join(__separator)
                }))
                    .to_uppercase();
                let mut effect: Option<i64> = ((*aliases).clone()).get(&(flag.clone())).cloned();
                if ((effect).is_none()
                    && !((key.clone()) == "SCIENTIFIC"
                        || (key.clone()) == "SMALL_WONDER"
                        || (key.clone()) == "INCREASES_FOOD_IN_WATER"
                        || (key.clone()) == "BUILD_SPACESHIP_PARTS"
                        || (key.clone()) == "PLUS50_PERCENT_RESEARCH"
                        || (key.clone()) == "REDUCED_WAR_WEARINESS"
                        || (key.clone()) == "ALLOWS_LARGER_ARMIES"
                        || (key.clone()) == "ALLOWS_CITY_SIZE2"
                        || (key.clone()) == "COASTAL_INSTALLATION"
                        || (key.clone()) == "COMMERCIAL"
                        || (key.clone()) == "FORBIDDEN_PALACE"
                        || (key.clone()) == "REDUCES_CORRUPTION"
                        || (key.clone()) == "DOUBLES_CITY_GROWTH_RATE"
                        || (key.clone()) == "INDUSTRIOUS"
                        || (key.clone()) == "AGRICULTURAL"
                        || (key.clone()) == "ALLOWS_BUILD_ARMY"
                        || (key.clone()) == "TREASURY_EARNS_INTEREST"
                        || (key.clone()) == "REQUIRES_ELITE_SHIP"
                        || (key.clone()) == "INCREASES_LEADER_CHANCE"
                        || (key.clone()) == "ALLOWS_WATER_TRADE"
                        || (key.clone()) == "ALLOW_DIPLOMATIC_VICTORY"
                        || (key.clone()) == "CONTINENTAL_MOOD_EFFECTS"
                        || (key.clone()) == "ALLOWS_ENEMY_TERRITORY_HEALING"
                        || (key.clone()) == "CENTER_OF_EMPIRE"
                        || (key.clone()) == "VETERAN_SEA_UNITS"
                        || (key.clone()) == "VETERAN_GROUND_UNITS"
                        || (key.clone()) == "DOUBLE_CITY_GROWTH"
                        || (key.clone()) == "MUST_BE_NEAR_WATER"
                        || (key.clone()) == "ALLOWS_NUCLEAR_WEAPONS"
                        || (key.clone()) == "INCREASES_LUXURY_TRADE"
                        || (key.clone()) == "RESISTANT_TO_BRIBERY"
                        || (key.clone()) == "REPLACES_OTHER_BUILDINGS"
                        || (key.clone()) == "ALLOWS_AIR_TRADE"
                        || (key.clone()) == "GOODS_MUST_BE_IN_CITY_RADIUS"
                        || (key.clone()) == "SAFE_SEA_TRAVEL"
                        || (key.clone()) == "MILITARISTIC"
                        || (key.clone()) == "EXPANSIONIST"
                        || (key.clone()) == "GAIN_ANY_TECH_KNOWN_BY_TWO_CIVS"
                        || (key.clone()) == "DOUBLE_COMBAT_VS_BARBARIANS"
                        || (key.clone()) == "REQUIRES_VICTORIOUS_ARMY"
                        || (key.clone()) == "DOUBLES_RESEARCH_OUTPUT"
                        || (key.clone()) == "REDUCES_BUILDING_POLLUTION"
                        || (key.clone()) == "INCREASES_TRADE_IN_WATER"
                        || (key.clone()) == "REMOVES_POPULATION_POLLUTION"
                        || (key.clone()) == "REDUCES_WAR_WEARINESS"
                        || (key.clone()) == "INCREASED_SHIP_MOVEMENT"
                        || (key.clone()) == "DECREASES_MISSILE_SUCCESS"
                        || (key.clone()) == "WONDER"
                        || (key.clone()) == "PAYS_TRADE_MAINTENANCE"
                        || (key.clone()) == "TOURIST_ATTRACTION"
                        || (key.clone()) == "INCREASES_SHIELDS_IN_WATER"
                        || (key.clone()) == "ALLOWS_CITY_SIZE3"
                        || (key.clone()) == "RELIGIOUS"
                        || (key.clone()) == "INCREASED_TRADE"
                        || (key.clone()) == "ALLOWS_SPY_MISSIONS"
                        || (key.clone()) == "TWO_FREE_ADVANCES"
                        || (key.clone()) == "PLUS50_PERCENT_LUXURY"
                        || (key.clone()) == "CHEAPER_UPGRADES"
                        || (key.clone()) == "VETERAN_AIR_UNITS"
                        || (key.clone()) == "TOWNS_ONLY"
                        || (key.clone()) == "SEAFARING"
                        || (key.clone()) == "CAN_MELTDOWN"
                        || (key.clone()) == "PLUS50_PERCENT_COMMERCE"
                        || (key.clone()) == "MUST_BE_NEAR_RIVER"))
                {
                    return Err({
                        let __separator = &(String::new());
                        (&(vec![
                            "Unsupported building flag: ".to_string(),
                            (flag).to_string(),
                        ]))
                            .join(__separator)
                    }
                    .into());
                }
                effect = Some(match (effect) {
                    Some(__value) => __value,
                    None => match (key).as_str() {
                        "CENTER_OF_EMPIRE" => 1i64,
                        "VETERAN_GROUND_UNITS" => 2i64,
                        "PLUS50_PERCENT_RESEARCH" => 4i64,
                        "PLUS50_PERCENT_LUXURY" => 8i64,
                        "PLUS50_PERCENT_COMMERCE" => 16i64,
                        "REMOVES_POPULATION_POLLUTION" => 32i64,
                        "REDUCES_BUILDING_POLLUTION" => 64i64,
                        "RESISTANT_TO_BRIBERY" => 128i64,
                        "REDUCES_CORRUPTION" => 256i64,
                        "DOUBLES_CITY_GROWTH_RATE" => 512i64,
                        "INCREASES_LUXURY_TRADE" => 1024i64,
                        "ALLOWS_CITY_SIZE2" => 2048i64,
                        "ALLOWS_CITY_SIZE3" => 4096i64,
                        "REPLACES_OTHER_BUILDINGS" => 8192i64,
                        "MUST_BE_NEAR_WATER" => 16384i64,
                        "MUST_BE_NEAR_RIVER" => 32768i64,
                        "CAN_MELTDOWN" => 65536i64,
                        "VETERAN_SEA_UNITS" => 131072i64,
                        "VETERAN_AIR_UNITS" => 262144i64,
                        "ALLOWS_WATER_TRADE" => 524288i64,
                        "ALLOWS_AIR_TRADE" => 1048576i64,
                        "REDUCES_WAR_WEARINESS" => 2097152i64,
                        "INCREASES_SHIELDS_IN_WATER" => 4194304i64,
                        "INCREASES_FOOD_IN_WATER" => 8388608i64,
                        "INCREASES_TRADE_IN_WATER" => 16777216i64,
                        "GOODS_MUST_BE_IN_CITY_RADIUS" => 33554432i64,
                        "COASTAL_INSTALLATION" => 67108864i64,
                        "MILITARISTIC" => 134217728i64,
                        "WONDER" => 268435456i64,
                        "SMALL_WONDER" => 536870912i64,
                        "CONTINENTAL_MOOD_EFFECTS" => 1073741824i64,
                        "SCIENTIFIC" => 2147483648i64,
                        "COMMERCIAL" => 4294967296i64,
                        "EXPANSIONIST" => 8589934592i64,
                        "RELIGIOUS" => 17179869184i64,
                        "INDUSTRIOUS" => 34359738368i64,
                        "AGRICULTURAL" => 68719476736i64,
                        "SEAFARING" => 137438953472i64,
                        "INCREASES_LEADER_CHANCE" => 274877906944i64,
                        "ALLOWS_BUILD_ARMY" => 549755813888i64,
                        "ALLOWS_LARGER_ARMIES" => 1099511627776i64,
                        "TREASURY_EARNS_INTEREST" => 2199023255552i64,
                        "BUILD_SPACESHIP_PARTS" => 4398046511104i64,
                        "FORBIDDEN_PALACE" => 8796093022208i64,
                        "DECREASES_MISSILE_SUCCESS" => 17592186044416i64,
                        "ALLOWS_SPY_MISSIONS" => 35184372088832i64,
                        "ALLOWS_ENEMY_TERRITORY_HEALING" => 70368744177664i64,
                        "REQUIRES_VICTORIOUS_ARMY" => 140737488355328i64,
                        "REQUIRES_ELITE_SHIP" => 281474976710656i64,
                        "SAFE_SEA_TRAVEL" => 562949953421312i64,
                        "GAIN_ANY_TECH_KNOWN_BY_TWO_CIVS" => 1125899906842624i64,
                        "DOUBLE_COMBAT_VS_BARBARIANS" => 2251799813685248i64,
                        "INCREASED_SHIP_MOVEMENT" => 4503599627370496i64,
                        "DOUBLES_RESEARCH_OUTPUT" => 9007199254740992i64,
                        "INCREASED_TRADE" => 18014398509481984i64,
                        "CHEAPER_UPGRADES" => 36028797018963968i64,
                        "PAYS_TRADE_MAINTENANCE" => 72057594037927936i64,
                        "ALLOWS_NUCLEAR_WEAPONS" => 144115188075855872i64,
                        "DOUBLE_CITY_GROWTH" => 288230376151711744i64,
                        "TWO_FREE_ADVANCES" => 576460752303423488i64,
                        "REDUCED_WAR_WEARINESS" => 1152921504606846976i64,
                        "ALLOW_DIPLOMATIC_VICTORY" => 2305843009213693952i64,
                        "TOWNS_ONLY" => 4611686018427387904i64,
                        "TOURIST_ATTRACTION" => -9223372036854775808i64,
                        _ => return Err("unknown enum name".into()),
                    },
                });
                if (effect).is_none() {
                    return Err({
                        let __separator = &(String::new());
                        (&(vec![
                            "Unsupported building flag: ".to_string(),
                            (flag).to_string(),
                        ]))
                            .join(__separator)
                    }
                    .into());
                }
                effects = (effects | (*(effect).as_ref().ok_or("expected a value")?).clone());
            }
        }
        let mut wonder: indexmap::IndexMap<String, rt::Json> =
            object_field(&row, "greatWonderProperties")?;
        if boolean(&row, "isSmallWonder", false)? {
            effects = (effects | 536870912i64);
        } else {
            if {
                let __needle: &str = AsRef::<str>::as_ref("greatWonderProperties");
                let __container = &row;
                __container.contains_key(__needle)
            } {
                effects = (effects | 268435456i64);
            }
        }
        let mut commerce_bonus: Option<f64> = building_commerce_bonus(&row, "commerceBonus")?;
        let mut research_bonus: Option<f64> = building_commerce_bonus(&row, "researchBonus")?;
        let mut luxury_bonus: Option<f64> = building_commerce_bonus(&row, "luxuryBonus")?;
        if (commerce_bonus.clone() == Some(0.5f64)) {
            effects = (effects | 16i64);
        }
        if (research_bonus.clone() == Some(0.5f64)) {
            effects = (effects | 4i64);
        } else {
            if (research_bonus.clone() == Some(1.0f64)) {
                effects = (effects | 9007199254740992i64);
            }
        }
        let mut requirements: Option<i64> = decode_buildings__behaviors(
            &row,
            "productionPrerequisites",
            "production_rules",
            production_rules,
        )?;
        if ((requirements).is_some()
            && ((*(requirements.clone()).as_ref().ok_or("expected a value")?).clone()
                & 8796093022208i64)
                != 0)
        {
            effects = (effects | 8796093022208i64);
        }
        let mut required: Vec<i64> = ({
            let mut __comprehension_result_1257: Vec<i64> = Vec::new();
            let __comprehension_source_1256 = (strings(&row, "requiredResources")?);
            for name in __comprehension_source_1256.iter().cloned() {
                __comprehension_result_1257.push(reference(
                    &([(
                        "resource".to_string(),
                        serde_json::Value::from(name.clone()),
                    )]
                    .into_iter()
                    .collect::<indexmap::IndexMap<_, _>>()),
                    "resource",
                    resources,
                )?);
            }
            __comprehension_result_1257
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
        if (((required).len() as i64) > 2i64) {
            return Err("Building has more than two required resources"
                .to_string()
                .into());
        }
        let (mut resource1, mut resource2): (i64, i64) = {
            let __tuple_values = rt::list_slice(
                &({
                    let mut __left: Vec<i64> = required;
                    let __right: Vec<i64> = {
                        let __tuple_value = &((
                            (1i64).checked_neg().ok_or("integer overflow")?,
                            (1i64).checked_neg().ok_or("integer overflow")?,
                        ));
                        vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
                    };
                    __left.extend(__right);
                    __left
                }),
                0i64,
                2i64,
            );
            if __tuple_values.len() != 2 {
                return Err("tuple length mismatch".into());
            }
            (
                rt::at(&__tuple_values, 0i64)?,
                rt::at(&__tuple_values, 1i64)?,
            )
        };
        let mut produced: i64 = {
            let __key = text(&row, "unitProduced", "")?;
            let __default = (1i64).checked_neg().ok_or("integer overflow")?;
            units.get(&__key).cloned().unwrap_or(__default)
        };
        let mut local_content: i64 = integer(&row, "contentFacesInCity", 0i64)?;
        let mut empire_content: i64 = integer(&row, "contentFacesInAllCities", 0i64)?;
        let mut defense: i64 = percentage(&row, "combatDefenseBonus")?;
        let mut cost: i64 = integer(&row, "shieldCost", 0i64)?;
        if (rt::int_modulo(cost, 10i64)? != 0i64) {
            return Err("Building shield cost must be a multiple of ten"
                .to_string()
                .into());
        }
        {
            result.push(crate::openciv3::building_rules::Building {
                description: String::new(),
                name: text(&row, "name", "")?,
                civilopedia_entry: text(&row, "civilopediaEntry", "")?,
                icon_row: integer(
                    &row,
                    "iconRowIndex",
                    (1i64).checked_neg().ok_or("integer overflow")?,
                )?,
                doubles_happiness: reference(
                    &wonder,
                    "buildingWithDoubledHappiness",
                    &building_ids,
                )?,
                gain_in_every_city: reference(&wonder, "buildingGainedInEveryCity", &building_ids)?,
                gain_in_every_city_on_continent: reference(
                    &wonder,
                    "buildingGainedInEveryCityOnContinent",
                    &building_ids,
                )?,
                required_building: reference(&row, "requiredBuilding", &building_ids)?,
                cost: rt::int_floor_div(cost, 10i64)?,
                culture: integer(&row, "culturePerTurn", 0i64)?,
                bombard_defense: integer(
                    &(row.clone()),
                    "bombardDefense",
                    (if {
                        let __needle = "providesWalls".to_string();
                        let __container = &(strings(&row, "flags")?);
                        __container.contains(&__needle)
                    } {
                        8i64
                    } else {
                        0i64
                    }),
                )?,
                naval_bombard_defense: integer(&row, "navalBombardDefense", 0i64)?,
                defense_bonus: defense,
                naval_defense_bonus: percentage(&row, "navalDefenseBonus")?,
                maintenance_cost: integer(&row, "maintenanceCost", 0i64)?,
                content_faces_all_cities: (0i64).max(empire_content),
                content_faces: (0i64).max(local_content),
                unhappy_faces_all_cities: (0i64)
                    .max((empire_content).checked_neg().ok_or("integer overflow")?),
                unhappy_faces: (0i64).max((local_content).checked_neg().ok_or("integer overflow")?),
                number_of_required_buildings: integer(&row, "numberOfRequiredBuildings", 0i64)?,
                air_power: integer(&row, "airPower", 0i64)?,
                naval_power: integer(&row, "navalPower", 0i64)?,
                pollution: integer(&row, "pollution", 0i64)?,
                production: percentage(&row, "productionBonus")?,
                required_government: reference(&row, "requiredGovernment", &governments)?,
                spaceship_part: integer(
                    &row,
                    "spaceshipPart",
                    (1i64).checked_neg().ok_or("integer overflow")?,
                )?,
                required_advance: reference(&row, "requiredTech", technologies)?,
                rendered_obsolete_by: reference(&row, "renderedObsoleteBy", technologies)?,
                required_resource1: resource1,
                required_resource2: resource2,
                effects: effects,
                number_of_armies_required: integer(&row, "numberOfArmiesRequired", 0i64)?,
                flavors: 0i64,
                unit_produced: produced,
                unit_frequency: (if (produced >= 0i64) {
                    integer(&row, "unitFrequency", 0i64)?
                } else {
                    0i64
                }),
                commerce_bonus: commerce_bonus,
                research_bonus: research_bonus,
                luxury_bonus: luxury_bonus,
                population_cost: integer(&row, "populationCost", 0i64)?,
                production_requirements: requirements,
                provides_walls: Some({
                    let __needle = "providesWalls".to_string();
                    let __container = &(strings(&row, "flags")?);
                    __container.contains(&__needle)
                }),
                unit_production_effects: decode_buildings__behaviors(
                    &row,
                    "onFinishedUnitProduction",
                    "unit_production_effects",
                    &unit_effects,
                )?,
                water_yield_effects: decode_buildings__behaviors(
                    &row,
                    "tileModifiers",
                    "tile_modifiers",
                    &tile_effects,
                )?,
            });
        };
    }
    Ok((result).iter().cloned().collect::<Vec<_>>())
}

// Python: openciv3/json_rules.py:567
pub(crate) fn decode_rule_catalog(
    root: &indexmap::IndexMap<String, rt::Json>,
) -> rt::Result<crate::openciv3::rules::RuleCatalog> {
    _assemble_catalog(&((*root).clone()), &(decode_foundational_rules(root)?))
}

// Python: openciv3/json_rules.py:571
pub(crate) fn _assemble_catalog(
    root: &indexmap::IndexMap<String, rt::Json>,
    decoded: &FoundationalRules,
) -> rt::Result<crate::openciv3::rules::RuleCatalog> {
    Ok(crate::openciv3::rules::RuleCatalog {
        technologies: (decoded).technologies.clone(),
        resources: (decoded).resources.clone(),
        terrains: (decoded).terrains.clone(),
        units: (decoded).units.clone(),
        experience_levels: (decoded).experience.clone(),
        citizens: (decoded).citizens.clone(),
        worker_jobs: (decoded).workers.clone(),
        governments: (decoded).governments.clone(),
        buildings: (decoded).buildings.clone(),
        global_rules: vec![decode_global_rules(root)?],
    })
}

// Python: openciv3/json_rules.py:580
pub(crate) fn decode_wealth(
    root: &indexmap::IndexMap<String, rt::Json>,
) -> rt::Result<crate::openciv3::inflows::WealthRule> {
    if {
        let __needle: &str = AsRef::<str>::as_ref("inflows");
        let __container = root;
        !__container.contains_key(__needle)
    } {
        return Ok(crate::openciv3::inflows::WealthRule::COMMERCE);
    }
    let mut inflows: Vec<indexmap::IndexMap<String, rt::Json>> = records(root, "inflows")?;
    if !(((inflows).len() as i64) != 0i64) {
        return Ok(crate::openciv3::inflows::WealthRule::UNAVAILABLE);
    }
    if (((inflows).len() as i64) != 1i64) {
        return Err("Unsupported production inflow; expected Wealth"
            .to_string()
            .into());
    }
    let mut row: indexmap::IndexMap<String, rt::Json> = rt::at(&inflows, 0i64)?;
    let mut name: String = text(&row, "name", "")?;
    crate::openciv3::inflows::Inflow__from_legacy_name(&name)?;
    let mut yields: Vec<indexmap::IndexMap<String, rt::Json>> = (if {
        let __needle: &str = AsRef::<str>::as_ref("localYield");
        let __container = &row;
        __container.contains_key(__needle)
    } {
        records(&row, "localYield")?
    } else {
        vec![]
    });
    if !(((yields).len() as i64) != 0i64) {
        return Ok(crate::openciv3::inflows::WealthRule::NO_YIELD);
    }
    if ((((yields).len() as i64) != 1i64)
        || ((text(
            {
                let __source = &yields;
                let __key = 0i64;
                &__source[rt::index(__source.len(), __key)?]
            },
            "yieldType",
            "",
        )?)
        .as_str()
            != "commerce"))
    {
        return Err("Unsupported Wealth inflow yield".to_string().into());
    }
    let mut calculation: Option<rt::Json> = (rt::at(&yields, 0i64)?)
        .get(&("yieldCalculation".to_string()))
        .cloned();
    if ((calculation.clone()).is_none()
        || (rt::json_string(
            &((*(calculation.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?) == ((((), String::new())).1))
    {
        return Ok(crate::openciv3::inflows::WealthRule::NO_YIELD);
    }
    if {
        let __needle = rt::json_string(
            &((*(calculation.clone()).as_ref().ok_or("expected a value")?).clone()),
        )?;
        let __container = &({
            let __tuple_value = &((
                match crate::openciv3::inflows::WealthRule::COMMERCE {
                    crate::openciv3::inflows::WealthRule::UNAVAILABLE => "unavailable".to_string(),
                    crate::openciv3::inflows::WealthRule::NO_YIELD => "no_yield".to_string(),
                    crate::openciv3::inflows::WealthRule::COMMERCE => {
                        "inflows.result.wealth.commerce".to_string()
                    }
                },
                {
                    let __separator = &(String::new());
                    (&(vec![
                        "inflows.result.".to_string(),
                        (rt::casefold(&name)).to_string(),
                        ".commerce".to_string(),
                    ]))
                        .join(__separator)
                },
            ));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        !__container.contains(&__needle)
    } {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Unsupported Wealth yield calculation: ".to_string(),
                (rt::json_string(&((*(calculation).as_ref().ok_or("expected a value")?).clone()))?)
                    .to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok(crate::openciv3::inflows::WealthRule::COMMERCE)
}

// Python: openciv3/json_rules.py:604
pub(crate) fn decode_global_rules(
    root: &indexmap::IndexMap<String, rt::Json>,
) -> rt::Result<crate::openciv3::global_rules::GlobalRules> {
    let mut rules: indexmap::IndexMap<String, rt::Json> = object_field(root, "rules")?;
    let mut healing: indexmap::IndexMap<String, rt::Json> = object_field(root, "healRates")?;
    let mut defaults: crate::openciv3::global_rules::HealingRates =
        crate::openciv3::global_rules::HealingRates____post_init__(
            &(crate::openciv3::global_rules::HealingRates {
                friendly: 1i64,
                neutral: 1i64,
                hostile: 0i64,
                city: 2i64,
            }),
        )?;
    let mut healing_rates: crate::openciv3::global_rules::HealingRates =
        crate::openciv3::global_rules::HealingRates____post_init__(
            &(crate::openciv3::global_rules::HealingRates {
                friendly: integer(&healing, "friendly_field", (defaults).friendly)?,
                neutral: integer(&healing, "neutral_field", (defaults).neutral)?,
                hostile: integer(&healing, "hostile_field", (defaults).hostile)?,
                city: integer(&healing, "city", (defaults).city)?,
            }),
        )?;
    let mut route_costs: indexmap::IndexMap<String, f64> = [
        ("road".to_string(), rt::int_true_div(1i64, 3i64)?),
        ("railroad".to_string(), 0.0f64),
    ]
    .into_iter()
    .collect::<indexmap::IndexMap<_, _>>();
    let mut defenses: indexmap::IndexMap<String, f64> = [
        ("fortress".to_string(), 0.5f64),
        ("barricade".to_string(), 1.0f64),
    ]
    .into_iter()
    .collect::<indexmap::IndexMap<_, _>>();
    let mut extra_defenses: Vec<(i64, String, f64)> = vec![];
    let mut improvement_draw_order: Vec<(String, i64)> = vec![];
    let mut railroad_development_bonus: bool = false;
    for mut improvement in records(root, "terrainImprovements")? {
        let mut key: String = text(&improvement, "key", "")?;
        if {
            let __needle: &str = AsRef::<str>::as_ref("zIndex");
            let __container = &improvement;
            __container.contains_key(__needle)
        } {
            {
                improvement_draw_order.push((key.clone(), integer(&improvement, "zIndex", 0i64)?));
            };
        }
        if (key.as_str() == "railroad") {
            let mut modifier: Option<rt::Json> = (improvement.clone())
                .get(&("tileModifier".to_string()))
                .cloned();
            if !((modifier.clone()).is_none()
                || (rt::json_string(
                    &((*(modifier.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?) == (((
                    (),
                    String::new(),
                    "terrain_improvements.railroad.tile_modifier".to_string(),
                ))
                    .1)
                || (rt::json_string(
                    &((*(modifier.clone()).as_ref().ok_or("expected a value")?).clone()),
                )?) == (((
                    (),
                    String::new(),
                    "terrain_improvements.railroad.tile_modifier".to_string(),
                ))
                    .2))
            {
                return Err({
                    let __separator = &(String::new());
                    (&(vec![
                        "Unsupported railroad tile modifier: ".to_string(),
                        (rt::json_string(
                            &((*(modifier).as_ref().ok_or("expected a value")?).clone()),
                        )?)
                        .to_string(),
                    ]))
                        .join(__separator)
                }
                .into());
            }
            railroad_development_bonus = (modifier).is_some();
        }
        if {
            let __needle: &str = AsRef::<str>::as_ref(&key);
            let __container = &defenses;
            __container.contains_key(__needle)
        } {
            let mut amount: rt::Json = {
                let __mapping = object_field(&improvement, "defenseBonus")?;
                let __key = "amount".to_string();
                let __default = rt::to_json((defenses).get(&key).ok_or("missing dict key")?)?;
                __mapping.get(&__key).cloned().unwrap_or(__default)
            };
            if (rt::json_kind(&(amount.clone())) == "bool"
                || (!(rt::json_kind(&(amount.clone())) == "number")
                    || !(rt::math_isfinite(rt::json_float(&(amount.clone()))?))))
            {
                return Err({
                    let __separator = &(String::new());
                    (&(vec!["Invalid defense bonus for ".to_string(), (key).to_string()]))
                        .join(__separator)
                }
                .into());
            }
            {
                let __value = rt::json_float(&(amount))?;
                let __key = key.clone();
                defenses.insert(__key, __value);
            }
        } else {
            if ({
                let __needle: &str = AsRef::<str>::as_ref(&key);
                let __container = {
                    static __CONSTANT_py__openciv3__world__OVERLAY_KEYS: std::sync::OnceLock<
                        indexmap::IndexMap<String, i64>,
                    > = std::sync::OnceLock::new();
                    if __CONSTANT_py__openciv3__world__OVERLAY_KEYS.get().is_none() {
                        let __constant_value = [
                            ("road".to_string(), 1i64),
                            ("railroad".to_string(), 2i64),
                            ("mine".to_string(), 4i64),
                            ("irrigation".to_string(), 8i64),
                            ("fortress".to_string(), 16i64),
                            ("goodyHut".to_string(), 32i64),
                            ("pollution".to_string(), 64i64),
                            ("barbarianCamp".to_string(), 128i64),
                            ("craters".to_string(), 256i64),
                            ("barricade".to_string(), 268435456i64),
                            ("airfield".to_string(), 536870912i64),
                            ("radarTower".to_string(), 1073741824i64),
                            ("outpost".to_string(), 2147483648i64),
                        ]
                        .into_iter()
                        .collect::<indexmap::IndexMap<_, _>>();
                        let _ = __CONSTANT_py__openciv3__world__OVERLAY_KEYS.set(__constant_value);
                    }
                    __CONSTANT_py__openciv3__world__OVERLAY_KEYS
                        .get()
                        .ok_or("missing module constant")?
                };
                __container.contains_key(__needle)
            } && ((improvement.clone())
                .get(&("defenseBonus".to_string()))
                .cloned())
            .is_some())
            {
                let mut defense: indexmap::IndexMap<String, rt::Json> =
                    object_field(&improvement, "defenseBonus")?;
                let mut amount: rt::Json = {
                    let __key = "amount".to_string();
                    let __default = serde_json::Value::from(0i64);
                    defense.get(&__key).cloned().unwrap_or(__default)
                };
                if (rt::json_kind(&(amount.clone())) == "bool"
                    || (!(rt::json_kind(&(amount.clone())) == "number")
                        || !(rt::math_isfinite(rt::json_float(&(amount.clone()))?))))
                {
                    return Err({
                        let __separator = &(String::new());
                        (&(vec!["Invalid defense bonus for ".to_string(), (key).to_string()]))
                            .join(__separator)
                    }
                    .into());
                }
                {
                    extra_defenses.push((
                        ({
                            static __CONSTANT_py__openciv3__world__OVERLAY_KEYS:
                                std::sync::OnceLock<indexmap::IndexMap<String, i64>> =
                                std::sync::OnceLock::new();
                            if __CONSTANT_py__openciv3__world__OVERLAY_KEYS.get().is_none() {
                                let __constant_value = [
                                    ("road".to_string(), 1i64),
                                    ("railroad".to_string(), 2i64),
                                    ("mine".to_string(), 4i64),
                                    ("irrigation".to_string(), 8i64),
                                    ("fortress".to_string(), 16i64),
                                    ("goodyHut".to_string(), 32i64),
                                    ("pollution".to_string(), 64i64),
                                    ("barbarianCamp".to_string(), 128i64),
                                    ("craters".to_string(), 256i64),
                                    ("barricade".to_string(), 268435456i64),
                                    ("airfield".to_string(), 536870912i64),
                                    ("radarTower".to_string(), 1073741824i64),
                                    ("outpost".to_string(), 2147483648i64),
                                ]
                                .into_iter()
                                .collect::<indexmap::IndexMap<_, _>>();
                                let _ = __CONSTANT_py__openciv3__world__OVERLAY_KEYS
                                    .set(__constant_value);
                            }
                            __CONSTANT_py__openciv3__world__OVERLAY_KEYS
                                .get()
                                .ok_or("missing module constant")?
                        })
                        .get(&key)
                        .ok_or("missing dict key")?
                        .clone(),
                        text(&defense, "description", &key)?,
                        rt::json_float(&(amount))?,
                    ));
                };
            }
        }
        if {
            let __needle: &str = AsRef::<str>::as_ref(&key);
            let __container = &route_costs;
            !__container.contains_key(__needle)
        } {
            continue;
        }
        let mut cost: rt::Json = {
            let __key = "movementCost".to_string();
            let __default = rt::to_json((route_costs).get(&key).ok_or("missing dict key")?)?;
            improvement.get(&__key).cloned().unwrap_or(__default)
        };
        if (rt::json_kind(&(cost.clone())) == "bool"
            || (!(rt::json_kind(&(cost.clone())) == "number")
                || (!(rt::math_isfinite(rt::json_float(&(cost.clone()))?))
                    || ((rt::json_float(&(cost.clone()))? < ((0i64) as f64))
                        && (rt::json_int(&(cost.clone()))?
                            != (1i64).checked_neg().ok_or("integer overflow")?)))))
        {
            return Err({
                let __separator = &(String::new());
                (&(vec!["Invalid movement cost for ".to_string(), (key).to_string()]))
                    .join(__separator)
            }
            .into());
        }
        {
            let __value = rt::json_float(&(cost))?;
            let __key = key;
            route_costs.insert(__key, __value);
        }
    }
    let mut barbarians: indexmap::IndexMap<String, rt::Json> = object_field(root, "barbarianInfo")?;
    let mut units: indexmap::IndexMap<String, i64> =
        identifiers(&(records(root, "unitPrototypes")?), "name")?;
    let mut difficulty: indexmap::IndexMap<String, i64> =
        identifiers(&(records(root, "difficulties")?), "name")?;
    let mut bonuses: indexmap::IndexMap<String, i64> = {
        let mut __comprehension_result_1259: indexmap::IndexMap<String, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_1258 = (records(root, "strengthBonuses")?);
        for row in __comprehension_source_1258.iter().cloned() {
            {
                let (__key, __value) =
                    (text(&row, "description", "")?, percentage(&row, "amount")?);
                __comprehension_result_1259.insert(__key, __value);
            }
        }
        __comprehension_result_1259
    };
    let mut camp_gold: i64 = integer(&rules, "barbarianCampGold", 25i64)?;
    if (camp_gold < 0i64) {
        return Err("Barbarian camp reward cannot be negative"
            .to_string()
            .into());
    }
    let mut radar_radius: i64 = integer(&rules, "radarTileVisibility", 2i64)?;
    if (radar_radius < 0i64) {
        return Err("Radar radius cannot be negative".to_string().into());
    }
    let mut disband_rate: rt::Json = {
        let __key = "shieldRateForDisbanding".to_string();
        let __default = rt::to_json(&(0.25f64))?;
        rules.get(&__key).cloned().unwrap_or(__default)
    };
    if (rt::json_kind(&(disband_rate.clone())) == "bool"
        || (!(rt::json_kind(&(disband_rate.clone())) == "number")
            || (!(rt::math_isfinite(rt::json_float(&(disband_rate.clone()))?))
                || (rt::json_float(&(disband_rate.clone()))? < ((0i64) as f64)))))
    {
        return Err("Disband shield rate must be finite and nonnegative"
            .to_string()
            .into());
    }
    let mut food_boxes: (i64, i64, i64) = (
        integer(&rules, "foodNeededToGrowForLevel1Cities", 20i64)?,
        integer(&rules, "foodNeededToGrowForLevel2Cities", 40i64)?,
        integer(&rules, "foodNeededToGrowForLevel3Cities", 60i64)?,
    );
    if ({
        let __values = &({
            let __tuple_value = &food_boxes;
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
            ]
        });
        let mut __items = __values.iter();
        let mut __best = __items.next().ok_or("min() arg is an empty sequence")?;
        for __candidate in __items {
            if __candidate < __best {
                __best = __candidate;
            }
        }
        (*__best).clone()
    } <= 0i64)
    {
        return Err("Food boxes must have positive capacity".to_string().into());
    }
    let mut interest_rate: rt::Json = {
        let __key = "treasuryInterestRate".to_string();
        let __default = rt::to_json(&(0.05f64))?;
        rules.get(&__key).cloned().unwrap_or(__default)
    };
    if (rt::json_kind(&(interest_rate.clone())) == "bool"
        || (!(rt::json_kind(&(interest_rate.clone())) == "number")
            || (!(rt::math_isfinite(rt::json_float(&(interest_rate.clone()))?))
                || (rt::json_float(&(interest_rate.clone()))? < ((0i64) as f64)))))
    {
        return Err("Treasury interest rate must be finite and nonnegative"
            .to_string()
            .into());
    }
    let mut max_interest: i64 = integer(&rules, "maxInterest", 50i64)?;
    let mut capital_distance: i64 = integer(&rules, "capitalNeighborDistance", 8i64)?;
    if ((max_interest < 0i64) || (capital_distance < 0i64)) {
        return Err(
            "Interest cap and capital neighbor distance must be nonnegative"
                .to_string()
                .into(),
        );
    }
    let mut building_discount: rt::Json = {
        let __key = "buildingDiscountForCivTraits".to_string();
        let __default = rt::to_json(&(0.5f64))?;
        rules.get(&__key).cloned().unwrap_or(__default)
    };
    if (rt::json_kind(&(building_discount.clone())) == "bool"
        || (!(rt::json_kind(&(building_discount.clone())) == "number")
            || (!(rt::math_isfinite(rt::json_float(&(building_discount.clone()))?))
                || (rt::json_float(&(building_discount.clone()))? < ((0i64) as f64)))))
    {
        return Err(
            "Civilization trait building discount must be finite and nonnegative"
                .to_string()
                .into(),
        );
    }
    let mut workable_rank: i64 = integer(&rules, "maxRankOfWorkableTiles", 2i64)?;
    let mut camp_rank: i64 = integer(&rules, "maxRankOfBarbarianCampTiles", 2i64)?;
    if ((workable_rank < 1i64) || (camp_rank < 0i64)) {
        return Err("Invalid workable tile or barbarian camp radius"
            .to_string()
            .into());
    }
    let mut deal_duration: i64 = integer(&rules, "defaultDealDuration", 20i64)?;
    if (deal_duration < 0i64) {
        return Err("Default deal duration cannot be negative"
            .to_string()
            .into());
    }
    let mut barbarian_hit_points: i64 = integer(&barbarians, "maxHitpoints", 2i64)?;
    if (barbarian_hit_points < 1i64) {
        return Err("Barbarian spawn hit points must be positive"
            .to_string()
            .into());
    }
    let mut default_experience: i64 = 1i64;
    if (((*root).clone())
        .get(&("defaultExperienceLevel".to_string()))
        .cloned())
    .is_some()
    {
        let mut levels: indexmap::IndexMap<String, i64> =
            identifiers(&(records(root, "experienceLevels")?), "key")?;
        default_experience = reference(root, "defaultExperienceLevel", &levels)?;
    }
    Ok(crate::openciv3::global_rules::GlobalRules____post_init__(
        &(crate::openciv3::global_rules::GlobalRules {
            city_size_names: (
                "Town".to_string(),
                "City".to_string(),
                "Metropolis".to_string(),
            ),
            spaceship_parts: vec![],
            advanced_barbarian_unit_type: reference(&barbarians, "advancedBarbarianUnit", &units)?,
            basic_barbarian_unit_type: reference(&barbarians, "basicBarbarianUnit", &units)?,
            barbarian_sea_unit_type: reference(&barbarians, "barbarianSeaUnit", &units)?,
            barbarian_spawn_hit_points: barbarian_hit_points,
            default_unit_experience: default_experience,
            cities_needed_to_support_an_army: 4i64,
            chance_of_rioting: 0i64,
            turn_penalty_for_each_drafted_citizen: 20i64,
            shields_cost_per_gold: integer(&rules, "shieldCostPerGold", 4i64)?,
            fortress_defensive_bonus: 50i64,
            citizens_affected_by_each_happy_face: 1i64,
            forest_value_in_shields: integer(&rules, "forestValueInShields", 10i64)?,
            shield_value_in_gold: integer(&rules, "shieldValueInGold", 4i64)?,
            citizen_value_in_shields: integer(&rules, "citizenValueInShields", 20i64)?,
            default_difficulty_level: {
                let __key = "Regent".to_string();
                let __default = 0i64;
                difficulty.get(&__key).cloned().unwrap_or(__default)
            },
            battle_created_unit: (1i64).checked_neg().ok_or("integer overflow")?,
            build_army_unit: (1i64).checked_neg().ok_or("integer overflow")?,
            building_defensive_bonus: integer(&rules, "buildingDefensiveBonus", 16i64)?,
            citizen_defensive_bonus: integer(&rules, "citizenDefensiveBonus", 12i64)?,
            default_money_resource: (1i64).checked_neg().ok_or("integer overflow")?,
            chance_to_intercept_enemy_air_missions: 50i64,
            chance_to_intercept_enemy_stealth_missions: 5i64,
            starting_treasury: 10i64,
            food_consumption_per_citizen: integer(&rules, "foodConsumptionPerCitizen", 2i64)?,
            river_defensive_bonus: {
                let __key = "Behind river".to_string();
                let __default = 25i64;
                bonuses.get(&__key).cloned().unwrap_or(__default)
            },
            turn_penalty_for_each_hurry_sacrifice: integer(
                &rules,
                "turnPenaltyForEachHurrySacrifice",
                20i64,
            )?,
            scout: reference(&rules, "scoutUnitType", &units)?,
            slave: (1i64).checked_neg().ok_or("integer overflow")?,
            movement_along_roads: 3i64,
            start_unit_type1: reference(&rules, "startUnitType1", &units)?,
            start_unit_type2: reference(&rules, "startUnitType2", &units)?,
            minimum_population_for_we_love_the_king: 6i64,
            town_defense_bonus: {
                let __key = "Town".to_string();
                let __default = 0i64;
                bonuses.get(&__key).cloned().unwrap_or(__default)
            },
            city_defense_bonus: {
                let __key = "City".to_string();
                let __default = 50i64;
                bonuses.get(&__key).cloned().unwrap_or(__default)
            },
            metropolis_defense_bonus: {
                let __key = "Metropolis".to_string();
                let __default = 100i64;
                bonuses.get(&__key).cloned().unwrap_or(__default)
            },
            maximum_level1_city_size: integer(&rules, "maximumLevel1CitySize", 6i64)?,
            maximum_level2_city_size: integer(&rules, "maximumLevel2CitySize", 12i64)?,
            fortifications_defensive_bonus: {
                let __key = "Fortified".to_string();
                let __default = 25i64;
                bonuses.get(&__key).cloned().unwrap_or(__default)
            },
            culture_levels: vec![
                "None".to_string(),
                "Small".to_string(),
                "Modest".to_string(),
                "Average".to_string(),
                "Impressive".to_string(),
                "Influential".to_string(),
                "Legendary".to_string(),
            ],
            border_expansion_multiplier: 10i64,
            border_factor: 10i64,
            future_tech_cost: 10i64,
            golden_age_duration: 20i64,
            maximum_research_time: integer(&rules, "maximumResearchTime", 50i64)?,
            minimum_research_time: integer(&rules, "minimumResearchTime", 4i64)?,
            flag_unit_type: (1i64).checked_neg().ok_or("integer overflow")?,
            upgrade_cost: 3i64,
            barbarian_camp_gold: camp_gold,
            wealth: decode_wealth(root)?,
            radar_tile_visibility: radar_radius,
            shield_rate_for_disbanding: rt::json_float(&(disband_rate))?,
            allow_lesser_unit_production: boolean(&rules, "allowLesserUnitProduction", false)?,
            food_boxes: food_boxes,
            treasury_interest_rate: rt::json_float(&(interest_rate))?,
            max_interest: max_interest,
            capital_neighbor_distance: capital_distance,
            building_discount_for_civ_traits: rt::json_float(&(building_discount))?,
            max_rank_of_workable_tiles: workable_rank,
            max_rank_of_barbarian_camp_tiles: camp_rank,
            default_deal_duration: deal_duration,
            healing_rates: healing_rates,
            road_movement_cost: (route_costs).get("road").ok_or("missing dict key")?.clone(),
            railroad_movement_cost: (route_costs)
                .get("railroad")
                .ok_or("missing dict key")?
                .clone(),
            railroad_development_bonus: railroad_development_bonus,
            fortress_defense: (defenses)
                .get("fortress")
                .ok_or("missing dict key")?
                .clone(),
            barricade_defense: (defenses)
                .get("barricade")
                .ok_or("missing dict key")?
                .clone(),
            extra_improvement_defenses: (extra_defenses).iter().cloned().collect::<Vec<_>>(),
            improvement_draw_order: (improvement_draw_order).iter().cloned().collect::<Vec<_>>(),
        }),
    )?)
}

// Python: openciv3/json_rules.py:749
pub(crate) fn decode_standalone_scenario(
    root: &indexmap::IndexMap<String, rt::Json>,
    source: &str,
) -> rt::Result<(
    crate::openciv3::scenario_model::ScenarioDefinition,
    Vec<crate::openciv3::world_size::WorldSize>,
)> {
    let mut portrait: String;
    let mut decoded: FoundationalRules = decode_foundational_rules(root)?;
    let mut tech_ids: indexmap::IndexMap<String, i64> =
        identifiers(&(records(root, "techs")?), "id")?;
    let mut groups: indexmap::IndexMap<String, i64> = {
        let mut __comprehension_result_1261: indexmap::IndexMap<String, i64> =
            indexmap::IndexMap::new();
        let __comprehension_source_1260 = (records(root, "cultureGroups")?);
        for row in __comprehension_source_1260.iter().cloned() {
            {
                let (__key, __value) = (text(&row, "name", "")?, integer(&row, "index", 0i64)?);
                __comprehension_result_1261.insert(__key, __value);
            }
        }
        __comprehension_result_1261
    };
    let mut civilizations: Vec<crate::openciv3::scenario_model::Civilization> = vec![];
    let mut portraits: indexmap::IndexMap<String, String> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut for_target_755_4 in (records(root, "civilizations")?)
        .into_iter()
        .enumerate()
        .map(|(__index, __value)| (__index as i64 + 0i64, __value))
        .collect::<Vec<_>>()
    {
        let (mut index, mut row): (i64, indexmap::IndexMap<String, rt::Json>) = for_target_755_4;
        if (boolean(&row, "isBarbarian", false)? != (index == 0i64)) {
            return Err("The first civilization must be the barbarian civilization"
                .to_string()
                .into());
        }
        let mut name: String = text(&row, "name", "")?;
        if ((({
            portrait = text(&row, "leaderArtFile", "")?;
            portrait.clone()
        })
        .chars()
        .count() as i64)
            != 0i64)
        {
            {
                let __value = portrait.clone();
                let __key = name.clone();
                portraits.insert(__key, __value);
            }
        }
        {
            civilizations.push(crate::openciv3::scenario_model::Civilization {
                index: index,
                name: name,
                noun: text(&row, "noun", "")?,
                adjective: text(&row, "adjective", "")?,
                leader: text(&row, "leader", "")?,
                leader_title: String::new(),
                civilopedia_entry: String::new(),
                city_names: strings(&row, "cityNames")?,
                great_leaders: vec![],
                scientific_leaders: vec![],
                era_animations: vec![],
                culture_group: (groups.clone())
                    .get(&(text(&row, "cultureGroupKey", "None")?))
                    .ok_or("missing dict key")?
                    .clone(),
                leader_gender: (((text(&row, "leaderGender", "")?).as_str() == "female") as i64),
                civilization_gender: 0i64,
                aggression: 2i64,
                shunned_government: (1i64).checked_neg().ok_or("integer overflow")?,
                favorite_government: (1i64).checked_neg().ok_or("integer overflow")?,
                primary_color: integer(&row, "primaryColorIndex", 0i64)?,
                secondary_color: integer(&row, "secondaryColorIndex", 0i64)?,
                starting_techs: ({
                    let mut __comprehension_result_1263: Vec<i64> = Vec::new();
                    let __comprehension_source_1262 = (strings(&row, "startingTechs")?);
                    for key in __comprehension_source_1262.iter().cloned() {
                        __comprehension_result_1263.push(reference(
                            &([("tech".to_string(), serde_json::Value::from(key.clone()))]
                                .into_iter()
                                .collect::<indexmap::IndexMap<_, _>>()),
                            "tech",
                            &tech_ids,
                        )?);
                    }
                    __comprehension_result_1263
                })
                .iter()
                .cloned()
                .collect::<Vec<_>>(),
                traits: ({
                    let mut __comprehension_result_1265: Vec<String> = Vec::new();
                    let __comprehension_source_1264 = (strings(&row, "traits")?);
                    for item in __comprehension_source_1264.iter().cloned() {
                        __comprehension_result_1265.push(rt::string_capitalize(&item));
                    }
                    __comprehension_result_1265
                })
                .iter()
                .cloned()
                .collect::<Vec<_>>(),
                governor_flags: rt::byte_buffer_new(12i64)?,
                plurality: 0i64,
                king_unit: (1i64).checked_neg().ok_or("integer overflow")?,
                flavors: 0i64,
                diplomacy_text_index: 0i64,
            });
        };
    }
    if ((((civilizations).len() as i64) < 2i64)
        || (!(((&(decoded).difficulties).len() as i64) != 0i64)
            || !(((&(decoded).world_sizes).len() as i64) != 0i64)))
    {
        return Err(
            "Standalone rules need civilizations, difficulties, and world sizes"
                .to_string()
                .into(),
        );
    }
    let mut playable: Vec<crate::openciv3::scenario_model::Civilization> =
        (rt::slice_view(&civilizations, 1i64, i64::MAX))
            .iter()
            .cloned()
            .collect::<Vec<_>>();
    let mut allowed: Vec<i64> = ({
        let mut __comprehension_result_1267: Vec<i64> = Vec::new();
        let __comprehension_source_1266 = (playable.clone());
        for civ in __comprehension_source_1266.iter().cloned() {
            __comprehension_result_1267.push((civ).index);
        }
        __comprehension_result_1267
    })
    .iter()
    .cloned()
    .collect::<Vec<_>>();
    let mut time: indexmap::IndexMap<String, rt::Json> = object_field(root, "timeOptions")?;
    let mut time_scale: Vec<(i64, i64)> = {
        static __CONSTANT_py__openciv3__calendar__DEFAULT_SCALE: std::sync::OnceLock<
            Vec<(i64, i64)>,
        > = std::sync::OnceLock::new();
        if __CONSTANT_py__openciv3__calendar__DEFAULT_SCALE
            .get()
            .is_none()
        {
            let __constant_value = vec![
                (25i64, 50i64),
                (25i64, 40i64),
                (40i64, 25i64),
                (50i64, 20i64),
                (100i64, 10i64),
                (100i64, 5i64),
                (100i64, 2i64),
            ];
            let _ = __CONSTANT_py__openciv3__calendar__DEFAULT_SCALE.set(__constant_value);
        }
        __CONSTANT_py__openciv3__calendar__DEFAULT_SCALE
            .get()
            .ok_or("missing module constant")?
            .clone()
    };
    if {
        let __needle: &str = AsRef::<str>::as_ref("timeScale");
        let __container = &time;
        __container.contains_key(__needle)
    } {
        let mut scale: rt::Json = (time).get("timeScale").ok_or("missing dict key")?.clone();
        if (!(rt::json_kind(&(scale.clone())) == "array")
            || ((((rt::json_array(&(scale))?).len() as i64) != 2i64)
                || (!(rt::json_kind(&(rt::json_index(&scale, 0i64)?)) == "array")
                    || !(rt::json_kind(&(rt::json_index(&scale, 1i64)?)) == "array"))))
        {
            return Err("Expected two time scale arrays".to_string().into());
        }
        time_scale = ({
            let mut __comprehension_result_1269: Vec<(i64, i64)> = Vec::new();
            let __comprehension_source_1268 = ({
                let __left = rt::json_array(&(rt::json_index(&scale, 0i64)?))?;
                let __right = rt::json_array(&(rt::json_index(&scale, 1i64)?))?;
                if true && __left.len() != __right.len() {
                    return Err("zip() argument lengths differ".into());
                }
                let mut __result: Vec<(rt::Json, rt::Json)> = Vec::new();
                let __length = __left.len().min(__right.len());
                let mut __left_iter = __left.into_iter();
                let mut __right_iter = __right.into_iter();
                for __index in 0..__length {
                    __result.push((__left_iter.next().unwrap(), __right_iter.next().unwrap()));
                }
                __result
            });
            for (duration, step) in __comprehension_source_1268.iter().cloned() {
                __comprehension_result_1269.push((
                    integer(
                        &([("duration".to_string(), duration.clone())]
                            .into_iter()
                            .collect::<indexmap::IndexMap<_, _>>()),
                        "duration",
                        0i64,
                    )?,
                    integer(
                        &([("step".to_string(), step.clone())]
                            .into_iter()
                            .collect::<indexmap::IndexMap<_, _>>()),
                        "step",
                        0i64,
                    )?,
                ));
            }
            __comprehension_result_1269
        })
        .iter()
        .cloned()
        .collect::<Vec<_>>();
    }
    let mut base_unit: String = (&(text(&time, "baseUnit", "years")?)).to_uppercase();
    if !((base_unit.clone()) == "DAYS"
        || (base_unit.clone()) == "WEEKS"
        || (base_unit.clone()) == "HOURS"
        || (base_unit.clone()) == "MONTHS"
        || (base_unit.clone()) == "YEARS")
    {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Unknown calendar unit: ".to_string(),
                (base_unit).to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    let mut options: crate::openciv3::scenario_model::ScenarioOptions =
        crate::openciv3::scenario_model::ScenarioOptions {
            allowed_civilizations: allowed.clone(),
            mod_paths: vec![],
            victory_flags: 0i64,
            start_year: integer(
                &time,
                "startYear",
                (4000i64).checked_neg().ok_or("integer overflow")?,
            )?,
            time_unit: match (base_unit).as_str() {
                "YEARS" => 0i64,
                "MONTHS" => 1i64,
                "WEEKS" => 2i64,
                "DAYS" => 3i64,
                "HOURS" => 4i64,
                _ => return Err("unknown enum name".into()),
            },
            turn_limit: integer(&time, "turnLimit", 540i64)?,
            alliance_ids: vec![],
            start_month: integer(&time, "startMonth", 1i64)?,
            start_week: integer(&time, "startWeek", 1i64)?,
            time_scale: time_scale,
            start_day: integer(&time, "startDay", 1i64)?,
            start_hour: integer(&time, "startHour", 12i64)?,
            negative_label: text(&time, "negativeLabel", "BC")?,
            positive_label: text(&time, "positiveLabel", "AD")?,
            alliance_names: vec![],
            alliance_wars: std::collections::BTreeSet::new(),
            alliance_victory_type: 0i64,
            map_visible: false,
        };
    let mut metadata: crate::openciv3::scenario::Scenario = crate::openciv3::scenario::Scenario {
        title: "Standalone".to_string(),
        description: String::new(),
        sections: [].into_iter().collect::<indexmap::IndexMap<_, _>>(),
        encoding: "cp1252".to_string(),
        world: None,
    };
    Ok((
        crate::openciv3::scenario_model::ScenarioDefinition {
            source: source.to_owned(),
            scenario: metadata.clone(),
            defaults: metadata.clone(),
            civilizations: (civilizations).iter().cloned().collect::<Vec<_>>(),
            difficulties: (decoded).difficulties.clone(),
            slots: vec![],
            options: options,
            assigned_civilizations: allowed,
            playable: playable,
            seed: 0i64,
            world: None,
            rules: _assemble_catalog(root, &decoded)?,
            portrait_paths: portraits,
            selected_civilization: String::new(),
            selected_difficulty: String::new(),
            world_size: None,
        },
        (decoded).world_sizes.clone(),
    ))
}

// Python: openciv3/json_rules.py:250
pub(crate) fn decode_terrains__bonus_for(
    improvement: &indexmap::IndexMap<String, rt::Json>,
    terrain: &str,
) -> rt::Result<crate::civ::economy::Yield> {
    let mut values: indexmap::IndexMap<String, rt::Json> = object_field(improvement, terrain)?;
    Ok(crate::civ::economy::Yield {
        food: integer(&values, "food", 0i64)?,
        shields: integer(&values, "production", 0i64)?,
        commerce: integer(&values, "commerce", 0i64)?,
    })
}

// Python: openciv3/json_rules.py:470
pub(crate) fn decode_buildings__behaviors(
    row: &indexmap::IndexMap<String, rt::Json>,
    field: &str,
    group: &str,
    supported: &indexmap::IndexMap<String, i64>,
) -> rt::Result<Option<i64>> {
    if {
        let __needle: &str = AsRef::<str>::as_ref(field);
        let __container = row;
        !__container.contains_key(__needle)
    } {
        return Ok(None);
    }
    let mut result: i64 = 0i64;
    let mut prefix: String = {
        let __separator = &(String::new());
        (&(vec![
            "buildings.".to_string(),
            (group.to_owned()).to_string(),
            ".".to_string(),
        ]))
            .join(__separator)
    };
    for mut path in strings(row, field)? {
        let mut effect: Option<i64> = (if (&path).starts_with(&prefix) {
            ((*supported).clone())
                .get(&(rt::str_slice(&path, ((prefix).chars().count() as i64), i64::MAX)))
                .cloned()
        } else {
            None
        });
        if (effect).is_none() {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Unsupported building behavior: ".to_string(),
                    (path).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        result = (result | (*(effect).as_ref().ok_or("expected a value")?).clone());
    }
    Ok(Some(result))
}
