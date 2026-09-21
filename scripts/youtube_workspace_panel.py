"""Two-brand public UI. No network calls or access to private credential stores."""
from html import escape
import json
from pathlib import Path
from aether_planner import read_catalog, plan

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'data' / 'youtube_ops_snapshot.json'

def _public_snapshot_json():
    if not SNAPSHOT.is_file():
        return 'null'
    data = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or data.get('kind') != 'onnellab_youtube_ops_snapshot':
        raise ValueError('youtube_ops_snapshot_invalid')
    if set(data.get('profiles', {})) - {'onnellab', 'aether_inn'}:
        raise ValueError('youtube_ops_snapshot_profile_invalid')
    # Prevent a future producer change from embedding credential-bearing fields,
    # without rejecting innocent viewer-comment text containing similar words.
    forbidden = {'refresh_token', 'client_secret', 'access_token', 'authorization'}
    def visit(value):
        if isinstance(value, dict):
            if any(str(key).lower() in forbidden for key in value):
                raise ValueError('youtube_ops_snapshot_secret_field')
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    visit(data)
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', r'<\/')

def youtube_workspace_panel():
    catalog = json.loads((ROOT / 'data/aether_catalog.json').read_text(encoding='utf-8'))
    rows = catalog['songs']
    if catalog['declared_count'] != len(rows):
        raise ValueError('aether_catalog_count_mismatch')
    cards = []
    for row in rows:
        seconds = row['duration_seconds']
        if type(seconds) is not int or not 0 < seconds < 3600:
            raise ValueError('invalid_catalog_duration')
        cards.append('<details class="ytw-song"><summary><span>' + escape(row['title']) +
            '</span><time>' + f'{seconds // 60}:{seconds % 60:02d}' + '</time></summary><p>' +
            escape(row['style']) + '</p></details>')
    template = (ROOT / 'templates/youtube_workspace.html').read_text(encoding='utf-8')
    mix = plan(read_catalog())
    chapter_rows = ''.join('<div class="ytw-plan-track"><time>' + c['timestamp'] + '</time> ' + escape(c['title']) + '</div>' for c in mix['chapters'])
    panel = template.replace('__TRACK_COUNT__', str(len(rows))).replace('__CATALOG_ROWS__', ''.join(cards)).replace('__MIX_CHAPTERS__', chapter_rows)
    marker='</section>\n<script>'
    if marker not in panel:
        raise ValueError('youtube_workspace_script_marker_missing')
    return panel.replace(marker, '</section>\n<script id="ytw-public-snapshot" type="application/json">' + _public_snapshot_json() + '</script>\n<script>', 1)
