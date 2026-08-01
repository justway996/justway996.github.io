# Codex Skill Toolbox

面向非技术用户的 Codex Skill 工具箱。它提供本地 Skill 扫描、业务分类、工作计划、工作流推荐和安全维护入口。

## 两台电脑开发

### 当前电脑：连接 GitHub 私有仓库

1. 在 GitHub 新建一个空的 **Private** 仓库，不勾选 README、`.gitignore` 或 License。
2. 复制仓库 HTTPS 地址，例如 `https://github.com/<你的账号>/codex-skill-toolbox.git`。
3. 在本项目目录执行：

```powershell
git remote add origin https://github.com/<你的账号>/codex-skill-toolbox.git
git push -u origin feature/codex-toolbox-mvp
```

如需把该分支作为默认开发分支，可在 GitHub 仓库设置中将默认分支设为 `feature/codex-toolbox-mvp`，或在本地将它合并到 `main` 后再推送。

### 下一台电脑：克隆并运行

```powershell
git clone https://github.com/<你的账号>/codex-skill-toolbox.git
cd codex-skill-toolbox
pnpm install
./scripts/check-dev-environment.ps1
pnpm dev
```

需要 Node.js 20 或更新版本、pnpm 和 Windows。首次运行会安装 Electron 依赖，耗时取决于网络。

### 日常同步

开发前：

```powershell
git pull --rebase
```

完成一个独立修改后：

```powershell
git add <相关文件>
git commit -m "feat: 简要说明"
git push
```

不要同步或提交 `node_modules`、`dist`、`release`、`.worktrees`，它们已经被 `.gitignore` 排除。

## 常用命令

```powershell
pnpm test
pnpm build
pnpm dev
pnpm dist
```
