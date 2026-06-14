from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import requests

from .config import FeishuEnvConfig, load_feishu_env
from .models import Notice


BITABLE_TABLE_NAME = "TenderRadarLite"
PRIMARY_FIELD_NAME = "项目名称"
OFFICIAL_PLATFORM_URL = "https://hengyang.hnsggzy.com/"
SCHEMA_FIELDS = [
    "来源网站",
    "来源子类",
    "唯一键",
    "地区",
    "发布时间",
    "原文链接",
    "抓取时间",
    "是否新增",
    "命中关键词",
    "人工判断",
    "标段名称",
    "公告类型",
    "项目编号",
    "招标人或采购单位",
    "代理机构",
    "文件获取截止时间",
    "开标或响应截止时间",
    "预算金额",
    "最高限价",
    "采购或招标方式",
    "项目内容摘要",
    "资质要求摘要",
    "是否接受联合体",
    "是否有附件",
    "附件数量",
    "商机层级",
    "分类理由",
    "正向信号",
    "排除信号",
    "验收标记",
    "官方平台入口",
    "建议搜索关键词",
    "原始接口链接",
]
TEXT_FIELD_TYPE = 1


@dataclass
class BitableTarget:
    app_token: str
    table_id: str
    table_name: str


class FeishuConfigError(RuntimeError):
    pass


class FeishuClient:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.config: FeishuEnvConfig = load_feishu_env()
        self.app_id = self.config.app_id
        self.app_secret = self.config.app_secret
        self.bitable_url = self.config.bitable_url
        self.bitable_app_token = self.config.bitable_app_token
        self.bitable_table_id = self.config.bitable_table_id
        self.webhook_url = self.config.webhook_url
        self.bot_mode = self.config.bot_mode
        self.chat_id = self.config.chat_id

    def get_env_status_lines(self) -> list[str]:
        return [
            f"FEISHU_APP_ID: {'已配置' if self.app_id else '未配置'}",
            f"FEISHU_APP_SECRET: {'已配置' if self.app_secret else '未配置'}",
            f"FEISHU_BITABLE_URL: {'已配置' if self.bitable_url else '未配置'}",
            f"FEISHU_WEBHOOK_URL: {'已配置' if self.webhook_url else '未配置'}",
            f"FEISHU_BITABLE_APP_TOKEN: {'已配置' if self.bitable_app_token else '未配置'} (fallback)",
            f"FEISHU_BITABLE_TABLE_ID: {'已配置' if self.bitable_table_id else '未配置'} (fallback)",
            f"FEISHU_BOT_MODE: {self.bot_mode}",
            f"FEISHU_CHAT_ID: {'已配置' if self.chat_id else '未配置'}",
        ]

    def can_write_bitable(self) -> bool:
        return bool((self.bitable_url or self.bitable_app_token) and self.app_id and self.app_secret)

    def can_send_webhook(self) -> bool:
        return self.bot_mode == "webhook" and bool(self.webhook_url)

    def can_send_app_bot(self) -> bool:
        return self.bot_mode == "app" and bool(self.app_id and self.app_secret and self.chat_id)

    def has_any_output(self) -> bool:
        return self.can_write_bitable() or self.can_send_webhook() or self.can_send_app_bot()

    def _mask(self, value: str, prefix: int = 4, suffix: int = 4) -> str:
        if not value:
            return ""
        if len(value) <= prefix + suffix:
            return "*" * len(value)
        return f"{value[:prefix]}***{value[-suffix:]}"

    def _raise_missing(self, env_name: str, message: str) -> None:
        raise FeishuConfigError(f"{env_name} 未配置：{message}")

    def _require_app_credentials(self) -> None:
        if not self.app_id:
            self._raise_missing("FEISHU_APP_ID", "请先配置自建应用 App ID")
        if not self.app_secret:
            self._raise_missing("FEISHU_APP_SECRET", "请先配置自建应用 App Secret")

    def _require_webhook(self) -> str:
        if not self.webhook_url:
            self._raise_missing("FEISHU_WEBHOOK_URL", "请先配置群机器人 Webhook URL")
        return self.webhook_url

    def _require_bot_mode(self) -> str:
        if self.bot_mode not in {"webhook", "app"}:
            raise FeishuConfigError("FEISHU_BOT_MODE 仅支持 webhook 或 app")
        return self.bot_mode

    def _require_chat_id(self) -> str:
        if not self.chat_id:
            raise FeishuConfigError(
                "FEISHU_CHAT_ID 未配置：app 模式请先执行 python run_mvp.py --list-feishu-chats"
            )
        return self.chat_id

    def parse_bitable_target_from_env(self) -> tuple[str, str | None]:
        if self.bitable_url:
            return self.parse_bitable_url(self.bitable_url)
        if self.bitable_app_token:
            return self.bitable_app_token, self.bitable_table_id or None
        self._raise_missing("FEISHU_BITABLE_URL", "请使用 /base/ 多维表格 URL，或兼容配置 FEISHU_BITABLE_APP_TOKEN")
        return "", None

    def parse_bitable_url(self, bitable_url: str) -> tuple[str, str | None]:
        parsed = urlparse(bitable_url)
        if "/wiki/" in parsed.path:
            raise FeishuConfigError("当前仅支持独立 /base/ 多维表格 URL，请改用 /base/<app_token> 链接")
        segments = [segment for segment in parsed.path.split("/") if segment]
        if "base" not in segments:
            raise FeishuConfigError("无法从 URL 解析 app_token：当前仅支持 /base/<app_token> 类型 URL")
        base_index = segments.index("base")
        if base_index + 1 >= len(segments):
            raise FeishuConfigError("无法从 URL 解析 app_token：/base/ 后缺少 app_token")
        app_token = segments[base_index + 1]
        table_id = parse_qs(parsed.query).get("table", [None])[0]
        return app_token, table_id

    def _api_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict | None = None,
        params: dict[str, str | int] | None = None,
    ) -> dict:
        response = requests.request(method, url, headers=headers, json=json_body, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("code", 0) not in (0, None):
            msg = data.get("msg") or data.get("message") or "unknown error"
            raise RuntimeError(f"Feishu API 错误: code={data.get('code')} msg={msg}")
        return data

    def _get_tenant_access_token(self) -> str:
        self._require_app_credentials()
        data = self._api_request(
            "POST",
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json_body={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        token = data.get("tenant_access_token")
        if not token:
            raise RuntimeError("tenant_access_token 获取失败")
        return token

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _list_tables(self, token: str, app_token: str) -> list[dict]:
        data = self._api_request(
            "GET",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables?page_size=100",
            headers=self._auth_headers(token),
        )
        return data.get("data", {}).get("items", [])

    def _create_table(self, token: str, app_token: str) -> dict:
        data = self._api_request(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables",
            headers=self._auth_headers(token),
            json_body={"table": {"name": BITABLE_TABLE_NAME}},
        )
        return data.get("data", {}).get("table", {})

    def _list_fields(self, token: str, app_token: str, table_id: str) -> list[dict]:
        data = self._api_request(
            "GET",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields?page_size=100",
            headers=self._auth_headers(token),
        )
        return data.get("data", {}).get("items", [])

    def _update_field(self, token: str, app_token: str, table_id: str, field_id: str, field_name: str) -> None:
        self._api_request(
            "PUT",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}",
            headers=self._auth_headers(token),
            json_body={"field_name": field_name},
        )

    def _create_field(self, token: str, app_token: str, table_id: str, field_name: str) -> None:
        self._api_request(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            headers=self._auth_headers(token),
            json_body={"field_name": field_name, "type": TEXT_FIELD_TYPE},
        )

    def _resolve_target_table(self, token: str, app_token: str, preferred_table_id: str | None) -> BitableTarget:
        tables = self._list_tables(token, app_token)
        if preferred_table_id:
            for table in tables:
                table_id = table.get("table_id") or table.get("id")
                if table_id == preferred_table_id:
                    return BitableTarget(app_token=app_token, table_id=table_id, table_name=table.get("name", ""))
        for table in tables:
            if table.get("name") == BITABLE_TABLE_NAME:
                table_id = table.get("table_id") or table.get("id")
                return BitableTarget(app_token=app_token, table_id=table_id, table_name=table.get("name", ""))
        created = self._create_table(token, app_token)
        table_id = created.get("table_id") or created.get("id")
        if not table_id:
            raise RuntimeError("飞书数据表创建成功但未返回 table_id")
        return BitableTarget(app_token=app_token, table_id=table_id, table_name=created.get("name", BITABLE_TABLE_NAME))

    def _resolve_bitable_target(self) -> BitableTarget:
        app_token, preferred_table_id = self.parse_bitable_target_from_env()
        token = self._get_tenant_access_token()
        return self._resolve_target_table(token, app_token, preferred_table_id)

    def init_schema(self) -> dict:
        app_token, preferred_table_id = self.parse_bitable_target_from_env()
        token = self._get_tenant_access_token()
        target = self._resolve_target_table(token, app_token, preferred_table_id)
        fields = self._list_fields(token, target.app_token, target.table_id)
        existing_names = [field.get("field_name", "") for field in fields]
        created_fields: list[str] = []
        renamed_fields: list[str] = []
        failed_fields: list[str] = []
        primary_field = next((field for field in fields if field.get("is_primary")), None) or (fields[0] if fields else None)

        if primary_field:
            current_name = primary_field.get("field_name", "")
            if current_name != PRIMARY_FIELD_NAME and PRIMARY_FIELD_NAME not in existing_names:
                try:
                    self._update_field(token, target.app_token, target.table_id, primary_field["field_id"], PRIMARY_FIELD_NAME)
                    renamed_fields.append(f"{current_name} -> {PRIMARY_FIELD_NAME}")
                    existing_names = [PRIMARY_FIELD_NAME if name == current_name else name for name in existing_names]
                except Exception:
                    failed_fields.append(f"rename:{current_name}")

        for field_name in SCHEMA_FIELDS:
            if field_name in existing_names:
                continue
            try:
                self._create_field(token, target.app_token, target.table_id, field_name)
                created_fields.append(field_name)
            except Exception:
                failed_fields.append(field_name)

        return {
            "app_token_masked": self._mask(target.app_token),
            "table_id": target.table_id,
            "table_name": target.table_name or BITABLE_TABLE_NAME,
            "existing_fields": existing_names,
            "created_fields": created_fields,
            "renamed_fields": renamed_fields,
            "failed_fields": failed_fields,
        }

    def create_test_record(self) -> dict:
        target = self._resolve_bitable_target()
        token = self._get_tenant_access_token()
        payload = {
            "fields": {
                "项目名称": "【测试】TenderRadarLite Feishu output",
                "来源网站": "本地测试",
                "地区": "衡阳",
                "发布时间": "测试",
                "原文链接": OFFICIAL_PLATFORM_URL,
                "抓取时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "是否新增": "测试",
                "命中关键词": "测试",
                "人工判断": "待确认",
                "官方平台入口": OFFICIAL_PLATFORM_URL,
                "建议搜索关键词": "TenderRadarLite Feishu output",
                "原始接口链接": "",
            }
        }
        data = self._api_request(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{target.app_token}/tables/{target.table_id}/records",
            headers=self._auth_headers(token),
            json_body=payload,
        )
        record = data.get("data", {}).get("record", {})
        return {"table_id": target.table_id, "record_id": record.get("record_id") or record.get("recordId") or ""}

    def write_notice(
        self,
        notice: Notice,
        *,
        newness_value: str | None = None,
        manual_judgement: str | None = None,
        pilot_flag: str = "",
    ) -> bool:
        target = self._resolve_bitable_target()
        token = self._get_tenant_access_token()
        payload = {
            "fields": self._build_notice_fields(
                notice,
                newness_value=newness_value,
                manual_judgement=manual_judgement,
                pilot_flag=pilot_flag,
            )
        }
        self._api_request(
            "POST",
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{target.app_token}/tables/{target.table_id}/records",
            headers=self._auth_headers(token),
            json_body=payload,
        )
        return True

    def _build_notice_fields(
        self,
        notice: Notice,
        *,
        newness_value: str | None = None,
        manual_judgement: str | None = None,
        pilot_flag: str = "",
    ) -> dict[str, str]:
        newness = newness_value if newness_value is not None else (notice.newness_label if notice.newness_label else ("是" if notice.is_new else "否"))
        manual_value = manual_judgement if manual_judgement is not None else notice.manual_judgement
        employee_url = notice.employee_readable_url or ""
        raw_url = notice.raw_api_url or notice.original_url or ""
        search_keyword = _build_search_keyword(notice)
        return {
            "项目名称": notice.project_name or notice.title,
            "来源网站": notice.source_site,
            "来源子类": notice.source_subtype,
            "唯一键": notice.dedupe_key,
            "地区": notice.region,
            "发布时间": notice.published_at,
            "原文链接": employee_url or OFFICIAL_PLATFORM_URL,
            "抓取时间": notice.fetched_at,
            "是否新增": newness,
            "命中关键词": "、".join(notice.hit_keywords),
            "人工判断": manual_value,
            "标段名称": notice.section_name,
            "公告类型": notice.notice_type,
            "项目编号": notice.project_code,
            "招标人或采购单位": notice.purchaser_or_tenderer,
            "代理机构": notice.agency,
            "文件获取截止时间": notice.file_get_deadline,
            "开标或响应截止时间": notice.bid_open_or_response_deadline,
            "预算金额": notice.budget_amount,
            "最高限价": notice.ceiling_price,
            "采购或招标方式": notice.procurement_method,
            "项目内容摘要": notice.content_summary,
            "资质要求摘要": notice.qualification_summary,
            "是否接受联合体": notice.accepts_consortium or "未提取到",
            "是否有附件": "是" if notice.has_attachment else "否",
            "附件数量": str(notice.attachment_count),
            "商机层级": notice.lead_tier,
            "分类理由": notice.lead_reason,
            "正向信号": "、".join(notice.matched_positive_signals),
            "排除信号": "、".join(notice.matched_negative_signals),
            "验收标记": pilot_flag,
            "官方平台入口": OFFICIAL_PLATFORM_URL,
            "建议搜索关键词": search_keyword,
            "原始接口链接": raw_url,
        }

    def list_chats(self) -> list[dict[str, str]]:
        token = self._get_tenant_access_token()
        page_token = ""
        chats: list[dict[str, str]] = []
        while True:
            params: dict[str, str | int] = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            data = self._api_request(
                "GET",
                "https://open.feishu.cn/open-apis/im/v1/chats",
                headers=self._auth_headers(token),
                params=params,
            )
            payload = data.get("data", {})
            for item in payload.get("items", []):
                chats.append(
                    {
                        "name": str(item.get("name") or ""),
                        "chat_id": str(item.get("chat_id") or ""),
                        "description": str(item.get("description") or ""),
                    }
                )
            if not payload.get("has_more"):
                break
            page_token = str(payload.get("page_token") or "")
            if not page_token:
                break
        return chats

    def send_app_message(self, text: str) -> bool:
        self._require_app_credentials()
        chat_id = self._require_chat_id()
        token = self._get_tenant_access_token()
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        self._api_request(
            "POST",
            "https://open.feishu.cn/open-apis/im/v1/messages",
            headers=self._auth_headers(token),
            params={"receive_id_type": "chat_id"},
            json_body=payload,
        )
        return True

    def send_bot_message(self, text: str) -> bool:
        mode = self._require_bot_mode()
        if mode == "webhook":
            return self.send_text_message(text)
        return self.send_app_message(text)

    def send_test_webhook(self) -> bool:
        return self.send_text_message("TenderRadarLite test: Feishu webhook is reachable")

    def send_text_message(self, text: str) -> bool:
        webhook = self._require_webhook()
        response = requests.post(webhook, json={"msg_type": "text", "content": {"text": text}}, timeout=20)
        response.raise_for_status()
        return True

    def send_summary(
        self,
        notices: list[Notice],
        *,
        summary_title: str | None = None,
        max_examples: int = 4,
    ) -> bool:
        notices = list(notices)
        if not notices:
            return False

        lines: list[str] = [summary_title or "【TenderRadarLite】", ""]
        for notice in notices[:max_examples]:
            lines.extend(self._build_notice_message_lines(notice))
            lines.append("")
        return self.send_bot_message("\n".join(lines).rstrip())

    def _build_notice_message_lines(self, notice: Notice) -> list[str]:
        employee_url = notice.employee_readable_url or ""
        raw_url = notice.raw_api_url or notice.original_url or ""
        lines = [
            f"商机层级：{notice.lead_tier or '未判定'}",
            f"项目名称：{notice.project_name or notice.title or '未提取到'}",
            f"公告类型：{notice.notice_type or '未提取到'}",
            f"招标人或采购单位：{notice.purchaser_or_tenderer or '未提取到'}",
            f"代理机构：{notice.agency or '未提取到'}",
            f"所属地区：{notice.region or '未提取到'}",
            f"预算金额：{notice.budget_amount or '未提取到'}",
            f"最高限价：{notice.ceiling_price or '未提取到'}",
            f"采购或招标方式：{notice.procurement_method or '未提取到'}",
            f"文件获取截止时间：{notice.file_get_deadline or '未提取到'}",
            f"开标或响应截止时间：{notice.bid_open_or_response_deadline or '未提取到'}",
            f"项目内容摘要：{_compact_line(notice.content_summary)}",
            f"资质要求摘要：{_compact_line(notice.qualification_summary)}",
            f"是否接受联合体：{notice.accepts_consortium or '未提取到'}",
            f"是否有附件：{'是' if notice.has_attachment else '否'}",
            f"附件数量：{notice.attachment_count}",
            f"分类理由：{_compact_line(notice.lead_reason)}",
            f"正向信号：{_compact_line('、'.join(notice.matched_positive_signals))}",
            f"排除信号：{_compact_line('、'.join(notice.matched_negative_signals))}",
        ]
        if notice.lead_tier == "WATCHLIST":
            lines.append("人工建议：当前属于关联观察，不代表可以直接投标，需要经营人员人工确认。")
        elif notice.lead_tier == "DIRECT":
            lines.append("人工建议：直接商机，建议尽快人工复核。")
        else:
            lines.append("人工建议：仅保留本地记录，不建议推送。")

        if employee_url:
            lines.append(f"原文详情页：{employee_url}")
        else:
            lines.append(f"官方平台入口：{OFFICIAL_PLATFORM_URL}")
            lines.append(f"建议搜索关键词：{_build_search_keyword(notice) or '未提取到'}")
        if raw_url:
            lines.append(f"原始接口链接（仅供复核）：{raw_url}")
        return lines


def _build_search_keyword(notice: Notice) -> str:
    return (notice.project_name or notice.title or "").strip()


def _compact_line(value: str, limit: int = 120) -> str:
    text = " ".join((value or "").split())
    if not text:
        return "未提取到"
    return text[:limit] + ("..." if len(text) > limit else "")
