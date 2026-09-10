pub fn foreign(f: extern "C" fn(u32) -> u32, x: u32) -> u32 { f(x) }
