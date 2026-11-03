"""Shared, relocatable deployment configuration; never stores a password."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def load_config(path=None):
    config = json.loads(Path(path or ROOT / 'config.json').read_text(encoding='utf-8-sig'))
    expected = {'host', 'ssh_port', 'username', 'remote_dir', 'camera_device',
                'http_port', 'board_python', 'serial_port', 'serial_baud'}
    if set(config) != expected:
        raise ValueError('config.json must contain exactly: ' + ', '.join(sorted(expected)))
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', config['host']):
        raise ValueError('host: use an IPv4 address or DNS name, without http://')
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*', config['username']):
        raise ValueError('Invalid Linux username')
    for key in ('remote_dir', 'camera_device', 'board_python'):
        value = config[key]
        if not re.fullmatch(r'/[A-Za-z0-9_./-]+', value) or '..' in value.split('/') or '//' in value:
            raise ValueError(key + ': absolute Linux path required, without spaces or ..')
    if config['remote_dir'] in ('/', '/home', '/opt', '/usr', '/tmp'):
        raise ValueError('remote_dir must be a dedicated application directory')
    if not config['camera_device'].startswith('/dev/'):
        raise ValueError('camera_device must start with /dev/')
    for key in ('ssh_port', 'http_port'):
        if type(config[key]) is not int or not 1 <= config[key] <= 65535:
            raise ValueError(key + ': expected an integer in 1..65535')
    if config['http_port'] < 1024:
        raise ValueError('http_port must be >=1024 for the unprivileged board service')
    if not isinstance(config['serial_port'], str) or type(config['serial_baud']) is not int or config['serial_baud'] <= 0:
        raise ValueError('Invalid serial settings')
    return config


def base_url(config):
    return 'http://{}:{}'.format(config['host'], config['http_port'])
