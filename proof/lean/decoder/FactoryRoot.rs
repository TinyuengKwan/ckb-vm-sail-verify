//! RV64 VERSION2 extraction caller of the actual production factory.
//! No instruction decoding or assembly is reimplemented here.
pub fn decode(bits: u32) -> Option<u64> {
    ckb_vm::instructions::i::factory::<u64>(bits, ckb_vm::machine::VERSION2)
}
