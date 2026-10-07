"""Behavioral tests for safe profile generation; no models or GPUs required."""
import copy
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.kervia_profile import DEFAULT_PROFILE, apply_profile, write_config


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(DEFAULT_PROFILE.read_text())
        self.config = {
            'exe': '/synthetic/engine', 'tokenizer': '/synthetic/tokenizer',
            'args': ['--pack', '/synthetic/pack', '--mtp', '/synthetic/draft',
                     '--native', '/synthetic/model.gguf', '--kv', 'q4_0',
                     '--max-context', '32768', '--prompt-cache', '9'],
            'gpu': 0, 'parallel': 4, 'split_skip_if_fits': True,
            'vision': {'exe': '/synthetic/vision', 'max_tokens': 1024},
            'api_key': 'test-only-placeholder', 'draft_vocab': 'fr',
            'lib_dirs': ['/synthetic/cuda'], 'host': '127.0.0.1', 'port': 18080,
        }

    def value(self, config, flag):
        args = config['args']
        self.assertEqual(args.count(flag), 1)
        return args[args.index(flag) + 1]

    def test_preserves_local_assets_and_does_not_mutate_input(self):
        original = copy.deepcopy(self.config)
        result = apply_profile(self.config, self.profile, [1, 0])
        self.assertEqual(self.config, original)
        for key in ['exe', 'tokenizer', 'vision', 'api_key', 'draft_vocab', 'lib_dirs', 'host', 'port']:
            self.assertEqual(result[key], original[key])
        self.assertEqual(self.value(result, '--native'), '/synthetic/model.gguf')
        self.assertEqual(result['gpu'], [1, 0])
        self.assertEqual(result['parallel'], 1)
        self.assertEqual(result['layer_split'], 'auto')
        self.assertNotIn('split_skip_if_fits', result)
        self.assertEqual(self.value(result, '--max-context'), '131072')
        self.assertEqual(self.value(result, '--kv'), 'int8')
        self.assertEqual(self.value(result, '--prompt-cache'), '6')

    def test_benchmark_disables_checkpoints_and_can_select_prepared_vocab(self):
        self.config['args'] += ['--prompt-cache', '3', '--kv', 'q4_0']
        result = apply_profile(self.config, self.profile, [0, 1], True, 'en')
        self.assertEqual(self.value(result, '--prompt-cache'), '0')
        self.assertEqual(self.value(result, '--kv'), 'int8')
        self.assertEqual(result['draft_vocab'], 'en')

    def test_rejects_non_dual_gpu_selection(self):
        for gpus in [[], [0], [0, 0], [0, 1, 2], [-1, 0], [True, 2], ['0', '1']]:
            with self.subTest(gpus=gpus), self.assertRaises(ValueError):
                apply_profile(self.config, self.profile, gpus)

    def test_rejects_inherited_experiments(self):
        for extra in [['--batch', '2'], ['--layer-split', '24'], ['--batch-mtp'],
                      ['--split-skip-if-fits'], ['--batch=2'], ['--trim-stage-weights'],
                      ['--control-vector', 'example.gguf']]:
            cfg = copy.deepcopy(self.config)
            cfg['args'] += extra
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                apply_profile(cfg, self.profile, [0, 1])

    def test_explicit_profile_placement_and_cli_override(self):
        profile = dict(self.profile, layer_split='23')
        self.assertEqual(apply_profile(self.config, profile, [0, 1])['layer_split'], '23')
        self.assertEqual(apply_profile(self.config, profile, [0, 1], layer_split='auto')['layer_split'], 'auto')
        self.assertEqual(apply_profile(self.config, self.profile, [0, 1])['layer_split'], 'auto')

    def test_rejects_invalid_reference_boundaries(self):
        for split in (True, None, 0, 1, 48, '2,20', '1.5', '-1', '２３'):
            with self.subTest(split=split), self.assertRaises(ValueError):
                apply_profile(self.config, dict(self.profile, layer_split=split), [0, 1])

    def test_rejects_missing_draft_and_malformed_arguments(self):
        for args in [[], ['--mtp'], ['--mtp', '--kv', 'int8'],
                     ['--mtp', 'draft', '--kv'], ['--mtp', 'draft', '--kv=int8'], [None]]:
            cfg = dict(self.config, args=args)
            with self.subTest(args=args), self.assertRaises(ValueError):
                apply_profile(cfg, self.profile, [0, 1])

    def test_rejects_non_cuda_backend(self):
        with self.assertRaises(ValueError):
            apply_profile(dict(self.config, backend='hip'), self.profile, [0, 1])

    def test_rejects_invalid_profile(self):
        for patch in [{'schema_version': 2}, {'gpu_count': 1}, {'engine_options': []},
                      {'engine_options': {'--kv': 8}}, {'conversation_checkpoints': -1}]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                apply_profile(self.config, dict(self.profile, **patch), [0, 1])

    def test_private_exclusive_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.local.json'
            write_config(path, self.config)
            if os.name == 'posix':
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                write_config(path, {'overwrite': True})
            self.assertEqual(path.read_bytes(), before)

    def test_cli_dry_run_and_write_do_not_disclose_or_change_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.json'
            source.write_text(json.dumps(self.config))
            before = source.read_bytes()
            cmd = [sys.executable, str(ROOT / 'tools/kervia_profile.py'), '--config', str(source)]
            dry = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.assertIn('Dry run', dry.stdout)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)
            output = Path(directory) / 'out.local.json'
            written = subprocess.run(cmd + ['--benchmark', '--output', str(output)],
                                     capture_output=True, text=True, check=True)
            self.assertEqual(self.value(json.loads(output.read_text()), '--prompt-cache'), '0')
            again = subprocess.run(cmd + ['--output', str(output)], capture_output=True, text=True)
            self.assertEqual(again.returncode, 2)
            self.assertEqual(source.read_bytes(), before)
            for result in [dry, written, again]:
                self.assertNotIn(self.config['api_key'], result.stdout + result.stderr)
                self.assertNotIn('/synthetic/', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
