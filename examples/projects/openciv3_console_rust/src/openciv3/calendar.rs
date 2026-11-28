use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct CalendarDate {
    pub(crate) year: i64,
    pub(crate) month: i64,
    pub(crate) week: i64,
    pub(crate) day: i64,
    pub(crate) hour: i64,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub(crate) struct Calendar {
    pub(crate) unit: i64,
    pub(crate) start_year: i64,
    pub(crate) start_month: i64,
    pub(crate) start_week: i64,
    pub(crate) start_day: i64,
    pub(crate) start_hour: i64,
    pub(crate) scale: Vec<(i64, i64)>,
    pub(crate) negative_label: String,
    pub(crate) positive_label: String,
}

// Python: openciv3/calendar.py:41
pub(crate) fn Calendar____post_init__(self_: &Calendar) -> rt::Result<Calendar> {
    if ({
        let mut __comprehension_result_189: Vec<bool> = Vec::new();
        let __comprehension_source_188 = ((self_).scale.clone());
        for (turns, step) in __comprehension_source_188.iter().cloned() {
            __comprehension_result_189.push(((turns < 0i64) || (step < 0i64)));
        }
        __comprehension_result_189
    })
    .into_iter()
    .any(|__value| __value)
    {
        return Err(
            "Calendar scale cannot contain negative durations or increments"
                .to_string()
                .into(),
        );
    }
    if (((self_).unit == 1i64)
        && !({
            let __compare_0 = 1i64;
            let __compare_1 = (self_).start_month;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = 12i64;
                (__compare_1 <= __compare_2)
            } else {
                false
            }
        }))
    {
        return Err("Start month must be 1–12".to_string().into());
    }
    if (((self_).unit == 2i64)
        && !({
            let __compare_0 = 1i64;
            let __compare_1 = (self_).start_week;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = 52i64;
                (__compare_1 <= __compare_2)
            } else {
                false
            }
        }))
    {
        return Err("Start week must be 1–52".to_string().into());
    }
    if ({
        let __needle = (self_).unit;
        let __container = &({
            let __tuple_value = &((3i64, 4i64));
            vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
        });
        __container.contains(&__needle)
    } && !({
        let __compare_0 = 1i64;
        let __compare_1 = (self_).start_day;
        if (__compare_0 <= __compare_1) {
            let __compare_2 = 365i64;
            (__compare_1 <= __compare_2)
        } else {
            false
        }
    })) {
        return Err("Start day must be 1–365".to_string().into());
    }
    if (((self_).unit == 4i64)
        && !({
            let __compare_0 = 0i64;
            let __compare_1 = (self_).start_hour;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = 24i64;
                (__compare_1 < __compare_2)
            } else {
                false
            }
        }))
    {
        return Err("Start hour must be 0–23".to_string().into());
    }
    Ok((*self_).clone())
}

// Python: openciv3/calendar.py:54
pub(crate) fn Calendar__start(self_: &Calendar) -> rt::Result<i64> {
    Ok(rt::at(
        &({
            let __tuple_value = &((
                (self_).start_year,
                (self_).start_month,
                (self_).start_week,
                (self_).start_day,
                (self_).start_hour,
            ));
            vec![
                __tuple_value.0.clone(),
                __tuple_value.1.clone(),
                __tuple_value.2.clone(),
                __tuple_value.3.clone(),
                __tuple_value.4.clone(),
            ]
        }),
        (self_).unit,
    )?)
}

// Python: openciv3/calendar.py:57
pub(crate) fn Calendar__raw(self_: &Calendar, mut turn: i64) -> rt::Result<i64> {
    if (turn < 0i64) {
        return Err("Turn cannot be negative".to_string().into());
    }
    let mut elapsed: i64 = Calendar__start(self_)?;
    for mut for_target_61_8 in (&(self_).scale).iter() {
        let (mut duration, mut increment): (i64, i64) = (*for_target_61_8).clone();
        let mut used: i64 = (turn).min(duration);
        elapsed = (elapsed)
            .checked_add((used).checked_mul(increment).ok_or("integer overflow")?)
            .ok_or("integer overflow")?;
        turn = (turn).checked_sub(used).ok_or("integer overflow")?;
        if (turn == 0i64) {
            return Ok(elapsed);
        }
    }
    Ok((elapsed).checked_add(turn).ok_or("integer overflow")?)
}

// Python: openciv3/calendar.py:70
pub(crate) fn Calendar__turn_from_raw(self_: &Calendar, mut value: i64) -> rt::Result<i64> {
    let (mut current, mut turn): (i64, i64) = (Calendar__start(self_)?, 0i64);
    if (value < current) {
        return Err("Date precedes the scenario start".to_string().into());
    }
    for mut for_target_74_8 in (&(self_).scale).iter() {
        let (mut duration, mut increment): (i64, i64) = (*for_target_74_8).clone();
        if (value == current) {
            return Ok(turn);
        }
        let mut end: i64 = (current)
            .checked_add(
                (duration)
                    .checked_mul(increment)
                    .ok_or("integer overflow")?,
            )
            .ok_or("integer overflow")?;
        if ((increment > 0i64) && {
            let __compare_0 = current;
            let __compare_1 = value;
            if (__compare_0 < __compare_1) {
                let __compare_2 = end;
                (__compare_1 <= __compare_2)
            } else {
                false
            }
        }) {
            let (mut steps, mut remainder): (i64, i64) = rt::divmod_int(
                (value).checked_sub(current).ok_or("integer overflow")?,
                increment,
            )?;
            if (remainder != 0i64) {
                return Err("Date does not fall on a turn boundary".to_string().into());
            }
            return Ok((turn).checked_add(steps).ok_or("integer overflow")?);
        }
        (current, turn) = (end, (turn).checked_add(duration).ok_or("integer overflow")?);
    }
    Ok(((turn).checked_add(value).ok_or("integer overflow")?)
        .checked_sub(current)
        .ok_or("integer overflow")?)
}

// Python: openciv3/calendar.py:86
pub(crate) fn Calendar__date(self_: &Calendar, mut turn: i64) -> rt::Result<CalendarDate> {
    let mut value: i64 = Calendar__raw(self_, turn)?;
    if ((self_).unit == 0i64) {
        return Ok(CalendarDate {
            year: value,
            month: 1i64,
            week: 1i64,
            day: 1i64,
            hour: 12i64,
        });
    }
    if ((self_).unit == 1i64) {
        let (mut years, mut month): (i64, i64) =
            rt::divmod_int((value).checked_sub(1i64).ok_or("integer overflow")?, 12i64)?;
        return Ok(CalendarDate {
            year: ((self_).start_year)
                .checked_add(years)
                .ok_or("integer overflow")?,
            month: (month).checked_add(1i64).ok_or("integer overflow")?,
            week: 1i64,
            day: 1i64,
            hour: 12i64,
        });
    }
    if ((self_).unit == 2i64) {
        let (mut years, mut week): (i64, i64) =
            rt::divmod_int((value).checked_sub(1i64).ok_or("integer overflow")?, 52i64)?;
        return Ok(CalendarDate {
            year: ((self_).start_year)
                .checked_add(years)
                .ok_or("integer overflow")?,
            week: (week).checked_add(1i64).ok_or("integer overflow")?,
            month: 1i64,
            day: 1i64,
            hour: 12i64,
        });
    }
    if ((self_).unit == 3i64) {
        let (mut years, mut day): (i64, i64) =
            rt::divmod_int((value).checked_sub(1i64).ok_or("integer overflow")?, 365i64)?;
        return Ok(CalendarDate {
            year: ((self_).start_year)
                .checked_add(years)
                .ok_or("integer overflow")?,
            day: (day).checked_add(1i64).ok_or("integer overflow")?,
            month: 1i64,
            week: 1i64,
            hour: 12i64,
        });
    }
    let (mut days, mut hour): (i64, i64) = rt::divmod_int(value, 24i64)?;
    let (mut years, mut day): (i64, i64) = rt::divmod_int(
        (((self_).start_day)
            .checked_sub(1i64)
            .ok_or("integer overflow")?)
        .checked_add(days)
        .ok_or("integer overflow")?,
        365i64,
    )?;
    Ok(CalendarDate {
        year: ((self_).start_year)
            .checked_add(years)
            .ok_or("integer overflow")?,
        day: (day).checked_add(1i64).ok_or("integer overflow")?,
        hour: hour,
        month: 1i64,
        week: 1i64,
    })
}

// Python: openciv3/calendar.py:103
pub(crate) fn Calendar__display(self_: &Calendar, mut turn: i64) -> rt::Result<String> {
    let mut date: CalendarDate = Calendar__date(self_, turn)?;
    let mut year: String = {
        let __separator = &(String::new());
        (&(vec![
            (((date).year).checked_abs().ok_or("integer overflow")?).to_string(),
            " ".to_string(),
            (if ((date).year < 0i64) {
                (self_).negative_label.clone()
            } else {
                (self_).positive_label.clone()
            })
            .to_string(),
        ]))
            .join(__separator)
    };
    if ((self_).unit == 0i64) {
        return Ok(year);
    }
    if ((self_).unit == 1i64) {
        return Ok({
            let __separator = &(String::new());
            (&(vec![
                (rt::at(
                    &({
                        let __tuple_value = {
                            static __CONSTANT_py__openciv3__calendar__MONTHS: std::sync::OnceLock<
                                (
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
                                ),
                            > = std::sync::OnceLock::new();
                            if __CONSTANT_py__openciv3__calendar__MONTHS.get().is_none() {
                                let __constant_value = (
                                    "Jan".to_string(),
                                    "Feb".to_string(),
                                    "Mar".to_string(),
                                    "Apr".to_string(),
                                    "May".to_string(),
                                    "Jun".to_string(),
                                    "Jul".to_string(),
                                    "Aug".to_string(),
                                    "Sep".to_string(),
                                    "Oct".to_string(),
                                    "Nov".to_string(),
                                    "Dec".to_string(),
                                );
                                let _ =
                                    __CONSTANT_py__openciv3__calendar__MONTHS.set(__constant_value);
                            }
                            __CONSTANT_py__openciv3__calendar__MONTHS
                                .get()
                                .ok_or("missing module constant")?
                        };
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
                        ]
                    }),
                    ((date).month).checked_sub(1i64).ok_or("integer overflow")?,
                )?)
                .to_string(),
                ", ".to_string(),
                (year).to_string(),
            ]))
                .join(__separator)
        });
    }
    if ((self_).unit == 2i64) {
        return Ok({
            let __separator = &(String::new());
            (&(vec![
                "Week ".to_string(),
                ((date).week).to_string(),
                ", ".to_string(),
                (year).to_string(),
            ]))
                .join(__separator)
        });
    }
    if ((self_).unit == 3i64) {
        return Ok({
            let __separator = &(String::new());
            (&(vec![
                "Day ".to_string(),
                ((date).day).to_string(),
                ", ".to_string(),
                (year).to_string(),
            ]))
                .join(__separator)
        });
    }
    Ok({
        let __separator = &(String::new());
        (&(vec![
            "Hour ".to_string(),
            ((date).hour).to_string(),
            ", Day ".to_string(),
            ((date).day).to_string(),
        ]))
            .join(__separator)
    })
}
