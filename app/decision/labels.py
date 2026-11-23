"""Intent labels and the rule-based baseline for the decision router.

The router classifies a user request into one of a closed label set. The
machine-learned classifier is plugged on top of this rule baseline: when the
model is unavailable or low-confidence, the rules act as the fallback layer.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Closed label space for the intent router.
LABEL_CHAT = "chat"          # general Q&A / conversation
LABEL_DOC = "doc"            # produce a document / report / summary
LABEL_SHEET = "sheet"        # produce a table / list / comparison
LABEL_IMAGE = "image"        # produce an illustration / diagram
LABEL_VISION = "vision"      # understand an uploaded image
LABEL_RISK = "risk"          # sensitive / unsafe request

ALL_LABELS: List[str] = [
    LABEL_CHAT,
    LABEL_DOC,
    LABEL_SHEET,
    LABEL_IMAGE,
    LABEL_VISION,
    LABEL_RISK,
]

# Keyword patterns per label. Order matters: more specific labels are
# matched before the generic chat fallback.
_KEYWORD_PATTERNS: Dict[str, List[str]] = {
    LABEL_RISK: [
        r"自杀", r"自残", r"赌博", r"色情", r"毒品", r"黑客攻击", r"入侵系统",
        r"泄露密码", r"骂人", r"诈骗", r"暴力",
    ],
    LABEL_VISION: [
        r"读图", r"识别图片", r"看这张图", r"分析图片", r"图片里", r"这张图",
        r"识别一下图", r"图中", r"描述这张图片",
    ],
    LABEL_IMAGE: [
        r"示意图", r"配图", r"插画", r"画一张", r"流程图", r"思维导图", r"结构图",
        r"海报图", r"画个图", r"生成图片", r"配张图", r"画一幅",
    ],
    LABEL_SHEET: [
        r"表格", r"清单", r"对比表", r"统计表", r"数据汇总", r"排班表", r"列表",
        r"对照表", r"排个表",
    ],
    LABEL_DOC: [
        r"文档", r"报告", r"方案", r"总结", r"论文", r"讲稿", r"手册", r"说明书",
        r"纪要", r"演示文稿", r"PPT", r"写一份", r"整理成稿",
    ],
}

# Map a label to the artifact / action the reply should carry.
LABEL_ARTIFACT: Dict[str, Optional[Dict[str, Any]]] = {
    LABEL_CHAT: None,
    LABEL_DOC: {"artifact_type": "docx", "kind": "file"},
    LABEL_SHEET: {"artifact_type": "csv", "kind": "file"},
    LABEL_IMAGE: {"artifact_type": "png", "kind": "image"},
    LABEL_VISION: None,
    LABEL_RISK: None,
}

_COMPILED = {
    label: [re.compile(p, re.IGNORECASE) for p in patterns]
    for label, patterns in _KEYWORD_PATTERNS.items()
}


def rule_classify(text: str) -> Dict[str, Any]:
    """Deterministic keyword baseline. Returns label + matched keyword.

    This is the fallback layer in the three-tier decision chain:
    model -> rules -> (large model arbitration upstream).
    """
    content = str(text or "")
    for label, patterns in _COMPILED.items():
        for pattern in patterns:
            match = pattern.search(content)
            if match:
                return {"label": label, "confidence": 1.0, "keyword": match.group(0)}
    return {"label": LABEL_CHAT, "confidence": 0.5, "keyword": None}
