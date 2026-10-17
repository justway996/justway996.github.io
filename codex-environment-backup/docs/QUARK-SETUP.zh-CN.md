# 夸克安装与换机接续

2026-10-17 实测组合：WSL 3.0.3、Ubuntu 26.04.1、Node 24.22.0 Linux x64、夸克官方 CLI 1.0.24-29460f9。实际 CLI 是 `download --fid <FID> --output-dir <目录>`，返回 `result.data.filePath`；安装包附带的 `read-file` 文档与该二进制不一致。升级后先核对 `--help`，再运行独立探针。

## 安装约定

1. 在新 Windows 安装并验证 WSL2。系统组件启用后若提示需要重启，先正常重启。发行版单独使用 `CodexBackup`，避免修改已有开发用 Linux。
2. 从 [微软发行清单](https://raw.githubusercontent.com/microsoft/WSL/master/distributions/DistributionInfo.json) 取得 Ubuntu 官方镜像地址和 SHA256。在线安装下载停滞时，下载并核对整文件哈希，再用 `wsl --install --from-file <镜像> --name CodexBackup --no-launch` 安装。
3. 从 [Node 官网](https://nodejs.org/dist/latest-v24.x/) 下载 Linux x64 LTS 包，并用同目录 SHASUMS256.txt 核对。Linux 中解压到 `/opt/codex-quark`，将其 node 放入专用用户 PATH。
4. 从 [夸克官方仓库](https://github.com/quark-clouddrive/quarkclouddrive_offical) 提供的版本接口取得官方 ZIP，核对当前版本。将完整 scripts 放到 `/opt/codex-quark/1.0.24/scripts`，文件与父目录由 root 拥有、普通用户不可写；保留同包 hash-worker.cjs，不能只复制主脚本。
5. 创建专用非 root 用户 `codexbackup`，设为该发行版默认用户。验证 `wsl -d CodexBackup --exec id`。不要用 root 运行备份适配器。

官方 CLI 优先向可写的安装目录保存状态，缺配置时还可能读取 HOME 下的旧授权。本适配器要求只读安装，并将工作目录与 HOME 都设为当前配置的 `data_dir/quark-runtime`。此目录包含本机授权状态，须放在采集范围之外，换机重新授权。

## 官方授权

用与程序相同的私有运行目录启动 `login`，设置 `CODEX_ENV=1`，由用户在官方浏览器页面确认；不把授权码或令牌发给 Codex。WSL 的浏览器桥接必须确实打开 Windows 浏览器，不能仅返回成功。

例如先通过 `wslpath -a <Windows数据目录>` 取得 Linux 目录，再运行：

```bash
env --chdir=/mnt/c/BackupData/quark-runtime HOME=/mnt/c/BackupData/quark-runtime CODEX_ENV=1 \
  node /opt/codex-quark/1.0.24/scripts/quark-drive.cjs login
```

以上数据目录只是示例，须预先创建并换成当前配置的真实路径。浏览器未打开或授权超时时，在本机终端完成处理，不把凭据粘贴进聊天。

## 新电脑或新 Codex 账号

1. 获取完整发行包或本工具源码，读取 README、CONTINUE 与本文件。确认空恢复目录和本机数据目录。
2. 使用原离线恢复密钥导入本机；原 DPAPI 文件无法代替跨机密钥。密钥独立保管，不上传网盘或源码仓库。
3. 安装上述 Linux/CLI，重新授权同一网盘可访问账号。配置 distribution=`CodexBackup`、script=`/opt/codex-quark/1.0.24/scripts/quark-drive.cjs` 和用户指定的网盘 path。
4. 运行 cloud-check，再用 versions 找到版本，fetch 下载并认证，最后 restore 到空目录。GUI 的本地恢复入口可选择下载完成的版本；CLI 参数见 `--help`。
5. 在恢复目录读 CONTINUE、RESTORE-REPORT、PATH-MAPPING。按映射定位原项目、聊天归档和知识库，核对原项目卡、当前任务、依赖、锁文件、测试与素材；实测运行后才能说可以继续开发。

已完成代表样本真实云端往返与同机恢复后项目测试。64 MiB 分卷、过期授权、长时间断网、全范围定时、干净 Windows 和新账号接续仍需验证。聊天保留为原始数据和可读归档，不承诺自动出现在另一个账号的侧栏。
