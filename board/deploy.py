"""Upload this package, preserve existing settings, install an enabled service.

First contact displays the SSH fingerprint for comparison with the physical board.
Neither board passwords nor this computer's host keys are included in the package.
"""
import argparse
import base64
import getpass
import hashlib
import os
import shlex
import sys
import time
import uuid
from pathlib import Path
import paramiko
from configuration import ROOT, base_url, load_config


class VerifyFirstKey(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        digest = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        print('\nFirst connection to {}: {} SHA256:{}'.format(hostname, key.get_name(), digest))
        print('Compare with the same key on the board console:')
        print('  ssh-keygen -lf /etc/ssh/ssh_host_*_key.pub -E sha256')
        if input('Fingerprint matches your board? Type yes to save it: ').strip().lower() != 'yes':
            raise paramiko.SSHException('Host key was not accepted.')
        client.get_host_keys().add(hostname, key.get_name(), key)
        client.save_host_keys(str(ROOT / 'board' / 'known_hosts.local'))


def run(client, command, password=None, timeout=120):
    if password is not None:
        command = 'sudo -S -p "" -- sh -c ' + shlex.quote(command)
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    if password is not None:
        stdin.write(password + '\n')
        stdin.flush()
    stdin.channel.shutdown_write()
    channel = stdout.channel
    deadline = time.monotonic() + timeout
    # Drain both streams to avoid a full SSH pipe blocking deployment output.
    while True:
        if channel.recv_ready():
            print(channel.recv(65536).decode('utf-8', 'replace'), end='', flush=True)
        if channel.recv_stderr_ready():
            print(channel.recv_stderr(65536).decode('utf-8', 'replace'), end='', flush=True)
        if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
            break
        if time.monotonic() > deadline:
            channel.close()
            raise TimeoutError('Remote command timed out; inspect ore-vision service on the board.')
        time.sleep(.05)
    code = channel.recv_exit_status()
    if code:
        raise RuntimeError('Remote command failed (exit {}). See output above.'.format(code))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--check', action='store_true', help='Read-only SSH/dependency/device check; no installation')
    args = parser.parse_args()
    config = load_config(args.config)
    password = os.environ.get('B220_PASSWORD') or getpass.getpass('Board SSH/sudo password (not saved): ')
    client = paramiko.SSHClient()
    host_keys = ROOT / 'board' / 'known_hosts.local'
    if host_keys.exists():
        client.load_host_keys(str(host_keys))
    client.set_missing_host_key_policy(VerifyFirstKey())
    try:
        client.connect(config['host'], port=config['ssh_port'], username=config['username'],
                       password=password, look_for_keys=False, allow_agent=False,
                       timeout=10, auth_timeout=15, banner_timeout=15)
        code = 'import sys,cv2,numpy; print(sys.version); print("OpenCV",cv2.__version__,"NumPy",numpy.__version__)'
        run(client, shlex.quote(config['board_python']) + ' -c ' + shlex.quote(code))
        run(client, 'ls -l ' + shlex.quote(config['camera_device']))
        if args.check:
            print('SSH, board dependencies and camera device check passed. No installation performed.')
            return
        stage = '/tmp/b220-ore-' + uuid.uuid4().hex
        run(client, 'mkdir -m 700 ' + shlex.quote(stage))
        with client.open_sftp() as sftp:
            sftp.mkdir(stage + '/ps')
            sftp.mkdir(stage + '/ps/badges')
            files = [p for p in (ROOT / 'src' / 'ps').rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py', '.json', '.html', '.png')]
            for path in files:
                target = stage + '/ps/' + path.relative_to(ROOT / 'src' / 'ps').as_posix()
                sftp.put(str(path), target)
            sftp.put(str(ROOT / 'board' / 'install_board.sh'), stage + '/install_board.sh')
        print('Uploaded {} application files. Staging directory: {}'.format(len(files), stage))
        # The installer makes a backup before replacing any existing application.
        arguments = [stage + '/install_board.sh', config['remote_dir'], config['username'],
                     config['camera_device'], str(config['http_port']), config['board_python']]
        run(client, 'bash ' + ' '.join(shlex.quote(value) for value in arguments), password=password)
        print('\nService installed and enabled. Open ' + base_url(config) + '/')
        print('Run board/check_live.py for frame freshness; installation alone is not a camera accuracy test.')
        print('Staging files retained for diagnosis at: ' + stage)
    finally:
        client.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print('\nDeployment stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
