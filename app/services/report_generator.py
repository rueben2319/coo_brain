from datetime import date, datetime, timezone
import logging
from typing import Optional
from uuid import UUID
from supabase import Client

from app.models.report import ReportGenerateRequest, ReportRead, ReportType
from app.services.company_state import CompanyStateService

logger = logging.getLogger("coo_brain.report_generator")


class ReportGeneratorService:
    def __init__(self, db: Client):
        self.db = db
        self.state_service = CompanyStateService(db)

    async def generate_report(
        self,
        company_id: UUID,
        request: ReportGenerateRequest,
        generated_by: Optional[UUID] = None,
    ) -> ReportRead:
        cid_str = str(company_id)
        snapshot = await self.state_service.get_latest_snapshot(company_id)
        if not snapshot:
            snapshot = await self.state_service.generate_snapshot(company_id)

        metrics = snapshot.metrics if snapshot else {}
        today_str = date.today().isoformat()

        # Fetch goals, events, decisions to include in report
        goals_res = self.db.table("goals").select("title, status, target_value, current_value, unit").eq("company_id", cid_str).execute()
        events_res = self.db.table("events").select("title, severity, status, event_type").eq("company_id", cid_str).limit(10).execute()
        decisions_res = self.db.table("decisions").select("action_type, status, outcome, reasoning").eq("company_id", cid_str).limit(10).execute()
        tasks_res = self.db.table("tasks").select("title, priority, status").eq("company_id", cid_str).limit(10).execute()

        goals = goals_res.data or []
        events = events_res.data or []
        decisions = decisions_res.data or []
        tasks = tasks_res.data or []

        report_type = request.report_type
        start_str = request.period_start.isoformat() if request.period_start else "N/A"
        end_str = request.period_end.isoformat() if request.period_end else today_str

        if report_type == ReportType.WEEKLY_SUMMARY:
            title = request.title or f"Executive Weekly Operational Summary - {today_str}"
            content = f"""# Executive Weekly Operational Summary
**Reporting Period:** {start_str} to {end_str}  
**Generated At:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}

## 1. Executive Snapshot & Health
- **Total Goals Tracked:** {metrics.get('total_goals', len(goals))}
- **Goals on Track:** {metrics.get('on_track_goals', 0)} ({metrics.get('goals_on_track_pct', 0.0)}%)
- **Goals at Risk / Off Track:** {metrics.get('at_risk_goals', 0)} at risk, {metrics.get('off_track_goals', 0)} off track
- **Active Signals:** {metrics.get('critical_events_count', 0)} critical, {metrics.get('warning_events_count', 0)} warning

## 2. Key Goal Trajectories
"""
            for g in goals:
                content += f"- **{g.get('title')}**: Status: `{g.get('status')}` | Target: {g.get('target_value')} {g.get('unit') or ''} (Current: {g.get('current_value')})\n"

            content += "\n## 3. Active Incident Signals & Exceptions\n"
            if events:
                for e in events:
                    content += f"- `[{e.get('severity', '').upper()}]` **{e.get('title')}** (Status: {e.get('status')})\n"
            else:
                content += "No active incident signals.\n"

            content += "\n## 4. Pending Decisions & Dispatched Tasks\n"
            if tasks:
                for t in tasks:
                    content += f"- `[{t.get('priority', '').upper()}]` **{t.get('title')}** - Status: `{t.get('status')}`\n"
            else:
                content += "No active operational tasks.\n"

        elif report_type == ReportType.FINANCIAL_REVIEW:
            title = request.title or f"Financial & Budget Variance Review - {today_str}"
            fin_events = [e for e in events if "budget" in e.get("event_type", "").lower() or "finance" in e.get("title", "").lower()]
            fin_decisions = [d for d in decisions if "budget" in d.get("action_type", "").lower() or "spend" in d.get("action_type", "").lower()]
            content = f"""# Financial & Budget Variance Review
**Reporting Period:** {start_str} to {end_str}

## 1. Financial Goals & Budgets
"""
            for g in goals:
                content += f"- **{g.get('title')}**: Status: `{g.get('status')}` (Target: {g.get('target_value')} {g.get('unit') or ''})\n"

            content += "\n## 2. Budget Anomalies & Signals\n"
            if fin_events:
                for e in fin_events:
                    content += f"- `[{e.get('severity', '').upper()}]` {e.get('title')}\n"
            else:
                content += "No financial exceptions detected.\n"

            content += "\n## 3. Financial Decisions & Actions\n"
            if fin_decisions:
                for d in fin_decisions:
                    content += f"- **{d.get('action_type')}** ({d.get('status')}): {d.get('outcome') or d.get('reasoning')}\n"
            else:
                content += "No pending financial review actions.\n"

        elif report_type == ReportType.RISK_REVIEW:
            title = request.title or f"Organizational Risk Assessment Report - {today_str}"
            crit_events = [e for e in events if e.get("severity") in ["critical", "warning"]]
            content = f"""# Organizational Risk Assessment Report
**Reporting Period:** {start_str} to {end_str}

## 1. Risk Overview
- **Critical Signals Count:** {metrics.get('critical_events_count', 0)}
- **Warning Signals Count:** {metrics.get('warning_events_count', 0)}

## 2. Active Risk Triggers
"""
            for e in crit_events:
                content += f"- `[{e.get('severity', '').upper()}]` **{e.get('title')}**\n"

        else:
            title = request.title or f"Operational Report ({report_type.value}) - {today_str}"
            content = f"""# Operational Report: {report_type.value.replace('_', ' ').title()}
**Reporting Period:** {start_str} to {end_str}

## Snapshot Summary
{snapshot.summary if snapshot else 'No snapshot available.'}
"""

        report_data = {
            "company_id": cid_str,
            "report_type": report_type.value,
            "title": title,
            "content": content,
            "period_start": request.period_start.isoformat() if request.period_start else None,
            "period_end": request.period_end.isoformat() if request.period_end else None,
            "source_snapshot_id": str(snapshot.id) if snapshot else None,
            "generated_by": str(generated_by) if generated_by else None,
        }

        res = self.db.table("reports").insert(report_data).execute()
        report_row = res.data[0]
        logger.info(f"Generated report {report_row['id']} ({title})")
        return ReportRead(**report_row)
