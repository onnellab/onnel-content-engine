#!/usr/bin/env python3
"""Read-only full-decode QA for the exact ClipNest guide and source assets."""
import hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np
from PIL import Image
import screenshot_guide as guide
root=Path(__file__).resolve().parents[1]
out=Path(sys.argv[1]) if len(sys.argv)>1 else root/'output/clipnest-search-20261014'
m=guide.load(root/'data/screenshot_guides/clipnest-search-20261014.json')
source_evidence=guide.validate(m,root/'assets')
video=out/(m['guide_id']+'.mp4')
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(video)]))
s=probe['streams'];assert len(s)==1 and s[0]['codec_type']=='video'
assert (s[0]['width'],s[0]['height'],s[0]['r_frame_rate'],s[0]['nb_read_frames'])==(1080,1920,'30/1','450')
assert float(probe['format']['duration'])==15.0
refs=[np.asarray(Image.open(out/f'slide-{i}.png').convert('RGB')).astype(np.int16) for i in range(1,4)]
# Exact full-image 1/2 fit; no crop. Compare every pasted source pixel before encoding.
for i,slide in enumerate(m['slides']):
    source=Image.open(root/'assets'/slide['asset']).convert('RGB')
    assert source.size==(1206,2622)
    fit=np.asarray(source.resize((603,1311),Image.Resampling.LANCZOS))
    assert np.array_equal(refs[i][330:1641,238:841],fit)
proc=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-threads','2','-i',str(video),'-f','rawvideo','-pix_fmt','rgb24','-threads','2','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
frame_bytes=1080*1920*3
records=[];images=[];boundaries={0,149,150,299,300,449}
try:
    while True:
        data=proc.stdout.read(frame_bytes)
        if not data:break
        assert len(data)==frame_bytes,'partial_frame'
        index=len(records);assert index<450,'extra_frame'
        arr=np.frombuffer(data,dtype=np.uint8).reshape((1920,1080,3))
        expected=index//150
        # Full-resolution comparison of every RGB sample, plus independent nearest-slide classification.
        difference=np.abs(arr.astype(np.int16)-refs[expected])
        mae=float(difference.mean());fraction=float((difference>24).mean())
        scores=[float(np.abs(arr[::4,::4].astype(np.int16)-ref[::4,::4]).mean()) for ref in refs]
        assert int(np.argmin(scores))==expected,(index,scores)
        assert mae<2.0 and fraction<0.01,(index,mae,fraction)
        records.append({'frame':index,'slide':expected+1,'mean_absolute_rgb_error':mae,'fraction_channels_error_gt_24':fraction,'closest_slide':int(np.argmin(scores))+1,'decoded_rgb_sha256':hashlib.sha256(data).hexdigest()})
        if index in boundaries:
            path=out/f'decoded-{index:03}.png';Image.fromarray(arr).save(path);images.append(path.name)
    stderr=proc.stderr.read().decode();assert proc.wait(timeout=30)==0,stderr
finally:
    if proc.poll() is None:
        proc.terminate();proc.wait(timeout=10)
assert len(records)==450
bounds=json.loads((out/'render-evidence.json').read_text())['text_bounds']
assert len(bounds)==18
for b in bounds:
    x0,y0,x1,y1=b['bbox'];assert 60<=x0<x1<=1020 and 64<=y0<y1<=1880
for i in range(1,4):
    assert sum(b['slide']==i and b['text']==m['metadata']['format_disclosure'] for b in bounds)==1
report={'status':'pass','video_sha256':guide.sha256(video),'source_evidence':source_evidence,'decoded_frames':450,'fps':30,'duration_seconds':15,'audio_streams':0,'segment_frames':[[0,149],[150,299],[300,449]],'all_frames_closest_to_expected_slide':True,'full_resolution_rgb_comparison':True,'maximum_frame_mean_absolute_rgb_error':max(r['mean_absolute_rgb_error'] for r in records),'maximum_fraction_channels_error_gt_24':max(r['fraction_channels_error_gt_24'] for r in records),'source_full_image_fit':{'original':[1206,2622],'display':[603,1311],'uniform_scale':0.5,'origin':[238,330],'source_pixels_match_preencode':True},'persistent_disclosure_verified':True,'text_bounds':bounds,'boundary_images':images,'decoder_exit_code':proc.returncode,'frames':records}
(out/'all-frames-qa.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'ffprobe.json').write_text(json.dumps(probe,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('frames','text_bounds')},indent=2))
