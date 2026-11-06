from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

from .protocol import (
    RADIUS_L1,
    build_brewer_exit,
    build_brewer_mode,
    build_grinder_exit,
    build_grinder_mode,
    build_grinder_start,
    build_grinder_stop,
    build_pour_pause,
    build_pour_start,
    build_set_mode,
    build_set_pour_pattern,
    build_set_pour_radius,
    build_set_temp,
    build_tare,
    build_water_start,
    build_water_stop,
)
from .recipe import Pour, Recipe

logger = logging.getLogger(__name__)

class OrchestratorState(str, Enum):
    IDLE = "IDLE"
    STARTING = "STARTING"
    TARE = "TARE"
    PREHEAT = "PREHEAT"
    GRINDING = "GRINDING"
    AGITATING = "AGITATING"
    POURING = "POURING"
    BLOOMING = "BLOOMING"
    BYPASSING = "BYPASSING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    ERROR = "ERROR"

@dataclass
class StepProgress:
    step_index: int
    total_steps: int
    step_name: str
    radius: str
    target_water_ml: float
    current_water_ml: float
    step_time_target: float
    step_time_elapsed: float
    total_elapsed_sec: float
    state: OrchestratorState
    temp_target: float
    flow_target: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "total_steps": self.total_steps,
            "step_name": self.step_name,
            "radius": self.radius,
            "target_water_ml": round(self.target_water_ml, 1),
            "current_water_ml": round(self.current_water_ml, 1),
            "step_time_target": round(self.step_time_target, 1),
            "step_time_elapsed": round(self.step_time_elapsed, 1),
            "total_elapsed_sec": round(self.total_elapsed_sec, 1),
            "state": self.state.value,
            "temp_target": round(self.temp_target, 1),
            "flow_target": round(self.flow_target, 1),
        }

class AdvancedRecipeOrchestrator:

    def __init__(
        self,
        recipe: Recipe,
        send_frame: Callable[[bytes], Coroutine[Any, Any, None]],
        on_progress: Callable[[StepProgress], None] | None = None,
        get_live_weight: Callable[[], float] | None = None,
        default_radius: str = "L3",
    ) -> None:
        self.recipe = recipe
        self._send_frame = send_frame
        self._on_progress = on_progress
        self._get_live_weight = get_live_weight or (lambda: 0.0)
        self.default_radius = (default_radius or "L3").upper()

        self.state = OrchestratorState.IDLE
        self.current_step_index = 0
        self.total_steps = len(recipe.pours)

        self._start_time: float = 0.0
        self._step_start_time: float = 0.0
        self._step_water_dispensed: float = 0.0
        self._total_water_dispensed: float = 0.0

        self._abort_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        self._task: asyncio.Task | None = None

        self._pump_running = False
        self._pump_start_time: float = 0.0

    @property
    def is_running(self) -> bool:
        return self.state not in (
            OrchestratorState.IDLE,
            OrchestratorState.COMPLETED,
            OrchestratorState.ABORTED,
            OrchestratorState.ERROR,
        )

    def get_progress(self) -> StepProgress:
        now = time.time()
        total_elapsed = (now - self._start_time) if self._start_time > 0 else 0.0
        step_elapsed = (now - self._step_start_time) if self._step_start_time > 0 else 0.0

        if self.state == OrchestratorState.BYPASSING:
            step_name = "Bypass"
            radius = "Center"
            target_ml = float(getattr(self.recipe, "bypass_volume", 0.0) or 0.0)
            step_time_target = float(target_ml / 3.5) if target_ml > 0 else 0.0
            temp_target = float(getattr(self.recipe, "bypass_temp", 85.0) or 85.0)
            flow_target = 3.5
        elif 1 <= self.current_step_index <= self.total_steps:
            pour = self.recipe.pours[self.current_step_index - 1]
            base_label = pour.label or f"Pour {self.current_step_index}"
            if self.state == OrchestratorState.AGITATING:
                step_name = f"{base_label} (교반)"
            else:
                step_name = base_label
            radius = str(pour.radius or "L3").upper()
            target_ml = float(pour.ml)
            step_time_target = float(pour.step_time if pour.step_time > 0 else (target_ml / max(1.0, pour.flow_ml_s) + pour.pause_s))
            temp_target = float(pour.temp_c)
            flow_target = float(pour.flow_ml_s)
        else:
            step_name = "Ready" if self.current_step_index == 0 else "Done"
            radius = "L3"
            target_ml = 0.0
            step_time_target = 0.0
            temp_target = float(self.recipe.pours[0].temp_c) if self.recipe.pours else 93.0
            flow_target = 3.0

        return StepProgress(
            step_index=self.current_step_index,
            total_steps=self.total_steps,
            step_name=step_name,
            radius=radius,
            target_water_ml=target_ml,
            current_water_ml=self._step_water_dispensed,
            step_time_target=step_time_target,
            step_time_elapsed=step_elapsed,
            total_elapsed_sec=total_elapsed,
            state=self.state,
            temp_target=temp_target,
            flow_target=flow_target,
        )

    def _notify(self) -> None:
        if self._on_progress:
            try:
                self._on_progress(self.get_progress())
            except Exception as e:
                logger.error("Error in on_progress callback: %s", e)

    async def start(self) -> None:
        if self.is_running:
            raise RuntimeError("Orchestrator is already running")
        self._abort_event.clear()
        self._pause_event.set()
        self.state = OrchestratorState.STARTING
        self._start_time = time.time()
        self._notify()
        self._task = asyncio.create_task(self._run_loop())

    async def abort(self) -> None:
        logger.info("[V2 Engine] Abort requested")
        self._abort_event.set()
        self._pause_event.set()
        if self._task and not self._task.done():
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        try:
            await self._stop_pump()
            await asyncio.sleep(0.1)
            await self._send_frame(build_grinder_exit())
            await asyncio.sleep(0.1)
            await self._send_frame(build_set_pour_radius(self.default_radius))
            await asyncio.sleep(0.1)
            await self._send_frame(build_brewer_exit())
        except Exception as e:
            logger.error("Error sending emergency stop frames: %s", e)
        self.state = OrchestratorState.ABORTED
        self._notify()

    def pause(self) -> None:
        if self.is_running and self._pause_event.is_set():
            self._pause_event.clear()
            self.state = OrchestratorState.PAUSED
            self._notify()

    def resume(self) -> None:
        if not self._pause_event.is_set():
            self._pause_event.set()
            self.state = OrchestratorState.POURING
            self._notify()

    async def _start_pump(self, volume_ml: float, flow_rate: float, temp_c: float, pattern: Any) -> None:
        await self._send_frame(build_water_start(
            volume_ml=volume_ml,
            flow_rate=flow_rate,
            temp_c=temp_c,
            pattern=pattern,
        ))
        self._pump_running = True
        self._pump_start_time = time.time()

    async def _stop_pump(self) -> None:
        await self._send_frame(build_water_stop())
        self._pump_running = False

    async def _check_pause_and_abort(self) -> bool:
        if self._abort_event.is_set():
            return True
        if not self._pause_event.is_set():
            paused_at = time.time()
            if self._pump_running:
                await self._send_frame(build_pour_pause())
            await self._pause_event.wait()
            if self._abort_event.is_set():
                return True
            if self._pump_running:
                await self._send_frame(build_pour_start())
                self._pump_start_time += time.time() - paused_at
        return False

    async def _run_loop(self) -> None:
        logger.info("[V2 Engine] Starting advanced brew sequence for '%s'", self.recipe.name)
        self.state = OrchestratorState.STARTING
        self._start_time = time.time()
        self._notify()

        try:
            logger.info("[V2 Engine] (0/4) Ensuring PRO Mode (0x2CF7)...")
            await self._send_frame(build_set_mode(pro=True))
            await asyncio.sleep(0.3)
            if await self._check_pause_and_abort():
                return

            self.state = OrchestratorState.TARE
            self._notify()
            logger.info("[V2 Engine] (1/4) Sending 0x2134 Tare...")
            await self._send_frame(build_tare())
            await asyncio.sleep(0.4)
            if await self._check_pause_and_abort():
                return

            if getattr(self.recipe, "auto_grind", False) and int(self.recipe.grind) > 0:
                self.state = OrchestratorState.GRINDING
                self._notify()
                rpm = int(getattr(self.recipe, "grind_rpm", 80) or 80)
                grind_size = int(getattr(self.recipe, "grind", 50) or 50)
                logger.info("[V2 Engine] (2/4) Aligning cradle and starting grinder at %d RPM (size %d)...", rpm, grind_size)
                await self._send_frame(build_grinder_mode(grind_size=grind_size, rpm=rpm))
                await asyncio.sleep(0.8)
                await self._send_frame(build_grinder_start(rpm))
                grind_duration = max(5.0, float(self.recipe.dose_g) * 0.8)
                grind_start = time.time()
                while time.time() - grind_start < grind_duration:
                    if await self._check_pause_and_abort():
                        await self._send_frame(build_grinder_stop())
                        await self._send_frame(build_grinder_exit())
                        return
                    await asyncio.sleep(0.2)
                await self._send_frame(build_grinder_stop())
                await asyncio.sleep(0.3)
                await self._send_frame(build_grinder_exit())
                await asyncio.sleep(0.8)

            logger.info("[V2 Engine] (3/4) Entering Dispense Session (0x1F47 进入浇水页面)...")
            first_pour = self.recipe.pours[0]
            await self._send_frame(build_brewer_mode(first_pour.pattern, first_pour.temp_c))
            await asyncio.sleep(0.4)
            if await self._check_pause_and_abort():
                return

            self.state = OrchestratorState.PREHEAT
            init_temp = float(first_pour.temp_c)
            logger.info("[V2 Engine] (4/4) Sending 0x119E target (%.1f C)...", init_temp)
            await self._send_frame(build_set_temp(init_temp))
            await asyncio.sleep(0.4)
            if await self._check_pause_and_abort():
                return

            for idx, pour in enumerate(self.recipe.pours, start=1):
                self.current_step_index = idx
                self._step_start_time = time.time()
                self._step_water_dispensed = 0.0
                target_ml = float(pour.ml)
                flow_rate = float(pour.flow_ml_s or 3.0)
                step_radius = str(pour.radius or "L3")
                step_time_target = float(pour.step_time if pour.step_time > 0 else (target_ml / flow_rate + pour.pause_s))

                logger.info(
                    "[V2 Engine] Step %d/%d (%s): Target %.1f ml @ %.1f ml/s, Radius %s, Total Step Time %.1fs",
                    idx, self.total_steps, pour.label or "Pour", target_ml, flow_rate, step_radius, step_time_target
                )

                vibe_before = bool(getattr(pour, "agitation_before", False))
                if vibe_before:
                    logger.info("[V2 Engine] Step %d: Bed leveling agitation (before pour)...", idx)
                    self.state = OrchestratorState.AGITATING
                    self._notify()
                    agit_before_duration = min(4.0, max(0.5, step_time_target * 0.2)) if step_time_target < 5.0 else 4.0
                    agit_start = time.time()
                    while (time.time() - agit_start) < agit_before_duration:
                        if await self._check_pause_and_abort():
                            return
                        await asyncio.sleep(0.1)

                await self._send_frame(build_set_pour_radius(step_radius))
                await asyncio.sleep(0.2)

                await self._send_frame(build_set_pour_pattern(pour.pattern))
                await asyncio.sleep(0.1)

                await self._send_frame(build_set_temp(pour.temp_c))
                await asyncio.sleep(0.1)

                self.state = OrchestratorState.POURING
                self._notify()
                await self._start_pump(target_ml, flow_rate, pour.temp_c, pour.pattern)

                initial_weight = self._get_live_weight()
                while self._step_water_dispensed < target_ml:
                    if await self._check_pause_and_abort():
                        return
                    await asyncio.sleep(0.1)
                    live_w = self._get_live_weight()
                    if live_w > initial_weight:
                        self._step_water_dispensed = max(0.0, live_w - initial_weight)
                    else:
                        simulated = (time.time() - self._pump_start_time) * flow_rate
                        self._step_water_dispensed = min(target_ml, simulated)
                    self._notify()

                logger.info("[V2 Engine] Step %d: Target %.1f ml reached -> Stopping pump", idx, target_ml)
                await self._stop_pump()

                vibe_after = bool(getattr(pour, "agitation_after", False) or getattr(pour, "agitation", False))
                if vibe_after:
                    logger.info("[V2 Engine] Step %d: Slurry turbulence agitation (after pour)...", idx)
                    self.state = OrchestratorState.AGITATING
                    self._notify()
                    agit_after_duration = min(4.0, max(0.5, step_time_target * 0.2)) if step_time_target < 5.0 else 4.0
                    agit_start = time.time()
                    while (time.time() - agit_start) < agit_after_duration:
                        if await self._check_pause_and_abort():
                            return
                        await asyncio.sleep(0.1)

                self.state = OrchestratorState.BLOOMING
                while (time.time() - self._step_start_time) < step_time_target:
                    if await self._check_pause_and_abort():
                        return
                    await asyncio.sleep(0.2)
                    self._notify()

            bp_enabled = bool(getattr(self.recipe, "bypass_enabled", False))
            bp_volume = float(getattr(self.recipe, "bypass_volume", 0.0) or 0.0)
            bp_temp = float(getattr(self.recipe, "bypass_temp", 0.0) or 0.0)
            if bp_temp <= 0.0 and self.recipe.pours:
                bp_temp = float(self.recipe.pours[-1].temp_c)
            if bp_temp <= 0.0:
                bp_temp = 85.0

            if bp_enabled and bp_volume > 0.0:
                logger.info("[V2 Engine] (Bypass Stage) Swinging arm away, locking pattern to Center, and dispensing %.1f ml @ %.1f C", bp_volume, bp_temp)
                self.state = OrchestratorState.BYPASSING
                self._step_start_time = time.time()
                self._step_water_dispensed = 0.0
                self._notify()

                logger.info("[V2 Engine] Swinging dripper arm away for direct cup bypass dilution (0x1F46)...")
                await self._send_frame(build_grinder_mode())
                await asyncio.sleep(0.8)
                if await self._check_pause_and_abort():
                    await self._send_frame(build_grinder_exit())
                    return

                logger.info("[V2 Engine] Fixing pour pattern to CENTER (0x1F50) for direct vertical stream...")
                await self._send_frame(build_set_pour_pattern("center"))
                await asyncio.sleep(0.2)

                await self._send_frame(build_set_temp(bp_temp))
                await asyncio.sleep(0.2)

                bp_flow = 3.5
                await self._start_pump(bp_volume, bp_flow, bp_temp, "center")

                initial_bp_weight = self._get_live_weight()
                while self._step_water_dispensed < bp_volume:
                    if await self._check_pause_and_abort():
                        await self._stop_pump()
                        await self._send_frame(build_grinder_exit())
                        return
                    await asyncio.sleep(0.1)
                    live_w = self._get_live_weight()
                    if live_w > initial_bp_weight:
                        self._step_water_dispensed = live_w - initial_bp_weight
                    else:
                        simulated = (time.time() - self._pump_start_time) * bp_flow
                        self._step_water_dispensed = min(bp_volume, simulated)
                    self._notify()

                logger.info("[V2 Engine] Bypass target %.1f ml reached -> Stopping pump", bp_volume)
                await self._stop_pump()
                await asyncio.sleep(0.3)

                logger.info("[V2 Engine] Returning dripper arm to home position (0x1F4C)...")
                await self._send_frame(build_grinder_exit())
                await asyncio.sleep(0.6)

            logger.info("[V2 Engine] All steps completed! Restoring default radius %s & exiting brewer.", self.default_radius)
            try:
                await self._send_frame(build_set_pour_radius(self.default_radius))
                await asyncio.sleep(0.1)
            except Exception:
                pass
            await self._send_frame(build_brewer_exit())
            self.state = OrchestratorState.COMPLETED
            self._notify()

        except Exception as e:
            logger.exception("[V2 Engine] Unexpected error in brew sequence: %s", e)
            self.state = OrchestratorState.ERROR
            try:
                await self._stop_pump()
                await self._send_frame(build_brewer_exit())
            except Exception:
                pass
            self._notify()
