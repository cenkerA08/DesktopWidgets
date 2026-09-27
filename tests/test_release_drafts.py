import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
import build


class ReleaseDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.notes = self.root/'notes'
        self.notes.mkdir()
        self.draft = self.notes/'next.md'
        self.patcher = patch.multiple(build, NOTES_DIR=self.notes, DRAFT_NOTES=self.draft,
                                      BUILD_DIR=self.root/'build', VERSION='1.0.46')
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_prepare_labels_next_version_and_preserves_edits(self):
        build.prepare_release()
        self.assertEqual(build.read_release_draft()[0], '1.0.47')
        self.draft.write_text('# DesktopWidget 1.0.47\n\nMy release notes.\n')
        build.prepare_release()
        self.assertEqual(build.read_release_draft()[1], 'My release notes.')

    def test_wrong_version_stops_before_build_or_version_change(self):
        self.draft.write_text('# DesktopWidget 2.0.0\n\nA major update.\n')
        with patch.object(build, 'build') as compile_app, patch.object(build, 'write_version') as write:
            with self.assertRaisesRegex(ValueError, 'Notes target 2.0.0'):
                build.release()
            compile_app.assert_not_called()
            write.assert_not_called()

    def test_bundled_notes_match_draft_body(self):
        self.draft.write_text('# DesktopWidget 1.0.47\n\n## Fixed\n- Multiple monitors\n')
        with patch.object(build.subprocess, 'run', side_effect=OSError):
            output = build.write_release_notes('1.0.47')
        data = json.loads(output.read_text())
        self.assertEqual(data, {'version': '1.0.47', 'body': '## Fixed\n- Multiple monitors'})

    def test_placeholder_cannot_be_released(self):
        build.prepare_release()
        with self.assertRaisesRegex(ValueError, 'placeholder'):
            build.release()

    def test_release_is_published_only_after_asset_uploads(self):
        self.draft.write_text('# DesktopWidget 1.0.47\n\nMy notes.\n')
        with patch.object(build.subprocess, 'run', side_effect=OSError):
            build.write_release_notes('1.0.47')
        archive = self.root/'DesktopWidget_v1.0.47.zip'
        archive.write_bytes(b'zip')
        (self.root/'DesktopWidget.sha256').write_text('digest')
        api = Mock()
        created = Mock(status_code=201)
        created.json.return_value = {'upload_url': 'https://example.test/assets{?name}',
                                     'url': 'https://example.test/release', 'assets': []}
        uploaded = Mock(status_code=201)
        api.post.side_effect = [created, uploaded, uploaded]
        with patch.dict('sys.modules', {'requests': api}), patch.dict('os.environ', {'GITHUB_TOKEN': 'test'}):
            build.github_release('1.0.47', archive)
        self.assertTrue(api.post.call_args_list[0].kwargs['json']['draft'])
        self.assertEqual(api.post.call_args_list[0].kwargs['json']['body'], 'My notes.')
        self.assertEqual(api.patch.call_args.kwargs['json'], {'draft': False, 'body': 'My notes.'})

    def test_failed_upload_never_publishes(self):
        self.draft.write_text('# DesktopWidget 1.0.47\n\nMy notes.\n')
        with patch.object(build.subprocess, 'run', side_effect=OSError):
            build.write_release_notes('1.0.47')
        archive = self.root/'release.zip'
        archive.write_bytes(b'zip')
        api = Mock()
        created = Mock(status_code=201)
        created.json.return_value = {'upload_url': 'https://example.test/assets{?name}',
                                     'url': 'https://example.test/release', 'assets': []}
        api.post.side_effect = [created, Mock(status_code=500)]
        with patch.dict('sys.modules', {'requests': api}), patch.dict('os.environ', {'GITHUB_TOKEN': 'test'}):
            with self.assertRaisesRegex(RuntimeError, 'remains a draft'):
                build.github_release('1.0.47', archive)
        api.patch.assert_not_called()
