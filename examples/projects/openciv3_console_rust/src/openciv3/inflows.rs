use py2rust_service_runtime as rt;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum Inflow {
    WEALTH,
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, serde::Serialize)]
pub(crate) enum WealthRule {
    UNAVAILABLE,
    NO_YIELD,
    COMMERCE,
}

// Python: openciv3/inflows.py:10
pub(crate) fn Inflow__from_legacy_name(name: &str) -> rt::Result<Inflow> {
    if {
        let __needle = rt::casefold(name);
        let __container = &({
            let __tuple_value = &(("wealth".to_string(), "благосостояние".to_string()));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        __container.contains(&__needle)
    } {
        return Ok(Inflow::WEALTH);
    }
    return Err({
        let __separator = &(String::new());
        (&(vec![
            "Unsupported production inflow: ".to_string(),
            rt::repr_text(&(name.to_owned())),
        ]))
            .join(__separator)
    }
    .into());
}

// Python: openciv3/inflows.py:22
pub(crate) fn wealth_commerce(
    mut useful_shields: i64,
    mut shields_per_gold: i64,
    mut doubled: bool,
) -> rt::Result<i64> {
    if ((useful_shields < 0i64) || (shields_per_gold <= 0i64)) {
        return Err(
            "Wealth requires nonnegative shields and a positive conversion ratio"
                .to_string()
                .into(),
        );
    }
    rt::round_float(
        (1.0f64).max(rt::int_true_div(
            (useful_shields)
                .checked_mul((if doubled { 2i64 } else { 1i64 }))
                .ok_or("integer overflow")?,
            shields_per_gold,
        )?),
    )
}
