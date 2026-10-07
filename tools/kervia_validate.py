"""Synthetic functional/long-context gates for a separately started experiment server.

Pillow and Strata's own tokenizer use the existing server environment.
Generated Python executes in a networkless Bubblewrap sandbox, never on the host.
"""
from __future__ import annotations

import ast
import base64
import hashlib
import io
import json
import subprocess
import urllib.request
from pathlib import Path

from tools.kervia_bench import NoRedirect, endpoint, request


def chat(base, model, messages, stream=False, **extra):
    payload = dict(model=model, messages=messages, temperature=0, seed=42, max_tokens=2048,
                   reasoning_effort='none', chat_template_kwargs={'enable_thinking': False},
                   stream=stream, cache_prompt=False, **extra)
    req = urllib.request.Request(endpoint(base, False), data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=240) as response:
        if not stream:
            return json.load(response)['choices'][0]['message']
        message = {'role': 'assistant', 'content': ''}
        calls = {}
        done = False
        for line in response:
            if not line.startswith(b'data: '):
                continue
            value = line[6:].strip()
            if value == b'[DONE]':
                done = True
                break
            event = json.loads(value)
            if event.get('error'):
                raise ValueError('Stream error')
            for choice in event.get('choices', []):
                delta = choice.get('delta', {})
                message['content'] += delta.get('content') or ''
                for call in delta.get('tool_calls', []):
                    target = calls.setdefault(call['index'], {'id': '', 'type': 'function',
                                                              'function': {'name': '', 'arguments': ''}})
                    if call.get('id'):
                        target['id'] = call['id']
                    for field in ('name', 'arguments'):
                        target['function'][field] += call.get('function', {}).get(field) or ''
        if not done:
            raise ValueError('Incomplete tool stream')
        if calls:
            message['tool_calls'] = [calls[i] for i in sorted(calls)]
        return message


CODE_PROMPT = ('Write only Python code, no Markdown or imports. Define merge_ranges(ranges). '
               'Given integer (start, end) pairs, raise ValueError if start > end, sort and merge '
               'overlapping intervals or intervals sharing an endpoint. Return a list of tuples. '
               'Do not mutate the input; an empty input returns [].')
CODE_CHECKS = '''
assert merge_ranges([]) == []
x = [(5,8),(1,3),(3,6),(10,10)]
assert merge_ranges(x) == [(1,8),(10,10)]
assert x == [(5,8),(1,3),(3,6),(10,10)]
assert merge_ranges([(-4,-2),(-3,0),(2,4)]) == [(-4,0),(2,4)]
assert merge_ranges([(1,10),(2,3),(1,10)]) == [(1,10)]
try: merge_ranges([(3,2)])
except ValueError: pass
else: raise AssertionError('missing validation')
'''


def check_code(source):
    source = source.strip()
    if source.startswith('```'):
        source = source.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    tree = ast.parse(source)
    if not tree.body or not all(isinstance(n, ast.FunctionDef) for n in tree.body):
        raise ValueError('Expected function definitions only')
    allowed = {'ValueError', 'sorted', 'len', 'max', 'min', 'list', 'tuple', 'range', 'enumerate',
               'isinstance', 'int', 'TypeError'}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal)):
            raise ValueError('Unexpected executable construct')
        if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            raise ValueError('Private attribute')
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in allowed:
                continue
            if isinstance(node.func, ast.Attribute) and node.func.attr in ('append', 'sort', 'copy', 'extend'):
                continue
            raise ValueError('Unexpected function call')
    cmd = ['bwrap', '--unshare-all', '--die-with-parent', '--ro-bind', '/usr', '/usr',
           '--ro-bind', '/lib', '/lib', '--ro-bind', '/lib64', '/lib64', '--proc', '/proc',
           '--dev', '/dev', '--tmpfs', '/tmp', '--clearenv', '--setenv', 'PATH', '/usr/bin',
           '/usr/bin/python3', '-I', '-']
    # Apply limits inside the sandbox before executing generated code.
    limits = 'import resource\nresource.setrlimit(resource.RLIMIT_CPU,(2,2))\nresource.setrlimit(resource.RLIMIT_AS,(268435456,268435456))\n'
    result = subprocess.run(cmd, input=limits + source + '\n' + CODE_CHECKS,
                            text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
    return dict(passed=result.returncode == 0, assertions=6,
                source_sha256=hashlib.sha256(source.encode()).hexdigest())


def vision_content():
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (1024, 768), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 50)
    draw.text((230, 65), 'ORCHID-5724', fill='black', font=font)
    draw.rectangle((100, 230, 400, 530), fill='red')
    draw.ellipse((624, 230, 924, 530), fill='blue')
    data = io.BytesIO()
    image.save(data, format='PNG')
    return [{'type': 'text', 'text': 'Read the code and describe both shapes, colors and left/right positions in English.'},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(data.getvalue()).decode()}}]


def tool_gate(base, model, stream):
    tools = [{'type': 'function', 'function': {'name': name, 'description': description,
              'parameters': {'type': 'object', 'properties': properties, 'required': list(properties),
                             'additionalProperties': False}}}
             for name, description, properties in [
                 ('read_fixture', 'Read the synthetic inventory.', {'fixture': {'type': 'string'}}),
                 ('save_result', 'Save the inventory total.', {'total': {'type': 'integer'}, 'unit': {'type': 'string'}})]]
    messages = [{'role': 'user', 'content': 'Call read_fixture for stock-test. Sum quantity times price. '
                 'Call save_result with that total and unit CHF, then tell me the saved total.'}]
    seen = []
    for _ in range(4):
        message = chat(base, model, messages, stream=stream, tools=tools, tool_choice='auto')
        messages.append(message)
        calls = message.get('tool_calls') or []
        if not calls:
            return dict(passed=seen == ['read_fixture', 'save_result'] and '119' in (message.get('content') or ''),
                        tool_names=seen)
        for call in calls:
            name = call['function']['name']
            args = json.loads(call['function']['arguments'])
            if name == 'read_fixture' and not seen and args == {'fixture': 'stock-test'}:
                result = {'items': [{'quantity': 3, 'price': 17}, {'quantity': 4, 'price': 17}]}
            elif name == 'save_result' and seen == ['read_fixture'] and args == {'total': 119, 'unit': 'CHF'}:
                result = {'saved': True, 'total': 119, 'unit': 'CHF'}
            else:
                return dict(passed=False, tool_names=seen, reason='Unexpected tool or arguments')
            seen.append(name)
            messages.append({'role': 'tool', 'tool_call_id': call['id'], 'name': name, 'content': json.dumps(result)})
    return dict(passed=False, tool_names=seen, reason='Tool loop exceeded four turns')


def functional(base, model):
    result = {}
    tasks = {
        'code': lambda: check_code(chat(base, model, [{'role': 'user', 'content': CODE_PROMPT}]).get('content') or ''),
        'vision': lambda: vision_gate(base, model),
        'tools': lambda: tool_gate(base, model, False),
        'streamed_tools': lambda: tool_gate(base, model, True),
    }
    for name, task in tasks.items():
        try:
            result[name] = task()
        except Exception as error:
            result[name] = dict(passed=False, error_type=type(error).__name__)
    return result


def vision_gate(base, model):
    answer = (chat(base, model, [{'role': 'user', 'content': vision_content()}]).get('content') or '').lower()
    return dict(passed=all(x in answer for x in ('orchid-5724', 'red', 'blue', 'left', 'right'))
                and ('square' in answer or 'rectangle' in answer) and 'circle' in answer,
                answer_sha256=hashlib.sha256(answer.encode()).hexdigest())


def long_prompt(tokenizer_dir: Path, target: int):
    from tools.strata_tokenizer import Tokenizer
    vocab = json.loads((tokenizer_dir / 'vocab.json').read_text())
    tokens = [None] * len(vocab)
    for token, index in vocab.items():
        tokens[index] = token
    tokenizer = Tokenizer(tokens, (tokenizer_dir / 'merges.txt').read_text().split('\n'),
                          json.loads((tokenizer_dir / 'token_type.json').read_text()))
    row = 'Synthetic ledger row: the amber module stores four stable values for a public test.\n'
    def build(repetitions):
        section = row * repetitions
        return ('Remember the three checkpoint codes in this synthetic ledger.\n'
                'FIRST_CHECKPOINT: SAPHIR-7319\n' + section + '\nMIDDLE_CHECKPOINT: CEDRE-4826\n'
                + section + '\nLAST_CHECKPOINT: NUAGE-9053\n'
                + '\nFirst print all three checkpoint codes in order. Then write a detailed 1200-word '
                'tutorial about testing Python parsers, with code and edge cases. Do not stop after the codes.')
    low, high = 0, target // max(1, 2 * len(tokenizer.encode(row))) + 32
    while low + 1 < high:
        middle = (low + high) // 2
        if len(tokenizer.encode(build(middle))) <= target:
            low = middle
        else:
            high = middle
    return build(low)


def long_gate(base, model, tokenizer_dir, target):
    prompt = long_prompt(Path(tokenizer_dir), target)
    result = request(endpoint(base, False), model, prompt, 768, None, collect_content=True)
    answer = result.pop('content')
    result['retrieval_passed'] = all(x in answer for x in ('SAPHIR-7319', 'CEDRE-4826', 'NUAGE-9053'))
    result['sustained_generation'] = result['usage']['completion_tokens'] == 768
    result['uncached'] = result['usage'].get('prompt_tokens_details', {}).get('cached_tokens', 0) == 0
    result['within_context'] = result['usage']['prompt_tokens'] + result['usage']['completion_tokens'] <= 131072
    return result
