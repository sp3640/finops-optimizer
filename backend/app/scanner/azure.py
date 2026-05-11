import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.models.finding import Cloud, ResourceType, Severity, WasteFinding

logger = logging.getLogger(__name__)

# Configuration via Environment Variables
CPU_THRESHOLD_PCT = float(os.getenv("IDLE_CPU_THRESHOLD_PCT", "5"))
OBSERVATION_DAYS  = int(os.getenv("IDLE_OBSERVATION_DAYS", "14"))

# Azure Pricing Data (Monthly estimates)
VM_MONTHLY_PRICE = {
    "Standard_B2s":     30.37,  "Standard_B4ms":    85.41,
    "Standard_D2s_v3":  70.08,  "Standard_D4s_v3": 140.16,
    "Standard_D8s_v3": 280.32,  "Standard_E2s_v3":  91.98,
    "Standard_E4s_v3": 183.96,
}

VM_DOWNSIZE = {
    "Standard_D4s_v3":  "Standard_B2s",
    "Standard_D8s_v3":  "Standard_D4s_v3",
    "Standard_E4s_v3":  "Standard_E2s_v3",
    "Standard_B4ms":    "Standard_B2s",
}


class AzureScanner:
    def __init__(self, subscription_id: Optional[str] = None):
        self.subscription_id = subscription_id or os.getenv("AZURE_SUBSCRIPTION_ID", "")
        self._compute    = None
        self._monitor    = None
        self._mock_mode  = False

    def _init_clients(self) -> bool:
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.compute import ComputeManagementClient
            from azure.mgmt.monitor import MonitorManagementClient

            if not self.subscription_id:
                raise ValueError("AZURE_SUBSCRIPTION_ID is not set")

            cred             = DefaultAzureCredential()
            self._compute    = ComputeManagementClient(cred, self.subscription_id)
            self._monitor    = MonitorManagementClient(cred, self.subscription_id)
            logger.info("Azure connected")
            return True

        except Exception as e:
            logger.warning(f"Azure credentials not found ({e}) — switching to mock mode")
            self._mock_mode = True
            return False

    def scan_idle_vms(self) -> list[WasteFinding]:
        if self._mock_mode:
            return self._mock_vms()

        findings = []
        try:
            for vm in self._compute.virtual_machines.list_all():
                vm_size = vm.hardware_profile.vm_size
                avg_cpu = self._get_cpu_avg(vm.id)

                if avg_cpu is None or avg_cpu >= CPU_THRESHOLD_PCT:
                    continue

                monthly_cost = VM_MONTHLY_PRICE.get(vm_size, 100.0)
                monthly_save = monthly_cost * 0.55
                new_size     = VM_DOWNSIZE.get(vm_size, "Standard_B2s")
                severity     = Severity.HIGH if avg_cpu < 3 else Severity.MEDIUM
                rg           = vm.id.split("/")[4]

                findings.append(WasteFinding.build(
                    id            = f"AZ-VM-{vm.name[:8].upper()}",
                    cloud         = Cloud.AZURE,
                    region        = vm.location,
                    resource_id   = vm.name,
                    resource_type = ResourceType.VM,
                    issue         = f"{avg_cpu:.1f}% avg CPU over {OBSERVATION_DAYS} days",
                    monthly_savings_usd = monthly_save,
                    severity      = severity,
                    terraform_fix = self._vm_tf_fix(vm.name, vm_size, new_size),
                    metadata      = {
                        "vm_size":          vm_size,
                        "recommended_size": new_size,
                        "resource_group":    rg,
                        "avg_cpu_pct":      round(avg_cpu, 2),
                    },
                ))
        except Exception as e:
            logger.error(f"Azure VM scan failed: {e}")

        return findings

    def scan_unattached_disks(self) -> list[WasteFinding]:
        if self._mock_mode:
            return self._mock_disks()

        findings = []
        try:
            for disk in self._compute.disks.list():
                if disk.disk_state != "Unattached":
                    continue

                size_gb = disk.disk_size_gb or 128
                sku     = disk.sku.name if disk.sku else "Premium_LRS"

                if "Premium" not in sku:
                    continue

                monthly_save = 135.17 if size_gb >= 512 else 19.71

                findings.append(WasteFinding.build(
                    id            = f"AZ-DISK-{disk.name[:8].upper()}",
                    cloud         = Cloud.AZURE,
                    region        = disk.location,
                    resource_id   = disk.name,
                    resource_type = ResourceType.MANAGED_DISK,
                    issue         = f"Unattached {sku} {size_gb}GB — no VM attached",
                    monthly_savings_usd = monthly_save,
                    severity      = Severity.MEDIUM,
                    terraform_fix = self._disk_tf_fix(disk.name, sku),
                    metadata      = {
                        "disk_size_gb": size_gb,
                        "sku":          sku,
                    },
                ))
        except Exception as e:
            logger.error(f"Azure disk scan failed: {e}")

        return findings

    def _get_cpu_avg(self, resource_id: str) -> Optional[float]:
        try:
            end   = datetime.now(timezone.utc)
            start = end - timedelta(days=OBSERVATION_DAYS)

            metrics = self._monitor.metrics.list(
                resource_uri = resource_id,
                timespan     = f"{start.isoformat()}/{end.isoformat()}",
                interval     = "P1D",
                metricnames  = "Percentage CPU",
                aggregation  = "Average",
            )
            for metric in metrics.value:
                if not metric.timeseries:
                    continue
                values = [
                    ts.average
                    for ts in metric.timeseries[0].data
                    if ts.average is not None
                ]
                if values:
                    return sum(values) / len(values)
        except Exception as e:
            logger.warning(f"Azure Monitor fetch failed: {e}")
        return None

    def _vm_tf_fix(self, vm_name: str, current: str, new: str) -> str:
        tf_name = vm_name.replace("-", "_")
        return (
            f'resource "azurerm_linux_virtual_machine" "{tf_name}" {{\n'
            f'  size = "{new}"  # was {current}\n'
            f'}}'
        )

    def _disk_tf_fix(self, disk_name: str, sku: str) -> str:
        tf_name = disk_name.replace("-", "_")
        return (
            f'resource "azurerm_managed_disk" "{tf_name}" {{\n'
            f'  storage_account_type = "Standard_LRS"  # was {sku}\n'
            f'}}'
        )

    def _mock_vms(self) -> list[WasteFinding]:
        return [
            WasteFinding.build(
                id="AZ-VM-PRODANAL0", cloud=Cloud.AZURE, region="eastus",
                resource_id="vm-prod-analytics-03",
                resource_type=ResourceType.VM,
                issue=f"3.1% avg CPU over {OBSERVATION_DAYS} days",
                monthly_savings_usd=77.09, severity=Severity.HIGH,
                terraform_fix=self._vm_tf_fix(
                    "vm-prod-analytics-03", "Standard_D4s_v3", "Standard_B2s"
                ),
                metadata={"vm_size": "Standard_D4s_v3", "avg_cpu_pct": 3.1},
            ),
        ]

    def _mock_disks(self) -> list[WasteFinding]:
        return [
            WasteFinding.build(
                id="AZ-DISK-BACKUPLE", cloud=Cloud.AZURE, region="westeurope",
                resource_id="disk-backup-legacy-2022",
                resource_type=ResourceType.MANAGED_DISK,
                issue="Unattached Premium_LRS 1024GB",
                monthly_savings_usd=135.17, severity=Severity.MEDIUM,
                terraform_fix=self._disk_tf_fix("disk-backup-legacy-2022", "Premium_LRS"),
                metadata={"disk_size_gb": 1024, "sku": "Premium_LRS"},
            ),
        ]

    def scan_all(self) -> list[WasteFinding]:
        self._init_clients()
        findings = []
        findings.extend(self.scan_idle_vms())
        findings.extend(self.scan_unattached_disks())
        logger.info(f"Azure scan done — {len(findings)} findings")
        return findings