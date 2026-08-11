# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Derivation of the synthetic email address used for Swing SSO accounts.

Swing SSO authenticates by staff ID, not by email, so Plane mints a synthetic
address per staff member and uses it as the User lookup key. The domain is
instance configuration rather than a constant: it used to be hardcoded to the
originating bank's domain, and an operator upgrading from that build keeps
their existing accounts by setting SWING_SSO_EMAIL_DOMAIN back to it.

Changing the domain on a live instance does NOT rename existing users — it only
affects addresses minted from that point on.
"""

import os

# Local part prefix. Retained verbatim from the pre-de-branding builds: it is
# baked into every existing account's email, so changing it would orphan them.
STAFF_EMAIL_PREFIX = "sh"

DEFAULT_STAFF_EMAIL_DOMAIN = "swing.local"


def get_staff_email_domain() -> str:
    """Resolve the configured Swing SSO email domain, falling back to the default."""
    # Imported lazily: plane.license imports plane.db.models, and this helper is
    # called from a model property.
    from plane.license.utils.instance_value import get_configuration_value

    (domain,) = get_configuration_value(
        [
            {
                "key": "SWING_SSO_EMAIL_DOMAIN",
                "default": os.environ.get("SWING_SSO_EMAIL_DOMAIN", DEFAULT_STAFF_EMAIL_DOMAIN),
            }
        ]
    )
    return domain or DEFAULT_STAFF_EMAIL_DOMAIN


def staff_email(staff_id) -> str:
    """Return the synthetic login email for a staff ID."""
    return f"{STAFF_EMAIL_PREFIX}{staff_id}@{get_staff_email_domain()}"
