use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct Building {
    pub(crate) description: String,
    pub(crate) name: String,
    pub(crate) civilopedia_entry: String,
    pub(crate) doubles_happiness: i64,
    pub(crate) gain_in_every_city: i64,
    pub(crate) gain_in_every_city_on_continent: i64,
    pub(crate) required_building: i64,
    pub(crate) cost: i64,
    pub(crate) culture: i64,
    pub(crate) bombard_defense: i64,
    pub(crate) naval_bombard_defense: i64,
    pub(crate) defense_bonus: i64,
    pub(crate) naval_defense_bonus: i64,
    pub(crate) maintenance_cost: i64,
    pub(crate) content_faces_all_cities: i64,
    pub(crate) content_faces: i64,
    pub(crate) unhappy_faces_all_cities: i64,
    pub(crate) unhappy_faces: i64,
    pub(crate) number_of_required_buildings: i64,
    pub(crate) air_power: i64,
    pub(crate) naval_power: i64,
    pub(crate) pollution: i64,
    pub(crate) production: i64,
    pub(crate) required_government: i64,
    pub(crate) spaceship_part: i64,
    pub(crate) required_advance: i64,
    pub(crate) rendered_obsolete_by: i64,
    pub(crate) required_resource1: i64,
    pub(crate) required_resource2: i64,
    pub(crate) effects: i64,
    pub(crate) number_of_armies_required: i64,
    pub(crate) flavors: i64,
    pub(crate) unit_produced: i64,
    pub(crate) unit_frequency: i64,
    pub(crate) commerce_bonus: Option<f64>,
    pub(crate) research_bonus: Option<f64>,
    pub(crate) luxury_bonus: Option<f64>,
    pub(crate) icon_row: i64,
    pub(crate) production_requirements: Option<i64>,
    pub(crate) unit_production_effects: Option<i64>,
    pub(crate) water_yield_effects: Option<i64>,
    pub(crate) provides_walls: Option<bool>,
    pub(crate) population_cost: i64,
}

// Python: openciv3/building_rules.py:122
pub(crate) fn Building__is_wall(self_: &Building) -> rt::Result<bool> {
    Ok((if (&(self_).provides_walls).is_none() {
        ((self_).bombard_defense > 0i64)
    } else {
        ((self_).provides_walls.clone()).is_some()
    }))
}

// Python: openciv3/building_rules.py:126
pub(crate) fn Building__towns_only(self_: &Building) -> rt::Result<bool> {
    Ok((((self_).effects & 4611686018427387904i64) != 0
        || ((&(self_).provides_walls).is_none() && ((self_).bombard_defense > 0i64))))
}

// Python: openciv3/building_rules.py:131
pub(crate) fn Building__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<Building> {
    Ok(Building {
        description: crate::openciv3::binary::Record__text(record, 4i64, 64i64)?,
        name: crate::openciv3::binary::Record__text(record, 68i64, 32i64)?,
        civilopedia_entry: crate::openciv3::binary::Record__text(record, 100i64, 32i64)?,
        doubles_happiness: crate::openciv3::binary::Record__integer(record, 132i64)?,
        gain_in_every_city: crate::openciv3::binary::Record__integer(record, 136i64)?,
        gain_in_every_city_on_continent: crate::openciv3::binary::Record__integer(record, 140i64)?,
        required_building: crate::openciv3::binary::Record__integer(record, 144i64)?,
        cost: crate::openciv3::binary::Record__integer(record, 148i64)?,
        culture: crate::openciv3::binary::Record__integer(record, 152i64)?,
        bombard_defense: crate::openciv3::binary::Record__integer(record, 156i64)?,
        naval_bombard_defense: crate::openciv3::binary::Record__integer(record, 160i64)?,
        defense_bonus: crate::openciv3::binary::Record__integer(record, 164i64)?,
        naval_defense_bonus: crate::openciv3::binary::Record__integer(record, 168i64)?,
        maintenance_cost: crate::openciv3::binary::Record__integer(record, 172i64)?,
        content_faces_all_cities: crate::openciv3::binary::Record__integer(record, 176i64)?,
        content_faces: crate::openciv3::binary::Record__integer(record, 180i64)?,
        unhappy_faces_all_cities: crate::openciv3::binary::Record__integer(record, 184i64)?,
        unhappy_faces: crate::openciv3::binary::Record__integer(record, 188i64)?,
        number_of_required_buildings: crate::openciv3::binary::Record__integer(record, 192i64)?,
        air_power: crate::openciv3::binary::Record__integer(record, 196i64)?,
        naval_power: crate::openciv3::binary::Record__integer(record, 200i64)?,
        pollution: crate::openciv3::binary::Record__integer(record, 204i64)?,
        production: crate::openciv3::binary::Record__integer(record, 208i64)?,
        required_government: crate::openciv3::binary::Record__integer(record, 212i64)?,
        spaceship_part: crate::openciv3::binary::Record__integer(record, 216i64)?,
        required_advance: crate::openciv3::binary::Record__integer(record, 220i64)?,
        rendered_obsolete_by: crate::openciv3::binary::Record__integer(record, 224i64)?,
        required_resource1: crate::openciv3::binary::Record__integer(record, 228i64)?,
        required_resource2: crate::openciv3::binary::Record__integer(record, 232i64)?,
        effects: rt::int_from_bytes(
            &(crate::openciv3::binary::Record__bytes(record, 236i64, 16i64)?),
            "little",
        )?,
        number_of_armies_required: crate::openciv3::binary::Record__integer(record, 252i64)?,
        flavors: crate::openciv3::binary::Record__integer(record, 256i64)?,
        unit_produced: crate::openciv3::binary::Record__integer(record, 264i64)?,
        unit_frequency: crate::openciv3::binary::Record__integer(record, 268i64)?,
        commerce_bonus: None,
        research_bonus: None,
        luxury_bonus: None,
        icon_row: (1i64).checked_neg().ok_or("integer overflow")?,
        production_requirements: None,
        unit_production_effects: None,
        water_yield_effects: None,
        provides_walls: None,
        population_cost: 0i64,
    })
}
