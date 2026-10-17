# 覆盖与恢复规则

| 内容 | 当前规则 |
|---|---|
| 工程与普通 Git | 不依据 .gitignore 排除；保存暂存区、工作目录、未跟踪文件和空目录。 |
| Git worktree | 管理目录、common Git 目录均已采集且布局可识别时，重写恢复副本的三处路径并记录哈希；外部、自定义配置、object alternates 标 unsupported。 |
| 目录联接 / 其他链接 | Windows junction 的真实目标已在采集范围时保存映射并在恢复目录重建；目标丢失、被排除、在范围外及其他 reparse point 标 unsupported，不静默跟随。 |
| 子模块 / 外部服务 | 检测到 .gitmodules 或 compose 文件时列待核对项，不因文件复制成功而承诺数据齐全。 |
| SQLite | backup API；只读环境无法打开时取主文件+WAL稳定副本并完整性检查。持续变化停止；不承诺所有服务同一瞬时一致。 |
| 登录凭据 | 排除 auth.json、credentials.json、token(s).json、浏览器资料应不在选定根；用户需重新登录。项目 .env 默认只进加密材料。 |
| 明确排除 | 根配置 exclude 列出相对目录或文件；报告排除项。排除明确的临时运行目录、Codex provisioning guard、根 .sqlite-maintenance.lock 及 tmp/arg0、arg0-windows 下的 .lock；项目 poetry.lock、yarn.lock 等依赖锁保留。 |
| Codex/插件/Skills | 选定目录的实际文件；工具授权需重新连接。路径不正确、库在不同 SQLite 根时须显式补进 roots，先检查覆盖。 |
| 知识库 | 作为独立根保存笔记、附件、Bases、模板及所选配置；原工程与资料不搬进库；外部引用另核对。 |
| 规则/项目卡 | 保留原文、草案和暂停状态；新机规则不会被自动覆盖。CONTINUE 是快照摘要，不建立第二套持续待办。 |
| 工程索引 | package.json、pyproject.toml、requirements.txt 所在工程建立声明索引，跳过依赖缓存内部的工程声明；记录同目录锁文件/交接来源哈希及选定项目卡哈希。未识别工程须按原目录检查。 |
| 聊天导出 | JSONL 文本消息；可识别历史数据库的 thread_items；未知 schema 明确报告，原始数据仍保存。 |
| 本地服务/驱动 | 只保存配置不能代表数据可恢复。容器、WSL、运行数据库等须专门导出并验证，首版不自动执行。 |
| 运行验证 | 初始 environment_checked/project_verified/handoff_checked 均为 false；不会因文件解压成功而设 ready_to_continue。 |

文件校验、运行、接续和跨机分别报告。未知依赖、失效引用、语义交接过时需人工/Codex核对；当前版本不会声称已自动推断全部依赖或开发意图。
