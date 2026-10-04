"""Read-only privacy checks. Never edit an ACL, owner, token, or OS policy."""
from __future__ import annotations

import os
from pathlib import Path
import stat

# Generic access, all file-specific rights, DELETE/READ_CONTROL/WRITE_DAC/OWNER.
# A foreign write-only grant can tamper with queue/session state just as a read
# grant can expose it. Only synchronization without data rights is harmless.
_EXPOSING_ACCESS = 0xF0000000 | 0x000F01FF


def private_dacl(owner, current_user, entries):
    """Conservatively reject unknown ACE kinds and broad/foreign readable grants."""
    if not owner or owner != current_user or entries is None:
        return False
    # OWNER RIGHTS is the verified object's owner, not a broad group. Python
    # 3.13+ uses it in the private DACL created for mode=0o700 directories.
    allowed = {owner, 'S-1-5-18', 'S-1-5-32-544', 'S-1-3-4'}
    for ace_type, mask, sid in entries:
        if ace_type == 1:  # ACCESS_DENIED_ACE cannot expose the file.
            continue
        if ace_type != 0 or (mask & _EXPOSING_ACCESS and sid not in allowed):
            return False
    return True


def _windows_security(path):
    import ctypes
    from ctypes import wintypes as wt

    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)

    def api(library, name, result, *args):
        func = getattr(library, name)
        func.restype = result
        func.argtypes = args
        return func

    pointer = ctypes.c_void_p
    get_security = api(advapi, 'GetNamedSecurityInfoW', wt.DWORD, wt.LPCWSTR,
                       ctypes.c_int, wt.DWORD, ctypes.POINTER(pointer), pointer,
                       ctypes.POINTER(pointer), pointer, ctypes.POINTER(pointer))
    get_ace = api(advapi, 'GetAce', wt.BOOL, pointer, wt.DWORD, ctypes.POINTER(pointer))
    convert_sid = api(advapi, 'ConvertSidToStringSidW', wt.BOOL, pointer, ctypes.POINTER(pointer))
    open_token = api(advapi, 'OpenProcessToken', wt.BOOL, wt.HANDLE, wt.DWORD, ctypes.POINTER(wt.HANDLE))
    get_token = api(advapi, 'GetTokenInformation', wt.BOOL, wt.HANDLE, ctypes.c_int,
                    pointer, wt.DWORD, ctypes.POINTER(wt.DWORD))
    current_process = api(kernel, 'GetCurrentProcess', wt.HANDLE)
    close = api(kernel, 'CloseHandle', wt.BOOL, wt.HANDLE)
    free = api(kernel, 'LocalFree', pointer, pointer)

    def sid_text(sid):
        text = pointer()
        if not sid or not convert_sid(sid, ctypes.byref(text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.wstring_at(text)
        finally:
            free(text)

    class ACL(ctypes.Structure):
        _fields_ = [('revision', wt.BYTE), ('reserved', wt.BYTE), ('size', wt.WORD),
                    ('count', wt.WORD), ('reserved2', wt.WORD)]

    token = wt.HANDLE()
    if not open_token(current_process(), 0x0008, ctypes.byref(token)):  # TOKEN_QUERY only
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wt.DWORD()
        get_token(token, 1, None, 0, ctypes.byref(size))  # TokenUser
        if not 0 < size.value < 65536:
            raise OSError('Cannot inspect the current user token')
        user = ctypes.create_string_buffer(size.value)
        if not get_token(token, 1, user, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        current_sid = sid_text(pointer.from_buffer(user).value)
    finally:
        close(token)

    owner, dacl, descriptor = pointer(), pointer(), pointer()
    result = get_security(str(path), 1, 0x00000005, ctypes.byref(owner), None,
                          ctypes.byref(dacl), None, ctypes.byref(descriptor))
    if result:
        raise ctypes.WinError(result)
    try:
        owner_sid = sid_text(owner)
        if not dacl:
            return owner_sid, current_sid, None  # Null DACL grants everyone access.
        acl = ACL.from_address(dacl.value)
        entries = []
        for index in range(acl.count):
            ace = pointer()
            if not get_ace(dacl, index, ctypes.byref(ace)):
                raise ctypes.WinError(ctypes.get_last_error())
            header = ctypes.string_at(ace, 4)
            kind = header[0]
            size = int.from_bytes(header[2:4], 'little')
            if kind not in (0, 1) or size < 12:
                raise OSError('Unsupported access-control entry')
            mask = wt.DWORD.from_address(ace.value + 4).value
            entries.append((kind, mask, sid_text(ace.value + 8)))
        return owner_sid, current_sid, entries
    finally:
        free(descriptor)


def private_path_permissions(path):
    """Fail closed on missing/linked/uninspectable paths; POSIX mode gate retained."""
    path = Path(path)
    try:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            return False
        if os.name == 'nt':
            return private_dacl(*_windows_security(path))
        return info.st_mode & 0o077 == 0
    except (OSError, ValueError):
        return False
