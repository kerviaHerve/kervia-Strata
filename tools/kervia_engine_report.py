"""Publish allowlisted measurements from a private engine campaign directory.

Do not export command lines, configuration, process IDs, raw logs or endpoints.
Synthetic response digests and numeric correctness results are kept for audit.
"""
import argparse
import json
import re
from pathlib import Path


def summarize_telemetry(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    valid = [r for r in rows if 'rss_bytes' in r]
    result = {'samples': len(valid), 'sample_errors': len(rows) - len(valid)}
    if not valid:
        return result
    result.update(rss_peak_bytes=max(r['rss_bytes'] for r in valid),
                  available_min_bytes=min(r['available_bytes'] for r in valid),
                  foreign_compute_count_max=max(len(r.get('foreign_compute_pids', [])) for r in valid))
    result['gpu_peaks'] = [[max(r['gpus'][g][col] for r in valid) for col in (1, 2, 3, 4)] for g in (0, 1)]
    events = {}
    for r in valid:
        for line in r.get('cgroup', {}).get('memory.events', '').splitlines():
            key, value = line.split()
            events[key] = max(events.get(key, 0), int(value))
    result['cgroup_events'] = events
    result['cgroup_peak_bytes'] = max(int(r.get('cgroup', {}).get('memory.peak', 0)) for r in valid)
    result['cgroup_swap_peak_bytes'] = max(int(r.get('cgroup', {}).get('memory.swap.current', 0)) for r in valid)
    return result


def extra_counters(text):
    pipeline, borrowed, parked, scored = [], [], [], []
    for line in text.splitlines():
        m = re.search(r'pipeline: (\d+) windows in (\d+) ms .*?: (\d+) speculative, (\d+) on the path, '
                      r'(\d+) rolled back, (\d+) below the gate', line)
        if m:
            pipeline.append(dict(zip(('windows', 'ms', 'speculative', 'on_path', 'rolled_back', 'gated'), map(int, m.groups()))))
        m = re.search(r'cache: borrowed (\d+) tokens.*?in ([\d.]+) ms; parked=(\d+) bytes=(\d+) borrowed=(\d+)', line)
        if m:
            borrowed.append(dict(tokens=int(m[1]), ms=float(m[2]), parked=int(m[3]), bytes=int(m[4]), count=int(m[5])))
        m = re.search(r'cache: (?:parked|skipped) (\d+) tokens in ([\d.]+) ms; parked=(\d+) bytes=(\d+) '
                      r'evictions=(\d+) snapshot_bytes=(\d+) reused_kv_bytes=(\d+)', line)
        if m:
            parked.append(dict(tokens=int(m[1]), ms=float(m[2]), parked=int(m[3]), bytes=int(m[4]),
                               evictions=int(m[5]), snapshot_bytes=int(m[6]), reused_kv_bytes=int(m[7])))
        m = re.search(r'pipeline adaptive: scored=(\d+)', line)
        if m:
            scored.append(int(m[1]))
    return dict(pipeline=pipeline, borrows=borrowed, parking=parked, adaptive_scored=scored)


def trial(directory):
    raw = json.loads((directory / 'result.json').read_text())
    out = {k: raw[k] for k in ('name', 'source_revision', 'binary_sha256', 'features', 'status',
                              'ready_seconds', 'seconds', 'results', 'engine') if k in raw}
    out['telemetry'] = summarize_telemetry(directory / 'telemetry.jsonl')
    if (directory / 'engine.log').exists():
        out['counters'] = extra_counters((directory / 'engine.log').read_text(errors='replace'))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('names', nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = dict(schema_version=1, workload='kervia-engine-agent-v2',
                  telemetry_note='Sampled process-tree RSS and whole-card peaks. GPU columns: MiB, utilization %, W, C.',
                  trials=[trial(args.root / name) for name in args.names])
    with args.output.open('x') as out:
        json.dump(result, out, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
