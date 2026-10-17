# Codex 工作环境备份

Windows 备份工具 v0.2.0。本地采集、加密分卷、空目录恢复、可读聊天归档、工程索引、知识库链接报告和中文操作窗口已实现。**代表样本的夸克往返与中断续传已通过；完整环境、跨电脑恢复、定时任务长期运行尚未验收。**

## 当前能做什么

- 保存用户选定的工程、未提交和未跟踪文件、普通 Git 仓库、Skills 配套文件和知识库。
- Windows 长路径、早期文件时间戳已验证。已采集范围内的目录联接可重建；Git worktree 在管理目录和 common Git 目录均已保存时，只改写恢复副本的路径，并记录改写前后哈希。外部或自定义布局列为缺项。
- 为 SQLite 在线备份；受只读限制时校验未变化的主文件与 WAL 副本，再生成独立数据库。
- 生成 AES-256-GCM 加密分卷与校验清单，完整版本独立恢复。默认分卷 32 MiB；当前夸克接口实测单文件下载上限 50 MiB，上传前拦截超限分卷。旧版 64 MiB 分卷仍可在本地恢复，但须重新打包才能通过该接口上传。
- 本机密钥由 Windows DPAPI 保护；另存离线恢复密钥用于换电脑。
- 恢复到空目录，生成路径映射、覆盖/缺项、聊天导出、链接和继续开发报告。不会覆盖当前 Codex 账号数据库，也不自动执行恢复的脚本。
- PROJECTS.md/PROJECTS.json 列出工程位置、声明的运行环境与命令、锁文件和交接来源哈希。索引只读取声明，不代表命令已运行或全部外部依赖已找齐。
- 通过夸克官方 CLI 的 WSL 适配上传和下载；中文、空格文件名和分页已实测。每个新设备仍须安装依赖、授权并验证连接。

## 使用

发行目录中的 `CodexEnvironmentBackup.exe` 双击打开中文窗口。命令行也支持：

```powershell
.\CodexEnvironmentBackup.exe inspect --config C:\BackupConfig\config.json
.\CodexEnvironmentBackup.exe new-key --config C:\BackupConfig\config.json --key-file F:\Codex-recovery.key
.\CodexEnvironmentBackup.exe backup --config C:\BackupConfig\config.json
.\CodexEnvironmentBackup.exe restore --config C:\BackupConfig\config.json --snapshot C:\BackupData\outbox\<版本ID> --destination D:\RestoredWorkspace
```

创建配置时必须逐项确认工程、Codex 目录和两个知识库。输出目录放在所有采集根之外；恢复密钥放在采集范围和备份数据之外，建议离线 U 盘。先做一个小项目的恢复演练，再扩大范围。

详细步骤见 [START-HERE](docs/START-HERE.zh-CN.md)；换机入口见 [新电脑接续](docs/NEW-COMPUTER.zh-CN.md)；采集边界见 [coverage-rules](docs/coverage-rules.zh-CN.md)。

## 开发与构建

Python 3.12+，安装项目依赖后：

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
python -m codex_backup gui-smoke
python -m codex_backup
```

构建：`packaging/build.ps1 -Python <python.exe路径>`。发行包带必要运行库；源码也随包交付。构建环境需 PyInstaller 与 cryptography；`requirements-lock.txt` 是本次实际测试的版本。

## 不误报完整

外部 Git worktree、子模块、非目录联接的符号链接、容器/WSL 服务数据、外部依赖和项目运行命令需专门核对；当前版本对可检测情况报告缺项，不承诺自动导出全部外部服务。未知数据库 schema 保留原始数据并报告无法导出的聊天。知识库别名、跨库 URI 和硬编码路径生成检查提示，不盲目改写。

含目录联接或 Git worktree 映射的快照使用 manifest v2，至少需要 v0.2.0 恢复器；旧恢复器会拒绝，不会静默遗漏映射。新版本兼容旧 v1 快照。

新版本上传后逐卷下载核对；以后定时检查已验证版本时，核对远端卷的存在、大小及 envelope/COMPLETE 的哈希，保留上次完整字节校验时间。同大小密文损坏须在再次下载校验时发现，不把元数据检查时间当作新的全量校验。

项目运行验证和交接语义验证默认未通过，需在恢复后按原项目步骤实测。源码仓库只保存程序、文档和脱敏测试；真实配置、聊天、备份数据和恢复密钥不应提交。
