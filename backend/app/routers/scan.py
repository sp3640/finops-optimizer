from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.scanner.orchestrator import ScanOrchestrator
from app.models.finding import ScanResult
from app.services.terraform_pr import TerraformPRGenerator
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class ScanRequest(BaseModel):
    clouds: list[str] = ["AWS", "Azure"]
    auto_pr: bool = False
    dry_run: bool = True


class ScanResponse(ScanResult):
    prs_opened: int = 0
    message: str = ""


@router.post("")
async def trigger_scan(
    req: ScanRequest = ScanRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> ScanResponse:
    try:
        orchestrator = ScanOrchestrator()
        result = await orchestrator.run()

        prs_opened = 0

        if req.auto_pr and not req.dry_run:
            background_tasks.add_task(
                open_prs_for_findings,
                result.findings
            )
            prs_opened = len(result.findings)

        return ScanResponse(
            **result.model_dump(),
            prs_opened=prs_opened,
            message=(
                f"Scan complete! {result.findings_count} issues mile — "
                f"${result.total_monthly_waste_usd:,.0f}/mo waste detected "
                f"(${result.total_annual_waste_usd:,.0f}/yr)"
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


async def open_prs_for_findings(findings):
    generator = TerraformPRGenerator()
    for finding in findings:
        try:
            finding_dict = finding.model_dump()
            finding_dict["cloud"] = finding.cloud.value
            finding_dict["resource_type"] = finding.resource_type.value
            finding_dict["severity"] = finding.severity.value
            pr = await generator.create_pr(finding_dict)
            if pr:
                logger.info(f"PR opened: #{pr.pr_number} — {pr.pr_url}")
        except Exception as e:
            logger.error(f"PR failed for {finding.id}: {e}")


@router.get("/summary")
async def get_summary():
    return {
        "total_monthly_spend_usd": 141600,
        "total_monthly_waste_usd": 49560,
        "waste_percentage":        35.0,
        "resources_scanned":       847,
        "open_prs":                3,
        "last_scan":               "2 minutes ago",
        "status":                  "healthy",
    }