#!/usr/bin/env python3
"""Install the exact-URL macOS launcher used by the public dashboard. No daemon."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
APP_ID = 'com.onnellab.content-engine.youtube-connect'
APP_NAME = 'ONNELLAB YouTube Connect.app'
SCHEME = 'onnellab-content'
YOUTUBE_URLS = (SCHEME+'://youtube/connect', SCHEME+'://youtube/status')
LYRIA_URLS = (SCHEME+'://lyria/connect', SCHEME+'://lyria/status')
URLS = YOUTUBE_URLS + LYRIA_URLS
LSREGISTER = '/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister'


def launch_command(python, script):
    # No OAuth/client values are ever passed on this command line.
    return '/usr/bin/nohup '+shlex.quote(str(python))+' '+shlex.quote(str(script))+' open </dev/null >/dev/null 2>&1 &'


def applescript_source(python, script):
    youtube_command=launch_command(python,script).replace('\\','\\\\').replace('"','\\"')
    lyria_script=Path(script).with_name('lyria_connect.py')
    lyria_command=launch_command(python,lyria_script).replace('\\','\\\\').replace('"','\\"')
    return ('on launchYouTube()\n  do shell script "'+youtube_command+'"\nend launchYouTube\n'
            'on launchLyria()\n  do shell script "'+lyria_command+'"\nend launchLyria\n'
            'on run\n  my launchYouTube()\nend run\n'
            'on open location targetURL\n'
            '  if targetURL is "'+YOUTUBE_URLS[0]+'" or targetURL is "'+YOUTUBE_URLS[1]+'" then\n'
            '    my launchYouTube()\n'
            '  else if targetURL is "'+LYRIA_URLS[0]+'" or targetURL is "'+LYRIA_URLS[1]+'" then\n'
            '    my launchLyria()\n'
            '  end if\nend open location\n')


def install(*, applications=None, dry_run=False):
    if sys.platform!='darwin': raise RuntimeError('macos_required')
    applications=Path(applications or Path.home()/'Applications').expanduser()
    target=applications/APP_NAME
    python=Path(sys.executable).resolve()
    script=ROOT/'scripts/short_video_connect.py'
    lyria_script=ROOT/'scripts/lyria_connect.py'
    if not script.is_file() or not lyria_script.is_file() or not python.is_file(): raise RuntimeError('launcher_source_missing')
    if target.exists():
        try:
            if target.is_symlink(): raise ValueError()
            with (target/'Contents/Info.plist').open('rb') as stream: existing=plistlib.load(stream)
            if existing.get('CFBundleIdentifier')!=APP_ID: raise ValueError()
        except (OSError, ValueError, plistlib.InvalidFileException):
            raise RuntimeError('unrelated_application_not_overwritten') from None
    result={'application':str(target),'scheme':SCHEME,'allowed_urls':list(URLS),
            'persistent_daemon':False,'installed':False}
    if dry_run: return result
    applications.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.onnellab-youtube-install-',dir=applications) as temp:
        build=Path(temp)/APP_NAME
        command=['/usr/bin/osacompile','-o',str(build),'-']
        compiled=subprocess.run(command,input=applescript_source(python,script).encode(),
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45)
        if compiled.returncode: raise RuntimeError('launcher_compile_failed')
        info=build/'Contents/Info.plist'
        with info.open('rb') as stream: config=plistlib.load(stream)
        config.update(CFBundleIdentifier=APP_ID, CFBundleName='ONNELLAB Provider Connect',
            CFBundleDisplayName='ONNELLAB Provider Connect',CFBundleShortVersionString='1.2',
            CFBundleVersion='3',LSUIElement=True,
            CFBundleURLTypes=[{'CFBundleURLName':APP_ID,'CFBundleURLSchemes':[SCHEME]}])
        with info.open('wb') as stream: plistlib.dump(config,stream)
        signed=subprocess.run(['/usr/bin/codesign','--force','--sign','-',str(build)],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        if signed.returncode: raise RuntimeError('launcher_sign_failed')
        backup=Path(temp)/'previous.app'
        if target.exists(): target.rename(backup)
        try:
            build.rename(target)
            registered=subprocess.run([LSREGISTER,'-f',str(target)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            if registered.returncode: raise RuntimeError('launcher_register_failed')
        except Exception:
            if target.exists(): shutil.rmtree(target)
            if backup.exists(): backup.rename(target)
            raise
    result['installed']=True
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    try:
        print(json.dumps(install(dry_run=args.dry_run),ensure_ascii=False,indent=2)); return 0
    except (RuntimeError,OSError,subprocess.SubprocessError) as exc:
        reason=str(exc) if isinstance(exc,RuntimeError) else 'launcher_install_failed'
        print(json.dumps({'status':'blocked','error':reason}),file=sys.stderr); return 2

if __name__=='__main__': raise SystemExit(main())
