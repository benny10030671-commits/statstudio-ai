"""Generate synthetic, non-personal reference data using only the standard library."""
import csv
import math
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['x', 'y', 'z', 'group', 'binary', 'paired_a', 'paired_b', 'item1', 'item2', 'item3']


def generate():
    rng = random.Random(20261012)
    rows = []
    for i in range(60):
        group = i % 3 + 1
        x = rng.gauss(0, 1.3)
        z = 0.35 * x + rng.gauss(0, 0.9)
        y = 2 + 1.1 * x - 0.8 * z + 0.3 * group + rng.gauss(0, 1.2)
        binary = int(rng.random() < 1 / (1 + math.exp(-(-0.2 + 0.5*x - 0.4*z))))
        paired_a = 10 + 0.3*x + rng.gauss(0, 1.4)
        paired_b = paired_a - 0.6 + rng.gauss(0, 1.1)
        latent = rng.gauss(0, 1)
        item1 = 3 + 0.9*latent + rng.gauss(0, 0.7)
        item2 = 4 + 1.2*latent + rng.gauss(0, 0.6)
        item3 = 2 + 0.7*latent + rng.gauss(0, 0.8)
        raw = [x,y,z,group,binary,paired_a,paired_b,item1,item2,item3]
        rows.append([str(v) if isinstance(v,int) else f'{v:.10f}' for v in raw])
    target = ROOT/'tests'/'fixtures'
    target.mkdir(parents=True,exist_ok=True)
    with (target/'reference.csv').open('w',encoding='utf-8',newline='') as handle:
        writer=csv.writer(handle,lineterminator='\n');writer.writerow(FIELDS);writer.writerows(rows)
    missing=[list(row) for row in rows]
    for row,column in [(1,'x'),(2,'y'),(5,'z'),(8,'paired_a'),(11,'paired_b'),(14,'item2')]:
        missing[row][FIELDS.index(column)]=''
    with (target/'reference_missing.csv').open('w',encoding='utf-8',newline='') as handle:
        writer=csv.writer(handle,lineterminator='\n');writer.writerow(FIELDS);writer.writerows(missing)
    print(f'Wrote 60 synthetic rows to {target}')


if __name__=='__main__':
    generate()
