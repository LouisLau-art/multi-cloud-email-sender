from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ses.v20201002 import ses_client, models

class TencentService:
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
        cred = credential.Credential(secret_id, secret_key)
        client = ses_client.SesClient(cred, region)
        
        req = models.SendEmailRequest()
        req.FromEmailAddress = f"{from_alias} <{from_email}>" if from_alias else from_email
        req.Destination = [to_email]
        req.Subject = subject
        req.Html = html_body
        
        return client.SendEmail(req)
