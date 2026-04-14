//! Machine state snapshot for trace comparison.

/// Execution state snapshot at a single step.
///
/// Captures the observable machine state after executing one instruction.
/// Used to compare CKB-VM against reference implementations.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct StepState {
    /// Program counter
    pub pc: u64,
    /// General-purpose registers x0..x31
    pub regs: [u64; 32],
}

impl StepState {
    pub fn new(pc: u64, regs: [u64; 32]) -> Self {
        Self { pc, regs }
    }
}

impl std::fmt::Display for StepState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "pc={:#018x}", self.pc)?;
        for (i, r) in self.regs.iter().enumerate() {
            if *r != 0 {
                write!(f, " x{}={:#x}", i, r)?;
            }
        }
        Ok(())
    }
}

/// Result of comparing two execution traces.
#[derive(Debug)]
pub struct CompareResult {
    pub total_steps: usize,
    pub first_mismatch: Option<Mismatch>,
}

#[derive(Debug)]
pub struct Mismatch {
    pub step: usize,
    pub ckb_state: StepState,
    pub ref_state: StepState,
}

impl CompareResult {
    pub fn compare(ckb_trace: &[StepState], ref_trace: &[StepState]) -> Self {
        let total_steps = ckb_trace.len().min(ref_trace.len());
        for i in 0..total_steps {
            if ckb_trace[i] != ref_trace[i] {
                return Self {
                    total_steps: i,
                    first_mismatch: Some(Mismatch {
                        step: i,
                        ckb_state: ckb_trace[i].clone(),
                        ref_state: ref_trace[i].clone(),
                    }),
                };
            }
        }
        Self {
            total_steps,
            first_mismatch: None,
        }
    }

    pub fn passed(&self) -> bool {
        self.first_mismatch.is_none()
    }
}
