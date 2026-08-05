# Security audit — newer source branch vs. running image

**Date:** 2026-08-05
**Question:** what would upgrading the live instance to the current source branch cost, security-wise?

## Subjects

| | Running image (`plane-api:latest`) | Source tree |
|---|---|---|
| Lineage | older Plane + security backports | `benpm/newplane`, branch `ben/feat/todo-github-sync-features` |
| Migration head | `0121_alter_estimate_type` (= live DB) | `0182_github_wiki_page_link` |
| Delta | — | 61 migrations, 196 differing files under `plane/` |

Not the same app with one side patched — different versions on different lineages. Audit is
code-level (no probing of the live instance).

## Regressions inherited on upgrade

### R1 — Invite token disclosure + unauthenticated acceptance — HIGH

`WorkspaceJoinEndpoint` is `permission_classes = [AllowAny]` (`app/views/workspace/invite.py:281`).

- **GET** `/workspaces/{slug}/invitations/{pk}/` (`invite.py:384`) serializes with
  `WorkSpaceMemberInviteSerializer`, whose `Meta.fields = "__all__"` includes `token`, plus an
  `invite_link` SerializerMethodField that embeds the token
  (`app/serializers/workspace.py:109-129`). Unauthenticated caller gets the acceptance token.
- **POST** (`invite.py:293-303`) checks only `workspace_invite.token != token`. No
  `request.user.is_authenticated`, no email match.

Image blocks both ends: `WorkSpaceMemberInvitePublicSerializer` omits `token`/`invite_link`
(cites GHSA-86mg-259g-pwgg, GHSA-gf48-p6jp-cwc4), and POST requires an authenticated session
whose email matches the invite (cites GHSA-4vj8-p63v-8p24).

Impact: anyone holding an invite `pk` — forwarded mail, referrer header, browser history, logs —
reads the token, then force-accepts or force-declines on the invitee's behalf. With
`ENABLE_SIGNUP=1` (current instance setting) an email-squatter who registers the invited address
first converts this into real workspace membership.
Mitigating: `pk` is a UUID, not enumerable.

### R2 — `WorkspaceFileAssetEndpoint` has no authorization decorator — HIGH

`post/patch/delete/get` at `app/views/asset/v2.py:314,379,400,409` carry no `@allow_permission`,
unlike every sibling endpoint in the same file (`AssetRestore`, `ProjectAsset`, `AssetCheck`,
`DuplicateAsset`, both Download endpoints all have one). They fall back to
`BaseAPIView.permission_classes = [IsAuthenticated]` (`app/views/base.py:150`).

Bodies do `FileAsset.objects.get(id=asset_id, workspace__slug=slug)` with no membership check.

Impact: any authenticated user of any workspace can read (via signed URL), overwrite `attributes`,
or soft-delete assets belonging to a workspace they are not a member of. Cross-tenant.
Mitigating: asset UUID required; `AssetRateThrottle` caps `asset_id` at 5/min.

### R3 — No filename sanitization on upload paths — MEDIUM

`sanitize_filename` has **zero** occurrences in source. Image applies it at 4 sites before
user-supplied names are interpolated into S3 object keys (`v2.py` post handlers, duplicate
handler). Source's `utils/path_validator.py` is an unrelated module (URL redirect safety) — no
drop-in replacement exists.

### R4 — Bulk asset attach not project-scoped — MEDIUM

`v2.py:655`: `FileAsset.objects.filter(id__in=asset_ids, workspace__slug=slug)` then
`.update(project_id=project_id)`. Workspace-scoped only, so assets belonging to project A can be
re-parented into project B by a member of B. Image scopes to `project_id` with a narrow
`Q(project_id__isnull=True, entity_type=PROJECT_COVER, created_by=request.user)` exception so
project-cover creation still works. This is also where the cover-image fix lives.

### R5 — Asset duplication not workspace-scoped — MEDIUM

`v2.py:765`: `FileAsset.objects.filter(id=asset_id, is_uploaded=True).first()` — no workspace
filter. Source asset from any workspace can be copied into the caller's. Image adds
`workspace=workspace`.

### R6 — Webhook SSRF validated at registration only, not delivery — MEDIUM

Source validates resolved IPs in `app/serializers/webhook.py` create/update. `bgtasks/webhook_task.py`
has no validation at send time → DNS rebinding between registration and delivery.
Source's other SSRF guard (`bgtasks/work_item_link_task.py:27` `validate_url_ip`) is
resolve-then-fetch, also TOCTOU-vulnerable, and relies on stdlib `is_private/is_loopback/
is_reserved/is_link_local`.

Image has `utils/url_security.py`: connection pinned to the validated IP, redirects followed
manually with re-resolution at each hop, wired into `webhook_task.py`. Its `utils/ip_address.py`
uses an explicit CIDR blocklist, with a comment noting stdlib flags miss carrier-grade NAT
(100.64.0.0/10) — exactly the gap the source version has.

Mitigating: requires webhook-create permission (admin) plus attacker-controlled DNS.

### R7 — Static asset endpoint serves script-capable MIME inline — LOW/MEDIUM

`v2.py:475` `generate_presigned_url(object_name=...)` uses the default `disposition="inline"`.
Image forces `attachment` when the asset's MIME is in `SCRIPT_CAPABLE_MIME_TYPES` (absent from
source), preventing stored XSS when assets are served on the app origin.
Partial credit: source *does* force attachment on `WorkspaceFileAssetEndpoint.get` (`v2.py:424-428`).

### R8 — Security test coverage lost

Image-only: `tests/unit/bg_tasks/test_ssrf_advisories.py` (rebinding + internal-target cases),
`tests/contract/api/test_authentication.py`, `tests/contract/app/test_project_member_is_active_authz.py`,
`test_generic_asset.py`, `test_projects.py`, `test_issues.py`, `test_issue_notifications.py`.

## Improvements gained on upgrade

- **I1** — Soft-deleted assets 404 at the public `StaticFileAssetEndpoint` (`v2.py:449-455`).
  Image lacks this guard and keeps serving deleted content from its unguessable URL.
- **I2** — Workspace asset download forces `Content-Disposition: attachment` with the original
  filename (`v2.py:424-428`).
- **I3** — Fail-closed menu RBAC for god-mode instance admins (`838e9b99d7`), with RBAC
  invariant test coverage (`1bed3ce0b2`).
- **I4** — 61 migrations' worth of upstream fixes not individually enumerated here.

## Verdict

Net **negative** on security as-is: 7 code regressions (2 HIGH) against 3 targeted improvements.
The regressions are small and localized — roughly one serializer + two guards in `invite.py`,
four decorators + membership scoping in `v2.py`, one new util + its call sites, two query
scopings, and one SSRF module wired into `webhook_task.py`.

Recommended order if upgrading: port R1–R7 onto the branch first, re-add R8's tests, then
migrate. Reference implementations are in the backup at
`code-patches/image-plane-app/` (also inside `/home/beb/plane-backup-20260805.zip`).

Separately, and larger than security: applying 61 migrations to the live DB is effectively
one-way. Take a fresh dump immediately before, and rehearse on a restored copy first.

## Upstream advisory check (added after initial audit)

Queried `gh api /repos/makeplane/plane/security-advisories`. The GHSA IDs cited in the image's
code comments are **real** repo-level advisories (they 404 from the *global* DB because they
haven't propagated there). Six criticals were published 2026-08-03 — two days ago.

**Every finding in this audit has an official upstream fix, all landing in Plane 1.4.0.**
Source `package.json` reports version **1.2.0**; the advisories cover `<= 1.3.1`.

| GHSA | Sev | Patched | Maps to |
|---|---|---|---|
| GHSA-4vj8-p63v-8p24 | critical | 1.4.0 | **R1** — "Pre-auth workspace invitation hijack via email-squat and self-served invitation token leak" |
| GHSA-r2hw-fff3-pjwp | critical | 1.4.0 | **R4** — "Cross-Project Asset Hijacking via ProjectBulkAssetEndpoint" |
| GHSA-mq87-52pf-hm3h | critical | 1.4.0 | **R6** — "SSRF via HTTP redirect in webhook delivery (allow_redirects not set)" |
| GHSA-mqjv-rwgv-4gxq | critical | 1.4.0 | **new R9** — magic-code verifier OTP brute force |
| GHSA-cmwv-pjmw-8483 | critical | 1.4.0 | hardcoded deploy secrets — *not exploitable here*, see below |
| GHSA-7j95-vh8g-f365 | critical | 1.4.0 | OAuth ATO (Gitea / self-managed GitLab) — *not applicable*, no OAuth configured |
| GHSA-qw87-v5w3-6vxx (CVE-2026-46558) | high | 1.3.1 | **R2 + R5** — cross-workspace asset read/copy/delete/overwrite |
| GHSA-fpx8-73gf-7x73 (CVE-2026-30242) | high | 1.2.3 | **R6** — incomplete IP validation in webhook serializer |

### R9 — Magic-code verifier unthrottled (new, CRITICAL)

Found while checking GHSA-mqjv-rwgv-4gxq. Source `authentication/views/app/magic.py`:
`MagicSignInEndpoint` (:61) and `MagicSignUpEndpoint` (:132) subclass plain Django `View`, so the
`throttle_classes = [AuthenticationThrottle]` on `MagicGenerateEndpoint` (:36) does not cover
them — only code *generation* is rate-limited, not *verification*. Image adds explicit
`authentication_throttle_allows(request)` guards in both verifier paths
(`magic.py:71,154`). Unlimited 6-digit OTP guessing.

### Live-instance exposure checks

- **GHSA-cmwv-pjmw-8483 — NOT affected.** The advisory's hardcoded values are
  `SECRET_KEY=60gp0byfz2dv…` / `LIVE_SERVER_SECRET_KEY=htbqvBJAgpm9…`. This instance runs
  `cwrswp0nph3a…` / `x8sz147gwtjw…`, randomized by `setup.sh` on the docker-compose path.
  Note the source tree **does** still ship the vulnerable defaults at
  `deployments/aio/community/variables.env:29,53` and `deployments/cli/community/variables.env:57`
  — only relevant if this deployment is ever re-provisioned via the aio/cli path.
- **GHSA-7j95-vh8g-f365 — NOT applicable.** All OAuth client IDs/secrets are empty in
  `instance_configurations` (Gitea, GitLab, GitHub, Google).

### Revised recommendation

Hand-porting R1–R7 is now the *worse* option. Upstream 1.4.0 contains official, tested fixes for
all of them plus R9 and two more criticals this audit did not reach. The running image is an
older Plane carrying hand-backported versions of these same fixes — which is why its code
comments cite these exact GHSA IDs.

**Blocked on a project rule:** `CLAUDE.md` states "❌ NEVER pull/merge/rebase from upstream
(`makeplane/plane`)". Taking 1.4.0 requires an explicit exception from the repo owner. Not
actioned. The fork carries ~7.8k commits of divergence (help center, god-mode RBAC, GitHub sync),
so this is a real merge, not a fast-forward.

## Unresolved questions

1. Upgrade path — merge upstream 1.4.0 into the fork (needs the CLAUDE.md rule waived), or
   backport the 1.4.0 security commits only, as the image's builder evidently did?
2. Is the fork's `upstream` remote (`shbvn/plane`) already carrying 1.4.0 backports? Not checked;
   would be the sanctioned route since it isn't `makeplane/plane`.
3. Two criticals were confirmed by advisory metadata but not code-audited here
   (GHSA-7j95 OAuth ATO, GHSA-cmwv secrets) because neither applies to this deployment. They
   would matter if OAuth is ever enabled or the stack re-provisioned via aio/cli.
4. Is the fork's own `_add_admin_to_all_projects` auto-join path (`invite.py:45`) in scope for a
   follow-up review? It grants role 20 across all projects and was not audited here.
5. Was the source branch's omission of these guards deliberate, or just a lineage that never
   received the backports? Given upstream 1.4.0 postdates the branch, the latter is likely.
