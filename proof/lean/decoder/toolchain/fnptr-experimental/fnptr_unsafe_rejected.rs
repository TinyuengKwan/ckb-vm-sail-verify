pub fn invoke(f: unsafe fn(u32) -> u32, x: u32) -> u32 { unsafe { f(x) } }
