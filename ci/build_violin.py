#!/usr/bin/env python3
"""Package local module sources with the hash-pinned official ARM64 injector."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import urllib.request
import zipfile

from test_violin import REPO, shell_checks

RELEASE_URL = (
    'https://github.com/Kimuinaii/OPlusAutoHR/releases/download/'
    'v2.0.0-canary1/OPlusAutoHR_V2_Canary_1.0.zip'
)
ARCHIVE_SHA = 'ee0107128e054587f451f749d2f819d259df5aafa51d1d2aadf9797e0b4bf3ac'
RUNTIME_SHA = '65039ccbb03bf6c17a164fea76ab1eb0e6b1bdf1d0676116fdea7229f9d510b1'
ARTIFACT = 'OPlusAutoHR-violin-OS3.0.305-offline1-UNTESTED.zip'
EXTRA_SOURCES = ['LICENSE', 'THIRD_PARTY_NOTICES.md', 'VIOLIN-OFFLINE.md',
                 'bin/violin-preflight.sh']


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def package(archive, host_checks):
    if sha256(archive.read_bytes()) != ARCHIVE_SHA:
        raise ValueError('Official release SHA256 mismatch')
    tracked = set(subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=REPO).decode().split('\0'))
    files = {}
    sources = {}
    with zipfile.ZipFile(archive) as upstream:
        if upstream.testzip() is not None:
            raise ValueError('Official release CRC check failed')
        for entry in upstream.infolist():
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in entry.filename:
                raise ValueError('Unsafe archive entry')
            if entry.is_dir():
                continue
            if entry.filename in files:
                raise ValueError('Duplicate archive entry')
            if entry.filename == 'bin/fij1673':
                files[entry.filename] = upstream.read(entry)
            else:
                sources[entry.filename] = None
                files[entry.filename] = b''
    for name in EXTRA_SOURCES:
        sources[name] = None
    # Every source module file comes from this checkout, never a stale release copy.
    for name in sources:
        if name not in tracked:
            raise ValueError(f'Module source must be tracked: {name}')
        files[name] = (REPO / name).read_bytes()
        sources[name] = sha256(files[name])
    runtime = files['bin/fij1673']
    if sha256(runtime) != RUNTIME_SHA or runtime[:6] != b'\x7fELF\x02\x01':
        raise ValueError('Official injector SHA256 or ELF class mismatch')
    if int.from_bytes(runtime[18:20], 'little') != 183:
        raise ValueError('Injector is not ARM64')
    commit = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    dirty = bool(subprocess.check_output(
        ['git', 'status', '--porcelain'], cwd=REPO, text=True).strip())
    report = {
        'sourceCommit': commit, 'sourceDirty': dirty,
        'artifact': ARTIFACT, 'upstreamReleaseUrl': RELEASE_URL,
        'upstreamArchiveSha256': ARCHIVE_SHA, 'runtimeSha256': RUNTIME_SHA,
        'hostChecks': host_checks, 'sourceFiles': sources,
        'verificationBoundary': 'Host shell stubs and package integrity only; '
                                'archived firmware ELF checks are not rerun in CI.',
        'runtimeExecuted': False, 'installedOnDevice': False,
        'deviceValidated': False, 'modeSwitchVerified': False,
    }
    out = REPO / 'dist'
    out.mkdir(exist_ok=True)
    target = out / ARTIFACT
    manifest = {name: sha256(data) for name, data in sorted(files.items())}
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
            entry.create_system = 3
            executable = name.startswith('bin/') or name.endswith('.sh')
            entry.external_attr = (0o100755 if executable else 0o100644) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(entry, data)
    with zipfile.ZipFile(target) as check:
        if check.testzip() is not None or len(check.namelist()) != len(manifest):
            raise ValueError('Output ZIP integrity check failed')
        if {name: sha256(check.read(name)) for name in check.namelist()} != manifest:
            raise ValueError('Output ZIP contents differ from inputs')
    report.update(sha256=sha256(target.read_bytes()), bytes=target.stat().st_size,
                  files=manifest)
    (out / 'build-verification.json').write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (out / 'SHA256SUMS').write_text(
        f"{report['sha256']}  {target.name}\n", encoding='ascii')
    print(json.dumps({k: report[k] for k in
                      ['sourceCommit', 'sourceDirty', 'artifact', 'sha256',
                       'bytes', 'deviceValidated']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream-zip', type=Path,
                        help='Use a local official release ZIP; SHA256 is still required')
    args = parser.parse_args()
    checks = shell_checks()
    with tempfile.TemporaryDirectory(prefix='oah-pinned-release-') as temporary:
        archive = args.upstream_zip
        if archive is None:
            archive = Path(temporary) / 'official.zip'
            request = urllib.request.Request(RELEASE_URL, headers={'User-Agent': 'OAH-violin-CI'})
            with urllib.request.urlopen(request, timeout=60) as response:
                archive.write_bytes(response.read())
        package(archive, checks)
