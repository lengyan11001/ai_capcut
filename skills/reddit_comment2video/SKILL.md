---
name: reddit_comment2video
description: 从指定 subreddit 抓取 24–48 小时内的帖子与顶部评论，按规则过滤（敏感词、评论文案兼容）后生成竖屏短视频，上传 TOS 并返回链接。需平台分配「skill.reddit_comment2video」能力后才可用。
---

# Reddit 评论转短视频（reddit_comment2video）

从 ProgrammerHumor / rosesarered / meirl 等 subreddit 抓取**近 24–48 小时**符合规则的帖子与顶部评论，经**敏感词与评论文案兼容过滤**后，按固定模版生成竖屏短视频，上传到 TOS 并返回可公网访问链接。

你（Agent）负责理解用户意图、确认需求并调用后端 HTTP 能力；后端负责抓取 → 过滤 → 生成 → 上传。

---

## 触发条件

- 用户提到 **Reddit / subreddit / 梗图 / meme / 评论转视频**，或本 skill 名称 **reddit_comment2video**。
- 不适用：长视频剪辑、口播讲解、Lottie 动画（用 svg-video 等）；或用户上传本地视频要求剪辑。

**重要**：本 skill 是**自动从 Reddit 抓取**近期帖子与顶部评论并生成视频，**不要**向用户索要「评论内容、风格/格式、语音选项、视频长度」等。用户可指定**生成哪几个板块（subreddit）、几条视频**；不指定则按默认**全部配置板块、时间段内**。任务为**异步执行**，调用后立即提示「任务已创建，请到能力库查看能力调用记录」，无需等待；在能力库的调用记录中可查看状态（执行中/完成/失败）、完成时的下载链接或失败原因。

---

## 前置依赖（运维执行一次）

1. **后端部署**  
   - 代码位置：本仓库 `backends/reddit_comment2video/`。  
   - 启动示例：
     ```bash
     cd /path/to/ai_capcut/backends/reddit_comment2video
     python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
     playwright install chromium
     .venv/bin/python scripts/reddit_skill_server.py
     ```
   - 默认监听 `http://0.0.0.0:8000`；若与平台同机，可设环境变量 `PORT=8003` 避免与 8000/8001 冲突。

2. **环境变量（必须由您配置）**  
   - **TIKHUB_API_KEY**：TikHub 的 API Key，用于抓取 Reddit。  
   - TOS 上传（可选，不配则只生成不传）：  
     - `REDDIT_COMMENT2VIDEO_TOS_ACCESS_KEY` / `REDDIT_COMMENT2VIDEO_TOS_SECRET_KEY`  
     - `REDDIT_COMMENT2VIDEO_TOS_ENDPOINT` / `REDDIT_COMMENT2VIDEO_TOS_REGION`  
     - `REDDIT_COMMENT2VIDEO_TOS_BUCKET` / `REDDIT_COMMENT2VIDEO_TOS_PUBLIC_DOMAIN`  
   详见 `backends/reddit_comment2video/README.md`。

3. **权限**  
   - 在管理后台「Skill 能力分配」中为对应用户勾选 **skill.reddit_comment2video**，保存后该用户才可用本 skill。

4. **OpenClaw**  
   - 将本目录 `skills/reddit_comment2video/` 放入 OpenClaw workspace 或 shared-skills，并执行 `sync-openclaw-skills.sh`（若使用共享目录）。

---

## 能力接口

后端：`backends/reddit_comment2video/scripts/reddit_skill_server.py`。

### POST /generate-clips

- **URL**：`http://<后端主机>:<端口>/generate-clips`（同机示例：`http://127.0.0.1:8003/generate-clips`）。
- **请求体**：
  ```json
  { "max_clips": 2, "subreddits": null, "work_dir": null, "config_path": null }
  ```
- **响应**：`success`、`count`、`work_dir`、`clips[]`（含 `video_path`、`public_url`）、`error`。

流程：爬 24–48h → 敏感词 + 评论文案兼容过滤 → 生成 → 打包（结果在 work_dir/clips），可选上传 TOS 得 public_url。

---

## Agent 使用规范

1. **一旦命中触发条件**（用户说做 Reddit 评论转视频等），**立即**走本 skill，不要反问用户要评论文案或风格。  
2. **查询当前配置的板块**：当用户问「配置了几个板块」「有哪些板块」「现在有哪些 Reddit 板块」时，调用平台工具 **get_reddit_configured_subreddits**（无参数），根据返回的 `count` 与 `subreddits` 列表回复，例如「当前已配置 N 个板块：A、B、C」。  
3. 从用户话里提取：生成条数 `max_clips`（如「1 条」→ 1，「几条」→ 2；不说明则可不传，用后端默认）、目标板块 `subreddits`（如「ProgrammerHumor 和 meirl」→ `["ProgrammerHumor","meirl"]`；不说明则不传，用全部配置板块）。  
4. 通过平台能力 **invoke_capability** 调用本 skill：`capability_id=skill.reddit_comment2video`，`payload` 中按需传入 `max_clips`、`subreddits`。平台会异步执行任务并立即返回。若平台返回错误提示「以下板块尚未配置」：**原样把该提示转给用户**，引导其到**能力库 → Reddit 评论转短视频**页面配置该板块与博主、视频音频的对应关系后再生成。  
5. 成功提交后向用户回复：任务已创建，请到**能力库**查看**能力调用记录**；记录中会显示状态（执行中/完成/失败），完成的可查看下载链接，失败会显示错误原因。

---

## 配置与规则

- 配置文件：`backends/reddit_comment2video/scripts/reddit_comment2video_config.json`（time_window_hours 24–48、post_filters、youtube_safety_filters_path、subreddits 人设等）。  
- 敏感词规则：`scripts/youtube_safety_filters.json`。  
- 修改人设或过滤规则后重启后端生效。
