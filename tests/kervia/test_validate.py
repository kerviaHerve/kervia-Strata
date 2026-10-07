"""Code validation must fail closed before executing any generated program."""
import shutil
import unittest
from tools.kervia_validate import check_code


class ValidationTests(unittest.TestCase):
    def test_rejects_imports_and_arbitrary_calls(self):
        for source in ['import os', 'def merge_ranges(x):\n return open("/etc/passwd").read()',
                       'def merge_ranges(x):\n return x.__class__']:
            with self.subTest(source=source), self.assertRaises(ValueError):
                check_code(source)

    @unittest.skipUnless(shutil.which('bwrap'), 'Bubblewrap required for isolated execution')
    def test_semantically_wrong_function_fails(self):
        self.assertFalse(check_code('def merge_ranges(ranges):\n return []')['passed'])


if __name__ == '__main__':
    unittest.main()
