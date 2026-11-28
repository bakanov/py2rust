use py2rust_service_runtime as rt;

// Python: openciv3/json_io.py:9
pub(crate) fn read_object(path: &str) -> rt::Result<indexmap::IndexMap<String, rt::Json>> {
    let mut value: rt::Json = rt::json_loads(&(rt::read_text_encoding(path, "utf-8-sig")?))?;
    if !(rt::json_kind(&(value.clone())) == "object") {
        return Err({
            let __separator = &(String::new());
            (&(vec![
                "Expected JSON object: ".to_string(),
                (path.to_owned()).to_string(),
            ]))
                .join(__separator)
        }
        .into());
    }
    Ok(rt::json_object(&(value))?)
}
