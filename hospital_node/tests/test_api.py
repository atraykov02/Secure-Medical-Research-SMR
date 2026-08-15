from __future__ import annotations

from fastapi.testclient import TestClient
import jwt

from bgw.models import MPCMessage, MessageType
from hospital_node.app.config import HospitalSettings
from hospital_node.app.main import create_app


def settings():
    return HospitalSettings(
        participant_id=1,
        organization_name="Test Hospital",
        participant_ids=[1, 2, 3],
        threshold=1,
        database_url="sqlite+pysqlite:///:memory:",
        service_token="test-token",
        peer_urls={1: "http://local", 2: "http://peer2", 3: "http://peer3"},
        auto_create_schema=True,
        auto_seed=False,
        local_access_secret="local-test-secret-with-32-bytes-minimum",
    )


def local_auth(participant_id: int = 1, scope: str = "local_patients", study_id: str | None = None):
    token = jwt.encode({
        "sub": "admin-id", "role": "ORG_ADMIN", "organization_id": "org-a",
        "participant_id": participant_id, "aud": "hospital-local-api",
        "type": "hospital_local_access",
        "scope": scope, "study_id": study_id,
    }, "local-test-secret-with-32-bytes-minimum", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_health_and_session_lifecycle():
    app = create_app(settings())
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        headers = {"X-MPC-Service-Token": "test-token"}
        assert client.get("/api/mpc/node-info").status_code == 401
        node_info = client.get("/api/mpc/node-info", headers=headers)
        assert node_info.status_code == 200
        assert node_info.json()["participant_id"] == 1
        payload = {
            "session_id": "s1",
            "participant_id": 1,
            "participant_ids": [1, 2, 3],
            "peer_urls": {"1": "http://local", "2": "http://peer2", "3": "http://peer3"},
            "threshold": 1,
            "prime": 2**61 - 1,
        }
        r = client.post("/api/mpc/sessions", json=payload, headers=headers)
        assert r.status_code == 201
        r = client.get("/api/mpc/sessions/s1", headers=headers)
        assert r.status_code == 200
        assert r.json()["available_value_names"] == []
        r = client.delete("/api/mpc/sessions/s1", headers=headers)
        assert r.status_code == 200


def test_incoming_share_is_stored_only_in_ephemeral_session_state():
    app = create_app(settings())
    with TestClient(app) as client:
        headers = {"X-MPC-Service-Token": "test-token"}
        client.post(
            "/api/mpc/sessions",
            json={"session_id": "s2", "participant_id": 1, "participant_ids": [1, 2, 3],
                  "peer_urls": {"1": "http://local", "2": "http://peer2", "3": "http://peer3"},
                  "threshold": 1, "prime": 2**61 - 1},
            headers=headers,
        )
        message = MPCMessage(
            session_id="s2",
            message_type=MessageType.INPUT_SHARE,
            sender_id=2,
            recipient_id=1,
            value_name="variant_count_p2",
            value=123456789,
        )
        r = client.post("/api/mpc/messages", json=message.to_payload(), headers=headers)
        assert r.status_code == 200
        r = client.get("/api/mpc/sessions/s2", headers=headers)
        assert r.json()["available_value_names"] == ["variant_count_p2"]
        # Status exposes the symbolic name, never the share value itself.
        assert "123456789" not in r.text


def test_session_identity_is_assigned_per_study():
    app = create_app(settings())
    with TestClient(app) as client:
        headers = {"X-MPC-Service-Token": "test-token"}
        response = client.post("/api/mpc/sessions", headers=headers, json={
            "session_id": "dynamic-role",
            "participant_id": 3,
            "participant_ids": [1, 2, 3],
            "peer_urls": {"1": "http://peer1", "2": "http://peer2", "3": "http://local"},
            "threshold": 1,
            "prime": 2**61 - 1,
        })
        assert response.status_code == 201, response.text
        status_response = client.get("/api/mpc/sessions/dynamic-role", headers=headers)
        assert status_response.json()["participant_id"] == 3


def test_session_accepts_six_dynamic_participants_with_threshold_two():
    app = create_app(settings())
    with TestClient(app) as client:
        headers = {"X-MPC-Service-Token": "test-token"}
        response = client.post("/api/mpc/sessions", headers=headers, json={
            "session_id": "six-participants",
            "participant_id": 4,
            "participant_ids": [1, 2, 3, 4, 5, 6],
            "peer_urls": {str(i): f"http://peer{i}" for i in range(1, 7)},
            "threshold": 2,
            "prime": 2**61 - 1,
        })
        assert response.status_code == 201, response.text
        status_response = client.get("/api/mpc/sessions/six-participants", headers=headers)
        assert status_response.json()["participant_ids"] == [1, 2, 3, 4, 5, 6]
        assert status_response.json()["threshold"] == 2


def test_local_data_requires_token_for_this_exact_hospital(tmp_path):
    configured = settings()
    configured.database_url = f"sqlite:///{tmp_path / 'local-data.sqlite'}"
    app = create_app(configured)
    with TestClient(app) as client:
        assert client.get("/api/local/patients").status_code == 401
        assert client.get("/api/local/patients", headers=local_auth(2)).status_code == 403
        allowed = client.get("/api/local/patients", headers=local_auth(1))
        assert allowed.status_code == 200
        assert allowed.json()["organization"] == "Test Hospital"


def test_local_patient_crud_is_isolated_in_hospital_database(tmp_path):
    configured = settings()
    configured.database_url = f"sqlite:///{tmp_path / 'patient-crud.sqlite'}"
    app = create_app(configured)
    headers = local_auth(1)
    payload = {
        "identifier": "TEST-PATIENT-001", "age": 44, "sex": "F",
        "disease_codes": ["DX-TEST"],
        "variants": [{"code": "VAR-TEST", "genotype": "0/1"}],
        "treatments": [{"therapy_code": "THERAPY-TEST", "response": "PARTIAL_RESPONSE"}],
    }
    with TestClient(app) as client:
        catalog = client.get("/api/local/catalog", headers=headers)
        assert catalog.status_code == 200
        assert catalog.json()["genotypes"] == ["0/0", "0/1", "1/0", "1/1"]

        assert client.post("/api/local/catalog/diseases", headers=headers, json={"code": "DX-TEST", "name": "Test disease"}).status_code == 201
        assert client.post("/api/local/catalog/variants", headers=headers, json={
            "code": "VAR-TEST", "gene": "GENE-T", "chromosome": "1", "position": 123,
            "reference_allele": "A", "alternate_allele": "G",
        }).status_code == 201
        assert client.post("/api/local/catalog/therapies", headers=headers, json={"code": "THERAPY-TEST", "name": "Test therapy"}).status_code == 201
        assert client.post("/api/local/catalog/responses", headers=headers, json={"code": "PARTIAL_RESPONSE", "name": "Partial response", "is_positive": True}).status_code == 201
        edited_disease = client.put("/api/local/catalog/diseases/DX-TEST", headers=headers, json={"code": "DX-TEST", "name": "Edited disease"})
        assert edited_disease.status_code == 200
        populated_catalog = client.get("/api/local/catalog", headers=headers).json()
        assert populated_catalog["responses"][0]["is_positive"] is True

        created = client.post("/api/local/patients", headers=headers, json=payload)
        assert created.status_code == 201, created.text
        assert created.json()["age"] == 44
        assert client.delete("/api/local/catalog/diseases/DX-TEST", headers=headers).status_code == 409

        detail = client.get("/api/local/patients/TEST-PATIENT-001", headers=headers)
        assert detail.status_code == 200

        updated = client.put("/api/local/patients/TEST-PATIENT-001", headers=headers, json={**payload, "age": 45})
        assert updated.status_code == 200, updated.text
        assert updated.json()["age"] == 45

        deleted = client.delete("/api/local/patients/TEST-PATIENT-001", headers=headers)
        assert deleted.status_code == 204
        assert client.get("/api/local/patients/TEST-PATIENT-001", headers=headers).status_code == 404
        assert client.delete("/api/local/catalog/diseases/DX-TEST", headers=headers).status_code == 204


def test_local_study_input_is_computed_without_persistence(tmp_path):
    configured = settings()
    configured.database_url = f"sqlite:///{tmp_path / 'local-input.sqlite'}"
    app = create_app(configured)
    with TestClient(app) as client:
        response = client.post("/api/local/studies/study-1/input", headers=local_auth(scope="local_study_input", study_id="study-1"), json={
            "analysis_type": "VARIANT_FREQUENCY",
            "criteria": {"variant_code": "V1"},
        })
        assert response.status_code == 200, response.text
        assert response.json()["study_id"] == "study-1"
        assert response.json()["cohort_size"] == 0
        assert response.json()["variant_count"] == 0


def test_demo_verification_input_requires_service_auth_and_synthetic_source(tmp_path):
    configured = settings()
    configured.database_url = f"sqlite:///{tmp_path / 'verification.sqlite'}"
    app = create_app(configured)
    payload = {
        "analysis_type": "VARIANT_FREQUENCY",
        "data_source": "SYNTHETIC",
        "criteria": {"variant_code": "V1"},
    }
    with TestClient(app) as client:
        path = "/api/verification/studies/demo-1/local-input"
        assert client.post(path, json=payload).status_code == 401
        invalid_source = {**payload, "data_source": "PRODUCTION"}
        assert client.post(path, json=invalid_source, headers={"X-MPC-Service-Token": "test-token"}).status_code == 422
        response = client.post(path, json=payload, headers={"X-MPC-Service-Token": "test-token"})
        assert response.status_code == 200, response.text
        assert response.json()["study_id"] == "demo-1"
        assert response.json()["organization"] == "Test Hospital"
