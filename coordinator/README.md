# PrecisionMPC Central Coordinator

The coordinator is the central application backend used by the Vue client. It manages users, organizations, multicenter studies, approvals, MPC session orchestration, public results and audit events.

It deliberately **does not connect to hospital medical databases**. In the normal `SECURE` mode it never receives local plaintext cohort aggregates: each hospital performs local cohort selection and Shamir secret sharing inside its own process, and hospital nodes exchange BGW shares directly. An explicit `DEMONSTRATION` mode may return temporary local aggregates from synthetic data only, solely for the independent correctness check described below; those inputs are not persisted centrally.

## Fixed demonstrator model

- three MPC organizations: Hospital A, Hospital B and Hospital C;
- BGW passive / semi-honest security model;
- `n = 3`, `t = 1`;
- arithmetic over `GF(2^61 - 1)`;
- minimum combined cohort size is configurable and defaults to 10;
- temporary shares and intermediate BGW values are not stored in the coordinator database.

## Study workflow

1. A `RESEARCHER` creates a multicenter study and selects between three and six organizations.
2. The coordinator stores only study metadata and cohort criteria.
3. An `ORG_ADMIN` from each participating organization approves or rejects participation.
4. After three approvals, the study becomes `READY`.
5. The researcher starts secure computation.
6. The coordinator creates the same ephemeral BGW session on all hospital nodes.
7. Each hospital selects its cohort locally and secret-shares only the required local aggregate values.
8. Hospital nodes exchange Shamir/BGW shares directly.
9. The coordinator collects only explicitly allowed final-result shares and reconstructs the aggregate output.
10. Results are suppressed if the combined cohort is below the configured privacy threshold.
11. Privacy-safe audit events and the final public result are stored centrally.
12. Ephemeral BGW session state is deleted from the hospital nodes.

## Independent correctness verification

Every study has a `study_mode`:

- `SECURE` (default) keeps the original privacy-preserving workflow and rejects plaintext verification;
- `DEMONSTRATION` is restricted to the synthetic local datasets and allows a completed result to be compared with an independent plaintext reference implementation.

For demonstration verification, the coordinator requests the local synthetic aggregates from the three hospital nodes, calculates the reference result in `coordinator/app/verification/reference_analysis.py`, compares it with the stored BGW output using a tolerance of `1e-9`, and returns the comparison to the authorized researcher or system administrator. Hospital-level plaintext aggregates exist only for that request and are not written to the coordinator database. A result suppressed by the privacy threshold cannot be verified.

For Therapy Response, the products `AD` and `BC` are reconstructed only transiently to calculate the odds ratio. They are not persisted in `study_results`. The combined cohort size and the odds ratio are the public stored outputs.

## Central database entities

- `organizations`
- `users`
- `studies`
- `study_cohort_criteria`
- `study_participants`
- `mpc_sessions`
- `study_results`
- `audit_logs`

There is intentionally no `patients` table in the coordinator database.

## Main API endpoints

```text
POST /api/auth/login
GET  /api/auth/me

GET  /api/organizations
POST /api/organizations              SYSTEM_ADMIN

GET  /api/users                      SYSTEM_ADMIN
POST /api/users                      SYSTEM_ADMIN

GET  /api/studies
POST /api/studies                    RESEARCHER / SYSTEM_ADMIN
GET  /api/studies/{study_id}
POST /api/studies/{study_id}/approval ORG_ADMIN
POST /api/studies/{study_id}/run      RESEARCHER / SYSTEM_ADMIN
POST /api/studies/{study_id}/verify   RESEARCHER / SYSTEM_ADMIN; DEMONSTRATION only

GET  /api/mpc-sessions
GET  /api/mpc-sessions/{session_id}

GET  /api/audit
```

Study, MPC-session and audit visibility is role-aware: a researcher sees studies they created, an organization administrator sees studies in which their organization participates, and the system administrator can see all records.

## Demo accounts (`COORDINATOR_AUTO_SEED=true`)

- `researcher@precisionmpc.example.com` / `Research123!`
- `admin1@precisionmpc.example.com` / `Admin123!`
- `admin2@precisionmpc.example.com` / `Admin123!`
- `admin3@precisionmpc.example.com` / `Admin123!`
- `system@precisionmpc.example.com` / `System123!`

These credentials are for the local thesis demonstrator only.

## Tests

From the project root:

```bash
python -m pytest -q
```

## Backend Docker stack

The complete backend stack is defined in:

```text
docker-compose.backend.yml
```

It starts one coordinator PostgreSQL database, the central FastAPI coordinator, three independent hospital PostgreSQL databases and three hospital FastAPI nodes.
