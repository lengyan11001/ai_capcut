# 部署用本地凭证（勿提交）

- `secrets.env`：SSH 与服务器信息，**已加入仓库根 `.gitignore`**，请勿复制到聊天或 PR。
- 使用前在 `secrets.env` 填写 **`DEPLOY_SSH_HOST`**（公网 IP 或域名）。当前仓库与对话里**没有**你的服务器地址记录，需自行填写。
- 私钥带口令时，建议在本机执行一次：
  ```bash
  ssh-add /path/to/lengyan.pem
  ```
  再 `ssh user@host`，避免脚本交互输入口令。
- **安全**：若私钥口令曾在公开场合发送过，建议在服务器上换用新密钥并更新口令。
