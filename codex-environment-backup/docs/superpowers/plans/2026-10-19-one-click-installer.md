# Windows 联网安装包实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution, or superpowers:subagent-driven-development if the user selects that method. Track steps below and keep a plan-specific ledger.

**Goal:** 发布用户双击即可安装、进入中文备份/恢复向导的联网Setup.exe，自动准备网盘依赖。

**Architecture:** 安装器携带完整Windows程序包，独立负责校验、安装和入口创建；组件准备使用持久化状态和实际检测，向导复用现有采集/加密/夸克/恢复接口。管理员步骤与用户数据操作分离，不改变正在运行的v0.2.4备份。

**Tech Stack:** Python 3.12、Tk/ttk、PyInstaller、PowerShell/Windows原生组件、WSL2与已验证的夸克CLI。

**Spec:** ../specs/2026-10-19-one-click-installer-design.md；用户已于2026-10-19批准。

## Global Constraints

- 首版Windows 11 x64，发行版本v0.3.0；保留原有命令行及v1/v2快照能力，最小映射恢复器仍为0.2.0。
- 默认程序目录LOCALAPPDATA/CodexWorkspaceBackup/app/<版本>；配置/数据与程序分离，并通过现有采集范围校验。
- WSL 3.0.3、Ubuntu 26.04.1 x64、Linux Node 24.22.0、夸克CLI 1.0.24固定官方来源与SHA256；WSL MSI还验证Microsoft有效签名。
- 只有系统组件安装申请管理员权限；DPAPI、授权、配置和发行版注册属于原Windows用户。
- 不覆盖已有工程、账号数据库、配置或其他WSL环境；不更改系统默认发行版，不全局关闭WSL，不强制重启。
- 四小时配置使用240分钟，任务保持PT0S/IgnoreNew；恢复向导不会自动启用旧任务。
- Setup.exe必须小于等于50MiB，发布前真实上传/回下载核对。个人数据与凭据不得进入源码、安装包或普通日志。
- 当前536卷快照、v0.2.4验收入口及其正式任务绑定保持原样；所有新安装器本机写入测试使用隔离目录或专用夹具。

## Review Focus

1. 中文、空格、引号或特殊字符路径：路径作为参数传递，不能变成PowerShell/命令行代码；归Task 1与Task 3测试。
2. 断网、坏缓存与重启后的旧状态：重新校验真实组件，错误阶段不能显示成功，也不能执行未通过SHA的文件；归Task 2测试。
3. 已有配置、WSL同名冲突、已有备份正在运行：不覆盖/重建/终止已有资源，不更改原备份程序绑定；归Task 1、3、4测试。
4. 权限拒绝、不同管理员身份及重启待完成：停止管理员步骤，原用户操作不可在管理员子进程中执行，保留可继续状态；归Task 3测试。
5. 恢复目标非空、错误密钥和中途失败：不得覆盖工程、导出凭据或显示已恢复；归Task 4与Task 5安装版验收。

## Task 1：可校验的安装与固定入口

**Files:** 新增src/codex_backup/installer.py、packaging/installer_entry.py、tests/test_installer.py。

**Interfaces:** `install_release(payload: Path, destination: Path) -> dict`校验压缩包和其SHA清单、安装到版本目录，返回安装位置与版本；`create_shortcuts(executable: Path) -> list[Path]`在原用户下创建桌面与开始菜单入口；`installer_main(payload: Path, smoke: bool = False)`提供中文安装窗口。

- [x] RED：test_installer.py验证完整包安装、同版幂等、旧配置保留；绝对路径、..、UNC/驱动器路径、符号链接、重复条目和SHA不符均在写入版本前拒绝；中文/空格/单引号路径不能改变命令语义。先运行并确认因缺实现失败。
- [x] GREEN：安装在新建暂存目录完成，验证后原子置入版本目录；不将下载位置作为长期运行位置，不删除旧版本或用户数据。快捷方式指向固定安装的程序首次向导入口。
- [x] 验证：定向测试通过，原93项回归通过；真实快捷方式写入测试仅针对临时专用入口，测试后只删除自身入口。提交Task 1。

## Task 2：可信下载与可续跑状态

**Files:** 新增src/codex_backup/bootstrap.py、src/codex_backup/setup-dependencies.json、tests/test_bootstrap.py；pyproject.toml补充清单包数据。

**Interfaces:** `download_component(spec: dict, cache: Path, progress=None) -> Path`要求HTTPS并验证固定SHA；`load_setup_state(path: Path) -> dict`、`save_setup_state(path: Path, state: dict)`原子保存步骤和非敏感安装信息。清单逐项定义name、version、url、sha256，不包含授权信息。

- [x] RED：坏SHA、被截断的下载、旧.part、有效缓存、网络失败后重试、旧状态与实际文件不符、第二个安装流程抢占锁等测试先失败。假下载器只用于测试；不能给产品加入跳过校验选项。
- [x] GREEN：缓存目录内临时下载，SHA通过后原子改名；重试复用已验证的组件，重新检查实际状态。所有清理只针对验证位于自身缓存内的精确文件。下载具有连接/读取超时，向导收到可重试步骤与中文原因。
- [x] 验证：从已有官方缓存独立计算清单SHA并核对来源；下载测试通过，状态中无token/key等字段。提交Task 2。

## Task 3：Windows组件、专用环境与官方授权

**Files:** 扩展bootstrap.py；新增src/codex_backup/setup-wsl.ps1、src/codex_backup/setup-quark.sh；tests/test_bootstrap_windows.py；必要时给quark.py补充官方登录包装与回归。

**Interfaces:** `inspect_environment(config: dict) -> dict`只读检测；`prepare_environment(config: dict, state_dir: Path, progress=None) -> dict`按缺项准备并返回state=ready/restart_required/failed及distribution/script；`request_restart_resume(executable: Path, state_dir: Path) -> None`仅登记本工具HKCU RunOnce，重启仍由用户确认；`authorize_cloud(config: dict, progress=None) -> dict`调用官方登录并实际检查网盘连接。

- [x] RED：已有可用环境不得执行安装/终止命令；同名但无所有权标记的发行版不可修改；禁止wsl --shutdown和--set-default；管理员拒绝、重启未完成、配置路径含引号、root身份误用、CLI安装目录可写、无效Microsoft签名与失败登录分别覆盖。
- [x] GREEN：先只读检测，管理员脚本仅执行已校验MSI与系统功能启用；注册发行版、用户和CLI配置在原用户身份下进行。使用专用稳定名称与所有权标记，避免与当前CodexBackup上传环境冲突。Linux侧用普通用户和只读CLI，私有HOME/cwd在采集范围外。
- [x] GREEN：持久化restart_required并登记固定程序入口，用户拒绝重启仍能稍后从桌面继续；成功后仅删除自己的RunOnce值。官方登录打开Windows浏览器，程序只保存本地官方授权状态，日志仅保留步骤及结果码；自动填入发行版、脚本和已授权网盘目录。
- [x] 验证：隔离runner测试通过；在本机真实只读检测WSL/CLI，不启用系统功能、不更新/重启当前WSL。需要干净机器的管理员安装分支保留至第二台Windows验收。提交Task 3。

## Task 4：中文首次使用、云端版本选择与恢复流程

**Files:** 新增src/codex_backup/setup_wizard.py、tests/test_setup_wizard.py；修改app.py以增加首次向导入口并保留原GUI/CLI；必要时scheduler.py增加可核验的初始working状态与回归。

**Interfaces:** `make_backup_config(config_path: Path, roots: list[dict], data_dir: Path) -> dict`使用现有load_config校验，默认schedule.interval_minutes=240、云端在连接验真前不启用；`make_restore_config(config_path: Path, data_dir: Path) -> dict`使用roots=[]且不得直接用于全环境备份；`setup_gui(smoke: bool = False)`提供开始页、备份、恢复及已有配置入口。

- [x] RED：已存在配置不可覆盖、数据目录在采集根内必须阻止、现有E盘配置不被自动改写、恢复配置不安装备份任务、原离线密钥选择、非空恢复目录/错误密钥失败、版本列表为空和下载失败不报成功等测试先失败。
- [x] GREEN：备份流程显示实际采集目录，支持选工程与知识库，确认密钥位置，调用Task 3自动连接并校验网盘；仅在相应检查后启用自动上传或定时。已有配置路径保留原参数与授权，不重新采集/启动运行中的全量。
- [x] GREEN：恢复流程用现有versions/fetch/restore，显示时间、版本与缺项，导入原密钥并恢复到空目录；提供打开恢复位置及接续文件的按钮。支持不用WSL的本地快照恢复。
- [x] GREEN：Tk更新在主线程，长操作在后台；备份使用固定worker，关闭向导不把正在执行的worker当成成功或直接杀掉。恢复仍在执行时给出明确关闭提示。普通用户不需要改JSON或填Linux路径；原高级GUI仍可进入。
- [x] 验证：向导控制逻辑与原回归全绿；打包前启动GUI冒烟；所有自动任务测试使用专用临时配置。提交Task 4。

## Task 5：v0.3.0安装包构建与安装版验收

**Files:** 新增packaging/build-installer.ps1，更新packaging/build.ps1、版本元数据、README.md、CONTINUE.md、docs/NEW-COMPUTER.zh-CN.md；新增docs/INSTALLER.zh-CN.md。验收脚本放本计划独有的忽略目录，不上传个人报告。

- [x] 更新v0.3.0元数据；构建包含Windows运行库、bootstrap资源和官方清单的程序包。Installer使用PyInstaller单文件模式嵌入程序ZIP及其固定哈希，不嵌入大型WSL/Ubuntu下载缓存。
- [x] 运行完整测试，记录实际测试总数；构建Setup.exe及SHA256SUMS，断言Setup.exe <= 50*1024*1024字节、包内不含个人配置、密钥、授权或docs/progress.md。
- [x] 运行真实Setup.exe安装到隔离固定目录，验证快捷方式、程序和worker路径、重复安装及旧配置保留；用安装版做合成文件加密备份、认证、解密恢复和损坏/错误密钥拒绝，核对生成的接续文件。
- [x] 用安装版注册专用四小时夹具，Windows原生查询确认固定worker、PT4H/PT240M、PT0S、IgnoreNew和未来NextRunTime；随后删除夹具。不能注册本机正式任务或改accept-full-backup.py现有v0.2.4绑定。
- [x] 记录本机实测通过项和干净机器仍待验证项，不将模拟runner当作真实首次系统安装通过。提交Task 5。

## Task 6：整体复核、发布与换机交付

- [x] 按requesting-code-review技能准备仅本分支变更与明确需求的评审包，交给全新上下文的审查者；处理阻断项并补充先红后绿回归，最后确认全套测试。
- [ ] 用显式公开文件白名单同步源码到用户GitHub仓库的独立codex-environment-backup目录；新增文件明确列出，不复制个人work、outputs或进度卡，确认站点其他路径无变化。
- [ ] 上传Setup.exe、中文指南、SHA清单，逐文件回下载核对，最后发布工具包完成标记；失败不得称新版工具包已发布成功。保持个人全量上传与其验收状态独立。
- [ ] 更新E:/CodexWorkspaceBackup/使用说明.md、工作知识库项目卡与续接记录，实际读取核验写入；仅记录来源、产物、测试和下一步，不记录凭据或聊天正文。
- [ ] 交付安装包位置与实际通过的验收结果。第二台Windows的首次安装、重启续跑、网盘授权和接续开发仍由后续实机验收确认；没有证据不得标记完成。

## 计划自检

设计的安装、下载、系统准备、重启续跑、用户身份、授权、备份/恢复、兼容、发布与保护现有上传均有对应任务；五类Review Focus均分配了测试。接口名称在本计划一致，不预设尚未运行的新测试数量或干净机器成功状态。不得把计划勾选完成等同于用户整体换机目标已经实现。
