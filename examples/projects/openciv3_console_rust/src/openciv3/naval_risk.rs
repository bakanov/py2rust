use py2rust_service_runtime as rt;

// Python: openciv3/naval_risk.py:10
pub(crate) fn safe_sea_travel(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<bool> {
    let mut rules: crate::openciv3::rules::RuleCatalog = (&(game).scenario).rules.clone();
    let mut known: std::collections::BTreeSet<i64> = ({
        let __source = &(game).players;
        let __key = owner;
        &__source[rt::index(__source.len(), __key)?]
    })
    .known_technologies
    .clone();
    Ok(({
        let mut __comprehension_result_780: Vec<bool> = Vec::new();
        let __comprehension_source_778 = ((game).cities.clone());
        for city in __comprehension_source_778.iter().cloned() {
            if ((city).owner == owner) {
                let __comprehension_source_779 = ((city).buildings.clone());
                for building in __comprehension_source_779.iter().cloned() {
                    __comprehension_result_780.push(
                        ((({
                            let __source = &(rules).buildings;
                            let __key = (building).building;
                            &__source[rt::index(__source.len(), __key)?]
                        })
                        .effects
                            & 562949953421312i64)
                            != 0
                            && {
                                let __needle = ({
                                    let __source = &(rules).buildings;
                                    let __key = (building).building;
                                    &__source[rt::index(__source.len(), __key)?]
                                })
                                .rendered_obsolete_by;
                                let __container = &known;
                                !__container.contains(&__needle)
                            }),
                    );
                }
            }
        }
        __comprehension_result_780
    })
    .into_iter()
    .any(|__value| __value))
}

// Python: openciv3/naval_risk.py:20
pub(crate) fn hazardous_waters(
    kind: &crate::openciv3::unit_rules::UnitPrototype,
    tile: &crate::openciv3::world::Tile,
    mut safe_sea: bool,
) -> rt::Result<bool> {
    if ((kind).domain != 1i64) {
        return Ok(false);
    }
    if ((tile).base_terrain == 12i64) {
        return Ok((!(safe_sea) && ((kind).abilities & 2048i64) != 0));
    }
    Ok((((tile).base_terrain == 13i64) && ((kind).abilities & 4096i64) != 0))
}
