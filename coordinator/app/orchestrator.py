from __future__ import annotations

from dataclasses import dataclass

import httpx

from bgw.field import PrimeField
from bgw.models import Share
from bgw.shamir import shamir_reconstruct

from .models import AnalysisType, Organization, Study


@dataclass(frozen=True)
class NodeTarget:
    participant_index: int
    organization_id: str
    organization_name: str
    node_url: str


class HospitalNodeClient:
    def __init__(self, *, service_token: str, timeout_seconds: float):
        self.service_token = service_token
        self.timeout_seconds = timeout_seconds

    @property
    def headers(self) -> dict[str, str]:
        return {"X-MPC-Service-Token": self.service_token}

    async def request(self, method: str, target: NodeTarget, path: str, *, json: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(
                method,
                f"{target.node_url.rstrip('/')}{path}",
                headers=self.headers,
                json=json,
            )
        response.raise_for_status()
        if response.content:
            return response.json()
        return {}


class MPCOrchestrator:
    def __init__(self, *, service_token: str, timeout_seconds: float, prime: int, threshold: int):
        self.client = HospitalNodeClient(service_token=service_token, timeout_seconds=timeout_seconds)
        self.prime = prime
        self.threshold = threshold

    @staticmethod
    def targets_for_study(study: Study) -> list[NodeTarget]:
        targets: list[NodeTarget] = []
        for participant in sorted(study.participants, key=lambda p: p.participant_index):
            org: Organization = participant.organization
            if not org.node_url:
                raise RuntimeError(f"organization {org.name} has no hospital node URL")
            targets.append(NodeTarget(
                participant_index=participant.participant_index,
                organization_id=org.id,
                organization_name=org.name,
                node_url=org.node_url,
            ))
        if not 3 <= len(targets) <= 6:
            raise RuntimeError("a study requires between three and six hospital nodes")
        return targets

    @staticmethod
    def threshold_for_participant_count(participant_count: int) -> int:
        if not 3 <= participant_count <= 6:
            raise ValueError("participant count must be between 3 and 6")
        return (participant_count - 1) // 2

    @staticmethod
    def criteria_payload(study: Study) -> dict:
        c = study.criteria
        return {
            "min_age": c.min_age,
            "max_age": c.max_age,
            "sex": c.sex,
            "disease_code": c.disease_code,
            "variant_code": c.variant_code,
            "therapy_code": c.therapy_code,
        }

    async def create_sessions(self, session_id: str, targets: list[NodeTarget], *, threshold: int, demonstration_trace: bool = False) -> None:
        participant_ids = [t.participant_index for t in targets]
        peer_urls = {t.participant_index: t.node_url for t in targets}
        for target in targets:
            payload = {
                "session_id": session_id,
                "participant_id": target.participant_index,
                "participant_ids": participant_ids,
                "peer_urls": peer_urls,
                "threshold": threshold,
                "prime": self.prime,
                "demonstration_trace": demonstration_trace,
            }
            await self.client.request("POST", target, "/api/mpc/sessions", json=payload)

    async def destroy_sessions(self, session_id: str, targets: list[NodeTarget]) -> None:
        for target in targets:
            try:
                await self.client.request("DELETE", target, f"/api/mpc/sessions/{session_id}")
            except Exception:
                # Cleanup is best effort. The coordinator still records failures separately.
                pass

    async def _result_shares(self, session_id: str, targets: list[NodeTarget], path: str) -> dict[str, list[Share]]:
        shares_by_name: dict[str, list[Share]] = {}
        for target in targets:
            data = await self.client.request("GET", target, path.format(session_id=session_id))
            if data.get("participant_id") != target.participant_index:
                raise RuntimeError("hospital node returned an unexpected participant id")
            for item in data["shares"]:
                shares_by_name.setdefault(item["name"], []).append(
                    Share(x=int(item["x"]), y=int(item["value"]))
                )
        return shares_by_name

    def _reconstruct(self, shares: list[Share], threshold: int) -> int:
        if len(shares) < threshold + 1:
            raise RuntimeError("not enough result shares for reconstruction")
        return shamir_reconstruct(PrimeField(self.prime), shares)

    async def run_variant_frequency(self, study: Study, session_id: str, targets: list[NodeTarget], threshold: int) -> dict:
        request = {"session_id": session_id, "criteria": self.criteria_payload(study)}
        for target in targets:
            await self.client.request(
                "POST", target, "/api/analyses/variant-frequency/share-local-inputs", json=request
            )
        for target in targets:
            await self.client.request(
                "POST", target, "/api/analyses/variant-frequency/build", json={"session_id": session_id}
            )
        shares = await self._result_shares(
            session_id, targets, "/api/analyses/variant-frequency/{session_id}/result-share"
        )
        variant_total = self._reconstruct(shares["variant_total"], threshold)
        cohort_total = self._reconstruct(shares["cohort_total"], threshold)
        frequency = (variant_total / cohort_total * 100.0) if cohort_total else None
        return {
            "cohort_size": cohort_total,
            "variant_count": variant_total,
            "frequency_percent": round(frequency, 4) if frequency is not None else None,
        }

    async def run_therapy_response(self, study: Study, session_id: str, targets: list[NodeTarget], threshold: int) -> dict:
        request = {"session_id": session_id, "criteria": self.criteria_payload(study)}
        for target in targets:
            await self.client.request(
                "POST", target, "/api/analyses/therapy-response/share-local-inputs", json=request
            )
        for target in targets:
            await self.client.request(
                "POST", target, "/api/analyses/therapy-response/build", json={"session_id": session_id}
            )
        for target in targets:
            await self.client.request(
                "POST", target, "/api/analyses/therapy-response/start-multiplication", json={"session_id": session_id}
            )
        for target in targets:
            await self.client.request(
                "POST", target, "/api/analyses/therapy-response/finalize-multiplication", json={"session_id": session_id}
            )
        shares = await self._result_shares(
            session_id, targets, "/api/analyses/therapy-response/{session_id}/result-share"
        )
        # AD and BC are reconstructed only transiently to derive the final odds ratio.
        # They are deliberately not returned/persisted as study results.
        ad = self._reconstruct(shares["AD"], threshold)
        bc = self._reconstruct(shares["BC"], threshold)
        cohort_total = self._reconstruct(shares["therapy_cohort_total"], threshold)
        odds_ratio = (ad / bc) if bc else None
        return {
            "cohort_size": cohort_total,
            "odds_ratio": round(odds_ratio, 6) if odds_ratio is not None else None,
        }

    async def run_secure_sum(self, study: Study, session_id: str, targets: list[NodeTarget], threshold: int) -> dict:
        analysis = study.analysis_type.value
        request = {"session_id": session_id, "criteria": self.criteria_payload(study)}
        for target in targets:
            await self.client.request("POST", target, f"/api/analyses/secure-sum/{analysis}/share-local-inputs", json=request)
        for target in targets:
            await self.client.request("POST", target, f"/api/analyses/secure-sum/{analysis}/build", json={"session_id": session_id})
        shares = await self._result_shares(session_id, targets, f"/api/analyses/secure-sum/{analysis}/{{session_id}}/result-share")
        if study.analysis_type == AnalysisType.ALLELE_FREQUENCY:
            value, count = self._reconstruct(shares["alternative_allele_total"], threshold), self._reconstruct(shares["cohort_total"], threshold)
            return {"cohort_size": count, "alternative_allele_count": value,
                    "allele_frequency_percent": round(value / (2 * count) * 100, 4) if count else None}
        if study.analysis_type == AnalysisType.COHORT_MEAN_AGE:
            value, count = self._reconstruct(shares["age_sum_total"], threshold), self._reconstruct(shares["cohort_total"], threshold)
            return {"cohort_size": count, "mean_age": round(value / count, 4) if count else None}
        value, count = self._reconstruct(shares["responder_total"], threshold), self._reconstruct(shares["treated_total"], threshold)
        return {"cohort_size": count, "treated_count": count, "responder_count": value,
                "response_rate_percent": round(value / count * 100, 4) if count else None}

    async def run_variant_disease_association(self, study: Study, session_id: str, targets: list[NodeTarget], threshold: int) -> dict:
        request = {"session_id": session_id, "criteria": self.criteria_payload(study)}
        for target in targets:
            await self.client.request("POST", target, "/api/analyses/association/VARIANT_DISEASE_ASSOCIATION/share-local-inputs", json=request)
        # The circuit after local A/B/C/D creation is deliberately identical to the existing association.
        for target in targets:
            await self.client.request("POST", target, "/api/analyses/therapy-response/build", json={"session_id": session_id})
        for target in targets:
            await self.client.request("POST", target, "/api/analyses/therapy-response/start-multiplication", json={"session_id": session_id})
        for target in targets:
            await self.client.request("POST", target, "/api/analyses/therapy-response/finalize-multiplication", json={"session_id": session_id})
        shares = await self._result_shares(session_id, targets, "/api/analyses/therapy-response/{session_id}/result-share")
        ad, bc = self._reconstruct(shares["AD"], threshold), self._reconstruct(shares["BC"], threshold)
        count = self._reconstruct(shares["therapy_cohort_total"], threshold)
        return {"cohort_size": count, "odds_ratio": round(ad / bc, 6) if bc else None}

    async def run(self, study: Study, session_id: str) -> dict:
        targets = self.targets_for_study(study)
        threshold = self.threshold_for_participant_count(len(targets))
        demo = study.study_mode == "DEMONSTRATION"
        await self.create_sessions(session_id, targets, threshold=threshold, demonstration_trace=demo)
        if study.analysis_type == AnalysisType.VARIANT_FREQUENCY:
            result = await self.run_variant_frequency(study, session_id, targets, threshold)
        elif study.analysis_type == AnalysisType.THERAPY_RESPONSE:
            result = await self.run_therapy_response(study, session_id, targets, threshold)
        elif study.analysis_type in (AnalysisType.ALLELE_FREQUENCY, AnalysisType.COHORT_MEAN_AGE, AnalysisType.THERAPY_RESPONSE_RATE):
            result = await self.run_secure_sum(study, session_id, targets, threshold)
        elif study.analysis_type == AnalysisType.VARIANT_DISEASE_ASSOCIATION:
            result = await self.run_variant_disease_association(study, session_id, targets, threshold)
        else:
            raise RuntimeError(f"unsupported analysis type: {study.analysis_type}")
        if demo:
            result["_demonstration_trace"] = [
                await self.client.request("GET", target, f"/api/mpc/sessions/{session_id}/demonstration-trace")
                for target in targets
            ]
        return result

    async def collect_demo_plaintext_inputs(self, study: Study) -> list[dict]:
        targets = self.targets_for_study(study)
        payload = {
            "analysis_type": study.analysis_type.value,
            "criteria": self.criteria_payload(study),
            "data_source": "SYNTHETIC",
        }
        results = []
        for target in targets:
            result = await self.client.request(
                "POST", target, f"/api/verification/studies/{study.id}/local-input", json=payload
            )
            # The node has a permanent infrastructure index, while P1...Pn are
            # session-local BGW roles assigned by the coordinator.
            result["participant_id"] = target.participant_index
            result["organization"] = target.organization_name
            results.append(result)
        return results
