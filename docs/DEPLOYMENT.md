# Deploying ScorePilot (Hetzner, auto-deploy on merge)

Every push to `main` builds a container image and deploys it to a Hetzner server,
which serves the app over HTTPS on a public subdomain. Data is stored in
**Postgres**. Nothing environment-specific lives in the repo - the server URL,
domain, and credentials are GitHub secrets and a server-side `.env`.

## How it works

```
push to main ──> GitHub Actions (deploy.yml)
                   1. build the Svelte frontend
                   2. build a Python image, push to GHCR (ghcr.io/kgdunn/scorepilot)
                   3. scp deploy/ files to the server, then SSH:
                        docker compose pull && docker compose up -d
                 ──> Hetzner: Caddy (TLS) -> app -> Postgres
```

The compose stack (`deploy/docker-compose.yml`) runs three services: `caddy`
(automatic HTTPS + reverse proxy), `app` (the image), and `db` (Postgres 16 with a
named volume). On start, the app runs `alembic upgrade head` then serves.

## One-time server setup

On a fresh Hetzner VPS (Ubuntu 22.04+):

```bash
# 1. Install Docker + the compose plugin
curl -fsSL https://get.docker.com | sh

# 2. Create the deploy directory
sudo mkdir -p /opt/scorepilot && sudo chown "$USER" /opt/scorepilot

# 3. Create the environment file (copy the example from the repo, then edit)
#    The compose stack reads /opt/scorepilot/.env
nano /opt/scorepilot/.env
```

Fill `/opt/scorepilot/.env` using `deploy/.env.example` as the template:

```ini
DOMAIN=scorepilot.example.com
TLS_EMAIL=you@example.com
POSTGRES_USER=scorepilot
POSTGRES_PASSWORD=<long-random-secret>
POSTGRES_DB=scorepilot
```

4. **DNS:** point an `A` (and `AAAA` if you have IPv6) record for the subdomain at
   the server's IP. Caddy obtains a Let's Encrypt certificate automatically once
   the record resolves.

5. **Firewall:** allow inbound `80` and `443` (Caddy needs both; 80 is used for the
   ACME challenge and redirects to HTTPS).

   ```bash
   sudo ufw allow 80,443/tcp
   ```

6. **GHCR image access.** The deploy pulls `ghcr.io/kgdunn/scorepilot`. Easiest is
   to make that package **public** (GitHub → your profile → Packages → scorepilot →
   Package settings → Change visibility → Public). If you prefer to keep it private,
   run `docker login ghcr.io` on the server once with a read-only PAT.

## One-time GitHub setup

Create a deploy SSH key and add three repository secrets.

```bash
# On your laptop: generate a dedicated key (no passphrase)
ssh-keygen -t ed25519 -f scorepilot_deploy -C "scorepilot-deploy"

# Add the PUBLIC key to the server account that runs Docker
ssh-copy-id -i scorepilot_deploy.pub <DEPLOY_USER>@<SERVER_IP>
```

Then in the repo: **Settings → Secrets and variables → Actions → New secret**:

| Secret           | Value                                  |
| ---------------- | -------------------------------------- |
| `DEPLOY_HOST`    | server IP or hostname                  |
| `DEPLOY_USER`    | the SSH user (member of the docker group) |
| `DEPLOY_SSH_KEY` | contents of the **private** `scorepilot_deploy` key |

No registry secret is needed - the build pushes to GHCR using the built-in
`GITHUB_TOKEN`.

## First deploy

Either merge a PR to `main`, or trigger it manually: **Actions → Deploy → Run
workflow**. After it finishes, check:

```bash
curl https://scorepilot.example.com/api/health   # -> {"status":"ok"}
```

Open `https://scorepilot.example.com` in any browser (including your phone).

## Rollback

Images are tagged `latest` and `sha-<commit>`. To roll back, on the server:

```bash
cd /opt/scorepilot
# pin a previous build
sed -i 's#scorepilot:latest#scorepilot:sha-<good-commit>#' docker-compose.yml
docker compose up -d
```

(The next merge resets the tag to `latest`.)

## Build / run the image locally

Building the image requires the frontend to be built first (it is baked in):

```bash
make image       # builds the frontend, then `docker build -t scorepilot:local .`
make image-run   # runs it on http://localhost:8000 with a throwaway SQLite DB
```

To exercise the Postgres path locally:

```bash
docker run -d --name sp-pg -e POSTGRES_PASSWORD=pw -e POSTGRES_USER=sp \
  -e POSTGRES_DB=scorepilot -p 5433:5432 postgres:16
SCOREPILOT_DATABASE_URL=postgresql+psycopg://sp:pw@127.0.0.1:5433/scorepilot \
  uv run alembic upgrade head
SCOREPILOT_DATABASE_URL=postgresql+psycopg://sp:pw@127.0.0.1:5433/scorepilot \
  uv run scorepilot
```

## Notes and next steps

- **Auth (planned).** The site is currently public with no login. Add HTTP basic
  auth in `deploy/Caddyfile` when ready:

  ```caddyfile
  {$DOMAIN} {
      basic_auth {
          {$BASIC_AUTH_USER} {$BASIC_AUTH_HASH}
      }
      reverse_proxy app:8000
  }
  ```

  (Generate the hash with `docker run caddy caddy hash-password`.)
- **Shared state.** It is a single app process: uploaded datasets are in memory and
  models share one Postgres database, so concurrent users share state. Fine for
  team testing; per-user isolation is a separate design (issue #6).
- **Backups.** Postgres data lives in the `pgdata` volume. Back up with
  `docker exec <db> pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql`.
- **Resources.** PCA/PLS on typical datasets is light; a small Hetzner CX/CPX
  instance is plenty.
