//! Experimental translator checks, not production decoder proof.
pub type Factory = fn(u32, u32) -> Option<u64>;
pub fn first(bits: u32, _version: u32) -> Option<u64> {
    Some(u64::from(bits))
}
pub fn second(bits: u32, version: u32) -> Option<u64> {
    if version == 2 { Some(u64::from(bits) + 1) } else { None }
}
pub fn failing(_bits: u32, _version: u32) -> Option<u64> {
    panic!("callback failed")
}
pub fn invoke(f: Factory, bits: u32, version: u32) -> Option<u64> {
    f(bits, version)
}
pub fn select(which: bool, bits: u32) -> Option<u64> {
    let f: Factory = if which { first } else { second };
    f(bits, 2)
}
pub fn invoke_failure(bits: u32) -> Option<u64> {
    let f: Factory = failing;
    f(bits, 2)
}
pub struct Table { pub entries: Vec<Factory> }
pub fn make_table() -> Table { Table { entries: vec![first, second] } }
pub fn from_table(table: &Table, index: usize, bits: u32) -> Option<u64> {
    table.entries[index](bits, 2)
}
pub fn through_table(table: &Table, bits: u32) -> Option<u64> {
    for f in &table.entries {
        if let Some(inst) = f(bits, 2) { return Some(inst); }
    }
    None
}
pub fn plus_one(x: u64) -> u64 { x + 1 }
pub fn plus_two(x: u64) -> u64 { x + 2 }
pub fn map_one(x: Option<u64>) -> Option<u64> { x.map(plus_one) }
pub fn map_two(x: Option<u64>) -> Option<u64> { x.map(plus_two) }
