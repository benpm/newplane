# Authentication and email setup

How people get into this instance, and the two settings that are currently
switched off. Both are configured in **God Mode**
(`https://plane.mousetrip.online/god-mode/`), which writes to the
`instance_configurations` table — not to a `.env` file. Nothing here needs a
rebuild or a redeploy; the settings are read per request.

## Current state

| Setting                                                                 | State                              | Effect                                             |
| ----------------------------------------------------------------------- | ---------------------------------- | -------------------------------------------------- |
| `ENABLE_EMAIL_PASSWORD`                                                 | on                                 | Email + password sign-in works                     |
| `ENABLE_MAGIC_LINK_LOGIN`                                               | on                                 | But magic codes are emailed, so they cannot arrive |
| `IS_GOOGLE_ENABLED`                                                     | **off** (no row → env default `0`) | Google button hidden everywhere                    |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`                             | **empty**                          | —                                                  |
| `EMAIL_HOST` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `EMAIL_FROM` | **empty**                          | No email is delivered at all                       |

Everyone on the instance has signed in by email and password. Google has never
completed a sign-in here, and no invitation email has ever been delivered.

---

## Google SSO

The sign-in and sign-up pages hide the Google button when the instance reports
Google as unconfigured — that is `config.is_google_enabled` in
`core/hooks/oauth/core.tsx`, fed by `IS_GOOGLE_ENABLED` in
`license/api/views/instance.py`. The button is missing because the setting is
off, not because the page is broken. Turning it on makes the button appear on
sign-in, sign-up **and** the `/invite/<token>` landing page, which shares the
same `AuthRoot` component.

### 1. Create the OAuth client

In the [Google Cloud console](https://console.cloud.google.com/apis/credentials),
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
credentials alone leaves the button hidden.

### 3. Existing accounts link automatically

`adapter/base.py` looks users up by email alone, so signing in with Google using
the address of an existing password account signs into **that** account and
associates the Google identity with it. It does not create a second account, and
the existing password keeps working. No migration or manual linking step.

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
