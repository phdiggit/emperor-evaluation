# GitHub 发布与认证规范

本仓库的 GitHub 发布流程以本地持久认证为准，不依赖 Codex 的会话型 GitHub 插件做长流程发布。

## 推荐方案

1. `git` 远端使用 SSH。
2. `gh` CLI 负责创建 PR、补正文、切换 ready for review。
3. 认证信息只在本机长期保存，不依赖临时会话重连。

## 首次配置

### 1. 切换远端

将 `origin` 指向 SSH 地址：

```bash
git remote set-url origin git@github.com:phdiggit/emperor-evaluation.git
```

### 2. 登录 GitHub CLI

安装并登录 `gh` 后，后续 PR 操作都走本地 CLI：

```bash
gh auth login
```

### 3. 配置 SSH key

为当前机器准备 GitHub SSH key，并确保 SSH agent 可用。完成后，本地 `git push` 应该不再依赖 HTTPS 凭据。

## 常用发布流程

```bash
git push -u origin <branch>
gh pr create --base GPT --head <branch> --title "<title>" --body "<body>" --draft
gh pr ready <pr-number>
```

如果希望一次性完成，也可以在创建 PR 后立即调用 `gh pr ready`。

## 约定

- 长时间运行的发布任务优先使用 SSH + `gh`，不要把发布稳定性押在临时插件会话上。
- 如果 `gh` 不可用，先补齐本机认证，再执行 PR 流程。
- 该规范只描述稳定发布链路，不改变仓库的数据或评分流程。
