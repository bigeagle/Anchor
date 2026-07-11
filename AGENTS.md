- 使用 uv 管理 python 环境和安装包
- 使用 pnpm 管理 ts 项目的依赖和构建
- 使用 vite 作为 ts 项目的构建工具
- 用 prek (uv add) 作为 git-pre-commit 钩子，确保提交前运行 lint
- 短任务不得自动 commit，必须主动征求用户同意
- 自主运行的长期任务需要在合适的位置 commit，方便未来 debug
- 前端在 `frontend/`（Vue 3 + vue-router + Tailwind v4 + Vite）：
  - `cd frontend && pnpm install && pnpm dev` 启动（5173 端口），vite proxy 把 `/api` 转发到后端 23119 端口，前端代码统一用相对路径 `/api/v1/...` 调后端
  - pnpm 11 不再读取 package.json 里的 `pnpm` 字段；esbuild 等依赖的构建白名单写在 `frontend/pnpm-workspace.yaml` 的 `allowBuilds`
  - `pnpm build` 产物在 `frontend/dist/`（已 gitignore）；后端启动时若 `ANCHOR_FRONTEND_DIST_DIR`（默认 `./frontend/dist`）下有 `index.html`，会在 `/` 直接托管 SPA，未知路径回落 index.html。改完后端需重启 23119 端口的 uvicorn 才生效
- 迁移生产数据库前必须备份当前数据库到 `backup/` 目录，文件名带时间戳：
  ```bash
  cp "$(uv run python -c 'from anchor_server.config import settings; print(settings.database_url.replace("sqlite:///", ""))')" "backup/anchor_$(date +%Y%m%d_%H%M%S).db"
  ```
