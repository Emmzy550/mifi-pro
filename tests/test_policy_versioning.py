from copy import deepcopy

import pytest

from utils import policy_config
from utils.db import Database


class _FakeSnapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = deepcopy(data) if data is not None else None
        self.exists = data is not None

    def to_dict(self):
        return deepcopy(self._data) if self._data is not None else None


class _FakeDocumentRef:
    def __init__(self, store, doc_id):
        self._store = store
        self._doc_id = doc_id

    def get(self):
        return _FakeSnapshot(self._doc_id, self._store.get(self._doc_id))

    def set(self, payload):
        self._store[self._doc_id] = deepcopy(payload)


class _FakeQuery:
    def __init__(self, store, field, value):
        self._store = store
        self._field = field
        self._value = value

    def stream(self):
        return [
            _FakeSnapshot(doc_id, payload)
            for doc_id, payload in self._store.items()
            if payload.get(self._field) == self._value
        ]


class _FakeCollection:
    def __init__(self, collections, name):
        self._store = collections.setdefault(name, {})

    def document(self, doc_id):
        return _FakeDocumentRef(self._store, doc_id)

    def where(self, field, _op, value):
        return _FakeQuery(self._store, field, value)


class _FakeDB:
    def __init__(self):
        self._collections = {}

    def collection(self, name):
        return _FakeCollection(self._collections, name)


@pytest.fixture
def fake_db(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(Database, "get_db", classmethod(lambda cls: db))
    return db


def _seed_version(fake_db, version_id, *, status, org_id="ORG-TEST", values=None):
    payload = {
        "id": version_id,
        "organization_id": org_id,
        "status": status,
        "values": values or {"policy_version_label": "v1"},
        "updated_at": "2026-03-30T00:00:00+00:00",
        "updated_by": "seed@example.com",
    }
    fake_db.collection("policy_versions").document(version_id).set(payload)
    return payload


def test_update_policy_draft_rejects_non_draft_versions(fake_db):
    _seed_version(fake_db, "POLICY-ACTIVE", status="ACTIVE")

    with pytest.raises(ValueError, match="Only draft versions can be updated"):
        policy_config.update_policy_draft(
            "POLICY-ACTIVE",
            "ORG-TEST",
            "admin@example.com",
            {"risk_low_max": 0.25},
        )


@pytest.mark.parametrize(
    ("starting_status", "target_status", "message"),
    [
        ("ACTIVE", "SUBMITTED", "Only draft versions can be submitted"),
        ("DRAFT", "APPROVED", "Only submitted versions can be approved"),
    ],
)
def test_set_policy_status_enforces_expected_transitions(fake_db, starting_status, target_status, message):
    _seed_version(fake_db, "POLICY-TRANSITION", status=starting_status)

    with pytest.raises(ValueError, match=message):
        policy_config.set_policy_status(
            "POLICY-TRANSITION",
            "ORG-TEST",
            target_status,
            "reviewer@example.com",
        )


def test_activate_policy_version_requires_approved_state(fake_db):
    _seed_version(fake_db, "POLICY-DRAFT", status="DRAFT")

    with pytest.raises(ValueError, match="Only approved versions can be activated"):
        policy_config.activate_policy_version(
            "POLICY-DRAFT",
            "ORG-TEST",
            "approver@example.com",
        )


def test_activate_policy_version_archives_existing_active_version(fake_db):
    _seed_version(fake_db, "POLICY-CURRENT", status="ACTIVE", values={"policy_version_label": "v-current"})
    _seed_version(fake_db, "POLICY-NEXT", status="APPROVED", values={"policy_version_label": "v-next"})

    activated = policy_config.activate_policy_version(
        "POLICY-NEXT",
        "ORG-TEST",
        "approver@example.com",
    )

    current = fake_db.collection("policy_versions").document("POLICY-CURRENT").get().to_dict()
    next_version = fake_db.collection("policy_versions").document("POLICY-NEXT").get().to_dict()
    policy_config_doc = fake_db.collection("policy_configs").document("ORG-TEST").get().to_dict()

    assert activated["status"] == "ACTIVE"
    assert current["status"] == "ARCHIVED"
    assert next_version["status"] == "ACTIVE"
    assert next_version["activated_by"] == "approver@example.com"
    assert policy_config_doc["active_version_id"] == "POLICY-NEXT"
    assert policy_config_doc["values"]["policy_version_label"] == "v-next"
