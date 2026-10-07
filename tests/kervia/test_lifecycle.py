"""A repeated prompt alone is not proof that checkpoint restore worked."""
from unittest import TestCase
from unittest.mock import patch
from tools.kervia_lifecycle import prefix_gate


def record(cached=0, retrieval=True):
    return {'usage': {'prompt_tokens': 32000, 'prompt_tokens_details': {'cached_tokens': cached}},
            'retrieval_passed': retrieval, 'sustained_generation': True, 'within_context': True}


class PrefixGateTests(TestCase):
    def test_cache_reuse_and_correctness_are_both_required(self):
        for cached, retrieval, expected in [(0, True, False), (31990, False, False), (31990, True, True)]:
            with self.subTest(cached=cached, retrieval=retrieval), patch(
                    'tools.kervia_lifecycle.long_gate', side_effect=[record(), record(cached, retrieval)]):
                self.assertEqual(prefix_gate('http://127.0.0.1:1/v1', 'test', '.')['passed'], expected)
