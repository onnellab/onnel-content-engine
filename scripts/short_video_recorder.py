"""Deterministic emulator/simulator screen recording for short-video assets."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import subprocess
import tempfile
import time

from short_video_pipeline import (
    ROOT,
    VideoError,
    atomic_json,
    canonical,
    file_hash,
    probe,
)

SCENARIO_FILE = ROOT / 'data/video_recording_scenarios.json'
INDEX_SCHEMA = 1
MAX_SCENARIOS = 100
MAX_LOG_BYTES = 2 * 1024 * 1024
ANDROID_RECORD_SIZE = '720x1280'


class RecordingError(VideoError):
    pass


def _run(argv, *, cwd=None, timeout=60, env=None, check=True):
    # Use files, not PIPE: Flutter/Gradle descendants may inherit stdout and keep
    # a pipe open after the direct child exits, which can deadlock communicate().
    with tempfile.TemporaryFile() as output:
        try:
            proc = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                _stop_group(proc, interrupt=False)
                raise RecordingError('recording_command_timeout') from exc
        except OSError as exc:
            raise RecordingError('recording_command_failed') from exc
        output.seek(0)
        raw = output.read(MAX_LOG_BYTES + 1)
        text = raw[-MAX_LOG_BYTES:].decode('utf-8', errors='replace')
        if check and proc.returncode:
            raise RecordingError('recording_command_failed')
        return proc.returncode, text

def _safe_rel(value, label):
    if not isinstance(value, str) or not value or len(value) > 240:
        raise RecordingError(f'invalid_{label}')
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or any(part in ('', '.') for part in path.parts):
        raise RecordingError(f'invalid_{label}')
    return path


def load_scenarios(path=SCENARIO_FILE):
    try:
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise RecordingError('recording_scenarios_invalid') from exc
    if set(payload) != {'schema_version', 'scenarios'} or payload['schema_version'] != 1:
        raise RecordingError('recording_scenarios_invalid')
    rows = payload['scenarios']
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_SCENARIOS:
        raise RecordingError('recording_scenarios_invalid')
    scenarios = {}
    for row in rows:
        scenario = validate_scenario(row)
        sid = scenario['scenario_id']
        if sid in scenarios:
            raise RecordingError('duplicate_recording_scenario')
        scenarios[sid] = scenario
    return scenarios


def scenario_for_topic(app_id, topic_id, platform):
    if not re.fullmatch(r'APP-\d{4}', app_id or '') or not re.fullmatch(r'TOPIC-\d{4}', topic_id or ''):
        raise RecordingError('recording_topic_request_invalid')
    scenarios = [
        row for row in load_scenarios().values()
        if row['production_eligible']
        and row['app_id'] == app_id
        and topic_id in row['topics']
        and platform in row['platforms']
    ]
    if not scenarios:
        raise RecordingError('recording_scenario_not_found_for_topic')
    if len(scenarios) != 1:
        raise RecordingError('recording_scenario_ambiguous_for_topic')
    return scenarios[0]


def validate_scenario(row):
    required = {
        'scenario_id', 'app_id', 'repository', 'runner', 'test_target',
        'start_marker', 'end_marker', 'max_seconds', 'platforms',
        'android_avd', 'ios_simulator_name', 'dart_defines',
        'watch_paths', 'topics', 'production_eligible',
    }
    optional = {'project_subdir'}
    if (not isinstance(row, dict)
            or not required.issubset(row)
            or not set(row).issubset(required | optional)):
        raise RecordingError('recording_scenario_fields_invalid')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{2,63}', row['scenario_id']):
        raise RecordingError('recording_scenario_id_invalid')
    if not re.fullmatch(r'APP-\d{4}', row['app_id']):
        raise RecordingError('recording_scenario_app_invalid')
    _safe_rel(row['repository'], 'repository')
    _safe_rel(row['test_target'], 'test_target')
    if 'project_subdir' in row:
        _safe_rel(row['project_subdir'], 'project_subdir')
    if row['runner'] != 'flutter_integration_test':
        raise RecordingError('recording_runner_unsupported')
    for key in ('start_marker', 'end_marker'):
        value = row[key]
        if not isinstance(value, str) or not value or len(value) > 120 or '\n' in value:
            raise RecordingError('recording_marker_invalid')
    if type(row['max_seconds']) is not int or not 15 <= row['max_seconds'] <= 180:
        raise RecordingError('recording_duration_invalid')
    expected = ['android_emulator', 'ios_simulator']
    if not isinstance(row['platforms'], list) or not row['platforms']:
        raise RecordingError('recording_platforms_invalid')
    if any(p not in expected for p in row['platforms']) or len(set(row['platforms'])) != len(row['platforms']):
        raise RecordingError('recording_platforms_invalid')
    if not isinstance(row['android_avd'], str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', row['android_avd']):
        raise RecordingError('recording_android_avd_invalid')
    if not isinstance(row['ios_simulator_name'], str) or not row['ios_simulator_name'].strip():
        raise RecordingError('recording_ios_simulator_invalid')
    defines = row['dart_defines']
    if not isinstance(defines, dict) or len(defines) > 32:
        raise RecordingError('recording_dart_defines_invalid')
    for key, value in defines.items():
        if (not re.fullmatch(r'[A-Z][A-Z0-9_]{1,79}', key)
                or not isinstance(value, str) or len(value) > 240
                or any(ord(c) < 32 for c in value)):
            raise RecordingError('recording_dart_defines_invalid')
    watch = row['watch_paths']
    if not isinstance(watch, list) or not 1 <= len(watch) <= 32:
        raise RecordingError('recording_watch_paths_invalid')
    for item in watch:
        _safe_rel(item, 'watch_path')
    topics = row['topics']
    if (not isinstance(topics, list) or not topics
            or any(not re.fullmatch(r'TOPIC-\d{4}', item) for item in topics)):
        raise RecordingError('recording_topics_invalid')
    if type(row['production_eligible']) is not bool:
        raise RecordingError('recording_production_eligibility_invalid')
    return row


def resolve_repo(projects_root, scenario):
    root = Path(projects_root).expanduser().resolve()
    repo = (root / scenario['repository']).resolve()
    if not repo.is_relative_to(root) or not (repo / '.git').exists():
        raise RecordingError('recording_repository_missing')
    return repo


def resolve_project(repo, scenario):
    repo = Path(repo).resolve()
    project = repo
    if scenario.get('project_subdir'):
        project = (repo / scenario['project_subdir']).resolve()
    if not project.is_relative_to(repo) or not (project / 'pubspec.yaml').is_file():
        raise RecordingError('recording_project_missing')
    return project


def _repo_test_target(scenario):
    target = Path(scenario['test_target'])
    if scenario.get('project_subdir'):
        target = Path(scenario['project_subdir']) / target
    return str(target)


def _git_output(repo, args):
    _, output = _run(['git', *args], cwd=repo, timeout=30)
    return output.strip()


def _watch_paths(scenario, platform):
    watch = list(scenario['watch_paths'])
    platform_dir = 'ios' if platform == 'ios_simulator' else 'android'
    if scenario.get('project_subdir'):
        platform_dir = str(Path(scenario['project_subdir']) / platform_dir)
    watch.append(platform_dir)
    return watch


def source_commit(repo, *, refresh):
    if refresh:
        _run(['git', 'fetch', '--quiet', 'origin', 'main'], cwd=repo, timeout=120)
    commit = _git_output(repo, ['rev-parse', 'origin/main'])
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise RecordingError('recording_source_commit_invalid')
    return commit


def scenario_fingerprint(repo, scenario, platform, *, refresh):
    commit = source_commit(repo, refresh=refresh)
    watch = _watch_paths(scenario, platform)
    tracked = _git_output(repo, ['ls-tree', '-r', commit, '--', *watch])
    if not tracked:
        raise RecordingError('recording_watch_paths_untracked')
    code, _ = _run(
        ['git', 'cat-file', '-e', f"{commit}:{_repo_test_target(scenario)}"],
        cwd=repo,
        timeout=30,
        check=False,
    )
    if code:
        raise RecordingError('recording_test_target_missing_in_source')
    flutter = shutil.which('flutter')
    if not flutter:
        raise RecordingError('flutter_missing')
    _, version = _run([flutter, '--version', '--machine'], cwd=repo, timeout=30)
    try:
        flutter_version = json.loads(version)
    except ValueError as exc:
        raise RecordingError('flutter_version_invalid') from exc
    material = {
        'scenario': scenario,
        'platform': platform,
        'tracked': tracked,
        'flutter': flutter_version,
        'recorder_sha256': file_hash(Path(__file__)),
    }
    return hashlib.sha256(canonical(material)).hexdigest(), commit


@contextmanager
def isolated_source_checkout(repo, commit, temp_root):
    target = Path(temp_root) / 'source'
    _run(
        ['git', 'clone', '--shared', '--no-checkout', str(repo), str(target)],
        timeout=120,
    )
    _run(['git', 'checkout', '--detach', commit], cwd=target, timeout=60)
    try:
        yield target
    finally:
        # The entire temporary directory is removed by TemporaryDirectory.
        pass


@contextmanager
def recording_lock(asset_root):
    root = Path(asset_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / 'recordings' / '.recording.lock'
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RecordingError('another_recording_is_active') from exc
        yield
    finally:
        os.close(fd)


def _index_path(asset_root):
    return Path(asset_root).resolve() / 'recordings' / 'index.json'
def load_index(asset_root):
    path = _index_path(asset_root)
    if not path.exists():
        return {'schema_version': INDEX_SCHEMA, 'recordings': {}}
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise RecordingError('recording_index_invalid') from exc
    if (set(value) != {'schema_version', 'recordings'}
            or value['schema_version'] != INDEX_SCHEMA
            or not isinstance(value['recordings'], dict)):
        raise RecordingError('recording_index_invalid')
    return value


def _verified_video(path, *, minimum=5, maximum=180):
    try:
        info = probe(path)
        streams = [s for s in info.get('streams', []) if s.get('codec_type') == 'video']
        seconds = float(info.get('format', {}).get('duration', 0))
        if len(streams) != 1 or not minimum <= seconds <= maximum:
            return False
        video = streams[0]
        return (
            video.get('codec_name') == 'h264'
            and int(video.get('width', 0)) >= 240
            and int(video.get('height', 0)) >= 240
        )
    except (VideoError, ValueError, TypeError):
        return False


def cached_recording(asset_root, scenario, platform, fingerprint):
    index = load_index(asset_root)
    key = f"{scenario['scenario_id']}:{platform}"
    item = index['recordings'].get(key)
    if not isinstance(item, dict) or item.get('fingerprint') != fingerprint:
        return None
    rel = item.get('path')
    try:
        path = (Path(asset_root).resolve() / _safe_rel(rel, 'recording_index_path')).resolve()
    except RecordingError:
        return None
    root = Path(asset_root).resolve()
    if not path.is_relative_to(root) or path.is_symlink() or not path.is_file():
        return None
    if item.get('sha256') != file_hash(path) or not _verified_video(path):
        return None
    return item


def _write_index(asset_root, scenario, platform, fingerprint, source_commit_value, resolved_lock_hash, output):
    root = Path(asset_root).resolve()
    index = load_index(root)
    key = f"{scenario['scenario_id']}:{platform}"
    rel = str(output.relative_to(root))
    index['recordings'][key] = {
        'scenario_id': scenario['scenario_id'],
        'scenario_hash': hashlib.sha256(canonical(scenario)).hexdigest(),
        'app_id': scenario['app_id'],
        'platform': platform,
        'fingerprint': fingerprint,
        'source_commit': source_commit_value,
        'resolved_lock_sha256': resolved_lock_hash,
        'path': rel,
        'sha256': file_hash(output),
        'recorded_at': datetime.now(timezone.utc).isoformat(),
        'production_eligible': scenario['production_eligible'],
        'topics': list(scenario['topics']),
    }
    path = _index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_json(path, index)
    return index['recordings'][key]


def _free_android_port():
    used = set()
    _, output = _run(['adb', 'devices'], timeout=15)
    for line in output.splitlines():
        match = re.match(r'emulator-(\d+)\s', line)
        if match:
            used.add(int(match.group(1)))
    for port in range(5580, 5680, 2):
        if port not in used:
            return port
    raise RecordingError('no_free_android_emulator_port')


def _emulator_binary():
    candidates = [
        shutil.which('emulator'),
        str(Path.home() / 'Library/Android/sdk/emulator/emulator'),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RecordingError('android_emulator_binary_missing')


def _wait_android(serial, timeout=180, proc=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            raise RecordingError('android_emulator_exited_during_boot')
        code, output = _run(
            ['adb', '-s', serial, 'shell', 'getprop', 'sys.boot_completed'],
            timeout=10,
            check=False,
        )
        if code == 0 and output.strip() == '1':
            return
        time.sleep(2)
    raise RecordingError('android_emulator_boot_timeout')


def _wait_android_gone(serial, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, output = _run(['adb', 'devices'], timeout=10)
        if not re.search(rf'^{re.escape(serial)}\s+', output, re.M):
            return
        time.sleep(1)
    raise RecordingError('android_emulator_shutdown_timeout')


@contextmanager
def android_device(scenario, explicit_serial=None):
    owned = False
    emulator_proc = None
    serial = explicit_serial or os.environ.get('ONNELLAB_VIDEO_ANDROID_SERIAL')
    if serial:
        if not re.fullmatch(r'emulator-\d+', serial):
            raise RecordingError('physical_android_device_forbidden')
        code, _ = _run(['adb', '-s', serial, 'get-state'], timeout=15, check=False)
        if code:
            raise RecordingError('configured_android_emulator_unavailable')
        code, name = _run(['adb', '-s', serial, 'emu', 'avd', 'name'], timeout=10, check=False)
        if code or not name.splitlines() or name.splitlines()[0].strip() != scenario['android_avd']:
            raise RecordingError('configured_android_emulator_wrong_avd')
    else:
        avd = scenario['android_avd']
        emulator = _emulator_binary()
        _, avds = _run([emulator, '-list-avds'], timeout=30)
        if avd not in {line.strip() for line in avds.splitlines() if line.strip()}:
            raise RecordingError('dedicated_android_avd_missing')
        _, devices = _run(['adb', 'devices'], timeout=15)
        for match in re.findall(r'^(emulator-\d+)\s+device$', devices, re.M):
            code, name = _run(['adb', '-s', match, 'emu', 'avd', 'name'], timeout=10, check=False)
            if code == 0 and name.splitlines()[0].strip() == avd:
                raise RecordingError('dedicated_android_emulator_already_running')
        port = _free_android_port()
        serial = f'emulator-{port}'
        emulator_proc = subprocess.Popen(
            [emulator, '-avd', avd, '-port', str(port), '-no-window',
             '-no-audio', '-no-boot-anim', '-no-snapshot-load', '-no-snapshot-save'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        owned = True
        _wait_android(serial, proc=emulator_proc)
    try:
        yield serial
    finally:
        if owned and serial:
            _run(['adb', '-s', serial, 'emu', 'kill'], timeout=15, check=False)
        if owned and emulator_proc:
            try:
                emulator_proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(emulator_proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    emulator_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(emulator_proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    emulator_proc.wait()
        if owned and serial:
            _wait_android_gone(serial)


def _simulator_rows():
    _, output = _run(['xcrun', 'simctl', 'list', 'devices', 'available', '--json'], timeout=30)
    try:
        payload = json.loads(output)
    except ValueError as exc:
        raise RecordingError('simulator_list_invalid') from exc
    rows = []
    for runtime, devices in payload.get('devices', {}).items():
        for item in devices:
            if item.get('isAvailable'):
                rows.append((runtime, item))
    return rows


@contextmanager
def ios_device(scenario, explicit_udid=None):
    owned = False
    udid = explicit_udid or os.environ.get('ONNELLAB_VIDEO_IOS_UDID')
    rows = _simulator_rows()
    if udid:
        matches = [item for _, item in rows if item.get('udid') == udid]
        if len(matches) != 1 or matches[0].get('state') != 'Booted':
            raise RecordingError('configured_ios_simulator_unavailable')
        if matches[0].get('name') != scenario['ios_simulator_name']:
            raise RecordingError('configured_ios_simulator_wrong_device')
    else:
        name = scenario['ios_simulator_name']
        matches = [item for _, item in rows if item.get('name') == name]
        if len(matches) != 1:
            raise RecordingError('dedicated_ios_simulator_ambiguous')
        item = matches[0]
        udid = item['udid']
        if item.get('state') == 'Booted':
            raise RecordingError('dedicated_ios_simulator_already_running')
        _run(['xcrun', 'simctl', 'boot', udid], timeout=30)
        _run(['xcrun', 'simctl', 'bootstatus', udid, '-b'], timeout=120)
        owned = True
    try:
        yield udid
    finally:
        if owned and udid:
            _run(['xcrun', 'simctl', 'shutdown', udid], timeout=30, check=False)


def _stop_group(proc, *, interrupt=True):
    if not proc or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGINT if interrupt else signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()


def _android_remote_alive(serial, remote_pid):
    code, _ = _run(
        ['adb', '-s', serial, 'shell', 'kill', '-0', str(remote_pid)],
        timeout=10,
        check=False,
    )
    return code == 0


def _android_screenrecord_pids(serial):
    code, output = _run(
        ['adb', '-s', serial, 'shell', 'pidof', 'screenrecord'],
        timeout=10,
        check=False,
    )
    if code != 0 or not output.strip():
        return []
    pids = []
    for value in output.split():
        if not re.fullmatch(r'\d{1,10}', value):
            raise RecordingError('android_recording_pid_invalid')
        pid = int(value)
        if pid <= 1:
            raise RecordingError('android_recording_pid_invalid')
        pids.append(pid)
    return sorted(set(pids))


def _stop_android_remote(serial, remote_pid):
    if not remote_pid:
        return
    _run(
        ['adb', '-s', serial, 'shell', 'kill', '-2', str(remote_pid)],
        timeout=10,
        check=False,
    )
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not _android_remote_alive(serial, remote_pid):
            return
        time.sleep(0.25)
    _run(
        ['adb', '-s', serial, 'shell', 'kill', '-15', str(remote_pid)],
        timeout=10,
        check=False,
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not _android_remote_alive(serial, remote_pid):
            return
        time.sleep(0.25)
    _run(
        ['adb', '-s', serial, 'shell', 'kill', '-9', str(remote_pid)],
        timeout=10,
        check=False,
    )


def _start_android_recording(serial, temp, seconds):
    if _android_screenrecord_pids(serial):
        raise RecordingError('unexpected_existing_screenrecord')
    remote = f'/data/local/tmp/onnellab-record-{os.getpid()}.mp4'
    proc = subprocess.Popen(
        [
            'adb', '-s', serial, 'shell', 'screenrecord',
            '--size', ANDROID_RECORD_SIZE,
            '--bit-rate', '8000000',
            '--size', '720x1280',
            '--time-limit', str(min(seconds + 15, 180)),
            remote,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + 10
    remote_pid = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        pids = _android_screenrecord_pids(serial)
        if len(pids) == 1:
            remote_pid = pids[0]
            break
        if len(pids) > 1:
            _stop_group(proc, interrupt=False)
            raise RecordingError('android_recording_pid_ambiguous')
        time.sleep(0.25)
    if remote_pid is None:
        _stop_group(proc, interrupt=False)
        raise RecordingError('android_recording_start_failed')
    return proc, remote_pid, remote


def _finish_android_recording(serial, proc, remote_pid, remote, temp):
    _stop_android_remote(serial, remote_pid)
    if _android_remote_alive(serial, remote_pid):
        _stop_group(proc, interrupt=False)
        raise RecordingError('android_recording_stop_failed')
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        _stop_group(proc, interrupt=False)
    time.sleep(0.5)
    raw = Path(temp) / 'raw-android.mp4'
    try:
        _run(['adb', '-s', serial, 'pull', remote, str(raw)], timeout=60)
    finally:
        _run(
            ['adb', '-s', serial, 'shell', 'rm', '-f', remote],
            timeout=15,
            check=False,
        )
    if not raw.is_file() or raw.stat().st_size <= 0:
        raise RecordingError('android_recording_missing')
    return raw


def _start_ios_recording(udid, temp):
    raw = Path(temp) / 'raw-ios.mov'
    proc = subprocess.Popen(
        ['xcrun', 'simctl', 'io', udid, 'recordVideo', '--codec=h264', '--force', str(raw)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        ready, _, _ = select.select([proc.stderr], [], [], 0.5)
        if ready:
            line = proc.stderr.readline()
            if 'Recording started' in line:
                return proc, raw
        if proc.poll() is not None:
            break
    _stop_group(proc, interrupt=False)
    raise RecordingError('ios_recording_start_failed')


def _finish_ios_recording(proc, raw):
    _stop_group(proc)
    if not raw.is_file():
        raise RecordingError('ios_recording_missing')
    return raw


def _normalize(raw, output):
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = output.with_suffix('.partial.mp4')
    temp.unlink(missing_ok=True)
    argv = [
        'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
        '-i', str(raw), '-an',
        '-vf', 'fps=30,scale=trunc(iw/2)*2:trunc(ih/2)*2',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
        '-y', str(temp),
    ]
    _run(argv, timeout=180)
    if not _verified_video(temp):
        temp.unlink(missing_ok=True)
        raise RecordingError('normalized_recording_invalid')
    os.replace(temp, output)


def _test_command(repo, scenario, device_id):
    flutter = shutil.which('flutter')
    if not flutter:
        raise RecordingError('flutter_missing')
    argv = [
        flutter, 'test', scenario['test_target'], '-d', device_id, '--no-pub',
    ]
    for key, value in sorted(scenario['dart_defines'].items()):
        argv.append(f'--dart-define={key}={value}')
    return argv


def resolve_flutter_dependencies(repo):
    flutter = shutil.which('flutter')
    if not flutter:
        raise RecordingError('flutter_missing')
    _run([flutter, 'pub', 'get'], cwd=repo, timeout=180)
    lock = Path(repo) / 'pubspec.lock'
    if not lock.is_file():
        raise RecordingError('resolved_flutter_lock_missing')
    return file_hash(lock)


def _run_and_capture(repo, scenario, platform, device_id, temp):
    test = subprocess.Popen(
        _test_command(repo, scenario, device_id),
        cwd=repo,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
        env={**os.environ, 'CI': 'true'},
    )
    recorder = None
    android_remote_pid = None
    remote = None
    raw = None
    seen_start = False
    seen_end = False
    log = []
    deadline = time.monotonic() + scenario['max_seconds'] + 180
    try:
        while True:
            if time.monotonic() > deadline:
                raise RecordingError('recording_scenario_timeout')
            if test.stdout is None:
                raise RecordingError('recording_test_log_unavailable')
            ready, _, _ = select.select([test.stdout], [], [], 0.5)
            if ready:
                line = test.stdout.readline()
                if line:
                    log.append(line)
                    if sum(len(x) for x in log) > MAX_LOG_BYTES:
                        log = log[-1000:]
                    if not seen_start and scenario['start_marker'] in line:
                        seen_start = True
                        if platform == 'android_emulator':
                            recorder, android_remote_pid, remote = _start_android_recording(
                                device_id, temp, scenario['max_seconds'])
                        else:
                            recorder, raw = _start_ios_recording(device_id, temp)
                    if seen_start and scenario['end_marker'] in line:
                        seen_end = True
            code = test.poll()
            if code is not None:
                if test.stdout:
                    rest = test.stdout.read()
                    if rest:
                        log.append(rest)
                        if scenario['end_marker'] in rest:
                            seen_end = True
                if code != 0:
                    raise RecordingError('recording_scenario_test_failed')
                break
        recording_started = (
            android_remote_pid is not None
            if platform == 'android_emulator'
            else recorder is not None
        )
        if not seen_start or not seen_end or not recording_started:
            raise RecordingError('recording_markers_missing')
        if platform == 'android_emulator':
            raw = _finish_android_recording(
                device_id, recorder, android_remote_pid, remote, temp)
            android_remote_pid = None
            recorder = None
        else:
            raw = _finish_ios_recording(recorder, raw)
            recorder = None
        return raw, ''.join(log)[-MAX_LOG_BYTES:]
    finally:
        if android_remote_pid is not None:
            _stop_android_remote(device_id, android_remote_pid)
        _stop_group(recorder, interrupt=False)
        if platform == 'android_emulator' and remote:
            _run(
                ['adb', '-s', device_id, 'shell', 'rm', '-f', remote],
                timeout=15,
                check=False,
            )
        _stop_group(test, interrupt=False)


def require_promotable_app(scenario):
    path = ROOT / 'data/apps_registry.csv'
    try:
        with path.open(newline='', encoding='utf-8') as stream:
            apps = {row['app_id']: row for row in csv.DictReader(stream)}
    except OSError as exc:
        raise RecordingError('app_registry_unavailable') from exc
    app = apps.get(scenario['app_id'])
    if (not app or app.get('status') != 'released'
            or app.get('content_eligible') != 'true'):
        raise RecordingError('recording_app_not_promotable')
    return app


def ensure_recording(
    scenario_id,
    *,
    projects_root,
    asset_root,
    platform,
    dry_run=False,
    android_serial=None,
    ios_udid=None,
):
    scenarios = load_scenarios()
    scenario = scenarios.get(scenario_id)
    if not scenario:
        raise RecordingError('unknown_recording_scenario')
    if platform not in scenario['platforms']:
        raise RecordingError('recording_platform_not_supported')
    require_promotable_app(scenario)
    repo = resolve_repo(projects_root, scenario)
    if dry_run:
        base_fingerprint, commit = scenario_fingerprint(
            repo, scenario, platform, refresh=False)
        return {
            'status': 'recording_plan',
            'scenario_id': scenario_id,
            'app_id': scenario['app_id'],
            'platform': platform,
            'base_fingerprint': base_fingerprint,
            'source_commit': commit,
            'dependency_resolution_required': True,
            'source_ref_may_be_stale': True,
        }
    root = Path(asset_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with recording_lock(root):
        base_fingerprint, commit = scenario_fingerprint(
            repo, scenario, platform, refresh=True)
        with tempfile.TemporaryDirectory(prefix='onnellab-record-') as temp:
            with isolated_source_checkout(repo, commit, temp) as source:
                project = resolve_project(source, scenario)
                resolved_lock_hash = resolve_flutter_dependencies(project)
                fingerprint = hashlib.sha256(canonical({
                    'base_fingerprint': base_fingerprint,
                    'resolved_lock_sha256': resolved_lock_hash,
                })).hexdigest()
                cached = cached_recording(root, scenario, platform, fingerprint)
                if cached:
                    return {'status': 'cached', **cached}
                output = (
                    root / 'recordings' / scenario['app_id'].lower()
                    / scenario_id / f'{fingerprint[:16]}.mp4'
                )
                if platform == 'android_emulator':
                    with android_device(scenario, android_serial) as device:
                        raw, log = _run_and_capture(
                            project, scenario, platform, device, temp)
                else:
                    with ios_device(scenario, ios_udid) as device:
                        raw, log = _run_and_capture(
                            project, scenario, platform, device, temp)
                _normalize(raw, output)
        item = _write_index(
            root, scenario, platform, fingerprint, commit,
            resolved_lock_hash, output)
    return {
        'status': 'recorded',
        **item,
        'log_markers': {
            'start': scenario['start_marker'],
            'end': scenario['end_marker'],
        },
    }


def status(asset_root):
    index = load_index(asset_root)
    result = []
    root = Path(asset_root).expanduser().resolve()
    for key, item in sorted(index['recordings'].items()):
        rel = item.get('path')
        try:
            path = (root / _safe_rel(
                rel, 'recording_index_path')).resolve()
            valid_path = path.is_relative_to(root)
        except RecordingError:
            path = root
            valid_path = False
        present = valid_path and path.is_file() and not path.is_symlink()
        verified = (
            present
            and item.get('sha256') == file_hash(path)
            and _verified_video(path)
        )
        result.append({
            **item,
            'key': key,
            'present': present,
            'verified': verified,
        })
    return result


def managed_recording_attestation(asset_root, job):
    """Validate that a production brief uses a current managed recording."""
    root = Path(asset_root).expanduser().resolve()
    recording = job.get('brief', {}).get('recording')
    if not isinstance(recording, str):
        raise RecordingError('managed_recording_missing')
    index = load_index(root)
    matches = [
        item for item in index['recordings'].values()
        if isinstance(item, dict) and item.get('path') == recording
    ]
    if len(matches) != 1:
        raise RecordingError('managed_recording_missing')
    item = matches[0]
    if (item.get('app_id') != job.get('brief', {}).get('app_id')
            or item.get('production_eligible') is not True
            or job.get('brief', {}).get('topic_id') not in item.get('topics', [])):
        raise RecordingError('managed_recording_scope_mismatch')
    path = (root / _safe_rel(recording, 'managed_recording_path')).resolve()
    if (not path.is_relative_to(root) or path.is_symlink() or not path.is_file()
            or item.get('sha256') != file_hash(path)
            or item.get('sha256') != job.get('assets', {}).get('recording', {}).get('sha256')
            or not _verified_video(path)):
        raise RecordingError('managed_recording_integrity')
    scenarios = load_scenarios()
    scenario = scenarios.get(item.get('scenario_id'))
    if (not scenario or scenario.get('production_eligible') is not True
            or scenario.get('app_id') != item.get('app_id')
            or job['brief']['topic_id'] not in scenario.get('topics', [])
            or item.get('scenario_hash') != hashlib.sha256(canonical(scenario)).hexdigest()):
        raise RecordingError('managed_recording_scenario_changed')
    return {
        'scenario_id': item['scenario_id'],
        'platform': item['platform'],
        'fingerprint': item['fingerprint'],
        'sha256': item['sha256'],
    }
