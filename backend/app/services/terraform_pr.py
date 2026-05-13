import logging
import os
import httpx
import base64
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Environment Variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "sp3640/finops-infrastructure")
BASE_BRANCH = os.getenv("GITHUB_BASE_BRANCH", "main")

@dataclass
class PRResult:
    pr_number: int
    pr_url: str
    branch_name: str
    finding_id: str
    monthly_savings_usd: float

class TerraformPRGenerator:
    """
    Automatically opens a GitHub PR for a WasteFinding 
    including the Terraform fix.
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str = GITHUB_TOKEN, repo: str = GITHUB_REPO):
        self.token = token
        self.repo = repo
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def create_pr(self, finding: dict) -> Optional[PRResult]:
        """
        For a specific finding:
        1. Create a branch
        2. Commit the Terraform fix
        3. Open the Pull Request
        """
        if not self.token:
            logger.warning("GITHUB_TOKEN not set — cannot create PR")
            return None

        finding_id = finding["id"]
        resource_id = finding["resource_id"]
        resource_type = finding["resource_type"]
        savings = finding["monthly_savings_usd"]
        tf_fix = finding["terraform_fix"]
        cloud = finding["cloud"]

        # Determine the target file path
        file_path = self._get_file_path(resource_type)
        if not file_path:
            logger.warning(f"File path not found for: {resource_type}")
            return None

        # Generate a unique branch name
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        branch_name = f"finops/{finding_id.lower()}-{timestamp}"

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:

                # Step 1 — Get the SHA of the base branch
                ref_resp = await client.get(
                    f"{self.BASE_URL}/repos/{self.repo}/git/ref/heads/{BASE_BRANCH}"
                )
                ref_resp.raise_for_status()
                base_sha = ref_resp.json()["object"]["sha"]
                logger.info(f"Base SHA found: {base_sha[:7]}")

                # Step 2 — Create a new branch
                branch_resp = await client.post(
                    f"{self.BASE_URL}/repos/{self.repo}/git/refs",
                    json={
                        "ref": f"refs/heads/{branch_name}",
                        "sha": base_sha,
                    }
                )
                branch_resp.raise_for_status()
                logger.info(f"Branch created: {branch_name}")

                # Step 3 — Get existing file SHA (required for updates)
                file_sha = None
                existing = await client.get(
                    f"{self.BASE_URL}/repos/{self.repo}/contents/{file_path}",
                    params={"ref": branch_name}
                )
                if existing.status_code == 200:
                    file_sha = existing.json()["sha"]

                # Step 4 — Commit the Terraform fix
                commit_body = {
                    "message": f"finops({finding_id}): rightsize {resource_id} — save ${savings:.0f}/mo",
                    "content": base64.b64encode(tf_fix.encode()).decode(),
                    "branch": branch_name,
                }
                if file_sha:
                    commit_body["sha"] = file_sha

                commit_resp = await client.put(
                    f"{self.BASE_URL}/repos/{self.repo}/contents/{file_path}",
                    json=commit_body,
                )
                commit_resp.raise_for_status()
                logger.info(f"Commit successful: {file_path}")

                # Step 5 — Open the Pull Request
                pr_resp = await client.post(
                    f"{self.BASE_URL}/repos/{self.repo}/pulls",
                    json={
                        "title": f"[FinOps] {resource_type} {resource_id} — save ${savings:.0f}/mo",
                        "body": self._pr_body(finding),
                        "head": branch_name,
                        "base": BASE_BRANCH,
                    }
                )
                pr_resp.raise_for_status()
                pr_data = pr_resp.json()
                logger.info(f"PR opened: #{pr_data['number']} — {pr_data['html_url']}")

                return PRResult(
                    pr_number = pr_data["number"],
                    pr_url = pr_data["html_url"],
                    branch_name = branch_name,
                    finding_id = finding_id,
                    monthly_savings_usd = savings,
                )

        except Exception as e:
            logger.error(f"PR creation failed for {finding_id}: {e}")
            return None

    def _get_file_path(self, resource_type: str) -> Optional[str]:
        """Determine the Terraform file path based on resource type."""
        mapping = {
            "EC2 Instance": "terraform/aws/ec2.tf",
            "RDS Instance": "terraform/aws/rds.tf",
            "Elastic IP": "terraform/aws/ec2.tf",
            "Virtual Machine": "terraform/azure/vm.tf",
            "Managed Disk": "terraform/azure/disk.tf",
        }
        return mapping.get(resource_type)

    def _pr_body(self, finding: dict) -> str:
        savings_annual = finding["monthly_savings_usd"] * 12
        lines = [
            "## FinOps Cost Optimization",
            "",
            "> This PR was automatically generated by the FinOps Cloud Cost Optimizer.",
            "> Changes will not be applied until an engineer approves and merges this PR.",
            "",
            "### Finding Details",
            "",
            "| Field | Value |",
            "|-------|-------|",
            "| Finding ID | `{finding['id']}` |",
            "| Cloud | {finding['cloud']} |",
            "| Region | {finding['region']} |",
            "| Resource | `{finding['resource_id']}` |",
            "| Type | {finding['resource_type']} |",
            "| Issue | {finding['issue']} |",
            "| Monthly Savings | **${finding['monthly_savings_usd']:.0f}** |",
            "| Annual Savings | **${savings_annual:.0f}** |",
            "",
            "### Terraform Fix",
            "",
            finding["terraform_fix"],
            "",
            "### Steps to validate",
            "",
            "1. Review the Terraform diff",
            "2. Verify the resource status in the {finding['cloud']} console",
            "3. Approve and merge the PR",
            "",
            "---",
            "*Generated by FinOps Cloud Cost Optimizer*",
        ]
        return "\n".join(lines)