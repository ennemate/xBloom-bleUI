from __future__ import annotations
import os
import stat
import sys
from pathlib import Path
import platformdirs
APP = 'xbloom'

def _resolve(override_env: str, xdg_env: str, default_factory) -> Path:
    override = os.environ.get(override_env)
    if override:
        return Path(override).expanduser()
    home = os.environ.get('XBLOOM_HOME')
    if home:
        return Path(home).expanduser()
    if sys.platform == 'darwin':
        base = os.environ.get(xdg_env)
        if base:
            return Path(base).expanduser() / APP
    return default_factory()

def config_dir() -> Path:
    return _resolve('XBLOOM_CONFIG_DIR', 'XDG_CONFIG_HOME', lambda: Path(platformdirs.user_config_dir(APP, appauthor=False)))

def data_dir() -> Path:
    return _resolve('XBLOOM_DATA_DIR', 'XDG_DATA_HOME', lambda: Path(platformdirs.user_data_dir(APP, appauthor=False)))

def state_dir() -> Path:
    return _resolve('XBLOOM_STATE_DIR', 'XDG_STATE_HOME', lambda: Path(platformdirs.user_state_dir(APP, appauthor=False)))

def config_file() -> Path:
    return config_dir() / 'config.yaml'

def recipes_dir() -> Path:
    return data_dir() / 'recipes'

def history_file() -> Path:
    return state_dir() / 'history.json'

def slots_file() -> Path:
    return state_dir() / 'slots.json'

def token_file() -> Path:
    return state_dir() / 'cloud-auth.json'

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

def write_private(path: Path, text: str) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    try:
        os.chmod(path.parent, 448)
    except OSError:
        pass
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 384)
    try:
        os.write(fd, text.encode('utf-8'))
    finally:
        os.close(fd)
    try:
        os.chmod(path, 384)
    except OSError:
        pass
    return path

def tighten_if_loose(path: Path) -> str | None:
    try:
        mode = os.stat(path).st_mode
    except OSError:
        return None
    if stat.S_ISREG(mode) and mode & 63:
        try:
            os.chmod(path, 384)
        except OSError:
            pass
        return f'{path} was accessible by other users (mode {stat.S_IMODE(mode):o}) — tightened to 0600'
    return None
