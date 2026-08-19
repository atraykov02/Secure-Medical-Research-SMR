"""Run this after starting docker-compose.hospital-demo.yml.

It temporarily acts as the future central coordinator: it creates the same MPC
session on all three hospital nodes, asks each hospital to query its own local
medical database and secret-share the aggregates, then reconstructs only the
explicitly authorized final result shares.
"""
from __future__ import annotations

import httpx

from bgw import DEFAULT_PRIME, Share, reconstruct_result

NODES = {
    1: "http://localhost:8101",
    2: "http://localhost:8102",
    3: "http://localhost:8103",
}
HEADERS = {"X-MPC-Service-Token": "precision-mpc-demo-token"}


def reconstruct(client: httpx.Client, path_template: str, names: list[str]) -> dict[str, int]:
    collected = {name: [] for name in names}
    for url in NODES.values():
        response = client.get(url + path_template, headers=HEADERS)
        response.raise_for_status()
        for item in response.json()["shares"]:
            collected[item["name"]].append(Share(x=int(item["x"]), y=int(item["value"])))
    return {
        name: reconstruct_result(
            prime=DEFAULT_PRIME,
            threshold=1,
            shares=shares,
        )
        for name, shares in collected.items()
    }


def create_session(client: httpx.Client, session_id: str) -> None:
    for participant_id, url in NODES.items():
        payload = {
            "session_id": session_id,
            "participant_id": participant_id,
            "participant_ids": [1, 2, 3],
            "peer_urls": NODES,
            "threshold": 1,
            "prime": DEFAULT_PRIME,
        }
        client.post(url + "/api/mpc/sessions", json=payload, headers=HEADERS).raise_for_status()


def main() -> None:
    with httpx.Client(timeout=15.0) as client:
        # Variant frequency
        create_session(client, "demo-variant")
        analysis = {
            "session_id": "demo-variant",
            "criteria": {
                "min_age": 40,
                "max_age": 70,
                "disease_code": "DX-LUNG",
                "variant_code": "VAR-A",
                "therapy_code": None,
                "sex": None,
            },
        }
        for url in NODES.values():
            client.post(
                url + "/api/analyses/variant-frequency/share-local-inputs",
                json=analysis,
                headers=HEADERS,
            ).raise_for_status()
        for url in NODES.values():
            client.post(
                url + "/api/analyses/variant-frequency/build",
                json={"session_id": "demo-variant"},
                headers=HEADERS,
            ).raise_for_status()

        result = reconstruct(
            client,
            "/api/analyses/variant-frequency/demo-variant/result-share",
            ["variant_total", "cohort_total"],
        )
        frequency = 100 * result["variant_total"] / result["cohort_total"]
        print("Variant Frequency:", result, f"{frequency:.2f}%")

        # Therapy response association
        create_session(client, "demo-therapy")
        analysis["session_id"] = "demo-therapy"
        analysis["criteria"]["therapy_code"] = "THERAPY-A"
        for url in NODES.values():
            client.post(
                url + "/api/analyses/therapy-response/share-local-inputs",
                json=analysis,
                headers=HEADERS,
            ).raise_for_status()
        for url in NODES.values():
            client.post(
                url + "/api/analyses/therapy-response/build",
                json={"session_id": "demo-therapy"},
                headers=HEADERS,
            ).raise_for_status()
        for url in NODES.values():
            client.post(
                url + "/api/analyses/therapy-response/start-multiplication",
                json={"session_id": "demo-therapy"},
                headers=HEADERS,
            ).raise_for_status()
        for url in NODES.values():
            client.post(
                url + "/api/analyses/therapy-response/finalize-multiplication",
                json={"session_id": "demo-therapy"},
                headers=HEADERS,
            ).raise_for_status()

        result = reconstruct(
            client,
            "/api/analyses/therapy-response/demo-therapy/result-share",
            ["AD", "BC"],
        )
        odds_ratio = result["AD"] / result["BC"] if result["BC"] else None
        print("Therapy Response:", result, "OR =", odds_ratio)


if __name__ == "__main__":
    main()
