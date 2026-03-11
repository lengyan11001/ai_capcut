# reddit_comment2video 部署与您需完成的配置

## 已在项目内完成

- **后端代码**：`ai_capcut/backends/reddit_comment2video/`（脚本、配置、模板、README）。
- **Skill 文档**：`ai_capcut/skills/reddit_comment2video/SKILL.md`。
- **能力 ID**：`skill.reddit_comment2video`（需在平台注册并在管理后台分配给用户）。

## 需要您完成的配置

### 1. TikHub API Key（必填）

用于抓取 Reddit 数据。未配置则生成会报错。

**操作：**

- 在运行后端的机器上设置环境变量（若用 systemd，在 service 的 `Environment=` 中配置）：
  ```bash
  TIKHUB_API_KEY=你的TikHub密钥
  ```
- 若已按下面「服务器上的部署」使用 systemd，则编辑：
  ```bash
  sudo vi /etc/systemd/system/reddit-comment2video.service.d/override.conf
  ```
  （vi：按 `i` 进入编辑，改完后按 `Esc`，输入 `:wq` 回车保存退出。）
  增加一行：
  ```ini
  Environment="TIKHUB_API_KEY=你的TikHub密钥"
  ```
  然后：
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl restart reddit-comment2video.service
  ```

### 2. TOS 上传（选填）

不配置则视频只生成在服务器本地，接口返回的 `public_url` 为空。

**操作：** 在同一 override 文件中增加（替换为您的真实值）；若端口改为 8003，可增加 `Environment="PORT=8003"`：

```ini
Environment="REDDIT_COMMENT2VIDEO_TOS_ACCESS_KEY=您的access_key"
Environment="REDDIT_COMMENT2VIDEO_TOS_SECRET_KEY=您的secret_key"
Environment="REDDIT_COMMENT2VIDEO_TOS_ENDPOINT=tos-cn-guangzhou.volces.com"
Environment="REDDIT_COMMENT2VIDEO_TOS_REGION=cn-guangzhou"
Environment="REDDIT_COMMENT2VIDEO_TOS_BUCKET=您的bucket名"
Environment="REDDIT_COMMENT2VIDEO_TOS_PUBLIC_DOMAIN=https://您的公网域名"
```

保存后 `daemon-reload` 与 `restart` 同上。

### 3. 在平台注册能力并分配给用户

**3.1 让新能力出现在管理员界面（二选一）**

- **方式 A（推荐）**：能力目录已包含 `skill.reddit_comment2video`。登录管理后台 → 进入「资源分配」→ 在 **Skill 能力分配** 区域点击 **「重扫能力」**（或页面上的重扫/同步按钮），将目录同步到数据库后，列表中会出现 **skill.reddit_comment2video**。
- **方式 B**：在已部署 ai_test_platform 的机器上，用管理员 Token 执行（请把 `你的ADMIN_SECRET` 和 `http://127.0.0.1:8000` 换成实际值；需使用**登录后的 Bearer Token** 时请用 `Authorization: Bearer <token>` 替代 `X-Admin-Token`，视你后端鉴权方式而定）：

```bash
curl -s -X POST "http://127.0.0.1:8000/capabilities/registry" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: 你的ADMIN_SECRET" \
  -d '{
    "capability_id": "skill.reddit_comment2video",
    "description": "Reddit 评论转短视频（抓取 24-48h 帖子与评论，过滤后生成竖屏视频并上传 TOS）",
    "upstream": "skill",
    "upstream_tool": "reddit_comment2video",
    "enabled": true,
    "is_default": false,
    "unit_credits": 0
  }'
```

**3.2 分配用户**

1. 登录管理后台 → **资源分配** → **Skill 能力分配**。
2. 选择用户，勾选 **skill.reddit_comment2video**，保存。

完成后，该用户才可使用 reddit_comment2video skill。

### 4. OpenClaw 加载 skill

若使用 OpenClaw，需同时满足：

1. **技能文件就位**  
   将 `ai_capcut/skills/reddit_comment2video/`（含 `SKILL.md`）放到：
   - **Workspace**：`~/.openclaw/workspace/skills/reddit_comment2video/`
   - **Managed（可选）**：`~/.openclaw/skills/reddit_comment2video/`  
   若使用 shared-skills，见 OPENCLAW_DUAL_SETUP 与 `sync-openclaw-skills.sh`。

2. **重启 Gateway 以加载新 skill**  
   OpenClaw 启动时加载 skills，新增或修改 skill 后必须重启 Gateway 才会生效。当前服务器（单实例 18789）示例：
   ```bash
   # 查当前进程
   ps aux | grep openclaw
   # 结束主进程（会连带结束 gateway 子进程）
   kill <openclaw 主进程 PID>
   # 重新启动（端口与 openclaw.json 中 gateway.port 一致）
   nohup openclaw gateway run --port 18789 > /tmp/openclaw-gateway-18789.log 2>&1 &
   ```
   若 Gateway 以 systemd 运行，则：`systemctl --user restart openclaw-gateway`（或对应 service 名）。

3. **能力与平台后端配置**  
   - 在管理后台为该用户勾选 **skill.reddit_comment2video** 并保存。  
   - 平台后端（ai_test_platform）需配置 **REDDIT_COMMENT2VIDEO_BACKEND_URL**（如 `http://127.0.0.1:8003`），以便异步任务能调用 Reddit 后端。用户通过智能对话发起任务后，会立即提示「任务已创建，请到能力库查看能力调用记录」；在能力库的调用记录中可查看状态（执行中/完成/失败）及完成时的下载链接或失败原因。

---

## 服务器上的部署（已由脚本/运维完成的部分）

- 代码路径：`ai_capcut/backends/reddit_comment2video/`（随仓库 git pull 更新）。
- 虚拟环境：`backends/reddit_comment2video/.venv`，已安装 `requirements.txt` 并执行 `playwright install chromium`。
- 服务：systemd 单元 `reddit-comment2video.service`，监听 **8003**（若 8002 被占用则已改为 8003），工作目录为上述 backend 根目录。
- 环境变量占位：unit 中已预留 `TIKHUB_API_KEY`、`REDDIT_COMMENT2VIDEO_TOS_*` 的说明，实际值需您按上面 1、2 在 override 中填写。

验证：`curl -s http://127.0.0.1:8003/docs` 可打开 Swagger；`curl -s -X POST http://127.0.0.1:8003/generate-clips -H "Content-Type: application/json" -d '{"max_clips":1}'` 需在配置好 TIKHUB_API_KEY 后才会成功跑通管线。
