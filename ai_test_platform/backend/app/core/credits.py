"""
控制台计费规则：每个能力对应的积分消耗。
便于 MCP 工具与 API 统一扣费、前端展示套餐与单价。
"""
from typing import Dict

# 单次调用消耗积分（可后续改为从配置/数据库读取）
CREDITS_PER_CALL: Dict[str, int] = {
    "api_test": 1,           # 单接口测试 1 次
    "from_doc_generate": 0, # 仅从文档生成用例不执行：暂不扣费，或按文档大小扣
    "from_doc_execute": 1,  # 从文档生成的每条用例执行：1 积分/条
}
# 后续可加：report_export=10, playwright_run=5 等

def credits_for_api_test() -> int:
    return CREDITS_PER_CALL["api_test"]

def credits_for_from_doc(only_generate: bool, case_count: int) -> int:
    if only_generate:
        return CREDITS_PER_CALL["from_doc_generate"]
    return case_count * CREDITS_PER_CALL["from_doc_execute"]
