//! Exhaustive runtime check of the production RV64 VERSION2 I factory.
//! This is not a Lean proof of factory control flow or DefaultDecoder.
use ckb_vm::instructions::{extract_opcode, i, insts, instruction_length, Rtype};
use ckb_vm::machine::VERSION2;

fn matches(inst: u64, rd: usize, rs1: usize, rs2: usize) -> bool {
    let decoded = Rtype(inst);
    extract_opcode(inst) == insts::OP_ADD && instruction_length(inst) == 4
        && decoded.rd() == rd && decoded.rs1() == rs1 && decoded.rs2() == rs2
}

fn main() {
    let mut checked = 0usize;
    let mut neighbors = 0usize;
    let mut mutations = 0usize;
    for rd in 0..32usize {
        for rs1 in 0..32usize {
            for rs2 in 0..32usize {
                let bits = 0x33 | ((rd as u32) << 7)
                    | ((rs1 as u32) << 15) | ((rs2 as u32) << 20);
                let inst = i::factory::<u64>(bits, VERSION2).expect("legal ADD rejected");
                assert!(matches(inst, rd, rs1, rs2), "wrong ADD decode: {bits:08x}");
                checked += 1;
                // Change the decoded destination while leaving the input unchanged.
                assert!(!matches(inst ^ (1 << 8), rd, rs1, rs2), "mutation missed");
                mutations += 1;
                // Different opcode/funct3/funct7 must not be silently accepted as ADD.
                for bit in [0, 3, 12, 25, 30, 31] {
                    let other = bits ^ (1 << bit);
                    assert!(i::factory::<u64>(other, VERSION2)
                        .is_none_or(|decoded| extract_opcode(decoded) != insts::OP_ADD),
                        "non-ADD accepted as ADD: {other:08x}");
                    neighbors += 1;
                }
            }
        }
    }
    assert_eq!((checked, neighbors, mutations), (32768, 196608, 32768));
    println!("{{\"status\":\"passed\",\"scope\":\"RV64 VERSION2 i::factory; not DefaultDecoder or Lean proof\",\"legal_add_encodings\":{checked},\"non_add_neighbor_checks\":{neighbors},\"detected_rd_mutations\":{mutations}}}");
}
