# 修仙模拟器 —— Git 协作指南

> **适用场景**: 4 人团队，3 周冲刺开发  
> **平台**: GitHub / Gitee（码云）  
> **分支策略**: Trunk Based Development（主分支 + 短生命周期功能分支）

---

## 一、平台选择：GitHub vs Gitee

| 维度 | GitHub | Gitee |
|---|---|---|
| 访问速度 | 国内可能不稳定（需科学上网） | 国内访问快 |
| 私有仓库 | 免费 | 免费（5 人以内） |
| CI/CD | GitHub Actions | Gitee Go |
| 生态 | 全球最大，工具链丰富 | 国内友好，与飞书等集成好 |
| Issue/PR | 功能完善 | 功能类似，界面中文 |

**建议**：如果团队都在国内且没有稳定的科学上网条件，**用 Gitee**；如果熟悉 GitHub 且网络没问题，**用 GitHub**。两者操作几乎一样，本指南以 GitHub 为例，Gitee 对应功能名称相同。

---

## 二、仓库结构

**一个仓库还是多个？**

建议**一个仓库**，用目录分离前后端和 Agent：

```
xiuxian-simulator/          <-- 根目录（一个仓库）
├── frontend/               <-- 人员A负责
├── backend/                <-- 人员B负责
├── agent/                  <-- 人员C负责
├── content/                <-- 人员D负责
├── docs/                   <-- 接口契约文档（全员维护）
└── README.md
```

**为什么不分仓库**：3 周时间太短，多仓库会增加同步成本（子模块、npm link 等）。一个仓库 + 目录隔离足够。

---

## 三、分支策略

```
main        <-- 主分支，永远可运行，不能直接 push
  │
  ├── frontend/dev    (人员A)
  ├── backend/dev     (人员B)
  ├── agent/dev       (人员C)
  └── content/dev     (人员D)
```

**规则**：
- `main` 分支只能通过 **Pull Request（PR）** 合并，不能直接 push
- 每人从 `main` 切出自己的开发分支
- 功能完成后发 PR，至少 **1 人 Review** 后才能合并
- 里程碑日（Day 5, Day 12, Day 19）所有分支合并到 `main`，打标签

---

## 四、仓库初始化（Day 1 执行）

### 4.1 创建仓库（任选一人执行，推荐人员B）

**方式一：网页创建**
1. 打开 GitHub / Gitee
2. 点击 "New Repository"
3. 名称：`xiuxian-simulator`
4. 选择 "Private"（私有仓库）
5. 勾选 "Add README.md"
6. 创建

**方式二：命令行创建**

```bash
# 本地初始化
mkdir xiuxian-simulator
cd xiuxian-simulator
git init

# 创建目录结构
mkdir frontend backend agent content docs

# 添加基础文件
echo "# 修仙模拟器" > README.md

# 创建 .gitignore
cat > .gitignore << 'EOF'
# Frontend
frontend/node_modules/
frontend/dist/
frontend/.env

# Backend
backend/__pycache__/
backend/*.pyc
backend/.env
backend/venv/

# Agent
agent/__pycache__/
agent/*.pyc
agent/.env

# Content
content/tools/__pycache__/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
EOF

# 提交初始代码
git add .
git commit -m "chore: init project structure"

# 关联远程仓库（替换为实际地址）
git remote add origin https://github.com/your-team/xiuxian-simulator.git
git push -u origin main
```

### 4.2 添加协作者

在 GitHub / Gitee 仓库设置中：
1. 进入 Settings -> Manage access（或 成员管理）
2. 添加其他 3 位队友的账号
3. 权限选择 "Write"（可推送代码）

### 4.3 每人首次拉取

```bash
# 克隆仓库
git clone https://github.com/your-team/xiuxian-simulator.git
cd xiuxian-simulator

# 创建自己的开发分支
git checkout -b frontend/dev    # 人员A
git checkout -b backend/dev     # 人员B
git checkout -b agent/dev       # 人员C
git checkout -b content/dev     # 人员D

# 推送到远程（建立远程分支）
git push -u origin frontend/dev   # 人员A
```

---

## 五、日常协作流程

### 5.1 每天的工作循环

```bash
# Step 1: 每天开始工作前，拉取 main 最新代码
git checkout main
git pull origin main

# Step 2: 切换到自己的分支，合并 main 的更新
git checkout frontend/dev
git merge main
# 如果有冲突，见第 7 节"冲突处理"

# Step 3: 写代码... 写代码...

# Step 4: 提交前检查：改了哪些文件
git status

# Step 5: 添加修改的文件（建议逐个确认，不要直接用 git add .）
git add frontend/src/components/TextDisplay.tsx
git add frontend/src/types/game.ts

# Step 6: 提交（遵循 Conventional Commits 规范，见第 6 节）
git commit -m "feat(frontend): add TextDisplay with typewriter effect"

# Step 7: 推送到远程
git push origin frontend/dev
```

### 5.2 提交前自检清单

每次 `git commit` 前确认：
- [ ] 我只修改了我负责的目录（A 不改 B 的代码）
- [ ] 我没有提交敏感信息（API Key、密码）
- [ ] 代码能在本地运行（至少不报错）
- [ ] 提交信息符合规范（第 6 节）

### 5.3 里程碑合并（Day 5, Day 12, Day 19）

**必须通过 Pull Request 合并到 main**，不能直接 push。

**合并前准备**：

```bash
# 1. 确保自己的分支包含最新 main
git checkout main
git pull origin main
git checkout frontend/dev
git merge main
# 解决冲突（如有）
git push origin frontend/dev
```

**发起 PR（网页操作）**：
1. 打开 GitHub / Gitee 仓库页面
2. 点击 "Pull Requests" -> "New Pull Request"
3. 源分支（compare）：`frontend/dev`
4. 目标分支（base）：`main`
5. 填写 PR 标题和描述（见下方模板）
6. @ 至少 1 个队友 Review
7. Review 通过后，点击 "Merge pull request"

**PR 描述模板**：

```markdown
## 修改内容
- 实现了 TextDisplay 组件的打字机效果
- 修复了状态面板数值不更新的问题

## 关联文档
- 基于 docs/api-contract.md v1.0
- 修改了 docs/frontend-interface.md

## 测试情况
- [x] 本地 npm run dev 可正常运行
- [x] 打字机效果在 Chrome/Firefox 测试通过
- [x] 接口符合 api-contract.md

## 截图（如有 UI 改动）
[粘贴截图]
```

### 5.4 里程碑打标签

```bash
# Day 5 里程碑
git checkout main
git pull origin main
git tag -a v0.1-week1 -m "Week 1 milestone: end-to-end runnable"
git push origin v0.1-week1

# Day 12 里程碑
git tag -a v0.2-week2 -m "Week 2 milestone: MVP feature complete"
git push origin v0.2-week2

# Day 19 里程碑（最终版）
git tag -a v1.0-mvp -m "v1.0 MVP: demo ready"
git push origin v1.0-mvp
```

---

## 六、提交规范（Conventional Commits）

### 6.1 格式

```
<type>(<scope>): <description>

[可选：详细说明]

[可选：关联 Issue #123]
```

### 6.2 Type（提交类型）

| Type | 含义 | 示例 |
|---|---|---|
| `feat` | 新功能 | `feat(frontend): add save/load modal` |
| `fix` | 修复 bug | `fix(backend): correct cultivation calculation` |
| `docs` | 文档修改 | `docs: update api-contract.md` |
| `style` | 代码格式（不影响逻辑） | `style(frontend): format with prettier` |
| `refactor` | 重构 | `refactor(agent): simplify prompt builder` |
| `perf` | 性能优化 | `perf(frontend): optimize text rendering` |
| `test` | 添加测试 | `test(backend): add event trigger tests` |
| `chore` | 构建/工具变动 | `chore: add docker-compose.yml` |
| `merge` | 合并分支/解决冲突 | `merge: resolve conflict in App.tsx` |

### 6.3 Scope（作用域）

| Scope | 对应模块 |
|---|---|
| `frontend` | 前端代码 |
| `backend` | 后端代码 |
| `agent` | Agent 叙事层 |
| `content` | 内容配置 |
| `docs` | 文档 |
| `api` | 接口契约 |

### 6.4 好的 vs 不好的提交示例

```bash
# ❌ 不好的示例
git commit -m "update"
git commit -m "fix bug"
git commit -m "aaa"
git commit -m "20250713"

# ✅ 好的示例
git commit -m "feat(backend): implement cultivation attribute calculation"
git commit -m "fix(agent): resolve JSON parse error when LLM returns markdown"
git commit -m "docs: add free input processing specification"
git commit -m "test(backend): add unit tests for event trigger conditions"
git commit -m "chore: add Makefile for dev/build commands"
```

---

## 七、冲突处理

### 7.1 场景：push 时被拒绝（别人先推送了）

```bash
git push origin frontend/dev
# 报错：! [rejected]  frontend/dev -> frontend/dev (fetch first)
```

**解决**：

```bash
# 1. 拉取远程更新
git pull origin frontend/dev

# 2. 如果有冲突，Git 会提示：
#    Auto-merging frontend/src/App.tsx
#    CONFLICT (content): Merge conflict in frontend/src/App.tsx

# 3. 打开冲突文件，找到冲突标记：
#    <<<<<<< HEAD
#    你的修改
#    =======
#    别人的修改
#    >>>>>>> origin/frontend/dev

# 4. 手动编辑，保留需要的代码，删除冲突标记（<<<<<<< / ======= / >>>>>>>）

# 5. 标记冲突已解决
git add frontend/src/App.tsx

# 6. 提交（使用 merge 提交，不要改提交信息）
git commit

# 7. 重新推送
git push origin frontend/dev
```

### 7.2 场景：main 更新了，自己的分支落后太多

```bash
# 每天开始工作前执行
git checkout main
git pull origin main
git checkout frontend/dev
git merge main
# 如果有冲突，按 7.1 解决
```

### 7.3 减少冲突的 4 个技巧

1. **按目录隔离**：人员A 只改 `frontend/`，人员B 只改 `backend/`，天然减少冲突
2. **文档变更走 PR**：`docs/` 目录容易冲突，必须发 PR 让全组 Review
3. **不要长时间不 push**：本地积累大量修改再 push，冲突概率指数上升
4. **内容配置用独立文件**：人员D 给每个事件建独立 YAML 文件，不要所有人改同一个文件

---

## 八、GitHub/Gitee 项目管理

### 8.1 Issue 跟踪 Bug 和任务

**创建 Issue 时打标签**：

| 标签 | 用途 |
|---|---|
| `bug` | Bug 报告 |
| `feature` | 新功能请求 |
| `docs` | 文档相关 |
| `P0-blocker` | 阻塞级（不修复无法进行） |
| `P1-important` | 重要（影响体验） |
| `P2-nice-to-have` | 锦上添花 |

**Issue 模板**（在项目设置中配置）：

```markdown
## 问题描述
清晰描述 Bug 或需求

## 复现步骤
1. 进入 xx 场景
2. 点击 xx
3. 看到错误

## 预期行为
应该发生什么

## 实际行为
实际发生了什么

## 环境
- 分支：frontend/dev
- 浏览器：Chrome 120
- 提交：abc1234
```

### 8.2 Milestone 管理里程碑

在 GitHub / Gitee 上创建 Milestone：

| Milestone | 截止日期 | 目标 |
|---|---|---|
| Week 1 基础 | Day 5 | 端到端可运行 |
| Week 2 主体 | Day 12 | MVP 功能完整 |
| Week 3 交付 | Day 19 | 演示就绪 |

把 Issue 和 PR 关联到对应的 Milestone，方便追踪进度。

### 8.3 关联 Issue 和 PR

在 PR 描述中写 `Closes #123` 或 `Fixes #123`，合并 PR 后自动关闭对应 Issue。

---

## 九、与开发计划文档的配合

### 9.1 契约文档变更流程

`docs/` 下的接口契约（GameState Schema、API 契约、Agent IO 格式）变更时：

1. 在自己的分支修改文档
2. 提交：`git commit -m "docs: update gamestate-schema.md - add free_input_history field"`
3. 推送到远程：`git push origin your-branch`
4. 发起 PR，@ 全组 Review
5. **全组在站会上确认后**，才能合并到 main
6. 合并后，各负责人根据新契约更新自己的代码

### 9.2 文档与代码的同步规则

**铁律**：`docs/` 目录的变更优先于代码。如果文档改了，代码必须在 24 小时内跟进。

### 9.3 必须发 PR 的情况

以下变更不允许直接 push 到 main，必须走 PR + Review：
- `docs/` 目录的任何文件
- `main` 分支的合并
- 跨目录的修改（如人员A 改了 `backend/` 的文件）
- 删除文件
- 修改 `.gitignore`

以下变更可以在自己的 dev 分支直接 push：
- 自己负责目录内的日常开发
- 添加测试文件
- 修改 README（非接口文档部分）

---

## 十、快速参考卡

### 10.1 每日必用命令

```bash
# 开始工作
git checkout main && git pull origin main
git checkout your-branch && git merge main

# 提交代码
git status                          # 查看修改
git diff                            # 查看具体改动
git add <file1> <file2>             # 添加指定文件
git commit -m "type(scope): desc"   # 提交
git push origin your-branch         # 推送

# 查看历史
git log --oneline -10               # 最近 10 条提交
git log --graph --oneline           # 图形化分支历史
```

### 10.2 紧急操作

```bash
# 查看某文件的历史修改
git log -p frontend/src/App.tsx

# 撤销工作区的修改（未 add）
git checkout -- frontend/src/App.tsx

# 撤销暂存区的修改（已 add 未 commit）
git reset HEAD frontend/src/App.tsx

# 修改最后一次提交（未 push 时）
git commit --amend -m "新的提交信息"

# 回滚到上一个版本（慎用，会丢失修改）
git reset --hard HEAD~1

# 查看某个提交改了什么
git show abc1234
```

### 10.3 分支管理

```bash
# 查看所有分支
git branch -a

# 切换到某个分支
git checkout branch-name

# 创建并切换新分支
git checkout -b new-branch

# 删除本地分支（已合并）
git branch -d branch-name

# 删除远程分支
git push origin --delete branch-name

# 从远程拉取新分支
git fetch origin
git checkout -b agent/dev origin/agent/dev
```

---

## 十一、常见问题

### Q1：我不小心把 API Key 提交到仓库了怎么办？

**答**：
1. 立即在 GitHub/Gitee 上删除该 Key（使其失效）
2. 生成新 Key
3. 从 Git 历史中删除敏感信息：
   ```bash
   git filter-branch --force --index-filter \
   'git rm --cached --ignore-unmatch 文件路径' \
   HEAD
   git push origin main --force
   ```
4. 将 Key 放到 `.env` 文件，并确保 `.env` 在 `.gitignore` 中

### Q2：我改了文件但想先不提交，切换分支怎么办？

**答**：
```bash
# 暂存当前修改
git stash

# 切换分支做别的事
git checkout other-branch

# 回来恢复修改
git checkout your-branch
git stash pop
```

### Q3：队友的 PR 改了 docs/，我需要等合并后才能继续吗？

**答**：不需要等。你可以在本地先合并队友的分支：
```bash
git checkout your-branch
git merge teammate-branch
# 基于新文档继续开发
```
等队友的 PR 合并到 main 后，再统一 merge main。

### Q4：如何查看某个文件是谁改的？

**答**：
```bash
git blame frontend/src/App.tsx
# 或
git log -p -- frontend/src/App.tsx
```

---

> **总结**：3 周时间紧，Git 协作的目标是"不拖后腿"。记住三个核心原则：**每天 pull main**、**commit 前检查**、**里程碑日 PR 合并**。不要把时间花在解决复杂的 Git 冲突上——按目录隔离、频繁 push、小步提交，冲突自然会少。
