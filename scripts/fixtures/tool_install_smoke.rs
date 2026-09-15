// Installer smoke only, not a VM equivalence test.
fn main() {
    assert_eq!(40u64.wrapping_add(2), 42);
    println!("rust-toolchain-smoke:42");
}
