#!/usr/bin/env python3
"""Exercise violin guards in isolated host stubs; never execute Android binaries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]


def write_executable(path, content):
    path.write_text(content)
    path.chmod(0o755)


def shell_checks():
    tests = []
    for name in ['service.sh', 'customize.sh', 'post-fs-data.sh', 'bin/oahctl',
                 'bin/engine_supervisor.sh', 'bin/violin-preflight.sh']:
        subprocess.run(['sh', '-n', str(REPO / name)], check=True)
    tests.append('shell_syntax')
    with tempfile.TemporaryDirectory(prefix='violin-oah-offline-') as td:
        root = Path(td)
        package = root / 'module'
        (package / 'bin').mkdir(parents=True)
        for name in ['service.sh', 'bin/oahctl', 'bin/engine_supervisor.sh', 'bin/violin-preflight.sh']:
            shutil.copyfile(REPO / name, package / name)
        mock = root / 'mock'
        mock.mkdir()
        marker = root / 'mutation-attempts'
        trap = '#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$MUTATION_MARKER"\nexit 91\n'
        for name in ['mkdir', 'touch', 'chmod', 'setprop', 'kill', 'service', 'mount',
                     'settings', 'reboot', 'ps', 'pidof', 'sleep']:
            write_executable(mock / name, trap)
        write_executable(package / 'bin/fij1673', trap)
        write_executable(mock / 'getprop', '''#!/bin/sh
case "$1" in
ro.product.device) printf '%s' "${MOCK_DEVICE-violin}" ;;
ro.product.vendor.device) printf '%s' "${MOCK_VENDOR_DEVICE-violin}" ;;
ro.build.version.sdk) printf '%s' "${MOCK_SDK-36}" ;;
ro.product.cpu.abi) printf '%s' "${MOCK_ABI-arm64-v8a}" ;;
sys.boot_completed) printf '%s' "${MOCK_BOOTED-1}" ;;
ro.bootmode) printf '%s' "${MOCK_BOOTMODE-normal}" ;;
ro.product.manufacturer) printf Xiaomi ;;
ro.product.brand) printf Xiaomi ;;
esac
''')
        write_executable(mock / 'id', '#!/bin/sh\nprintf "%s\\n" "${MOCK_UID-0}"\n')
        write_executable(mock / 'sha256sum', '''#!/bin/sh
case "$1" in
/system/bin/surfaceflinger) key=sf; hash=288a5ed242100bd3ed7ab0607c3f1ae43c6e37a3d4e57ee594a1bab77a98a374 ;;
/system_ext/lib64/libsurfaceflinger.so) key=impl; hash=d43fd3fd362ab9a42dad9e4797e570583175362e2b01668b04a93f1835f02ad6 ;;
/system/lib64/android.hardware.graphics.composer3-V4-ndk.so) key=composer; hash=8e553fe2c8414f8d422727be4f490ec3d4f89dfee83e4e01544c30962e1f15f4 ;;
*) exit 1 ;;
esac
[ "${MOCK_BAD_HASH-}" = "$key" ] && hash=bad
[ "${MOCK_MISSING-}" = "$key" ] && exit 1
printf '%s  %s\\n' "$hash" "$1"
''')
        env = dict(os.environ, PATH=f'{mock}:/usr/bin:/bin', MUTATION_MARKER=str(marker))

        def run(script, args=(), **overrides):
            result = subprocess.run(['timeout', '4', 'sh', str(package / script), *args],
                                    env=dict(env, **overrides), capture_output=True, text=True)
            assert result.returncode != 124, 'Unexpected long-running command'
            assert not marker.exists(), marker.read_text() if marker.exists() else ''
            return result

        result = run('bin/oahctl', ['preflight'])
        data = json.loads(result.stdout)
        assert result.returncode == 0 and data['ok'] and all(data['checks'].values())
        assert data['injectorPresent'] and not data['runtimeVerified'] and not data['modeSwitchVerified']
        assert not (package / 'config').exists()
        tests.append('matching_profile_read_only_no_injector_execution')

        cases = [
            ('wrong_device', {'MOCK_DEVICE': 'other', 'MOCK_VENDOR_DEVICE': 'other'}, 'device'),
            ('wrong_sdk', {'MOCK_SDK': '35'}, 'sdk36'),
            ('wrong_abi', {'MOCK_ABI': 'armeabi-v7a'}, 'arm64'),
            ('non_root', {'MOCK_UID': '2000'}, 'root'),
            ('boot_incomplete', {'MOCK_BOOTED': '0'}, 'normalSystem'),
            ('recovery_even_if_stale_boot_flag', {'MOCK_BOOTMODE': 'recovery'}, 'normalSystem'),
            ('sf_changed', {'MOCK_BAD_HASH': 'sf'}, 'surfaceflingerHash'),
            ('implementation_changed', {'MOCK_BAD_HASH': 'impl'}, 'implementationHash'),
            ('composer_changed', {'MOCK_BAD_HASH': 'composer'}, 'composerV4Hash'),
            ('missing_implementation', {'MOCK_MISSING': 'impl'}, 'implementationHash'),
        ]
        for name, overrides, key in cases:
            result = run('bin/oahctl', ['preflight'], **overrides)
            data = json.loads(result.stdout)
            assert result.returncode != 0 and not data['ok'] and not data['checks'][key], name
            assert not (package / 'config').exists(), name
            tests.append(name)

        result = run('bin/oahctl', ['preflight'], MOCK_DEVICE='generic')
        assert result.returncode == 0 and json.loads(result.stdout)['checks']['device']
        tests.append('vendor_device_fallback')

        result = run('bin/engine_supervisor.sh', MOCK_BAD_HASH='impl')
        assert result.returncode == 2 and not json.loads(result.stdout)['ok']
        assert not (package / 'config').exists()
        tests.append('supervisor_rejects_changed_firmware_before_runtime_writes')

        for name in ['mkdir', 'touch', 'chmod']:
            (mock / name).unlink()
        result = run('service.sh')
        config = package / 'config/settings.conf'
        assert result.returncode == 0
        assert config.read_text() == 'auto_enabled=0\ninternal_max_enabled=0\n'
        assert 'boot injection disabled' in result.stdout
        tests.append('violin_fresh_defaults_off_and_no_boot_injection')
        config.write_text('auto_enabled=1\ninternal_max_enabled=1\n')
        result = run('service.sh')
        assert result.returncode == 0 and config.read_text() == 'auto_enabled=1\ninternal_max_enabled=1\n'
        assert 'boot injection disabled' in result.stdout
        tests.append('existing_user_settings_preserved_no_boot_injection')
    return tests


if __name__ == '__main__':
    checks = shell_checks()
    print(json.dumps({'hostChecks': checks, 'passed': len(checks),
                      'deviceValidated': False}, indent=2))
