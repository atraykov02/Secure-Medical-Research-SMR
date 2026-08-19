# PrecisionMPC BGW refactor

This directory contains a refactor of the original single-process `bgw.py` into a reusable BGW library suitable for the PrecisionMPC architecture.

## Fixed application model

- 3 hospital MPC nodes (`P1`, `P2`, `P3`)
- semi-honest/passive adversary model
- threshold `t = 1`
- arithmetic over `GF(2^61 - 1)`
- shares and intermediate values remain in process memory only
- clear local medical aggregates never go through the central coordinator
- hospital nodes exchange Shamir shares directly

The application supports studies with 3–6 hospital nodes. It selects the BGW threshold automatically as `t=floor((n-1)/2)`, while preserving `n >= 2t + 1`.

## Main changes from the original file

### Removed from the production design

The old `BGW` class instantiated every party in one process and the old `Network` stored every message centrally. That is correct for an educational simulator, but not for the distributed PrecisionMPC deployment.

### Added

- `BGWParticipant`: one hospital owns one participant object and sees only its own shares.
- `MPCTransport`: network abstraction.
- `InMemoryTransport`: unit-test transport with separate participant objects.
- `HTTPTransport`: direct hospital-node communication over HTTP.
- `BGWSessionStore`: ephemeral session state for a hospital node.
- session-aware `MPCMessage` objects.
- multiplication split into `begin_multiplication()` and `finalize_multiplication()` so network messages can arrive asynchronously.
- final-result reconstruction separated from participant state.
- medical circuit helpers for Variant Frequency and Therapy Response.
- field elements are serialized as decimal strings in HTTP payloads to avoid JavaScript's `2^53-1` integer limit.

## Package layout

```text
bgw/
  field.py
  models.py
  shamir.py
  participant.py
  reconstruction.py
  session_store.py
  circuits.py
  transport/
    base.py
    memory.py
    http.py
```

## Hospital-node integration

Each hospital FastAPI process will create one `BGWParticipant` per active MPC session:

```python
participant = BGWParticipant(
    session_id=session_id,
    participant_id=1,             # Hospital A
    participant_ids=[1, 2, 3],
    threshold=1,
)
```

Incoming HTTP messages are converted with:

```python
message = MPCMessage.from_payload(request_json)
await participant.handle_message(message)
```

The production `HTTPTransport` sends directly to the other hospital nodes at:

```text
POST /api/mpc/messages
```

The central coordinator should orchestrate phases and store statuses/results, but it should not store Shamir shares.

## Variant Frequency

Each hospital locally computes two clear values:

- local number of patients carrying the selected variant
- local cohort size

Those two values are secret-shared locally. The MPC nodes then add the corresponding shared values. Only the global totals `V` and `N` are reconstructed, after which the coordinator may compute `100 * V / N`.

## Therapy Response / Variant Association

Each hospital locally builds four counts:

- `a`: variant + responder
- `b`: variant + non-responder
- `c`: no variant + responder
- `d`: no variant + non-responder

The global shared values `A,B,C,D` are obtained with local BGW additions. The nodes then securely multiply:

```text
AD = A * D
BC = B * C
```

Only `AD` and `BC` need to be reconstructed. The odds ratio is calculated after reconstruction:

```text
OR = AD / BC
```

This deliberately exercises the interactive BGW multiplication and degree-reduction step.

## Tests

Run:

```bash
PYTHONPATH=. pytest -q
```

The tests cover:

- Shamir sharing
- distributed input sharing
- local addition
- interactive multiplication + degree reduction
- Variant Frequency flow
- Therapy Response secure cross-products
- safe HTTP serialization of field elements

## Demo

```bash
PYTHONPATH=. python examples/distributed_medical_demo.py
```

This uses `InMemoryTransport`, so it is suitable for development and thesis demonstrations before FastAPI hospital nodes are wired in.

## Not implemented intentionally

- VSS / malicious-adversary BGW
- persistent storage of shares
- arbitrary user-defined arithmetic expressions in production
- secure memory zeroization (Python does not guarantee it)
- TLS certificate management / production PKI

These are outside the fixed MVP scope or belong to the deployment layer rather than the BGW core.

## Phase 2: distributed hospital nodes

The project now also contains `hospital_node/`, a FastAPI service that is instantiated once per medical organization. Each node owns a separate medical database, computes cohort aggregates locally, and exchanges only Shamir/BGW shares with peer nodes.

A three-hospital demo stack is defined in `docker-compose.hospital-demo.yml`. After it is running, `examples/http_three_hospital_demo.py` exercises both PrecisionMPC analyses through actual HTTP communication between the three hospital processes.

## Phase 3: Central Coordinator

`coordinator/` is the central FastAPI application backend intended for the Vue frontend. It provides JWT authentication, role-based access, organizations, studies, cohort criteria, organization approvals, MPC orchestration, privacy-threshold suppression, public results, MPC-session status and audit logs.

The coordinator is deliberately separated from all hospital medical databases. It never queries patient records. The hospital nodes receive only cohort criteria and perform their queries locally.

Studies default to privacy-preserving `SECURE` mode. For thesis-defense correctness experiments, an explicit synthetic-only `DEMONSTRATION` mode can compare the allowed BGW output with a separate plaintext reference implementation. The temporary hospital aggregates used by that verification are never stored in the coordinator database, and the verification endpoint rejects `SECURE` studies.

A complete backend-only development stack is available with:

```bash
docker compose -f docker-compose.backend.yml up --build
```

The Vue 3 + TypeScript frontend is included in `frontend/` and is part of the
same Compose stack. Open `http://localhost:5174` after startup. For local UI
development, run `npm install` and `npm run dev` from `frontend/`; Vite proxies
`/api` to the coordinator on port 8000.

The coordinator is exposed at `http://localhost:8000` and the three hospital nodes at ports `8101`, `8102` and `8103`.

Run all automated tests with:

```bash
python -m pytest -q
```

After the backend Docker stack is running, a complete API workflow can be demonstrated with:

```bash
python examples/coordinator_workflow_demo.py variant
python examples/coordinator_workflow_demo.py therapy
```
