- 使用 uv 管理 python 环境和安装包
- 使用 pnpm 管理 ts 项目的依赖和构建
- 使用 vite 作为 ts 项目的构建工具
- 用 prek (uv add) 作为 git-pre-commit 钩子，确保提交前运行 lint
- 短任务不得自动 commit，必须主动征求用户同意
- 自主运行的长期任务需要在合适的位置 commit，方便未来 debug
- 本地开发配置和服务器部署信息（本地路径、worktree 布局、端口分配、部署方式等）只属于本地环境，不得写进 git 跟踪的文件或 commit message；需要记录时放在已 gitignore 的 `.kimi-code/` 里
- 前端在 `frontend/`（Vue 3 + vue-router + Tailwind v4 + Vite）：
  - `cd frontend && pnpm install && pnpm dev` 启动（5173 端口），vite proxy 把 `/api` 转发到根 `.env` 里 `ANCHOR_PORT` 指定的后端（默认 23119），前端代码统一用相对路径 `/api/v1/...` 调后端
  - pnpm 11 不再读取 package.json 里的 `pnpm` 字段；esbuild 等依赖的构建白名单写在 `frontend/pnpm-workspace.yaml` 的 `allowBuilds`
  - `pnpm build` 产物在 `frontend/dist/`（已 gitignore）；后端启动时若 `ANCHOR_FRONTEND_DIST_DIR`（默认 `./frontend/dist`）下有 `index.html`，会在 `/` 直接托管 SPA，未知路径回落 index.html。改完后端需重启 23119 端口的 uvicorn 才生效
- 迁移生产数据库前必须备份当前数据库到 `backup/` 目录，文件名带时间戳：
  ```bash
  cp "$(uv run python -c 'from anchor_server.config import settings; print(settings.database_url.replace("sqlite:///", ""))')" "backup/anchor_$(date +%Y%m%d_%H%M%S).db"
  ```
- 多端同步（设计见 `docs/sync.md`）：`ANCHOR_ROLE` 取 `standalone`（默认）/ `central` / `device`；中心端必须开 `ANCHOR_AUTH_ENABLED=true`，设备端配 `ANCHOR_CENTRAL_URL` + `ANCHOR_SYNC_TOKEN`，轮询间隔 `ANCHOR_SYNC_INTERVAL`（默认 30s）
- 改动同步协议或被同步的 schema（items/attachments 的字段）时，必须 bump `backend/anchor_server/schemas/sync.py` 里的 `SYNC_PROTOCOL_VERSION`；版本不一致时设备端和中心端会互相拒绝运行
- Notes：每个 item 可通过 `note_path` 字段（相对 `ANCHOR_NOTES_DIR`，默认 `./data/notes`）关联一个 Obsidian 风格 markdown，只读展示、关联仅经 API（PUT item）设置；笔记和图片文件像附件字节一样经 Syncthing 带外同步，DB 只同步 `note_path`
