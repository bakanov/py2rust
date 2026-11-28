#![allow(
    unused_mut,
    unused_variables,
    unused_parens,
    dead_code,
    non_camel_case_types,
    non_snake_case
)]

pub(crate) mod civ;

pub(crate) mod civ3_ai;

pub(crate) mod civ3_console;

pub(crate) mod openciv3;

pub(crate) mod strategy;

use py2rust_service_runtime as rt;

fn main() -> rt::Result<()> {
    crate::civ3_console::native_campaign::main()?;
    Ok(())
}
