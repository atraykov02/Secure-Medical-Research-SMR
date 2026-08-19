#!/usr/bin/env python3
"""Run a complete PrecisionMPC study through the Central Coordinator API.

Prerequisite:
    docker compose -f docker-compose.backend.yml up --build

Usage:
    python examples/coordinator_workflow_demo.py variant
    python examples/coordinator_workflow_demo.py therapy
"""
from __future__ import annotations

import argparse
import sys

import httpx

BASE_URL = "http://localhost:8000"


def login(client: httpx.Client, email: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return response.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def approve_all(client: httpx.Client, study_id: str) -> None:
    for index in (1, 2, 3):
        token = login(client, f"admin{index}@precisionmpc.example.com", "Admin123!")
        response = client.post(
            f"/api/studies/{study_id}/approval",
            json={"approve": True},
            headers=headers(token),
        )
        response.raise_for_status()
        print(f"Hospital {index}: {response.json()['participants'][index - 1]['status']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis", choices=["variant", "therapy"])
    args = parser.parse_args()

    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        researcher = login(client, "researcher@precisionmpc.example.com", "Research123!")
        org_response = client.get("/api/organizations", headers=headers(researcher))
        org_response.raise_for_status()
        organizations = org_response.json()

        analysis_type = "VARIANT_FREQUENCY" if args.analysis == "variant" else "THERAPY_RESPONSE"
        criteria = {
            "min_age": 40,
            "max_age": 70,
            "sex": None,
            "disease_code": "DX-LUNG",
            "variant_code": "VAR-A",
            "therapy_code": "THERAPY-A" if args.analysis == "therapy" else None,
        }
        payload = {
            "name": f"Demo {analysis_type}",
            "description": "PrecisionMPC coordinator workflow demonstration",
            "analysis_type": analysis_type,
            "organization_ids": [o["id"] for o in organizations],
            "criteria": criteria,
        }

        create = client.post("/api/studies", json=payload, headers=headers(researcher))
        create.raise_for_status()
        study = create.json()
        print(f"Study created: {study['id']} ({study['status']})")

        approve_all(client, study["id"])

        run = client.post(f"/api/studies/{study['id']}/run", headers=headers(researcher))
        run.raise_for_status()
        body = run.json()
        print("\nSecure computation completed")
        print("Session:", body["session_id"])
        print("Result:", body["result"])

        audit = client.get("/api/audit", params={"study_id": study["id"]}, headers=headers(researcher))
        audit.raise_for_status()
        print("\nAudit events:")
        for event in reversed(audit.json()):
            print(" -", event["event_type"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
