#!/system/bin/sh
# Local experimental adaptation; original OPlusAutoHR authors and LICENSE apply.
# Read-only: emit JSON to stdout; do not start the engine or create runtime files.
MODDIR="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
DEVICE="$(getprop ro.product.device)"
[ "$DEVICE" = violin ] || DEVICE="$(getprop ro.product.vendor.device)"
SDK="$(getprop ro.build.version.sdk)"
ABI="$(getprop ro.product.cpu.abi)"
BOOTED="$(getprop sys.boot_completed)"
BOOTMODE="$(getprop ro.bootmode)"

matches_hash() {
  actual="$(sha256sum "$1" 2>/dev/null)"
  [ "${actual%% *}" = "$2" ]
}

device=false; [ "$DEVICE" = violin ] && device=true
sdk=false; [ "$SDK" = 36 ] && sdk=true
abi=false; [ "$ABI" = arm64-v8a ] && abi=true
normal=false
[ "$BOOTED" = 1 ] && [ "$BOOTMODE" != recovery ] && normal=true
root=false; [ "$(id -u)" = 0 ] && root=true
sf=false
matches_hash /system/bin/surfaceflinger 288a5ed242100bd3ed7ab0607c3f1ae43c6e37a3d4e57ee594a1bab77a98a374 && sf=true
impl=false
matches_hash /system_ext/lib64/libsurfaceflinger.so d43fd3fd362ab9a42dad9e4797e570583175362e2b01668b04a93f1835f02ad6 && impl=true
composer=false
matches_hash /system/lib64/android.hardware.graphics.composer3-V4-ndk.so 8e553fe2c8414f8d422727be4f490ec3d4f89dfee83e4e01544c30962e1f15f4 && composer=true
injector=false
for path in "$MODDIR/bin/fij1673" /data/local/tmp/oplusautohr_beta/fij1673; do
  [ -x "$path" ] && injector=true
done

ok=false
if $device && $sdk && $abi && $normal && $root && $sf && $impl && $composer; then
  ok=true
fi
printf '{"ok":%s,"scope":"static_prerequisites_only","profile":"violin-OS3.0.305.0.WOTCNXM","checks":{"device":%s,"sdk36":%s,"arm64":%s,"normalSystem":%s,"root":%s,"surfaceflingerHash":%s,"implementationHash":%s,"composerV4Hash":%s},"injectorPresent":%s,"runtimeVerified":false,"modeSwitchVerified":false}\n' \
  "$ok" "$device" "$sdk" "$abi" "$normal" "$root" "$sf" "$impl" "$composer" "$injector"
$ok
