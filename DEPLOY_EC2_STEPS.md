# DataMIQ — EC2 Deployment Guide (self-contained)

Deploys DataMIQ (React/Vite frontend + FastAPI backend + PostgreSQL) on ONE
AWS EC2 instance. PostgreSQL runs on the same box — no RDS required — which is
the simplest setup for a personal deployment / demo.

**Two kinds of credentials (don't confuse them):**
- **Database login** (`datamiq` / a DB password) — created in Phase 2; lets the
  app connect to PostgreSQL. Goes in `.env` as `APP_DB_USER`/`APP_DB_PASSWORD`.
- **Website login** (`admin` / a password) — created in Phase 4 by
  `create_admin_user.py`; this is what you type on the DataMIQ login page. It is
  a row inside the database, so the DB must exist and migrations must run first.

**Architecture:** nginx serves the built frontend as static files AND proxies
`/api/` to the FastAPI backend (single public URL). Backend runs as a
single-worker systemd service. Postgres is local.

Ready-to-copy artifacts: `infrastructure/datamiq.service`,
`infrastructure/datamiq.nginx.conf`, `infrastructure/deploy-checklist.md`.

---

## Phase 0 — Prerequisites

**0.1 No secrets in git** (run locally; should print nothing):
```powershell
git ls-files | Select-String -Pattern "\.env$|\.env\."
```

**0.2 Launch EC2 (console):**
- AMI: Ubuntu 22.04 LTS
- Type: **t3.medium** min (2 vCPU / 4 GB — t3.micro fails `uv sync`)
- Storage: 30 GB gp3
- Key pair: download `datamiq.pem`
- Security group inbound: **22 from your IP**, **80 from 0.0.0.0/0**, **443 from
  0.0.0.0/0**. Nothing else public (no 8000, no 5432).

No RDS needed — Postgres is installed on this instance in Phase 2.

---

## Phase 1 — Install dependencies

```bash
ssh -i datamiq.pem ubuntu@<EC2_PUBLIC_IP>

sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl nginx unixodbc-dev gcc g++ build-essential libpq-dev

# PostgreSQL server (runs on this box)
sudo apt install -y postgresql postgresql-contrib

# Node 20 (build the Vite frontend)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Microsoft ODBC Driver 18 for SQL Server  (REQUIRED: backend uses pyodbc)
curl https://packages.microsoft.com/keys/microsoft.asc | sudo tee /etc/apt/trusted.gpg.d/microsoft.asc
curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt update
sudo ACCEPT_EULA=Y apt install -y msodbcsql18

# uv (project's Python package manager) — installs to ~/.local/bin
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv --version
```

---

## Phase 2 — Create the PostgreSQL database + DB user (on this box)

PostgreSQL starts automatically after install. Create the app's database and
role:
```bash
sudo -u postgres psql -c "CREATE USER datamiq WITH PASSWORD 'datamiq_db_pass';"
sudo -u postgres psql -c "CREATE DATABASE datamiq OWNER datamiq;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE datamiq TO datamiq;"

# verify
psql "host=localhost port=5432 user=datamiq dbname=datamiq password=datamiq_db_pass" -c "\conninfo"
```
> `datamiq` / `datamiq_db_pass` is the **database** login. Change the password to
> something strong for a non-demo deploy. This is NOT the website login.

---

## Phase 3 — Clone and configure `.env`

```bash
cd /home/ubuntu
git clone https://github.com/<your-username>/<your-repo>.git datamiq
cd datamiq/backend

cat > .env <<EOF
# Database — local Postgres on this EC2 box
APP_DB_HOST=localhost
APP_DB_PORT=5432
APP_DB_NAME=datamiq
APP_DB_USER=datamiq
APP_DB_PASSWORD=datamiq_db_pass
APP_DB_SSL_MODE=disable

APP_ENV=production
APP_PORT=8000
APP_HOST=0.0.0.0
LOG_LEVEL=INFO

JWT_SECRET_KEY=<paste-generated-secret>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

CORS_ORIGINS=http://<EC2_PUBLIC_IP>
REDIS_ENABLED=false
AWS_REGION=us-east-1

# DataMIQ WEBSITE admin login (created in Phase 4)
ADMIN_USER=admin
ADMIN_PASSWORD=<strong-website-password>
EOF

python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # -> paste as JWT_SECRET_KEY
```

---

## Phase 4 — Backend: install, build schema, create website admin

```bash
cd /home/ubuntu/datamiq/backend
uv sync                               # install exact locked deps (NOT 'uv pip install -r requirements.txt')

uv run alembic upgrade head           # creates ALL tables incl. 'users' and the validation tables
uv run python create_admin_user.py    # inserts the DataMIQ website admin from .env

# smoke test
uv run uvicorn main:app --host 0.0.0.0 --port 8000 &
sleep 5 && curl http://localhost:8000/health      # -> {"status":"healthy",...}
kill %1
```
Website login is now `admin` / `<strong-website-password>`.

---

## Phase 5 — Backend as a systemd service (single worker)

> Single worker on purpose: `main.py` runs an in-process background scheduler;
> multiple workers would run it multiple times.
```bash
sudo cp /home/ubuntu/datamiq/infrastructure/datamiq.service /etc/systemd/system/datamiq.service
sudo systemctl daemon-reload
sudo systemctl enable --now datamiq
sudo systemctl status datamiq         # active (running)
```

---

## Phase 6 — Build the frontend

No API URL needed in production — the app uses relative `/api` and nginx
proxies it. Do NOT create a CRA-style `.env.production`.
```bash
cd /home/ubuntu/datamiq/frontend
npm install
npm run build        # outputs to frontend/dist
```

---

## Phase 7 — nginx (serve frontend + proxy /api)

```bash
sudo cp /home/ubuntu/datamiq/infrastructure/datamiq.nginx.conf /etc/nginx/sites-available/datamiq
sudo ln -sf /etc/nginx/sites-available/datamiq /etc/nginx/sites-enabled/datamiq
sudo rm -f /etc/nginx/sites-enabled/default
sudo chmod o+x /home/ubuntu          # let nginx traverse into the home dir
sudo nginx -t && sudo systemctl restart nginx && sudo systemctl enable nginx
```
Site live at **http://<EC2_PUBLIC_IP>** — log in with the Phase 3/4 website admin.

---

## Phase 8 — Give someone access

**Option A — share the IP (quickest).** Port 80 is public, so anyone with the
link reaches the login page; they still need a login to get in.
1. Allocate an **Elastic IP** and associate it (so the address survives reboots).
2. Share `http://<ELASTIC_IP>` + a login (the admin, or create another user with
   different `ADMIN_USER`/`ADMIN_PASSWORD` and re-running `create_admin_user.py`).

**Option B — domain + HTTPS (recommended for sharing).**
1. Elastic IP → DNS **A record** `yourdomain.com` → that IP.
2. `sudo apt install -y certbot python3-certbot-nginx && sudo certbot --nginx -d yourdomain.com`
3. Set `CORS_ORIGINS=https://yourdomain.com` in `backend/.env`; `sudo systemctl restart datamiq`.
4. Share `https://yourdomain.com` + login.

---

## Updating after a git push
```bash
cd /home/ubuntu/datamiq && git pull
cd backend && uv sync && uv run alembic upgrade head
cd ../frontend && npm install && npm run build
sudo systemctl restart datamiq && sudo systemctl restart nginx
```

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Backend won't start | `sudo journalctl -u datamiq -n 100 --no-pager` |
| `pyodbc` / SQL Server error | `odbcinst -q -d` lists "ODBC Driver 18 for SQL Server" |
| DB connection refused | `systemctl status postgresql`; Phase 2 `psql` test works? |
| 502 Bad Gateway | backend down (`systemctl status datamiq`) or not on :8000 |
| Blank page / 404 on refresh | nginx `try_files ... /index.html`; `frontend/dist` exists |
| nginx 403 | `sudo chmod o+x /home/ubuntu` |
| Login says invalid | migrations ran (`uv run alembic current`) and admin created |
| CORS error | `CORS_ORIGINS` matches the exact scheme+host you're visiting |

---

## Backups (local Postgres)
```bash
pg_dump "host=localhost user=datamiq dbname=datamiq password=datamiq_db_pass" > ~/datamiq_backup_$(date +%F).sql
# copy off the box, e.g.:  aws s3 cp ~/datamiq_backup_*.sql s3://your-bucket/
```

## Appendix — AWS features needing an IAM role
Connection-param encryption (KMS) and AI analysis (Bedrock) need an EC2
**instance IAM role** with `kms:Encrypt`, `kms:Decrypt`,
`secretsmanager:GetSecretValue`, `bedrock:InvokeModel`. Policy JSON is in
`iam-policies/`. The app runs without these; those specific features error until
the role is attached. Prefer an instance role over AWS keys in `.env`.

## Appendix — Moving to RDS later
To use managed RDS instead of local Postgres: create an RDS PostgreSQL instance
(SG allows 5432 from the EC2 SG), create the `datamiq` database on it, then set
`APP_DB_HOST=<rds-endpoint>` and `APP_DB_SSL_MODE=require` in `.env`, re-run
`uv run alembic upgrade head` + `create_admin_user.py` against it, and restart.
