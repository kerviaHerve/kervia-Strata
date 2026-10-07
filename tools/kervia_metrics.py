"""Extract numeric experiment evidence from Strata logs without exporting raw log text."""
from __future__ import annotations

import re


def parse_engine_log(text: str) -> dict:
    result = {'requests': [], 'pcie_probes': [], 'pipeline_disabled': False,
              'pipeline_active': False, 'trimmed_stages': [], 'expert_caches': []}
    current = None
    for line in text.splitlines():
        match = re.search(r'prompt (\d+) tokens = (\d+) reused \+ (\d+) read in ([\d.]+) ms.*?'
                          r'(\d+) generated in ([\d.]+) ms.*?drafts accepted (\d+) of (\d+)', line)
        if match:
            n, reused, read, prefill_ms, produced, decode_ms, accepted, offered = match.groups()
            current = dict(input_tokens=int(n), reused_tokens=int(reused), read_tokens=int(read),
                           prefill_ms=float(prefill_ms), output_tokens=int(produced), decode_ms=float(decode_ms),
                           drafts_accepted=int(accepted), drafts_offered=int(offered))
            result['requests'].append(current)
        match = re.search(r'\((\d+) hits / (\d+) lookups\)(?:; (\d+) more.*?all (\d+) routed)?', line)
        if match and current is not None:
            hits, lookups, offloaded, total = match.groups()
            hits, lookups, offloaded = int(hits), int(lookups), int(offloaded or 0)
            total = int(total) if total else lookups
            if total != lookups + offloaded or not 0 <= hits <= lookups or total <= 0:
                raise ValueError('Inconsistent expert counters')
            current['experts'] = dict(resident_hits=hits, cpu_remainder=lookups-hits,
                                     offloaded=offloaded, total_routed=total,
                                     resident_fraction=hits/total, offload_fraction=offloaded/total)
        match = re.search(r'PCIe probe(?::| )([\d.]+) GB/s', line)
        # The later-stage probe omits the space after the colon; support both forms.
        if not match:
            match = re.search(r'PCIe probe:\s+([\d.]+) GB/s', line)
        if match:
            result['pcie_probes'].append(float(match[1]))
        match = re.search(r'layer split auto: K=(\d+)', line)
        if match:
            result['auto_boundary'] = int(match[1])
        match = re.search(r'CUDA(\d+) loads the dense weights of layers (\d+)-(\d+) only', line)
        if match:
            result['trimmed_stages'].append([int(x) for x in match.groups()])
        match = re.search(r'layer split: CUDA(\d+) runs layers (\d+)-(\d+), expert cache (\d+) slots', line)
        if match:
            result['expert_caches'].append([int(x) for x in match.groups()])
        match = re.search(r'generate: expert cache (\d+) slots, ([\d.]+) GiB', line)
        if match:
            result['first_cache_slots'] = int(match[1])
            result['first_cache_gib'] = float(match[2])
        if '--pipeline-windows' in line and 'is off:' in line:
            result['pipeline_disabled'] = True
        if '--pipeline-windows 2: two verifiers per stage' in line:
            result['pipeline_active'] = True
    return result
