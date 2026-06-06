# Deploying ScorePilot (shared host, auto-deploy on merge)

ScorePilot deploys to a server that **already runs a reverse proxy** (a host-level
Caddy) fronting other apps. We therefore run only the **app + Postgres** in Docker,
publish the app on a **loopback port**, and let the host proxy terminate TLS and
route the subdomain to it. Every push to `main` rebuilds the image and redeploys.

## How it works

```
push to main ──> GitHub Actions (deploy.yml)
                   1. build the Svelte frontend
                   2. build a Python image, push to GHCR (ghcr.io/kgdunn/scorepilot)
                   3. scp deploy/docker-compose.yml to the server, then SSH:
                        docker compose pull && docker compose up -d --remove-orphans
                 ──> host Caddy (TLS) ──> 127.0.0.1:APP_PORT ──> app ──> Postgres
```

The compose stack (`deploy/docker-compose.yml`) runs `app` (published on
`127.0.0.1:${APP_PORT}`, default **8003**) and `db` (Postgres 16, named volume). On
start the app runs `alembic upgrade head` then serves. **No Caddy/TLS in our
stack** - the host's existing proxy handles HTTPS.

## One-time server setup

On the host (as the `deploy` user; use `sudo` for system bits):

```bash
# 1. Docker + compose plugin (skip if already installed)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy        # let 'deploy' use Docker; re-login to apply

# 2. Deploy directory owned by 'deploy'
sudo mkdir -p /opt/scorepilot && sudo chown -R deploy:deploy /opt/scorepilot

# 3. Environment file (compose reads it). Use a password with NO '$' characters.
cat > /opt/scorepilot/.env <<EOF
APP_PORT=8003
POSTGRES_USER=scorepilot
POSTGRES_PASSWORD=$(openssl rand -hex 24)
POSTGRES_DB=scorepilot

# App-level HTTP Basic auth (the app has no other login). Required for a public
# deploy unless you put basic_auth in the host Caddy instead.
SCOREPILOT_AUTH_USERNAME=scorepilot
SCOREPILOT_AUTH_PASSWORD=$(openssl rand -hex 24)
# Hide the interactive API docs / OpenAPI schema in production.
SCOREPILOT_DOCS_ENABLED=false
EOF
```

The app reads every `SCOREPILOT_*` key in this file (forwarded via `env_file`);
see `deploy/.env.example` for the full list (auth, docs, and the `MAX_UPLOAD_MB` /
`MAX_CELLS` resource caps).

Pick a **free** `APP_PORT` (check with `ss -tlnp | grep :8003`); other apps on the
box already use 8000/8001/8002.

No firewall changes are needed - the host proxy already owns 80/443, and the app
port is loopback-only.

### GitHub secrets and the deploy key

Generate a deploy key on the server and authorize it for the `deploy` user:

```bash
ssh-keygen -t ed25519 -f ~/scorepilot_deploy -N "" -C scorepilot-deploy
mkdir -p ~/.ssh && chmod 700 ~/.ssh
cat ~/scorepilot_deploy.pub >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
cat ~/scorepilot_deploy   # copy this private key into the GitHub secret below
```

Repo → **Settings → Secrets and variables → Actions → Secrets**:

| Secret | Value |
| --- | --- |
| `DEPLOY_HOST` | server IP/hostname |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_SSH_KEY` | the full private key (BEGIN/END lines included) |

Delete the private key from the server afterwards (`rm ~/scorepilot_deploy`).

Also make the **GHCR package public** (your Packages → `scorepilot` → Package
settings → Change visibility → Public) so the server can pull without logging in.

## DNS

Point the subdomain at the server. With Cloudflare, set the record to **DNS only
(grey cloud)** so the host Caddy can obtain its own certificate:

| Type | Name | Value | Proxy |
| --- | --- | --- | --- |
| A | `scorepilot` | server IPv4 | DNS only (grey) |

Verify: `dig +short scorepilot.learnche.org` returns the server IP.

## Wire it into the host Caddy

Add a site block to the host Caddyfile (typically `/etc/caddy/Caddyfile`) - same
shape as the other apps on the box:

```caddyfile
scorepilot.learnche.org {
    reverse_proxy 127.0.0.1:8003
}
```

Then reload: `sudo systemctl reload caddy`. Caddy fetches the Let's Encrypt
certificate automatically once DNS resolves.

## First deploy

Merge to `main`, or **Actions → Deploy → Run workflow**. Then check:

```bash
# on the server
cd /opt/scorepilot && docker compose ps          # app + db should be Up/healthy
curl -s http://127.0.0.1:8003/api/health          # -> {"status":"ok"}
# from anywhere
curl -s https://scorepilot.learnche.org/api/health
```

### Resetting the database (only if the password was changed after first run)

Postgres bakes `POSTGRES_PASSWORD` into its data volume on first init. If you
change it later, the app and db will disagree (app crash-loops on auth). With no
real data yet, reset the volume:

```bash
cd /opt/scorepilot
docker compose down --remove-orphans
docker volume rm scorepilot_pgdata
docker compose up -d        # db re-initialises with the current .env password
```

## Rollback

Images are tagged `latest` and `sha-<commit>`. To pin a previous build, edit the
`app` image tag in `/opt/scorepilot/docker-compose.yml` and `docker compose up -d`.
(The next merge resets it to `latest`.)

## Build / run the image locally

```bash
make image       # builds the frontend, then `docker build -t scorepilot:local .`
make image-run   # runs it on http://localhost:8000 with a throwaway SQLite DB
```

## Notes

- **Auth.** The app ships an optional HTTP Basic gate, off until
  `SCOREPILOT_AUTH_PASSWORD` is set (see the `.env` above). With it set, the whole
  app (API, docs, SPA) requires the credentials and `/api/health` stays open for
  the proxy. You can use the host Caddy's `basic_auth` instead if you prefer.
- **Rate limiting.** Best applied at the host Caddy, which sees real client IPs
  (the app, behind the proxy, only sees the proxy's IP). Example using Caddy's
  `rate_limit` (Caddy v2 with the plugin), in the site block:

  ```caddyfile
  scorepilot.learnche.org {
      rate_limit {
          zone scorepilot { key {remote_host}; events 120; window 1m }
      }
      reverse_proxy 127.0.0.1:8003
  }
  ```
- **Shared state.** Single app process: datasets in memory, models in one Postgres
  DB - concurrent users share state. Fine for team testing; per-user isolation is a
  separate design (issue #6).
- **Backups.** `docker exec scorepilot-db-1 pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql`.
