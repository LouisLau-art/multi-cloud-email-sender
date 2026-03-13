import json
from alibabacloud_dm20151123.client import Client as Dm20151123Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dm20151123 import models as dm_20151123_models
from alibabacloud_tea_util import models as util_models


_DIRECTMAIL_ENDPOINTS = {
    "cn-hangzhou": "dm.aliyuncs.com",
    "ap-southeast-1": "dm.ap-southeast-1.aliyuncs.com",
    "ap-southeast-2": "dm.ap-southeast-2.aliyuncs.com",
    "us-west-1": "dm.ap-southeast-2.aliyuncs.com",
    "eu-central-1": "dm.eu-central-1.aliyuncs.com",
}


def _resolve_directmail_endpoint(region_id: str | None) -> str:
    normalized = (region_id or "cn-hangzhou").strip().lower()
    if normalized not in _DIRECTMAIL_ENDPOINTS:
        raise ValueError(
            "Unsupported Aliyun DirectMail region: "
            f"{region_id}. Supported regions: {', '.join(sorted(_DIRECTMAIL_ENDPOINTS))}"
        )
    return _DIRECTMAIL_ENDPOINTS[normalized]


class AliyunService:
    @staticmethod
    def create_client(
        access_key_id: str,
        access_key_secret: str,
        region_id: str = "cn-hangzhou",
    ) -> Dm20151123Client:
        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            read_timeout=10000,  # 10s
            connect_timeout=10000,  # 10s
            protocol="HTTPS",
        )
        config.endpoint = _resolve_directmail_endpoint(region_id)
        return Dm20151123Client(config)

    @staticmethod
    def query_templates(client: Dm20151123Client, page_no: int = 1, page_size: int = 50):
        request = dm_20151123_models.QueryTemplateByParamRequest(
            page_no=page_no, page_size=page_size
        )
        runtime = util_models.RuntimeOptions()
        return client.query_template_by_param_with_options(request, runtime)

    @staticmethod
    def desc_template(client: Dm20151123Client, template_id: int):
        request = dm_20151123_models.DescTemplateRequest(template_id=template_id)
        runtime = util_models.RuntimeOptions()
        return client.desc_template_with_options(request, runtime)

    @staticmethod
    def query_mail_address(client: Dm20151123Client, page_no: int = 1, page_size: int = 50):
        request = dm_20151123_models.QueryMailAddressByParamRequest(
            page_no=page_no, page_size=page_size
        )
        runtime = util_models.RuntimeOptions()
        return client.query_mail_address_by_param_with_options(request, runtime)

    @staticmethod
    def batch_send_mail(
        client: Dm20151123Client,
        account_name: str,
        receivers_name: str,  # 收件人列表名称
        template_name: str,  # 模板名称
        tag_name: str = None,
    ):
        """
        注意：阿里云的 BatchSendMail 是基于控制台预先配置好的‘收件人列表’和‘模板’。
        如果你需要动态替换标题中的变量，且不想预先在阿里云控制台创建成千上万个模板，
        我们需要通过 API 的方式动态构建请求。
        """
        request = dm_20151123_models.BatchSendMailRequest(
            account_name=account_name,
            receivers_name=receivers_name,
            template_name=template_name,
            address_type=0,
            tag_name=tag_name,
        )
        runtime = util_models.RuntimeOptions()
        return client.batch_send_mail_with_options(request, runtime)

    @staticmethod
    def single_send_mail(
        client: Dm20151123Client,
        account_name: str,
        reply_to_address: bool,
        address_type: int,
        to_address: str,
        subject: str,
        html_body: str,
        from_alias: str = None,
    ):
        request = dm_20151123_models.SingleSendMailRequest(
            account_name=account_name,
            reply_to_address=reply_to_address,
            address_type=address_type,
            to_address=to_address,
            subject=subject,
            html_body=html_body,
            from_alias=from_alias,
        )
        runtime = util_models.RuntimeOptions()
        return client.single_send_mail_with_options(request, runtime)
