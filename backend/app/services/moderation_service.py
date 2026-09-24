"""内容审查服务：检测违法违纪、色情等不当词汇"""
import re

# 敏感词库（可按需扩充）。命中即判定为违规。
SENSITIVE_WORDS = [
    # 违法违纪
    "赌博", "毒品", "吸毒", "贩毒", "洗钱", "诈骗", "传销", "枪支", "弹药",
    "恐怖袭击", "暴恐", "分裂国家", "反政府", "邪教",
    # 色情低俗
    "色情", "裸聊", "约炮", "一夜情", "嫖娼", "卖淫", "黄图", "黄片",
    "毛片", "AV", "做爱", "性行为", "自慰", "春药",
    # 辱骂攻击
    "傻逼", "智障", "废物", "去死", "滚蛋", "王八蛋", "畜生", "sb","草",
    # 其他违规
    "办证", "代开发票", "刷单", "水军", "外挂", "私彩","vx","qq",
]

# 编译为正则，忽略大小写
_PATTERN = re.compile("|".join(re.escape(w) for w in SENSITIVE_WORDS), re.IGNORECASE)


def check_content(text: str) -> dict:
    """
    检查文本内容是否合规
    返回：{"ok": bool, "reason": str}
    """
    if not text or not text.strip():
        return {"ok": False, "reason": "内容不能为空"}

    matches = _PATTERN.findall(text)
    if matches:
        # 去重，最多返回 3 个命中词
        hit = list(dict.fromkeys(matches))[:3]
        return {"ok": False, "reason": f"内容包含违规词汇：{', '.join(hit)}"}

    return {"ok": True, "reason": ""}
