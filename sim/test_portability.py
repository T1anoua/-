"""Exercise relocated paths, configurable deployment and input rejection without a board."""
import json
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'board'))
from configuration import load_config, base_url
import deploy


class PortabilityTests(unittest.TestCase):
    def test_external_configuration_and_validation(self):
        config = load_config()
        with tempfile.TemporaryDirectory(prefix='b220 config ') as directory:
            path = Path(directory) / '配置.json'
            custom = dict(config, host='10.42.0.99', username='demo', http_port=8010,
                          remote_dir='/home/demo/ore', camera_device='/dev/video2')
            path.write_text(json.dumps(custom), encoding='utf-8-sig')
            self.assertEqual(base_url(load_config(path)), 'http://10.42.0.99:8010')
            for key, value in [('host', '192.168.2.99;whoami'), ('http_port', 80),
                               ('http_port', True), ('remote_dir', '/tmp/../etc'),
                               ('remote_dir', '/home'), ('camera_device', '/etc/passwd'),
                               ('username', 'xilinx;id')]:
                with self.subTest(key=key, value=value):
                    path.write_text(json.dumps(dict(custom, **{key: value})), encoding='utf-8')
                    with self.assertRaises(ValueError):
                        load_config(path)

    def test_custom_deployment_uploads_complete_package(self):
        config = dict(load_config(), host='board.example', username='demo',
                      http_port=8010, remote_dir='/home/demo/ore', camera_device='/dev/video2')
        with tempfile.TemporaryDirectory(prefix='b220 deploy ') as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(config), encoding='utf-8')
            client = mock.MagicMock()
            sftp = client.open_sftp.return_value.__enter__.return_value
            with mock.patch.object(deploy.paramiko, 'SSHClient', return_value=client), \
                 mock.patch.object(deploy, 'run') as run, \
                 mock.patch.object(deploy.getpass, 'getpass', return_value='test-only'), \
                 mock.patch.dict(deploy.os.environ, {}, clear=True), \
                 mock.patch.object(sys, 'argv', ['deploy.py', '--config', str(path)]), \
                 contextlib.redirect_stdout(io.StringIO()):
                deploy.main()
            self.assertEqual(client.connect.call_args.args[0], 'board.example')
            self.assertEqual(client.connect.call_args.kwargs['username'], 'demo')
            uploads = [call.args[0] for call in sftp.put.call_args_list]
            self.assertEqual(sum(Path(p).suffix == '.png' for p in uploads), 52)
            self.assertTrue(any(Path(p).name == 'settings.json' for p in uploads))
            self.assertTrue(any(Path(p).name == 'install_board.sh' for p in uploads))
            install_command = run.call_args_list[-1].args[1]
            self.assertIn('/home/demo/ore demo /dev/video2 8010', install_command)
            self.assertEqual(run.call_args_list[-1].kwargs['password'], 'test-only')
            client.close.assert_called_once()

    def test_check_does_not_upload_or_install(self):
        client = mock.MagicMock()
        with mock.patch.object(deploy.paramiko, 'SSHClient', return_value=client), \
             mock.patch.object(deploy, 'run') as run, \
             mock.patch.object(deploy.getpass, 'getpass', return_value='test-only'), \
             mock.patch.dict(deploy.os.environ, {}, clear=True), \
             mock.patch.object(sys, 'argv', ['deploy.py', '--check']), \
             contextlib.redirect_stdout(io.StringIO()):
            deploy.main()
        client.open_sftp.assert_not_called()
        self.assertEqual(run.call_count, 2)
        self.assertTrue(all('password' not in call.kwargs for call in run.call_args_list))

    @unittest.skipUnless(sys.platform == 'win32', 'Windows EXE resource check')
    def test_exe_relocated_with_custom_board_address(self):
        with tempfile.TemporaryDirectory(prefix='b220 移动应用 ') as directory:
            folder = Path(directory)
            exe = folder / 'b220_ore_app.exe'
            shutil.copy2(ROOT / 'src' / 'pc' / 'b220_ore_app.exe', exe)
            config = dict(load_config(), host='10.42.0.99', http_port=8010)
            (folder / 'config.json').write_text(json.dumps(config), encoding='utf-8')
            result = subprocess.run([str(exe), '--prepare-only'], timeout=20)
            self.assertEqual(result.returncode, 0)
            import os
            page = Path(os.environ['LOCALAPPDATA']) / 'B220OreVision/cache/10.42.0.99_8010/launcher.html'
            content = page.read_text(encoding='utf-8')
            self.assertIn('http://10.42.0.99:8010', content)
            self.assertNotIn('@@BOARD_', content)
            self.assertNotIn('192.168.2.99', content)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows desktop shortcut check')
    def test_desktop_install_in_temporary_directory(self):
        with tempfile.TemporaryDirectory(prefix='b220 desktop ') as directory:
            folder = Path(directory)
            app = folder / '应用'
            desktop = folder / '桌面'
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                     '-File', str(ROOT / 'src/pc/install_desktop.ps1'),
                                     '-InstallDirectory', str(app), '-DesktopDirectory', str(desktop)],
                                    timeout=30, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            self.assertEqual((app / 'config.json').read_bytes(), (ROOT / 'config.json').read_bytes())
            self.assertEqual((app / 'b220_ore_app.exe').read_bytes(), (ROOT / 'src/pc/b220_ore_app.exe').read_bytes())
            self.assertEqual(len(list(desktop.glob('*.lnk'))), 1)
            result = subprocess.run([str(app / 'b220_ore_app.exe'), '--prepare-only'], timeout=20)
            self.assertEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
