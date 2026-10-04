#!/usr/bin/env python3
"""Apply a reviewed local plugin replacement without overwriting upstream changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import time

BUNDLE = Path(__file__).resolve().parent


def digest(content):
    return hashlib.sha256(content).hexdigest()


def replace(target, original, replacement, mode):
    descriptor, name = tempfile.mkstemp(prefix='.herdr-v2-fix-', dir=target.parent)
    staged = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        staged.chmod(mode)
        if target.is_symlink() or target.read_bytes() != original:
            raise ValueError('Plugin changed during installation; nothing was overwritten.')
        os.replace(staged, target)
    finally:
        staged.unlink(missing_ok=True)


def main():
    config = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, default=config / 'opencode/herdr-tui-session.js')
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument('--apply', action='store_true', help='Back up and apply the reviewed fix')
    operation.add_argument('--restore', type=Path, metavar='BACKUP', help='Restore an exact stock backup')
    args = parser.parse_args()
    target = args.target.expanduser().absolute()
    manifest = json.loads((BUNDLE / 'manifest.json').read_text())
    if target.is_symlink() or not target.is_file():
        raise ValueError('Target must be an existing regular file, not a symbolic link.')
    original = target.read_bytes()
    current = digest(original)
    mode = stat.S_IMODE(target.stat().st_mode)

    if args.restore:
        replacement = args.restore.expanduser().read_bytes()
        if digest(replacement) != manifest['stock_sha256']:
            raise ValueError('Backup is not the reviewed stock plugin; refusing to restore it.')
        if current == manifest['stock_sha256']:
            print('Stock plugin is already installed. No changes made.')
            return
        if current != manifest['patched_sha256']:
            raise ValueError('Plugin has changed since patching; refusing to overwrite the newer file.')
        replace(target, original, replacement, mode)
        print(f'Restored stock plugin: {target}')
        print('Relaunch affected OpenCode terminals to load the restored plugin; do not stop Herdr.')
        return

    replacement = (BUNDLE / 'herdr-tui-session.js').read_bytes()
    if digest(replacement) != manifest['patched_sha256']:
        raise ValueError('Bundled fix failed its checksum. No changes made.')
    if current == manifest['patched_sha256']:
        print('Local fix is already installed. No changes made.')
        return
    if current != manifest['stock_sha256']:
        raise ValueError('Unrecognized plugin version or local edits. No changes made. '
                         'Review the new upstream plugin before adapting this workaround.')
    if not args.apply:
        print(f'Compatible stock plugin: {target}')
        print('Check only: no changes made. Use --apply to install with a backup.')
        return

    state = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')
    backups = state / 'herdr-opencode-v2-fix'
    backups.mkdir(parents=True, mode=0o700, exist_ok=True)
    backup = backups / f'herdr-tui-session-{time.time_ns()}.js.backup'
    with backup.open('xb') as stream:
        stream.write(original)
    backup.chmod(0o600)
    replace(target, original, replacement, mode)
    print(f'Installed local fix: {target}')
    print(f'Backup: {backup}')
    print(f'Restore: python3 {BUNDLE / "manage.py"} --target {target} --restore {backup}')
    print('Relaunch affected OpenCode terminals to load the fix; do not stop Herdr.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error))
