"""Leak grid for docs/VALIDATION_ASSESSMENT.md: K % of candidates know the answers of their main family.

Run from backend/:  PYTHONPATH=. python ../docs/tools/leak_grid.py --n 2000 --seed 7
Uses only app.validation.assessment (the same simulator as the published numbers); changes nothing.
"""
import argparse
import random

from app.validation.assessment import Truth, calibrate, cohort, monitor, population

p = argparse.ArgumentParser()
p.add_argument("--n", type=int, default=2000)
p.add_argument("--seed", type=int, default=7)
a = p.parse_args()
rng = random.Random(a.seed)
truth = Truth.draw(rng)
_, pretest = cohort(population(a.n, rng), truth, rng)
offsets = calibrate(pretest)
people = population(a.n, random.Random(a.seed + 5))
print("| K, % | Монитор | Верное «сдал/не сдал» | Ложно сдали (ниже грейда) | Грейд выше истины | Ключей в карантине |")
print("|---|---|---|---|---|---|")
for k in (0, 5, 25, 100):
    share = k / 100
    # The monitor learns on an earlier cohort with the same leak share, as in the main run.
    _, learn = cohort(population(a.n, random.Random(a.seed + 100 + k)), truth, rng, leak_share=share, offsets=offsets)
    stats = monitor(learn)
    flagged = {key for key, st in stats.items() if st.alarm or st.cusum_alarm}
    for label, blocked in (("нет", None), ("да", flagged)):
        r, _ = cohort(people, truth, rng, leak_share=share, blocked=blocked, offsets=offsets, stream=a.seed + 6)
        print(f"| {k} | {label} | {r.accuracy:.1%} | {r.false_pass:.1%} | {r.overgrade:.1%} | "
              f"{len(flagged) if blocked is not None else '—'} |")
