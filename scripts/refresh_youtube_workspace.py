"""Refresh only the YouTube workspace, preserving every other dashboard byte."""
import argparse
from pathlib import Path
from youtube_workspace_panel import youtube_workspace_panel

def replace_workspace(page):
    anchor='<section class="ytw" id="youtube-brands"'
    if page.count(anchor)!=1:raise ValueError('ambiguous_youtube_workspace')
    at=page.index(anchor);start=page.rfind('<style>',0,at)
    if start<0 or '.ytw{' not in page[start:at]:raise ValueError('workspace_style_missing')
    section_end=page.index('</section>',at)+len('</section>')
    cursor=section_end
    while cursor<len(page) and page[cursor].isspace():cursor+=1
    if page.startswith('<script id="ytw-public-snapshot"',cursor):
        cursor=page.index('</script>',cursor)+len('</script>')
        while cursor<len(page) and page[cursor].isspace():cursor+=1
    found=False
    marker="const root=document.getElementById('youtube-brands')"
    while page.startswith('<script>',cursor):
        script_end=page.index('</script>',cursor)+len('</script>')
        if marker not in page[cursor:script_end]:break
        found=True;cursor=script_end
        while cursor<len(page) and page[cursor].isspace():cursor+=1
    if not found:raise ValueError('workspace_script_missing')
    return page[:start]+youtube_workspace_panel()+page[cursor:]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('page',type=Path)
    args=parser.parse_args();before=args.page.read_text(encoding='utf-8');after=replace_workspace(before)
    if args.page.read_text(encoding='utf-8')!=before:raise RuntimeError('dashboard_changed_during_refresh')
    args.page.write_text(after,encoding='utf-8')
    print('Only the YouTube workspace was refreshed; other snapshots preserved.')

if __name__=='__main__':main()
