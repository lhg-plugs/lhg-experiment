#!/usr/bin/env python3
"""lhg-experiment 确定性实验审计：20 条规则，零第三方依赖。

扫描目标目录：
  - *plan*.json  —— 实验设计文档（对照/随机/功效测算/分流/时长）
  - *result*/*report*/*报告*/*分析*/*实验*.md —— 结果解读文档（p-hacking 等误读检查）

输出 JSON 与人类可读报告；有 blocker 时以 exit code 2 退出（供 hooks 与 CI 使用）。

用法：
    python3 experiment_audit.py --target <目录> [--format json|text] [--fail-on blocker|warning|nit]

规则文案均为本插件原创（统计公式为教科书标准方法）。
"""

import argparse
import json
import os
import re
import sys

VERSION = "1.0.0"
TOOL = "lhg-experiment/audit"

SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", ".next",
             "vendor", "coverage", ".turbo", "out"}

PVAL_RE = re.compile(r"p\s*[=<>≤≥]\s*0?\.\d+|p\s*值\s*[=<>≤≥]?\s*0?\.\d+", re.I)
EDGE_PVAL_RE = re.compile(r"p\s*=\s*0\.04\d", re.I)
SIG_RE = re.compile(r"显著")
EFFECT_RE = re.compile(r"效应量|Cohen|置信区间|\bCI\b|d\s*=\s*0?\.\d+")
CORRECT_RE = re.compile(r"Bonferroni|Holm|FDR|多重比较|校正")
PEEK_RE = re.compile(r"提前停止|边跑边看|中途.{0,6}显著|第.{1,4}天.{0,10}显著.{0,10}(停止|结束)|每天看.{0,6}数据")
SUBGROUP_RE = re.compile(r"分组分析|分人群|细分.{0,4}看|事后")
PREREG_RE = re.compile(r"预先声明|预先设定|预注册|设计阶段.{0,6}确定")
BIZ_RE = re.compile(r"业务意义|实际意义|ROI|投入产出|决策建议")
REPORT_NAME_RE = re.compile(r"result|report|报告|分析|实验|结论", re.I)


class Finding:
    __slots__ = ("rule_id", "severity", "category", "title", "file", "line", "snippet", "detail")

    def __init__(self, rule_id, severity, category, title, file, line, snippet, detail):
        self.rule_id = rule_id
        self.severity = severity
        self.category = category
        self.title = title
        self.file = file
        self.line = line
        self.snippet = snippet
        self.detail = detail

    def to_dict(self):
        return {
            "rule_id": self.rule_id, "severity": self.severity,
            "category": self.category, "title": self.title,
            "file": self.file, "line": self.line,
            "snippet": self.snippet, "detail": self.detail,
        }


RULES = []
_RULE_BY_ID = {}


def rule(rule_id, severity, category, title, detail):
    def deco(fn):
        r = {"id": rule_id, "severity": severity, "category": category,
             "title": title, "detail": detail}
        _RULE_BY_ID[rule_id] = r
        r["check"] = fn
        RULES.append(r)
        return fn
    return deco


def _mk(rule_id, file, line, snippet):
    r = _RULE_BY_ID[rule_id]
    return Finding(r["id"], r["severity"], r["category"], r["title"],
                   file, line, snippet[:160], r["detail"])


def _plans(target):
    out = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".json") and "plan" in f.lower():
                out.append(os.path.join(root, f))
    return sorted(out)


def _reports(target):
    out = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".md") and REPORT_NAME_RE.search(f):
                out.append(os.path.join(root, f))
    return sorted(out)


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _iter_plans(target):
    """yield (relpath, dict|None, parse_ok)。"""
    for p in _plans(target):
        rel = os.path.relpath(p, target)
        d = _load_json(p)
        yield rel, d, d is not None


def _iter_reports(target):
    for p in _reports(target):
        rel = os.path.relpath(p, target)
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        yield rel, text


# ---------------- 设计文档检查 ----------------

@rule("EXP-DSG-000", "warning", "设计", "设计文档解析失败",
      "plan.json 解析失败。修好 JSON 格式（多半是少逗号或中文引号），否则审计看不到设计。")
def r_dsg_000(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        if not ok:
            out.append(_mk("EXP-DSG-000", rel, 0, "JSON 解析失败"))
    return out


@rule("EXP-DSG-001", "warning", "设计", "缺少实验设计文档",
      "没找到 *plan*.json。实验开始前先把假设/对照/随机/样本量写成 plan.json，"
      "事后补容易选择性报告。")
def r_dsg_001(target, ctx):
    if not _plans(target):
        return [_mk("EXP-DSG-001", ".", 0, "未找到 *plan*.json")]
    return []


@rule("EXP-DSG-002", "blocker", "设计", "无对照组",
      "设计中没有对照组（control 缺失或为 false）。没有对照就无法区分"
      "是干预的效果还是时间趋势/季节性——结论站不住。")
def r_dsg_002(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        if ok and not d.get("control"):
            out.append(_mk("EXP-DSG-002", rel, 0, "control 缺失或为 false"))
    return out


@rule("EXP-DSG-003", "warning", "设计", "未声明随机化方法",
      "没有写随机化/分流方式。非随机分流（按时间/地域切）会引入混杂，"
      "至少写明分流键（如用户 id 哈希）与分流层级。")
def r_dsg_003(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        if ok and not d.get("randomization"):
            out.append(_mk("EXP-DSG-003", rel, 0, "randomization 缺失"))
    return out


@rule("EXP-DSG-004", "warning", "设计", "假设不可证伪或缺失",
      "hypothesis 缺失，或没有可测量的判定标准。好假设的格式："
      "「干预 X 使指标 Y 变化 ≥Z%」——写不出 Z 就先别开实验。")
def r_dsg_004(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        h = (d.get("hypothesis") or "") if ok else ""
        if not h or not re.search(r"\d", h):
            out.append(_mk("EXP-DSG-004", rel, 0, "hypothesis 缺失或无量化标准"))
    return out


@rule("EXP-DSG-005", "warning", "设计", "主要指标未声明",
      "primary_metrics 缺失。开跑前必须锁定 1~2 个主要指标，"
      "否则结果出来后容易挑好看的指标报（p-hacking 的温床）。")
def r_dsg_005(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        if ok and not d.get("primary_metrics"):
            out.append(_mk("EXP-DSG-005", rel, 0, "primary_metrics 缺失"))
    return out


@rule("EXP-DSG-006", "warning", "设计", "实验时长不足一个业务周期",
      "duration_days < 7。短于一个完整周期的实验会被工作日/周末效应污染，"
      "建议至少跑满 1~2 个完整周期。")
def r_dsg_006(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        dur = d.get("duration_days") if ok else None
        if isinstance(dur, (int, float)) and dur < 7:
            out.append(_mk("EXP-DSG-006", rel, 0, "duration_days=%s" % dur))
    return out


# ---------------- 功效测算检查 ----------------

@rule("EXP-PWR-001", "blocker", "功效", "样本量无功效测算依据",
      "required_sample_per_group 或 sample_size_basis 缺失。样本量拍脑袋的实验，"
      "要么浪费流量、要么根本检不出效应——先用 power_calc.py 算。")
def r_pwr_001(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        if ok and not (d.get("required_sample_per_group") and d.get("sample_size_basis")):
            out.append(_mk("EXP-PWR-001", rel, 0, "缺少功效测算依据"))
    return out


@rule("EXP-PWR-002", "blocker", "功效", "实际样本量不足",
      "actual_sample_per_group < required_sample_per_group。样本不够的实验"
      "即使 p<0.05 也可能是噪音；补足样本或承认结论不可靠。")
def r_pwr_002(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        if not ok:
            continue
        req, act = d.get("required_sample_per_group"), d.get("actual_sample_per_group")
        if isinstance(req, (int, float)) and isinstance(act, (int, float)) and act < req:
            out.append(_mk("EXP-PWR-002", rel, 0,
                           "实际 %s < 需求 %s" % (act, req)))
    return out


@rule("EXP-PWR-003", "warning", "功效", "效应量无依据",
      "effect_basis 缺失。效应量不能凭感觉：从历史数据、最小业务价值"
      "（小到多少就不值得做）或文献中取三者最保守的那个。")
def r_pwr_003(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        if ok and not d.get("effect_basis"):
            out.append(_mk("EXP-PWR-003", rel, 0, "effect_basis 缺失"))
    return out


@rule("EXP-PWR-004", "warning", "功效", "显著性水平/功效目标未声明",
      "alpha 或 power_target 缺失。默认值 α=0.05、功效 80% 也要写出来，"
      "写出来才算数。")
def r_pwr_004(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        if ok and (d.get("alpha") is None or d.get("power_target") is None):
            out.append(_mk("EXP-PWR-004", rel, 0, "alpha/power_target 缺失"))
    return out


@rule("EXP-PWR-005", "warning", "功效", "功效目标低于 80%",
      "power_target < 0.8。功效低于 80% 意味着超过两成概率漏掉真实效应，"
      "除非流量实在不够，否则把目标定到 80% 以上。")
def r_pwr_005(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        pt = d.get("power_target") if ok else None
        if isinstance(pt, (int, float)) and pt < 0.8:
            out.append(_mk("EXP-PWR-005", rel, 0, "power_target=%s" % pt))
    return out


# ---------------- A/B 专项检查 ----------------

@rule("EXP-AB-001", "warning", "分流", "未声明 SRM 检查",
      "srm_check 缺失或为 false。分流 bug（样本比例不匹配）会让整个实验作废，"
      "开跑 24 小时内必须做一次 SRM 检查。")
def r_ab_001(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        if ok and not d.get("srm_check"):
            out.append(_mk("EXP-AB-001", rel, 0, "srm_check 缺失或为 false"))
    return out


@rule("EXP-AB-002", "warning", "分流", "分流比例不均且无说明",
      "allocation_ratio 不是 1:1 且没有 allocation_note。非均分流会放大方差，"
      "有理由（如风险控制）就写下来。")
def r_ab_002(target, ctx):
    out = []
    for rel, d, ok in _iter_plans(target):
        if not ok:
            continue
        ratio = d.get("allocation_ratio")
        if isinstance(ratio, list) and len(ratio) == 2 and ratio[0] != ratio[1] \
                and not d.get("allocation_note"):
            out.append(_mk("EXP-AB-002", rel, 0, "allocation_ratio=%s 无说明" % ratio))
    return out


# ---------------- 结果解读检查 ----------------

def _p_hits(text):
    return list(PVAL_RE.finditer(text))


@rule("EXP-RSLT-001", "blocker", "解读", "只报 p 值不报效应量",
      "报告里有 p 值却没有效应量/置信区间。p 值只回答「是不是噪音」，"
      "效应量才回答「值不值得做」——两个都要报。")
def r_rslt_001(target, ctx):
    out = []
    for rel, text in _iter_reports(target):
        if _p_hits(text) and not EFFECT_RE.search(text):
            m = _p_hits(text)[0]
            out.append(_mk("EXP-RSLT-001", rel, text[:m.start()].count("\n") + 1,
                           text[m.start():m.end() + 40].strip()))
    return out


@rule("EXP-RSLT-002", "blocker", "解读", "多重比较未校正",
      "报告多次宣称「显著」却未提任何多重比较校正（Bonferroni/Holm/FDR）。"
      "看的指标越多，假阳性越多——必须校正或预先声明只看主要指标。")
def r_rslt_002(target, ctx):
    out = []
    for rel, text in _iter_reports(target):
        if len(SIG_RE.findall(text)) >= 2 and not CORRECT_RE.search(text):
            out.append(_mk("EXP-RSLT-002", rel, 0,
                           "显著出现 %d 次，无校正声明" % len(SIG_RE.findall(text))))
    return out


@rule("EXP-RSLT-003", "blocker", "解读", "偷看数据/提前停止嫌疑",
      "报告出现「提前停止」「边跑边看」等表述。实验中途反复看 p 值、"
      "显著了就停，会把假阳性率抬到远超 5%——必须按预定样本量/时长跑完。")
def r_rslt_003(target, ctx):
    out = []
    for rel, text in _iter_reports(target):
        m = PEEK_RE.search(text)
        if m:
            out.append(_mk("EXP-RSLT-003", rel, text[:m.start()].count("\n") + 1,
                           text[max(0, m.start() - 20):m.end() + 20].strip()))
    return out


@rule("EXP-RSLT-004", "warning", "解读", "事后分组挖掘嫌疑",
      "报告做了分组/细分分析却没有「预先声明」。事后从数据里找显著分组"
      "基本等于 p-hacking；确有价值的发现请标注为「探索性」，另起实验验证。")
def r_rslt_004(target, ctx):
    out = []
    for rel, text in _iter_reports(target):
        m = SUBGROUP_RE.search(text)
        if m and not PREREG_RE.search(text):
            out.append(_mk("EXP-RSLT-004", rel, text[:m.start()].count("\n") + 1,
                           text[max(0, m.start() - 20):m.end() + 20].strip()))
    return out


@rule("EXP-RSLT-005", "warning", "解读", "边缘显著（p 在 0.04~0.05）",
      "p 值落在 0.04~0.05 之间。这个区间的「显著」最不可靠：换个随机种子"
      "就可能翻转——请看效应量与置信区间下限再做决策。")
def r_rslt_005(target, ctx):
    out = []
    for rel, text in _iter_reports(target):
        for m in EDGE_PVAL_RE.finditer(text):
            out.append(_mk("EXP-RSLT-005", rel, text[:m.start()].count("\n") + 1,
                           text[m.start():m.end() + 30].strip()))
    return out


@rule("EXP-RSLT-006", "warning", "解读", "只谈显著不谈业务意义",
      "报告宣称显著却没讨论业务意义/实际价值。统计显著 ≠ 值得做："
      "提升 0.1% 的点击率可能连开发成本都覆盖不了。")
def r_rslt_006(target, ctx):
    out = []
    for rel, text in _iter_reports(target):
        if SIG_RE.search(text) and not BIZ_RE.search(text):
            out.append(_mk("EXP-RSLT-006", rel, 0, "有显著结论，无业务意义讨论"))
    return out


# ---------------------------------------------------------------- 运行器

def run(target):
    findings = []
    for r in RULES:
        try:
            for f in r["check"](target, {}) or []:
                findings.append(f)
        except Exception:
            continue  # 单条规则异常不影响整体
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description="lhg-experiment 确定性实验审计")
    ap.add_argument("--target", default=".", help="扫描目录")
    ap.add_argument("--format", choices=["json", "text"], default="text")
    ap.add_argument("--fail-on", choices=["blocker", "warning", "nit"], default="blocker")
    args = ap.parse_args(argv)

    target = os.path.abspath(args.target)
    if not os.path.isdir(target):
        print("target 不是目录：%s" % args.target, file=sys.stderr)
        return 1

    findings = run(target)
    sev_rank = {"blocker": 3, "warning": 2, "nit": 1}
    counts = {"blocker": 0, "warning": 0, "nit": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    files = _plans(target) + _reports(target)
    result = {
        "tool": TOOL,
        "version": VERSION,
        "target": args.target,
        "summary": {
            "files_scanned": len(files),
            "rules_run": len(RULES),
            "blocker": counts["blocker"],
            "warning": counts["warning"],
            "nit": counts["nit"],
        },
        "findings": [f.to_dict() for f in sorted(
            findings, key=lambda x: (-sev_rank.get(x.severity, 0), x.file, x.line))],
    }

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        s = result["summary"]
        print("实验审计：扫描 %d 文件，运行 %d 条规则" % (s["files_scanned"], s["rules_run"]))
        print("blocker=%d warning=%d nit=%d" % (s["blocker"], s["warning"], s["nit"]))
        for f in result["findings"]:
            print("[%s][%s] %s:%d %s" % (
                f["severity"].upper(), f["rule_id"], f["file"], f["line"], f["title"]))
            print("    %s" % f["detail"])
            if f["snippet"]:
                print("    → %s" % f["snippet"])

    level = sev_rank[args.fail_on]
    bad = any(sev_rank.get(f.severity, 0) >= level for f in findings)
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
