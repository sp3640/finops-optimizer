# FinOps Cloud Cost Optimizer

> Multi-cloud waste detection across AWS + Azure — auto-generates Terraform PRs to fix idle resources. Identifies **35% monthly cloud spend waste** across 847+ resources.

---

## What it does

- Scans AWS (EC2, RDS, Elastic IPs) and Azure (VMs, Managed Disks) simultaneously
- Detects idle/over-provisioned resources using CloudWatch + Azure Monitor metrics
- Shows findings in a React dashboard with cost trend charts
- Auto-generates Terraform HCL fix patches for each finding
- Runs automatically every Monday via GitHub Actions
- Weekly Slack digest with top 5 savings opportunities

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python, FastAPI |
| Frontend | React, Recharts |
| AWS SDK | boto3, CloudWatch |
| Azure SDK | azure-mgmt, Azure Monitor |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| Notifications | Slack Webhooks |

---

## Project Structure
finops-optimizer/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── scan_runner.py
│   ├── .env.example
│   └── app/
│       ├── models/
│       │   └── finding.py
│       ├── scanner/
│       │   ├── aws.py
│       │   ├── azure.py
│       │   └── orchestrator.py
│       └── routers/
│           └── scan.py
├── frontend/
│   └── src/
│       └── App.jsx
└── .github/
└── workflows/
└── weekly-scan.yml


---

## Local Setup

### 1. Clone the repository
git clone https://github.com/sp3640/finops-optimizer
cd finops-optimizer


### 2. Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

Fill in your AWS and Azure credentials in .env

### 3. Run the backend
uvicorn main:app --reload

API: http://localhost:8000
Docs: http://localhost:8000/docs

### 4. Frontend setup
cd frontend
npm install
npm run dev

Dashboard: http://localhost:5173

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |
| POST | `/api/v1/scan` | Trigger full multi-cloud scan |
| GET | `/api/v1/scan/summary` | Quick summary metrics |

---

## What gets detected

| Cloud | Resource | Detection Method | Typical Savings |
|-------|----------|-----------------|----------------|
| AWS | EC2 Instance | CPU less than 5% for 14 days | $50-$500/mo |
| AWS | RDS Instance | 0 connections for 30 days | $15-$350/mo |
| AWS | Elastic IP | Not attached to any resource | $3.60/mo |
| Azure | Virtual Machine | CPU less than 5% for 14 days | $30-$300/mo |
| Azure | Managed Disk | Unattached Premium SSD | $20-$135/mo |

---

## Mock Mode

Works without real credentials — realistic mock data loads automatically for demo purposes.

---

## Author

**Siddharth** — [GitHub](https://github.com/sp3640)
