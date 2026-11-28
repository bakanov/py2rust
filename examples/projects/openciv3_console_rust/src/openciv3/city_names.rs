use py2rust_service_runtime as rt;

// Python: openciv3/city_names.py:5
pub(crate) fn next_city_name(
    game: &crate::openciv3::game_state::GameState,
    mut owner: i64,
) -> rt::Result<String> {
    let mut names: Vec<String> = ({
        let __source = &(&(game).scenario).civilizations;
        let __key = owner;
        &__source[rt::index(__source.len(), __key)?]
    })
    .city_names
    .clone();
    if !(((names).len() as i64) != 0i64) {
        return Err("Civilization has no city names".to_string().into());
    }
    let mut used: std::collections::BTreeSet<String> = {
        let mut __comprehension_result_998: std::collections::BTreeSet<String> =
            std::collections::BTreeSet::new();
        let __comprehension_source_997 = ((game).cities.clone());
        for city in __comprehension_source_997.iter().cloned() {
            if ((city).owner == owner) {
                __comprehension_result_998.insert((city).name.clone());
            }
        }
        __comprehension_result_998
    };
    let mut cycle: i64 = 0i64;
    loop {
        for mut name in (names).iter() {
            let mut candidate: String = format!(
                "{}{}{}",
                (if (rt::int_modulo(cycle, 2i64)? != 0i64) {
                    "New ".to_string()
                } else {
                    String::new()
                }),
                name.to_owned(),
                (if (cycle >= 2i64) {
                    {
                        let __separator = &(String::new());
                        (&(vec![
                            " ".to_string(),
                            ((rt::int_floor_div(cycle, 2i64)?)
                                .checked_add(1i64)
                                .ok_or("integer overflow")?)
                            .to_string(),
                        ]))
                            .join(__separator)
                    }
                } else {
                    String::new()
                })
            );
            if {
                let __needle: &str = AsRef::<str>::as_ref(&candidate);
                let __container = &used;
                !__container.contains(__needle)
            } {
                return Ok(candidate);
            }
        }
        cycle = (cycle).checked_add(1i64).ok_or("integer overflow")?;
    }
}
