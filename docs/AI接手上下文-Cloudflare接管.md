# AI 接手上下文：Cloudflare 接管

> 用途：给后续 AI / 代理 / 自动化流程快速续接，不要求先读完整聊天记录  
> 更新日期：2026-03-17

---

## 1. 核心任务

当前核心任务不是修业务代码，而是完成这条追踪链路的接管：

```text
Cloudflare zone
  -> Cloudflare Tunnel
  -> Windows cloudflared
  -> backend track_domain
  -> 邮件打开/点击统计
```

目标固定域名：

```text
https://track.louisliu.fun
```

---

## 2. 关键事实

### 已确认事实

- 项目仓库：`/root/multi-cloud-email-sender`
- 主分支：`main`
- 最新已推送文档提交：`6869a91 Add Cloudflare handoff documentation`
- 域名：`louisliu.fun`
- 域名注册商：阿里云
- 历史旧 Cloudflare NS：`may.ns.cloudflare.com` / `noel.ns.cloudflare.com`
- 新建 zone 分配的 NS：`haley.ns.cloudflare.com` / `keenan.ns.cloudflare.com`
- 历史旧 tunnel：
  - name: `email-tracker-dev`
  - uuid: `9ff93171-7bbd-4a91-b716-abfe2ecc6f83`
- 最后已知 Windows cloudflared 路径：`C:\Users\A\Downloads\cloudflared.exe`
- 最后已知 Windows config 路径：`C:\Users\A\.cloudflared\config.yml`

### 已确认的决策

- 不再把复用旧 `9ff...` 作为默认主路径
- 默认主路径改为：**新账号 / 新 zone / 新 tunnel / `track.louisliu.fun`**
- 普通同事不应手动改 `track_domain` 或运行 `cloudflared`
- 技术同事应优先通过 UI 更新 `track_domain`，API 只作兜底

### 未确认事实

- 新 zone 当前是否已 `Active`
- 当前注册商实际生效 NS 是否已切到 `haley/keenan`
- 新账号下是否已经创建了新 tunnel
- Windows 上是否已经把 `config.yml` 改成 `track.louisliu.fun`
- 应用当前 `track_domain` 是否已改到 `https://track.louisliu.fun`

---

## 3. 推荐推理规则

后续 AI 继续工作时，请遵循：

1. **不要把旧 `9ff...` 当成默认应复用资源**
2. **不要要求普通同事执行管理员动作**
3. **不要把 Linux 工作区路径误当成 Windows 服务器现成路径**
4. **不要在公网域名未打通时先改应用 `track_domain`**
5. **不要把 quick tunnel 当长期生产方案**

---

## 4. 读文档顺序

1. [离职交接文档总览.md](/root/multi-cloud-email-sender/docs/%E7%A6%BB%E8%81%8C%E4%BA%A4%E6%8E%A5%E6%96%87%E6%A1%A3%E6%80%BB%E8%A7%88.md)
2. [给技术同事看的-离职交接说明-Cloudflare接管技术版.md](/root/multi-cloud-email-sender/docs/%E7%BB%99%E6%8A%80%E6%9C%AF%E5%90%8C%E4%BA%8B%E7%9C%8B%E7%9A%84-%E7%A6%BB%E8%81%8C%E4%BA%A4%E6%8E%A5%E8%AF%B4%E6%98%8E-Cloudflare%E6%8E%A5%E7%AE%A1%E6%8A%80%E6%9C%AF%E7%89%88.md)
3. [cloudflare_activation_manual.md](/root/multi-cloud-email-sender/docs/cloudflare_activation_manual.md)
4. [track_domain_update_guide.md](/root/multi-cloud-email-sender/docs/track_domain_update_guide.md)
5. [cloudflared_config_template.yml](/root/multi-cloud-email-sender/docs/cloudflared_config_template.yml)
6. [.claude/handoffs/2026-03-13-165731-cloudflare-tracking-migration.md](/root/multi-cloud-email-sender/.claude/handoffs/2026-03-13-165731-cloudflare-tracking-migration.md)

---

## 5. 操作决策树

### 如果 Cloudflare zone 还不是 Active

动作：

- 不要继续切 `track_domain`
- 先确认注册商 NS
- 先确认 zone 状态

### 如果 zone 已 Active，但 `track.louisliu.fun` 不通

动作：

1. 确认新 tunnel 是否已创建
2. 确认 Public Hostname 是否是 `track.louisliu.fun -> http://localhost:8000`
3. 确认 Windows `cloudflared` 服务是否 Running
4. 确认本地 `localhost:8000` 是否返回 `200`

### 如果 zone 已 Active，但旧 `9ff...` 仍能看到

动作：

- 默认不复用
- 除非团队明确决定保留旧账号上下文并已完成公司权限接管

---

## 6. 最关键的验证命令

### DNS

```powershell
nslookup -type=ns louisliu.fun
```

### 本地后端

```powershell
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/track/open/ping-test"
```

### 公网 tracking

```powershell
Invoke-WebRequest -UseBasicParsing "https://track.louisliu.fun/api/track/open/ping-test"
```

### 查看应用当前配置

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/settings"
```

### 重启 cloudflared

```powershell
Restart-Service cloudflared
```

---

## 7. 关键文件

### 人类可读文档

- `docs/给同事看的-离职交接说明-Cloudflare与追踪域名.md`
- `docs/给技术同事看的-离职交接说明-Cloudflare接管技术版.md`

### 执行模板

- `docs/cloudflare_activation_manual.md`
- `docs/track_domain_update_guide.md`
- `docs/cloudflared_config_template.yml`

### 迁移素材

- `louisliu.fun.cloudflare.zone`
- `/root/Downloads/louisliu.fun_1773390294285.txt`

### 历史 AI handoff

- `.claude/handoffs/2026-03-13-165731-cloudflare-tracking-migration.md`

---

## 8. AI 继续工作时的优先级

1. 保护单一真相
2. 不让普通同事承担管理员动作
3. 先账号与 zone，再 tunnel，再 `track_domain`
4. 先验证公网，再改程序配置
5. 文档产出优先于猜测

---

## 9. 如果只剩很少时间

最小可接受结果：

- 文档已交付
- 权限已交付
- 技术同事知道默认路径是“新账号 + 新 tunnel + `track.louisliu.fun`”
- 未完成项有明确清单
