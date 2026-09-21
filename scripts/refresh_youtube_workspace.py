"""Refresh only the YouTube workspace, preserving every other dashboard byte."""
import argparse
from pathlib import Path
from youtube_workspace_panel import youtube_workspace_panel

def replace_workspace(page):
    anchor='<section class="ytw" id="youtube-brands"'
    if page.count(anchor)!=1:raise ValueError('ambiguous_youtube_workspace')
    at=page.index(anchor);start=page.rfind('<style>',0,at)
    end=page.index('</script>',at)+len('</script>')
    if start<0 or '.ytw{' not in page[start:at]:raise ValueError('workspace_style_missing')
    return page[:start]+youtube_workspace_panel()+page[end:]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('page',type=Path)
    args=parser.parse_args();before=args.page.read_text(encoding='utf-8');after=replace_workspace(before)
    if args.page.read_text(encoding='utf-8')!=before:raise RuntimeError('dashboard_changed_during_refresh')
    args.page.write_text(after,encoding='utf-8')
    print('Only the YouTube workspace was refreshed; other snapshots preserved.')

if __name__=='__main__':main()
