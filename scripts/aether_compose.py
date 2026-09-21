"""Compose approved existing masters; never generate or approve new music here."""
from __future__ import annotations
import json
import math
from pathlib import Path
import re
import shutil
from aether_planner import read_catalog, plan, timeline
from short_video_pipeline import VideoError, file_hash, digest, run_process, atomic_json, MAX_ASSET
from youtube_report_store import directory


def checked_asset(root, spec, suffixes):
    if not isinstance(spec,dict) or spec.get('commercial_use_confirmed') is not True:
        raise VideoError('aether_asset_rights_unconfirmed')
    relative=spec.get('path')
    if not isinstance(relative,str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise VideoError('aether_relative_asset_required')
    if Path(root).is_symlink():raise VideoError("aether_symlink_asset_root_rejected")
    root=Path(root).resolve();path=root
    for part in Path(relative).parts:
        path=path/part
        if path.is_symlink():raise VideoError('aether_symlink_asset_rejected')
    if not path.is_file() or path.suffix.lower() not in suffixes or not 0<path.stat().st_size<=1024**3:
        raise VideoError('aether_asset_missing_or_invalid')
    expected=spec.get('sha256')
    if not isinstance(expected,str) or not re.fullmatch(r'[0-9a-f]{64}',expected) or file_hash(path)!=expected:
        raise VideoError('aether_asset_hash_mismatch')
    return path


def media_info(path):
    data=run_process(['ffprobe','-v','error','-protocol_whitelist','file,pipe',
        '-format_whitelist','wav,mp3,flac,mov,image2,png_pipe,jpeg_pipe',
        '-show_entries','format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,pix_fmt',
        '-of','json',str(path)],timeout=60)
    try:return json.loads(data)
    except (ValueError,TypeError):raise VideoError('aether_probe_invalid') from None


def audio_duration(path):
    data=media_info(path)
    try:value=float(data.get('format',{}).get('duration',0))
    except (TypeError,ValueError):raise VideoError('aether_duration_invalid') from None
    if not math.isfinite(value) or not 10<=value<=900 or not any(s.get('codec_type')=='audio' for s in data.get('streams',[])):
        raise VideoError('aether_audio_invalid')
    return value


def prepare(manifest,assets,theme,history=()):
    if manifest.get('schema_version')!=1 or manifest.get('profile')!='aether_inn' or type(manifest.get('test_only')) is not bool:
        raise VideoError('aether_manifest_invalid')
    specs=manifest.get('tracks',{})
    if not isinstance(specs,dict) or not specs:raise VideoError('aether_master_audio_required')
    catalog={r['id']:r for r in read_catalog()};available=[]
    for key,spec in specs.items():
        if key not in catalog or not isinstance(spec,dict):raise VideoError('aether_unregistered_track')
        if spec.get('quality_accepted') is not True:continue
        path=checked_asset(assets,spec,{'.wav','.mp3','.flac','.m4a'})
        available.append({**catalog[key],'duration_seconds':audio_duration(path)})
    selection=plan(available,theme,history=history)
    cover=manifest.get('covers',{}).get(theme)
    checked_asset(assets,cover,{'.png','.jpg','.jpeg'})
    return {**selection,'audio_measured':True,'test_only':manifest['test_only'],
        'source_assets':{key:specs[key] for key in selection['track_ids']},'cover_asset':cover}


def validate_output(path,expected_seconds):
    data=media_info(path)
    video=next((s for s in data.get('streams',[]) if s.get('codec_type')=='video'),{})
    audio=next((s for s in data.get('streams',[]) if s.get('codec_type')=='audio'),{})
    actual=float(data.get('format',{}).get('duration',0))
    if (video.get('width'),video.get('height'),video.get('codec_name'),video.get('pix_fmt'),video.get('avg_frame_rate'))!=(1920,1080,'h264','yuv420p','30/1') or audio.get('codec_name')!='aac':
        raise VideoError('aether_output_format_invalid')
    if not math.isfinite(actual) or abs(actual-expected_seconds)>1 or not 0<path.stat().st_size<=MAX_ASSET:
        raise VideoError('aether_output_duration_or_size_invalid')
    return actual


def render(selection,assets,output):
    if selection.get('profile')!='aether_inn' or selection.get('content_type')!='aether_compilation' or selection.get('audio_measured') is not True:
        raise VideoError('aether_measured_compilation_required')
    if type(selection.get('test_only')) is not bool:raise VideoError('aether_test_flag_required')
    ids=selection['track_ids']
    if not 3<=len(ids)<=20 or len(set(ids))!=len(ids):raise VideoError('aether_unique_tracks_required')
    output=directory(output)
    if shutil.disk_usage(output).free<2*1024**3:raise VideoError('aether_insufficient_free_disk')
    cover=checked_asset(assets,selection['cover_asset'],{'.png','.jpg','.jpeg'})
    image=next((s for s in media_info(cover).get('streams',[]) if s.get('codec_type')=='video'),{})
    w,h=image.get('width',0),image.get('height',0)
    if w<1280 or h<720 or abs(w/max(1,h)-16/9)>.01:raise VideoError('aether_landscape_cover_required')
    sources=[];rows=[];fingerprints=set();by_id={r['id']:r for r in selection['tracks']}
    for key in ids:
        spec=selection['source_assets'][key]
        if spec.get('quality_accepted') is not True:raise VideoError('aether_uncurated_master')
        path=checked_asset(assets,spec,{'.wav','.mp3','.flac','.m4a'})
        duration=audio_duration(path)
        pcm=run_process(['ffmpeg','-v','error','-nostdin','-threads','1','-protocol_whitelist','file,pipe','-format_whitelist','wav,mp3,flac,mov','-i',str(path),
            '-map','0:a:0','-ac','1','-ar','16000','-c:a','pcm_s16le','-f','hash','-hash','sha256','-'],timeout=120).decode().strip()
        if not re.fullmatch(r'SHA256=[0-9a-f]{64}',pcm):raise VideoError('aether_pcm_fingerprint_failed')
        if pcm in fingerprints:raise VideoError('aether_duplicate_decoded_master')
        fingerprints.add(pcm);sources.append(path);rows.append({**by_id[key],'duration_seconds':duration})
    chapters,duration=timeline(rows,selection['crossfade_seconds'])
    if not selection['test_only'] and not 1740<=duration<=1860:raise VideoError('aether_compilation_outside_30_minute_target')
    if abs(duration-selection['estimated_duration_seconds'])>1:raise VideoError('aether_source_duration_changed')
    filters=[f'[{i+1}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]' for i in range(len(sources))]
    last='a0';fade=selection['crossfade_seconds']
    for i in range(1,len(sources)):
        label=f'm{i}'
        operation=f'acrossfade=d={fade}:c1=tri:c2=tri' if fade else 'concat=n=2:v=0:a=1'
        filters.append(f'[{last}][a{i}]{operation}[{label}]');last=label
    filters.append(f'[{last}]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[out]')
    partial=output/'render.partial.mp4'
    if partial.is_symlink():raise VideoError('aether_unsafe_render_path')
    command=['ffmpeg','-v','error','-nostdin','-y','-filter_complex_threads','1','-loop','1','-framerate','30','-protocol_whitelist','file,pipe','-i',str(cover)]
    for source in sources:command+=['-protocol_whitelist','file,pipe','-format_whitelist','wav,mp3,flac,mov','-i',str(source)]
    command+=['-filter_complex',';'.join(filters),'-map','0:v:0','-map','[out]','-vf','scale=1920:1080,setsar=1',
        '-c:v','libx264','-threads','2','-preset','veryfast','-tune','stillimage','-pix_fmt','yuv420p','-r','30',
        '-c:a','aac','-b:a','256k','-shortest','-movflags','+faststart',str(partial)]
    try:
        run_process(command,timeout=5400)
        actual=validate_output(partial,duration)
        for key in ids:checked_asset(assets,selection['source_assets'][key],{'.wav','.mp3','.flac','.m4a'})
        checked_asset(assets,selection['cover_asset'],{'.png','.jpg','.jpeg'})
        run_process(['ffmpeg','-v','error','-nostdin','-y','-protocol_whitelist','file,pipe','-i',str(cover),
            '-vf','scale=1280:720','-frames:v','1','-q:v','3',str(output/'thumbnail.jpg')],timeout=60)
        if not 0<(output/'thumbnail.jpg').stat().st_size<=2*1024*1024:raise VideoError('aether_thumbnail_size_invalid')
        partial.replace(output/'video.mp4')
        result={'test_only':selection['test_only'],'upload_eligible':not selection['test_only'],
            'duration_seconds':actual,'chapters':chapters,'selection_hash':digest(selection),
            'sha256':{name:file_hash(output/name) for name in ('video.mp4','thumbnail.jpg')}}
        atomic_json(output/'render.json',result)
        return result
    finally:partial.unlink(missing_ok=True)
