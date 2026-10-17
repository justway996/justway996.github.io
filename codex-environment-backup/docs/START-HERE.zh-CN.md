# 先从小项目恢复演练开始

1. 解压完整发行目录，双击 CodexEnvironmentBackup.exe。不能只复制 exe 而丢掉 `_internal`。
2. 新建配置，选择正在开发的工程和本地备份目录。检查范围中是否包括 Codex、工作知识库、自生长，以及必要的来源和素材。缺目录不是“已备份”。可编辑 JSON 增加 roots；每项需要唯一英文 id、path、kind。
3. 创建离线恢复密钥，保存在采集范围之外，转存 U 盘。它能解密所有对应版本，不能随备份上传；丢失后无法恢复。DPAPI 副本只供本 Windows 用户后台使用。
4. 立即备份。状态 local_ready 表示本地校验完成；complete=false 表示采集有缺项。cloud_verified 表示对应版本曾逐卷回读核对；cloud_verified_at 保留完整校验时间，cloud_metadata_checked_at 仅表示当前清单/元数据检查。核对 cloud_check_scope。
5. 选择完整版本与空目录恢复。查看 START-HERE、CONTINUE、RESTORE-REPORT、PATH-MAPPING、PROJECTS.md；原工程在 roots/<id>，原项目卡/规则均保留。含路径映射的 manifest v2 须使用 v0.2.0 或更新版本。
6. 在恢复目录打开新 Codex。先读项目卡和原交接，再核对启动、测试、依赖、数据和重新授权项。原任务暂停时，恢复不等于重新开工。按用户已授权范围验证运行。

## 新电脑

先取得同一发行包，创建新机配置并选择新机数据目录。导入原恢复密钥；授权网盘后运行 versions、fetch 下载所选版本，随后 restore。当前 GUI 支持本地恢复，远端下载使用 CLI 的 `fetch --snapshot-id <ID>`；下载后才可选择本地版本目录恢复。

原 Codex 聊天保存为原始材料和 chats 中的可读导出；不承诺出现在新账号侧栏。原始账号 auth.json、浏览器资料和网盘令牌不迁移。

## 夸克接入

官方仓库当前注明 Windows 需要 WSL。先按微软/夸克官方指引配置 WSL 与官方 CLI，在官方页面完成 OAuth；不要把授权码和令牌贴到聊天或写进本程序配置。

cloud 配置包括 WSL 发行版 distribution、WSL 内官方 `quark-drive.cjs` 的绝对路径 script、目标云端绝对路径 path。目标目录须已存在且用户有权访问。先 cloud-check，再对独立探针目录做上传/下载哈希核对；通过后才将 cloud.enabled 设为 true，随后 backup 会尝试上传并回读校验。

适配器按官方 NDJSON 与完整 Artifact 工作；若工具版本改变、权限/额度不足或需要登录，会停止并保留本地版本。代表样本已完成真实账号上传、发现、下载与恢复；这不等于全部环境或新电脑验收。已验证版本和授权隔离要求见 [夸克安装与接续](QUARK-SETUP.zh-CN.md)。

## 定时任务

发行 exe 支持 install-schedule，默认每 30 分钟检查，可在配置加入 `"schedule": {"interval_minutes": 240}` 改为每 4 小时（范围 1—1440 整数分钟）。当前用户保持登录时运行；默认未注册。点击启用前完成范围、密钥、磁盘容量和小样本演练。注册后的周期从下次登录开始；当前立即运行用“立即备份”。任务使用同发行目录中的 CodexEnvironmentBackupWorker.exe，无控制台窗口。保持整个发行目录位置固定。

Windows 任务计划程序中可找到 CodexEnvironmentBackup-<配置标识>；停用任务不删除版本。每个变化版本独立保存，首版不自动删除历史，大范围频繁备份会持续占用本地和网盘空间。不承诺关机、注销或睡眠期间仍能备份。

## 继续开发工具本身

源码在发行包 source/。先读 README 和 CONTINUE.md，运行测试；继续完整范围、定时和干净 Windows 恢复演练。依赖/缺项如实报告，不把样本验证描述成全环境迁移已验收。
