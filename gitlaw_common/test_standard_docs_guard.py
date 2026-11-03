import unittest
import build as B


class DocumentationGuardTest(unittest.TestCase):
    def test_docs_cannot_write_law(self):
        for path in ('a/s-1.md', 'a/assets/anything.png'):
            with self.assertRaises(B.CorpusError):
                B.check_documentation_paths({'acts': [{'slug': 'a'}]}, {path: 'text'})
        B.check_documentation_paths({'acts': [{'slug': 'a'}]}, {'a/README.md': 'index', 'data/acts.json': '{}'})


if __name__ == '__main__':
    unittest.main()
