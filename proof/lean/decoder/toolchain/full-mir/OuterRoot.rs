use ckb_vm::decoder::{DefaultDecoder, InstDecoder};
use ckb_vm::memory::sparse::SparseMemory;

pub fn fresh_decoder() -> DefaultDecoder {
    DefaultDecoder::new::<u64>(ckb_vm::ISA_IMC | ckb_vm::ISA_B, ckb_vm::machine::VERSION2)
}
pub fn decode_raw(decoder: &mut DefaultDecoder, memory: &mut SparseMemory<u64>, pc: u64)
    -> Result<u64, ckb_vm::Error> {
    decoder.decode_raw(memory, pc)
}
pub fn decode(decoder: &mut DefaultDecoder, memory: &mut SparseMemory<u64>, pc: u64)
    -> Result<u64, ckb_vm::Error> {
    decoder.decode(memory, pc)
}
