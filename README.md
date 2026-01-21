# 多云邮件营销发送系统 (Multi-Cloud Email Sender)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB)](https://reactjs.org/)

这是一个专为非技术人员设计的企业级邮件营销系统。它集成了**阿里云 DirectMail** 和 **腾讯云 SES** 双通道，能够智能规避风控，支持百万级邮件的分批调度发送。

核心解决痛点：**无需登录复杂的云控制台，一站式管理所有发信任务，且支持高度个性化的变量替换（如姓名、性别、生日等）。**

![Dashboard Preview](https://via.placeholder.com/800x400?text=%E7%B3%BB%E7%BB%9F%E7%95%8C%E9%9D%A2%E9%A2%84%E8%A7%88)

## ✨ 核心亮点

*   **☁️ 多云双通道切换**：支持阿里云和腾讯云一键切换。当某家服务商额度耗尽或被限流时，可立即切换线路，保障业务连续性。
*   **🛡️ 智能防风控策略**：
    *   **随机抖动 (Jitter)**：模拟人工发送行为，在每封邮件之间增加随机延迟，降低进入垃圾箱的概率。
    *   **自动分批**：支持设置“每15分钟发送2000封”等策略，平滑推送。
*   **⏰ 计划任务**：支持设置“计划开始时间”，提前安排好明早的营销活动，系统到点自动执行。
*   **💪 强力数据清洗**：
    *   智能解析 CSV/Excel 导出文件，完美兼容 Tab 分隔符、UTF-16 等复杂编码。
    *   自动去除邮箱前后的空格、不可见字符，最大限度降低“无效地址”报错。
*   **📝 模板云端同步**：一键拉取阿里云后台已审核通过的模板。支持 `{UserName}`, `{Gender}` 等动态变量替换。
*   **👀 全链路监控**：实时查看发送进度、成功率，支持任务的暂停与恢复。

---

## 🚀 部署与安装指南

本系统支持两种模式：**源码部署**（适合技术运维）和 **EXE 离线运行**（适合办公电脑）。

### 方式一：EXE 离线运行（推荐老板/运营使用）

无需安装 Python 环境，下载即用。

1.  下载最新的 `EmailSender.zip` 压缩包。
2.  解压后，进入文件夹。
3.  双击运行 **`EmailSender.exe`**。
4.  系统会自动打开浏览器窗口（`http://localhost:8000`）。
5.  **注意**：数据文件 `email_app.db` 会自动生成在同级目录下，请妥善保管。

### 方式二：源码部署（适合 Linux 服务器）

**环境要求**：Python 3.10+, Node.js 18+

```bash
# 1. 克隆代码
git clone git@gitee.com:louisshawn-art/multi-cloud-email-sender.git
cd multi-cloud-email-sender

# 2. 一键启动 (Linux/Mac)
./start.sh

# 2. 一键启动 (Windows)
# 双击 start.bat
```

---

## 📖 详细使用说明书

### 第一步：系统配置
进入 **[系统设置]** 页面：
1.  **阿里云/腾讯云配置**：填入对应的 `AccessKey ID` 和 `Secret`。
2.  **全局默认发件人昵称**：设置一个兜底的发件人名字（如“XX客服中心”）。当模板和任务都没设置具体人名时，会显示这个名字。

### 第二步：导入联系人
进入 **[联系人管理]** 页面：
1.  准备好 CSV 文件。
    *   **必须包含**：`EmailAddr` 列（收件人邮箱）。
    *   **推荐包含**：`UserName`（姓名）、`Gender`（称谓）、`Birthday`（生日）等。
2.  点击“上传 CSV 文件”，系统会自动解析并显示总人数。
3.  *提示：系统会自动处理文件中的 Tab 符号和乱码，您直接从 Excel 导出 CSV 即可。*

### 第三步：准备邮件模板
进入 **[模板管理]** 页面：
1.  **新建/编辑模板**：
    *   **模板名称**：内部管理用（如“元旦大促A版”）。
    *   **发送人名称**：**可选项**。如果填写（如“市场部经理”），该模板发出的邮件将显示此名字。
    *   **邮件标题/正文**：支持变量插入。例如：
        > 标题：`{UserName} {Gender}，这是您的专属优惠！`
        > 正文：`亲爱的 {UserName}，祝您生日快乐...`
2.  **从云端同步**：点击“从阿里云同步”，可直接把后台审核好的模板拉取到本地。

### 第四步：创建发送任务
进入 **[邮件任务]** 页面，点击“创建新任务”：

| 字段 | 说明 |
| :--- | :--- |
| **服务商** | 选择阿里云或腾讯云。 |
| **本次任务发信人昵称** | **最高优先级**。如果填写（如“活动小助手”），将强制覆盖模板和全局设置的名字。 |
| **选择模板** | 选择刚才准备好的模板。 |
| **选择列表** | 选择上传的联系人名单。 |
| **发信地址** | 下拉选择已验证的发信域名账号（如 `admin@yourdomain.com`）。 |
| **分批策略** | 例如：每 `15` 分钟发送 `2000` 封。 |
| **计划开始时间** | 选填。如果不选，点击“开始”后立即发送；如果选了未来时间，系统会进入 `计划中` 状态，到点自动开跑。 |

---

## 🛠️ API 文档 (开发人员参考)

系统基于 FastAPI 开发，启动后访问 `http://localhost:8000/docs` 可查看完整的 Swagger UI 文档。

主要接口：
*   `POST /api/campaigns`: 创建任务
*   `POST /api/contacts/upload`: 上传 CSV
*   `GET /api/senders/sync`: 同步云端发信地址

## 🤝 贡献指南

1.  Fork 本仓库
2.  创建特性分支 (`git checkout -b feature/AmazingFeature`)
3.  提交更改 (`git commit -m 'Add some AmazingFeature'`)
4.  推送到分支 (`git push origin feature/AmazingFeature`)
5.  提交 Pull Request

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE) 开源。您可以免费用于商业用途，但需保留原作者版权声明。