"""HTTP contract tests: no service/model dependencies, no network."""

import io
import json
from copy import deepcopy
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from europriv_bench import shield
from europriv_bench.adapters import BUILDERS, PresidioAdapter, ShieldAdapter
from europriv_bench.leaderboard import build_leaderboard
from europriv_bench.runner import run_spec
from europriv_bench.spec import EvalSpec
from europriv_bench.taxonomy import ENTITY_NAMES


@pytest.fixture
def wire(monkeypatch):
    pin = {"schema": "europriv-shield-pin/v1", "languages": {}}
    for language in ("en", "nl"):
        inventory = {
            "language": language,
            "threshold": 0.8,
            "recognizers": [
                {"name": "TestRecognizer", "class": "TestRecognizer", "entities": ["PERSON"]},
            ],
        }
        fingerprint = (
            language
            + ":"
            + shield._digest(
                {
                    **inventory,
                    "operators": shield.OPERATORS,
                    "postprocess": shield.POSTPROCESS,
                }
            )[:12]
        )
        inventory["recognizer_set"] = fingerprint
        identity = {
            "webos_sha": "a" * 40,
            "source_sha256": "b" * 64,
            "requirements_sha256": "c" * 64,
            "resolved_dependencies": {"presidio-analyzer": "2.2.364"},
            "resolved_dependencies_sha256": "d" * 64,
            "language": language,
            "recognizer_set": fingerprint,
            "threshold": 0.8,
            "models": {"spacy": {"revision": "3.8.0"}},
            "requested_accelerator": "cpu",
            "resolved_accelerator": "cpu",
            "workers": 1,
            "worker_enforcement": "exclusive-process-lock",
            "max_concurrency": 1,
            "os": "Darwin",
            "architecture": "arm64",
        }
        pin["languages"][language] = {
            "inventory": inventory,
            "identity": identity,
            "operators": deepcopy(shield.OPERATORS),
            "postprocess": shield.POSTPROCESS.copy(),
        }
    state = {"calls": [], "mutate": lambda data, path: None, "pin": pin}

    def urlopen(request, timeout):
        assert timeout == 300
        parsed = urlsplit(request.full_url)
        payload = json.loads(request.data) if request.data else None
        state["calls"].append((parsed.path, payload))
        language = (payload or parse_qs(parsed.query)).get("language", "nl")
        if isinstance(language, list):
            language = language[0]
        language = language.split("-")[0].lower()
        language = language if language in ("nl", "en") else "nl"
        config = pin["languages"][language]
        if parsed.path == "/benchmark-attestation":
            data = {**config["identity"], "ready": True, "missing": [], "process_instance_id": "process-one"}
        elif parsed.path == "/recognizers":
            data = deepcopy(config["inventory"])
        else:
            assert parsed.path == "/anonymize-batch"
            assert payload["entities"] is None and payload["whitelist"] is None
            assert payload["pseudonymize"] is False and payload["salt"] == ""
            results = []
            for index, text in enumerate(payload["texts"]):
                items = []
                for value, label in (
                    ("Ștefan", "PERSON"),
                    ("123456789", "NL_BSN"),
                    ("Acme", "ORGANIZATION"),
                    ("1234 AB", "NL_POSTAL_CODE"),
                ):
                    start = text.find(value)
                    if start >= 0:
                        items.append(
                            {
                                "start": start,
                                "end": start + len(value),
                                "text": value,
                                "entity_type": label,
                                "score": 0.91,
                            }
                        )
                results.append({"index": index, "text": "<service output>", "items": items, "failed": False})
            data = {"results": results, "recognizer_set": config["inventory"]["recognizer_set"]}
        state["mutate"](data, parsed.path)
        response = io.BytesIO(json.dumps(data).encode())
        response.headers = {"X-Presidio-Process-Instance-Id": state.get("response_process", "process-one")}
        if parsed.path == "/anonymize-batch":
            assert request.has_header("X-benchmark-run-id")
        return response

    monkeypatch.setattr(shield, "urlopen", urlopen)
    return state


def adapter(wire, **kwargs):
    return ShieldAdapter("http://127.0.0.1:11439", wire["pin"], **kwargs)


def test_full_batch_unicode_document_offsets_and_mapping(wire):
    a = adapter(wire, batch_size=2)
    a.prepare(["ro"])
    text = "🙂  Ștefan\n123456789 Acme 1234 AB"
    assert a.predict_tags([text, "", "plain"]) == [
        ["O", "S-PERSON", "S-NATIONAL_ID", "S-ORG_PARTY", "B-ADDRESS", "E-ADDRESS"],
        [],
        ["O"],
    ]
    posts = [payload for path, payload in wire["calls"] if path == "/anonymize-batch"]
    assert [p["texts"] for p in posts] == [[text, ""], ["plain"]]
    assert all(p["language"] == "ro" for p in posts)
    assert a.provenance()["service_provenance"]["resolved_language"] == "nl"
    assert set(a.SHIELD_TO_KP.values()) <= set(ENTITY_NAMES)


def test_long_document_offsets_are_not_redacted_text_offsets(wire):
    text = "filler " * 2400 + "Ștefan"
    assert adapter(wire).predict_tags([text])[0] == ["O"] * 2400 + ["S-PERSON"]
    assert [p for path, p in wire["calls"] if path == "/anonymize-batch"][0]["texts"] == [text]


def test_actual_service_anonymization_and_empty_call(wire):
    a = adapter(wire)
    assert a.predict_tags([]) == [] and wire["calls"] == []
    assert a.anonymize(["Ștefan"]) == ["<service output>"]
    with pytest.raises(NotImplementedError):
        a.pseudonymize(["Ștefan"])


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["results"].pop(),
        lambda d: d["results"].append(deepcopy(d["results"][0])),
        lambda d: d["results"].reverse(),
        lambda d: d["results"][1].update(index=0),
        lambda d: d["results"][0].update(index=False),
        lambda d: d["results"][1].update(failed=True),
        lambda d: [r.update(failed=True) for r in d["results"]],
        lambda d: d["results"][0].pop("failed"),
        lambda d: d["results"][0].pop("items"),
        lambda d: d["results"][0].update(items=None),
        lambda d: d["results"][0].update(text=None),
        lambda d: d.update(recognizer_set="nl:drift"),
    ],
)
def test_failed_or_malformed_batch_aborts_whole_call(wire, change):
    wire["mutate"] = lambda d, path: change(d) if path == "/anonymize-batch" else None
    with pytest.raises(shield.ShieldError):
        adapter(wire).predict_tags(["Ștefan", "Acme"])


@pytest.mark.parametrize(
    "change",
    [
        {"start": -1},
        {"end": 999},
        {"start": 4, "end": 4},
        {"start": True},
        {"end": 1.2},
        {"text": "wrong"},
        {"score": float("nan")},
        {"score": 1.1},
        {"entity_type": None},
    ],
)
def test_invalid_entity_offsets_never_silently_become_tags(wire, change):
    def mutate(data, path):
        if path == "/anonymize-batch":
            data["results"][0]["items"][0].update(change)

    wire["mutate"] = mutate
    with pytest.raises(shield.ShieldError):
        adapter(wire).predict_tags(["🙂 Ștefan"])


@pytest.mark.parametrize(
    "error", [URLError("offline"), HTTPError("http://local", 500, "failed", {}, None), TimeoutError("timed out")]
)
def test_http_failure_propagates(wire, monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(shield, "urlopen", fail)
    with pytest.raises(type(error)):
        adapter(wire).predict_tags(["Ștefan"])


@pytest.mark.parametrize("field,value", [("source_sha256", "e" * 64), ("threshold", 0.7), ("ready", False)])
def test_service_drift_refused_before_inference(wire, field, value):
    wire["mutate"] = lambda d, path: d.update({field: value}) if path == "/benchmark-attestation" else None
    with pytest.raises(shield.ShieldError):
        adapter(wire).predict_tags(["Ștefan"])
    assert not any(path == "/anonymize-batch" for path, _ in wire["calls"])


def test_restart_after_inference_refused(wire):
    def mutate(data, path):
        if path == "/benchmark-attestation" and any(p == "/anonymize-batch" for p, _ in wire["calls"]):
            data["process_instance_id"] = "restarted"

    wire["mutate"] = mutate
    with pytest.raises(shield.ShieldError, match="process changed"):
        adapter(wire).predict_tags(["Ștefan"])


def test_operator_pin_tampering_and_capture(wire):
    assert shield.capture_pin("http://local") == wire["pin"]
    wire["pin"]["languages"]["nl"]["operators"] = [["DEFAULT", "keep", "{}"]]
    with pytest.raises(shield.ShieldError, match="fingerprint"):
        adapter(wire)


def test_runner_provenance_and_board_keep_stock_separate(wire):
    a = adapter(wire)
    spec = EvalSpec.from_yaml("evaluations/pii-detection-en.yaml")
    row = run_spec(spec, a, gold=(["Ștefan"], [["S-PERSON"]]))
    assert row["scores"]["entity_f1"]["f1"] == 1
    provenance = row["service_provenance"]
    assert provenance["identity"]["webos_sha"] == "a" * 40
    assert provenance["inventory"]["threshold"] == 0.8
    assert provenance["operators"] == shield.OPERATORS
    assert provenance["resolved_language"] == "en"
    assert provenance["entity_mapping"]["NL_BSN"] == "NATIONAL_ID"
    board = build_leaderboard([row, {"adapter": "presidio", "model_id": PresidioAdapter.model_id}])
    assert len(board["entries"]) == 2
    assert BUILDERS["shield"] is ShieldAdapter
    assert BUILDERS["presidio"] is PresidioAdapter
    saved = deepcopy(row)
    a.prepare(["pl"])
    assert row == saved


def test_environment_configuration(wire, monkeypatch, tmp_path):
    path = tmp_path / "pin.json"
    path.write_text(json.dumps(wire["pin"]))
    monkeypatch.setenv("EUROPRIV_SHIELD_URL", "http://127.0.0.1:11439/")
    monkeypatch.setenv("EUROPRIV_SHIELD_PIN", str(path))
    assert ShieldAdapter().model_id.startswith("klusai/kos-shield@")
    with pytest.raises(ValueError):
        adapter(wire, batch_size=65)
    with pytest.raises(ValueError):
        adapter(wire).prepare(["ro", "pl"])


def test_two_spans_in_one_token_use_shared_alignment(wire):
    # Service spans are exact; the harness token grid owns punctuation collisions.
    assert adapter(wire).predict_tags(["Ștefan/123456789"]) == [["S-PERSON"]]


def test_later_batch_failure_does_not_return_partial_predictions(wire):
    def mutate(data, path):
        posted = sum(p == "/anonymize-batch" for p, _ in wire["calls"])
        if path == "/anonymize-batch" and posted == 2:
            data["results"][0]["failed"] = True

    wire["mutate"] = mutate
    with pytest.raises(shield.ShieldError, match="failed batch item 1"):
        adapter(wire, batch_size=1).predict_tags(["Ștefan", "Ștefan"])


def test_unknown_native_type_is_validated_but_not_mislabeled(wire):
    def mutate(data, path):
        if path == "/anonymize-batch":
            data["results"][0]["items"][0]["entity_type"] = "ABBREVIATION"

    wire["mutate"] = mutate
    assert adapter(wire).predict_tags(["Ștefan"]) == [["O"]]


def test_inventory_drift_is_refused_even_with_same_fingerprint(wire):
    def mutate(data, path):
        if path == "/recognizers":
            data["recognizers"] = []

    wire["mutate"] = mutate
    with pytest.raises(shield.ShieldError, match="inventory drifted"):
        adapter(wire).predict_tags(["Ștefan"])


def test_real_http_json_decode_failure_is_not_a_clean_prediction(wire, monkeypatch):
    monkeypatch.setattr(shield, "urlopen", lambda *args, **kwargs: io.BytesIO(b"not-json"))
    with pytest.raises(json.JSONDecodeError):
        adapter(wire).predict_tags(["Ștefan"])


def test_recorded_service_pin_is_self_consistent():
    from pathlib import Path

    pin = json.loads(Path("baselines/shield-service-pin.json").read_text())
    a = ShieldAdapter("http://127.0.0.1:11439", pin)
    assert a.model_id.endswith(shield._digest(pin))
    identities = [config["identity"] for config in pin["languages"].values()]
    assert len({identity["webos_sha"] for identity in identities}) == 1
    assert len({identity["source_sha256"] for identity in identities}) == 1


@pytest.mark.parametrize("process", [None, "another-worker"])
def test_batch_must_come_from_the_attested_process(wire, process):
    wire["response_process"] = process
    with pytest.raises(shield.ShieldError, match="unattested process"):
        adapter(wire).predict_tags(["Ștefan"])
