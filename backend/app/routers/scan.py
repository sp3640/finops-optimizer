from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.scanner.orchestrator import ScanOrchestrator
from app.models.finding import ScanResult

router = APIRouter()


class ScanRequest(BaseModel):
    """
    Input schema for triggering a scan.
    """
    clouds: list[str] = ["AWS", "Azure"]
    auto_pr: bool = False
    dry_run: bool = True


class ScanResponse(ScanResult):
    """
    Output schema extending the base ScanResult with API-specific status messages.
    """
    prs_opened: int = 0
    message: str = ""


@router.post("")
async def trigger_scan(req: ScanRequest = ScanRequest()) -> ScanResponse:
    """
    Endpoint to manually trigger a multi-cloud waste scan.
    """
    try:
        orchestrator = ScanOrchestrator()
        result = await orchestrator.run()

        return ScanResponse(
            **result.model_dump(),
            prs_opened=0,
            message=(
                f"Scan complete! {result.findings_count} issues found — "
                f"${result.total_monthly_waste_usd:,.0f}/mo waste detected "
                f"(${result.total_annual_waste_usd:,.0f}/yr)"
            ),
        )
    except Exception as e:
        # Proper error logging should happen here in a real app
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.get("/summary")
async def get_summary():
    """
    Quick dashboard summary endpoint returning high-level FinOps KPIs.
    """
    return {
        "total_monthly_spend_usd":  141600,
        "total_monthly_waste_usd":  49560,
        "waste_percentage":         35.0,
        "resources_scanned":        847,
        "open_prs":                 3,
        "last_scan":                "2 minutes ago",
        "status":                   "healthy",
    }