"""Local file locks and owned subprocesses for Windows and POSIX workers.

Windows uses an exclusive non-inheritable file handle and a private Job Object.
Children start suspended and enter the job before any application code can spawn
descendants. No process-name searches, global taskkill, or security changes.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading

if os.name == 'nt':
    import ctypes
    from ctypes import wintypes as wt

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)

    def _api(name, result, *args):
        func = getattr(kernel, name)
        func.restype = result
        func.argtypes = args
        return func

    _close = _api('CloseHandle', wt.BOOL, wt.HANDLE)
    _create_file = _api('CreateFileW', wt.HANDLE, wt.LPCWSTR, wt.DWORD,
                        wt.DWORD, wt.LPVOID, wt.DWORD, wt.DWORD, wt.HANDLE)
    _file_info = _api('GetFileInformationByHandleEx', wt.BOOL, wt.HANDLE,
                      ctypes.c_int, wt.LPVOID, wt.DWORD)
    _create_job = _api('CreateJobObjectW', wt.HANDLE, wt.LPVOID, wt.LPCWSTR)
    _set_job = _api('SetInformationJobObject', wt.BOOL, wt.HANDLE,
                    ctypes.c_int, wt.LPVOID, wt.DWORD)
    _assign_job = _api('AssignProcessToJobObject', wt.BOOL, wt.HANDLE, wt.HANDLE)
    _snapshot = _api('CreateToolhelp32Snapshot', wt.HANDLE, wt.DWORD, wt.DWORD)
    _thread_first = _api('Thread32First', wt.BOOL, wt.HANDLE, wt.LPVOID)
    _thread_next = _api('Thread32Next', wt.BOOL, wt.HANDLE, wt.LPVOID)
    _open_thread = _api('OpenThread', wt.HANDLE, wt.DWORD, wt.BOOL, wt.DWORD)
    _resume_thread = _api('ResumeThread', wt.DWORD, wt.HANDLE)
    _INVALID_HANDLE = ctypes.c_void_p(-1).value

    class _BasicLimits(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                    ('flags', wt.DWORD), ('minimum_working_set', ctypes.c_size_t),
                    ('maximum_working_set', ctypes.c_size_t), ('active_processes', wt.DWORD),
                    ('affinity', ctypes.c_size_t), ('priority', wt.DWORD), ('scheduling', wt.DWORD)]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [('basic', _BasicLimits), ('io', ctypes.c_uint64 * 6),
                    ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                    ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]

    class _ThreadEntry(ctypes.Structure):
        _fields_ = [('size', wt.DWORD), ('usage', wt.DWORD), ('thread', wt.DWORD),
                    ('process', wt.DWORD), ('base_priority', wt.LONG),
                    ('delta_priority', wt.LONG), ('flags', wt.DWORD)]

    def _resume_owned_process(pid):
        snapshot = _snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
        if snapshot == _INVALID_HANDLE:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = _ThreadEntry()
            entry.size = ctypes.sizeof(entry)
            found = _thread_first(snapshot, ctypes.byref(entry))
            while found:
                if entry.process == pid:
                    thread = _open_thread(0x0002, False, entry.thread)  # THREAD_SUSPEND_RESUME
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if _resume_thread(thread) == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                        return
                    finally:
                        _close(thread)
                found = _thread_next(snapshot, ctypes.byref(entry))
            raise OSError('Cannot resume the owned suspended process')
        finally:
            _close(snapshot)


@contextmanager
def exclusive_file_lock(path):
    """Nonblocking lock; reject a link at the lock file instead of following it."""
    if os.name == 'nt':
        # share=0 holds an exclusive lock until close, including against deletion.
        handle = _create_file(str(Path(path)), 0xC0000000, 0, None, 4, 0x00200000, None)
        if handle == _INVALID_HANDLE:
            error = ctypes.get_last_error()
            if error in (32, 33):  # sharing/lock violation
                raise BlockingIOError(errno.EAGAIN, 'Lock is held', str(path))
            raise ctypes.WinError(error)
        try:
            attributes = (wt.DWORD * 2)()
            if not _file_info(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes)):
                raise ctypes.WinError(ctypes.get_last_error())
            if attributes[0] & 0x00000400:  # FILE_ATTRIBUTE_REPARSE_POINT
                raise OSError(errno.ELOOP, 'Linked lock file rejected', str(path))
            yield
        finally:
            _close(handle)
    else:
        import fcntl
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)


def sync_directory(path):
    # Windows has no portable directory fsync. atomic_json still flushes the
    # file before os.replace; POSIX retains its additional directory durability.
    if os.name == 'nt':
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def spawn_owned(argv, **kwargs):
    """Start a hidden Windows job or a POSIX session, with no shell."""
    if os.name != 'nt':
        proc = subprocess.Popen(argv, start_new_session=True, **kwargs)
        proc._short_video_pgid = proc.pid
        return proc
    job = _create_job(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    proc = None
    try:
        limits = _ExtendedLimits()
        limits.basic.flags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _set_job(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        proc = subprocess.Popen(
            argv, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004,
            **kwargs,  # CREATE_SUSPENDED prevents descendants escaping assignment.
        )
        if not _assign_job(job, int(proc._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        _resume_owned_process(proc.pid)
        proc._short_video_job = job
        return proc
    except BaseException:
        _close(job)
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=10)
        raise


def _darwin_group_finished(proc):
    """Confirm Darwin's zombie-only-group EPERM without ignoring live failures.

    XNU killpg1 skips zombies and can return EPERM when none remain signalable.
    Inspect only the recorded group, after reaping our direct child; any unknown
    output or live member leaves the original permission error intact.
    """
    if sys.platform != 'darwin' or getattr(proc, '_short_video_pgid', None) != proc.pid:
        return False
    if proc.poll() is None:
        return False
    try:
        result = subprocess.run(
            ['/bin/ps', '-x', '-o', 'pid=,pgid=,stat=', '-g', str(proc.pid)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode not in (0, 1) or result.stderr.strip():
        return False
    for line in result.stdout.splitlines():
        fields = line.split()
        if (len(fields) != 3 or not fields[0].isdigit() or int(fields[0]) <= 0
                or fields[1] != str(proc.pid) or not fields[2].startswith('Z')):
            return False
    return True


def _signal_owned_group(proc, signum):
    try:
        os.killpg(proc.pid, signum)
        return True
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        if exc.errno == errno.EPERM and _darwin_group_finished(proc):
            return False
        raise


def stop_owned(proc, *, interrupt=False, grace=5):
    """Clean only the invocation's job/session, even if its direct child exited."""
    if proc is None:
        return
    if getattr(proc, '_short_video_stopped', False) is True:
        return
    if os.name == 'nt':
        job = getattr(proc, '_short_video_job', None)
        if job is None:
            if hasattr(proc, '_short_video_job'):
                return  # This exact invocation was already cleaned.
            raise OSError('Refusing cleanup of a process without an owned job')
        proc._short_video_job = None
        _close(job)  # Kills remaining descendants, including after parent exit.
        proc.wait(timeout=10)
        proc._short_video_stopped = True
        return
    if not _signal_owned_group(proc, signal.SIGINT if interrupt else signal.SIGTERM):
        proc.wait(timeout=grace)
        proc._short_video_stopped = True
        return
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
    _signal_owned_group(proc, signal.SIGKILL)
    proc.wait()
    proc._short_video_stopped = True


class OutputLines:
    """Bounded line reader for subprocess pipes (Windows select is socket-only)."""
    def __init__(self, stream):
        self.stream = stream
        self.lines = queue.Queue(maxsize=32)
        self.stopped = threading.Event()
        self.eof = False
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        try:
            while not self.stopped.is_set():
                line = self.stream.readline(65536)
                while not self.stopped.is_set():
                    try:
                        self.lines.put(line, timeout=0.1)
                        break
                    except queue.Full:
                        pass
                if not line:
                    return
        except (OSError, ValueError):
            self.stopped.set()

    def read(self, timeout=0.5):
        try:
            line = self.lines.get(timeout=timeout)
        except queue.Empty:
            return None
        if not line:
            self.eof = True
        return line

    def close(self):
        # Caller terminates the owned process first, which releases inherited pipes.
        self.stopped.set()
        self.thread.join(timeout=2)
        if not self.thread.is_alive():
            self.stream.close()
