"""Public platform evidence for new video product snapshots and recordings."""
import csv
from pathlib import Path


def public_video_platforms(app, store_versions_path):
    """A platform target or configured URL alone is not proof of a release."""
    app_id = (app.get('app_id') or '').strip()
    if not app_id:
        return []
    try:
        with Path(store_versions_path).open(encoding='utf-8', newline='') as handle:
            stores = list(csv.DictReader(handle))
    except (OSError, UnicodeError, csv.Error):
        return []
    targets = set(app.get('platforms', '').split('|'))
    platforms = []
    for platform, url_field in [('ios', 'app_store_url'), ('android', 'play_store_url')]:
        url = (app.get(url_field) or '').strip()
        if platform not in targets or not url:
            continue
        if any(
            (row.get('app_id') or '').strip() == app_id
            and (row.get('platform') or '').strip() == platform
            and (row.get('store_url') or '').strip() == url
            and row.get('status') in {'new', 'updated', 'unchanged'}
            and (row.get('version') or '').strip()
            for row in stores
        ):
            platforms.append(platform)
    return platforms
