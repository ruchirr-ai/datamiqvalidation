# DataMIQ EC2 Deploy — Quick Checklist (self-contained, Postgres on the box)

Full detail in `DEPLOY_EC2_STEPS.md`. Copy-ready files:
`infrastructure/datamiq.service`, `infrastructure/datamiq.nginx.conf`.

## Pre-flight
- [ ] `git ls-files | grep .env` returns nothing
- [ ] EC2 Ubuntu 22.04, t3.medium, 30GB, key pair downloaded
- [ ] SG: 22 (my IP), 80, 443 open; nothing else public

## On the box — install
- [ ] base pkgs + nginx + unixodbc-dev + libpq-dev
- [ ] **postgresql + postgresql-contrib** installed
- [ ] Node 20
- [ ] **msodbcsql18** installed (`odbcinst -q -d` lists it)
- [ ] uv installed (`source ~/.local/bin/env`)

## Database (local)
- [ ] `CREATE USER datamiq` + `CREATE DATABASE datamiq OWNER datamiq`
- [ ] `psql ... \conninfo` connects OK

## App config
- [ ] repo cloned to `/home/ubuntu/datamiq`
- [ ] `backend/.env` with APP_DB_HOST=localhost, APP_DB_* , SSL_MODE=disable,
      fresh JWT_SECRET_KEY, ADMIN_USER/ADMIN_PASSWORD (website login), CORS_ORIGINS

## Backend
- [ ] `uv sync` succeeds
- [ ] `uv run alembic upgrade head` → `uv run alembic current` shows head
- [ ] `uv run python create_admin_user.py` → "created successfully"
- [ ] `curl localhost:8000/health` → healthy
- [ ] systemd service installed; `systemctl status datamiq` = active

## Frontend + nginx
- [ ] `npm install && npm run build` → `frontend/dist` exists
- [ ] nginx config installed, default site removed, `chmod o+x /home/ubuntu`
- [ ] `nginx -t` ok, nginx restarted + enabled
- [ ] `http://<EC2_PUBLIC_IP>` loads login page

## Access
- [ ] Elastic IP allocated + associated
- [ ] (optional) domain A record + `certbot --nginx`; CORS_ORIGINS updated; restart datamiq
- [ ] Shared URL + website login with the viewer

## Verify end to end
- [ ] Log in as admin (website login)
- [ ] Create + test a connection (e.g. SQL Server)
- [ ] Run a direct/connection validation
