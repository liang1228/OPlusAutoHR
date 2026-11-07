# OPlusAutoHR violin 离线实验适配

这是基于 Kimu / 酷安 @苦力小怕 / 酷安 @念来过倒别叫你 / ChatGPT 的
OPlusAutoHR V2 Canary 1.0 制作的本地修改版，不是作者官方构建。
原项目：https://github.com/Kimuinaii/OPlusAutoHR
基线提交：40e758c16ce9de5823d098c5050409b2199028b4。
保留原作者署名、LICENSE 和用户协议，仅供非商业研究测试。

## 当前状态

目标为小米平板 7S Pro / violin / 星玄 O1，离线参考固件
OS3.0.305.0.WOTCNXM、Android 16。尚未在平板上安装或运行此修改版。
这不是 Recovery 功能，也不修改 Recovery。

- 原厂系统 Composer3 V4 的 6 项必需方法匹配；DMC 两个切换函数和 6 个捕获入口匹配。
- 保留上游 Composer3 HWC + SurfaceFlinger DMC 路径，不使用高通专用 drm_dp 控制节点。
- 增加 `preflight` 只读命令，检查机型、SDK、ABI、正常系统、root 及 3 个精确 ELF 哈希。
- violin 的 supervisor 在预检失败时退出，不创建运行目录、不启动注入器。
- violin 的开机脚本不启动注入；首次默认关闭外屏自动最高刷新和内屏最高刷新锁定。
  原有用户配置仍会保留。手动打开 WebUI 的引擎、状态查询或应用模式可能启动引擎。
- 外屏支持哪些分辨率/刷新率、真实切换、渲染调度、插拔回退均未实测。
  符号匹配不证明对象布局、调用线程和运行 ABI 一定正确。
- 不启用 External Pacesetter 实验。源码中两个 getter 未在此固件的动态导出表中找到；
  这不等于 Scheduler 全部缺失，也不证明运行时一定无法捕获。

## 注入器与包

源码仓库不含 `bin/fij1673`；官方 v2.0.0-canary1 Release 含此 ARM64 ELF。
本地测试 ZIP 使用官方 Release 中未修改的注入器，文件 SHA256：
`65039ccbb03bf6c17a164fea76ab1eb0e6b1bdf1d0676116fdea7229f9d510b1`。
它仅被静态检查，没有在电脑或平板执行。

ZIP 是待实测的实验模块，不是已经验收的成品。模块 ID 仍为 `oplusautohr.v2`，
安装时会更新同 ID 原版模块；本次没有安装。
除上述已核对固件外，其他构建会被 violin 的哈希预检拒绝。

## 后续只读检查

在正常 Android 中，以 root 执行已安装模块的以下命令：

```sh
sh /data/adb/modules/oplusautohr.v2/bin/oahctl preflight
```

也可以对未安装、单独解包的目录运行 `sh <解包目录>/bin/oahctl preflight`。
该命令仅向标准输出打印 JSON，不创建配置或日志、不启动引擎。
不要把 `status` 当成只读预检：上游 `status` 在引擎离线时会调用 `ensure_engine`。

`ok=true` 只表示静态前提满足，`injectorPresent` 独立报告注入器是否存在；
`runtimeVerified` 和 `modeSwitchVerified` 始终为 false。
后续仍需连接外屏，读取实际 HWC/SF 模式，先人工验证一次切换及回退。
平板上的用户产物应放真实内部存储 Download；当前所有新增产物只在电脑。

## GitHub 云端构建

修改分支：`liang1228/OPlusAutoHR` 的 `violin-os3.0.305`。
推送此分支后，Actions 的 `Build violin experimental module` 自动执行：

1. 检查 3 个 JavaScript 文件语法，并运行 16 项隔离 shell 检查。
2. 下载固定的官方 v2.0.0-canary1 Release，校验 ZIP 和注入器 SHA256。
3. 使用当前提交的模块源码覆盖官方包，保留未修改的官方 ARM64 注入器。
4. 上传实验 ZIP、`SHA256SUMS` 和 `build-verification.json`，保留 30 天。

这里的云端构建是测试和打包，不是从源码编译闭源注入器，也不构建 Recovery。
CI 不上传或使用原厂固件文件，不重做本地 ELF 符号检查，不连接或安装到设备。
成功构建只证明所列主机检查与产物完整性，不代表外屏切换已通过实测。
可在已有 Actions 运行页面选择重新运行；产物报告记录确切源码提交与每个文件哈希。

在 Linux 主机上本地复现（Python 3、Git、POSIX shell、GNU timeout）：

```sh
python3 ci/test_violin.py
python3 ci/build_violin.py
# 已有官方 ZIP 时可离线复现，哈希校验仍然强制执行：
python3 ci/build_violin.py --upstream-zip /path/to/OPlusAutoHR_V2_Canary_1.0.zip
```

输出位于 `dist/`，不会将工作目录、日志、配置或系统库打入模块。
