"""Aether media boundary tests. No network, credentials or real publication."""
import copy
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
