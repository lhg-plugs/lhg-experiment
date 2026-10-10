#!/usr/bin/env python3
"""lhg-experiment 硬门②（警告级，不拦截）：写实验报告 md 时，
若命中 p 值表述却没有效应量/置信区间，提醒补上（EXP-RSLT-001 的前置提醒）。

触发：PostToolUse / Write|Edit。只做提醒，永远 exit 0、不拦截写入。

逃生方式：LHG_EXPERIMENT_HOOKS_OFF=1（环境变量）可关闭本提醒；
或 /plugin disable lhg-experiment 停用整个插件。
零第三方依赖。
"""

import json
import os
import re
import sys

PVAL_RE = re.compile(r"p\s*[=<>]\s*0?\.\d+|p\s*值", re.I)
EFFECT_RE = re.compile(r"效应量|Cohen|置信区间|\bCI\b")
REPORT_NAME_RE = re.compile(r"result|report|报告|分析|实验|结论", re.I)


def main() -> int:
    if os.environ.get("LHG_EXPERIMENT_HOOKS_OFF") == "1":
        return 0

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # fail-open

    tool_input = payload.get("tool_input", {}) or {}
    path = tool_input.get("file_path", "") or ""
    if not path.endswith(".md") or not REPORT_NAME_RE.search(os.path.basename(path)):
        return 0  # 非实验报告：快速放行
    if not os.path.isfile(path):
        return 0

    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return 0

    if PVAL_RE.search(text) and not EFFECT_RE.search(text):
        note = (
            "lhg-experiment 提醒：这份实验报告里出现了 p 值，但没看到效应量/置信区间。\n"
            "只报 p 值的解读会被审计脚本判为 blocker（EXP-RSLT-001）。"
            "建议补上：效应量（绝对+相对提升）与 95% 置信区间，再下结论。\n"
            "关闭此提醒：LHG_EXPERIMENT_HOOKS_OFF=1"
        )
        sys.stdout.write(json.dumps({"additionalContext": note}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
