from pydantic import BaseModel, Field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Cloud(str, Enum):
    AWS = "AWS"
    AZURE = "Azure"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"


class ResourceType(str, Enum):
    EC2_INSTANCE  = "EC2 Instance"
    RDS_INSTANCE  = "RDS Instance"
    ELASTIC_IP    = "Elastic IP"
    LOAD_BALANCER = "Load Balancer"
    VM            = "Virtual Machine"
    MANAGED_DISK  = "Managed Disk"


class WasteFinding(BaseModel):
    id: str
    cloud: Cloud
    region: str
    resource_id: str
    resource_type: ResourceType
    issue: str
    monthly_savings_usd: float
    annual_savings_usd: float
    severity: Severity
    terraform_fix: str
    metadata: dict = Field(default_factory=dict)
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    def build(
        cls,
        *,
        id: str,
        cloud: Cloud,
        region: str,
        resource_id: str,
        resource_type: ResourceType,
        issue: str,
        monthly_savings_usd: float,
        severity: Severity,
        terraform_fix: str,
        metadata: Optional[dict] = None,
    ) -> "WasteFinding":
        return cls(
            id=id,
            cloud=cloud,
            region=region,
            resource_id=resource_id,
            resource_type=resource_type,
            issue=issue,
            monthly_savings_usd=round(monthly_savings_usd, 2),
            annual_savings_usd=round(monthly_savings_usd * 12, 2),
            severity=severity,
            terraform_fix=terraform_fix,
            metadata=metadata or {},
        )


class ScanResult(BaseModel):
    scan_id: str
    scanned_at: datetime
    resources_scanned: int
    findings_count: int
    total_monthly_waste_usd: float
    total_annual_waste_usd: float
    waste_percentage: float
    by_cloud: dict
    by_severity: dict
    findings: list[WasteFinding]