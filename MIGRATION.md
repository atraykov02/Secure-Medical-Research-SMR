# Migration map from the original bgw.py

| Original element | Refactored element | Decision |
|---|---|---|
| `PrimeField` | `bgw/field.py` | Kept, isolated as core arithmetic |
| `Share` | `bgw/models.py` | Kept |
| `shamir_share` | `bgw/shamir.py` | Kept + validation |
| `lagrange_coeffs_at_zero` | `bgw/shamir.py` | Kept |
| `shamir_reconstruct` | `bgw/shamir.py` | Kept + threshold validation |
| `Network` | `transport/InMemoryTransport` | Test-only replacement |
| `Party` | `BGWParticipant` | Converted to one hospital / one session participant |
| central `BGW.parties` | removed | Production must not see all parties' shares |
| `BGW.input_share` | `BGWParticipant.share_private_input` | Owner shares locally and sends direct messages |
| local gates | methods on `BGWParticipant` | Kept |
| `BGW.mul` | `begin_multiplication` + `finalize_multiplication` | Split for asynchronous network delivery |
| `BGW.reveal` | `reconstruct_result` | Explicit final-result reconstruction only |
| `ExprCompiler` | not ported to production core | Medical analyses use fixed audited circuits |
| `_interactive` | removed | Vue/FastAPI replaces CLI |
| `_selftest` | `pytest` suite | Replaced by automated tests |

The original expression compiler is intentionally not part of the production core. Allowing arbitrary formulas in the medical workflow would make validation and orchestration harder. If the thesis BGW visualization screen later needs an expression sandbox, it should compile to an explicit distributed circuit plan rather than directly executing one participant at a time.

## Phase 3 coordinator integration

The application now includes a separate `coordinator/` FastAPI service. It owns only platform metadata (users, organizations, studies, approvals, MPC sessions, public results and audit events). It never reads hospital medical databases.

The coordinator creates ephemeral BGW sessions on three hospital nodes, supplies cohort criteria, orchestrates the selected analysis, reconstructs only permitted aggregate outputs and destroys hospital session state afterward. Therapy-response cross-products `AD` and `BC` are used transiently to derive the odds ratio and are not persisted as public study results.
