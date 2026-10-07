"""Cancellation and prefix-restore checks for an isolated experiment server."""
import json
import time
import urllib.request

from tools.kervia_bench import NoRedirect, endpoint, request
from tools.kervia_validate import long_gate


def cancellation_gate(base, model):
    payload = {'model': model, 'messages': [{'role': 'user', 'content':
               'Write an extensive 5000-word tutorial about sorting algorithms with many Python examples.'}],
               'max_tokens': 4096, 'temperature': 0, 'seed': 42, 'stream': True,
               'reasoning_effort': 'none', 'chat_template_kwargs': {'enable_thinking': False}}
    req = urllib.request.Request(endpoint(base, False), data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    received = False
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=90) as response:
        for line in response:
            if not line.startswith(b'data: '):
                continue
            value = line[6:].strip()
            if value == b'[DONE]':
                break
            event = json.loads(value)
            if event.get('error'):
                raise ValueError('Cancellation request failed before content')
            if any(c.get('delta', {}).get('content') for c in event.get('choices', [])):
                received = True
                break
    if not received:
        return {'passed': False, 'reason': 'No content before close'}
    start = time.monotonic()
    result = request(endpoint(base, False), model,
                     'Begin with RECOVERED-573 and explain in a paragraph what a Python dictionary is.',
                     128, None, collect_content=True)
    content = result.pop('content')
    return {'passed': 'RECOVERED-573' in content and time.monotonic()-start < 30,
            'recovery_seconds': time.monotonic()-start, 'recovery_request': result}


def prefix_gate(base, model, tokenizer_dir):
    """Requires an engine configured with checkpoints; never silently enables them."""
    first = long_gate(base, model, tokenizer_dir, 32000)
    second = long_gate(base, model, tokenizer_dir, 32000)
    cached = second['usage'].get('prompt_tokens_details', {}).get('cached_tokens', 0)
    passed = (first['retrieval_passed'] and second['retrieval_passed']
              and first['sustained_generation'] and second['sustained_generation']
              and first['within_context'] and second['within_context']
              and cached >= int(second['usage']['prompt_tokens'] * .9))
    return {'passed': passed, 'first': first, 'second': second, 'cached_tokens': cached}
