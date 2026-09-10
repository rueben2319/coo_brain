import logging
from typing import Any, Dict, Optional
from uuid import UUID
from supabase import Client

from app.models.snapshot import CompanyStateSnapshotCreate, CompanyStateSnapshotRead

logger = logging.getLogger("coo_brain.company_state")


class CompanyStateService:
    def __init__(self, db: Client):
        self.db = db

    async def get_latest_snapshot(self, company_id: UUID) -> Optional[CompanyStateSnapshotRead]:
        res = (
            self.db.table("company_state_snapshots")
            .select("*")
            .eq("company_id", str(company_id))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return CompanyStateSnapshotRead(**res.data[0])
        return None

    async def generate_snapshot(
        self, company_id: UUID, generated_by: Optional[UUID] = None
    ) -> CompanyStateSnapshotRead:
        cid_str = str(company_id)

        # 1. Gather Goals metrics
        goals_res = self.db.table("goals").select("status").eq("company_id", cid_str).execute()
        goals = goals_res.data or []
        total_goals = len(goals)
        on_track = sum(1 for g in goals if g.get("status") == "on_track")
        at_risk = sum(1 for g in goals if g.get("status") == "at_risk")
        off_track = sum(1 for g in goals if g.get("status") == "off_track")
        achieved = sum(1 for g in goals if g.get("status") == "achieved")
        goals_on_track_pct = round((on_track / total_goals * 100), 1) if total_goals > 0 else 100.0

        # 2. Gather Events metrics
        events_res = (
            self.db.table("events")
            .select("severity, status")
            .eq("company_id", cid_str)
            .neq("status", "resolved")
            .neq("status", "dismissed")
            .execute()
        )
        open_events = events_res.data or []
        total_open_events = len(open_events)
        critical_events = sum(1 for e in open_events if e.get("severity") == "critical")
        warning_events = sum(1 for e in open_events if e.get("severity") == "warning")

        # 3. Gather Decisions metrics
        decisions_res = (
            self.db.table("decisions")
            .select("status, risk_level")
            .eq("company_id", cid_str)
            .execute()
        )
        decisions = decisions_res.data or []
        pending_decisions = sum(1 for d in decisions if d.get("status") == "proposed")
        approved_decisions = sum(1 for d in decisions if d.get("status") == "approved")

        # 4. Gather Active Policies
        policies_res = (
            self.db.table("policies")
            .select("id")
            .eq("company_id", cid_str)
            .eq("is_active", True)
            .execute()
        )
        active_policies = len(policies_res.data or [])

        metrics: Dict[str, Any] = {
            "total_goals": total_goals,
            "on_track_goals": on_track,
            "at_risk_goals": at_risk,
            "off_track_goals": off_track,
            "achieved_goals": achieved,
            "goals_on_track_pct": goals_on_track_pct,
            "total_open_events": total_open_events,
            "critical_events_count": critical_events,
            "warning_events_count": warning_events,
            "pending_decisions_count": pending_decisions,
            "approved_decisions_count": approved_decisions,
            "active_policies_count": active_policies,
        }

        # Build short human-readable summary
        summary_parts = [
            f"Goals: {on_track}/{total_goals} on track ({goals_on_track_pct}%)."
        ]
        if at_risk > 0 or off_track > 0:
            summary_parts.append(f"Issues: {at_risk} goals at risk, {off_track} off track.")
        if total_open_events > 0:
            summary_parts.append(
                f"Open Signals: {total_open_events} active events ({critical_events} critical, {warning_events} warning)."
            )
        else:
            summary_parts.append("Open Signals: No active open event signals.")
        if pending_decisions > 0:
            summary_parts.append(f"Decisions: {pending_decisions} decisions pending approval.")

        summary_text = " ".join(summary_parts)

        snapshot_data = {
            "company_id": cid_str,
            "generated_by": str(generated_by) if generated_by else None,
            "metrics": metrics,
            "summary": summary_text,
        }

        res = self.db.table("company_state_snapshots").insert(snapshot_data).execute()
        logger.info(f"Generated new company state snapshot for company {company_id}: {summary_text}")
        return CompanyStateSnapshotRead(**res.data[0])
