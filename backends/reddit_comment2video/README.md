# reddit_comment2video 后端

Reddit 评论转短视频 skill 的后端服务：抓取 24–48 小时帖子与评论 → 敏感词与评论文案过滤 → 生成竖屏短视频 → 可选上传 TOS。

## 环境变量（必须由您配置）

以下为**必须或推荐**在部署时配置的项（systemd 的 `Environment=` 或 `.env`）。

### 1. TikHub API Key（必填，用于抓取 Reddit）

| 变量名 | 说明 |
|--------|------|
| `TIKHUB_API_KEY` | TikHub 的 API Key。未设置时抓取会报错。 |

获取方式：登录 [TikHub](https://tikhub.io) 或相关文档申请 API Key。

### 2. TOS 上传（选填）

不配置则生成视频仍可写入 `work_dir/clips`，但不会上传到 TOS，接口返回的 `public_url` 为空。

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `REDDIT_COMMENT2VIDEO_TOS_ACCESS_KEY` | 火山 TOS access_key | |
| `REDDIT_COMMENT2VIDEO_TOS_SECRET_KEY` | 火山 TOS secret_key | |
| `REDDIT_COMMENT2VIDEO_TOS_ENDPOINT` | 端点 | `tos-cn-guangzhou.volces.com` |
| `REDDIT_COMMENT2VIDEO_TOS_REGION` | 区域 | `cn-guangzhou` |
| `REDDIT_COMMENT2VIDEO_TOS_BUCKET` | 桶名 | |
| `REDDIT_COMMENT2VIDEO_TOS_PUBLIC_DOMAIN` | 公网访问域名 | `https://cdn-video.51sux.com` |

## 本地运行

```bash
cd backends/reddit_comment2video
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
playwright install chromium

export TIKHUB_API_KEY=你的TikHub密钥
# 可选：export REDDIT_COMMENT2VIDEO_TOS_*=

.venv/bin/python scripts/reddit_skill_server.py
# 指定端口：.venv/bin/python scripts/reddit_skill_server.py  # 修改脚本内 port 或 uvicorn --port 8002
```

默认监听 `http://0.0.0.0:8000`。与平台同机时建议改用 8002，避免与 8000（平台）、8001（MCP）冲突。

## 权限

本 skill 对应能力 ID：**skill.reddit_comment2video**。在管理后台「资源分配 → Skill 能力分配」中为对应用户勾选该能力并保存后，用户才可用。
