"""Synthetic engine workloads: short prefills and sibling conversation reuse.

Run only against an explicitly selected loopback experiment server. The caller
owns service lifecycle, cache settings and telemetry. No actual user data.
"""
import hashlib
import json
import time
import urllib.request

from tools.kervia_bench import NoRedirect, endpoint, parse_stream


def measured_chat(base, messages, limit=96):
    payload = dict(model='kervia-strata', messages=messages, temperature=0, seed=42,
                   max_tokens=limit, reasoning_effort='none',
                   chat_template_kwargs={'enable_thinking': False}, stream=True,
                   stream_options={'include_usage': True})
    body = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint(base, False), data=body, headers={'Content-Type': 'application/json'})
    start = time.monotonic()
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=600) as response:
        result = parse_stream(response, collect_content=True)
    result['time_to_first_token_seconds'] = result.pop('first') - start
    result.pop('last')
    result['total_seconds'] = time.monotonic() - start
    result['fixture_sha256'] = hashlib.sha256(body).hexdigest()
    content = result.pop('content')
    return result, content


def rows(label, count):
    return '\n'.join(f'{label} record {i:04d}: blue widget, quantity 7, status verified.' for i in range(count))


def short_prefills(base, record):
    # API token counts, not row counts, determine whether a case hits <1024.
    measured_chat(base, [{'role': 'user', 'content': 'Explain a Python dictionary in a paragraph.'}])
    for repetition in range(3):
        for count in (5, 20, 40):
            messages = [{'role': 'user', 'content': f'Case {repetition}-{count}.\n' + rows('Inventory', count) +
                         '\nStart with SHORT-573 then explain how to validate these records in Python.'}]
            value, content = measured_chat(base, messages)
            value.update(kind='cold-short', repetition=repetition, rows=count, passed='SHORT-573' in content)
            record(value)
        system = f'Continuation family {repetition}. Reference table:\n' + rows('Shared', 160)
        messages = [{'role': 'system', 'content': system},
                    {'role': 'user', 'content': 'Start with READY-573 and describe this reference table in a paragraph.'}]
        first, content = measured_chat(base, messages)
        record(dict(first, kind='continuation-seed', repetition=repetition, passed='READY-573' in content))
        messages += [{'role': 'assistant', 'content': 'READY-573. The reference table contains verified synthetic inventory records.'}]
        for count in (5, 20, 40):
            branch = messages + [{'role': 'user', 'content': rows('Tool-result', count) +
                                  '\nStart with CONTINUE-573 and explain validation of the new records.'}]
            value, content = measured_chat(base, branch)
            value.update(kind='cached-short', repetition=repetition, rows=count, passed='CONTINUE-573' in content)
            record(value)


def siblings(base, record):
    for repetition in range(3):
        system = f'Sibling family {repetition}. Shared instructions and reference data:\n' + rows('Common', 160)
        a = [{'role': 'system', 'content': system},
             {'role': 'user', 'content': rows('ALPHA', 80) +
              '\nThe private marker for this branch is ALPHA-573. Start with it and summarize this branch.'}]
        other = [{'role': 'system', 'content': f'Unrelated conversation {repetition}; describe only your user request.'},
                 {'role': 'user', 'content': 'Start with OTHER-918 and explain a priority queue in Python.'}]
        b = [{'role': 'system', 'content': system},
             {'role': 'user', 'content': rows('BETA', 80) +
              '\nThe private marker for this branch is BETA-829. Start with it and summarize this branch.'}]
        value, answer_a = measured_chat(base, a)
        record(dict(value, kind='sibling-a', repetition=repetition, passed='ALPHA-573' in answer_a))
        value, content = measured_chat(base, other)
        record(dict(value, kind='sibling-other', repetition=repetition, passed='OTHER-918' in content))
        value, content = measured_chat(base, b)
        record(dict(value, kind='sibling-b', repetition=repetition,
                    passed='BETA-829' in content and 'ALPHA-573' not in content))
        a += [{'role': 'assistant', 'content': 'ALPHA-573. This branch contains verified inventory records.'},
              {'role': 'user', 'content': 'Start with the private marker for OUR branch, then explain its next validation step.'}]
        value, content = measured_chat(base, a)
        record(dict(value, kind='sibling-a-return', repetition=repetition,
                    passed='ALPHA-573' in content and 'BETA-829' not in content))
