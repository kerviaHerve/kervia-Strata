#!/usr/bin/env python3
"""Measure a running OpenAI-compatible server with synthetic English prompts only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

TOPICS = ('an LRU cache in Python with examples', 'a priority task queue in Python',
          'a robust CSV parser in Python')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward credentials or silently turn a local test into a remote request.
        return None


def parse_stream(lines, clock=time.monotonic, collect_content=False) -> dict:
    first = last = None
    count = 0
    digest = hashlib.sha256()
    usage = None
    done = False
    chunks = []
    finish = None
    for line in lines:
        if not line.startswith(b'data: '):
            continue
        data = line[6:].strip()
        if data == b'[DONE]':
            done = True
            break
        event = json.loads(data)
        if event.get('error'):
            raise ValueError('The server returned a streaming error.')
        if event.get('usage'):
            usage = event['usage']
        for choice in event.get('choices', []):
            finish = choice.get('finish_reason') or finish
            delta = choice.get('delta', {})
            content = (delta.get('content') or '') + (delta.get('reasoning_content') or delta.get('reasoning') or '')
            if content:
                now = clock()
                if first is None:
                    first = now
                last = now
                count += 1
                digest.update(content.encode())
                if collect_content:
                    chunks.append(content)
    if not done or first is None or not usage or not isinstance(usage.get('completion_tokens'), int):
        raise ValueError('Incomplete stream or missing completion-token usage; no rate can be reported.')
    tokens = usage['completion_tokens']
    if tokens <= 1 or last <= first:
        raise ValueError('Response too short to measure a decode interval.')
    result = {'first': first, 'last': last, 'content_chunks': count, 'usage': usage,
              'decode_tokens_per_second': (tokens - 1) / (last - first),
              'response_sha256': digest.hexdigest(), 'finish_reason': finish}
    if collect_content:
        result['content'] = ''.join(chunks)
    return result


def endpoint(base: str, allow_remote: bool) -> str:
    url = urllib.parse.urlsplit(base)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Use a plain HTTP(S) API base URL without credentials, query or fragment.')
    if not allow_remote and url.hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('Remote requests require --allow-remote.')
    return base.rstrip('/') + '/chat/completions'


def request(url: str, model: str, prompt: str, limit: int, api_key: str | None,
            collect_content=False) -> dict:
    payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.6,
               'top_p': 0.95, 'top_k': 20, 'min_p': 0, 'seed': 42, 'max_tokens': limit,
               'reasoning_effort': 'none', 'chat_template_kwargs': {'enable_thinking': False},
               'cache_prompt': False, 'stream': True, 'stream_options': {'include_usage': True}}
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = 'Bearer ' + api_key
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    start = time.monotonic()
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=900) as response:
            result = parse_stream(response, collect_content=collect_content)
    except urllib.error.HTTPError as error:
        error.close()
        raise
    result['time_to_first_token_seconds'] = result.pop('first') - start
    result.pop('last')
    result['total_seconds'] = time.monotonic() - start
    result['prompt_sha256'] = hashlib.sha256(prompt.encode()).hexdigest()
    return result


def summarize_runs(runs: list[dict]) -> dict:
    """Keep different prompts separate; never silently omit a failed/incomplete sample."""
    groups = {}
    for run in runs:
        if run['usage'].get('prompt_tokens_details', {}).get('cached_tokens', 0):
            raise ValueError('Prefix reuse invalidates this uncached comparison.')
        groups.setdefault(run['prompt_sha256'], []).append(run)
    return {key: {'repetitions': len(values),
                  'median_decode_tokens_per_second': statistics.median(
                      r['decode_tokens_per_second'] for r in values),
                  'min_decode_tokens_per_second': min(r['decode_tokens_per_second'] for r in values),
                  'max_decode_tokens_per_second': max(r['decode_tokens_per_second'] for r in values),
                  'median_total_seconds': statistics.median(r['total_seconds'] for r in values),
                  'output_token_counts': [r['usage']['completion_tokens'] for r in values]}
            for key, values in groups.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080/v1')
    parser.add_argument('--model', default='kervia-strata')
    parser.add_argument('--tokens', type=int, default=768)
    parser.add_argument('--repetitions', type=int, default=3, help='Complete replays of the fixed three-topic order')
    parser.add_argument('--allow-remote', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('benchmark.local.json'))
    opts = parser.parse_args()
    try:
        if not 128 <= opts.tokens <= 4096:
            raise ValueError('Choose a token limit from 128 to 4096.')
        if not 1 <= opts.repetitions <= 20:
            raise ValueError('Choose 1 to 20 repetitions.')
        if opts.output.exists():
            raise FileExistsError('Choose a new output filename.')
        url = endpoint(opts.base_url, opts.allow_remote)
        api_key = os.environ.get('STRATA_API_KEY')
        warm = request(url, opts.model, 'Write a short paragraph about a Python dictionary.', 128, api_key)
        runs = []
        for repetition in range(opts.repetitions):
            for topic_index, topic in enumerate(TOPICS):
                run = request(url, opts.model, 'Write a detailed 1200-word tutorial in English about ' + topic
                              + '. Include code and explain edge cases.', opts.tokens, api_key)
                run.update(repetition=repetition + 1, topic_index=topic_index)
                runs.append(run)
        result = {'schema_version': 2, 'workload': 'kervia-english-code-v1', 'model': opts.model,
                  'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  'max_tokens': opts.tokens, 'warmup_seconds': warm['total_seconds'], 'runs': runs,
                  'repetitions': opts.repetitions, 'per_prompt': summarize_runs(runs),
                  'replay_policy': 'One warmup, then fixed topic order repeated; adaptive expert state is not reset between requests.',
                  'median_decode_tokens_per_second': statistics.median(r['decode_tokens_per_second'] for r in runs),
                  'all_outputs_reached_limit': all(r['usage']['completion_tokens'] == opts.tokens for r in runs),
                  'prefix_cache_note': 'For Strata, start the engine with --prompt-cache 0; the request flag alone is insufficient.'}
        fd = os.open(opts.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(result, out, indent=2)
            out.write('\n')
        print(f"Median decode: {result['median_decode_tokens_per_second']:.2f} tokens/s over {len(runs)} runs.")
        if not result['all_outputs_reached_limit']:
            print('Some answers ended early: inspect token counts before comparing rates.')
        print('Results saved locally without endpoint, credentials, prompt text or response text.')
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f'Benchmark failed ({type(error).__name__}); no valid comparison was produced.\n')


if __name__ == '__main__':
    main()
