from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .protocol import PATTERN_CODES

__all__ = ["Pour", "Recipe", "RecipeError", "MODEL_PATTERN_COMBOS"]

MODEL_PATTERN_COMBOS: frozenset[tuple[str, bool]] = frozenset(PATTERN_CODES) | {("ring", True), ("center", True)}

class RecipeError(ValueError):
    pass

@dataclass
class Pour:

    ml: int
    temp_c: int
    pattern: str = "spiral"
    agitation: bool = False
    pause_s: int = 0
    rpm: int = 0
    flow_ml_s: float = 3.0
    label: str | None = None
    agitation_before: bool = False
    radius: str = "L3"
    step_time: int = 0

    def ble_omissions(self) -> list[str]:
        return []

    def to_protocol_dict(self) -> dict[str, Any]:
        after = bool(getattr(self, "agitation_after", self.agitation))
        before = bool(getattr(self, "agitation_before", False))
        return {
            "ml": self.ml,
            "temp": self.temp_c,
            "pattern": self.pattern,
            "agitation": after,
            "agitation_before": before,
            "agitation_after": after,
            "pause": self.pause_s,
            "rpm": self.rpm,
            "flow": self.flow_ml_s,
            "radius": self.radius,
            "step_time": self.step_time,
        }

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.label is not None:
            d["label"] = self.label
        d.update(
            ml=int(self.ml),
            temp_c=int(self.temp_c),
            pattern=self.pattern,
            pause_s=int(self.pause_s),
            rpm=int(self.rpm),
            flow_ml_s=float(self.flow_ml_s),
            agitation=bool(self.agitation),
            radius=str(self.radius or "L3"),
        )
        if int(self.step_time) > 0:
            d["step_time"] = int(self.step_time)
        if self.agitation_before:
            d["agitation_before"] = True
        return d

@dataclass
class Recipe:

    name: str
    dose_g: int
    grind: int
    pours: list[Pour]
    stage_temps: tuple[float, float] = (110.0, 90.0)
    ratio: float | None = None
    tail: int = 0xA0
    dripper: str | None = None
    kind: str | None = None
    water_ml: int | None = None
    hot_water_ml: int | None = None
    ice_g: int | None = None
    time: str | None = None
    note: str | None = None
    bypass_enabled: bool = False
    bypass_volume: float = 0.0
    bypass_temp: float = 85.0
    is_advanced: bool = False
    schema_version: int = 1
    grind_rpm: int = 80
    auto_grind: bool = True
    mode: str = "coffee"
    tea_type: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recipe:
        if not isinstance(data, dict):
            raise RecipeError("recipe must be a mapping")
        raw_pours = data.get("pours") if "pours" in data else data.get("steps")
        if raw_pours is None:
            raise RecipeError("recipe is missing required key 'pours'")
        if not isinstance(raw_pours, list) or not raw_pours:
            raise RecipeError("recipe 'pours' must be a non-empty list")

        pours: list[Pour] = []
        for i, rp in enumerate(raw_pours):
            if not isinstance(rp, dict):
                raise RecipeError(f"pour #{i + 1} must be a mapping")
            ml_val = rp.get("ml", rp.get("pour", rp.get("water")))
            if ml_val is None:
                raise RecipeError(f"pour #{i + 1} missing key 'ml'")
            temp_val = rp.get("temp_c", rp.get("temp"))
            if temp_val is None:
                raise RecipeError(f"pour #{i + 1} missing key 'temp_c'")

            pause_val = rp.get("pause_s", rp.get("wait", 0))
            flow_val = rp.get("flow_ml_s", rp.get("flow_rate", rp.get("flow", 3.0)))
            pat_val = str(rp.get("pattern", "spiral")).strip().lower()
            if pat_val in ("circle", "circular"):
                pat_val = "ring"

            if "rpm" in rp:
                rpm_val = int(rp["rpm"])
            else:
                rpm_val = 0 if pat_val == "center" else 80

            if "agitation" in rp:
                agit_val = bool(rp["agitation"])
            elif "agitation_after" in rp:
                agit_val = bool(rp["agitation_after"])
            else:
                agit_val = False

            pours.append(
                Pour(
                    ml=ml_val,
                    temp_c=temp_val,
                    pattern=pat_val,
                    agitation=agit_val,
                    pause_s=pause_val,
                    rpm=rpm_val,
                    flow_ml_s=flow_val,
                    label=rp.get("label"),
                    agitation_before=bool(rp.get("agitation_before", False)),
                    radius=str(rp.get("radius", "L3")),
                    step_time=int(rp.get("step_time", 0)),
                )
            )

        stage_temps = data.get("stage_temps", [110.0, 90.0])
        if not isinstance(stage_temps, (list, tuple)) or len(stage_temps) != 2:
            raise RecipeError("'stage_temps' must be a 2-element list [temp1, temp2]")

        dose_val = data.get("dose_g", data.get("dose"))
        if dose_val is None:
            raise RecipeError("recipe is missing required key 'dose_g'")

        grind_val = data.get("grind", data.get("grind_size"))
        if grind_val is None:
            if str(data.get("mode", "coffee")) == "tea":
                grind_val = 0
            else:
                raise RecipeError("recipe is missing required key 'grind'")

        is_adv = bool(data.get("is_advanced", False) or data.get("schema_version") == 2)
        schema_v = int(data.get("schema_version", 2 if is_adv else 1))

        recipe = cls(
            name=str(data.get("name", "Unnamed")),
            dose_g=dose_val,
            grind=grind_val,
            pours=pours,
            stage_temps=(float(stage_temps[0]), float(stage_temps[1])),
            ratio=data.get("ratio"),
            tail=data.get("tail", 0xA0),
            dripper=data.get("dripper"),
            kind=data.get("kind"),
            water_ml=data.get("water_ml"),
            hot_water_ml=data.get("hot_water_ml"),
            ice_g=data.get("ice_g"),
            time=data.get("time"),
            note=data.get("note"),
            bypass_enabled=bool(data.get("bypass_enabled", False)) and float(data.get("bypass_volume", 0.0) or 0.0) > 0,
            bypass_volume=float(data.get("bypass_volume", 0.0) or 0.0) if bool(data.get("bypass_enabled", False)) else 0.0,
            bypass_temp=float(data.get("bypass_temp", 85.0) or 85.0) if bool(data.get("bypass_enabled", False)) else 85.0,
            is_advanced=is_adv,
            schema_version=schema_v,
            grind_rpm=int(data.get("grind_rpm", 80)),
            auto_grind=bool(data.get("auto_grind", True)),
            mode=str(data.get("mode", "coffee")),
            tea_type=data.get("tea_type"),
        )
        recipe.validate()
        return recipe

    @classmethod
    def from_yaml(cls, path: str | Path) -> Recipe:
        text = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        if data is None:
            raise RecipeError(f"recipe file {path} is empty")
        return cls.from_dict(data)

    @classmethod
    def from_yaml_text(cls, text: str, *, origin: str = "<text>") -> Recipe:
        data = yaml.safe_load(text)
        if data is None:
            raise RecipeError(f"recipe {origin} is empty")
        return cls.from_dict(data)

    @classmethod
    def from_source(cls, src: str | Path, *, timeout: float = 15.0) -> Recipe:
        s = str(src)
        if s.startswith(("http://", "https://")):
            from urllib.request import Request, urlopen

            req = Request(s, headers={"User-Agent": "xbloom-ble"})
            with urlopen(req, timeout=timeout) as resp:
                text = resp.read(1_000_000).decode("utf-8")
            return cls.from_yaml_text(text, origin=s)
        return cls.from_yaml(s)

    def validate(self) -> None:
        errors: list[str] = []

        is_tea = (getattr(self, "mode", "coffee") == "tea")
        if int(self.dose_g) < 1:
            errors.append(f"dose_g {self.dose_g} must be at least 1 g")
        if int(self.grind) != 0 and not (1 <= int(self.grind) <= 80):
            errors.append(
                f"grind {self.grind} out of range (1–80; the grinder has 80 micro-steps — "
                f"or 0 for no-grind / pre-ground)"
            )

        for label, t in zip(("stage temp1", "stage temp2"), self.stage_temps, strict=False):
            if not (40 <= float(t) <= 130):
                errors.append(f"{label} {t}°C out of range (40–130°C)")

        min_pours = 1 if is_tea else 2
        if len(self.pours) < min_pours:
            if is_tea:
                errors.append("recipe needs at least 1 pour")
            else:
                errors.append("recipe needs at least a bloom pour and a first pour (≥2 pours)")

        total_ml = 0
        for i, p in enumerate(self.pours, start=1):
            if (p.pattern, bool(p.agitation)) not in MODEL_PATTERN_COMBOS:
                valid = sorted({pat for pat, _ in MODEL_PATTERN_COMBOS})
                errors.append(
                    f"pour #{i}: pattern/agitation ({p.pattern!r}, {p.agitation}) "
                    f"not in known set {valid}"
                )
            if not (1 <= int(p.ml) <= 4000):
                errors.append(f"pour #{i}: ml {p.ml} out of range (1–4000)")
            if int(p.temp_c) not in (0, 100) and not (40 <= int(p.temp_c) <= 95):
                errors.append(f"pour #{i}: temp_c {p.temp_c} out of range (0, 40–95 or 100°C)")
            if getattr(self, "is_advanced", False):
                if int(p.rpm) != 0 and not (60 <= int(p.rpm) <= 120):
                    errors.append(f"pour #{i}: rpm {p.rpm} out of range (0 or 60–120)")
            else:
                if p.pattern == "center":
                    if int(p.rpm) != 0 and not (60 <= int(p.rpm) <= 120):
                        errors.append(
                            f"pour #{i}: rpm {p.rpm} out of range (0 for a center pour, else 60–120)"
                        )
                else:
                    if not (60 <= int(p.rpm) <= 120):
                        errors.append(f"pour #{i}: rpm {p.rpm} out of range (60–120)")
            if not (3.0 <= float(p.flow_ml_s) <= 3.5):
                errors.append(f"pour #{i}: flow_ml_s {p.flow_ml_s} out of range (3.0–3.5)")
            if getattr(self, "is_advanced", False):
                if int(p.step_time) < 0:
                    errors.append(f"pour #{i}: step_time {p.step_time} must be non-negative")
                r_norm = str(p.radius).strip().upper()
                if r_norm not in ("L1", "L2", "L3", "L4", "L5", "0", "1", "2", "3", "4"):
                    errors.append(f"pour #{i}: radius {p.radius} must be one of L1..L5")
            else:
                if not (0 <= int(p.pause_s) <= 255):
                    errors.append(f"pour #{i}: pause_s {p.pause_s} out of range (0–255)")
            total_ml += int(p.ml)

        if not is_tea and self.ratio is not None:
            expected = round(float(self.dose_g) * float(self.ratio))
            if total_ml != expected:
                errors.append(
                    f"Σpours = {total_ml} ml but dose_g*ratio = "
                    f"{self.dose_g}*{self.ratio} = {expected} ml"
                )

        for label, v in (("water_ml", self.water_ml), ("hot_water_ml", self.hot_water_ml),
                         ("ice_g", self.ice_g)):
            if v is not None and (not isinstance(v, (int, float)) or v < 0):
                errors.append(f"{label} must be a non-negative number, got {v!r}")

        if errors:
            raise RecipeError("; ".join(errors))

    def ble_warnings(self) -> list[str]:
        out: list[str] = []
        for i, p in enumerate(self.pours, start=1):
            omitted = p.ble_omissions()
            if omitted:
                out.append(
                    f"pour #{i}: {' and '.join(omitted)} omitted from the BLE load "
                    f"(kept in the recipe/cloud); {p.pattern} pattern is sent"
                )
        return out

    @property
    def no_grind(self) -> bool:
        return int(self.grind) == 0

    @property
    def total_water_ml(self) -> int:
        return sum(int(p.ml) for p in self.pours)

    @property
    def effective_ratio(self) -> float:
        if self.ratio is not None:
            return float(self.ratio)
        return round(self.total_water_ml / float(self.dose_g), 1) if self.dose_g else 0.0

    def to_protocol_dict(self) -> dict[str, Any]:
        d = {
            "dose": int(self.dose_g),
            "grind": int(self.grind),
            "stage_temps": tuple(self.stage_temps),
            "pours": [p.to_protocol_dict() for p in self.pours],
        }
        bp_active = bool(getattr(self, "bypass_enabled", False)) and float(getattr(self, "bypass_volume", 0.0) or 0.0) > 0
        if bp_active:
            d["bypass_enabled"] = True
            d["bypass_volume"] = float(getattr(self, "bypass_volume", 0.0) or 0.0)
            d["bypass_temp"] = float(getattr(self, "bypass_temp", 85.0) or 85.0)
        return d

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "dose_g": int(self.dose_g),
                             "grind": int(self.grind)}
        if getattr(self, "mode", "coffee") == "tea":
            d["mode"] = "tea"
            if getattr(self, "tea_type", None):
                d["tea_type"] = self.tea_type
        if getattr(self, "is_advanced", False):
            d["is_advanced"] = True
            d["schema_version"] = 2
            d["grind_rpm"] = int(getattr(self, "grind_rpm", 80))
            d["auto_grind"] = bool(getattr(self, "auto_grind", True))
        if self.ratio is not None:
            d["ratio"] = self.ratio
        d["stage_temps"] = [float(self.stage_temps[0]), float(self.stage_temps[1])]
        for key in ("kind", "dripper", "water_ml", "hot_water_ml", "ice_g", "time", "note"):
            val = getattr(self, key)
            if val is not None:
                d[key] = val
        bp_active = bool(getattr(self, "bypass_enabled", False)) and float(getattr(self, "bypass_volume", 0.0) or 0.0) > 0
        if bp_active:
            d["bypass_enabled"] = True
            d["bypass_volume"] = float(getattr(self, "bypass_volume", 0.0) or 0.0)
            d["bypass_temp"] = float(getattr(self, "bypass_temp", 85.0) or 85.0)
        d["pours"] = [p.to_dict() for p in self.pours]
        return d

