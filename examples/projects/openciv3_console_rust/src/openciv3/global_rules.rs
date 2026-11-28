use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct HealingRates {
    pub(crate) friendly: i64,
    pub(crate) neutral: i64,
    pub(crate) hostile: i64,
    pub(crate) city: i64,
}

#[derive(Clone, PartialEq)]
pub(crate) struct GlobalRules {
    pub(crate) city_size_names: (String, String, String),
    pub(crate) spaceship_parts: Vec<i64>,
    pub(crate) advanced_barbarian_unit_type: i64,
    pub(crate) basic_barbarian_unit_type: i64,
    pub(crate) barbarian_sea_unit_type: i64,
    pub(crate) cities_needed_to_support_an_army: i64,
    pub(crate) chance_of_rioting: i64,
    pub(crate) turn_penalty_for_each_drafted_citizen: i64,
    pub(crate) shields_cost_per_gold: i64,
    pub(crate) fortress_defensive_bonus: i64,
    pub(crate) citizens_affected_by_each_happy_face: i64,
    pub(crate) forest_value_in_shields: i64,
    pub(crate) shield_value_in_gold: i64,
    pub(crate) citizen_value_in_shields: i64,
    pub(crate) default_difficulty_level: i64,
    pub(crate) battle_created_unit: i64,
    pub(crate) build_army_unit: i64,
    pub(crate) building_defensive_bonus: i64,
    pub(crate) citizen_defensive_bonus: i64,
    pub(crate) default_money_resource: i64,
    pub(crate) chance_to_intercept_enemy_air_missions: i64,
    pub(crate) chance_to_intercept_enemy_stealth_missions: i64,
    pub(crate) starting_treasury: i64,
    pub(crate) food_consumption_per_citizen: i64,
    pub(crate) river_defensive_bonus: i64,
    pub(crate) turn_penalty_for_each_hurry_sacrifice: i64,
    pub(crate) scout: i64,
    pub(crate) slave: i64,
    pub(crate) movement_along_roads: i64,
    pub(crate) start_unit_type1: i64,
    pub(crate) start_unit_type2: i64,
    pub(crate) minimum_population_for_we_love_the_king: i64,
    pub(crate) town_defense_bonus: i64,
    pub(crate) city_defense_bonus: i64,
    pub(crate) metropolis_defense_bonus: i64,
    pub(crate) maximum_level1_city_size: i64,
    pub(crate) maximum_level2_city_size: i64,
    pub(crate) fortifications_defensive_bonus: i64,
    pub(crate) culture_levels: Vec<String>,
    pub(crate) border_expansion_multiplier: i64,
    pub(crate) border_factor: i64,
    pub(crate) future_tech_cost: i64,
    pub(crate) golden_age_duration: i64,
    pub(crate) maximum_research_time: i64,
    pub(crate) minimum_research_time: i64,
    pub(crate) flag_unit_type: i64,
    pub(crate) upgrade_cost: i64,
    pub(crate) barbarian_camp_gold: i64,
    pub(crate) radar_tile_visibility: i64,
    pub(crate) shield_rate_for_disbanding: f64,
    pub(crate) allow_lesser_unit_production: bool,
    pub(crate) food_boxes: (i64, i64, i64),
    pub(crate) treasury_interest_rate: f64,
    pub(crate) max_interest: i64,
    pub(crate) capital_neighbor_distance: i64,
    pub(crate) building_discount_for_civ_traits: f64,
    pub(crate) max_rank_of_workable_tiles: i64,
    pub(crate) max_rank_of_barbarian_camp_tiles: i64,
    pub(crate) default_deal_duration: i64,
    pub(crate) barbarian_spawn_hit_points: i64,
    pub(crate) default_unit_experience: i64,
    pub(crate) healing_rates: HealingRates,
    pub(crate) road_movement_cost: f64,
    pub(crate) railroad_movement_cost: f64,
    pub(crate) railroad_development_bonus: bool,
    pub(crate) fortress_defense: f64,
    pub(crate) barricade_defense: f64,
    pub(crate) extra_improvement_defenses: Vec<(i64, String, f64)>,
    pub(crate) wealth: crate::openciv3::inflows::WealthRule,
    pub(crate) improvement_draw_order: Vec<(String, i64)>,
}

// Python: openciv3/global_rules.py:18
pub(crate) fn HealingRates____post_init__(self_: &HealingRates) -> rt::Result<HealingRates> {
    if (((((self_).friendly).min((self_).neutral)).min((self_).hostile)).min((self_).city) < 0i64) {
        return Err("Healing rates cannot be negative".to_string().into());
    }
    Ok((*self_).clone())
}

// Python: openciv3/global_rules.py:96
pub(crate) fn GlobalRules____post_init__(self_: &GlobalRules) -> rt::Result<GlobalRules> {
    if ((self_).food_consumption_per_citizen < 0i64) {
        return Err("Food consumption per citizen cannot be negative"
            .to_string()
            .into());
    }
    Ok((*self_).clone())
}

// Python: openciv3/global_rules.py:101
pub(crate) fn GlobalRules__from_record(
    record: &crate::openciv3::binary::Record,
) -> rt::Result<GlobalRules> {
    let mut parts: i64 = crate::openciv3::binary::Record__count(record, 100i64, 4i64)?;
    let mut middle: i64 = (104i64)
        .checked_add((parts).checked_mul(4i64).ok_or("integer overflow")?)
        .ok_or("integer overflow")?;
    let mut levels: i64 = crate::openciv3::binary::Record__count(
        record,
        (middle).checked_add(160i64).ok_or("integer overflow")?,
        64i64,
    )?;
    let mut tail: i64 = ((middle).checked_add(164i64).ok_or("integer overflow")?)
        .checked_add((levels).checked_mul(64i64).ok_or("integer overflow")?)
        .ok_or("integer overflow")?;
    let mut road_rate: i64 = crate::openciv3::binary::Record__integer(
        record,
        (middle).checked_add(116i64).ok_or("integer overflow")?,
    )?;
    Ok(GlobalRules____post_init__(
        &(GlobalRules {
            city_size_names: (
                crate::openciv3::binary::Record__text(record, 4i64, 32i64)?,
                crate::openciv3::binary::Record__text(record, 36i64, 32i64)?,
                crate::openciv3::binary::Record__text(record, 68i64, 32i64)?,
            ),
            spaceship_parts: ({
                let mut __comprehension_result_258: Vec<i64> = Vec::new();
                let __comprehension_source_257 = ((0i64..parts).collect::<Vec<i64>>());
                for i in __comprehension_source_257.iter().cloned() {
                    __comprehension_result_258.push(crate::openciv3::binary::Record__integer(
                        record,
                        (104i64)
                            .checked_add((i).checked_mul(4i64).ok_or("integer overflow")?)
                            .ok_or("integer overflow")?,
                    )?);
                }
                __comprehension_result_258
            })
            .iter()
            .cloned()
            .collect::<Vec<_>>(),
            advanced_barbarian_unit_type: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(0i64).ok_or("integer overflow")?,
            )?,
            basic_barbarian_unit_type: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(4i64).ok_or("integer overflow")?,
            )?,
            barbarian_sea_unit_type: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(8i64).ok_or("integer overflow")?,
            )?,
            cities_needed_to_support_an_army: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(12i64).ok_or("integer overflow")?,
            )?,
            chance_of_rioting: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(16i64).ok_or("integer overflow")?,
            )?,
            turn_penalty_for_each_drafted_citizen: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(20i64).ok_or("integer overflow")?,
            )?,
            shields_cost_per_gold: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(24i64).ok_or("integer overflow")?,
            )?,
            fortress_defensive_bonus: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(28i64).ok_or("integer overflow")?,
            )?,
            citizens_affected_by_each_happy_face: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(32i64).ok_or("integer overflow")?,
            )?,
            forest_value_in_shields: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(44i64).ok_or("integer overflow")?,
            )?,
            shield_value_in_gold: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(48i64).ok_or("integer overflow")?,
            )?,
            citizen_value_in_shields: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(52i64).ok_or("integer overflow")?,
            )?,
            default_difficulty_level: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(56i64).ok_or("integer overflow")?,
            )?,
            battle_created_unit: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(60i64).ok_or("integer overflow")?,
            )?,
            build_army_unit: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(64i64).ok_or("integer overflow")?,
            )?,
            building_defensive_bonus: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(68i64).ok_or("integer overflow")?,
            )?,
            citizen_defensive_bonus: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(72i64).ok_or("integer overflow")?,
            )?,
            default_money_resource: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(76i64).ok_or("integer overflow")?,
            )?,
            chance_to_intercept_enemy_air_missions: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(80i64).ok_or("integer overflow")?,
            )?,
            chance_to_intercept_enemy_stealth_missions: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(84i64).ok_or("integer overflow")?,
            )?,
            starting_treasury: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(88i64).ok_or("integer overflow")?,
            )?,
            food_consumption_per_citizen: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(96i64).ok_or("integer overflow")?,
            )?,
            river_defensive_bonus: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(100i64).ok_or("integer overflow")?,
            )?,
            turn_penalty_for_each_hurry_sacrifice: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(104i64).ok_or("integer overflow")?,
            )?,
            scout: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(108i64).ok_or("integer overflow")?,
            )?,
            slave: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(112i64).ok_or("integer overflow")?,
            )?,
            movement_along_roads: road_rate,
            road_movement_cost: rt::int_true_div(
                1i64,
                (if (road_rate > 0i64) { road_rate } else { 3i64 }),
            )?,
            start_unit_type1: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(120i64).ok_or("integer overflow")?,
            )?,
            start_unit_type2: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(124i64).ok_or("integer overflow")?,
            )?,
            minimum_population_for_we_love_the_king: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(128i64).ok_or("integer overflow")?,
            )?,
            town_defense_bonus: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(132i64).ok_or("integer overflow")?,
            )?,
            city_defense_bonus: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(136i64).ok_or("integer overflow")?,
            )?,
            metropolis_defense_bonus: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(140i64).ok_or("integer overflow")?,
            )?,
            maximum_level1_city_size: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(144i64).ok_or("integer overflow")?,
            )?,
            maximum_level2_city_size: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(148i64).ok_or("integer overflow")?,
            )?,
            fortifications_defensive_bonus: crate::openciv3::binary::Record__integer(
                record,
                (middle).checked_add(156i64).ok_or("integer overflow")?,
            )?,
            culture_levels: ({
                let mut __comprehension_result_260: Vec<String> = Vec::new();
                let __comprehension_source_259 = ((0i64..levels).collect::<Vec<i64>>());
                for i in __comprehension_source_259.iter().cloned() {
                    __comprehension_result_260.push(crate::openciv3::binary::Record__text(
                        record,
                        ((middle).checked_add(164i64).ok_or("integer overflow")?)
                            .checked_add((i).checked_mul(64i64).ok_or("integer overflow")?)
                            .ok_or("integer overflow")?,
                        64i64,
                    )?);
                }
                __comprehension_result_260
            })
            .iter()
            .cloned()
            .collect::<Vec<_>>(),
            border_expansion_multiplier: crate::openciv3::binary::Record__integer(
                record,
                (tail).checked_add(0i64).ok_or("integer overflow")?,
            )?,
            border_factor: crate::openciv3::binary::Record__integer(
                record,
                (tail).checked_add(4i64).ok_or("integer overflow")?,
            )?,
            future_tech_cost: crate::openciv3::binary::Record__integer(
                record,
                (tail).checked_add(8i64).ok_or("integer overflow")?,
            )?,
            golden_age_duration: crate::openciv3::binary::Record__integer(
                record,
                (tail).checked_add(12i64).ok_or("integer overflow")?,
            )?,
            maximum_research_time: crate::openciv3::binary::Record__integer(
                record,
                (tail).checked_add(16i64).ok_or("integer overflow")?,
            )?,
            minimum_research_time: crate::openciv3::binary::Record__integer(
                record,
                (tail).checked_add(20i64).ok_or("integer overflow")?,
            )?,
            flag_unit_type: crate::openciv3::binary::Record__integer(
                record,
                (tail).checked_add(24i64).ok_or("integer overflow")?,
            )?,
            upgrade_cost: crate::openciv3::binary::Record__integer(
                record,
                (tail).checked_add(28i64).ok_or("integer overflow")?,
            )?,
            barbarian_camp_gold: 25i64,
            radar_tile_visibility: 2i64,
            shield_rate_for_disbanding: 0.25f64,
            allow_lesser_unit_production: false,
            food_boxes: (20i64, 40i64, 60i64),
            treasury_interest_rate: 0.05f64,
            max_interest: 50i64,
            capital_neighbor_distance: 8i64,
            building_discount_for_civ_traits: 0.5f64,
            max_rank_of_workable_tiles: 2i64,
            max_rank_of_barbarian_camp_tiles: 2i64,
            default_deal_duration: 20i64,
            barbarian_spawn_hit_points: 2i64,
            default_unit_experience: 1i64,
            healing_rates: HealingRates {
                friendly: 1i64,
                neutral: 1i64,
                hostile: 0i64,
                city: 2i64,
            },
            railroad_movement_cost: 0.0f64,
            railroad_development_bonus: true,
            fortress_defense: 0.5f64,
            barricade_defense: 1.0f64,
            extra_improvement_defenses: vec![],
            wealth: crate::openciv3::inflows::WealthRule::COMMERCE,
            improvement_draw_order: vec![],
        }),
    )?)
}
