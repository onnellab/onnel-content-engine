"""User-excluded channels retain historical artifacts but cannot accept new work."""
USER_EXCLUDED_PLATFORMS = frozenset({'hashnode', 'medium'})


def channel_excluded(platform):
    return platform in USER_EXCLUDED_PLATFORMS
