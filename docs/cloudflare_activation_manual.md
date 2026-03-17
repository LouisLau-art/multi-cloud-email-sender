# Cloudflare 域名激活后操作手册

## ⚠️ 重要前提
在执行以下操作前，请确认 Cloudflare 域名状态已经变为「Active」（NS 记录 propagation 完成）。
验证方法：
```powershell
nslookup -type=ns louisliu.fun
```
返回结果应该包含：
- haley.ns.cloudflare.com
- keenan.ns.cloudflare.com

---

## 步骤一：在新 Cloudflare 账号创建新隧道
> 注意：旧隧道 ID `9ff93171-7bbd-4a91-b716-abfe2ecc6f83` 属于旧账号，无法在新账号下使用，必须重新创建！

1. 登录新 Cloudflare 账号
2. 进入「Zero Trust」→「Networks」→「Tunnels」
3. 点击「Create a tunnel」，选择「Cloudflared」类型，命名为 `email-sender-tunnel`
4. 复制新生成的 Tunnel Token（后续步骤需要用到）
5. 在「Public Hostname」标签页，点击「Add a public hostname」
   - 域名选择：`louisliu.fun`
   - 子域名填写：`track`
   - Service 填写：`http://localhost:8000`
6. 保存配置

---

## 步骤二：更新 Windows 服务器 cloudflared 配置
### 情况 A：你使用的是 Token 方式运行（推荐）
1. 以管理员身份打开 PowerShell
2. 停止现有 cloudflared 服务：
   ```powershell
   Stop-Service cloudflared
   ```
3. 卸载旧服务：
   ```powershell
   cloudflared service uninstall
   ```
4. 安装新服务（替换为你在步骤一复制的新 Token）：
   ```powershell
   cloudflared service install <你的新 Tunnel Token>
   ```
5. 启动服务：
   ```powershell
   Start-Service cloudflared
   ```
6. 验证服务状态：
   ```powershell
   Get-Service cloudflared
   # 状态应该显示为 Running
   ```

### 情况 B：你使用的是 config.yml 方式运行
1. 编辑配置文件：`%USERPROFILE%\.cloudflared\config.yml`
2. 使用 `docs/cloudflared_config_template.yml` 模板替换内容，替换其中的 `<新隧道ID>` 和路径
3. 重启 cloudflared 服务：
   ```powershell
   Restart-Service cloudflared
   ```

---

## 步骤三：更新后端 track_domain 配置
参考文档：`docs/track_domain_update_guide.md`

1. 启动系统：双击 `start.bat`
2. 进入前端页面 http://localhost:5173 →「系统设置」
3. 将「追踪域名」修改为：`https://track.louisliu.fun`
4. 保存设置

---

## 步骤四：验证所有功能正常
### 验证 1：追踪接口可达性
```powershell
Invoke-WebRequest -Uri "https://track.louisliu.fun/api/track/open/ping-test"
# 应该返回 StatusCode 200
```

### 验证 2：系统启动检查
双击运行 `03-发信前检查.bat`，所有检查项都应该显示「OK」。

### 验证 3：发信测试
创建一个测试邮件任务，发送到自己的邮箱，确认邮件能够正常收到，并且打开/点击统计正常工作。

---

## 常见问题排查
### Q：出现 Error 1014: CNAME Cross-User Banned
A：说明你还在使用旧账号的隧道，必须在新账号下重新创建隧道。

### Q：cloudflared 服务启动失败
A：检查 Token 是否正确，网络是否能够访问 Cloudflare，查看日志文件 `logs/tunnel.log`。

### Q：追踪接口返回 404
A：检查隧道 Public Hostname 配置是否正确，Service 是否指向 `http://localhost:8000`。
