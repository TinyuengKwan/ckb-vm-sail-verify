//@ charon-args=--deallocate-all-locals

struct Word(u64);
impl Word {
    fn rd(&self) -> u8 { (self.0 >> 8) as u8 }
    fn rs1(&self) -> u8 { (self.0 >> 32) as u8 }
    fn rs2(&self) -> u8 { (self.0 >> 40) as u8 }
}

pub fn field_alternatives(head: u64, next: Result<u64, String>, tail: Result<u64, String>) -> Result<Option<u8>, String> {
    let i0 = Word(head);
    let i1 = Word(next?);
    let i2 = Word(tail?);
    {
        let r0 = i0.rd();
        let r1 = i0.rs1();
        let r2 = i1.rd();
        let r3 = i2.rd();
        let r4 = i2.rs2();
        let matched = i0.rd() == r0 && i0.rs1() == r1 && i0.rs2() == r0
            && i1.rd() == r2 && i1.rs1() == r0 && i1.rs2() == r1
            && i2.rd() == r3 && i2.rs1() == r2 && i2.rs2() == r4
            && r0 != r1 && r0 != r4 && r2 != r4 && r0 != 0 && r2 != 0;
        if matched {
            return Ok(Some(11));
        }
    }
    {
        let r0 = i0.rd();
        let r1 = i0.rs1();
        let r2 = i0.rs2();
        let r3 = i2.rd();
        let r4 = i2.rs2();
        let matched = i0.rd() == r0 && i0.rs1() == r1 && i0.rs2() == r2
            && i1.rd() == r1 && i1.rs1() == r0 && i1.rs2() == r1
            && i2.rd() == r3 && i2.rs1() == r1 && i2.rs2() == r4
            && r0 != r1 && r0 != r4 && r1 != r4 && r0 != 0 && r1 != 0;
        if matched {
            return Ok(Some(22));
        }
    }
    {
        let r0 = i0.rd();
        let r1 = i0.rs1();
        let r2 = i0.rs2();
        let r3 = i1.rd();
        let r4 = i2.rs2();
        let matched = i0.rd() == r0 && i0.rs1() == r1 && i0.rs2() == r2
            && i1.rd() == r3 && i1.rs1() == r0 && i1.rs2() == r1
            && i2.rd() == r3 && i2.rs1() == r3 && i2.rs2() == r4
            && r0 != r1 && r0 != r4 && r3 != r4 && r0 != 0 && r3 != 0;
        if matched {
            return Ok(Some(33));
        }
    }
    Ok(None)
}
