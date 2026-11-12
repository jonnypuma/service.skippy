# -*- coding: utf-8 -*-
"""A stand-in for Kodi's ``xbmcvfs`` that reads and writes real files in a temp folder.

``install(test, *modules)`` patches ``xbmcvfs`` in each module for the length of the test and
returns the folder (a str ending without a separator). Paths are plain OS paths.
"""

import os
import shutil
import tempfile
import types
from unittest.mock import patch


class _File:
    def __init__(self, vfs, path, mode="r"):
        self._vfs = vfs
        self._path = path
        self._mode = mode
        self._buffer = b""
        if "w" in mode:
            # A path in ``fail_writes_to`` fails that many writes (a dropped connection, say).
            left = vfs.fail_writes_to.get(path, 0)
            self._broken = left > 0
            if left:
                vfs.fail_writes_to[path] = left - 1
            if vfs.truncate_on_open or not os.path.exists(path):
                with open(path, "wb"):
                    pass

    def __bool__(self):
        return True

    def read(self):
        with open(self._path, "rb") as handle:
            data = handle.read()
        return data.decode("utf-8", errors="replace")

    def readBytes(self, *_size):
        with open(self._path, "rb") as handle:
            return bytearray(handle.read())

    def write(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        if getattr(self, "_broken", False):
            return False  # what a full disk or read-only share looks like through Kodi's VFS
        self._buffer += bytes(data)
        return True

    def size(self):
        return os.path.getsize(self._path)

    def close(self):
        if "w" in self._mode and not getattr(self, "_broken", False):
            # Like Kodi's NFS and SMB backends with truncate_on_open off: bytes past the
            # new end of the file stay where they were.
            with open(self._path, "r+b" if not self._vfs.truncate_on_open else "wb") as handle:
                handle.write(self._buffer)


class FakeVfs(types.SimpleNamespace):
    def __init__(self, root):
        super().__init__()
        self.root = root
        self.fail_writes_to = {}
        self.truncate_on_open = True
        self.deleted = []

    def exists(self, path):
        return os.path.exists(path.rstrip("/\\") or path)

    def File(self, path, mode="r"):
        return _File(self, path, mode)

    def delete(self, path):
        self.deleted.append(path)
        os.remove(path)
        return True

    def copy(self, src, dst):
        shutil.copyfile(src, dst)
        return True

    def rename(self, src, dst):
        os.replace(src, dst)
        return True

    def mkdirs(self, path):
        os.makedirs(path, exist_ok=True)
        return True

    def mkdir(self, path):
        os.makedirs(path, exist_ok=True)
        return True

    def listdir(self, path):
        path = path.rstrip("/\\")
        if not os.path.isdir(path):
            return [], []
        names = os.listdir(path)
        dirs = [n for n in names if os.path.isdir(os.path.join(path, n))]
        files = [n for n in names if not os.path.isdir(os.path.join(path, n))]
        return dirs, files

    def translatePath(self, path):
        return path

    def Stat(self, path):
        info = os.stat(path)
        return types.SimpleNamespace(st_size=lambda: info.st_size, st_mtime=lambda: int(info.st_mtime))


def install(test, *modules):
    """Patch ``xbmcvfs`` in ``modules`` with a disk-backed fake; returns ``(vfs, folder)``."""
    folder = tempfile.mkdtemp(prefix="skippy-vfs-")
    test.addCleanup(shutil.rmtree, folder, True)
    vfs = FakeVfs(folder)
    for module in modules:
        patcher = patch.object(module, "xbmcvfs", vfs)
        patcher.start()
        test.addCleanup(patcher.stop)
    return vfs, folder


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()
