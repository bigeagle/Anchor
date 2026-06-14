- 使用 uv 管理 python 环境和安装包
- 使用 pnpm 管理 ts 项目的依赖和构建
- 使用 vite 作为 ts 项目的构建工具
- 用 prek (uv add) 作为 git-pre-commit 钩子，确保提交前运行 lint
- 短任务不得自动 commit，必须主动征求用户同意
- 自主运行的长期任务需要在合适的位置 commit，方便未来 debug
- 迁移生产数据库前必须备份当前数据库到 `backup/` 目录，文件名带时间戳：
  ```bash
  cp "$(uv run python -c 'from anchor_server.config import settings; print(settings.database_url.replace("sqlite:///", ""))')" "backup/anchor_$(date +%Y%m%d_%H%M%S).db"
  ```
