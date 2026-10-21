from __future__ import annotations
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import yaml
from . import paths
_KNOWN = ('address', 'recipes_dir', 'cloud_email', 'scale_on', 'auto_connect')

@dataclass
class Config:
    address: str = ''
    recipes_dir: str = ''
    cloud_email: str = ''
    scale_on: bool = True
    auto_connect: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def resolved_recipes_dir(self) -> Path:
        return Path(self.recipes_dir).expanduser() if self.recipes_dir else paths.recipes_dir()

def load(path: Path | None=None) -> Config:
    path = Path(path) if path is not None else paths.config_file()
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except (FileNotFoundError, OSError, yaml.YAMLError):
        return Config()
    if not isinstance(data, dict):
        return Config()
    known = {k: data[k] for k in _KNOWN if k in data}
    extra = {k: v for k, v in data.items() if k not in _KNOWN}
    return Config(**known, extra=extra)

def save(cfg: Config, path: Path | None=None) -> Path:
    path = Path(path) if path is not None else paths.config_file()
    paths.ensure_dir(path.parent)
    body = {k: v for k, v in asdict(cfg).items() if k != 'extra'}
    body.update(cfg.extra)
    path.write_text(yaml.safe_dump(body, sort_keys=False, allow_unicode=True))
    return path

def exists(path: Path | None=None) -> bool:
    return (Path(path) if path is not None else paths.config_file()).exists()
