pub fn borrowed(f: fn(&u32) -> u32, x: &u32) -> u32 { f(x) }
