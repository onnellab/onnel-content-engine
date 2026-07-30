#!/usr/bin/env python3
"""Validate centralized app privacy-policy data and localized rendering."""

from __future__ import annotations

import sys

from publishing import (
    DEFAULT_APPS_REGISTRY_PATH,
    DEFAULT_PRIVACY_POLICIES_PATH,
    PublishingError,
    load_privacy_policies,
    localized_policy_markdown,
)


def main() -> int:
    try:
        payload, policies = load_privacy_policies(
            DEFAULT_PRIVACY_POLICIES_PATH,
            DEFAULT_APPS_REGISTRY_PATH,
        )
        developer_name = str(payload.get("developer_name") or "")
        contact_email = str(payload.get("contact_email") or "")
        for policy in policies:
            for language in ("en", "ko"):
                rendered = localized_policy_markdown(
                    policy,
                    language,
                    developer_name,
                    contact_email,
                )
                required = (
                    str(policy["app_name"]),
                    developer_name,
                    contact_email,
                    str(policy["last_updated"]),
                )
                if any(value not in rendered for value in required):
                    raise PublishingError(
                        f"{policy['app_slug']} {language} privacy policy omitted required identity or contact data"
                    )
    except (OSError, ValueError, KeyError, TypeError, PublishingError) as error:
        print(f"app privacy policy validation failed: {error}", file=sys.stderr)
        return 1
    print(f"validated {len(policies)} app privacy policies in English and Korean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
