import asyncio
import logging
from datetime import datetime, timezone

from app.scanner.aws import AWSScanner
from app.scanner.azure import AzureScanner
from app.models.finding import ScanResult, WasteFinding, Severity

logger = logging.getLogger(__name__)

# Constant for total monthly cloud spend to calculate waste percentage
TOTAL_SPEND = 141600.0


class ScanOrchestrator:
    """
    Orchestrates multi-cloud scans by running AWS and Azure scanners 
    concurrently using asyncio.
    """

    async def run(self) -> ScanResult:
        logger.info("Multi-cloud scan starting...")
        start_time = datetime.now(timezone.utc)

        # Run scanners in threads to avoid blocking the event loop 
        # (since cloud SDKs are often synchronous)
        aws_findings, azure_findings = await asyncio.gather(
            asyncio.to_thread(self._run_aws),
            asyncio.to_thread(self._run_azure),
        )

        all_findings: list[WasteFinding] = aws_findings + azure_findings

        # Calculate metrics
        total_waste = sum(f.monthly_savings_usd for f in all_findings)
        waste_pct   = round((total_waste / TOTAL_SPEND) * 100, 1)

        by_cloud = {
            "aws": {
                "count":     len(aws_findings),
                "waste_usd": round(sum(f.monthly_savings_usd for f in aws_findings), 2),
            },
            "azure": {
                "count":     len(azure_findings),
                "waste_usd": round(sum(f.monthly_savings_usd for f in azure_findings), 2),
            },
        }

        by_severity = {s.value: 0 for s in Severity}
        for f in all_findings:
            by_severity[f.severity.value] += 1

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            f"Scan complete in {elapsed:.1f}s — "
            f"{len(all_findings)} findings, "
            f"${total_waste:,.0f}/mo waste"
        )

        return ScanResult(
            scan_id                 = f"SCAN-{start_time.strftime('%Y%m%d%H%M%S')}",
            scanned_at              = start_time,
            resources_scanned       = 847,  # Hardcoded for demonstration
            findings_count          = len(all_findings),
            total_monthly_waste_usd = round(total_waste, 2),
            total_annual_waste_usd  = round(total_waste * 12, 2),
            waste_percentage        = waste_pct,
            by_cloud                = by_cloud,
            by_severity             = by_severity,
            findings                = all_findings,
        )

    def _run_aws(self) -> list[WasteFinding]:
        # Initializing AWS scanner for a specific region
        return AWSScanner(region="us-east-1").scan_all()

    def _run_azure(self) -> list[WasteFinding]:
        # Initializing Azure scanner using default env credentials
        return AzureScanner().scan_all()