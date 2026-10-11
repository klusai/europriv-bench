"""Strict HTTP contract and content pin for the kOS Shield service (RES-122).

No detector runs here. The inventory fingerprint binds the operators/postprocessing read
from the service mirror; attestation binds the executing source, dependencies and models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

OPERATORS = [["DEFAULT", "replace", "{}"]]
POSTPROCESS = ["trim", "merge", "addr-digit", "cut-between-words"]
IDENTITY_FIELDS = (
    "webos_sha",
    "source_sha256",
    "requirements_sha256",
    "resolved_dependencies",
    "resolved_dependencies_sha256",
    "language",
    "recognizer_set",
    "threshold",
    "models",
    "requested_accelerator",
    "resolved_accelerator",
    "workers",
    "worker_enforcement",
    "max_concurrency",
    "os",
    "architecture",
)


class ShieldError(RuntimeError):
    """A service failure or drift must abort scoring, never become all-O predictions."""


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _http(base_url: str, path: str, payload: dict | None = None, *, expected_process: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if expected_process is not None:
        # Ask the service to enforce its single-process lock on inference too.
        headers["X-Benchmark-Run-Id"] = str(uuid4())
    request = Request(
        base_url + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers=headers,
    )
    with urlopen(request, timeout=300) as response:
        if expected_process is not None and response.headers.get("X-Presidio-Process-Instance-Id") != expected_process:
            raise ShieldError("Shield batch came from a different/unattested process")
        data = json.load(response)
    if not isinstance(data, dict):
        raise ShieldError("Shield response must be a JSON object")
    return data


def _identity(attestation: dict) -> dict:
    if attestation.get("ready") is not True or attestation.get("missing") != []:
        raise ShieldError("Shield attestation is not ready/complete")
    if any(key not in attestation for key in IDENTITY_FIELDS):
        raise ShieldError("Shield attestation lacks identity fields")
    for field, length in (
        ("webos_sha", 40),
        ("source_sha256", 64),
        ("requirements_sha256", 64),
        ("resolved_dependencies_sha256", 64),
    ):
        if not re.fullmatch(rf"[0-9a-f]{{{length}}}", str(attestation[field])):
            raise ShieldError(f"Shield invalid {field}")
    return {key: attestation[key] for key in IDENTITY_FIELDS}


def _validate_config(config: dict, language: str) -> None:
    inventory = config["inventory"]
    identity = config["identity"]
    payload = {
        "language": language,
        "threshold": inventory["threshold"],
        "recognizers": sorted(inventory["recognizers"], key=lambda e: (e["name"], e["class"])),
        "operators": config["operators"],
        "postprocess": config["postprocess"],
    }
    expected = f"{language}:{_digest(payload)[:12]}"
    if inventory["language"] != language or identity["language"] != language:
        raise ShieldError("Shield pin language mismatch")
    if inventory["recognizer_set"] != expected or identity["recognizer_set"] != expected:
        raise ShieldError("Shield fingerprint does not bind the declared recognizers/operators/postprocess")
    if identity["threshold"] != inventory["threshold"]:
        raise ShieldError("Shield threshold mismatch")
    _identity({**identity, "ready": True, "missing": []})


def capture_pin(base_url: str) -> dict:
    """Capture an auditable pin BEFORE scoring; review/save it, then use that exact file."""
    configs = {}
    for language in ("en", "nl"):
        query = "?" + urlencode({"language": language})
        configs[language] = {
            "identity": _identity(_http(base_url, "/benchmark-attestation" + query)),
            "inventory": _http(base_url, "/recognizers" + query),
            "operators": deepcopy(OPERATORS),
            "postprocess": POSTPROCESS.copy(),
        }
        _validate_config(configs[language], language)
    return {"schema": "europriv-shield-pin/v1", "languages": configs}


class ShieldClient:
    def __init__(self, base_url: str | None, pin: dict | None, batch_size: int) -> None:
        self.base_url = (base_url or os.environ.get("EUROPRIV_SHIELD_URL", "")).rstrip("/")
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.query or parsed.fragment:
            raise ValueError("Set EUROPRIV_SHIELD_URL to the service HTTP base URL")
        if pin is None:
            path = os.environ.get("EUROPRIV_SHIELD_PIN")
            if not path:
                raise ValueError("Set EUROPRIV_SHIELD_PIN to a reviewed service pin JSON")
            pin = json.loads(Path(path).read_text())
        self.pin = deepcopy(pin)
        if self.pin.get("schema") != "europriv-shield-pin/v1":
            raise ShieldError("Unsupported Shield pin schema")
        for language in ("en", "nl"):
            _validate_config(self.pin["languages"][language], language)
        if type(batch_size) is not int or not 1 <= batch_size <= 64:
            raise ValueError("Shield batch size must be 1..64")
        self.batch_size = batch_size
        self.language = "nl"
        self.pin_sha256 = _digest(self.pin)
        self.model_id = "klusai/kos-shield@" + self.pin_sha256

    @property
    def resolved_language(self) -> str:
        code = (self.language or "nl").split("-")[0].lower()
        return code if code in {"en", "nl"} else "nl"

    def provenance(self) -> dict:
        return deepcopy(
            {
                "pin_sha256": self.pin_sha256,
                **self.pin["languages"][self.resolved_language],
                "requested_language": self.language,
                "resolved_language": self.resolved_language,
                "request": {"entities": None, "whitelist": None, "pseudonymize": False, "salt": ""},
                "endpoint": "/anonymize-batch",
                "batch_size": self.batch_size,
                "client_chunking": "none; service owns document offsets and internal splitting",
            }
        )

    def _verify_service(self) -> str:
        query = "?" + urlencode({"language": self.language})
        actual = _http(self.base_url, "/benchmark-attestation" + query)
        config = self.pin["languages"][self.resolved_language]
        if _identity(actual) != config["identity"]:
            raise ShieldError("Shield service identity drifted from pin")
        inventory = _http(self.base_url, "/recognizers" + query)
        if inventory != config["inventory"]:
            raise ShieldError("Shield recognizer inventory drifted from pin")
        instance = actual.get("process_instance_id")
        if not isinstance(instance, str) or not instance:
            raise ShieldError("Shield attestation lacks process identity")
        return instance

    def analyze(self, texts: list[str]) -> list[dict]:
        if not texts:
            return []
        instance = self._verify_service()
        expected_set = self.pin["languages"][self.resolved_language]["inventory"]["recognizer_set"]
        out = []
        for offset in range(0, len(texts), self.batch_size):
            batch = texts[offset : offset + self.batch_size]
            data = _http(
                self.base_url,
                "/anonymize-batch",
                {
                    "texts": batch,
                    "language": self.language,
                    "entities": None,
                    "whitelist": None,
                    "pseudonymize": False,
                    "salt": "",
                },
                expected_process=instance,
            )
            if data.get("recognizer_set") != expected_set:
                raise ShieldError("Shield response recognizer fingerprint differs from pin")
            results = data.get("results")
            if not isinstance(results, list) or len(results) != len(batch):
                raise ShieldError("Shield batch cardinality mismatch")
            for index, (text, result) in enumerate(zip(batch, results, strict=True)):
                if not isinstance(result, dict) or type(result.get("index")) is not int or result["index"] != index:
                    raise ShieldError("Shield batch index/order mismatch")
                if result.get("failed") is not False:
                    raise ShieldError(f"Shield failed batch item {offset + index}")
                if not isinstance(result.get("text"), str) or not isinstance(result.get("items"), list):
                    raise ShieldError("Shield batch item lacks text/items")
                for item in result["items"]:
                    if not isinstance(item, dict):
                        raise ShieldError("Shield entity must be an object")
                    start, end, score = item.get("start"), item.get("end"), item.get("score")
                    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
                        raise ShieldError("Shield entity has invalid input character offsets")
                    if item.get("text") != text[start:end]:
                        raise ShieldError("Shield entity text does not match input offsets")
                    if not isinstance(item.get("entity_type"), str) or not item["entity_type"]:
                        raise ShieldError("Shield entity lacks a type")
                    if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
                        raise ShieldError("Shield entity has invalid confidence")
                out.append(result)
        if self._verify_service() != instance:
            raise ShieldError("Shield process changed during scoring")
        return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture the local Shield service content pin before evaluation")
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    pin = capture_pin(args.url.rstrip("/"))
    with args.out.open("x") as file:
        json.dump(pin, file, indent=2, ensure_ascii=False)
        file.write("\n")


if __name__ == "__main__":
    main()
