import asyncio
from app.scanner.orchestrator import ScanOrchestrator

async def main():
    # Initialize the core scanner logic
    o = ScanOrchestrator()
    
    # Execute the multi-cloud scan
    result = await o.run()
    
    # Log summary statistics for the GitHub Action
    print("Scan complete!")
    print(f"Findings: {result.findings_count}")
    print(f"Monthly waste: ${result.total_monthly_waste_usd:,.0f}")
    print(f"Annual waste: ${result.total_annual_waste_usd:,.0f}")
    print(f"Waste percent: {result.waste_percentage}%")
    
    # Detail individual cloud waste findings
    for f in result.findings:
        print(f"  - [{f.severity.upper()}] {f.resource_id}: save ${f.monthly_savings_usd}/mo")

if __name__ == "__main__":
    asyncio.run(main())