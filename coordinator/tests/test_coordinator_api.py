from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from coordinator.app.config import CoordinatorSettings
from coordinator.app.main import create_app
from coordinator.app.orchestrator import MPCOrchestrator, NodeTarget


class FakeOrchestrator:
    threshold = 1
    prime = 2**61 - 1

    def __init__(self, result: dict | None = None):
        self.result = result or {"cohort_size": 300, "variant_count": 40, "frequency_percent": 13.3333}
        self.destroyed: list[str] = []

    @staticmethod
    def threshold_for_participant_count(participant_count: int) -> int:
        return (participant_count - 1) // 2

    def targets_for_study(self, study):
        return [
            NodeTarget(
                participant_index=p.participant_index,
                organization_id=p.organization.id,
                organization_name=p.organization.name,
                node_url=p.organization.node_url,
            )
            for p in sorted(study.participants, key=lambda item: item.participant_index)
        ]

    async def run(self, study, session_id: str):
        return dict(self.result)

    async def destroy_sessions(self, session_id: str, targets):
        self.destroyed.append(session_id)

    async def collect_demo_plaintext_inputs(self, study):
        if study.analysis_type.value == "VARIANT_FREQUENCY":
            return [
                {"organization": "Hospital A", "cohort_size": 100, "variant_count": 10},
                {"organization": "Hospital B", "cohort_size": 100, "variant_count": 15},
                {"organization": "Hospital C", "cohort_size": 100, "variant_count": 15},
            ]
        return [
            {"organization": "Hospital A", "cohort_size": 12, "a": 7, "b": 2, "c": 2, "d": 1},
            {"organization": "Hospital B", "cohort_size": 0, "a": 0, "b": 0, "c": 0, "d": 0},
            {"organization": "Hospital C", "cohort_size": 0, "a": 0, "b": 0, "c": 0, "d": 0},
        ]


def make_client(tmp_path: Path, *, result: dict | None = None, minimum_cohort_size: int = 10):
    db_path = tmp_path / "coordinator.sqlite"
    settings = CoordinatorSettings(
        database_url=f"sqlite:///{db_path}",
        jwt_secret="test-secret-with-enough-entropy-123456",
        mpc_service_token="test-token",
        auto_create_schema=True,
        auto_seed=True,
        minimum_cohort_size=minimum_cohort_size,
    )
    app = create_app(settings)
    fake = FakeOrchestrator(result)
    app.state.orchestrator = fake
    return TestClient(app), fake


def login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_variant_study(client: TestClient, researcher_token: str, study_mode: str = "SECURE") -> dict:
    orgs = client.get("/api/organizations", headers=auth(researcher_token)).json()
    assert len(orgs) == 6
    payload = {
        "name": "Variant V1 multicenter study",
        "description": "Synthetic precision medicine demonstration",
        "analysis_type": "VARIANT_FREQUENCY",
        "study_mode": study_mode,
        "organization_ids": [o["id"] for o in orgs[:3]],
        "criteria": {
            "min_age": 40,
            "max_age": 70,
            "sex": None,
            "disease_code": "DX",
            "variant_code": "V1",
            "therapy_code": None,
        },
    }
    response = client.post("/api/studies", json=payload, headers=auth(researcher_token))
    assert response.status_code == 201, response.text
    return response.json()


def approve_all(client: TestClient, study_id: str) -> None:
    for idx in (1, 2, 3):
        token = login(client, f"admin{idx}@smr.com", "Admin123!")
        response = client.post(
            f"/api/studies/{study_id}/approval",
            json={"approve": True},
            headers=auth(token),
        )
        assert response.status_code == 200, response.text
    assert response.json()["status"] == "READY"


def test_full_study_workflow(tmp_path: Path):
    client, fake = make_client(tmp_path)
    with client:
        researcher = login(client, "researcher@smr.com", "Research123!")
        me = client.get("/api/auth/me", headers=auth(researcher))
        assert me.status_code == 200
        assert me.json()["role"] == "RESEARCHER"

        study = create_variant_study(client, researcher)
        assert study["status"] == "WAITING_APPROVAL"
        assert all(p["status"] == "INVITED" for p in study["participants"])

        approve_all(client, study["id"])

        run = client.post(f"/api/studies/{study['id']}/run", headers=auth(researcher))
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["status"] == "COMPLETED"
        assert body["result"]["variant_count"] == 40
        assert body["result"]["cohort_size"] == 300
        assert fake.destroyed == [body["session_id"]]

        stored = client.get(f"/api/studies/{study['id']}", headers=auth(researcher)).json()
        assert stored["status"] == "COMPLETED"
        assert stored["result"]["frequency_percent"] == 13.3333

        audit = client.get(f"/api/audit?study_id={study['id']}", headers=auth(researcher))
        events = {row["event_type"] for row in audit.json()}
        assert "STUDY_CREATED" in events
        assert "PARTICIPATION_APPROVED" in events
        assert "MPC_STARTED" in events
        assert "RESULT_RECONSTRUCTED" in events


def test_failed_mpc_execution_can_be_retried_after_nodes_recover(tmp_path: Path):
    client, fake = make_client(tmp_path)
    with client:
        researcher = login(client, "researcher@smr.com", "Research123!")
        study = create_variant_study(client, researcher)
        approve_all(client, study["id"])

        successful_run = fake.run

        async def unavailable_nodes(study, session_id: str):
            raise OSError("hospital nodes unavailable")

        fake.run = unavailable_nodes
        failed = client.post(f"/api/studies/{study['id']}/run", headers=auth(researcher))
        assert failed.status_code == 502
        stored = client.get(f"/api/studies/{study['id']}", headers=auth(researcher)).json()
        assert stored["status"] == "FAILED"
        assert all(p["status"] == "APPROVED" for p in stored["participants"])

        fake.run = successful_run
        retried = client.post(f"/api/studies/{study['id']}/run", headers=auth(researcher))
        assert retried.status_code == 200, retried.text
        assert retried.json()["status"] == "COMPLETED"


def test_researcher_cannot_approve_hospital_participation(tmp_path: Path):
    client, _ = make_client(tmp_path)
    with client:
        researcher = login(client, "researcher@smr.com", "Research123!")
        study = create_variant_study(client, researcher)
        response = client.post(
            f"/api/studies/{study['id']}/approval",
            json={"approve": True},
            headers=auth(researcher),
        )
        assert response.status_code == 403


def test_only_org_admin_receives_hospital_local_access_token(tmp_path: Path):
    client, _ = make_client(tmp_path)
    with client:
        admin = login(client, "admin1@smr.com", "Admin123!")
        allowed = client.get("/api/organizations/me/local-access", headers=auth(admin))
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["organization"]["name"] == "УМБАЛ Св. Иван Рилски - София"
        assert allowed.json()["node_url"] == "http://localhost:8101"

        researcher = login(client, "researcher@smr.com", "Research123!")
        assert client.get("/api/organizations/me/local-access", headers=auth(researcher)).status_code == 403
        system_admin = login(client, "system@smr.com", "System123!")
        assert client.get("/api/organizations/me/local-access", headers=auth(system_admin)).status_code == 403


def test_invalid_hospital_node_port_is_rejected(tmp_path: Path):
    client, _ = make_client(tmp_path)
    with client:
        system = login(client, "system@smr.com", "System123!")
        organization = client.get("/api/organizations", headers=auth(system)).json()[0]
        response = client.patch(
            f"/api/organizations/{organization['id']}",
            headers=auth(system),
            json={"node_url": "http://hospital-a:80001"},
        )
        assert response.status_code == 422


def test_system_admin_registers_verifies_and_activates_existing_node(tmp_path: Path, monkeypatch):
    class NodeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "ok", "participant_id": 7, "organization_name": "New Hospital"}

    requests = []

    def fake_get(url, *, headers, timeout):
        requests.append((url, headers, timeout))
        return NodeResponse()

    monkeypatch.setattr("coordinator.app.routers.organizations.httpx.get", fake_get)
    client, _ = make_client(tmp_path)
    with client:
        system = login(client, "system@smr.com", "System123!")
        created = client.post("/api/organizations", headers=auth(system), json={
            "name": "New Hospital",
            "type": "HOSPITAL",
            "node_url": "http://hospital-g:8000",
        })
        assert created.status_code == 201, created.text
        assert created.json()["participant_index"] == 7
        assert created.json()["is_active"] is False

        verified = client.post(
            f"/api/organizations/{created.json()['id']}/verify", headers=auth(system)
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["status"] == "verified"

        activated = client.patch(
            f"/api/organizations/{created.json()['id']}",
            headers=auth(system), json={"is_active": True},
        )
        assert activated.status_code == 200, activated.text
        assert activated.json()["is_active"] is True
        assert all(call[1]["X-MPC-Service-Token"] == "test-token" for call in requests)


def test_small_cohort_result_is_suppressed(tmp_path: Path):
    result = {"cohort_size": 5, "variant_count": 2, "frequency_percent": 40.0}
    client, _ = make_client(tmp_path, result=result, minimum_cohort_size=10)
    with client:
        researcher = login(client, "researcher@smr.com", "Research123!")
        study = create_variant_study(client, researcher)
        approve_all(client, study["id"])
        run = client.post(f"/api/studies/{study['id']}/run", headers=auth(researcher))
        assert run.status_code == 200
        assert run.json()["result"] == {
            "suppressed": True,
            "reason": "cohort_below_privacy_threshold",
            "minimum_cohort_size": 10,
        }


def create_therapy_study(client: TestClient, researcher_token: str, study_mode: str = "SECURE") -> dict:
    orgs = client.get("/api/organizations", headers=auth(researcher_token)).json()
    payload = {
        "name": "Variant V1 therapy response study",
        "description": "Synthetic therapy-response demonstration",
        "analysis_type": "THERAPY_RESPONSE",
        "study_mode": study_mode,
        "organization_ids": [o["id"] for o in orgs[:3]],
        "criteria": {
            "min_age": 40,
            "max_age": 70,
            "sex": None,
            "disease_code": "DX",
            "variant_code": "V1",
            "therapy_code": "T1",
        },
    }
    response = client.post("/api/studies", json=payload, headers=auth(researcher_token))
    assert response.status_code == 201, response.text
    return response.json()


def test_therapy_response_public_result_does_not_persist_cross_products(tmp_path: Path):
    result = {"cohort_size": 240, "odds_ratio": 1.75}
    client, _ = make_client(tmp_path, result=result)
    with client:
        researcher = login(client, "researcher@smr.com", "Research123!")
        study = create_therapy_study(client, researcher)
        approve_all(client, study["id"])
        run = client.post(f"/api/studies/{study['id']}/run", headers=auth(researcher))
        assert run.status_code == 200, run.text
        assert run.json()["result"] == {"cohort_size": 240, "odds_ratio": 1.75}
        assert "ad" not in run.json()["result"]
        assert "bc" not in run.json()["result"]


def test_demonstration_variant_verification_matches_bgw(tmp_path: Path):
    client, _ = make_client(tmp_path)
    with client:
        researcher = login(client, "researcher@smr.com", "Research123!")
        study = create_variant_study(client, researcher, "DEMONSTRATION")
        approve_all(client, study["id"])
        assert client.post(f"/api/studies/{study['id']}/run", headers=auth(researcher)).status_code == 200
        verification = client.post(f"/api/studies/{study['id']}/verify", headers=auth(researcher))
        assert verification.status_code == 200, verification.text
        assert verification.json()["verified"] is True
        assert verification.json()["differences"]["frequency_percent"] == 0
        stored_study = client.get(f"/api/studies/{study['id']}", headers=auth(researcher)).json()
        assert "local_breakdown" not in stored_study
        assert stored_study["result"] == verification.json()["bgw"]

        hospital_admin = login(client, "admin1@smr.com", "Admin123!")
        assert client.post(f"/api/studies/{study['id']}/verify", headers=auth(hospital_admin)).status_code == 403


def test_secure_study_cannot_use_plaintext_verification(tmp_path: Path):
    client, _ = make_client(tmp_path)
    with client:
        researcher = login(client, "researcher@smr.com", "Research123!")
        study = create_variant_study(client, researcher)
        approve_all(client, study["id"])
        client.post(f"/api/studies/{study['id']}/run", headers=auth(researcher))
        assert client.post(f"/api/studies/{study['id']}/verify", headers=auth(researcher)).status_code == 403


def test_suppressed_demonstration_result_cannot_expose_plaintext(tmp_path: Path):
    client, _ = make_client(
        tmp_path,
        result={"cohort_size": 5, "variant_count": 2, "frequency_percent": 40.0},
        minimum_cohort_size=10,
    )
    with client:
        researcher = login(client, "researcher@smr.com", "Research123!")
        study = create_variant_study(client, researcher, "DEMONSTRATION")
        approve_all(client, study["id"])
        client.post(f"/api/studies/{study['id']}/run", headers=auth(researcher))
        assert client.post(f"/api/studies/{study['id']}/verify", headers=auth(researcher)).status_code == 409


def test_demonstration_therapy_verification_matches_bgw(tmp_path: Path):
    client, _ = make_client(tmp_path, result={"cohort_size": 12, "odds_ratio": 1.75})
    with client:
        researcher = login(client, "researcher@smr.com", "Research123!")
        study = create_therapy_study(client, researcher, "DEMONSTRATION")
        approve_all(client, study["id"])
        client.post(f"/api/studies/{study['id']}/run", headers=auth(researcher))
        verification = client.post(f"/api/studies/{study['id']}/verify", headers=auth(researcher))
        assert verification.status_code == 200, verification.text
        assert verification.json()["verified"] is True
        assert verification.json()["reference"]["ad"] == 7
        assert verification.json()["reference"]["bc"] == 4


def test_org_admin_only_lists_participating_studies(tmp_path: Path):
    client, _ = make_client(tmp_path)
    with client:
        researcher = login(client, "researcher@smr.com", "Research123!")
        study = create_variant_study(client, researcher)
        admin1 = login(client, "admin1@smr.com", "Admin123!")
        studies = client.get("/api/studies", headers=auth(admin1))
        assert studies.status_code == 200
        assert [item["id"] for item in studies.json()] == [study["id"]]


def test_public_registration_creates_researcher(tmp_path: Path):
    client, _ = make_client(tmp_path)
    with client:
        response = client.post("/api/auth/register", json={
            "email": "new.researcher@example.com",
            "password": "StrongPass123!",
            "first_name": "New",
            "last_name": "Researcher",
        })
        assert response.status_code == 201, response.text
        assert response.json()["role"] == "RESEARCHER"
        assert response.json()["organization_id"] is None
        assert login(client, "new.researcher@example.com", "StrongPass123!")


def test_study_can_include_all_six_registered_organizations(tmp_path: Path):
    client, _ = make_client(tmp_path)
    with client:
        system = login(client, "system@smr.com", "System123!")
        orgs = client.get("/api/organizations", headers=auth(system)).json()
        assert len(orgs) == 6

        payload = {
            "name": "Dynamic organization selection",
            "analysis_type": "VARIANT_FREQUENCY",
            "organization_ids": [org["id"] for org in orgs],
            "criteria": {"variant_code": "V1"},
        }
        created = client.post("/api/studies", json=payload, headers=auth(system))
        assert created.status_code == 201, created.text
        assert [p["participant_index"] for p in created.json()["participants"]] == [1, 2, 3, 4, 5, 6]
        assert MPCOrchestrator.threshold_for_participant_count(6) == 2
