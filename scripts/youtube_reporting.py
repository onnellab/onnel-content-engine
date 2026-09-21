"""Read-only report queries through an injected, already-verified YouTube client.

No credential storage, OAuth exchange, upload, or publication operations live here.
"""
from datetime import datetime, timedelta, timezone
import math
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from short_video_pipeline import VideoError
from short_video_youtube import UploadError
from youtube_profiles import profile_id

METRICS = ('views','estimatedMinutesWatched','subscribersGained','subscribersLost')
VIDEO_METRICS = ('views','averageViewDuration','averageViewPercentage')


def numeric(value):
    if value is None: return None
    if isinstance(value,str) and value.isdigit(): value=int(value)
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise VideoError('youtube_report_number_invalid')
    return value


def report_rows(data, columns):
    headers=data.get('columnHeaders',[])
    if [h.get('name') for h in headers] != list(columns):
        raise VideoError('youtube_report_columns_changed')
    rows=data.get('rows',[])
    if not isinstance(rows,list) or len(rows)>200 or any(not isinstance(r,list) or len(r)!=len(columns) for r in rows):
        raise VideoError('youtube_report_rows_invalid')
    return [dict(zip(columns,r)) for r in rows]


def collect(api, profile, expected_channel, *, now=None):
    """Caller must verify its profile-bound API client before calling this function."""
    profile=profile_id(profile)
    if not api.token or api.channel!=expected_channel or getattr(api,'profile',None)!=profile:
        raise VideoError('verified_report_profile_required')
    now=now or datetime.now(timezone.utc)
    budget=8
    def get(endpoint, params):
        nonlocal budget
        if endpoint not in ('channels','videos','commentThreads','analytics') or budget<=0:
            raise VideoError('report_query_not_allowed')
        budget-=1
        base='https://youtubeanalytics.googleapis.com/v2/reports' if endpoint=='analytics' else 'https://www.googleapis.com/youtube/v3/'+endpoint
        return api.request('GET',base+'?'+urlencode(params),headers=api.headers(),retry=True)[2]
    channel_data=get('channels',{'part':'id,snippet,statistics','mine':'true'})
    items=channel_data.get('items',[])
    if len(items)!=1 or items[0].get('id')!=expected_channel or channel_data.get('nextPageToken'):
        raise VideoError('report_channel_mismatch')
    channel=items[0];stats=channel.get('statistics',{})
    end=now.astimezone(ZoneInfo('America/Los_Angeles')).date()-timedelta(days=1)
    start=end-timedelta(days=27)
    result={'profile':profile,'state':'available','channel':{'id':expected_channel,'title':str(channel.get('snippet',{}).get('title',''))[:256]},
        'statistics':{key:numeric(stats.get(key)) for key in ('subscriberCount','viewCount','videoCount')},
        'summary':None,'videos':[],'comments':[],'warnings':[],
        'period':{'requested_start':str(start),'requested_end':str(end),'last_reported_day':None,'timezone':'America/Los_Angeles'}}
    result['statistics']['hiddenSubscriberCount']=stats.get('hiddenSubscriberCount') is True
    if result['statistics']['hiddenSubscriberCount']:result['statistics']['subscriberCount']=None
    result['statistics']['subscriberCountPrecision']='rounded_down_to_three_significant_figures'
    params={'ids':'channel=='+expected_channel,'startDate':str(start),'endDate':str(end)}
    try:
        daily=report_rows(get('analytics',{**params,'dimensions':'day','metrics':','.join(METRICS)}),('day',*METRICS))
        for row in daily:
            if not isinstance(row['day'],str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',row['day']) or not str(start)<=row['day']<=str(end):raise VideoError('report_day_invalid')
            for metric in METRICS:row[metric]=numeric(row[metric])
        if daily and all(row[m] is not None for row in daily for m in METRICS):
            result['summary']={m:sum(row[m] for row in daily) for m in METRICS}
            result['period']['last_reported_day']=max(row['day'] for row in daily)
        else:result['warnings'].append('analytics_no_complete_rows')
        videos=report_rows(get('analytics',{**params,'dimensions':'video','metrics':','.join(VIDEO_METRICS),'sort':'-views','maxResults':100}),('video',*VIDEO_METRICS))
        ids=[v['video'] for v in videos]
        if any(not isinstance(v,str) or not re.fullmatch(r'[-_A-Za-z0-9]{11}',v) for v in ids):raise VideoError('report_video_id_invalid')
        titles={}
        for pos in range(0,len(ids),50):
            data=get('videos',{'part':'snippet','id':','.join(ids[pos:pos+50])})
            for item in data.get('items',[]):
                if item.get('id') not in ids or item.get('snippet',{}).get('channelId')!=expected_channel:raise VideoError('report_foreign_video')
                titles[item['id']]=str(item['snippet'].get('title',''))[:200]
        result['videos']=[{'video':v['video'],'title':titles[v['video']],**{m:numeric(v[m]) for m in VIDEO_METRICS}} for v in videos if v['video'] in titles]
        if len(videos)==100:result['warnings'].append('videos_limited_to_top_100')
    except UploadError as error:
        if str(error)=='auth_required':raise
        result['warnings'].append('analytics_unavailable_check_scope_and_api')
    try:
        data=get('commentThreads',{'part':'snippet','allThreadsRelatedToChannelId':expected_channel,'maxResults':100,'order':'time','textFormat':'plainText'})
        for item in data.get('items',[]):
            snippet=item.get('snippet',{});top=snippet.get('topLevelComment',{}).get('snippet',{})
            if snippet.get('channelId')!=expected_channel:raise VideoError('report_foreign_comment')
            text=top.get('textOriginal',top.get('textDisplay',''))
            if not isinstance(text,str):raise VideoError('report_comment_invalid')
            result['comments'].append({'text':text[:5000],'likes':numeric(top.get('likeCount')),'reply_count':numeric(snippet.get('totalReplyCount'))})
        result['comments_status']='available'
        if data.get('nextPageToken'):result['warnings'].append('comments_limited_to_latest_100')
    except UploadError as error:
        if str(error)=='auth_required':raise
        result['comments_status']='unavailable';result['warnings'].append('comments_unavailable_or_disabled')
    if result['warnings']:result['state']='partial'
    return {'schema_version':1,'kind':'onnellab_youtube_private_report','generated_at':now.isoformat(),
        'expires_at':(now+timedelta(days=1)).isoformat(),'profiles':{profile:result}}
