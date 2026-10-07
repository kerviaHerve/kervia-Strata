"""Numeric evidence and denominator checks; no GPU needed."""
import unittest
from tools.kervia_metrics import parse_engine_log


class MetricsTests(unittest.TestCase):
    def test_resident_share_includes_pcie_in_denominator(self):
        log = '''strata serve: prompt 48 tokens = 0 reused + 48 read in 360 ms (133.3 tok/s), 768 generated in 5874 ms (130.7 tok/s), drafts accepted 495 of 644, 0 checkpoints
strata serve: decode expert cache hit rate: 92.8% (397284 hits / 428305 lookups); 12335 more read by the GPU over PCIe or from another GPU (2.8% of all 440640 routed)
'''
        request = parse_engine_log(log)['requests'][0]
        self.assertEqual(request['experts']['total_routed'], 440640)
        self.assertAlmostEqual(request['experts']['resident_fraction'], 397284/440640)
        self.assertEqual(request['experts']['cpu_remainder'], 31021)

    def test_bad_counters_fail_instead_of_becoming_a_result(self):
        log = 'prompt 10 tokens = 0 reused + 10 read in 20 ms, 8 generated in 50 ms, drafts accepted 2 of 3\n'
        with self.assertRaises(ValueError):
            parse_engine_log(log + '(5 hits / 8 lookups); 4 more (all 11 routed)')

    def test_only_numeric_evidence_is_exported(self):
        log = '''/private/path with credential-placeholder
strata generate: PCIe probe: 28.9 GB/s
strata generate: layer split: CUDA1 PCIe probe 14.5 GB/s
strata generate: layer split auto: K=21
strata generate: layer split: CUDA0 loads the dense weights of layers 0-20 only
strata generate: --pipeline-windows 2 is off: incompatible
'''
        result = parse_engine_log(log)
        self.assertEqual(result['pcie_probes'], [28.9, 14.5])
        self.assertEqual(result['auto_boundary'], 21)
        self.assertEqual(result['trimmed_stages'], [[0, 0, 20]])
        self.assertTrue(result['pipeline_disabled'])
        self.assertNotIn('private', str(result))


if __name__ == '__main__':
    unittest.main()
