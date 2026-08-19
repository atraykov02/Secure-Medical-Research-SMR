# PrecisionMPC Hospital Node

A hospital node has two responsibilities:

1. Query its own local synthetic medical PostgreSQL database to form a cohort and compute the minimum local aggregates required by the selected analysis.
2. Act as exactly one participant in the distributed BGW protocol. Plaintext local aggregates never leave the node; only Shamir shares are exchanged directly with peer hospital nodes.

## Internal API

All `/api/mpc/*` and `/api/analyses/*` endpoints require `X-MPC-Service-Token`.

### MPC lifecycle

- `POST /api/mpc/sessions` - creates ephemeral BGW state for this hospital.
- `POST /api/mpc/messages` - receives a Shamir input share or multiplication reshare from another hospital.
- `GET /api/mpc/sessions/{id}` - returns only non-sensitive session metadata and symbolic value names.
- `DELETE /api/mpc/sessions/{id}` - removes shares and intermediate values from application memory.

### Variant Frequency

1. Create the same MPC session on all participating nodes.
2. Call `POST /api/analyses/variant-frequency/share-local-inputs` on each hospital.
3. Call `POST /api/analyses/variant-frequency/build` on each hospital after all shares arrive.
4. The coordinator explicitly requests `/result-share` from all hospitals and reconstructs only `variant_total` and `cohort_total`.

### Therapy Response

1. Each hospital locally forms its four 2x2-table cells and secret-shares them.
2. Each hospital builds shared global `A`, `B`, `C`, `D`.
3. Each hospital starts the `AD` and `BC` BGW multiplication rounds.
4. Once reshares have arrived, each hospital finalizes degree reduction.
5. The coordinator reconstructs only `AD` and `BC`, then computes `OR = AD / BC` outside MPC.

## Environment

Example values are in `.env.example`. Each study uses 3–6 participants and an automatically selected threshold `t=floor((n-1)/2)` in the semi-honest model.
