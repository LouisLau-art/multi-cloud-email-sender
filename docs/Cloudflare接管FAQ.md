# Cloudflare 接管 FAQ

---

## Q1：为什么不能继续长期用离职人的个人 Cloudflare 账号？

因为这样会把公司的持续运营绑定在个人账号上。

风险包括：

- 离职后无法登录
- 2FA 在离职人手机上
- zone / tunnel 无法修改
- 出问题时没人能修

---

## Q2：为什么不能默认继续复用旧 tunnel `9ff93171-7bbd-4a91-b716-abfe2ecc6f83`？

因为旧 tunnel 很可能属于旧账号上下文。

在新的公司账号 / 新的 zone 下，默认应该新建 tunnel，避免：

- 账号归属不清
- `CNAME Cross-User Banned`
- 后续长期维护困难

---

## Q3：为什么不能先把应用里的 `track_domain` 改掉再说？

因为启动脚本会先检查公网追踪域名。

如果新域名还没打通，先改 `track_domain` 的结果是：

- 系统启动被拦住
- 普通同事无法正常使用

---

## Q4：为什么普通同事不能自己改 `track_domain` 或跑 `cloudflared`？

因为这不是日常使用动作，而是管理员动作。

普通同事的职责应限定为：

- 启动
- 停止
- 预检
- 报障

否则一旦误操作，容易把追踪链路搞断。

---

## Q5：如果 zone 还没 Active，该干嘛？

先不要继续切应用配置。

先做：

1. 查 `nslookup -type=ns louisliu.fun`
2. 看注册商当前 NS
3. 看 Cloudflare zone 状态

---

## Q6：如果 zone Active 了，但 `track.louisliu.fun` 还是不通怎么办？

按这个顺序查：

1. 是否已经在新账号下创建新 tunnel
2. Public Hostname 是否配置了 `track -> http://localhost:8000`
3. Windows `cloudflared` 服务是否 Running
4. `http://localhost:8000/api/track/open/ping-test` 是否返回 `200`
5. `https://track.louisliu.fun/api/track/open/ping-test` 是否返回 `200`

---

## Q7：为什么要统一成 `track.louisliu.fun`？

主要是为了命名统一和长期维护方便。

它不是因为“层级必须更浅”才换，而是因为：

- 更简洁
- 更适合作为正式生产 hostname
- 当前仓库文档和预检默认值已向这个名字对齐

---

## Q8：如果离职前来不及全部做完，最少要做到什么？

最少做到：

1. 文档交出去
2. 权限交出去
3. 技术同事知道主路径
4. 未完成项清楚

这比“你自己继续顶着账号跑，但没人会接”更重要。
