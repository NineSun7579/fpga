"""Summarize measured stage costs; upper bounds are not FPGA FPS measurements."""
import csv
import json
import statistics
from pathlib import Path

root = Path(__file__).resolve().parent
with (root / 'pipeline_block_samples.csv').open(newline='') as stream:
    rows = list(csv.DictReader(stream))
stages = [name for name in rows[0] if name.endswith('_wall_ms')]
report = {'measurement': 'RK3568 paired inference with viewer running', 'profiles': {}}
for profile in sorted({row['profile'] for row in rows}):
    samples = [row for row in rows if row['profile'] == profile]
    means = {stage: statistics.mean(float(row[stage]) for row in samples) for stage in stages}
    elapsed = means['completed_wall_ms']
    prep = means['preprocess_wall_ms']
    report['profiles'][profile] = {
        'completed_samples': len(samples), 'mean_stage_ms': means,
        'preprocess_fraction': prep / elapsed,
        'ideal_zero_cost_preprocess_fps': 1000 / (elapsed - prep),
        'ideal_zero_cost_preprocess_speedup_percent': 100 * (elapsed / (elapsed - prep) - 1),
        'bound_assumptions': 'Remove CPU preprocessing completely with zero FPGA/DMA/wait cost; all other measured stage costs remain fixed. This is a stage-budget estimate, not measured FPGA acceleration.'
    }
(root / 'stage_budget.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
