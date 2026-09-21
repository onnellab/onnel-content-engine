"""Offline report query tests. No credentials, Keychain, sockets or network."""
import unittest
from unittest.mock import Mock
from datetime import datetime, timezone
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from youtube_reporting import collect, numeric, report_rows, METRICS, VIDEO_METRICS
from short_video_pipeline import VideoError
from short_video_youtube import UploadError

CHANNEL='UC'+'x'*22
VIDEO='abcdefghijk'
NOW=datetime(2026,9,21,12,tzinfo=timezone.utc)
def table(columns, values):
    return {'columnHeaders':[{'name':name} for name in columns],'rows':values}
def client():
    api=Mock(profile='aether_inn',channel=CHANNEL,token=True)
    api.headers.return_value={}
    data=[{'items':[{'id':CHANNEL,'snippet':{'title':'Example'},'statistics':{'subscriberCount':'12'}}]},
          table(('day',*METRICS),[['2026-09-20',10,20,2,1]]),
          table(('video',*VIDEO_METRICS),[[VIDEO,10,120,80]]),
          {'items':[{'id':VIDEO,'snippet':{'channelId':CHANNEL,'title':'Example track'}}]},
          {'items':[{'snippet':{'channelId':CHANNEL,'totalReplyCount':1,'topLevelComment':{'snippet':{'textOriginal':'Warm melody','likeCount':2}}}}]}]
    api.request.side_effect=[(200,{},item) for item in data]
    return api

class Queries(unittest.TestCase):
    def test_reads_owned_channel_report_without_writes(self):
        api=client();result=collect(api,'aether_inn',CHANNEL,now=NOW)['profiles']['aether_inn']
        self.assertEqual(12,result['statistics']['subscriberCount'])
        self.assertEqual(20,result['summary']['estimatedMinutesWatched'])
        self.assertEqual(120,result['videos'][0]['averageViewDuration'])
        self.assertEqual('Warm melody',result['comments'][0]['text'])
        self.assertEqual('2026-09-20',result['period']['last_reported_day'])
        self.assertTrue(all(call.args[0]=='GET' for call in api.request.call_args_list))
    def test_wrong_brand_or_expected_channel_never_queries(self):
        api=client()
        for profile,channel in [('onnellab',CHANNEL),('aether_inn','UC'+'z'*22)]:
            with self.assertRaises(VideoError):collect(api,profile,channel,now=NOW)
        api.request.assert_not_called()
    def test_analytics_denied_is_partial_not_zero(self):
        api=client();api.request.side_effect=[(200,{}, {'items':[{'id':CHANNEL,'statistics':{}}]}),
            UploadError('permission_or_quota_denied'),(200,{}, {'items':[]})]
        result=collect(api,'aether_inn',CHANNEL,now=NOW)['profiles']['aether_inn']
        self.assertEqual('partial',result['state']);self.assertIsNone(result['summary'])
        self.assertEqual('available',result['comments_status'])
    def test_bad_metrics_and_changed_columns_fail(self):
        for value in [True,-1,float('nan'),'missing']:
            with self.assertRaises(VideoError):numeric(value)
        with self.assertRaises(VideoError):report_rows(table(('wrong',),[]),('views',))
    def test_authentication_failure_does_not_return_report(self):
        api=client();api.request.side_effect=UploadError('auth_required')
        with self.assertRaises(UploadError):collect(api,'aether_inn',CHANNEL,now=NOW)
    def test_foreign_channel_cannot_supply_statistics(self):
        api=client();api.request.side_effect=[(200,{}, {'items':[{'id':'UC'+'z'*22}]})]
        with self.assertRaises(VideoError):collect(api,'aether_inn',CHANNEL,now=NOW)

class SnapshotIsolation(unittest.TestCase):
    def test_private_cache_expiry_and_profile_binding(self):
        import tempfile
        from datetime import timedelta
        from short_video_pipeline import atomic_json
        from youtube_report_store import read, clear
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            report=collect(client(),'aether_inn',CHANNEL,now=NOW)
            atomic_json(root/'aether_inn.json',report)
            self.assertEqual(0,(root/'aether_inn.json').stat().st_mode & 0o077)
            self.assertIsNotNone(read('aether_inn',root,now=NOW))
            atomic_json(root/'onnellab.json',report)
            with self.assertRaises(VideoError):read('onnellab',root,now=NOW)
            self.assertIsNone(read('aether_inn',root,now=NOW+timedelta(days=2)))
            self.assertFalse((root/'aether_inn.json').exists())
            self.assertTrue((root/'onnellab.json').exists());clear('onnellab',root)
    def test_workspace_refresh_preserves_other_data(self):
        import re
        from refresh_youtube_workspace import replace_workspace
        page=(Path(__file__).resolve().parents[1]/'generated/manual-publish/index.html').read_text()
        after=replace_workspace(page)
        pattern=r'<script[^>]*id="[^"]+-data"[^>]*>.*?</script>'
        self.assertEqual(re.findall(pattern,page,re.S),re.findall(pattern,after,re.S))

if __name__=='__main__':unittest.main()
