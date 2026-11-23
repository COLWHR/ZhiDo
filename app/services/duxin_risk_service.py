from __future__ import annotations

from typing import List, Tuple

from app.schemas.duxin import DuxinRiskAssessment


L3_PATTERNS: Tuple[Tuple[str, ...], ...] = (
    ("想死", "不想活", "结束生命", "自杀", "轻生"),
    ("kill myself", "end my life", "suicide", "want to die"),
    ("割腕", "上吊", "跳楼", "服药过量", "过量服药", "吃药自杀"),
    ("伤害别人", "杀人", "报复社会", "我会杀", "hurt someone", "kill them"),
)

# L2 不再用"刀/药"这类孤立名词命中：日常场景（切菜、吃药）会大量误报。
# 只有当"准备/手段/计划"与"风险语境"同时出现时才升级。
L2_PREPARE = ("已经准备好了", "准备好了", "今晚就", "马上就", "已经买了", "刚买了", "写好了遗书")
L2_MEANS = ("安眠药", "刀片", "农药", "汽油", "绳子", "天台", "遗书", "过量服药")
L2_PLAN = ("计划", "具体做法", "步骤", "地点", "时间")
L2_ENGLISH = ("can't go on", "cannot go on", "no way out", "i am done")

RISK_CONTEXT = ("死", "不想活", "结束", "解脱", "自杀", "伤害自己", "离开这个世界", "消失")

L1_PATTERNS: Tuple[Tuple[str, ...], ...] = (
    ("崩溃", "难受", "焦虑", "失眠", "失恋", "孤独", "委屈", "自责"),
    ("撑不住", "压力好大", "很痛苦", "想哭", "心慌", "害怕", "迷茫"),
    ("活着没意思", "活着没意义", "没有意义", "看不到希望", "绝望", "撑不下去", "好累", "活着好累"),
    ("burned out", "anxious", "overwhelmed", "lonely", "panic", "hopeless"),
)


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _collect_signals(text: str, patterns: Tuple[Tuple[str, ...], ...]) -> List[str]:
    normalized = _normalize_text(text)
    signals: List[str] = []
    for group in patterns:
        hits = [item for item in group if item and item.lower() in normalized]
        if hits:
            signals.append(hits[0])
    return signals


def _has_any(normalized: str, words: Tuple[str, ...]) -> bool:
    return any(word.lower() in normalized for word in words)


def assess_risk(text: str) -> DuxinRiskAssessment:
    normalized = _normalize_text(text)

    signals = _collect_signals(normalized, L3_PATTERNS)
    if signals:
        return DuxinRiskAssessment(
            risk_level="L3",
            signals=signals,
            response_mode="crisis",
            should_escalate=True,
            summary="检测到明确的自伤、自杀或伤害他人高风险信号。",
            recommended_actions=[
                "立刻停止普通陪伴流程",
                "鼓励联系当地急救或危机热线",
                "建议联系现实中可信任的人陪同",
                "避免提供任何危险细节",
            ],
        )

    risk_context = _has_any(normalized, RISK_CONTEXT)
    l2_signals: List[str] = []
    if risk_context:
        for group in (L2_PREPARE, L2_MEANS, L2_PLAN):
            hits = [item for item in group if item in normalized]
            if hits:
                l2_signals.append(hits[0])
    english_hits = [item for item in L2_ENGLISH if item in normalized]
    l2_signals.extend(english_hits)

    if l2_signals:
        return DuxinRiskAssessment(
            risk_level="L2",
            signals=l2_signals,
            response_mode="stabilize",
            should_escalate=True,
            summary="检测到潜在危机或已经出现准备行为。",
            recommended_actions=[
                "先稳定情绪，再继续对话",
                "鼓励联系现实世界的支持",
                "避免讨论危险细节",
                "给出下一步安全动作",
            ],
        )

    signals = _collect_signals(normalized, L1_PATTERNS)
    if signals:
        return DuxinRiskAssessment(
            risk_level="L1",
            signals=signals,
            response_mode="support",
            should_escalate=False,
            summary="检测到明显的情绪压力或低落信号。",
            recommended_actions=[
                "先接住情绪",
                "帮助用户澄清最主要的困扰",
                "提供一个可执行的小步骤",
            ],
        )

    return DuxinRiskAssessment(
        risk_level="L0",
        signals=[],
        response_mode="support",
        should_escalate=False,
        summary="未检测到明显风险信号。",
        recommended_actions=[
            "保持温柔、稳定、有限边界的支持",
            "协助用户整理感受和下一步行动",
        ],
    )


def build_crisis_reply(risk: DuxinRiskAssessment, latest_user_message: str = "") -> str:
    """User-facing crisis message.

    Deliberately does NOT echo the user's own high-risk wording and does NOT
    expose the internal handling checklist；it only offers concrete, safe next
    steps plus both mainland-China and overseas hotlines.
    """
    return (
        "我很在意你现在的安全，谢谢你愿意说出来。\n\n"
        "先不讲细节，我们一起把眼前这一步稳住，可以做这 3 件事：\n"
        "1. 把可能伤害自己的东西先放远，或交给身边人保管。\n"
        "2. 现在就联系一个你信得过的、可信任的人，请对方来陪你，不要一个人待着。\n"
        "3. 拨打心理援助热线：中国大陆可拨 400-161-9995（全国 24 小时心理援助热线）"
        "或 010-82951332（北京心理危机研究与干预中心）；紧急情况请直接拨 120 / 110。"
        "香港可拨 2389 2222；美国、加拿大可拨打或短信 988。\n\n"
        "如果你愿意，回我一个“在”，我就继续陪你把下一步走完。你不需要一个人扛。"
    )


def build_support_reply_hint(mode: str, summary: str) -> str:
    mode_label = {
        "support": "情绪接住",
        "relationship": "关系复盘",
        "growth": "成长拆解",
        "crisis": "安全守门",
    }.get(mode, "情绪接住")

    playbook = {
        "support": "先接住情绪，再复述需求，最后给一个今天就能做的小动作。",
        "relationship": "先镜像双方感受，再指出互动循环和边界，最后给一句能直接说出口的话。",
        "growth": "先确认目标，再拆成下一步行动，最后把任务缩成一个今天能完成的动作。",
        "crisis": "先稳定安全，不追问细节，只给现实可执行的支持与求助路径。",
    }.get(mode, "先接住情绪，再复述需求，最后给一个今天就能做的小动作。")

    return f"当前模式：{mode_label}。{playbook} 参考摘要：{summary}"
