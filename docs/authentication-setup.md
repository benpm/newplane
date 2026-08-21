# Authentication and email setup

How people get into this instance, and what is still switched off. Everything
here is configured in **God Mode**
(`https://plane.mousetrip.online/god-mode/`), which writes to the
`instance_configurations` table — not to a `.env` file. Nothing here needs a
rebuild or a redeploy; the settings are read per request.

## Current state

| Setting                                                                 | State                | Effect                                             |
| ----------------------------------------------------------------------- | -------------------- | -------------------------------------------------- |
| `ENABLE_SIGNUP`                                                         | `1`                  | Anyone with a link can create an account           |
| `ENABLE_EMAIL_PASSWORD`                                                 | `1`                  | Email + password sign-in works                     |
| `IS_GOOGLE_ENABLED`                                                     | `1` since 2026-08-21 | Google button shows on sign-in, sign-up, `/invite` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`                             | set                  | Client owned by project `mousetrip`                |
| `ENABLE_MAGIC_LINK_LOGIN`                                               | `0`                  | Off, and it would need email anyway                |
| `ENABLE_SMTP`                                                           | `0`                  | Flips to `1` on its own when the email form saves  |
| `EMAIL_HOST` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `EMAIL_FROM` | **empty**            | No email is delivered at all                       |
| `EMAIL_PORT` / `EMAIL_USE_TLS` / `EMAIL_USE_SSL`                        | `587` / `1` / `0`    | Already consistent; leave alone                    |

Email is still the gap, and it is worth being precise about the consequence:
password reset goes over SMTP too (`bgtasks/forgot_password_task.py`), so a user
who forgets their password has no self-service way back in. Google sign-in now
gives them a second route, but only if they used a Google address.

---

## Google SSO

Configured and live on production since 2026-08-21. The steps below are the
record of how, and what to repeat for another host.

The sign-in and sign-up pages hide the Google button whenever the instance
reports Google as unconfigured — that is `config.is_google_enabled` in
`core/hooks/oauth/core.tsx`, fed by `IS_GOOGLE_ENABLED` in
`license/api/views/instance.py`. So a missing button means the setting is off,
not that the page is broken; that is worth checking before debugging anything in
the frontend. With it on, the button appears on sign-in, sign-up **and** the
`/invite/<token>` landing page, which shares the same `AuthRoot` component.

### 1. Create the OAuth client

This step is **console-only — there is no CLI or API for it.** Do not spend time
looking: the one programmatic path Google ever offered was the IAP OAuth Admin
API (`gcloud alpha iap oauth-clients create`), which was permanently shut down on
19 March 2026, and which could not set custom redirect URIs anyway because the
clients it made were owned by IAP. Nothing replaced it — `gcloud services list`
shows no OAuth-client-management API. The project here is `mousetrip`
(number 847000914006).

In the [Google Cloud console](https://console.cloud.google.com/apis/credentials?project=mousetrip),
create an **OAuth 2.0 Client ID** of type _Web application_, and register this
exact **authorised redirect URI**:

```
https://plane.mousetrip.online/auth/google/callback/
```

The trailing slash matters — the URL is built in
`authentication/provider/oauth/google.py` from `request.get_host()`, and Google
matches redirect URIs by exact string. A mismatch fails with
`redirect_uri_mismatch` at the Google end, before any Plane code runs.

Add the same URI with the dev-site host if you want Google on the dev stack too;
a client can hold several.

### 2. Paste it into God Mode

**God Mode → Authentication → Google**: paste the client ID and secret, and turn
the toggle on. The toggle is what sets `IS_GOOGLE_ENABLED`; filling the
credentials alone leaves the button hidden. The page shows the callback URI it
expects, which is the same one above — worth comparing against what you gave
Google.

**Do not write these straight into the database.** `GOOGLE_CLIENT_SECRET` is
stored Fernet-encrypted with a key derived from `SECRET_KEY`
(`license/utils/encryption.py`, `is_encrypted: True` in
`utils/instance_config_variables/core.py`), so a plain `UPDATE` produces a row
that looks right and fails to decrypt at sign-in time. `GOOGLE_CLIENT_ID` is
plaintext, which makes the mistake easy to half-make. Go through God Mode, or
through `encrypt_data()` in a Django shell.

**If you do write config outside God Mode, invalidate the cache afterwards.**
`/api/instances/` is wrapped in `@cache_response(60 * 60 * 2, user=False)`, and
the God Mode config endpoints carry a matching
`@invalidate_cache(path="/api/instances/", user=False)`. Change the rows without
that second half and the API keeps serving the old answer for up to two hours —
correct in the database, `is_google_enabled: false` on the wire, button still
hidden, nothing in any log to say why. The fix:

```bash
docker exec api sh -c 'cd /code && PYTHONPATH=/code python -c "
import os, django
os.environ.setdefault(\"DJANGO_SETTINGS_MODULE\", \"plane.settings.production\")
django.setup()
from plane.utils.cache import invalidate_cache_directly
invalidate_cache_directly(path=\"/api/instances/\", user=False)"'
```

### 3. Existing accounts link automatically

`adapter/base.py` looks users up by email alone, so signing in with Google using
the address of an existing password account signs into **that** account and
associates the Google identity with it. It does not create a second account, and
the existing password keeps working. No migration or manual linking step.

### 4. Verify without a browser

Two checks get you most of the way. First, that the instance advertises Google:

```bash
curl -s https://plane.mousetrip.online/api/instances/ | grep -o '"is_google_enabled":[a-z]*'
```

Second, that Google accepts the client — follow the initiate endpoint and read
the `Location` it hands back:

```bash
curl -s -o /dev/null -D - https://plane.mousetrip.online/auth/google/ | grep -i '^location'
```

The `client_id` and `redirect_uri` in that URL must match the console exactly.
Fetching it should end on Google's own sign-in page; a `redirect_uri_mismatch`
or `invalid_client` error page instead means the console and this instance
disagree. Only the final leg — a real account consenting — needs a browser.

### The dev stack is not covered

The client registered here lists only `https://plane.mousetrip.online`. Google
matches redirect URIs by exact string, so Google sign-in on the dev site fails
with `redirect_uri_mismatch` until the dev host is added to the same client's
authorised redirect URIs. `IS_GOOGLE_ENABLED` was set on production only.

---

## Email (SMTP)

Nothing is delivered today: workspace and project invitations, magic-link codes,
forgotten-password links and notification digests all go out over SMTP, and
`EMAIL_HOST` is empty. Django dials host `""`, the OS refuses the connection, and
the task gives up.

Since the guard added alongside this document, that shows up in the worker log as

```
SMTP is not configured, so the invitation to <address> was not emailed.
```

rather than a `ConnectionRefusedError` traceback that reads like an outage. If
you see the traceback instead of the warning, the worker is running an image
built before that change.

### Configure it

**God Mode → Email**, filling every field:

| Field                                     | Notes                                                                                  |
| ----------------------------------------- | -------------------------------------------------------------------------------------- |
| `EMAIL_HOST`                              | The one field with no usable default; empty here means "off"                           |
| `EMAIL_PORT`                              | Already `587`                                                                          |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | For Gmail this must be an **app password**, not the account password                   |
| `EMAIL_FROM`                              | Must be an address the provider will let you send as, or mail is accepted then dropped |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL`         | TLS on port 587, SSL on 465 — exactly one of the two                                   |

Saving the form sets `ENABLE_SMTP` to `1` for you (`email-config-form.tsx`), so
there is no separate switch to hunt for.

### Verify it

There is a management command that sends one real message using the stored
configuration, which isolates SMTP from the rest of the app:

```bash
docker compose exec api python manage.py test_email you@example.com
```

A traceback here is an SMTP problem. Success plus a missing invitation is a Celery
problem — check `docker compose logs bgworker`.

---

## Invitations without email

Invitations do not depend on any of the above, which is why the instance has been
usable without SMTP:

- **[Reusable workspace invite links](./features.md#reusable-workspace-invite-links)** —
  Workspace Settings → Members. One link, any number of people, valid until
  revoked. Nothing is emailed.
- **Per-email invites** still record their rendered body on the invite row even
  when SMTP is off, so an admin can pass the text on by hand. The guard in
  `bgtasks/workspace_invitation_task.py` deliberately sits _after_ that write for
  this reason.
- **God Mode → Users** creates named invite links directly.

With Google SSO on, the invite link covers the full flow the fork was built for:
one link, opened by anyone, who then joins with either a password or Google.
