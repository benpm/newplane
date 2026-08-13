# Deployment Guide

## Overview

Plane uses an **offline-first GitLab CI/CD pipeline** with two deployment models:

- **Dev deployments**: Automatic via `deploy:external-test` job on merge to `develop` branch
- **Release deployments**: Manual via `deploy:external-test` (dev) or `release:production` (prod) jobs using packages from GitLab Generic Package Registry

All runners execute on their target servers — **no SSH/SCP** required for internal deploys.

## Quick Start

### For Operations Teams

1. [Setup Runners & Tokens](./setup-runners.md) — Register runners, create deploy/publish tokens
2. [Configure Environment](./environment-setup.md) — Set up `/etc/plane-release-deploy.env` on each server
3. [Understand Workflow](./deployment-workflow.md) — Learn manual and automatic triggers
4. [Rollback Procedure](./rollback.md) — Archive-based rollback for each release

### For Developers

- **Automatic:** Merge to `develop` branch → Pipeline automatically deploys to dev
- **Manual:** Use GitLab CI/CD UI to trigger `deploy:external-test` with explicit `RELEASE_TAG`

### Architecture

```
Commit to develop/preview
    ↓
Build (web, admin, api → tar.gz images)
    ↓
Deploy:dev (auto) OR Release:publish → GitLab Package Registry
    ↓
Deploy:dev:release / Deploy:prod:release (manual) — downloads from Registry
    ↓
Deploy-from-internal-gitlab-release.sh (local, no SSH)
    ↓
docker-compose up + migrations + smoke tests
    ↓
Archive previous for rollback
```

## Key Concepts

| Concept                     | Purpose                                                 |
| --------------------------- | ------------------------------------------------------- |
| **Deploy Runner**           | Executes on target server, no SSH credentials needed    |
| **GitLab Package Registry** | Stores release packages (zip) as source-of-truth        |
| **Release Tags**            | `dev/vX.Y.Z-build.N` or `prod/vX.Y.Z` trigger stages    |
| **Archive Retention**       | Keeps last N releases for instant rollback              |
| **Offline Cache**           | `/opt/plane-cache/` on dev server for air-gapped builds |

## Files Referenced

| File                                       | Purpose                                                     |
| ------------------------------------------ | ----------------------------------------------------------- |
| `scripts/plane deploy ci`                  | Automatic dev deployment (CI artifacts → docker-compose up) |
| `scripts/plane deploy from-gitlab`         | Release deploy (GitLab Registry → verify → deploy)          |
| `scripts/plane deploy release`             | Core deployment logic (migrations, health checks)           |
| `scripts/plane release publish`            | Create zip, upload to GitLab                                |
| `scripts/plane release verify`             | Verify all images are linux/amd64                           |
| `scripts/plane-release-deploy.env.example` | Env template for deploy credentials                         |
| `.gitlab-ci.yml`                           | Pipeline definition (build → deploy → release)              |

---

**See also:**

- [Setup Runners & Tokens](./setup-runners.md)
- [Environment Configuration](./environment-setup.md)
- [Deployment Workflow](./deployment-workflow.md)
- [Rollback & Recovery](./rollback.md)
- [Health & Monitoring](./health-monitoring.md)

**Last Updated:** 2026-05-04
**Version:** 2.0
