//! Build driver only. No replacement decoder or iterator implementation.
pub fn check_std() -> usize { std::mem::size_of::<Vec<u64>>() }
