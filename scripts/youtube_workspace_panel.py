"""Two-brand public UI. No network calls or access to private credential stores."""
from html import escape
import json
from pathlib import Path
from aether_planner import read_catalog, plan

ROOT = Path(__file__).resolve().parents[1]

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
    return template.replace('__TRACK_COUNT__', str(len(rows))).replace('__CATALOG_ROWS__', ''.join(cards)).replace('__MIX_CHAPTERS__', chapter_rows)
