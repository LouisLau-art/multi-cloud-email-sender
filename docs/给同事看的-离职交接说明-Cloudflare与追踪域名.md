# 给同事看的离职交接说明：Cloudflare 与追踪域名

> 文档版本：2026-03-17  
> 文档目的：给接手同事和管理者看的正式交接说明  
> 适用对象：普通使用同事、技术接手同事、管理者

---

## 一、先说结论

这套邮件系统的“打开率 / 点击率统计”依赖 Cloudflare 追踪域名。

当前最大的离职风险不是系统代码本身，而是：

- Cloudflare 资源曾经或目前仍可能和离职人的个人账号有关
- 如果账号、域名、tunnel、Windows 服务器配置没有交清楚，离职后系统可能出现：
  - 可以发邮件，但统计失效
  - 启动脚本因为追踪域名不可达而直接不让系统启动
  - 同事找不到该去哪里修改 DNS / tunnel / track_domain

**接手工作的核心不是“先让系统跑起来”，而是“让公司完全接管这条追踪链路”。**

---

## 二、这份文档给谁看

### 1. 普通使用同事

如果你只是日常负责：

- 开机
- 启动系统
- 发邮件
- 看统计

你重点看：

- 第四部分《普通同事只需要知道什么》
- 第九部分《发生问题时先做什么》

### 2. 技术接手同事

如果你负责接手：

- Cloudflare
- 域名
- Windows 服务器
- tunnel
- 系统设置

你重点看：

- 第三部分《当前交接重点》
- 第五部分《最后已知状态》
- 第六部分《技术接手人操作步骤》
- 第七部分《主参考文档》
- 第十部分《交接完成标准》

### 3. 管理者

如果你负责安排交接，重点看：

- 第三部分《当前交接重点》
- 第八部分《账号与权限必须交接的内容》
- 第十部分《交接完成标准》

---

## 三、当前交接重点

当前交接重点只有三件事：

1. **Cloudflare 账号归属要从个人风险变成公司可控**
2. **`track.louisliu.fun` 要成为正式固定追踪域名**
3. **Windows 服务器上的 tunnel 配置要和新 Cloudflare 账号保持一致**

换句话说，接手人最终要做到：

- 公司账号能登录 Cloudflare 并管理 `louisliu.fun`
- 公司账号能管理用于追踪的 tunnel
- `https://track.louisliu.fun/api/track/open/ping-test` 对公网返回 `200`
- 启动脚本看到 `Tracking check: OK`

---

## 四、普通同事只需要知道什么

### 1. 每天怎么用

普通同事还是只按现有 SOP 使用：

- 启动：`01-启动系统.bat`
- 停止：`02-停止系统.bat`
- 发信前检查：`03-发信前检查.bat`
- 追踪诊断：`04-追踪链路诊断.bat`

### 2. 普通同事禁止做什么

普通同事 **不要** 做以下任何事：

- 不要手动修改 `track_domain`
- 不要手动运行 `cloudflared` 命令
- 不要自己改 Cloudflare DNS
- 不要自己改阿里云域名 NS
- 不要自己改 Windows 服务器里的 `config.yml`

### 3. 如果看到异常怎么办

#### 情况 A：启动后提示 tracking 不可用

做法：

1. 双击 `04-追踪链路诊断.bat`
2. 保留完整输出
3. 把输出和 `logs` 目录里的日志一起发给技术接手同事

#### 情况 B：已发出的邮件统计一直是 0

做法：

1. 先双击 `03-发信前检查.bat`
2. 如果不是全部通过，不要继续发新任务
3. 联系技术接手同事处理

### 4. 普通同事的主参考文档

- [给同事-一键使用说明.txt](/root/multi-cloud-email-sender/%E7%BB%99%E5%90%8C%E4%BA%8B-%E4%B8%80%E9%94%AE%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E.txt)
- [同事值班SOP_傻瓜版.txt](/root/multi-cloud-email-sender/docs/%E5%90%8C%E4%BA%8B%E5%80%BC%E7%8F%ADSOP_%E5%82%BB%E7%93%9C%E7%89%88.txt)

普通同事不需要去读 Cloudflare 技术操作文档。

---

## 五、最后已知状态（截至 2026-03-13，之后需由接手人复核）

以下内容是最后一次排查中确认过的状态，不应被当成 2026-03-17 的实时事实，接手人必须自行复核。

### 1. 域名与 DNS

- 主域名：`louisliu.fun`
- 域名注册商：阿里云
- 历史上域名曾指向旧 Cloudflare nameserver：
  - `may.ns.cloudflare.com`
  - `noel.ns.cloudflare.com`
- 之后新建了新的 Cloudflare zone，并拿到新的 nameserver：
  - `haley.ns.cloudflare.com`
  - `keenan.ns.cloudflare.com`
- 最后一次会话时，新 zone 仍在等待 nameserver propagation

### 2. Cloudflare Tunnel

- 旧 tunnel 名称：`email-tracker-dev`
- 旧 tunnel UUID：`9ff93171-7bbd-4a91-b716-abfe2ecc6f83`

### 3. 关键结论

#### 不再把“复用旧 tunnel UUID 9ff...”作为默认主路径

当前仓库里已经有专项手册明确写了：

- **旧 tunnel `9ff...` 属于旧账号**
- **如果现在走新的 Cloudflare 账号 / 新的 zone，应默认新建新 tunnel**

所以给接手同事的标准口径是：

> 如果已经迁移到新的 Cloudflare 账号或新的 zone，就默认在新账号下重新创建 tunnel，不再优先尝试复用旧 `9ff...`。

这点非常重要，避免同事在“复用旧 tunnel”和“新建 tunnel”两条路径之间反复试错。

### 4. 目标固定追踪域名

推荐统一使用：

```text
https://track.louisliu.fun
```

说明：

- 历史上也出现过 `track-dev.louisliu.fun`
- 当前建议统一收敛成 `track.louisliu.fun`
- 仓库里本地文档和预检默认值也已经改到这个目标域名

---

## 六、技术接手人操作步骤

> 下面这些步骤 **仅限技术接手同事或管理员执行**。  
> 普通使用同事不需要做，也不应该做。

### 步骤 1：确认当前新的 Cloudflare zone 是否已经 Active

在任一可执行命令的环境中运行：

```powershell
nslookup -type=ns louisliu.fun
```

如果结果已经稳定返回：

- `haley.ns.cloudflare.com`
- `keenan.ns.cloudflare.com`

再去 Cloudflare Dashboard 看 zone 是否已经显示为 `Active`。

如果 zone 还没 Active，不要继续往下做 tunnel 和 `track_domain` 的最终切换。

### 步骤 2：确认新 zone 的 DNS 记录已经导入

接手人需要在 Cloudflare DNS 页面看到至少这些记录：

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

如果缺失，优先参考：

- [cloudflare_activation_manual.md](/root/multi-cloud-email-sender/docs/cloudflare_activation_manual.md)
- `louisliu.fun.cloudflare.zone`

### 步骤 3：在新的 Cloudflare 账号下新建新的 tunnel

**这是默认标准路径。**

不要默认尝试复用旧 `9ff93171-7bbd-4a91-b716-abfe2ecc6f83`。

原因：

- 旧 tunnel 和旧账号绑定的风险很高
- 跨账号/跨 zone 容易出现 `CNAME Cross-User Banned` 等问题
- 离职交接场景下，最重要的是“资产重新归到公司账号”，不是“勉强复用旧对象”

标准做法：

1. 登录当前新的公司可控 Cloudflare 账号
2. 进入 `Zero Trust` → `Networks` → `Tunnels`
3. 新建一条新的 tunnel
4. 在 Public Hostname 中添加：
   - Domain：`louisliu.fun`
   - Subdomain：`track`
   - Service：`http://localhost:8000`

详细参考：

- [cloudflare_activation_manual.md](/root/multi-cloud-email-sender/docs/cloudflare_activation_manual.md)

### 步骤 4：更新 Windows 服务器上的 cloudflared 配置

如果服务器使用的是 `config.yml` 方式，修改：

```text
%USERPROFILE%\.cloudflared\config.yml
```

建议直接参考模板：

- [cloudflared_config_template.yml](/root/multi-cloud-email-sender/docs/cloudflared_config_template.yml)

当前目标配置应指向：

```yaml
ingress:
  - hostname: track.louisliu.fun
    service: http://localhost:8000
  - service: http_status:404
```

如果服务器使用的是 token 方式，则按专项手册重新安装新的服务。

### 步骤 5：重启 cloudflared 服务

在 Windows 上执行：

```powershell
Restart-Service cloudflared
```

然后确认服务处于运行状态。

### 步骤 6：通过 UI 更新应用内 `track_domain`

优先推荐 UI 操作，而不是直接 API。

做法：

1. 启动系统
2. 访问前端页面
3. 进入“系统设置”
4. 把追踪域名改成：

```text
https://track.louisliu.fun
```

专项说明见：

- [track_domain_update_guide.md](/root/multi-cloud-email-sender/docs/track_domain_update_guide.md)

### 步骤 7：验证公网追踪是否真正可用

执行：

```powershell
Invoke-WebRequest -UseBasicParsing "https://track.louisliu.fun/api/track/open/ping-test"
```

目标结果：

- 返回 `200`

### 步骤 8：验证系统启动是否通过

执行：

- 双击 `03-发信前检查.bat`
- 再双击 `01-启动系统.bat`

目标现象：

- 能正常进入系统
- 启动提示或日志体现 `Tracking check: OK`
- 不再因为固定域名不可达而被拦住

### 步骤 9：做一次真实最小发信验证

技术接手人必须做一次最小闭环验证：

1. 发一封测试邮件到自己的邮箱
2. 打开一次邮件
3. 点击正文内一个 `http/https` 链接
4. 确认后台和看板统计正常变化

如果只做了 `ping-test`，但没有做真实邮件验证，交接仍然不算完成。

---

## 七、主参考文档

接手人不要只看这一份长文。下面几份文件是主参考：

### 1. Cloudflare 激活与新 tunnel 操作

- [cloudflare_activation_manual.md](/root/multi-cloud-email-sender/docs/cloudflare_activation_manual.md)

作用：

- 这是 Cloudflare 激活后的专项执行手册
- 当前应把它视为“新账号下新建 tunnel”的主路径

### 2. track_domain 更新说明

- [track_domain_update_guide.md](/root/multi-cloud-email-sender/docs/track_domain_update_guide.md)

作用：

- 说明如何通过 UI 或 API 改应用内追踪域名

### 3. cloudflared 配置模板

- [cloudflared_config_template.yml](/root/multi-cloud-email-sender/docs/cloudflared_config_template.yml)

作用：

- 给 Windows 服务器的 `config.yml` 提供标准模板

### 4. 普通同事值班 SOP

- [同事值班SOP_傻瓜版.txt](/root/multi-cloud-email-sender/docs/%E5%90%8C%E4%BA%8B%E5%80%BC%E7%8F%ADSOP_%E5%82%BB%E7%93%9C%E7%89%88.txt)
- [给同事-一键使用说明.txt](/root/multi-cloud-email-sender/%E7%BB%99%E5%90%8C%E4%BA%8B-%E4%B8%80%E9%94%AE%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E.txt)

作用：

- 给日常发邮件同事使用
- 不负责 Cloudflare 技术接管

---

## 八、账号与权限必须交接的内容

如果下面这些没有交清楚，技术上就算今天能跑，离职后仍然有高风险：

### 1. Cloudflare

- 当前最终要使用的 Cloudflare 账号/组织名
- 谁拥有 owner/admin 权限
- 2FA 由谁持有
- 哪些公司同事已经被加入并能登录

### 2. 阿里云域名

- 谁能登录阿里云域名控制台
- 谁能查看和修改 `louisliu.fun` 的 NS

### 3. Windows 服务器

- 谁能登录服务器
- 谁能修改 `%USERPROFILE%\.cloudflared\config.yml`
- 谁能重启 `cloudflared` 服务
- 谁能打开系统设置并修改 `track_domain`

### 4. 代码仓库

- 谁能访问 GitHub / Gitee
- 谁能提交脚本和文档改动

---

## 九、发生问题时先做什么

### 1. 普通同事的处理方式

只做这几件事：

1. 双击 `03-发信前检查.bat`
2. 如果失败，再双击 `04-追踪链路诊断.bat`
3. 把输出和 `logs` 目录发给技术接手同事

### 2. 技术接手人的排查顺序

严格按这个顺序来：

1. `nslookup -type=ns louisliu.fun`
2. 看 Cloudflare zone 是否 `Active`
3. 看 `track.louisliu.fun` 是否已经存在于新 tunnel Public Hostname 中
4. 看 `cloudflared` 服务是否运行
5. 看 `http://localhost:8000/api/track/open/ping-test` 是否返回 `200`
6. 看 `https://track.louisliu.fun/api/track/open/ping-test` 是否返回 `200`
7. 看应用内 `track_domain` 是否已经更新成 `https://track.louisliu.fun`

### 3. 不要这样排查

- 不要让普通同事自己改 `track_domain`
- 不要让普通同事自己跑 `cloudflared`
- 不要把 quick tunnel 当作长期正式方案
- 不要把“域名已指向 Cloudflare”误认为“公司已经完全接管 Cloudflare 资产”

---

## 十、交接完成标准

只有同时满足下面所有条件，才算真正交接完成：

1. 公司同事能登录并管理当前有效的 Cloudflare zone
2. 公司同事能登录并管理当前有效的 Cloudflare tunnel
3. `track.louisliu.fun` 对公网返回 `200`
4. 系统在固定域名模式下能正常启动
5. 普通同事依然只需要使用既有双击脚本
6. 离职人退出后，系统仍能被公司独立维护

---

## 十一、建议交付给接手人的文件

建议把下面这些一起交给接手人：

- 本文档
- [cloudflare_activation_manual.md](/root/multi-cloud-email-sender/docs/cloudflare_activation_manual.md)
- [track_domain_update_guide.md](/root/multi-cloud-email-sender/docs/track_domain_update_guide.md)
- [cloudflared_config_template.yml](/root/multi-cloud-email-sender/docs/cloudflared_config_template.yml)
- [同事值班SOP_傻瓜版.txt](/root/multi-cloud-email-sender/docs/%E5%90%8C%E4%BA%8B%E5%80%BC%E7%8F%ADSOP_%E5%82%BB%E7%93%9C%E7%89%88.txt)
- [给同事-一键使用说明.txt](/root/multi-cloud-email-sender/%E7%BB%99%E5%90%8C%E4%BA%8B-%E4%B8%80%E9%94%AE%E4%BD%BF%E7%94%A8%E8%AF%B4%E6%98%8E.txt)

如果这些文件只存在于个人电脑或当前 Linux 工作区，还需要额外导出到：

- 团队共享盘
- 接手人的电脑
- Windows 服务器可访问目录
- 或公司文档系统

否则“文档写好了”不等于“文档已经完成交接”。

---

## 十二、最后提醒

这份交接文档的核心不是教普通同事学会 Cloudflare，而是防止离职后出现下面这种情况：

- 普通同事会发邮件，但没人知道怎么修追踪
- 代码在，服务器也在，但 Cloudflare 账号不在公司手里
- 表面上能启动，实际上统计链路随时会断

因此，真正的优先级是：

1. 账号归属
2. zone 与 tunnel 归属
3. `track.louisliu.fun` 打通
4. 日常 SOP 保持不变

顺序不要倒。
