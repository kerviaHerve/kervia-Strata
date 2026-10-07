"""Streaming metric and HTTP boundary tests with synthetic fixtures only."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
import unittest
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.kervia_bench import endpoint, parse_stream, request, summarize_runs


def event(value):
    return b'data: ' + json.dumps(value).encode() + b'\n\n'


def content(value):
    return event({'choices': [{'delta': {'content': value}}]})


def stream():
    return [event({'choices': [{'delta': {'role': 'assistant'}}]}), content('hello'),
            content(' world'), event({'usage': {'completion_tokens': 9, 'prompt_tokens': 12}}),
            b'data: [DONE]\n']


@contextmanager
def server(handler):
    instance = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{instance.server_port}/v1'
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=5)


class BenchmarkTests(unittest.TestCase):
    def test_content_collection_is_opt_in_and_retains_finish_reason(self):
        lines = stream()[:-1] + [event({'choices': [{'delta': {}, 'finish_reason': 'length'}]}), stream()[-1]]
        result = parse_stream(lines, clock=iter([0., 2.]).__next__, collect_content=True)
        self.assertEqual(result['content'], 'hello world')
        self.assertEqual(result['finish_reason'], 'length')

    def test_repetitions_are_grouped_by_input_not_pooled(self):
        runs = [{'prompt_sha256': p, 'decode_tokens_per_second': rate,
                 'total_seconds': 10., 'usage': {'completion_tokens': tokens}}
                for p, rate, tokens in [('a', 100, 768), ('b', 20, 512), ('a', 120, 768)]]
        summary = summarize_runs(runs)
        self.assertEqual(summary['a']['median_decode_tokens_per_second'], 110)
        self.assertEqual(summary['a']['repetitions'], 2)
        self.assertEqual(summary['b']['output_token_counts'], [512])
        runs[0]['usage']['prompt_tokens_details'] = {'cached_tokens': 64}
        with self.assertRaises(ValueError):
            summarize_runs(runs)

    def test_stream_rate_excludes_role_and_uses_first_content_even_at_zero(self):
        result = parse_stream(stream(), clock=iter([0.0, 2.0]).__next__)
        self.assertEqual(result['first'], 0.0)
        self.assertEqual(result['content_chunks'], 2)
        self.assertEqual(result['decode_tokens_per_second'], 4.0)
        self.assertEqual(len(result['response_sha256']), 64)
        self.assertNotIn('hello', json.dumps(result))

    def test_reasoning_deltas_count_as_content(self):
        lines = [event({'choices': [{'delta': {'reasoning_content': 'plan'}}]}), content('answer'),
                 event({'usage': {'completion_tokens': 4}}), b'data: [DONE]\n']
        self.assertEqual(parse_stream(lines, clock=iter([1., 2.]).__next__)['content_chunks'], 2)

    def test_rejects_truncated_and_unmeasurable_streams(self):
        for lines in [stream()[:-1], stream()[:3] + stream()[-1:],
                      [content('one'), event({'usage': {'completion_tokens': 1}}), b'data: [DONE]\n'],
                      [event({'error': {'message': 'synthetic failure'}})],
                      [content('only chunk'), event({'usage': {'completion_tokens': 10}}), b'data: [DONE]\n']]:
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                parse_stream(lines, clock=iter([1., 2.]).__next__)

    def test_endpoint_loopback_and_explicit_remote(self):
        for base in ['http://127.0.0.1:8080/v1', 'http://localhost:8080/v1/', 'http://[::1]:8080/v1']:
            self.assertTrue(endpoint(base, False).endswith('/v1/chat/completions'))
        with self.assertRaises(ValueError):
            endpoint('https://example.invalid/v1', False)
        self.assertEqual(endpoint('https://example.invalid/v1', True),
                         'https://example.invalid/v1/chat/completions')

    def test_rejects_embedded_credentials_and_non_http_urls(self):
        for base in ['file:///tmp/example', 'http://user:password@localhost/v1',
                     'http://localhost/v1?api_key=placeholder', 'http://localhost/v1#fragment']:
            with self.subTest(base=base), self.assertRaises(ValueError):
                endpoint(base, True)

    def test_real_local_http_stream_and_request_settings(self):
        received = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                received.update(path=self.path, auth=self.headers.get('Authorization'),
                                body=json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                for line in stream():
                    self.wfile.write(line)
                    self.wfile.flush()
                    time.sleep(0.002)

        with server(Handler) as base:
            result = request(endpoint(base, False), 'synthetic-model', 'synthetic prompt', 128, 'test-placeholder')
        self.assertEqual(received['path'], '/v1/chat/completions')
        self.assertEqual(received['auth'], 'Bearer test-placeholder')
        self.assertEqual(received['body']['max_tokens'], 128)
        self.assertFalse(received['body']['cache_prompt'])
        self.assertTrue(received['body']['stream_options']['include_usage'])
        self.assertGreater(result['decode_tokens_per_second'], 0)
        self.assertGreaterEqual(result['total_seconds'], result['time_to_first_token_seconds'])
        for private in ['test-placeholder', 'synthetic prompt', base]:
            self.assertNotIn(private, json.dumps(result))

    def test_redirect_is_not_followed(self):
        paths = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                paths.append(self.path)
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(307)
                self.send_header('Location', '/unexpected')
                self.end_headers()

        with server(Handler) as base:
            with self.assertRaises(urllib.error.HTTPError):
                request(endpoint(base, False), 'synthetic-model', 'synthetic prompt', 128, 'test-placeholder')
        self.assertEqual(paths, ['/v1/chat/completions'])


if __name__ == '__main__':
    unittest.main()
