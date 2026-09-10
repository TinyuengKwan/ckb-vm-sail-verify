//! Reproducer for repeated guarded alternatives, shaped like production rule_add3.
//! All arms and the final fallthrough have observable, distinct results.
pub fn guard_chain(x: u32, y: u32, z: u32) -> u32 {
    if x > 1 && y > 2 && z > 3 && x != y && y != z && x != z {
        return 11;
    }
    if x > 4 && y > 5 && z > 6 && x == y && y != z && x != z {
        return 22;
    }
    if x > 7 && y > 8 && z > 9 && x != y && y == z && x != z {
        return 33;
    }
    44
}

pub fn nested_early_exit(x: u32, flag: bool) -> u32 {
    if flag {
        if x == 3 {
            return 7;
        }
    } else if x == 5 {
        return 11;
    }
    if x == 9 { 13 } else { 17 }
}
