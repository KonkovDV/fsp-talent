"""Runs solve on each case and prints the outputs. Exit 2 means a limit was hit."""
import json
import os
import sys

_CONTROL = "/run/sandbox"


def _guarded(path: object) -> bool:
    """True for the control socket and its directory. The solution shares the server uid."""
    try:
        text = os.fsdecode(path)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    for item in (text.replace("\\", "/"), os.path.abspath(text).replace("\\", "/")):
        if item == _CONTROL or item.startswith(_CONTROL + "/"):
            return True
    return False


def _shield_control_socket() -> None:
    """Refuse to unlink, rename or rewrite the control socket. Reload is blocked separately."""
    def deny(path: object) -> None:
        raise OSError(13, "Permission denied", path)

    real_unlink = os.unlink
    real_rename, real_replace = os.rename, os.replace
    real_chmod, real_open = os.chmod, os.open
    real_builtin_open = open

    def unlink(path, *args, **kwargs):
        if _guarded(path):
            deny(path)
        return real_unlink(path, *args, **kwargs)

    def rename(src, dst, *args, **kwargs):
        if _guarded(src) or _guarded(dst):
            deny(src)
        return real_rename(src, dst, *args, **kwargs)

    def replace(src, dst, *args, **kwargs):
        if _guarded(src) or _guarded(dst):
            deny(src)
        return real_replace(src, dst, *args, **kwargs)

    def chmod(path, mode, *args, **kwargs):
        if _guarded(path):
            deny(path)
        return real_chmod(path, mode, *args, **kwargs)

    def os_open(path, flags, *args, **kwargs):
        if _guarded(path):
            deny(path)
        return real_open(path, flags, *args, **kwargs)

    def builtin_open(file, *args, **kwargs):
        if _guarded(file):
            deny(file)
        return real_builtin_open(file, *args, **kwargs)

    os.unlink = unlink
    os.remove = unlink
    os.rename = rename
    os.replace = replace
    os.chmod = chmod
    os.open = os_open
    builtins_open = sys.modules["builtins"]
    builtins_open.open = builtin_open


def _shield_reimport() -> None:
    """A reload of os, or a fresh ctypes, must not reach the control socket.

    Loading the stdlib file by its path still builds an unshielded module. The container
    has no network and the server binds the socket again if the path disappears.
    """
    import importlib
    import importlib.util

    real_reload = importlib.reload
    real_spec = importlib.util.spec_from_file_location

    def reload(module):
        name = getattr(module, "__name__", "")
        if name in {"os", "posix", "nt"}:
            raise OSError(13, "Permission denied")
        return real_reload(module)

    def spec_from_file_location(name, location, *args, **kwargs):
        base = ""
        if isinstance(location, (str, bytes, os.PathLike)):
            base = os.path.basename(os.fsdecode(location))
        blocked = name in {"os", "posix", "nt", "ctypes", "_ctypes"} or base in {"os.py", "posixmodule.c"}
        if blocked:
            raise OSError(13, "Permission denied")
        return real_spec(name, location, *args, **kwargs)

    class _BlockFreshOs:
        def find_spec(self, fullname, path, target=None):
            if fullname in {"ctypes", "_ctypes"} or fullname.startswith("ctypes."):
                raise ModuleNotFoundError(fullname)
            return None

    importlib.reload = reload
    importlib.util.spec_from_file_location = spec_from_file_location
    sys.meta_path.insert(0, _BlockFreshOs())


def main() -> None:
    sys.setrecursionlimit(2000)
    _shield_control_socket()
    _shield_reimport()
    msg = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    ns: dict = {}
    try:
        exec(compile(msg["source"], "<solution>", "exec"), ns, ns)  # noqa: S102 — isolated container
        solve = ns["solve"]
        out = []
        for args in msg["cases"]:
            try:
                value = solve(*args)
            except (RecursionError, MemoryError):
                raise
            except Exception:
                value = None
            out.append(value if isinstance(value, int) and not isinstance(value, bool) else None)
    except (RecursionError, MemoryError):
        sys.exit(2)
    except Exception:
        sys.exit(1)
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
