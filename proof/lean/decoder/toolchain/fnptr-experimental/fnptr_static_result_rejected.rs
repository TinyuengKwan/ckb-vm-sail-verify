pub struct HiddenBorrow { pub value: &'static u32 }
pub fn invoke(f: fn(u32) -> HiddenBorrow, x: u32) -> HiddenBorrow { f(x) }
