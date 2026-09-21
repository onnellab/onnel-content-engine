"""Literal brand identities shared by setup, reporting and upload routing."""
from short_video_pipeline import VideoError

PROFILES = {'onnellab': 'ONNELLAB', 'aether_inn': 'Aether Inn'}
ROUTES = {'app_promo': 'onnellab', 'aether_single': 'aether_inn', 'aether_compilation': 'aether_inn'}
ANALYTICS_SCOPE = 'https://www.googleapis.com/auth/yt-analytics.readonly'

def profile_id(value):
    if not isinstance(value, str) or value not in PROFILES:
        raise VideoError('unknown_youtube_profile')
    return value

def content_profile(brief):
    expected = ROUTES.get(brief.get('content_kind', 'app_promo'))
    if expected is None or brief.get('youtube_profile', expected) != expected:
        raise VideoError('youtube_content_profile_mismatch')
    return expected

def require_content_profile(brief, profile):
    if content_profile(brief) != profile_id(profile):
        raise VideoError('youtube_content_profile_mismatch')

def environment_names(profile):
    prefix = '' if profile_id(profile) == 'onnellab' else 'AETHER_INN_'
    return tuple(prefix + 'YOUTUBE_' + part for part in ('CLIENT_ID', 'CLIENT_SECRET', 'REFRESH_TOKEN', 'CHANNEL_ID'))
