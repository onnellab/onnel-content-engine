#!/usr/bin/env python3
"""Durable Aether-only compilation queue for already-curated existing masters."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from functools import partial
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo
from aether_compose import prepare, render, validate_output
from aether_planner import THEMES
from short_video_pipeline import VideoError, atomic_json, digest, file_hash, load_json
from short_video_youtube import YouTube, Uploader, UploadError
from short_video_credentials import credential_status
from youtube_report_store import directory

ROOT=Path.home()/'Library/Application Support/ONNELLAB/content-engine/aether-inn'
POLICY={'version':1,'profile':'aether_inn','kind':'curated_compilation','minimum_seconds':1740,
    'maximum_seconds':1860,'rights_confirmed':True,'quality_previously_accepted':True,'no_new_song_generation':True}
FINAL={'published','uploaded_private','uploaded_unlisted','forced_private','rejected'}


def brief_for(selection):
    chapters='\n'.join(row['timestamp']+' '+row['title'] for row in selection['chapters'])
    return {'locale':'en','content_kind':'aether_compilation','youtube_profile':'aether_inn',
        'test_only':selection['test_only'],'title':selection['title']+' 🌙 Fantasy RPG Music | 30 Minute Journey',
        'description':'A quiet journey through a world that still remembers magic.\n\n'
            'A curated collection of AI-generated fantasy music from Aether Inn, with nostalgic JRPG and MMORPG travel atmosphere. '
            'Warm melodies for reading, studying, relaxing and exploring imaginary worlds.\n\n'
            +chapters+'\n\nWelcome to Aether Inn — a place where travelers rest before the next adventure.\n\n'
            '#fantasymusic #jrpg #rpgmusic #mmorpg #cozyfantasy #studymusic #aimusic'}


class MusicQueue:
    def __init__(self,root):
        self.root=directory(root);self.assets=self.root/'assets';self.state_path=self.root/'queue.json'
        directory(self.root/'jobs')
        self.clock=lambda:datetime.now(timezone.utc)
    @contextmanager
    def lock(self):
        fd=os.open(self.root/'worker.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            os.fchmod(fd,0o600)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise VideoError('aether_worker_already_running') from None
            yield
        finally:os.close(fd)
    def _read(self):
        if not self.state_path.exists():return {'schema_version':1,'jobs':{}}
        if self.state_path.is_symlink() or self.state_path.stat().st_mode & 0o077:raise VideoError('aether_unsafe_queue')
        state=load_json(self.state_path,limit=16*1024*1024)
        if state.get('schema_version')!=1 or not isinstance(state.get('jobs'),dict) or len(state['jobs'])>1000:raise VideoError('aether_queue_invalid')
        for key,job in state['jobs'].items():
            if not re.fullmatch(r'[0-9a-f]{24}',key) or job.get('id')!=key or key!=digest({'slot':job['slot'],'selection':job['selection']})[:24]:
                raise VideoError('aether_job_identity_changed')
            if job['brief']!=brief_for(job['selection']) or job['payload_hash']!=digest(job['brief']):raise VideoError('aether_brief_integrity')
        return state
    def _render(self,state,job,renderer):
        result=job.get('result') or {}
        if job['brief']['test_only'] or result.get('selection_hash')!=digest(job['selection']):raise UploadError('aether_production_proof_required')
        path=self.root/'jobs'/job['id']/'video.mp4'
        if not 1740<=result.get('duration_seconds',0)<=1860:raise UploadError('aether_production_duration_required')
        if path.is_symlink():raise UploadError('aether_unsafe_render_path')
        if file_hash(path)!=result.get('sha256',{}).get('video.mp4'):raise UploadError('aether_render_integrity')
        validate_output(path,result['duration_seconds'])


def readiness(root=ROOT):
    root=Path(root)
    return {'profile':'aether_inn','worker':'curated_compilation','credentials':credential_status(profile='aether_inn'),
        'asset_manifest_present':(root/'assets/manifest.json').is_file(),
        'requires':['rights-confirmed curated master audio','theme-specific landscape cover','Aether Inn OAuth'],
        'new_suno_generation':'not_implemented','new_image_generation':'not_implemented','audio_originality_model':'not_implemented'}


def thumbnail(q,state,job,api):
    upload=job.get('upload') or {};video=upload.get('video_id')
    if not video or job.get('thumbnail_status')=='set':return
    path=q.root/'jobs'/job['id']/'thumbnail.jpg'
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=2*1024*1024 or file_hash(path)!=job['result']['sha256']['thumbnail.jpg']:
        raise UploadError('aether_thumbnail_integrity')
    api.video(video)
    job['thumbnail_status']='setting';atomic_json(q.state_path,state)
    _,_,response=api.request('POST','https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId='+video,
        path.read_bytes(),api.headers(**{'Content-Type':'image/jpeg'}))
    if not response.get('items'):raise UploadError('aether_thumbnail_unconfirmed')
    job['thumbnail_status']='set';job.pop('thumbnail_error',None);atomic_json(q.state_path,state)


def worker(root=ROOT,theme='open_roads',slot=None,*,publish=False,execute=False,api_factory=None,existing_only=False):
    if not execute:return {'dry_run':True,**readiness(root)}
    slot=slot or datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    try:datetime.strptime(slot,'%Y-%m-%d')
    except (ValueError,TypeError):raise VideoError('aether_slot_invalid') from None
    if theme not in THEMES:raise VideoError('aether_theme_invalid')
    q=MusicQueue(root)
    with q.lock():
        state=q._read();api=None
        pending=[j for j in state['jobs'].values() if j.get('upload') and (j['status'] not in FINAL or j.get('thumbnail_status')!='set' and j['status']!='rejected')]
        existing=[j for j in state['jobs'].values() if j['slot']==slot]
        unfinished=[j for j in state['jobs'].values() if not j.get('upload') and j['status'] in {'rendering','rendered','blocked'}]
        if existing_only:
            unfinished=[j for j in unfinished if j.get('publish_requested') is True]
            job=(pending or unfinished or [None])[0]
            if job is None:return {'profile':'aether_inn','status':'idle','created_new_job':False}
        else:job=(pending or existing or unfinished or [None])[0]
        if publish:
            api=(api_factory or partial(YouTube,profile='aether_inn'))()
            if getattr(api,'profile',None)!='aether_inn':raise UploadError('aether_profile_required')
            api.verify()
        if job is None:
            manifest_path=q.assets/'manifest.json'
            if not manifest_path.is_file() or manifest_path.is_symlink():raise VideoError('aether_asset_manifest_missing')
            manifest=load_json(manifest_path,limit=2*1024*1024)
            history=[{'track_ids':j['selection']['track_ids']} for j in state['jobs'].values() if j.get('upload')]
            selection=prepare(manifest,q.assets,theme,history)
            if publish and selection['test_only']:raise UploadError('aether_test_assets_cannot_publish')
            key=digest({'slot':slot,'selection':selection})[:24];brief=brief_for(selection)
            job={'id':key,'slot':slot,'selection':selection,'brief':brief,'payload_hash':digest(brief),
                'status':'rendering','result':None,'upload_eligible':False,'error':None,'publish_requested':publish}
            state['jobs'][key]=job;atomic_json(q.state_path,state)
        if publish and not job.get('publish_requested'):
            job['publish_requested']=True;atomic_json(q.state_path,state)
        try:
            if not job.get('result'):
                result=render(job['selection'],q.assets,q.root/'jobs'/job['id'])
                result['job_id']=job['id'];job.update(result=result,status='rendered',upload_eligible=result['upload_eligible'],error=None)
                atomic_json(q.state_path,state)
            if publish:
                uploader=Uploader(q,partial(YouTube,profile='aether_inn'))
                if not job.get('approval'):
                    choices={'made_for_kids':False,'synthetic_media':True,'privacy':'public','publish_approved':True}
                    uploader.bind_approval_locked(state,job,choices,mode='automatic_fail_closed',policy_hash=digest(POLICY))
                if job['approval'].get('policy_hash')!=digest(POLICY):raise UploadError('aether_policy_changed')
                q._render(state,job,None)
                uploader.run_locked(state,job,reconcile=bool(job.get('upload')),api=api)
                if job.get('upload',{}).get('video_id') and job['status'] not in {'rejected','reconcile_required','blocked'}:
                    try:thumbnail(q,state,job,api)
                    except UploadError as error:
                        job['thumbnail_status']='retry_required';job['thumbnail_error']=str(error);atomic_json(q.state_path,state)
            return {'profile':'aether_inn','status':job['status'],'job_id':job['id'],
                'video_id':job.get('upload',{}).get('video_id'),'error':job.get('error'),
                'thumbnail_status':job.get('thumbnail_status'),'thumbnail_error':job.get('thumbnail_error'),
                'publication_complete':job['status']=='published' and job.get('thumbnail_status')=='set'}
        except (VideoError,OSError) as error:
            job.update(status='reconcile_required' if job.get('upload') else 'blocked',error=str(error) if isinstance(error,VideoError) else 'aether_storage_error')
            atomic_json(q.state_path,state)
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT)
    sub=parser.add_subparsers(dest='command',required=True);sub.add_parser('readiness')
    r=sub.add_parser('reconcile');r.add_argument('--execute',action='store_true')
    p=sub.add_parser('worker');p.add_argument('--theme',choices=THEMES,default='open_roads');p.add_argument('--slot')
    p.add_argument('--execute',action='store_true');p.add_argument('--publish',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='readiness':result=readiness(args.root)
        elif args.command=='reconcile':result=worker(args.root,publish=True,execute=args.execute,existing_only=True)
        else:result=worker(args.root,args.theme,args.slot,publish=args.publish,execute=args.execute)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 2 if result.get('status') in {'blocked','reconcile_required','rejected'} else 0
    except Exception as error:
        reason=str(error) if isinstance(error,VideoError) and re.fullmatch(r'[a-z_]{1,90}',str(error)) else 'aether_operation_failed'
        print(json.dumps({'profile':'aether_inn','status':'blocked','error':reason}));return 2

if __name__=='__main__':raise SystemExit(main())
