# digestive_simulation_fixed.py
# Clean, modular, professional code with improved Rich Live behavior,
# single "editable" console panel (Live updated in-place), loading/progress bar,
# hormone state machine fixed and updated during digestion, and more robust
# stage tick tracking. Preserves original structure as much as possible; changes
# are clearly marked and minimal where feasible.
# GPT 4o, LloydLewis, SezaRSaeed
from dataclasses import dataclass
import time
import sys
import threading
import queue
from typing import Dict, Optional, List

# Optional rich UI
try:
    from rich.live import Live
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn, TimeElapsedColumn
    from rich.align import Align
    from rich.layout import Layout
    from rich.box import SIMPLE
except Exception:
    Console = Live = Table = Panel = Progress = Align = Layout = None

# Shorter timers for faster demo runs
TIME_MAP = {
    "Stomach": 6,          # ~ reduced from 12
    "Duodenum": 2,
    "SmallIntestine": 18,  # ~ reduced from 36
    "LargeIntestine": 36   # ~ reduced from 72
}

# ---- Data structures ----
@dataclass
class Microbiome:
    good_bacteria: float = 70.0
    bad_bacteria: float = 30.0
    fiber_intake: float = 0.0
    antibiotic: bool = False

    def tick(self):
        # fiber supports good bacteria
        if self.fiber_intake > 0:
            self.good_bacteria = min(100.0, self.good_bacteria + 1.2)
            self.bad_bacteria = max(0.0, self.bad_bacteria - 0.6)
        # antibiotics harm microbiome
        if self.antibiotic:
            self.good_bacteria = max(0.0, self.good_bacteria - 5.0)
            self.bad_bacteria = max(0.0, self.bad_bacteria - 2.0)
        # re-normalize
        total = self.good_bacteria + self.bad_bacteria
        if total > 0:
            self.good_bacteria = (self.good_bacteria / total) * 100
            self.bad_bacteria = (self.bad_bacteria / total) * 100

    def gas_production(self) -> float:
        # rough heuristic: more bad bacteria and fiber -> more gas
        return round(self.bad_bacteria * 0.08 + self.fiber_intake * 0.05, 2)


@dataclass
class Food:
    name: str
    carbs: float
    proteins: float
    fats: float
    fiber: float = 0.0


@dataclass
class Environment:
    temperature_c: float = 37.0
    stress_level: int = 2  # 0-10


@dataclass
class Conditions:
    gastroparesis: bool = False
    gerd: bool = False
    malabsorption: bool = False
    diabetes: bool = False
    obesity: bool = False

    def active(self) -> List[str]:
        return [k for k, v in self.__dict__.items() if v]


# ---- Organs (single responsibility) ----
class Mouth:
    def process(self, food: Food, hormones: Dict[str, str], env: Environment) -> Dict:
        parasym = hormones.get('parasympathetic_stim', 'Normal')
        stress = env.stress_level
        saliva_factor = 1.0
        if parasym == 'High' and stress < 6:
            saliva_factor = 1.15
        elif parasym == 'Low' or stress >= 6:
            saliva_factor = 0.75
        # apply a light initial carb breakdown
        # be careful not to mutate user-provided Food unexpectedly outside scope
        food.carbs = max(0.0, food.carbs * (1.0 - 0.05 * saliva_factor))
        return {'desc': 'Chewing and salivary amylase', 'saliva_factor': saliva_factor}


class Esophagus:
    def transport(self, env: Environment) -> Dict:
        return {'desc': 'Peristalsis moves bolus to stomach'}


class Stomach:
    def __init__(self):
        self.base_timer = TIME_MAP['Stomach']
        self.timer = self.base_timer
        self.food: Optional[Food] = None
        self.gastrin_factor = 1.0

    def start_digestion(self, food: Food, hormones: Dict[str, str], cond: Conditions, env: Environment) -> Dict:
        gastrin = hormones.get('gastrin', 'Normal')
        ghrelin = hormones.get('ghrelin', 'Normal')
        gastrin_factor = 1.0
        if gastrin == 'High':
            gastrin_factor = 1.3
        elif gastrin == 'Low':
            gastrin_factor = 0.75
        stress_factor = 1.0 if env.stress_level < 6 else 0.85
        temp = env.temperature_c
        temp_factor = 1.0
        if temp < 36.0:
            temp_factor = 0.9
        elif temp > 38.0:
            temp_factor = 1.05
        disease_factor = 1.0
        if cond.gastroparesis:
            disease_factor *= 1.8
        if cond.gerd:
            disease_factor *= 1.05
        hunger_factor = 0.9 if ghrelin == 'High' else 1.0
        computed = max(2, int(self.base_timer / (gastrin_factor * temp_factor * hunger_factor) * disease_factor / stress_factor))
        self.timer = computed
        # store a shallow copy of food object to avoid accidental external mutation
        self.food = Food(name=food.name, carbs=food.carbs, proteins=food.proteins, fats=food.fats, fiber=food.fiber)
        self.gastrin_factor = gastrin_factor
        return {'desc': 'Stomach acid and pepsin', 'timer': self.timer}

    def digest_tick(self) -> Dict:
        if self.timer > 0:
            self.timer -= 1
            return {'running': True, 'remaining_ticks': self.timer}
        # finalize partial protein digestion
        finished = None
        if self.food:
            # apply final protein hydrolysis depending on gastrin_factor
            self.food.proteins = max(0.0, self.food.proteins * 0.5 * self.gastrin_factor)
            finished = self.food
        self.food = None
        return {'running': False, 'finished_food': finished}


class Duodenum:
    def __init__(self):
        self.timer = TIME_MAP['Duodenum']

    def process_tick(self, hormones: Dict[str, str]) -> Dict:
        if self.timer > 0:
            self.timer -= 1
            return {'running': True, 'remaining_ticks': self.timer}
        return {'running': False}


class SmallIntestine:
    def __init__(self):
        self.base_timer = TIME_MAP['SmallIntestine']
        self.timer = self.base_timer
        self.food: Optional[Food] = None

    def start_absorption(self, food: Food, hormones: Dict[str, str]) -> Dict:
        # create a copy of the food to simulate chyme entering the small intestine
        self.food = Food(name=food.name, carbs=food.carbs, proteins=food.proteins, fats=food.fats, fiber=food.fiber)
        return {'desc': 'Brush border enzymes active', 'timer': self.timer}

    def absorb_tick(self, cond: Conditions, env: Environment, hormones: Dict[str, str]) -> Dict:
        if self.timer > 0:
            self.timer -= 1
            return {'running': True, 'remaining_ticks': self.timer}
        malabs_factor = 0.65 if cond.malabsorption else 1.0
        insulin_resistance = 0.75 if (cond.diabetes or cond.obesity) else 1.0
        absorbed = {
            'carbs': max(0.0, self.food.carbs * 0.95 * malabs_factor),
            'proteins': max(0.0, self.food.proteins * 0.9 * malabs_factor),
            'fats': max(0.0, self.food.fats * 0.85 * malabs_factor)
        }
        energy_kcal = (absorbed['carbs'] * 4 + absorbed['proteins'] * 4 + absorbed['fats'] * 9) * insulin_resistance
        return {'running': False, 'absorbed': absorbed, 'energy_kcal': energy_kcal}


class LargeIntestine:
    def __init__(self):
        self.timer = TIME_MAP['LargeIntestine']

    def tick(self) -> Dict:
        if self.timer > 0:
            self.timer -= 1
            return {'running': True, 'remaining_ticks': self.timer}
        return {'running': False}


class Rectum:
    def store_and_defecate(self) -> Dict:
        return {'desc': 'Rectum stores feces until voluntary release'}


# ---- Body & metabolism ----
class Body:
    def __init__(self, env: Environment, cond: Conditions):
        self.env = env
        self.cond = cond
        self.microbiome = Microbiome()
        self.hormones: Dict[str, str] = {
            'parasympathetic_stim': 'Normal',
            'gastrin': 'Normal',
            'ghrelin': 'Normal',
            'insulin': 'Normal',
            'leptin': 'Normal'
        }
        self.hunger_level = 5
        self.energy = 0.0
        self.stage = 'idle'
        self.prev_stage = None  # track previous stage to detect changes
        self.ticks = 0  # ticks in current stage
        self.total_ticks = 0
        self.food: Optional[Food] = None
        self.current_absorbed: Dict[str, float] = {}
        self.metabolism: Optional[Dict[str, float]] = None

        # organs
        self.mouth = Mouth()
        self.esophagus = Esophagus()
        self.stomach = Stomach()
        self.duodenum = Duodenum()
        self.small_intestine = SmallIntestine()
        self.large_intestine = LargeIntestine()
        self.rectum = Rectum()

    def set_hunger_from_flags(self) -> None:
        # leptin and ghrelin reflect adiposity and short-term hunger
        if self.cond.obesity:
            self.hormones['leptin'] = 'High'
            # obesity leads to reduced subjective hunger
            self.hunger_level = max(1, self.hunger_level - 2)
            self.hormones['ghrelin'] = 'Low'
        else:
            if self.hunger_level >= 7:
                self.hormones['ghrelin'] = 'High'
            else:
                self.hormones['ghrelin'] = 'Low'

    def eat(self, food: Food) -> None:
        self.food = Food(name=food.name, carbs=food.carbs, proteins=food.proteins, fats=food.fats, fiber=food.fiber)
        self.stage = 'mouth'
        # satiety signal after initiating a meal
        self.hormones['ghrelin'] = 'Low'
        self.hunger_level = max(0, self.hunger_level - 3)
        # small anticipatory insulin rise when food is taken
        self.hormones['insulin'] = 'Slight'

    def metabolize(self, absorbed: Dict[str, float]) -> Dict[str, float]:
        # simple partition: carbs -> glycogen, fats -> stored fat, proteins -> used
        glycogen = min(100.0, absorbed.get('carbs', 0.0) * 0.6)
        fat_storage = absorbed.get('fats', 0.0) * 0.7
        protein_use = absorbed.get('proteins', 0.0) * 0.8
        energy_added = glycogen * 4 + protein_use * 4 + fat_storage * 9
        self.energy += energy_added
        result = {
            'glycogen': round(glycogen, 2),
            'fat_storage': round(fat_storage, 2),
            'protein_use': round(protein_use, 2),
            'energy_added': round(energy_added, 2),
            'total_energy': round(self.energy, 2)
        }
        return result

    def _update_hormones_on_stage_entry(self):
        # Called when stage changes; set hormones that should change when a stage begins
        if self.stage == 'mouth':
            # chewing increases parasympathetic tone slightly
            self.hormones['parasympathetic_stim'] = 'High' if self.env.stress_level < 6 else 'Normal'
            # anticipatory insulin
            if self.hormones.get('insulin') != 'High':
                self.hormones['insulin'] = 'Slight'
        elif self.stage == 'esophagus':
            # neutral
            self.hormones['parasympathetic_stim'] = 'Normal'
        elif self.stage == 'stomach':
            # increase gastrin to promote acid secretion
            self.hormones['gastrin'] = 'High'
            # ghrelin falls when food arrives
            self.hormones['ghrelin'] = 'Low'
            # parasympathetic tone supports digestion unless stressed
            self.hormones['parasympathetic_stim'] = 'High' if self.env.stress_level < 6 else 'Low'
        elif self.stage == 'duodenum':
            # cholecystokinin (not tracked) would rise; we simulate insulin rise input
            self.hormones['gastrin'] = 'Normal'
        elif self.stage == 'small_intestine':
            # major nutrient absorption: insulin should rise
            self.hormones['insulin'] = 'High' if not self.cond.diabetes else 'Impaired'
            # modest reduction in parasympathetic if severe stress
            self.hormones['parasympathetic_stim'] = 'Normal' if self.env.stress_level >= 6 else 'High'
        elif self.stage == 'large_intestine':
            # decreased hormonal activity
            self.hormones['insulin'] = 'Normal'
            self.hormones['gastrin'] = 'Low'
        elif self.stage == 'rectum':
            # finalize
            self.hormones['parasympathetic_stim'] = 'Normal'

    def tick(self) -> Dict:
        # update autonomic tone from stress each tick
        # this is overwritten by stage-specific settings below when entering a stage
        self.hormones['parasympathetic_stim'] = 'Low' if self.env.stress_level >= 6 else 'Normal'

        # track stage transitions
        if self.prev_stage != self.stage:
            # reset per-stage tick counter and let organs know
            self.ticks = 0
            self._update_hormones_on_stage_entry()
            self.prev_stage = self.stage

        info: Dict = {}
        if self.stage == 'idle':
            self.set_hunger_from_flags()
            info['status'] = 'Idle'

        elif self.stage == 'mouth':
            info = self.mouth.process(self.food, self.hormones, self.env)
            # after mouth processing, move to esophagus next tick
            self.stage = 'esophagus'

        elif self.stage == 'esophagus':
            info = self.esophagus.transport(self.env)
            self.stage = 'stomach'

        elif self.stage == 'stomach':
            if self.stomach.food is None:
                info = self.stomach.start_digestion(self.food, self.hormones, self.cond, self.env)
            else:
                info = self.stomach.digest_tick()
                if not info.get('running'):
                    self.food = info.get('finished_food')
                    # if stomach finished and provided finished_food is None, create placeholder
                    if self.food is None:
                        # ensure safe downstream
                        self.food = Food(name='chyme', carbs=0.0, proteins=0.0, fats=0.0, fiber=0.0)
                    self.stage = 'duodenum'

        elif self.stage == 'duodenum':
            res = self.duodenum.process_tick(self.hormones)
            if not res.get('running'):
                self.stage = 'small_intestine'
                info = self.small_intestine.start_absorption(self.food, self.hormones)
            else:
                info = res

        elif self.stage == 'small_intestine':
            res = self.small_intestine.absorb_tick(self.cond, self.env, self.hormones)
            if not res.get('running'):
                self.current_absorbed = res['absorbed']
                # metabolize and record
                self.metabolism = self.metabolize(self.current_absorbed)
                self.stage = 'large_intestine'
                info = {'status': 'Absorption complete', 'absorbed': self.current_absorbed}
            else:
                info = res

        elif self.stage == 'large_intestine':
            res = self.large_intestine.tick()
            if not res.get('running'):
                self.stage = 'rectum'
            info = res

        elif self.stage == 'rectum':
            _ = self.rectum.store_and_defecate()
            # finalize digestion and reset
            self.stage = 'idle'
            # reset organs for next meal
            self.stomach = Stomach()
            self.duodenum = Duodenum()
            self.small_intestine = SmallIntestine()
            self.large_intestine = LargeIntestine()
            self.food = None
            self.hunger_level = min(10, self.hunger_level + 4)
            info = {'status': 'Defecation complete'}

        else:
            info = {'status': 'Unknown'}

        # feed microbiome with fiber from current food
        self.microbiome.fiber_intake = self.food.fiber if self.food else 0.0
        self.microbiome.tick()

        # tick counters
        self.ticks += 1
        self.total_ticks += 1
        return info


# ---- UI helpers ----
def input_listener(command_queue: queue.Queue, stop_event: threading.Event) -> None:
    try:
        while not stop_event.is_set():
            cmd = input().strip().lower()
            if cmd:
                command_queue.put(cmd)
            if cmd == 'q':
                break
    except Exception:
        # ignore input errors; they should not crash the thread
        pass


def render_plain_status(body: Body, spinner: str) -> str:
    lines: List[str] = []
    lines.append(f"Stage: {body.stage}")
    lines.append(f"Ticks (stage): {body.ticks}")
    lines.append(f"Ticks (total): {body.total_ticks}")
    lines.append(f"Spinner: {spinner}")
    lines.append(f"Env: temp={body.env.temperature_c:.1f}C stress={body.env.stress_level}")
    lines.append(f"Conditions: {', '.join(body.cond.active()) or 'none'}")
    lines.append(f"Hormones: {body.hormones}")
    lines.append(f"Energy so far: {round(body.energy,2)} kcal")
    lines.append(f"Microbiome good/bad: {body.microbiome.good_bacteria:.1f}% / {body.microbiome.bad_bacteria:.1f}%")
    lines.append(f"Fiber intake: {body.microbiome.fiber_intake:.1f} g")
    lines.append(f"Gas production: {body.microbiome.gas_production()} units")
    if body.food:
        lines.append(f"Food: {body.food.name} carbs={body.food.carbs:.1f} proteins={body.food.proteins:.1f} fats={body.food.fats:.1f} fiber={body.food.fiber:.1f}")
    if body.metabolism:
        m = body.metabolism
        lines.append(f"Metabolism: glycogen={m['glycogen']} fat={m['fat_storage']} protein={m['protein_use']} added={m['energy_added']} total={m['total_energy']}")
    lines.append("Controls: p pause/resume | n skip stage | + / - stress | t / g temp up/down | o toggle obesity | m toggle malabsorption | a toggle antibiotic | q quit")
    return "\n".join(lines)


def _hormones_table_markup(body: Body) -> Table:
    t = Table(show_header=False, box=SIMPLE)
    t.add_column("h", ratio=1)
    t.add_column("v", ratio=2)
    for k, v in body.hormones.items():
        t.add_row(k, v)
    return t


def render_rich_status(body: Body, spinner_frame: int, progress: Progress, progress_task_id: Optional[int]) -> Panel: # type: ignore
    # Build a two-column layout with organ/hormone info and controls
    table = Table.grid(expand=True)
    table.add_column(ratio=2)
    table.add_column(ratio=3)

    left = Table.grid()
    left.add_row("Stage", str(body.stage))
    left.add_row("Ticks (stage)", str(body.ticks))
    left.add_row("Ticks (total)", str(body.total_ticks))
    left.add_row("Temperature C", f"{body.env.temperature_c:.1f}")
    left.add_row("Stress Level", str(body.env.stress_level))
    left.add_row("Active Conditions", ', '.join(body.cond.active()) or 'none')
    left.add_row("Energy kcal", f"{round(body.energy,2)}")
    left.add_row("Microbiome Good/Bad %", f"{body.microbiome.good_bacteria:.1f} / {body.microbiome.bad_bacteria:.1f}")
    left.add_row("Fiber Intake (g)", f"{body.microbiome.fiber_intake:.1f}")
    left.add_row("Gas Production", f"{body.microbiome.gas_production()}")

    right = Table.grid()
    hormones_table = _hormones_table_markup(body)
    right.add_row(hormones_table)

    if body.food:
        food_table = Table(title="Food", show_header=False, box=SIMPLE)
        food_table.add_row("Name", body.food.name)
        food_table.add_row("Carbs (g)", f"{body.food.carbs:.1f}")
        food_table.add_row("Proteins (g)", f"{body.food.proteins:.1f}")
        food_table.add_row("Fats (g)", f"{body.food.fats:.1f}")
        food_table.add_row("Fiber (g)", f"{body.food.fiber:.1f}")
        right.add_row(food_table)

    table.add_row(left, right)

    spinner_frames = ['|', '/', '-', '\\']
    spinner = spinner_frames[spinner_frame % len(spinner_frames)]
    controls = "[p] pause/resume  [n] skip stage  [+/-] stress  [t/g] temp up/down  [o] toggle obesity  [m] toggle malabsorption  [a] toggle antibiotic  [q] quit"

    # Compose a layout where the progress bar is shown under the main table
    layout = Layout()
    layout.split_column(
        Layout(name="main", ratio=3),
        Layout(name="progress", ratio=1)
    )
    layout['main'].update(Panel(table, title=f"Digestive Simulation  {spinner}"))

    if progress_task_id is not None:
        # render progress with an explanatory panel
        progress_panel = Panel(Align.center(progress), title="Organ Progress", padding=(1, 1))
        layout['progress'].update(progress_panel)
    else:
        layout['progress'].update(Panel("No active progress", title="Organ Progress", padding=(1, 1)))

    # final wrapper
    wrapper = Panel(layout, title="Digestive Simulation Dashboard", subtitle=controls)
    return wrapper


# ---- Main loop ----
def main_loop():
    if Console is None:
        print("Warning: rich not available. Install rich for better UI: pip install rich")
    console = Console() if Console else None

    env = Environment(temperature_c=37.0, stress_level=2)
    cond = Conditions()

    foods = [
        Food("Burger & Fries", carbs=60.0, proteins=30.0, fats=35.0, fiber=4.0),
        Food("Salad", carbs=15.0, proteins=5.0, fats=10.0, fiber=8.0),
        Food("Pasta", carbs=70.0, proteins=20.0, fats=10.0, fiber=3.0),
        Food("Steak", carbs=0.0, proteins=50.0, fats=20.0, fiber=0.0)
    ]

    body = Body(env, cond)

    # command queue and input thread
    cmd_q = queue.Queue()
    stop_event = threading.Event()
    t = threading.Thread(target=input_listener, args=(cmd_q, stop_event), daemon=True)
    t.start()

    paused = False
    spinner_idx = 0

    try:
        print("Choose your meal by number or type 'q' to quit")
        for i, f in enumerate(foods, 1):
            print(f"{i}. {f.name} (Carbs: {f.carbs}g, Proteins: {f.proteins}g, Fats: {f.fats}g, Fiber: {f.fiber}g)")
        while True:
            choice = input("Enter number: ").strip().lower()
            if choice == 'q':
                stop_event.set()
                return
            if choice.isdigit() and 1 <= int(choice) <= len(foods):
                chosen = foods[int(choice) - 1]
                break
            print("Invalid input")

        body.eat(chosen)

        # Create a single Progress instance and a single Live instance to update in-place
        progress = Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TimeElapsedColumn()) if Progress else None
        progress_task_id = None

        if Live and Console and progress:
            # start progress
            progress.start()
            # We'll add a task and update its total when a new organ timer is set
            progress_task_id = progress.add_task("idle", total=1)

            with Live(render_rich_status(body, spinner_idx, progress, progress_task_id), refresh_per_second=4, console=console, screen=True) as live:
                # main update loop - we will update the live panel in-place
                while True:
                    # handle commands
                    while not cmd_q.empty():
                        cmd = cmd_q.get().strip().lower()
                        if cmd == 'p':
                            paused = not paused
                        elif cmd == 'n':
                            # skip current and future timers
                            body.stomach.timer = 0
                            body.duodenum.timer = 0
                            body.small_intestine.timer = 0
                            body.large_intestine.timer = 0
                        elif cmd == '+':
                            body.env.stress_level = min(10, body.env.stress_level + 1)
                        elif cmd == '-':
                            body.env.stress_level = max(0, body.env.stress_level - 1)
                        elif cmd == 't':
                            body.env.temperature_c += 0.5
                        elif cmd == 'g':
                            body.env.temperature_c -= 0.5
                        elif cmd == 'o':
                            body.cond.obesity = not body.cond.obesity
                        elif cmd == 'm':
                            body.cond.malabsorption = not body.cond.malabsorption
                        elif cmd == 'a':
                            body.microbiome.antibiotic = not body.microbiome.antibiotic
                        elif cmd == 'q':
                            stop_event.set()
                            raise KeyboardInterrupt

                    if not paused:
                        # Before ticking, possibly set progress task to current organ timer
                        # Determine current organ remaining ticks to show
                        organ_remaining = None
                        organ_total = None
                        desc = "idle"
                        if body.stage == 'stomach':
                            # If digestion hasn't started yet, compute will set timer on start_digestion
                            if body.stomach.timer > 0:
                                organ_remaining = body.stomach.timer
                                organ_total = body.stomach.base_timer
                                desc = 'Stomach'
                        elif body.stage == 'duodenum':
                            organ_remaining = body.duodenum.timer
                            organ_total = TIME_MAP['Duodenum']
                            desc = 'Duodenum'
                        elif body.stage == 'small_intestine':
                            organ_remaining = body.small_intestine.timer
                            organ_total = body.small_intestine.base_timer
                            desc = 'Small Intestine'
                        elif body.stage == 'large_intestine':
                            organ_remaining = body.large_intestine.timer
                            organ_total = TIME_MAP['LargeIntestine']
                            desc = 'Large Intestine'
                        else:
                            organ_remaining = None

                        # Update progress bar if reasonable
                        if progress and progress_task_id is not None:
                            try:
                                if organ_total and organ_total > 0:
                                    progress.update(progress_task_id, total=organ_total, completed=max(0, organ_total - (organ_remaining or 0)), description=desc)
                                else:
                                    progress.update(progress_task_id, total=1, completed=1, description=desc)
                            except Exception:
                                # progress may be stopped or finished; ignore update errors
                                pass

                        body.tick()

                    spinner_idx += 1

                    # update live view (single panel edit)
                    live.update(render_rich_status(body, spinner_idx, progress, progress_task_id))

                    # stop when digestion returned idle and no food
                    if body.stage == 'idle' and body.food is None:
                        console.print(f"Digestion complete. Total energy gained: {round(body.energy,2)} kcal")
                        time.sleep(1.2)
                        break

                    time.sleep(1)

                # end with: stop progress safely
                try:
                    progress.stop()
                except Exception:
                    pass

        else:
            # Fallback non-rich loop: prints single updatable text region by clearing screen
            while True:
                while not cmd_q.empty():
                    cmd = cmd_q.get().strip().lower()
                    if cmd == 'p':
                        paused = not paused
                    elif cmd == 'n':
                        body.stomach.timer = 0
                        body.duodenum.timer = 0
                        body.small_intestine.timer = 0
                        body.large_intestine.timer = 0
                    elif cmd == '+':
                        body.env.stress_level = min(10, body.env.stress_level + 1)
                    elif cmd == '-':
                        body.env.stress_level = max(0, body.env.stress_level - 1)
                    elif cmd == 't':
                        body.env.temperature_c += 0.5
                    elif cmd == 'g':
                        body.env.temperature_c -= 0.5
                    elif cmd == 'o':
                        body.cond.obesity = not body.cond.obesity
                    elif cmd == 'm':
                        body.cond.malabsorption = not body.cond.malabsorption
                    elif cmd == 'a':
                        body.microbiome.antibiotic = not body.microbiome.antibiotic
                    elif cmd == 'q':
                        stop_event.set()
                        raise KeyboardInterrupt

                if not paused:
                    body.tick()

                spinner_frames = ['|', '/', '-', '\\']
                spinner = spinner_frames[spinner_idx % len(spinner_frames)]
                sys.stdout.write('\x1b[2J\x1b[H')  # clear terminal (ansi)
                print(render_plain_status(body, spinner))

                if body.stage == 'idle' and body.food is None:
                    print(f"Digestion complete. Total energy gained: {round(body.energy,2)} kcal")
                    time.sleep(1.2)
                    break

                spinner_idx += 1
                time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        try:
            t.join(timeout=0.5)
        except Exception:
            pass
        print("Exiting simulation. Goodbye.")


if __name__ == '__main__':
    main_loop()