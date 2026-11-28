use py2rust_service_runtime as rt;

// Python: openciv3/standalone.py:7
pub(crate) fn _load_unit_art() -> rt::Result<indexmap::IndexMap<String, String>> {
    let mut path: String = "GameModes/standalone/unit-art.json".to_string();
    let mut result: indexmap::IndexMap<String, String> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    for mut for_target_10_4 in (crate::openciv3::json_io::read_object(&path)?)
        .iter()
        .map(|(__key, __value)| (__key.clone(), __value.clone()))
        .collect::<Vec<_>>()
    {
        let (mut unit, mut art): (String, rt::Json) = for_target_10_4;
        if !(rt::json_kind(&(art.clone())) == "string") {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Invalid standalone art directory for ".to_string(),
                    (unit).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        {
            let __value = rt::json_string(&(art.clone()))?;
            let __key = unit.clone();
            result.insert(__key, __value);
        }
    }
    Ok(result)
}

// Python: openciv3/standalone.py:20
pub(crate) fn replacement_art(name: &str) -> rt::Result<String> {
    let mut replacement: Option<String> = ({
        static __CONSTANT_py__openciv3__standalone__UNIT_ART: std::sync::OnceLock<
            indexmap::IndexMap<String, String>,
        > = std::sync::OnceLock::new();
        if __CONSTANT_py__openciv3__standalone__UNIT_ART
            .get()
            .is_none()
        {
            let __constant_value = _load_unit_art()?;
            let _ = __CONSTANT_py__openciv3__standalone__UNIT_ART.set(__constant_value);
        }
        __CONSTANT_py__openciv3__standalone__UNIT_ART
            .get()
            .ok_or("missing module constant")?
            .clone()
    })
    .get(&(name.to_owned()))
    .cloned();
    if (replacement).is_none() {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "No standalone art replacement for unit: ".to_string(),
                (name.to_owned()).to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok((*(replacement).as_ref().ok_or("expected a value")?).clone())
}

/// Copy a base ruleset, retaining supported units and removing dead upgrades.
// Python: openciv3/standalone.py:27
pub(crate) fn standalone_ruleset(
    base: &indexmap::IndexMap<String, rt::Json>,
) -> rt::Result<indexmap::IndexMap<String, rt::Json>> {
    let mut result: indexmap::IndexMap<String, rt::Json> = (*base).clone();
    let mut prototypes: Option<rt::Json> = (result.clone())
        .get(&("unitPrototypes".to_string()))
        .cloned();
    if !(rt::json_kind(&((*(prototypes.clone()).as_ref().ok_or("expected a value")?).clone()))
        == "array")
    {
        return Err("Ruleset must define a unitPrototypes array"
            .to_string()
            .into());
    }
    let mut supported: Vec<rt::Json> = vec![];
    for mut prototype in
        rt::json_array(&((*(prototypes).as_ref().ok_or("expected a value")?).clone()))?
    {
        if (!(rt::json_kind(&(prototype.clone())) == "object")
            || !(rt::json_kind(&(rt::json_get(&prototype, "name", &(serde_json::Value::Null))?))
                == "string"))
        {
            return Err("Each unit prototype must have a name".to_string().into());
        }
        let mut name: rt::Json = rt::json_key(&prototype, "name")?;
        if !(rt::json_kind(&(name.clone())) == "string") {
            rt::assertion(false, &("".to_string()))?;
        }
        let mut replacement: Option<String> = ({
            static __CONSTANT_py__openciv3__standalone__UNIT_ART: std::sync::OnceLock<
                indexmap::IndexMap<String, String>,
            > = std::sync::OnceLock::new();
            if __CONSTANT_py__openciv3__standalone__UNIT_ART
                .get()
                .is_none()
            {
                let __constant_value = _load_unit_art()?;
                let _ = __CONSTANT_py__openciv3__standalone__UNIT_ART.set(__constant_value);
            }
            __CONSTANT_py__openciv3__standalone__UNIT_ART
                .get()
                .ok_or("missing module constant")?
                .clone()
        })
        .get(&(rt::json_string(&(name.clone()))?))
        .cloned();
        if (replacement).is_none() {
            continue;
        }
        let mut art: Option<rt::Json> =
            Some(rt::json_get(&prototype, "art", &(serde_json::Value::Null))?);
        if !(rt::json_kind(&((*(art.clone()).as_ref().ok_or("expected a value")?).clone()))
            == "object")
        {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Missing art definition for ".to_string(),
                    (rt::json_string(&(name))?).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        let mut main_art: Option<rt::Json> = Some(rt::json_get(
            &((*(art.clone()).as_ref().ok_or("expected a value")?).clone()),
            "mainArt",
            &(serde_json::Value::Null),
        )?);
        let mut pedia: Option<rt::Json> = Some(rt::json_get(
            &((*(art).as_ref().ok_or("expected a value")?).clone()),
            "pediaArt",
            &(serde_json::Value::Null),
        )?);
        if (!(rt::json_kind(&((*(main_art.clone()).as_ref().ok_or("expected a value")?).clone()))
            == "object")
            || !(rt::json_kind(&((*(pedia.clone()).as_ref().ok_or("expected a value")?).clone()))
                == "object"))
        {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Incomplete art definition for ".to_string(),
                    (rt::json_string(&(name))?).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        {
            let __value = serde_json::Value::from(
                (*(replacement).as_ref().ok_or("expected a value")?).clone(),
            );
            let __key = "defaultName".to_string();
            main_art
                .as_mut()
                .ok_or("expected a value")?
                .as_object_mut()
                .ok_or("expected JSON object")?
                .insert(__key, __value);
        }
        {
            let __value =
                serde_json::Value::from("art/civilopedia/icons/units/unit_large.png".to_string());
            let __key = "large".to_string();
            pedia
                .as_mut()
                .ok_or("expected a value")?
                .as_object_mut()
                .ok_or("expected JSON object")?
                .insert(__key, __value);
        }
        {
            let __value =
                serde_json::Value::from("art/civilopedia/icons/units/unit_small.png".to_string());
            let __key = "small".to_string();
            pedia
                .as_mut()
                .ok_or("expected a value")?
                .as_object_mut()
                .ok_or("expected JSON object")?
                .insert(__key, __value);
        }
        let mut upgrades: rt::Json = rt::json_get(
            &prototype,
            "upgradesTo",
            &(serde_json::Value::Array(vec![])),
        )?;
        if (!(rt::json_kind(&(upgrades.clone())) == "array")
            || ({
                let mut __comprehension_result_1271: Vec<bool> = Vec::new();
                let __comprehension_source_1270 = (rt::json_array(&(upgrades.clone()))?);
                for target in __comprehension_source_1270.iter().cloned() {
                    __comprehension_result_1271
                        .push(!(rt::json_kind(&(target.clone())) == "string"));
                }
                __comprehension_result_1271
            })
            .into_iter()
            .any(|__value| __value))
        {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Invalid upgrade list for ".to_string(),
                    (rt::json_string(&(name))?).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        {
            let __value = rt::json_from_array({
                let mut __comprehension_result_1273: Vec<rt::Json> = Vec::new();
                let __comprehension_source_1272 = (rt::json_array(&(upgrades.clone()))?);
                for target in __comprehension_source_1272.iter().cloned() {
                    if (rt::json_kind(&(target.clone())) == "string" && {
                        let __needle = rt::json_string(&(target.clone()))?;
                        let __container = {
                            static __CONSTANT_py__openciv3__standalone__UNIT_ART:
                                std::sync::OnceLock<indexmap::IndexMap<String, String>> =
                                std::sync::OnceLock::new();
                            if __CONSTANT_py__openciv3__standalone__UNIT_ART
                                .get()
                                .is_none()
                            {
                                let __constant_value = _load_unit_art()?;
                                let _ = __CONSTANT_py__openciv3__standalone__UNIT_ART
                                    .set(__constant_value);
                            }
                            __CONSTANT_py__openciv3__standalone__UNIT_ART
                                .get()
                                .ok_or("missing module constant")?
                        };
                        __container.contains_key(&__needle)
                    }) {
                        __comprehension_result_1273.push(target.clone());
                    }
                }
                __comprehension_result_1273
            })?;
            let __key = "upgradesTo".to_string();
            prototype
                .as_object_mut()
                .ok_or("expected JSON object")?
                .insert(__key, __value);
        }
        {
            supported.push(prototype);
        };
    }
    {
        let __value = rt::json_from_array(supported)?;
        let __key = "unitPrototypes".to_string();
        result.insert(__key, __value);
    }
    Ok(result)
}

/// Load the packaged JSON rules without executing a Lua interpreter.
// Python: openciv3/standalone.py:63
pub(crate) fn load_ruleset(
    project: &str,
    mut standalone: bool,
) -> rt::Result<indexmap::IndexMap<String, rt::Json>> {
    let mut rules: indexmap::IndexMap<String, rt::Json> = crate::openciv3::json_io::read_object(
        &(rt::path_join(project, "GameModes/civ3/ruleset.json")?),
    )?;
    Ok((if standalone {
        standalone_ruleset(&rules)?
    } else {
        rules.clone()
    }))
}
