import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.models.finding import Cloud, ResourceType, Severity, WasteFinding

logger = logging.getLogger(__name__)

# Configuration via Environment Variables
CPU_THRESHOLD_PCT  = float(os.getenv("IDLE_CPU_THRESHOLD_PCT", "5"))
OBSERVATION_DAYS   = int(os.getenv("IDLE_OBSERVATION_DAYS", "14"))
RDS_CONN_THRESHOLD = int(os.getenv("RDS_CONNECTION_THRESHOLD", "1"))

# Pricing Data (Monthly estimates)
EC2_MONTHLY_PRICE = {
    "t3.micro": 8.47,    "t3.small": 16.93,   "t3.medium": 33.87,
    "t3.large": 60.74,   "t3.xlarge": 121.47,  "t3.2xlarge": 242.94,
    "m5.large": 70.08,   "m5.xlarge": 140.16,  "m5.2xlarge": 280.32,
    "c5.large": 62.05,   "c5.xlarge": 124.10,  "c5.2xlarge": 248.20,
}

RDS_MONTHLY_PRICE = {
    "db.t3.micro": 15.33,  "db.t3.small": 30.66,
    "db.t3.medium": 61.32, "db.r5.large": 175.20,
}

EC2_DOWNSIZE = {
    "t3.xlarge":  "t3.medium",
    "t3.large":   "t3.small",
    "t3.2xlarge": "t3.large",
    "m5.2xlarge": "m5.large",
    "m5.xlarge":  "m5.small",
    "c5.2xlarge": "c5.xlarge",
}


class AWSScanner:
    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self._ec2 = None
        self._cw  = None
        self._rds = None
        self._mock_mode = False

    def _init_clients(self) -> bool:
        try:
            import boto3
            self._ec2 = boto3.client("ec2", region_name=self.region)
            self._cw  = boto3.client("cloudwatch", region_name=self.region)
            self._rds = boto3.client("rds", region_name=self.region)
            self._ec2.describe_availability_zones()
            logger.info(f"AWS connected — region: {self.region}")
            return True
        except Exception as e:
            logger.warning(f"AWS credentials not found ({e}) — switching to mock mode")
            self._mock_mode = True
            return False

    def scan_idle_ec2(self) -> list[WasteFinding]:
        if self._mock_mode:
            return self._mock_ec2()

        findings = []
        try:
            paginator = self._ec2.get_paginator("describe_instances")
            pages = paginator.paginate(
                Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
            )
            for page in pages:
                for reservation in page["Reservations"]:
                    for instance in reservation["Instances"]:
                        iid   = instance["InstanceId"]
                        itype = instance["InstanceType"]
                        name  = self._get_tag(instance, "Name") or iid

                        avg_cpu = self._get_metric_avg(
                            namespace   = "AWS/EC2",
                            metric_name = "CPUUtilization",
                            dimension   = {"Name": "InstanceId", "Value": iid},
                            days        = OBSERVATION_DAYS,
                        )

                        if avg_cpu is None or avg_cpu >= CPU_THRESHOLD_PCT:
                            continue

                        monthly_cost = EC2_MONTHLY_PRICE.get(itype, 80.0)
                        monthly_save = monthly_cost * 0.60
                        new_type     = EC2_DOWNSIZE.get(itype, "t3.micro")
                        severity     = Severity.HIGH if avg_cpu < 2 else Severity.MEDIUM

                        findings.append(WasteFinding.build(
                            id            = f"AWS-EC2-{iid[2:10].upper()}",
                            cloud         = Cloud.AWS,
                            region        = self.region,
                            resource_id   = iid,
                            resource_type = ResourceType.EC2_INSTANCE,
                            issue         = f"{avg_cpu:.1f}% avg CPU over {OBSERVATION_DAYS} days",
                            monthly_savings_usd = monthly_save,
                            severity      = severity,
                            terraform_fix = self._ec2_tf_fix(iid, itype, new_type),
                            metadata      = {
                                "instance_type":    itype,
                                "recommended_type": new_type,
                                "avg_cpu_pct":      round(avg_cpu, 2),
                                "name_tag":          name,
                            },
                        ))
        except Exception as e:
            logger.error(f"EC2 scan failed: {e}")

        return findings

    def scan_unattached_eips(self) -> list[WasteFinding]:
        if self._mock_mode:
            return []

        findings = []
        try:
            response = self._ec2.describe_addresses()
            for addr in response["Addresses"]:
                if "AssociationId" in addr:
                    continue

                alloc_id = addr["AllocationId"]
                findings.append(WasteFinding.build(
                    id            = f"AWS-EIP-{alloc_id[-6:].upper()}",
                    cloud         = Cloud.AWS,
                    region        = self.region,
                    resource_id   = alloc_id,
                    resource_type = ResourceType.ELASTIC_IP,
                    issue         = "Not attached to any resource — $0.005/hr waste",
                    monthly_savings_usd = 3.60,
                    severity      = Severity.LOW,
                    terraform_fix = (
                        f"# Release EIP: {alloc_id}\n"
                        f"# aws ec2 release-address --allocation-id {alloc_id}"
                    ),
                    metadata={"allocation_id": alloc_id},
                ))
        except Exception as e:
            logger.error(f"EIP scan failed: {e}")

        return findings

    def scan_idle_rds(self) -> list[WasteFinding]:
        if self._mock_mode:
            return self._mock_rds()

        findings = []
        try:
            paginator = self._rds.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for db in page["DBInstances"]:
                    if db["DBInstanceStatus"] != "available":
                        continue

                    db_id    = db["DBInstanceIdentifier"]
                    db_class = db["DBInstanceClass"]

                    avg_conn = self._get_metric_avg(
                        namespace   = "AWS/RDS",
                        metric_name = "DatabaseConnections",
                        dimension   = {"Name": "DBInstanceIdentifier", "Value": db_id},
                        days        = 30,
                    )

                    if avg_conn is None or avg_conn >= RDS_CONN_THRESHOLD:
                        continue

                    monthly_save = RDS_MONTHLY_PRICE.get(db_class, 100.0)
                    severity     = Severity.CRITICAL if avg_conn == 0 else Severity.HIGH

                    findings.append(WasteFinding.build(
                        id            = f"AWS-RDS-{db_id[:8].upper()}",
                        cloud         = Cloud.AWS,
                        region        = self.region,
                        resource_id   = db_id,
                        resource_type = ResourceType.RDS_INSTANCE,
                        issue         = f"Avg {avg_conn:.1f} connections over 30 days",
                        monthly_savings_usd = monthly_save,
                        severity      = severity,
                        terraform_fix = self._rds_tf_fix(db_id),
                        metadata      = {
                            "db_class":        db_class,
                            "engine":          db.get("Engine"),
                            "avg_connections": round(avg_conn, 2),
                        },
                    ))
        except Exception as e:
            logger.error(f"RDS scan failed: {e}")

        return findings

    def _get_metric_avg(
        self,
        namespace: str,
        metric_name: str,
        dimension: dict,
        days: int,
    ) -> Optional[float]:
        try:
            end   = datetime.now(timezone.utc)
            start = end - timedelta(days=days)
            resp  = self._cw.get_metric_statistics(
                Namespace  = namespace,
                MetricName = metric_name,
                Dimensions = [dimension],
                StartTime  = start,
                EndTime    = end,
                Period     = 86400,
                Statistics = ["Average"],
            )
            pts = resp.get("Datapoints", [])
            if not pts:
                return None
            return sum(p["Average"] for p in pts) / len(pts)
        except Exception as e:
            logger.warning(f"CloudWatch metric fetch failed: {e}")
            return None

    def _ec2_tf_fix(self, instance_id: str, current: str, new: str) -> str:
        return (
            f'resource "aws_instance" "this" {{\n'
            f'  instance_type = "{new}"  # was {current}\n'
            f'  # NOTE: instance stop/start required\n'
            f'}}'
        )

    def _rds_tf_fix(self, db_id: str) -> str:
        from datetime import date
        return (
            f'resource "aws_db_instance" "{db_id}" {{\n'
            f'  skip_final_snapshot       = false\n'
            f'  final_snapshot_identifier = "{db_id}-finops-{date.today()}"\n'
            f'}}'
        )

    @staticmethod
    def _get_tag(resource: dict, key: str) -> Optional[str]:
        return next(
            (t["Value"] for t in resource.get("Tags", []) if t["Key"] == key),
            None,
        )

    def _mock_ec2(self) -> list[WasteFinding]:
        return [
            WasteFinding.build(
                id="AWS-EC2-I0A3B2C4", cloud=Cloud.AWS, region=self.region,
                resource_id="i-0a3b2c4d5e6f7a8b9",
                resource_type=ResourceType.EC2_INSTANCE,
                issue=f"0.0% avg CPU over {OBSERVATION_DAYS} days",
                monthly_savings_usd=72.88, severity=Severity.HIGH,
                terraform_fix=self._ec2_tf_fix("i-0a3b2c4d5e6f7a8b9", "t3.xlarge", "t3.medium"),
                metadata={"instance_type": "t3.xlarge", "avg_cpu_pct": 0.0},
            ),
            WasteFinding.build(
                id="AWS-EC2-I1C4D5E6", cloud=Cloud.AWS, region=self.region,
                resource_id="i-1c4d5e6f7a8b9c0d",
                resource_type=ResourceType.EC2_INSTANCE,
                issue=f"2.3% avg CPU over {OBSERVATION_DAYS} days",
                monthly_savings_usd=168.19, severity=Severity.MEDIUM,
                terraform_fix=self._ec2_tf_fix("i-1c4d5e6f7a8b9c0d", "m5.2xlarge", "m5.large"),
                metadata={"instance_type": "m5.2xlarge", "avg_cpu_pct": 2.3},
            ),
        ]

    def _mock_rds(self) -> list[WasteFinding]:
        return [
            WasteFinding.build(
                id="AWS-RDS-DBREPORT", cloud=Cloud.AWS, region=self.region,
                resource_id="db-reporting-replica",
                resource_type=ResourceType.RDS_INSTANCE,
                issue="0.0 avg connections over 30 days",
                monthly_savings_usd=175.20, severity=Severity.CRITICAL,
                terraform_fix=self._rds_tf_fix("db-reporting-replica"),
                metadata={"db_class": "db.r5.large", "avg_connections": 0.0},
            ),
        ]

    def scan_all(self) -> list[WasteFinding]:
        self._init_clients()
        findings = []
        findings.extend(self.scan_idle_ec2())
        findings.extend(self.scan_unattached_eips())
        findings.extend(self.scan_idle_rds())
        logger.info(f"AWS scan done — {len(findings)} findings")
        return findings