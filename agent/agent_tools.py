from datetime import datetime
from contextlib import contextmanager
from contextvars import ContextVar
import csv
import json
import os
import re
import uuid

import requests
from langchain_core.tools import tool

from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path
from agent.interview_role_manager import InterviewRoleManager


_rag_service = None
_tool_context: ContextVar[dict] = ContextVar("agent_tool_context", default={})


@contextmanager
def tool_tenant_context(context: dict | None):
    """Bind trusted request context for tools without exposing it to the model."""
    token = _tool_context.set(dict(context or {}))
    try:
        yield
    finally:
        _tool_context.reset(token)


def _get_rag_service():
    global _rag_service
    if _rag_service is None:
        from rag.rag_service import RagSummarizeService

        _rag_service = RagSummarizeService()
    return _rag_service


def _get_weather_api_key() -> str:
    return os.getenv("WEATHER_API_KEY", agent_conf.get("weather_api_key", "")).strip()


def _request_json(base_url: str, params: dict) -> dict:
    response = requests.get(base_url, params=params, timeout=8)
    response.raise_for_status()
    return response.json()


def _clean_location_value(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text in ["", "[]", "[ ]", "null", "None"]:
        return ""
    return text


def _resolve_city_from_ip() -> str:
    ip_api = agent_conf.get("weather_ip_api", "http://ip-api.com/json/")
    try:
        data = _request_json(ip_api, {"lang": "zh-CN"})
        if str(data.get("status", "")).lower() != "success":
            return ""

        city = _clean_location_value(data.get("city"))
        if city:
            return city

        province = _clean_location_value(data.get("regionName"))
        if province:
            return province
        return ""
    except Exception:
        return ""


@tool
def rag_summarize(query: str):
    """从向量存储中检索参考资料。"""
    return _get_rag_service().rag_summarize(query)


@tool("knowledge_search")
def knowledge_search(query: str):
    """检索本地知识库并返回带来源编号的相关证据。"""
    context = _tool_context.get()
    result = _get_rag_service().search_with_citations(
        query,
        filters={"user_id": context.get("user_id"), "organization_id": context.get("organization_id")},
    )
    citations = result["citations"]
    if not citations:
        return "知识库中没有找到足够相关的资料。"
    return json.dumps({"query": query, "citations": citations}, ensure_ascii=False)


@tool
def get_weather(city: str):
    """查询指定城市的天气，以字符串形式返回。"""
    weather_api_key = _get_weather_api_key()
    if not weather_api_key:
        return "天气服务未配置：请先在环境变量 WEATHER_API_KEY 或 config/agent.yml 的 weather_api_key 中填写 Key。"

    target_city = _clean_location_value(city)
    if not target_city:
        target_city = _clean_location_value(get_city.invoke({}))
    if not target_city or target_city in ["未知城市", "未设置城市"]:
        return "无法获取城市信息，暂时无法查询天气。"

    weather_api = agent_conf.get("weather_api_url", "https://api.weatherapi.com/v1/current.json")
    try:
        data = _request_json(
            weather_api,
            {"key": weather_api_key, "q": target_city, "lang": "zh"},
        )

        current = data.get("current") or {}
        location = data.get("location") or {}
        if not current:
            return f"{target_city}暂无可用天气数据。"

        actual_city = _clean_location_value(location.get("name")) or target_city
        condition = current.get("condition") or {}
        weather_text = str(condition.get("text", "")).strip()
        temperature = str(current.get("temp_c", "")).strip()
        feels_like = str(current.get("feelslike_c", "")).strip()
        wind_kph = str(current.get("wind_kph", "")).strip()
        wind_dir = str(current.get("wind_dir", "")).strip()
        humidity = str(current.get("humidity", "")).strip()
        report_time = str(location.get("localtime", "")).strip()
        return (
            f"{actual_city}当前天气：{weather_text}，气温{temperature}°C，体感{feels_like}°C，"
            f"风向{wind_dir}，风速{wind_kph}km/h，湿度{humidity}%，更新时间{report_time}。"
        )
    except requests.HTTPError as exc:
        try:
            error_payload = exc.response.json()
            error_message = error_payload.get("error", {}).get("message", "")
        except Exception:
            error_message = str(exc)
        return f"{target_city}天气查询失败：{error_message or '请求天气接口失败'}"
    except Exception:
        return f"{target_city}天气查询失败，请稍后重试。"


@tool("weather_search")
def weather_search(city: str):
    """查询指定城市的实时天气；只有天气相关问题才使用此工具。"""
    return get_weather.invoke({"city": city})


@tool("resume_lookup")
def resume_lookup(resume_text: str, keyword: str = ""):
    """从当前简历文本中提取与关键词相关的项目或技能片段。"""
    # Prefer the server-side resume from the authenticated conversation. The
    # model-provided argument remains only for compatibility with the tool schema.
    content = str(_tool_context.get().get("resume_text") or resume_text or "").strip()
    if not content:
        return "当前会话没有上传简历。"
    if not keyword.strip():
        return content[:1200]
    fragments = [item.strip() for item in re.split(r"[。！？\n]", content) if keyword.lower() in item.lower()]
    return "\n".join(fragments[:8]) or f"简历中没有找到与“{keyword}”直接匹配的内容。"


@tool("question_search")
def question_search(role: str, question_index: int = 0):
    """按岗位和题目序号查询建议考察维度，帮助规划面试问题。"""
    manager = InterviewRoleManager()
    index = max(0, int(question_index))
    return json.dumps(
        {
            "role": role,
            "dimension": manager.get_dimension_name(role, index),
            "focus": manager.get_dimension_focus(role, index),
        },
        ensure_ascii=False,
    )


@tool("save_report")
def save_report(title: str, content: str):
    """把已经生成的报告保存为 Markdown 文件并返回文件名。"""
    safe_title = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", title or "agent_report").strip("_")
    filename = f"{safe_title or 'agent_report'}_{uuid.uuid4().hex[:8]}.md"
    report_dir = get_abs_path("data/tool_reports")
    os.makedirs(report_dir, exist_ok=True)
    file_path = os.path.join(report_dir, filename)
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(str(content or ""))
    return filename


@tool
def get_city():
    """获取用户所在城市名称。"""
    cached_city = os.getenv("CURRENT_USER_CITY", "").strip()
    if cached_city:
        return cached_city

    city = _resolve_city_from_ip()
    if city:
        os.environ["CURRENT_USER_CITY"] = city
        return city
    return "洛阳市"


@tool
def get_id():
    """获取当前用户 ID。"""
    return os.getenv("CURRENT_USER_ID", "guest")


@tool
def get_current_month():
    """获取当前月份。"""
    return datetime.now().strftime("%Y-%m")


@tool
def fetch_external_data(user_id: str, month: str):
    """获取指定用户在指定月份的外部记录。"""
    csv_path = get_abs_path(agent_conf.get("external_data_path", "data/external/records.csv"))
    if not os.path.exists(csv_path):
        return ""

    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("user_id", "")).strip() == str(user_id).strip() and str(row.get("month", "")).strip() == str(month).strip():
                records.append(row)

    if not records:
        return ""
    return str(records)
