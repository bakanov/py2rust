use py2rust_service_runtime as rt;

#[derive(Clone, PartialEq)]
pub(crate) struct Scenario {
    pub(crate) title: String,
    pub(crate) description: String,
    pub(crate) sections: indexmap::IndexMap<String, Vec<Vec<u8>>>,
    pub(crate) encoding: String,
    pub(crate) world: Option<crate::openciv3::world::WorldMap>,
}

// Python: openciv3/scenario.py:13
pub(crate) fn _integer(data: &[u8], mut offset: i64) -> rt::Result<i64> {
    if ((offset < 0i64)
        || ((offset).checked_add(4i64).ok_or("integer overflow")? > ((data).len() as i64)))
    {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Truncated BIQ integer at byte ".to_string(),
                (offset).to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    rt::int_from_bytes_signed(
        rt::slice_view(
            data,
            offset,
            (offset).checked_add(4i64).ok_or("integer overflow")?,
        ),
        "little",
        true,
    )
}

// Python: openciv3/scenario.py:19
pub(crate) fn _text(data: &[u8], encoding: &str) -> rt::Result<String> {
    rt::decode_bytes(
        &(rt::at(
            &(rt::bytes_split(&(rt::byte_buffer_copy(data)?), &(vec![0u8]), 1i64)),
            0i64,
        )?),
        encoding,
        "replace",
    )
}

// Python: openciv3/scenario.py:33
pub(crate) fn Scenario__load(path: &str, encoding: &str) -> rt::Result<Scenario> {
    Scenario__from_bytes(rt::read_bytes(path)?, encoding, false)
}

// Python: openciv3/scenario.py:37
pub(crate) fn Scenario__from_bytes(
    mut raw: Vec<u8>,
    encoding: &str,
    mut embedded: bool,
) -> rt::Result<Scenario> {
    if ((((raw).len() as i64) >= 2i64)
        && ({
            let __needle = (rt::at(&raw, 0i64)? as i64);
            let __container = &({
                let __tuple_value = &((0i64, 1i64));
                vec![__tuple_value.0.clone(), __tuple_value.1.clone()]
            });
            __container.contains(&__needle)
        } && {
            let __needle = (rt::at(&raw, 1i64)? as i64);
            let __container = &({
                let __tuple_value = &((4i64, 5i64, 6i64));
                vec![
                    __tuple_value.0.clone(),
                    __tuple_value.1.clone(),
                    __tuple_value.2.clone(),
                ]
            });
            __container.contains(&__needle)
        }))
    {
        raw = crate::openciv3::blast::decompress(&raw)?;
    }
    let mut valid_signature: bool = ((rt::bytes_slice(&raw, 0i64, 8i64)
        == vec![66u8, 73u8, 67u8, 88u8, 86u8, 69u8, 82u8, 35u8])
        || (embedded
            && (rt::bytes_slice(&raw, 0i64, 8i64)
                == vec![66u8, 73u8, 67u8, 81u8, 86u8, 69u8, 82u8, 35u8])));
    if ((((raw).len() as i64) < 736i64)
        || (!(valid_signature) || (_integer(&raw, 24i64)? != 12i64)))
    {
        return Err("Expected a Civilization III Conquests version 12 BIQ"
            .to_string()
            .into());
    }
    let mut data: Vec<u8> = raw;
    let mut sections: indexmap::IndexMap<String, Vec<Vec<u8>>> =
        [].into_iter().collect::<indexmap::IndexMap<_, _>>();
    let mut offset: i64 = 736i64;
    while (offset < ((data).len() as i64)) {
        if ((offset).checked_add(8i64).ok_or("integer overflow")? > ((data).len() as i64)) {
            return Err({
                let __separator = &(String::new());
                (&(vec![
                    "Truncated BIQ section header at byte ".to_string(),
                    (offset).to_string(),
                ]))
                    .join(__separator)
            }
            .into());
        }
        let mut name: String = rt::decode_ascii(
            &(rt::byte_buffer_copy(rt::slice_view(
                &data,
                offset,
                (offset).checked_add(4i64).ok_or("integer overflow")?,
            ))?),
        )?;
        let mut count: i64 =
            _integer(&data, (offset).checked_add(4i64).ok_or("integer overflow")?)?;
        offset = (offset).checked_add(8i64).ok_or("integer overflow")?;
        if (name.as_str() == "FLAV") {
            if (count != 1i64) {
                return Err("Unsupported flavor group count".to_string().into());
            }
            count = _integer(&data, offset)?;
            offset = (offset).checked_add(4i64).ok_or("integer overflow")?;
        }
        let mut records: Vec<Vec<u8>> = (sections).entry(name.clone()).or_insert(vec![]).clone();
        let mut minimum_size: i64 = (if (name.as_str() == "FLAV") {
            264i64
        } else {
            (if (name.as_str() == "BLDG") {
                272i64
            } else {
                4i64
            })
        });
        if !({
            let __compare_0 = 0i64;
            let __compare_1 = count;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = rt::int_floor_div(
                    ((data).len() as i64)
                        .checked_sub(offset)
                        .ok_or("integer overflow")?,
                    minimum_size,
                )?;
                (__compare_1 <= __compare_2)
            } else {
                false
            }
        }) {
            return Err({
                let __separator = &(String::new());
                (&(vec!["Invalid record count in ".to_string(), (name).to_string()]))
                    .join(__separator)
            }
            .into());
        }
        for _ in 0i64..count {
            let mut size: i64 = 0i64;
            if (name.as_str() == "FLAV") {
                let mut relationships: i64 = _integer(
                    &data,
                    (offset).checked_add(260i64).ok_or("integer overflow")?,
                )?;
                if (relationships < 0i64) {
                    return Err("Invalid flavor relationship count".to_string().into());
                }
                size = (264i64)
                    .checked_add(
                        (relationships)
                            .checked_mul(4i64)
                            .ok_or("integer overflow")?,
                    )
                    .ok_or("integer overflow")?;
            } else {
                size = (4i64)
                    .checked_add(_integer(&data, offset)?)
                    .ok_or("integer overflow")?;
            }
            if ((size < minimum_size)
                || ((offset).checked_add(size).ok_or("integer overflow")? > ((data).len() as i64)))
            {
                return Err({
                    let __separator = &(String::new());
                    (&(vec![
                        "Invalid ".to_string(),
                        (name).to_string(),
                        " record at byte ".to_string(),
                        (offset).to_string(),
                    ]))
                        .join(__separator)
                }
                .into());
            }
            {
                records.push(rt::bytes_slice(
                    &data,
                    offset,
                    (offset).checked_add(size).ok_or("integer overflow")?,
                ));
            };
            offset = (offset).checked_add(size).ok_or("integer overflow")?;
        }
    }
    Ok(Scenario {
        title: _text(rt::slice_view(&data, 672i64, 736i64), encoding)?,
        description: _text(rt::slice_view(&data, 32i64, 672i64), encoding)?,
        sections: sections,
        encoding: encoding.to_owned(),
        world: None,
    })
}

// Python: openciv3/scenario.py:76
pub(crate) fn Scenario__resources(
    self_: &Scenario,
) -> rt::Result<Vec<(String, i64, i64, Option<String>)>> {
    let mut yield_values: Vec<(String, i64, i64, Option<String>)> = vec![];
    let mut techs: Vec<Vec<u8>> = {
        let __mapping = &(self_).sections;
        let __key = "TECH".to_string();
        let __default = vec![];
        __mapping.get(&__key).cloned().unwrap_or(__default)
    };
    for mut record in {
        let __mapping = &(self_).sections;
        let __key = "GOOD".to_string();
        let __default = vec![];
        __mapping.get(&__key).cloned().unwrap_or(__default)
    } {
        let mut icon: i64 = _integer(&record, 72i64)?;
        let mut prerequisite: i64 = _integer(&record, 76i64)?;
        let mut tech: Option<String> = None;
        if {
            let __compare_0 = 0i64;
            let __compare_1 = prerequisite;
            if (__compare_0 <= __compare_1) {
                let __compare_2 = ((techs).len() as i64);
                (__compare_1 < __compare_2)
            } else {
                false
            }
        } {
            tech = Some(_text(
                rt::slice_view(
                    {
                        let __source = &techs;
                        let __key = prerequisite;
                        &__source[rt::index(__source.len(), __key)?]
                    },
                    4i64,
                    36i64,
                ),
                &(self_).encoding,
            )?);
        }
        {
            yield_values.push((
                _text(rt::slice_view(&record, 4i64, 28i64), &(self_).encoding)?,
                icon,
                prerequisite,
                tech,
            ));
        };
    }
    Ok(yield_values)
}
