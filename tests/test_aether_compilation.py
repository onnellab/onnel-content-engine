"""Aether media boundary tests. No network, credentials or real publication."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from short_video_pipeline import VideoError,file_hash
from short_video_youtube import metadata,UploadError
from aether_compose import checked_asset,render
from aether_compilation import worker,brief_for
from aether_compilation_assets import activate_mybox,approval_template,hash_private_source,source_title,sync as sync_assets
from aether_planner import plan,read_catalog
from datetime import datetime,timezone

class Compilation(unittest.TestCase):
    def test_rights_hash_paths_and_root_isolation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();audio=root/'track.wav';audio.write_bytes(b'unit fixture')
            spec={'path':'track.wav','sha256':file_hash(audio),'commercial_use_confirmed':True,'quality_accepted':True}
            self.assertEqual(audio,checked_asset(root,spec,{'.wav'}))
            for changes in [{'commercial_use_confirmed':False},{'path':'../track.wav'},{'path':str(audio)},{'sha256':'0'*64}]:
                with self.assertRaises(VideoError):checked_asset(root,{**spec,**changes},{'.wav'})
            (root/'link.wav').symlink_to(audio)
            with self.assertRaises(VideoError):checked_asset(root,{**spec,'path':'link.wav'},{'.wav'})
    def test_music_uses_music_category_and_explicit_disclosure(self):
        selection=plan(read_catalog());selection['test_only']=False
        brief=brief_for(selection)
        body=metadata({'brief':brief},{'made_for_kids':False,'synthetic_media':True,'privacy':'public','publish_approved':True},datetime.now(timezone.utc))
        self.assertEqual('10',body['snippet']['categoryId']);self.assertTrue(body['status']['containsSyntheticMedia'])
        self.assertLessEqual(len(body['snippet']['title']),100)
        self.assertIn('00:00',body['snippet']['description'])
    def test_wrong_publication_profile_stops_before_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            api=Mock(profile='onnellab')
            with self.assertRaisesRegex(UploadError,'aether_profile_required'):
                worker(Path(temporary).resolve(),execute=True,publish=True,api_factory=lambda:api)
            api.verify.assert_not_called()
    def test_reconcile_cannot_create_a_new_job_or_touch_provider_when_idle(self):
        with tempfile.TemporaryDirectory() as temporary:
            factory=Mock(side_effect=AssertionError('must_not_connect'))
            result=worker(Path(temporary).resolve(),execute=True,publish=True,existing_only=True,api_factory=factory)
            self.assertEqual('idle',result['status']);self.assertFalse(result['created_new_job'])
            factory.assert_not_called()
    def test_missing_master_manifest_does_not_make_a_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            with self.assertRaisesRegex(VideoError,'manifest_missing'):worker(root,execute=True)
            self.assertFalse((root/'queue.json').exists())
    def test_unmeasured_metadata_is_not_renderable(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(VideoError,'measured_compilation_required'):
                render(plan(read_catalog()),Path(temporary),Path(temporary))

    def test_asset_sync_requires_explicit_owner_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            with self.assertRaisesRegex(VideoError,'aether_asset_approval_missing'):
                sync_assets(root/'assets',source_root=root/'source',execute=True)

    def test_cloud_materialization_failure_is_explicit(self):
        with patch('aether_compilation_assets.file_hash', side_effect=OSError('provider cancelled')):
            with self.assertRaisesRegex(VideoError,'aether_asset_source_materialization_failed'):
                hash_private_source(Path('/tmp/cloud-placeholder.wav'))

    def test_mybox_activation_is_bounded_and_checked(self):
        completed=Mock(returncode=0)
        with patch('aether_compilation_assets.subprocess.run',return_value=completed) as run, \
             patch('aether_compilation_assets.time.sleep') as sleep:
            activate_mybox()
        self.assertEqual(['/usr/bin/open','-gja','MYBOX'],run.call_args.args[0])
        sleep.assert_called_once_with(3)

    def test_catalog_style_suffix_is_not_part_of_source_filename(self):
        self.assertEqual('The Last Light Over Seren Fields', source_title({'title':'The Last Light Over Seren Fields Style:'}))
        self.assertTrue(any(row['title']=='The Last Light Over Seren Fields' for row in read_catalog()))

    def test_theme_sync_materializes_only_preselected_tracks_and_cover(self):
        from short_video_pipeline import atomic_json
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source=root/'source';assets=root/'assets'
            (source/'01_Audio_Master').mkdir(parents=True)
            (source/'02_Cover_Original').mkdir()
            catalog=read_catalog();chosen=catalog[:3];unused=catalog[3]
            approval=approval_template()
            for row in chosen+[unused]:
                approval['tracks'][row['id']].update(commercial_use_confirmed=True,quality_accepted=True)
                (source/'01_Audio_Master'/f"{source_title(row)}.wav").write_bytes(row['title'].encode())
            cover=approval['covers']['open_roads']
            cover['commercial_use_confirmed']=True
            (source/'02_Cover_Original'/cover['filename']).write_bytes(b'cover')
            assets.mkdir();atomic_json(assets/'approval.json',approval)
            planned={'track_ids':[row['id'] for row in chosen],'tracks':chosen}
            def fake_cover(_source,output,_title):
                output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(b'compiled-cover')
                return {'sha256':file_hash(output)}
            with patch('aether_compilation_assets.plan',return_value=planned), \
                 patch('aether_compilation_assets.tokens',return_value={'road'}), \
                 patch('aether_compilation_assets.audio_duration',return_value=600), \
                 patch('aether_compilation_assets.build_compilation_cover',side_effect=fake_cover):
                result=sync_assets(assets,source_root=source,execute=True,theme='open_roads')
            manifest=json.loads((assets/'manifest.json').read_text())
            self.assertEqual({row['id'] for row in chosen},set(manifest['tracks']))
            self.assertNotIn(unused['id'],manifest['tracks'])
            self.assertEqual({'open_roads'},set(manifest['covers']))
            self.assertEqual('local_private_cache',manifest['asset_source'])
            self.assertTrue(all(spec['path'].startswith('staged/open_roads/masters/') for spec in manifest['tracks'].values()))
            self.assertEqual(3,result['approved_track_count'])

    def test_asset_sync_never_infers_unapproved_tracks(self):
        from short_video_pipeline import atomic_json
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();source=root/'source';assets=root/'assets'
            (source/'01_Audio_Master').mkdir(parents=True)
            (source/'02_Cover_Original').mkdir()
            catalog=read_catalog();approved=catalog[0];unapproved=catalog[1]
            for row in (approved,unapproved):
                (source/'01_Audio_Master'/f"{row['title']}.wav").write_bytes(b'fixture')
            approval=approval_template()
            approval['tracks'][approved['id']].update(commercial_use_confirmed=True,quality_accepted=True)
            for theme,spec in approval['covers'].items():
                spec['commercial_use_confirmed']=True
                (source/'02_Cover_Original'/spec['filename']).write_bytes(b'cover')
            assets.mkdir()
            atomic_json(assets/'approval.json',approval)
            def fake_cover(_source,output,_title):
                output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(b'compiled-cover')
                return {'sha256':file_hash(output)}
            with patch('aether_compilation_assets.build_compilation_cover',side_effect=fake_cover):
                result=sync_assets(assets,source_root=source,execute=True)
            manifest=json.loads((assets/'manifest.json').read_text())
            self.assertEqual('ready',result['status'])
            self.assertEqual({approved['id']},set(manifest['tracks']))
            self.assertNotIn(unapproved['id'],manifest['tracks'])

class DurablePublication(unittest.TestCase):
    def test_repeated_slot_reuses_video_and_does_not_insert_again(self):
        from short_video_pipeline import digest,atomic_json
        import aether_compilation as module
        selection=plan(read_catalog());selection.update(test_only=False,audio_measured=True)
        class Provider:
            profile='aether_inn';channel='UC'+'x'*22;token=True
            def __init__(self):self.inserts=0;self.thumbnails=0
            def verify(self):return {'channel_verified':True}
            def initiate(self,body,size):
                self.inserts+=1
                if body['snippet']['categoryId']!='10':raise AssertionError('wrong_category')
                return 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&upload_id=unit-fixture'
            def probe(self,url,size):return 201,{}, {'id':'abcdefghijk'}
            def video(self,video_id):return {'id':video_id,'snippet':{'channelId':self.channel},'status':{'uploadStatus':'processed','privacyStatus':'public'},'processingDetails':{'processingStatus':'succeeded'}}
            def headers(self,**extra):return extra
            def request(self,method,url,*args,**kwargs):
                if method!='POST' or '/thumbnails/set?videoId=abcdefghijk' not in url:raise AssertionError('unexpected_call')
                self.thumbnails+=1;return 200,{}, {'items':[{}]}
        api=Provider()
        def renderer(selected,assets,output):
            output.mkdir(parents=True,exist_ok=True)
            for name in ('video.mp4','thumbnail.jpg'):(output/name).write_bytes(b'unit-fixture-not-real-media')
            return {'test_only':False,'upload_eligible':True,'duration_seconds':1800,'selection_hash':digest(selected),
                'sha256':{name:file_hash(output/name) for name in ('video.mp4','thumbnail.jpg')}}
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();(root/'assets').mkdir();atomic_json(root/'assets/manifest.json',{})
            with patch.object(module,'prepare',return_value=selection),patch.object(module,'render',side_effect=renderer),patch.object(module,'validate_output',return_value=1800):
                first=worker(root,slot='2026-09-27',execute=True,publish=True,api_factory=lambda:api)
                second=worker(root,slot='2026-09-27',execute=True,publish=True,api_factory=lambda:api)
            self.assertEqual('published',first['status']);self.assertTrue(first['publication_complete'])
            self.assertEqual(first['job_id'],second['job_id']);self.assertEqual(first['video_id'],second['video_id'])
            self.assertEqual(1,api.inserts);self.assertEqual(1,api.thumbnails)

if __name__=='__main__':unittest.main()
