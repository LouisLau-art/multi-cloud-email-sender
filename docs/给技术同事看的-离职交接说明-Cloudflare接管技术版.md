# 给技术同事看的离职交接说明：Cloudflare 接管技术版

> 文档版本：2026-03-17  
> 目标读者：技术接手同事 / 运维 / 负责域名与 Cloudflare 的管理员  
> 文档目的：在离职后，让公司技术同事可以独立接管 `louisliu.fun` 相关的 Cloudflare zone、Cloudflare Tunnel、Windows 服务器追踪链路配置与应用内 `track_domain`

---

## 1. 阅读前说明

这份文档是**技术管理员文档**，不是普通使用 SOP。

请先区分两类文档：

### 普通同事日常使用文档

这类文档只适合发邮件同事使用，不适合拿来做技术接管：

- [给同事-一键使用说明.txt](/root/multi-cloud-email-sender/%E7%BB%99%E5%90%8C%E4%BA%8B-%E4%B8%80%E9%94%AE%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E.txt)
- [同事值班SOP_傻瓜版.txt](/root/multi-cloud-email-sender/docs/%E5%90%8C%E4%BA%8B%E5%80%BC%E7%8F%ADSOP_%E5%82%BB%E7%93%9C%E7%89%88.txt)

普通同事只负责：

- 启动
- 停止
- 预检
- 报障

普通同事**不应该**：

- 手动修改 `track_domain`
- 手动运行 `cloudflared`
- 手动改 Cloudflare DNS
- 手动改 Windows 上的 `config.yml`

### 技术接管文档

本文件属于技术接管文档，适合处理：

- Cloudflare 账号归属
- Cloudflare zone 接管
- Cloudflare Tunnel 新建或迁移
- Windows 服务器 `cloudflared` 配置
- 应用内 `track_domain` 更新
- 启动链路/追踪链路验证

---

## 2. 交接目标

本次交接的最终目标不是“今天先凑合能发”，而是：

1. 公司技术同事能独立登录并管理当前有效的 Cloudflare zone
2. 公司技术同事能独立管理当前有效的 Cloudflare Tunnel
3. 追踪域名统一为 `https://track.louisliu.fun`
4. Windows 服务器上的 `cloudflared` 配置与新的公司 Cloudflare 账号一致
5. 应用启动时 fixed-domain 检查可以通过
6. 离职人退出后，公司仍能独立维护

---

## 3. 关键结论

### 3.1 旧 tunnel 不再作为默认主路径

旧 tunnel：

- 名称：`email-tracker-dev`
- UUID：`9ff93171-7bbd-4a91-b716-abfe2ecc6f83`

当前应把它视为**历史对象**，不是默认可复用资源。

原因：

- 旧 tunnel 对应旧账号上下文的风险很高
- 当前迁移方向已经切到新的 Cloudflare zone / 新的 nameserver 组
- 仓库已有专项手册明确写了：**在新账号下应新建 tunnel，而不是优先复用旧 `9ff...`**

因此，这份文档的标准口径是：

> 如果当前最终采用的是新的 Cloudflare zone / 新的 Cloudflare 账号，那么默认路径就是“在新账号下新建 tunnel”，而不是“先尝试复用旧 9ff... 再说”。

### 3.2 当前是双阻塞，不是单阻塞

接手时不要只盯着 “zone 是否 Active”。

当前至少有两个阻塞项必须都确认：

1. **Cloudflare zone 是否已经 Active**
2. **最终使用的 tunnel 是否确实属于当前公司可控的 Cloudflare 账号**

这两个条件缺一个都不算接管完成。

### 3.3 `track.louisliu.fun` 是推荐的正式追踪域名

历史上讨论过：

- `track-dev.louisliu.fun`
- `track.louisliu.fun`

当前推荐收敛到：

```text
https://track.louisliu.fun
```

说明：

- `track-dev` 和 `track` 对 `louisliu.fun` 来说都属于一级子域名
- 改成 `track` 是命名收敛和长期运维简化，不是层级问题

---

## 4. 单一真相与主参考文档

为了避免“长文、短文、SOP、聊天记录彼此打架”，本次接管应按以下优先级理解文档：

### 第一优先级：专项操作手册

1. [cloudflare_activation_manual.md](/root/multi-cloud-email-sender/docs/cloudflare_activation_manual.md)
2. [track_domain_update_guide.md](/root/multi-cloud-email-sender/docs/track_domain_update_guide.md)
3. [cloudflared_config_template.yml](/root/multi-cloud-email-sender/docs/cloudflared_config_template.yml)

这些文件负责“怎么操作”。

### 第二优先级：本技术交接文档

本文件负责：

- 交代背景
- 统一路径
- 明确资产归属与交接风险
- 告诉接手人到底该选哪条路线

### 第三优先级：旧 handoff / 旧长文

下列文件可以作为补充背景，但不应再作为第一执行入口：

- [.claude/handoffs/2026-03-13-165731-cloudflare-tracking-migration.md](/root/multi-cloud-email-sender/.claude/handoffs/2026-03-13-165731-cloudflare-tracking-migration.md)
- [离职交接-Cloudflare追踪域名与账号迁移.md](/root/multi-cloud-email-sender/docs/%E7%A6%BB%E8%81%8C%E4%BA%A4%E6%8E%A5-Cloudflare%E8%BF%BD%E8%B8%AA%E5%9F%9F%E5%90%8D%E4%B8%8E%E8%B4%A6%E5%8F%B7%E8%BF%81%E7%A7%BB.md)

原因：

- 这些文件保留了大量排查过程
- 但对接手人来说，优先需要的是单一执行口径，而不是历史分支讨论

---

## 5. 最后已知事实与当前状态

### 5.1 域名与 nameserver

已知事实：

- 主域名：`louisliu.fun`
- 域名注册商：阿里云
- 历史上域名曾使用旧 Cloudflare nameserver：
  - `may.ns.cloudflare.com`
  - `noel.ns.cloudflare.com`
- 后续又创建过新的 Cloudflare zone，对应新的 nameserver：
  - `haley.ns.cloudflare.com`
  - `keenan.ns.cloudflare.com`

最后一次会话的状态是：

- 用户已经在新的 Cloudflare zone 里导入了 DNS 记录
- Cloudflare 页面仍在等待 nameserver propagation
- 用户点击过 `I updated my nameservers`

截至当前文档编写时，**并未再次验证**：

- 新 zone 是否已经最终 `Active`
- `nslookup -type=ns louisliu.fun` 是否已返回 `haley/keenan`

因此这些必须由接手人重新确认。

### 5.2 Cloudflare Tunnel

最后已知的旧 tunnel 信息：

| 项目 | 值 |
|------|----|
| 旧 tunnel 名称 | `email-tracker-dev` |
| 旧 tunnel UUID | `9ff93171-7bbd-4a91-b716-abfe2ecc6f83` |
| 最后已知 Windows cloudflared 路径 | `C:\Users\A\Downloads\cloudflared.exe` |
| 最后已知本地配置路径 | `C:\Users\A\.cloudflared\config.yml` |

但请注意：

- 这些信息描述的是**历史/当前服务器本地状态**
- 不代表这些对象已经属于公司最终接管的 Cloudflare 账号

### 5.3 应用与脚本

当前 repo 中与本次交接直接相关的运行逻辑：

- `start.bat`：启动 Windows 系统时会先校验固定追踪域名能否公网返回 `200`
- `03-发信前检查.bat`：发信前预检
- `04-追踪链路诊断.bat`：诊断追踪链路问题

含义：

- 如果把 `track_domain` 改成了一个还没打通的新域名
- 系统会故意拦住启动

这不是 bug，而是保护机制。

### 5.4 本地 repo 中已做但未提交的改动

当前仓库里有以下本地修改尚未提交：

- `03-发信前检查.bat`
  - 预期追踪域名示例改为 `https://track.louisliu.fun`
- `docs/VM_START_GUIDE.txt`
  - 固定域名示例改为 `https://track.louisliu.fun`

另外还有以下辅助文件尚未纳入版本控制：

- `docs/cloudflare_activation_manual.md`
- `docs/track_domain_update_guide.md`
- `docs/cloudflared_config_template.yml`
- `louisliu.fun.cloudflare.zone`
- 本技术交接文档

如果这些文件最终要成为正式交接材料，建议接手团队决定是否纳入版本库。

---

## 6. 运行环境与路径说明

### 6.1 不要混淆 Linux 工作区和 Windows 生产环境

当前会话中的代码工作区位于 Linux：

```text
/root/multi-cloud-email-sender
```

但真实运行环境是 Windows 机器 / Windows 虚拟机。

因此：

- Linux 工作区里的文件路径不能直接当作 Windows 机器上的现成路径
- 如果某个文件只存在于当前工作区，就必须额外交付给接手人

### 6.2 最后已知 Windows 环境信息

从用户此前会话可确认的最后已知信息：

| 项目 | 最后已知值 |
|------|------------|
| 项目目录 | `C:\Users\A\Desktop\multi-cloud-email-sender-main` |
| cloudflared 可执行文件 | `C:\Users\A\Downloads\cloudflared.exe` |
| cloudflared 配置文件 | `C:\Users\A\.cloudflared\config.yml` |

### 6.3 必须补充的“实际交付位置”

如果下面这些文件只在当前 Linux 工作区存在，就需要补交到团队可访问的位置：

- `louisliu.fun.cloudflare.zone`
- 本技术交接文档
- 同事版交接文档（md / pdf）
- 专项操作手册

建议至少交付到其中一个位置：

- 公司共享盘
- 接手同事本地电脑
- Windows 服务器固定目录
- 团队知识库 / 文档系统

---

## 7. 账号与权限交接要求

这部分是最容易被低估但最关键的内容。

### 7.1 Cloudflare

必须确认：

- 当前生效 zone 在哪个 Cloudflare 账号 / 组织下
- 至少两位公司同事拥有管理权限
- 至少一位公司同事具备 owner 或等效高权限
- 2FA 不再只绑定在离职人个人设备上

必须明确记录：

- 登录邮箱
- 组织名
- 当前 owner
- 是否启用 SSO
- 2FA 管理方式

### 7.2 阿里云域名

必须确认：

- 接手同事能登录阿里云域名控制台
- 接手同事能查看 `louisliu.fun` 的当前 NS
- 接手同事有权限做必要的 NS 调整或复核

### 7.3 Windows 服务器

必须确认：

- 接手同事有管理员权限
- 接手同事能修改 `%USERPROFILE%\.cloudflared\config.yml`
- 接手同事能执行 `Restart-Service cloudflared`
- 接手同事能打开系统前端并进入“系统设置”

### 7.4 代码仓库

必须确认：

- 接手同事能访问 GitHub / Gitee 远端
- 接手同事能提交文档与脚本修订

---

## 8. 技术接管标准路径

> 下面是推荐默认路径。  
> 原则：新的公司账号 + 新的 zone + 新的 tunnel + `track.louisliu.fun`

### 步骤 1：确认新 zone 是否已经接管成功

执行：

```powershell
nslookup -type=ns louisliu.fun
```

目标：

- 返回新的 Cloudflare nameserver
- 在 Dashboard 中看到 zone 为 `Active`

若 zone 未 `Active`：

- 暂停后续技术切换
- 先处理 nameserver propagation / zone 激活问题

### 步骤 2：确认 DNS 记录完整

在新的 Cloudflare zone 中至少确认以下记录存在：

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

如有缺失：

- 参考 `louisliu.fun.cloudflare.zone`
- 或参考 `cloudflare_activation_manual.md`

### 步骤 3：在新账号下创建新的 tunnel

不要默认复用旧 `9ff...`。

标准做法：

1. 登录新的公司 Cloudflare 账号
2. 进入 `Zero Trust` → `Networks` → `Tunnels`
3. 点击 `Create a tunnel`
4. 选择 `Cloudflared`
5. 建议命名为：

```text
email-sender-tunnel
```

6. 记录新生成的：
   - tunnel ID
   - tunnel token
7. 在 `Public Hostname` 中添加：
   - Domain：`louisliu.fun`
   - Subdomain：`track`
   - Service：`http://localhost:8000`

如果这一步已经在 Dashboard 内完成，通常不需要再手工执行 `tunnel route dns`。

### 步骤 4：更新 Windows 服务器上的 cloudflared

当前仓库给了两种思路，但推荐优先级如下：

#### 方案 A：Token 方式（推荐）

适用于：

- 新账号新建 tunnel 后
- 希望服务部署更直接、少依赖旧配置残留

执行思路见：

- [cloudflare_activation_manual.md](/root/multi-cloud-email-sender/docs/cloudflare_activation_manual.md)

核心动作是：

1. 停止旧 `cloudflared` 服务
2. 卸载旧服务
3. 用新 tunnel token 安装新服务
4. 启动服务

#### 方案 B：config.yml 方式

适用于：

- 需要继续维护显式本地配置文件

模板见：

- [cloudflared_config_template.yml](/root/multi-cloud-email-sender/docs/cloudflared_config_template.yml)

目标配置核心应为：

```yaml
ingress:
  - hostname: track.louisliu.fun
    service: http://localhost:8000
  - service: http_status:404
```

并且：

- `tunnel:` 要替换成**新账号下新建的 tunnel ID**
- `credentials-file:` 要替换成新的 json 路径

### 步骤 5：重启并确认 cloudflared 服务

执行：

```powershell
Restart-Service cloudflared
Get-Service cloudflared
```

目标：

- 服务状态为 `Running`

如失败，先看：

- token 是否正确
- 网络是否能访问 Cloudflare
- 本机 `config.yml` 是否有语法错误

### 步骤 6：确认本地后端可用

在 Windows 服务器本机确认：

```powershell
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/track/open/ping-test"
```

目标：

- 返回 `200`

如果本地后端都不通，就先不要继续查 Cloudflare。

### 步骤 7：更新应用内 `track_domain`

优先推荐 UI 更新：

1. 打开前端
2. 进入“系统设置”
3. 把追踪域名改成：

```text
https://track.louisliu.fun
```

专项说明见：

- [track_domain_update_guide.md](/root/multi-cloud-email-sender/docs/track_domain_update_guide.md)

如果 UI 不可用，再走 API。

### 步骤 8：确认公网追踪接口可用

执行：

```powershell
Invoke-WebRequest -UseBasicParsing "https://track.louisliu.fun/api/track/open/ping-test"
```

目标：

- 返回 `200`

### 步骤 9：验证启动链路

执行：

- `03-发信前检查.bat`
- `01-启动系统.bat`

目标：

- fixed-domain 检查通过
- 系统能正常进入前端

### 步骤 10：做真实邮件最小闭环

必须做一次完整验证：

1. 创建测试任务
2. 发给自己邮箱
3. 打开邮件
4. 点击正文里的一个 `http/https` 链接
5. 查看看板与日志是否更新

如果没有做这一步，交接仍然不完整。

---

## 9. 验证清单

### 9.1 DNS 层

- [ ] `nslookup -type=ns louisliu.fun` 返回新 zone 的 nameserver
- [ ] Cloudflare Dashboard 中 zone 状态为 `Active`
- [ ] `track.louisliu.fun` 已作为 Public Hostname 或等效 DNS 记录存在

### 9.2 Tunnel 层

- [ ] 新 tunnel 已在公司账号下创建
- [ ] Windows 上 `cloudflared` 已使用新 tunnel 配置运行
- [ ] `cloudflared` 服务为 `Running`

### 9.3 应用层

- [ ] `http://localhost:8000/api/track/open/ping-test` 返回 `200`
- [ ] `https://track.louisliu.fun/api/track/open/ping-test` 返回 `200`
- [ ] 应用 `track_domain` 已更新到 `https://track.louisliu.fun`

### 9.4 业务层

- [ ] 发信测试成功
- [ ] 打开统计正常
- [ ] 点击统计正常

---

## 10. 故障排查顺序

如果接手后仍然失败，按这个顺序排查：

1. 先看 zone 是否 `Active`
2. 再看 `track.louisliu.fun` 是否已在新 tunnel Public Hostname 中
3. 再看 `cloudflared` 服务是否在 Windows 上运行
4. 再看本地后端 `localhost:8000` 是否可用
5. 再看公网 `ping-test` 是否可用
6. 最后再看应用内 `track_domain` 是否已经写对

不要倒序查。

### 禁止的错误排查习惯

- 让普通同事自己改 `track_domain`
- 让普通同事自己跑 `cloudflared`
- 先改应用配置，后验公网域名
- 在新账号接管时继续把旧 `9ff...` 当默认主路径
- 只看 DNS，不看 tunnel 归属

---

## 11. 回退与应急策略

### 11.1 短期回退目标

如果新账号接管当天来不及全部完成，至少要保证：

- 普通同事知道不能乱改
- 技术同事能定位问题点
- 日志和配置不会丢

### 11.2 不推荐的长期回退

以下方案只适合极短时应急，不适合长期：

- 回到 quick tunnel 作为正式生产方案
- 继续依赖离职人个人 Cloudflare 账号
- 继续依赖旧账号下的旧 tunnel，但没有公司管理员权限

### 11.3 真正的回退原则

回退时要回到“公司可控”的状态，而不是“今天谁手里刚好能点进去”的状态。

---

## 12. 必须交给技术接手人的材料

### 12.1 账号与访问

- Cloudflare 账号 / 组织名
- Cloudflare 权限列表
- 阿里云域名控制台访问路径
- Windows 服务器登录方式
- GitHub / Gitee 仓库权限

### 12.2 文档

- 本文档
- [cloudflare_activation_manual.md](/root/multi-cloud-email-sender/docs/cloudflare_activation_manual.md)
- [track_domain_update_guide.md](/root/multi-cloud-email-sender/docs/track_domain_update_guide.md)
- [cloudflared_config_template.yml](/root/multi-cloud-email-sender/docs/cloudflared_config_template.yml)
- [.claude/handoffs/2026-03-13-165731-cloudflare-tracking-migration.md](/root/multi-cloud-email-sender/.claude/handoffs/2026-03-13-165731-cloudflare-tracking-migration.md)

### 12.3 配置与迁移素材

- `louisliu.fun.cloudflare.zone`
- 阿里云导出的 zone 文件：`/root/Downloads/louisliu.fun_1773390294285.txt`
- Windows 当前 `%USERPROFILE%\.cloudflared\config.yml` 备份
- Windows 当前 cloudflared 服务安装方式说明

### 12.4 程序相关文件

- `03-发信前检查.bat`
- `04-追踪链路诊断.bat`
- `start.bat`
- `docs/VM_START_GUIDE.txt`

---

## 13. 交接完成标准

技术接管完成的标准必须同时满足：

1. 公司账号能登录并管理有效 Cloudflare zone
2. 公司账号能管理有效 Cloudflare Tunnel
3. `track.louisliu.fun` 对公网返回 `200`
4. Windows 服务器重启后，系统仍能在 fixed-domain 模式下正常启动
5. 普通同事依旧只需要按既有双击 SOP 操作
6. 离职人退出后，公司不再依赖个人账号维持追踪链路

---

## 14. 关键命令速查

### 查看 nameserver

```powershell
nslookup -type=ns louisliu.fun
```

### 查看本地后端追踪接口

```powershell
Invoke-WebRequest -UseBasicParsing "http://localhost:8000/api/track/open/ping-test"
```

### 查看公网追踪接口

```powershell
Invoke-WebRequest -UseBasicParsing "https://track.louisliu.fun/api/track/open/ping-test"
```

### 查看 cloudflared 服务

```powershell
Get-Service cloudflared
```

### 重启 cloudflared 服务

```powershell
Restart-Service cloudflared
```

### 查看当前应用设置

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/settings"
```

### API 更新 `track_domain`

```powershell
$body = @{ track_domain = "https://track.louisliu.fun" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/settings" -ContentType "application/json" -Body $body
```

---

## 15. 最后的技术建议

如果时间只够做最关键的事，优先级如下：

1. 账号归属交接
2. zone 激活
3. 新账号下新建 tunnel
4. Windows `cloudflared` 接到新 tunnel
5. `track_domain` 改为 `https://track.louisliu.fun`
6. 真实邮件闭环验证

不要倒序。

因为：

- 脚本和文档后面都能补
- 但如果账号归属和 tunnel 归属没交清楚，离职后最难补救
