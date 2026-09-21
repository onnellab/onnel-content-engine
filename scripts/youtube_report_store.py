"""Private, expiring report snapshots for the verified brand reporting worker."""
from datetime import datetime, timezone
import os
from pathlib import Path
import fcntl
from short_video_pipeline import VideoError, atomic_json, load_json
from short_video_youtube import YouTube
from youtube_profiles import profile_id
from youtube_reporting import collect

ROOT=Path.home()/'Library/Application Support/ONNELLAB/content-engine/youtube-reports'

def directory(root):
    root=Path(root).expanduser()
    for part in (root,*root.parents):
        if part.is_symlink():raise VideoError('unsafe_report_directory')
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if root.stat().st_uid!=os.getuid():raise VideoError('unsafe_report_owner')
    os.chmod(root,0o700)
    return root

def clear(profile,root=ROOT):
    path=Path(root)/(profile_id(profile)+'.json')
    if path.is_symlink():raise VideoError('unsafe_report_file')
    path.unlink(missing_ok=True)

def read(profile,root=ROOT,now=None):
    profile=profile_id(profile);path=Path(root)/(profile+'.json')
    if not path.exists():return None
    if path.is_symlink() or path.stat().st_uid!=os.getuid() or path.stat().st_mode & 0o077:raise VideoError('unsafe_report_file')
    data=load_json(path,limit=1024*1024)
    now=now or datetime.now(timezone.utc)
    if set(data.get('profiles',{}))!={profile}:raise VideoError('report_profile_mismatch')
    try:expired=datetime.fromisoformat(data['expires_at'])<=now
    except (ValueError,TypeError,KeyError):expired=True
    if expired:clear(profile,root);return None
    return data

def sync(profile,root=ROOT,*,api_factory=YouTube,now=None):
    profile=profile_id(profile);root=directory(root)
    fd=os.open(root/(profile+'.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        os.fchmod(fd,0o600)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise VideoError('report_sync_in_progress') from None
        try:
            api=api_factory(profile=profile)
            api.verify()
            report=collect(api,profile,api.channel,now=now)
            atomic_json(root/(profile+'.json'),report)
            return report
        except Exception:
            clear(profile,root)
            raise
    finally:os.close(fd)
