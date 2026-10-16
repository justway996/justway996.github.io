import json
import unittest
from codex_backup.quark import parse_output


class QuarkTests(unittest.TestCase):
    def test_partial_failure_is_failure_even_with_zero_exit(self):
        lines = [dict(type='list', code=0, data={'fileId': 'one'}),
                 dict(type='result', code=31003, data={'successCount': 1, 'failedCount': 1})]
        with self.assertRaises(RuntimeError):
            parse_output('\n'.join(json.dumps(x) for x in lines), 0)

    def test_exit_failure_overrides_success_result(self):
        with self.assertRaises(RuntimeError):
            parse_output('{"type":"result","code":0,"data":{}}', 1)

    def test_missing_result_and_noise_rejected(self):
        for text in ['', 'not-json', '{"type":"progress"}']:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                parse_output(text, 0)

    def test_valid_artifact_and_notice_preserved(self):
        output = '\n'.join(json.dumps(x) for x in [dict(type='result', code=0, data={'hasMore': False}, notice={'text': 'real notice'}),
                          dict(type='artifact', data={'file_path': '/tmp/list.jsonl'})])
        result, records = parse_output(output, 0)
        self.assertEqual(result['notice']['text'], 'real notice')
        self.assertEqual(records[-1]['type'], 'artifact')
