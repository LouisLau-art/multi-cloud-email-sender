# 离职交接文档：Cloudflare 追踪域名与账号迁移

## 1. 文档目的

本文档用于把“邮件系统追踪域名、Cloudflare 账号归属、Windows 服务器 tunnel 配置、域名解析接管状态”完整交接给下一位维护同事。

这份文档重点解决一个现实风险：

- 当前邮件系统的追踪能力依赖 Cloudflare
- Cloudflare 曾经或目前至少部分由离职人的个人账号/个人操作接管
- 离职后不应继续依赖个人账号维持公司业务

因此，本次交接的核心目标不是“单纯让系统能跑”，而是：

1. 让接手人明确当前资产归属和最后已知状态
2. 让接手人知道下一步该如何完成 Cloudflare 迁移或接管
3. 让接手人在不依赖离职人口头解释的情况下完成验证、恢复、回滚和后续维护

---

## 2. 适用范围

本文档只覆盖与以下主题直接相关的内容：

- 域名 `louisliu.fun`
- Cloudflare zone / DNS / SSL / Tunnel
- 邮件系统打开率/点击率追踪链路
- Windows 服务器上的 `cloudflared` 运行方式
- 应用内 `track_domain` 配置

本文档不全面覆盖以下主题，但这些主题与本交接强相关，建议接手人同步核查：

- 阿里云 DirectMail 账号归属与权限
- 腾讯云 SES 账号归属与权限
- GitHub / Gitee 仓库访问权限
- Windows 服务器管理员权限与远程接入方式
- `email_app.db` 数据文件备份与恢复策略

---

## 3. 面向读者

默认读者是：

- 负责接手该系统的技术同事
- 负责接手域名/解析/邮件发送环境的运维同事
- 需要审阅迁移风险的管理者

文档写法按“技术交接”处理，优先可执行性，不追求对非技术人员的完全友好。

---

## 4. 一页结论

### 4.1 当前最重要的事实

- 邮件系统的打开/点击追踪依赖可公网访问的固定域名或临时 tunnel
- 近期决定把固定追踪域名统一收敛为 `track.louisliu.fun`
- 当前这套追踪链路依赖 Cloudflare zone + Cloudflare Tunnel + Windows 服务器本地后端
- 该 Cloudflare 环节存在“个人账号持有/操作”的风险，因此必须完成交接或迁移

### 4.2 当前最重要的动作

接手人应优先完成以下事项：

1. 确认 `louisliu.fun` 当前实际托管在哪个 Cloudflare 账户/组织
2. 确认后续是否继续使用“新的 Cloudflare zone”而不是历史 zone
3. 确认 `track.louisliu.fun` 将绑定到哪条 Cloudflare Tunnel
4. 确认 Windows 服务器上的 `cloudflared` 配置与 Cloudflare 账户归属一致
5. 在公司可控账号下完成最终验证，避免离职后依赖个人账号

### 4.3 如果只能记住一件事

**不要把“域名已指向 Cloudflare”误认为“公司已经完全接管 Cloudflare 资源”。**

真正需要完成的是：

- 域名权威解析归属清晰
- Tunnel 归属清晰
- 服务器本地配置与 Cloudflare 账户上下文一致
- 追踪域名可用且由公司账号可持续维护

---

## 5. 资产与对象清单

### 5.1 域名与主机名

| 项目 | 值 | 说明 |
|------|----|------|
| 主域名 | `louisliu.fun` | 公司使用的域名 |
| 历史追踪主机名 | `track-dev.louisliu.fun` | 过去讨论和配置中出现过 |
| 目标追踪主机名 | `track.louisliu.fun` | 当前建议统一使用 |

### 5.2 域名注册与 DNS

| 项目 | 最后已知状态 | 说明 |
|------|--------------|------|
| 域名注册商 | 阿里云 | 用户明确在阿里云侧管理域名 |
| 历史 Cloudflare NS | `may.ns.cloudflare.com` / `noel.ns.cloudflare.com` | 表明域名曾接入过另一组 Cloudflare zone |
| 新 Cloudflare NS | `haley.ns.cloudflare.com` / `keenan.ns.cloudflare.com` | 用户在新 zone 中拿到并已尝试切换 |
| DNS 导出文件 | `/root/Downloads/louisliu.fun_1773390294285.txt` | 阿里云导出的 BIND 风格 zone 文件 |
| 清洗后的导入文件 | `louisliu.fun.cloudflare.zone` | 当前 repo 中生成的 Cloudflare 可导入版本 |

### 5.3 Cloudflare Tunnel

| 项目 | 值 | 说明 |
|------|----|------|
| Tunnel 名称 | `email-tracker-dev` | 用户在 Windows 上跑 `tunnel info` 时显示 |
| Tunnel UUID | `9ff93171-7bbd-4a91-b716-abfe2ecc6f83` | 所有 tunnel 命令都依赖这个 UUID |
| 最后已知客户端路径 | `C:\\Users\\A\\Downloads\\cloudflared.exe` | 用户手工执行命令时使用 |
| 最后已知配置路径 | `C:\\Users\\A\\.cloudflared\\config.yml` | named tunnel 本地配置文件 |

### 5.4 应用与代码库

| 项目 | 值 | 说明 |
|------|----|------|
| 项目路径 | `/root/multi-cloud-email-sender` | 当前代码仓库 |
| 主分支 | `main` | 当前仓库分支 |
| 最后已推送提交 | `97135ac Harden quick tunnel startup checks` | 已推到远端 |
| 本地未提交修改 | `03-发信前检查.bat`、`docs/VM_START_GUIDE.txt` | 已把默认示例域名改为 `track.louisliu.fun`，尚未提交 |

### 5.5 账号接管时必须明确的归属信息

以下信息如果离职前不交清楚，接手人后续会非常被动：

| 项目 | 当前状态 | 接手人需要拿到什么 |
|------|----------|-------------------|
| Cloudflare 账号/组织名 | 待接手人确认 | 至少知道当前有效 zone 在哪个账户/组织下 |
| Cloudflare 登录邮箱 | 待补充 | 如果是个人邮箱，必须尽快替换为公司可控方式 |
| Cloudflare 2FA 管理方式 | 待补充 | 接手人必须知道是手机、邮箱、Authenticator 还是硬件密钥 |
| Cloudflare billing/所有者 | 待补充 | 必须知道谁有 owner 级权限 |
| 域名阿里云登录权限 | 待补充 | 接手人必须能查看和修改 NS |
| Windows 服务器管理员权限 | 待补充 | 接手人必须能改 `cloudflared` 配置、重启服务、更新 app 设置 |
| GitHub/Gitee 权限 | 待补充 | 至少一位接手人能提交和发布变更 |

---

## 6. 背景与问题演进

### 6.1 为什么会有这份交接

近期排查过程中发现：

- 邮件追踪域名依赖 Cloudflare
- Cloudflare 操作明显涉及离职人的个人账号或至少个人可控上下文
- 离职后如果不交接，最容易出问题的不是“发信本身”，而是：
  - 打开率/点击率追踪中断
  - 启动脚本因为固定域名不可达直接阻断系统启动
  - 同事找不到正确的 Cloudflare zone / Tunnel / 配置文件

### 6.2 本轮排查中确认过的关键事实

1. Windows 服务器上存在 named tunnel 配置，说明系统并非单纯依赖 quick tunnel
2. 旧的 quick tunnel 会被 `%USERPROFILE%\\.cloudflared\\config.yml` 阻断，这是 Cloudflare 的正常行为
3. 域名曾经已经指向过一组旧的 Cloudflare NS（`may/noel`）
4. 当前用户又创建了一组新的 Cloudflare zone，对应新的 NS（`haley/keenan`）
5. 当前操作方向已经不是“恢复旧 zone”，而是“迁移到新的 zone”
6. 当前 repo 默认示例域名已经改为 `track.louisliu.fun`

### 6.3 非常容易搞混的三个概念

#### A. 阿里云域名注册商

作用：

- 负责域名注册
- 负责修改权威 NS（nameserver）

不负责：

- 在 Cloudflare 接管后继续作为权威 DNS 生效

#### B. 阿里云 DNS 导出文件

作用：

- 是 DNS 记录的备份和迁移输入

不等于：

- Cloudflare 已经有这个 zone
- 公司已经接管 Cloudflare 账号

#### C. Cloudflare zone 与 Cloudflare Tunnel

二者都需要归属清晰：

- zone 决定谁对公网发布 `louisliu.fun` 及其子域名
- tunnel 决定 `track.louisliu.fun` 这样的 hostname 最终转发到哪台内网/本地服务

二者如果不在同一公司可控账户上下文中，后期维护会非常痛苦。

---

## 7. 当前代码与脚本改动

### 7.1 已推送到远端的改动

本仓库之前已经推送过以下与追踪链路相关的提交：

- `406a902` `Fix contact sync and regional template issues`
- `e143228` `Allow deleting snapshotted contact lists`
- `97135ac` `Harden quick tunnel startup checks`

这些提交已经在远端，重点包括：

- quick tunnel 启动诊断增强
- fixed track domain 健康检查
- 配置阻断 quick tunnel 时的明确报错

### 7.2 当前本地未提交改动

#### 文件一：`03-发信前检查.bat`

当前本地已改为：

- `EXPECTED_TRACK_DOMAIN=https://track.louisliu.fun`

作用：

- 预检脚本默认检查新目标域名

#### 文件二：`docs/VM_START_GUIDE.txt`

当前本地已改为：

- 固定域名示例从 `https://track-dev.louisliu.fun` 改为 `https://track.louisliu.fun`

作用：

- 让操作说明与新的目标域名保持一致

### 7.3 尚未提交的辅助文件

#### `louisliu.fun.cloudflare.zone`

这是根据阿里云导出内容生成的清洗版 zone file，用于：

- Cloudflare 手工导入 DNS 记录
- 避免手填长 TXT / DKIM 记录
- 迁移时复核 DNS 内容

说明：

- 这是辅助迁移文件，不是程序代码
- 目前处于未提交状态

---

## 8. 当前 Cloudflare 迁移状态

### 8.1 最后已知状态

根据最后一次会话确认：

- 新的 Cloudflare zone 已创建
- Cloudflare DNS 页面中已经导入 MX/TXT 相关记录
- Cloudflare 页面显示仍在等待 nameserver propagation
- 用户已经点击过 `I updated my nameservers`

### 8.2 目前不能当成已完成的事项

以下事项在最后一次会话中**没有被最终验证**：

- 新 zone 是否已经 `Active`
- `nslookup -type=ns louisliu.fun` 是否已经实际返回 `haley/keenan`
- `track.louisliu.fun` 是否已经创建并指向 tunnel
- 本机 Windows `config.yml` 是否已经改为 `track.louisliu.fun`
- `track_domain` 是否已经在后端设置中改成 `https://track.louisliu.fun`

### 8.3 当前阻塞点

当前真正的阻塞点只有一个：

- **Cloudflare zone 是否已经完成接管并激活**

只有 zone 变成 `Active`，后续 tracking hostname 绑定和公网验证才有意义。

---

## 9. 接手人必须先确认的 8 件事

1. 现在真正生效的权威 nameserver 是哪一组
2. 新 zone 是否已经 `Active`
3. 当前正在操作的是不是公司可持续接手的 Cloudflare 账号
4. `email-tracker-dev` 这条 tunnel 是否仍在可见范围内
5. `9ff93171-7bbd-4a91-b716-abfe2ecc6f83` 这条 tunnel 是否属于当前新 zone 所在账户
6. Windows 服务器上 `cloudflared.exe` 和 `config.yml` 路径是否仍然与会话记录一致
7. 后端 `track_domain` 当前实际值是什么
8. 邮件系统是否已经在发送真实任务，如果是，要避免贸然切域名导致统计断裂

---

## 10. 推荐迁移目标

### 10.1 目标一：公司账号持有 Cloudflare zone

最终不应再依赖离职人的个人账号。

应当确保：

- `louisliu.fun` 的 Cloudflare zone 在公司账号或公司组织名下
- 至少 2 名公司同事拥有可管理权限
- 所有后续 DNS/TLS/Tunnel 操作都能在该账户内完成

### 10.2 目标二：统一使用 `track.louisliu.fun`

原因：

- 名字更简洁
- 更适合作为长期固定 tracking hostname
- 已经与 repo 本地默认文档和预检示例对齐

说明：

- `track-dev.louisliu.fun` 和 `track.louisliu.fun` 对 `louisliu.fun` 来说都属于一级子域名
- 切换到 `track` 是命名收敛，不是因为“层级不同必须切”

### 10.3 目标三：启动链路不再依赖个人 quick tunnel 习惯

系统的长期正确姿势应该是：

- 固定公网 `track_domain`
- named tunnel
- Cloudflare DNS 由公司账号管理

不应把 quick tunnel 作为长期生产方案。

### 10.4 目标四：Cloudflare 归属方式必须制度化

如果当前新 zone 仍在离职人的个人 Cloudflare 账号下，那么“系统能用”不等于“交接完成”。

推荐按以下优先级处理：

1. **最佳方案**：迁移到公司专用 Cloudflare 账号/组织
2. **次优方案**：在当前账户中先加入至少两位公司同事并确认 owner/admin 权限，再计划二次迁移
3. **不推荐方案**：离职后继续默认依赖个人账号长期维持

本质原则是：

- zone 控制权必须归公司
- tunnel 控制权必须归公司
- 2FA 和 owner 权限不能只在离职人手里

---

## 11. 推荐接管步骤（按顺序执行）

### 步骤 0：先决定“接管策略”

在真正执行技术步骤前，先做一个管理决定：

#### 方案 A：继续使用当前新 zone，但把账户管理权移交给公司

适用于：

- 现在这个新 zone 已经配好
- 离职前仍有时间加人、交接、验证

要求：

- 公司同事必须进入当前 Cloudflare 账户/组织
- 至少一名公司同事有足够高的权限继续维护 zone 和 tunnel

#### 方案 B：用公司账号重新建最终 zone / tunnel，再做一次正式迁移

适用于：

- 当前 zone 仍然在个人账号下，不适合长期保留
- 公司有明确的 Cloudflare 账号治理要求

代价：

- 会多一次迁移
- 需要重新验证 NS、DNS、tunnel、tracking

建议：

- 如果离职时间非常近而迁移没做完，至少先完成方案 A 的“临时接管”，再安排方案 B

在没有明确方案前，不要让接手人误以为“只要系统今天能发邮件就算交接结束”。

### 步骤 1：确认新 zone 是否已经 Active

执行：

```powershell
nslookup -type=ns louisliu.fun
```

如果结果已经是：

- `haley.ns.cloudflare.com`
- `keenan.ns.cloudflare.com`

再去 Cloudflare Dashboard 确认 zone 状态是否为 `Active`。

### 步骤 2：确认 DNS 记录已完整导入

核对以下记录至少存在：

- `MX louisliu.fun -> mxbiz1.qq.com`
- `MX send -> feedback-smtp.ap-northeast-1.amazonses.com`
- `TXT alidnscheck`
- `TXT aliyun-cn-hangzhou._domainkey`
- `TXT aliyundm`
- `TXT _dmarc`
- `TXT louisliu.fun -> v=spf1 include:qcloudmail.com ~all`
- `TXT qcloud._domainkey`
- `TXT resend._domainkey`
- `TXT send -> v=spf1 include:amazonses.com ~all`

### 步骤 3：确认 tunnel 是否可继续使用

在 Windows 服务器执行：

```powershell
& "C:\Users\A\Downloads\cloudflared.exe" tunnel info 9ff93171-7bbd-4a91-b716-abfe2ecc6f83
```

如果命令能正常返回 tunnel 信息，说明本机客户端至少还能识别这条 tunnel。

但这一步**不能单独证明**：

- 这条 tunnel 一定属于当前新 zone 所在的公司账号

所以还要继续做步骤 4。

### 步骤 4：把 `track.louisliu.fun` 绑定到 tunnel

执行：

```powershell
& "C:\Users\A\Downloads\cloudflared.exe" tunnel route dns 9ff93171-7bbd-4a91-b716-abfe2ecc6f83 track.louisliu.fun
```

如果成功：

- 说明当前 tunnel 与当前 zone 上下文大概率可协同工作

如果失败，常见含义：

- 这条 tunnel 不属于当前 zone 所在账户
- 当前登录/认证上下文不对
- 应改为在新账户中新建 tunnel，而不是复用旧 tunnel

### 步骤 5：修改 Windows 本地 `cloudflared` 配置

最后已知本地配置路径：

```text
C:\Users\A\.cloudflared\config.yml
```

最后已知旧配置思路是：

```yaml
tunnel: 9ff93171-7bbd-4a91-b716-abfe2ecc6f83
credentials-file: C:\Users\A\.cloudflared\9ff93171-7bbd-4a91-b716-abfe2ecc6f83.json
ingress:
  - hostname: track-dev.louisliu.fun
    service: http://localhost:8000
  - service: http_status:404
```

目标改成：

```yaml
tunnel: 9ff93171-7bbd-4a91-b716-abfe2ecc6f83
credentials-file: C:\Users\A\.cloudflared\9ff93171-7bbd-4a91-b716-abfe2ecc6f83.json
ingress:
  - hostname: track.louisliu.fun
    service: http://localhost:8000
  - service: http_status:404
```

如果最终新建 tunnel，则这里的 `tunnel` 和 `credentials-file` 也要一起换成新的 UUID。

### 步骤 6：重启 Cloudflared 服务

执行：

```powershell
Restart-Service cloudflared
```

然后再次检查：

```powershell
& "C:\Users\A\Downloads\cloudflared.exe" tunnel info 9ff93171-7bbd-4a91-b716-abfe2ecc6f83
```

### 步骤 7：更新应用内 `track_domain`

只在公网 hostname 已经可用后执行：

```powershell
$body = @{ track_domain = "https://track.louisliu.fun" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/settings" -ContentType "application/json" -Body $body
```

然后确认：

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/settings"
```

目标是看到：

```text
track_domain = https://track.louisliu.fun
```

### 步骤 8：做公网验证

执行：

```powershell
Invoke-WebRequest -UseBasicParsing "https://track.louisliu.fun/api/track/open/ping-test"
```

目标结果：

- HTTP `200`

如果返回成功，再运行系统启动脚本并观察：

- `[Track] Fixed track_domain is healthy.`

### 步骤 9：完成账号与权限交接确认

技术验证完成后，还必须完成以下交接动作：

- 确认至少两位公司同事可登录并看到当前有效的 Cloudflare zone
- 确认至少一位公司同事可管理 tunnel 或可新建替代 tunnel
- 确认至少一位公司同事可修改阿里云域名 NS
- 确认接手人知道 Windows 服务器上 `cloudflared` 配置文件位置与服务重启方法

如果这些动作没完成，技术验证通过也不能算真正交接完成。

---

## 12. 如果第 4 步失败怎么办

### 场景：`tunnel route dns` 失败

可能原因：

- 当前 tunnel 仍属于旧账户
- 新 zone 和旧 tunnel 不在同一个公司可控上下文

处理建议：

1. 不要继续硬复用旧 tunnel
2. 在新的公司 Cloudflare 账户中重新创建一条 tunnel
3. 把新的 tunnel 绑定到 `track.louisliu.fun`
4. 更新 Windows 本地 `config.yml`
5. 更新应用内 `track_domain`

### 新建 tunnel 的接手建议

虽然本轮会话没有在当前 Linux 环境实际执行 Windows 端的新建命令，但接手人应遵循 Cloudflare 官方 named tunnel 流程：

- 在新账户里创建 tunnel
- 为 `track.louisliu.fun` 创建 public hostname
- 本地 Windows 服务器安装/复用 `cloudflared`
- 配置 ingress 指向 `http://localhost:8000`
- 让服务自启动

---

## 13. 启动脚本与运行机制说明

### 13.1 为什么 fixed domain 不可达会导致启动失败

本仓库的 Windows 启动脚本被改造成“先验证 tracking 域名，再放行前端”。

逻辑是：

- 如果 `track_domain` 是固定公网域名
- 启动时先请求：

```text
GET {track_domain}/api/track/open/ping-test
```

- 只有返回 `200` 才继续启动

这样做的目的不是增加复杂度，而是防止：

- 看起来系统已经起来了
- 但打开率/点击率统计其实已经失效

### 13.2 这意味着什么

意味着：

- 一旦把 `track_domain` 改成新域名
- 但新域名实际上还没通

`start.bat` 会故意拦住系统

所以所有接手同事必须记住：

**不要抢跑修改 `track_domain`。必须先保证公网域名已经真正能通。**

---

## 14. 失败排查顺序

如果接手后仍然不通，严格按下面顺序查：

1. `nslookup -type=ns louisliu.fun`
2. Cloudflare zone 是否 `Active`
3. `track.louisliu.fun` 这条 DNS / public hostname 是否存在
4. `cloudflared tunnel info ...` 是否有 active connector
5. `C:\Users\A\.cloudflared\config.yml` 是否已改成 `track.louisliu.fun`
6. `http://localhost:8000/api/track/open/ping-test` 本地是否返回 `200`
7. `https://track.louisliu.fun/api/track/open/ping-test` 公网是否返回 `200`
8. 应用内 `track_domain` 是否已经更新

禁止的排查方式：

- 一上来就乱改阿里云解析记录
- 一上来就强行切回 quick tunnel 当长期方案
- 没有验证公网是否可达就先改 `track_domain`

---

## 15. 风险清单

### 高风险

1. 离职后公司无法登录当前有效的 Cloudflare 账户
2. Tunnel 仍绑定在个人账号上下文，导致 zone 虽然已迁移但 hostname 无法正确路由
3. 接手人只接了代码仓库，没有接 Windows 服务器本地 `cloudflared` 配置文件和服务控制权
4. 追踪域名切换后没有验证历史任务影响，导致新旧邮件统计混用

### 中风险

1. 只迁移了 zone，没有迁移 tunnel
2. 只迁移了 tunnel，没有同步后端 `track_domain`
3. 文档里默认域名已改成 `track.louisliu.fun`，但实际服务器仍指向旧 hostname

### 低风险

1. `03-发信前检查.bat` / `VM_START_GUIDE` 的示例域名尚未提交到远端
2. `louisliu.fun.cloudflare.zone` 还未纳入版本管理

---

## 16. 必做交接清单

### 离职前必须完成

- [ ] 明确公司最终要接手的 Cloudflare 账户/组织
- [ ] 至少两位公司同事具备该账户管理权限
- [ ] 明确 `louisliu.fun` 最终归属的新 zone
- [ ] 明确 `email-tracker-dev` 或替代 tunnel 的归属
- [ ] 确认 Windows 服务器上的 `cloudflared` 配置文件归档给接手人
- [ ] 交付本仓库、服务器、域名、Cloudflare 的访问路径与说明
- [ ] 至少完成一次从外网访问 `https://track.louisliu.fun/api/track/open/ping-test` 的成功验证

### 最好一并完成

- [ ] 把 `track.louisliu.fun` 相关改动提交到仓库
- [ ] 把 `louisliu.fun.cloudflare.zone` 纳入仓库或安全制品库
- [ ] 在团队文档库中存一份最终版交接文档
- [ ] 由接手同事亲手执行一次启动、验证、停止流程

---

## 17. 交接后的验收标准

只有同时满足以下条件，才算真正完成交接：

1. 公司可控 Cloudflare 账户可登录
2. `louisliu.fun` 在该账户下可管理
3. `track.louisliu.fun` 在公网可访问并返回 `200`
4. Windows 服务器重启后，系统仍可在固定域名模式下成功启动
5. 接手同事知道如何修改 DNS、如何重启 cloudflared、如何更新 `track_domain`
6. 离职人退出后，系统仍能独立维护

---

## 18. 推荐附带交付材料

建议把以下内容一起打包给接手人：

- 本文档
- `.claude/handoffs/2026-03-13-165731-cloudflare-tracking-migration.md`
- `docs/VM_START_GUIDE.txt`
- `03-发信前检查.bat`
- `louisliu.fun.cloudflare.zone`
- 阿里云导出的 zone 文件原件：`/root/Downloads/louisliu.fun_1773390294285.txt`
- Windows 服务器 `cloudflared` 配置文件备份
- 关键命令清单

---

## 19. 关键命令速查

### 查看当前 NS

```powershell
nslookup -type=ns louisliu.fun
```

### 查看 tunnel 信息

```powershell
& "C:\Users\A\Downloads\cloudflared.exe" tunnel info 9ff93171-7bbd-4a91-b716-abfe2ecc6f83
```

### 绑定新 tracking hostname

```powershell
& "C:\Users\A\Downloads\cloudflared.exe" tunnel route dns 9ff93171-7bbd-4a91-b716-abfe2ecc6f83 track.louisliu.fun
```

### 重启 cloudflared 服务

```powershell
Restart-Service cloudflared
```

### 读取应用设置

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/settings"
```

### 更新应用 tracking 域名

```powershell
$body = @{ track_domain = "https://track.louisliu.fun" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/settings" -ContentType "application/json" -Body $body
```

### 验证公网 tracking

```powershell
Invoke-WebRequest -UseBasicParsing "https://track.louisliu.fun/api/track/open/ping-test"
```

---

## 20. 最后的建议

如果交接时间非常紧，优先级请按下面排序：

1. 账号归属
2. zone 激活
3. tunnel 归属
4. `track.louisliu.fun` 打通
5. 系统设置改域名
6. 文档和仓库清理

不要把顺序倒过来。

文档、脚本、说明都可以补；但如果账号归属和公网追踪链路没交接清楚，离职后最难补。
