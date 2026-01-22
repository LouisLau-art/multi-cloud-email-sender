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
        from_alias: str = None
    ):
        client = TencentService.create_client(secret_id, secret_key, region)
        
        req = models.SendEmailRequest()
        
        # 自动补全发信地址：如果只是域名，加上前缀
        real_from_email = from_email
        if "@" not in from_email:
            real_from_email = f"notification@{from_email}"

        # 腾讯云要求 Html 内容必须是 Base64 编码
        if html_body:
            html_base64 = base64.b64encode(html_body.encode('utf-8')).decode('utf-8')
        else:
            html_base64 = ""

        # 使用 JSON 字符串初始化请求对象
        params = {
            "FromEmailAddress": f"{from_alias} <{real_from_email}>" if from_alias else real_from_email,
            "Destination": [to_email],
            "Subject": subject,
            "Simple": {
                "Html": html_base64
            }
        }
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