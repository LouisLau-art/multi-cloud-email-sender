from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ses.v20201002 import ses_client, models
import json
import base64


class TencentService:
    @staticmethod
    def create_client(secret_id, secret_key, region):
        cred = credential.Credential(secret_id, secret_key)
        httpProfile = HttpProfile()
        httpProfile.endpoint = "ses.tencentcloudapi.com"
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        return ses_client.SesClient(cred, region, clientProfile)

    @staticmethod
    def send_mail(
        secret_id: str,
        secret_key: str,
        region: str,
        from_email: str,
        to_email: str,
        subject: str,
        html_body: str,
        from_alias: str = None,
        template_id: str = None,
        template_params: str = None,
        reply_to_address: str = None,
    ):
        client = TencentService.create_client(secret_id, secret_key, region)

        req = models.SendEmailRequest()

        # 自动补全发信地址
        real_from_email = from_email
        if "@" not in from_email:
            real_from_email = f"notification@{from_email}"

        params = {
            "FromEmailAddress": f"{from_alias} <{real_from_email}>"
            if from_alias
            else real_from_email,
            "Destination": [to_email],
        }

        if reply_to_address:
            params["ReplyToAddresses"] = reply_to_address

        # 模式一：使用云端模板 (Template) - 推荐，无需额外权限
        if template_id:
            # Tencent API field name is 'TemplateData'
            params["Template"] = {
                "TemplateID": int(template_id),
                "TemplateData": template_params or "{}",
            }
            # 模板模式下，Subject 通常由模板决定，但在 API 里传 Subject 会覆盖模板默认 Subject
            if subject:
                params["Subject"] = subject

        # 模式二：自定义 HTML (Simple) - 需要申请权限
        else:
            if html_body:
                html_base64 = base64.b64encode(html_body.encode("utf-8")).decode(
                    "utf-8"
                )
            else:
                html_base64 = ""

            params["Subject"] = subject
            params["Simple"] = {"Html": html_base64}

        req.from_json_string(json.dumps(params))

        return client.SendEmail(req)

    @staticmethod
    def query_senders(client):
        """获取发信域名/地址列表"""
        req = models.ListEmailIdentitiesRequest()
        resp = client.ListEmailIdentities(req)
        return resp

    @staticmethod
    def query_templates(client):
        """获取模板列表"""
        req = models.ListEmailTemplatesRequest()
        req.Limit = 50
        req.Offset = 0
        resp = client.ListEmailTemplates(req)
        return resp

    @staticmethod
    def get_template(client, template_id):
        """获取模板详情"""
        req = models.GetEmailTemplateRequest()
        req.TemplateID = template_id
        resp = client.GetEmailTemplate(req)
        return resp

    @staticmethod
    def get_send_email_status(
        secret_id: str,
        secret_key: str,
        region: str,
        request_date: str,
        message_id: str = None,
        to_email_address: str = None,
        offset: int = 0,
        limit: int = 100,
    ):
        """
        获取邮件发送状态 (Pull Tracking)

        Args:
            secret_id: 腾讯云密钥 ID
            secret_key: 腾讯云密钥
            region: 区域 (ap-guangzhou 或 ap-hongkong)
            request_date: 发送日期，格式 yyyy-MM-dd
            message_id: SendEmail 返回的 MessageId (可选)
            to_email_address: 收件人邮箱 (可选)
            offset: 偏移量 (默认 0)
            limit: 拉取条数 (最大 100)

        Returns:
            EmailStatusList: 包含 UserOpened, UserClicked 等字段的状态列表
        """
        client = TencentService.create_client(secret_id, secret_key, region)

        req = models.GetSendEmailStatusRequest()

        params = {
            "RequestDate": request_date,
            "Offset": offset,
            "Limit": limit,
        }

        if message_id:
            params["MessageId"] = message_id
        if to_email_address:
            params["ToEmailAddress"] = to_email_address

        req.from_json_string(json.dumps(params))

        return client.GetSendEmailStatus(req)
