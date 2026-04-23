from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timezone

import config
import lending_config.capacity_config as cap_config
from utils.db import Database


def get_policy_defaults() -> Dict[str, Any]:
    return {
        "policy_version_label": "v1.5.0-duration-handling",
        "data_quality_refer_threshold": config.DATA_QUALITY_REFER_THRESHOLD,
        "min_monthly_income": config.MIN_MONTHLY_INCOME,
        "max_debt_to_income_ratio": config.MAX_DEBT_TO_INCOME_RATIO,
        "affordability_ratio_target": config.AFFORDABILITY_RATIO_TARGET,
        "risk_low_max": config.RISK_LEVEL_THRESHOLDS.get("LOW", (0.0, 0.3))[1],
        "risk_medium_max": config.RISK_LEVEL_THRESHOLDS.get("MEDIUM", (0.3, 0.6))[1],
        "risk_high_max": config.RISK_LEVEL_THRESHOLDS.get("HIGH", (0.6, 1.0))[1],
        "min_transaction_count": cap_config.MIN_TRANSACTION_COUNT,
        "min_capacity_threshold": cap_config.MIN_CAPACITY_THRESHOLD,
        "min_history_days": cap_config.MIN_HISTORY_DAYS,
        "starter_history_threshold_days": cap_config.STARTER_HISTORY_THRESHOLD_DAYS,
        "starter_deposit_threshold": cap_config.STARTER_DEPOSIT_THRESHOLD,
        "starter_loan_cap": cap_config.STARTER_LOAN_CAP,
        "min_duration_days": cap_config.MIN_DURATION_DAYS,
        "max_duration_days": cap_config.MAX_DURATION_DAYS,
        "starter_loan_max_duration_days": cap_config.STARTER_LOAN_MAX_DURATION_DAYS
    }


def validate_policy_values(values: Dict[str, Any]) -> None:
    required_ranges = {
        "data_quality_refer_threshold": (0.0, 1.0),
        "max_debt_to_income_ratio": (0.0, 1.0),
        "affordability_ratio_target": (0.0, 1.0),
        "risk_low_max": (0.0, 1.0),
        "risk_medium_max": (0.0, 1.0),
        "risk_high_max": (0.0, 1.0)
    }

    for key, bounds in required_ranges.items():
        if key in values:
            val = float(values[key])
            if val < bounds[0] or val > bounds[1]:
                raise ValueError(f"{key} must be between {bounds[0]} and {bounds[1]}.")

    low = float(values.get("risk_low_max", 0.3))
    med = float(values.get("risk_medium_max", 0.6))
    high = float(values.get("risk_high_max", 1.0))
    if not (low < med < high):
        raise ValueError("Risk thresholds must be ascending: low < medium < high.")

    if int(values.get("min_duration_days", 1)) > int(values.get("max_duration_days", 1)):
        raise ValueError("Minimum duration cannot exceed maximum duration.")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_policy_versions(org_id: str) -> List[Dict[str, Any]]:
    db = Database.get_db()
    try:
        docs = db.collection("policy_versions").where("organization_id", "==", org_id).stream()
    except Exception:
        docs = []
    versions = []
    for doc in docs:
        data = doc.to_dict()
        if not data:
            continue
        if "id" not in data:
            data["id"] = getattr(doc, "id", None)
        versions.append(data)
    versions.sort(key=lambda v: v.get("created_at") or "", reverse=True)
    return versions


def get_active_policy_version(org_id: str) -> Optional[Dict[str, Any]]:
    versions = list_policy_versions(org_id)
    for v in versions:
        if v.get("status") == "ACTIVE":
            return v
    return None


def create_policy_draft(org_id: str, created_by: str, values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    defaults = get_policy_defaults()
    active = get_active_policy_version(org_id)
    base_values = (active or {}).get("values") or {}
    draft_values = {**defaults, **base_values, **(values or {})}
    version_id = f"POLICY-{org_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    payload = {
        "id": version_id,
        "organization_id": org_id,
        "status": "DRAFT",
        "values": draft_values,
        "created_at": _now_iso(),
        "created_by": created_by,
        "updated_at": _now_iso(),
        "updated_by": created_by
    }
    Database.get_db().collection("policy_versions").document(version_id).set(payload)
    return payload


def update_policy_draft(version_id: str, org_id: str, updated_by: str, values: Dict[str, Any]) -> Dict[str, Any]:
    doc = Database.get_db().collection("policy_versions").document(version_id).get()
    if not doc.exists:
        raise ValueError("Policy version not found")
    stored = doc.to_dict() or {}
    if stored.get("organization_id") != org_id:
        raise ValueError("Cross-organization access denied")
    if stored.get("status") != "DRAFT":
        raise ValueError("Only draft versions can be updated")
    merged = {**(stored.get("values") or {}), **values}
    stored["values"] = merged
    stored["updated_at"] = _now_iso()
    stored["updated_by"] = updated_by
    Database.get_db().collection("policy_versions").document(version_id).set(stored)
    return stored


def set_policy_status(version_id: str, org_id: str, status: str, actor: str) -> Dict[str, Any]:
    doc = Database.get_db().collection("policy_versions").document(version_id).get()
    if not doc.exists:
        raise ValueError("Policy version not found")
    stored = doc.to_dict() or {}
    if stored.get("organization_id") != org_id:
        raise ValueError("Cross-organization access denied")
    current_status = stored.get("status")
    if status == "SUBMITTED" and current_status != "DRAFT":
        raise ValueError("Only draft versions can be submitted")
    if status == "APPROVED" and current_status != "SUBMITTED":
        raise ValueError("Only submitted versions can be approved")
    stored["status"] = status
    stored["updated_at"] = _now_iso()
    stored["updated_by"] = actor
    if status == "SUBMITTED":
        stored["submitted_at"] = _now_iso()
        stored["submitted_by"] = actor
    if status == "APPROVED":
        stored["approved_at"] = _now_iso()
        stored["approved_by"] = actor
    Database.get_db().collection("policy_versions").document(version_id).set(stored)
    return stored


def activate_policy_version(version_id: str, org_id: str, actor: str) -> Dict[str, Any]:
    db = Database.get_db()
    doc = db.collection("policy_versions").document(version_id).get()
    if not doc.exists:
        raise ValueError("Policy version not found")
    stored = doc.to_dict() or {}
    if stored.get("organization_id") != org_id:
        raise ValueError("Cross-organization access denied")
    if stored.get("status") != "APPROVED":
        raise ValueError("Only approved versions can be activated")

    # Archive existing active versions
    for v in list_policy_versions(org_id):
        if v.get("status") == "ACTIVE" and v.get("id") != version_id:
            v["status"] = "ARCHIVED"
            v["updated_at"] = _now_iso()
            v["updated_by"] = actor
            db.collection("policy_versions").document(v["id"]).set(v)

    stored["status"] = "ACTIVE"
    stored["activated_at"] = _now_iso()
    stored["activated_by"] = actor
    stored["updated_at"] = _now_iso()
    stored["updated_by"] = actor
    db.collection("policy_versions").document(version_id).set(stored)

    # Keep policy_configs in sync for legacy reads
    db.collection("policy_configs").document(org_id).set({
        "values": stored.get("values") or {},
        "updated_at": stored.get("updated_at"),
        "updated_by": actor,
        "source": "versioned",
        "active_version_id": version_id
    })
    return stored


def get_policy_for_org(org_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    defaults = get_policy_defaults()
    active = get_active_policy_version(org_id)
    if active:
        values = {**defaults, **(active.get("values") or {})}
        values["policy_version_id"] = active.get("id")
        meta = {
            "updated_at": active.get("updated_at"),
            "updated_by": active.get("updated_by"),
            "source": "versioned",
            "status": active.get("status"),
            "policy_version_id": active.get("id")
        }
        return values, meta

    try:
        doc = Database.get_db().collection("policy_configs").document(org_id).get()
    except Exception:
        doc = None

    stored = doc.to_dict() if doc and doc.exists else {}
    stored_values = stored.get("values", {}) if isinstance(stored, dict) else {}
    values = {**defaults, **stored_values}
    values["policy_version_id"] = stored.get("active_version_id")

    meta = {
        "updated_at": stored.get("updated_at") if isinstance(stored, dict) else None,
        "updated_by": stored.get("updated_by") if isinstance(stored, dict) else None,
        "source": "custom" if stored_values else "defaults",
        "policy_version_id": stored.get("active_version_id") if isinstance(stored, dict) else None
    }

    return values, meta
