use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct Resident {
    pub(crate) citizen_type: i64,
    pub(crate) nationality: i64,
    pub(crate) city: i64,
    pub(crate) tile_worked: Option<(i64, i64)>,
    pub(crate) mood: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct CityBuilding {
    pub(crate) building: i64,
    pub(crate) built_by: i64,
    pub(crate) year: i64,
    pub(crate) total_culture: i64,
}

#[derive(Clone, PartialEq)]
pub(crate) struct City {
    pub(crate) id: i64,
    pub(crate) owner: i64,
    pub(crate) name: String,
    pub(crate) x: i64,
    pub(crate) y: i64,
    pub(crate) capital: bool,
    pub(crate) walls: bool,
    pub(crate) level: i64,
    pub(crate) border_level: i64,
    pub(crate) auto_name: bool,
    pub(crate) producing_unit: Option<i64>,
    pub(crate) residents: Vec<Resident>,
    pub(crate) buildings: Vec<CityBuilding>,
    pub(crate) culture: indexmap::IndexMap<i64, i64>,
    pub(crate) food_stored: i64,
    pub(crate) shields_stored: i64,
    pub(crate) pop_rush_unhappiness_turns: i64,
    pub(crate) disorder: bool,
    pub(crate) producing_inflow: Option<crate::openciv3::inflows::Inflow>,
    pub(crate) producing_building: Option<i64>,
}

// Python: openciv3/cities.py:57
pub(crate) fn City__select_unit(mut self_: City, mut unit: i64) -> rt::Result<()> {
    self_.producing_unit = Some(unit);
    self_.producing_building = None;
    self_.producing_inflow = None;
    Ok(())
}

// Python: openciv3/cities.py:62
pub(crate) fn City__select_building(mut self_: City, mut building: i64) -> rt::Result<()> {
    self_.producing_unit = None;
    self_.producing_building = Some(building);
    self_.producing_inflow = None;
    Ok(())
}

// Python: openciv3/cities.py:67
pub(crate) fn City__select_inflow(
    mut self_: City,
    inflow: &Option<crate::openciv3::inflows::Inflow>,
) -> rt::Result<()> {
    self_.producing_unit = None;
    self_.producing_building = None;
    self_.producing_inflow = (*inflow).clone();
    Ok(())
}

// Python: openciv3/cities.py:72
pub(crate) fn City__validate_production(
    self_: &City,
    mut unit_count: i64,
    mut building_count: i64,
) -> rt::Result<()> {
    if (((&(self_).producing_unit).is_some() && (&(self_).producing_building).is_some())
        || (((&(self_).producing_unit).is_some() && (&(self_).producing_inflow).is_some())
            || ((&(self_).producing_building).is_some() && (&(self_).producing_inflow).is_some())))
    {
        return Err("City cannot produce multiple targets simultaneously"
            .to_string()
            .into());
    }
    if ((&(self_).producing_unit).is_some()
        && !({
            let __compare_0 = 0i64;
            let __compare_1 = (self_).producing_unit.clone();
            if (__compare_0 <= (*(__compare_1).as_ref().ok_or("expected a value")?).clone()) {
                let __compare_2 = unit_count;
                ((*(__compare_1).as_ref().ok_or("expected a value")?).clone() < __compare_2)
            } else {
                false
            }
        }))
    {
        return Err("Invalid production unit index".to_string().into());
    }
    if ((&(self_).producing_building).is_some()
        && !({
            let __compare_0 = 0i64;
            let __compare_1 = (self_).producing_building.clone();
            if (__compare_0 <= (*(__compare_1).as_ref().ok_or("expected a value")?).clone()) {
                let __compare_2 = building_count;
                ((*(__compare_1).as_ref().ok_or("expected a value")?).clone() < __compare_2)
            } else {
                false
            }
        }))
    {
        return Err("Invalid production building index".to_string().into());
    }
    Ok(())
}

// Python: openciv3/cities.py:83
pub(crate) fn City__size(self_: &City) -> rt::Result<i64> {
    Ok(((&(self_).residents).len() as i64))
}

// Python: openciv3/cities.py:87
pub(crate) fn initialize_cities(
    definition: &crate::openciv3::scenario_model::ScenarioDefinition,
) -> rt::Result<Vec<City>> {
    let mut world: Option<crate::openciv3::world::WorldMap> = (definition).world.clone();
    if (world).is_none() {
        return Err("Generate a map before initializing cities"
            .to_string()
            .into());
    }
    if !(((((*(world.clone()).as_ref().ok_or("expected a value")?).clone())
        .cities
        .clone())
    .len() as i64)
        != 0i64)
    {
        return Ok(vec![]);
    }
    let mut rules: crate::openciv3::rules::RuleCatalog = (definition).rules.clone();
    if (((&(rules).global_rules).len() as i64) != 1i64) {
        return Err("City initialization needs one global rules record"
            .to_string()
            .into());
    }
    let mut default_citizen: Option<i64> = {
        let __find_source_110 = ((rules).citizens.clone())
            .into_iter()
            .enumerate()
            .map(|(__index, __value)| (__index as i64 + 0i64, __value))
            .collect::<Vec<_>>();
        let mut __find_result_110: Option<i64> = None;
        for (i, citizen) in __find_source_110.iter().cloned() {
            if (citizen).default_citizen {
                __find_result_110 = Some(i);
                break;
            }
        }
        __find_result_110
    };
    if (default_citizen).is_none() {
        return Err("City initialization needs a default citizen type"
            .to_string()
            .into());
    }
    let mut production: i64 = ({
        let __source = &(rules).global_rules;
        let __key = 0i64;
        &__source[rt::index(__source.len(), __key)?]
    })
    .start_unit_type2;
    if (production >= ((&(rules).units).len() as i64)) {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Invalid initial city production unit: ".to_string(),
                (production).to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    let mut cities: Vec<City> = vec![];
    let mut occupied: std::collections::BTreeSet<(i64, i64)> = std::collections::BTreeSet::new();
    for mut for_target_104_4 in (((*(world.clone()).as_ref().ok_or("expected a value")?).clone())
        .cities
        .clone())
    .into_iter()
    .enumerate()
    .map(|(__index, __value)| (__index as i64 + 0i64, __value))
    .collect::<Vec<_>>()
    {
        let (mut index, mut placed): (i64, crate::openciv3::world::PlacedCity) = for_target_104_4;
        let mut owner: Option<i64> = crate::openciv3::world::resolve_owner(
            (placed).owner_kind,
            (placed).owner,
            &((definition).assigned_civilizations.clone()),
            ((&(definition).civilizations).len() as i64),
        )?;
        if (owner).is_none() {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "CITY[".to_string(),
                    (index).to_string(),
                    "] has no owner".to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        let mut tile: Option<crate::openciv3::world::Tile> =
            crate::openciv3::world::WorldMap__tile_at(
                &((*(world.clone()).as_ref().ok_or("expected a value")?).clone()),
                (placed).x,
                (placed).y,
            )?;
        if (tile).is_none() {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "CITY[".to_string(),
                    (index).to_string(),
                    "] is outside the map".to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        if {
            let __needle = (
                ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
            );
            let __container = &occupied;
            __container.contains(&__needle)
        } {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "CITY[".to_string(),
                    (index).to_string(),
                    "] overlaps another city".to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        {
            occupied.insert((
                ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
                ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
            ));
        };
        if ((placed).size < 0i64) {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "CITY[".to_string(),
                    (index).to_string(),
                    "] has negative population".to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        if ({
            let mut __comprehension_result_112: Vec<bool> = Vec::new();
            let __comprehension_source_111 = ((placed).buildings.clone());
            for building in __comprehension_source_111.iter().cloned() {
                __comprehension_result_112.push(
                    !({
                        let __compare_0 = 0i64;
                        let __compare_1 = building;
                        if (__compare_0 <= __compare_1) {
                            let __compare_2 = ((&(rules).buildings).len() as i64);
                            (__compare_1 < __compare_2)
                        } else {
                            false
                        }
                    }),
                );
            }
            __comprehension_result_112
        })
        .into_iter()
        .any(|__value| __value)
        {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "CITY[".to_string(),
                    (index).to_string(),
                    "] has an invalid building".to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        let mut city: City = City {
            id: index,
            owner: (*(owner.clone()).as_ref().ok_or("expected a value")?).clone(),
            name: (placed).name.clone(),
            x: ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).x,
            y: ((*(tile.clone()).as_ref().ok_or("expected a value")?).clone()).y,
            capital: (placed).palace,
            walls: (placed).walls,
            level: (placed).level,
            border_level: (placed).border_level,
            auto_name: (placed).auto_name,
            producing_unit: (if (production >= 0i64) {
                Some(production)
            } else {
                None
            }),
            residents: {
                let mut __comprehension_result_114: Vec<Resident> = Vec::new();
                let __comprehension_source_113 = ((0i64..(placed).size).collect::<Vec<i64>>());
                for _ in __comprehension_source_113.iter().cloned() {
                    __comprehension_result_114.push(Resident {
                        citizen_type: (*(default_citizen.clone())
                            .as_ref()
                            .ok_or("expected a value")?)
                        .clone(),
                        nationality: (*(owner.clone()).as_ref().ok_or("expected a value")?).clone(),
                        city: index,
                        tile_worked: None,
                        mood: 0i64,
                    });
                }
                __comprehension_result_114
            },
            buildings: {
                let mut __comprehension_result_116: Vec<CityBuilding> = Vec::new();
                let __comprehension_source_115 = ((placed).buildings.clone());
                for building in __comprehension_source_115.iter().cloned() {
                    __comprehension_result_116.push(CityBuilding {
                        building: building,
                        built_by: (*(owner.clone()).as_ref().ok_or("expected a value")?).clone(),
                        year: 0i64,
                        total_culture: 0i64,
                    });
                }
                __comprehension_result_116
            },
            culture: [(
                (*(owner.clone()).as_ref().ok_or("expected a value")?).clone(),
                (placed).culture,
            )]
            .into_iter()
            .collect::<indexmap::IndexMap<_, _>>(),
            food_stored: 0i64,
            shields_stored: 0i64,
            pop_rush_unhappiness_turns: 0i64,
            disorder: false,
            producing_inflow: None,
            producing_building: None,
        };
        {
            cities.push(city);
        };
    }
    Ok(cities)
}

// Python: openciv3/cities.py:131
pub(crate) fn built_great_wonders(
    cities: &[City],
    definition: &crate::openciv3::scenario_model::ScenarioDefinition,
) -> rt::Result<std::collections::BTreeSet<i64>> {
    Ok({
        let mut __comprehension_result_119: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        let __comprehension_source_117 = (cities.to_vec());
        for city in __comprehension_source_117.iter().cloned() {
            let __comprehension_source_118 = ((city).buildings.clone());
            for constructed in __comprehension_source_118.iter().cloned() {
                if ((({
                    let __source = &(&(definition).rules).buildings;
                    let __key = (constructed).building;
                    &__source[rt::index(__source.len(), __key)?]
                })
                .effects
                    & 268435456i64)
                    != 0i64)
                {
                    __comprehension_result_119.insert((constructed).building);
                }
            }
        }
        __comprehension_result_119
    })
}
