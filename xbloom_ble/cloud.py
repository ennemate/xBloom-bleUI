from __future__ import annotations
import base64
import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote
from urllib.request import Request, urlopen
from . import paths
if TYPE_CHECKING:
    from .recipe import Pour, Recipe
__all__ = ['XBloomCloud', 'XBloomCloudError', 'recipe_to_cloud', 'recipe_from_cloud', 'parse_share_id', 'rsa_encrypt', 'encrypt_form', 'BASE_URL', 'CUP_TYPES', 'PATTERN_CODES', 'MANAGED_PREFIX']
MANAGED_PREFIX = 'AUTO '

def _is_managed(name: object) -> bool:
    return isinstance(name, str) and name.startswith(MANAGED_PREFIX)
BASE_URL = 'https://client-api.xbloom.com/'
SKEY = 'testskey'
RSA_PUBLIC_KEY_B64 = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC4LF40GZ72SdhMyl765K/i4nY5CPcHz2Q1IKWKZ9S79xmK7G8pUhbVf4EZLvnNF1+9IvOFQUKV5Z7ZNNviqSpnql9tAT+8+J/He0R7pcirvVSxgdr2i9V/C/gmqAEZ5qVTzRnd3uWdFoKzPdEBxP0IporJ1VBbCv90yBSOhVxO+QIDAQAB'
RSA_KEY_BYTES = 128
RSA_MAX_PLAIN_BLOCK = 117
INTERFACE_VERSION = 20240918
PUBLIC_INTERFACE_VERSION = 19700101
EP_LOGIN = 'tMemberLogin.thtml'
EP_RECIPE_ADD = 'tuRecipeAdd.tuhtml'
EP_RECIPE_UPDATE = 'tuRecipeUpdate.tuhtml'
EP_RECIPE_DELETE = 'tuRecipeDelete.tuhtml'
EP_RECIPE_LIST = 'tuMyTeaRecipeCreated.tuhtml'
EP_RECIPE_PUBLIC = 'RecipeDetail.html'
CUP_TYPES = {'xpod': 1, 'xdripper': 2, 'other': 3, 'tea': 4}
PATTERN_CODES = {'center': 1, 'circular': 2, 'ring': 3, 'spiral': 2}
CLOUD_TRUE = 1
CLOUD_FALSE = 2

def _cloud_bool(value: bool) -> int:
    return CLOUD_TRUE if value else CLOUD_FALSE
LEGACY_AUTH_PATH = Path.home() / '.config' / 'xbloom-ble' / 'cloud-auth.json'

class XBloomCloudError(RuntimeError):
    pass

def _require_cryptography():
    try:
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.serialization import load_der_public_key
    except ModuleNotFoundError as exc:
        raise XBloomCloudError('The cloud client needs the \'cryptography\' package. Install it with:\n    pip install "xbloom-ble[cloud]"') from exc
    return (load_der_public_key, padding)

def _load_rsa_public_key():
    load_der_public_key, _ = _require_cryptography()
    der = base64.b64decode(RSA_PUBLIC_KEY_B64)
    return load_der_public_key(der)

def rsa_encrypt(plaintext: bytes) -> bytes:
    _, padding = _require_cryptography()
    pub_key = _load_rsa_public_key()
    num_blocks = max(1, math.ceil(len(plaintext) / RSA_MAX_PLAIN_BLOCK))
    ciphertext = bytearray()
    for i in range(num_blocks):
        start = i * RSA_MAX_PLAIN_BLOCK
        end = min(start + RSA_MAX_PLAIN_BLOCK, len(plaintext))
        block = plaintext[start:end]
        ciphertext.extend(pub_key.encrypt(block, padding.PKCS1v15()))
    return bytes(ciphertext)

def encrypt_form(form: dict[str, Any]) -> str:
    json_bytes = json.dumps(form, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return base64.b64encode(rsa_encrypt(json_bytes)).decode('ascii')

def _pour_to_cloud(pour: Pour, index: int) -> dict[str, Any]:
    pattern_code = PATTERN_CODES.get(pour.pattern)
    if pattern_code is None:
        raise XBloomCloudError(f'pour #{index + 1}: unknown pattern {pour.pattern!r} (known: {sorted(PATTERN_CODES)})')
    return {'theName': f'Pour{index + 1}' if index else 'Bloom', 'volume': float(pour.ml), 'temperature': float(pour.temp_c), 'flowRate': float(pour.flow_ml_s), 'pattern': pattern_code, 'pausing': int(pour.pause_s), 'isEnableVibrationBefore': _cloud_bool(bool(getattr(pour, 'agitation_before', False))), 'isEnableVibrationAfter': _cloud_bool(bool(getattr(pour, 'agitation_after', getattr(pour, 'agitation', False))))}

def recipe_to_cloud(recipe: Recipe, *, cup_type: str | int='xdripper', adapted_model: int=1, the_color: str='#C9D5B8', bypass_temp: float=85.0, bypass_volume: float=0.0) -> dict[str, Any]:
    if isinstance(cup_type, str):
        code = CUP_TYPES.get(cup_type.lower())
        if code is None:
            raise XBloomCloudError(f'unknown cup_type {cup_type!r} (known: {sorted(CUP_TYPES)})')
        cup_type_code = code
    else:
        cup_type_code = int(cup_type)
    pour_list = [_pour_to_cloud(p, i) for i, p in enumerate(recipe.pours)]
    first_rpm = int(recipe.pours[0].rpm) if recipe.pours else 0
    bypass_on = float(bypass_volume) > 0
    is_no_grind = bool(getattr(recipe, 'no_grind', False) or not getattr(recipe, 'grind_enabled', True) or getattr(recipe, 'grind', 1) == 0)
    raw_rpm = getattr(recipe, 'grind_rpm', None) or getattr(recipe, 'rpm', None)
    if raw_rpm is not None and int(raw_rpm) >= 60:
        grind_rpm = int(raw_rpm)
    elif first_rpm >= 60:
        grind_rpm = first_rpm
    else:
        grind_rpm = 60
    out = {'theName': recipe.name, 'dose': float(recipe.dose_g), 'grandWater': float(recipe.effective_ratio), 'grinderSize': float(recipe.grind), 'rpm': grind_rpm, 'cupType': cup_type_code, 'adaptedModel': int(adapted_model), 'isEnableBypassWater': _cloud_bool(bypass_on), 'isSetGrinderSize': _cloud_bool(not is_no_grind), 'theColor': the_color, 'theSubsetId': 0, 'bypassTemp': float(bypass_temp), 'bypassVolume': float(bypass_volume), 'subSetType': 2, 'appPlace': [4], 'createTimeStamp': int(time.time() * 1000), 'isShortcuts': CLOUD_FALSE, 'pourDataJSONStr': json.dumps(pour_list, ensure_ascii=False, separators=(',', ':'))}
    if is_no_grind:
        out.pop('grinderSize', None)
    return out

def parse_share_id(share_url_or_id: str) -> str:
    s = share_url_or_id.strip()
    if 'id=' in s:
        s = s.split('id=')[-1].split('&')[0]
    return unquote(s)

def recipe_from_cloud(payload: dict[str, Any]) -> Recipe:
    from .recipe import Recipe
    rv = payload.get('recipeVo', payload)
    raw = rv.get('pourDataJSONStr')
    pours_src = json.loads(raw) if isinstance(raw, str) else rv.get('pourList') or []
    rpm = min(120, max(60, int(rv.get('rpm') or 100)))
    pours = []
    for p in pours_src:
        pattern = 'center' if int(p.get('pattern', 2)) == 1 else 'spiral'
        pours.append({'ml': int(round(float(p.get('volume', 0)))), 'temp_c': int(round(float(p.get('temperature', 92)))), 'pattern': pattern, 'pause_s': int(p.get('pausing', 5)), 'rpm': 0 if pattern == 'center' else rpm, 'flow_ml_s': float(p.get('flowRate', 3.0)), 'agitation': int(p.get('isEnableVibrationAfter', CLOUD_FALSE)) == CLOUD_TRUE})
    no_grind = rv.get('isSetGrinderSize') == CLOUD_FALSE or rv.get('grinderSize') in (None, 0)
    return Recipe.from_dict({'name': str(rv.get('theName') or 'Imported recipe'), 'dose_g': int(round(float(rv.get('dose', 16)))), 'grind': 0 if no_grind else int(round(float(rv.get('grinderSize')))), 'pours': pours})

@dataclass
class XBloomCloud:
    email: str | None = None
    password: str | None = None
    auth_path: Path | None = None
    timeout: float = 15.0
    token: str = ''
    member_id: int = 0

    def __post_init__(self) -> None:
        self.email = self.email or os.environ.get('XBLOOM_EMAIL')
        self.password = self.password or os.environ.get('XBLOOM_PASSWORD')
        if self.auth_path is None:
            env = os.environ.get('XBLOOM_CLOUD_AUTH')
            self.auth_path = Path(env) if env else paths.token_file()
        if not self.token or not self.member_id:
            self._load_cached_auth()

    def _load_cached_auth(self) -> None:
        candidates = [Path(self.auth_path)]
        if Path(self.auth_path) != LEGACY_AUTH_PATH:
            candidates.append(LEGACY_AUTH_PATH)
        for candidate in candidates:
            try:
                data = json.loads(candidate.read_text(encoding='utf-8'))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                continue
            self.token = self.token or str(data.get('token', ''))
            self.member_id = self.member_id or int(data.get('member_id', 0) or 0)
            return

    def _save_cached_auth(self) -> None:
        paths.write_private(Path(self.auth_path), json.dumps({'member_id': self.member_id, 'token': self.token}))

    def _base_form(self) -> dict[str, Any]:
        return {'interfaceVersion': INTERFACE_VERSION, 'skey': SKEY, 'phoneType': 'Android', 'memberId': self.member_id, 'clientType': 2, 'languageType': 1, 'token': self.token}

    def _require_auth(self) -> None:
        if not self.member_id or not self.token:
            raise XBloomCloudError('not authenticated — call login() first (or set XBLOOM_EMAIL / XBLOOM_PASSWORD and a valid cached token)')

    def _post(self, endpoint: str, body: str | dict[str, Any], *, encrypted: bool) -> dict[str, Any]:
        url = BASE_URL + endpoint
        if encrypted:
            assert isinstance(body, str)
            data = body.encode('utf-8')
        else:
            data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        req = Request(url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json; charset=utf-8')
        req.add_header('Accept', 'application/json, text/plain, */*')
        if not encrypted:
            req.add_header('Referer', 'https://share-h5.xbloom.com/')
        with urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))

    @staticmethod
    def _check(resp: dict[str, Any], what: str) -> dict[str, Any]:
        if resp.get('result') != 'success':
            raise XBloomCloudError(f"{what} failed: {resp.get('info', resp)}")
        return resp

    def login(self, email: str | None=None, password: str | None=None) -> dict[str, Any]:
        email = email or self.email
        password = password or self.password
        if not email or not password:
            raise XBloomCloudError('login needs an email and password (args, constructor, or XBLOOM_EMAIL / XBLOOM_PASSWORD env vars)')
        form = {'interfaceVersion': INTERFACE_VERSION, 'skey': SKEY, 'phoneType': 'Android', 'clientType': 2, 'languageType': 1, 'email': email, 'password': password, 'jpushId': ''}
        resp = self._post(EP_LOGIN, encrypt_form(form), encrypted=True)
        self._check(resp, 'login')
        member = resp.get('member', {})
        self.member_id = int(member.get('tableId', 0) or 0)
        self.token = str(resp.get('token', ''))
        self._save_cached_auth()
        return resp

    def add_recipe(self, recipe: Recipe | dict[str, Any], **map_kwargs: Any) -> dict[str, Any]:
        self._require_auth()
        cloud_recipe = self._as_cloud_dict(recipe, map_kwargs)
        form = self._base_form()
        form.update(cloud_recipe)
        resp = self._post(EP_RECIPE_ADD, encrypt_form(form), encrypted=True)
        return self._check(resp, 'add_recipe')

    def update_recipe(self, table_id: int | str, recipe: Recipe | dict[str, Any], *, require_managed: bool=True, **map_kwargs: Any) -> dict[str, Any]:
        self._require_auth()
        if require_managed:
            self._assert_managed(table_id)
        cloud_recipe = self._as_cloud_dict(recipe, map_kwargs)
        form = self._base_form()
        form.update(cloud_recipe)
        form['tableId'] = table_id
        resp = self._post(EP_RECIPE_UPDATE, encrypt_form(form), encrypted=True)
        return self._check(resp, 'update_recipe')

    def delete_recipe(self, table_id: int | str, *, require_managed: bool=True) -> dict[str, Any]:
        self._require_auth()
        if require_managed:
            self._assert_managed(table_id)
        form = self._base_form()
        form['tableId'] = table_id
        resp = self._post(EP_RECIPE_DELETE, encrypt_form(form), encrypted=True)
        return self._check(resp, 'delete_recipe')

    def recipe_items(self) -> list[dict[str, Any]]:
        self._require_auth()
        return list(self.list_recipes(adapted_model=0).get('list', []) or [])

    def managed_recipes(self) -> list[dict[str, Any]]:
        return [r for r in self.recipe_items() if _is_managed(r.get('theName', ''))]

    def _assert_managed(self, table_id: int | str) -> None:
        for r in self.recipe_items():
            if str(r.get('tableId')) == str(table_id):
                name = str(r.get('theName', ''))
                if not _is_managed(name):
                    raise XBloomCloudError(f"refusing to modify {name!r}: only recipes named '{MANAGED_PREFIX}…' are managed by this tool — your own recipes are never changed.")
                return
        raise XBloomCloudError(f'recipe tableId={table_id} not found in this account')

    def sync_recipe(self, recipe: Recipe | dict[str, Any], *, prefix: str=MANAGED_PREFIX, **map_kwargs: Any) -> tuple[dict[str, Any], str]:
        self._require_auth()
        cloud = dict(self._as_cloud_dict(recipe, map_kwargs))
        name = str(cloud.get('theName', '')).strip()
        if prefix and (not name.startswith(prefix)):
            name = prefix + name
        cloud['theName'] = name
        existing = next((r for r in self.recipe_items() if str(r.get('theName', '')) == name), None)
        if existing is not None:
            resp = self.update_recipe(existing['tableId'], cloud, require_managed=False)
            return (resp, 'updated')
        return (self.add_recipe(cloud), 'added')

    def prune_managed(self, keep_names: list[str] | set[str]) -> list[str]:
        keep = {n if _is_managed(n) else MANAGED_PREFIX + n for n in keep_names}
        deleted: list[str] = []
        for r in self.managed_recipes():
            name = str(r.get('theName', ''))
            if name not in keep:
                self.delete_recipe(r['tableId'], require_managed=False)
                deleted.append(name)
        return deleted

    def list_recipes(self, adapted_model: int=1) -> dict[str, Any]:
        self._require_auth()
        form = self._base_form()
        form['pageNumber'] = 1
        form['countPerPage'] = 100
        if adapted_model:
            form['adaptedModel'] = adapted_model
        resp = self._post(EP_RECIPE_LIST, encrypt_form(form), encrypted=True)
        return self._check(resp, 'list_recipes')

    def fetch_public(self, share_id_or_url: str) -> dict[str, Any]:
        body = {'tableIdOfRSA': parse_share_id(share_id_or_url), 'interfaceVersion': PUBLIC_INTERFACE_VERSION, 'skey': SKEY}
        resp = self._post(EP_RECIPE_PUBLIC, body, encrypted=False)
        return self._check(resp, 'fetch_public')

    @staticmethod
    def _as_cloud_dict(recipe: Recipe | dict[str, Any], map_kwargs: dict[str, Any]) -> dict[str, Any]:
        if isinstance(recipe, dict):
            return recipe
        return recipe_to_cloud(recipe, **map_kwargs)
