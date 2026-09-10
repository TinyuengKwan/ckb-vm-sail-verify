//@ [!lean] skip

// Reduced from CKB-VM's I factory: an outer shared closure, a branching
// Option, and an inner closure which retains a shared capture across the join.
pub fn shared_factory(bits: u32, version: u32) -> Option<u32> {
    (|| match bits & 0x7f {
        0x67 => {
            let opcode = match (bits >> 12) & 7 {
                0 => Some(if version >= 1 { 10 } else { 20 }),
                _ => None,
            };
            opcode.map(|op| op + ((bits >> 7) & 31))
        }
        0x33 => Some((bits >> 7) & 31),
        _ => None,
    })()
}

#[test]
fn representative_results() {
    assert_eq!(shared_factory(0x67 | (3 << 7), 2), Some(13));
    assert_eq!(shared_factory(0x67 | (3 << 7), 0), Some(23));
    assert_eq!(shared_factory(0x67 | (1 << 12), 2), None);
    assert_eq!(shared_factory(0x33 | (31 << 7), 2), Some(31));
    assert_eq!(shared_factory(0, 2), None);
}
