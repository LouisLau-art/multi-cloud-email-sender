# 后端 track_domain 配置更新说明

## 方法一：UI 界面更新（推荐）
1. 启动系统后，访问前端页面 http://localhost:5173
2. 进入「系统设置」页面
3. 在「追踪域名」字段中填入：https://track.louisliu.fun
4. 点击「保存设置」即可

## 方法二：API 直接更新
如果 UI 访问有问题，可以通过 API 直接更新：
```powershell
# PowerShell 命令
$body = @{
    track_domain = "https://track.louisliu.fun"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/settings" -ContentType "application/json" -Body $body
```

## 验证更新是否成功
```powershell
# 查看当前配置
(Invoke-RestMethod -Uri "http://localhost:8000/api/settings").track_domain
# 应该返回：https://track.louisliu.fun
```
