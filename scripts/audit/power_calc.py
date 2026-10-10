#!/usr/bin/env python3
"""lhg-experiment 功效测算脚本：纯 Python 标准库，零第三方依赖。

支持两类最常用的实验场景：
  t2s    —— 两组均值比较（两样本 t 检验），输入 Cohen's d
  prop2s —— 两组比例比较（转化率/点击率等），输入基准比例 p1 与期望比例 p2

三种用法：
  1. 算样本量：--test t2s --d 0.2            → 每组需要多少样本
  2. 算功效：  --test t2s --d 0.2 --n 400    → 给定样本量，功效是多少
  3. 算 MDE：  --test prop2s --p1 0.05 --n 8000 → 给定样本量，能检出的最小差异

公式均为教科书标准（正态近似；n>30/组时与精确 t 分布差异可忽略）。
实现与文案均为本插件原创。

用法：
    python3 power_calc.py --test t2s --d 0.2 [--alpha 0.05] [--power 0.8] [--sided 2]
    python3 power_calc.py --test prop2s --p1 0.05 --p2 0.06 [--format json]
"""

import argparse
import json
import math
import sys
from statistics import NormalDist

VERSION = "1.0.0"
_N = NormalDist()


def z_alpha(alpha: float, sided: int) -> float:
    if sided == 2:
        return _N.inv_cdf(1 - alpha / 2)
    return _N.inv_cdf(1 - alpha)


def z_beta(power: float) -> float:
    return _N.inv_cdf(power)


def _ceil_int(x: float) -> int:
    return int(math.ceil(x - 1e-12))


# ---------------- 样本量 ----------------

def n_t2s(d: float, alpha: float, power: float, sided: int = 2) -> int:
    """两样本 t 检验：每组所需样本量（正态近似）。"""
    if d <= 0:
        raise ValueError("效应量 d 必须 > 0")
    za, zb = z_alpha(alpha, sided), z_beta(power)
    return _ceil_int(2 * ((za + zb) / d) ** 2)


def n_prop2s(p1: float, p2: float, alpha: float, power: float, sided: int = 2) -> int:
    """两组比例检验：每组所需样本量（正态近似）。"""
    if not (0 < p1 < 1 and 0 < p2 < 1) or p1 == p2:
        raise ValueError("p1、p2 必须在 (0,1) 且不相等")
    za, zb = z_alpha(alpha, sided), z_beta(power)
    pbar = (p1 + p2) / 2
    num = (za * math.sqrt(2 * pbar * (1 - pbar))
           + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return _ceil_int(num / (p1 - p2) ** 2)


# ---------------- 功效 ----------------

def power_t2s(d: float, n: int, alpha: float, sided: int = 2) -> float:
    za = z_alpha(alpha, sided)
    return _N.cdf(d * math.sqrt(n / 2) - za)


def power_prop2s(p1: float, p2: float, n: int, alpha: float, sided: int = 2) -> float:
    za = z_alpha(alpha, sided)
    pbar = (p1 + p2) / 2
    se0 = math.sqrt(2 * pbar * (1 - pbar))
    se1 = math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return _N.cdf((abs(p2 - p1) * math.sqrt(n) - za * se0) / se1)


# ---------------- MDE（最小可检出效应） ----------------

def mde_t2s(n: int, alpha: float, power: float, sided: int = 2) -> float:
    za, zb = z_alpha(alpha, sided), z_beta(power)
    return (za + zb) * math.sqrt(2 / n)


def mde_prop2s(p1: float, n: int, alpha: float, power: float, sided: int = 2,
               direction: int = 1) -> float:
    """在基准 p1 下，给定 n 能检出的最小 p2（direction=1 找提升，-1 找下降）。"""
    lo, hi = (p1, 1 - 1e-9) if direction > 0 else (1e-9, p1)
    for _ in range(80):
        mid = (lo + hi) / 2
        if power_prop2s(p1, mid, n, alpha, sided) < power:
            lo = mid
        else:
            hi = mid
    return hi


def interpret_n(n: int, alpha: float, power: float) -> str:
    return ("每组 %d 个样本（显著性水平 α=%.2f、目标功效 %.0f%%）。"
            "实际执行时按分流比例与预计流失再上浮 10%%~20%%。" % (n, alpha, power * 100))


def main(argv=None):
    ap = argparse.ArgumentParser(description="lhg-experiment 功效测算（纯标准库）")
    ap.add_argument("--test", choices=["t2s", "prop2s"], required=True,
                    help="t2s=两组均值比较；prop2s=两组比例比较")
    ap.add_argument("--d", type=float, default=None, help="Cohen's d（t2s 用）")
    ap.add_argument("--p1", type=float, default=None, help="基准组比例（prop2s 用）")
    ap.add_argument("--p2", type=float, default=None, help="实验组期望比例（prop2s 用）")
    ap.add_argument("--n", type=int, default=None, help="每组样本量：给了就改算功效/MDE")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--power", type=float, default=0.8)
    ap.add_argument("--sided", type=int, choices=[1, 2], default=2)
    ap.add_argument("--format", choices=["json", "text"], default="text")
    args = ap.parse_args(argv)

    if not (0 < args.alpha < 1) or not (0 < args.power < 1):
        print("alpha 与 power 必须在 (0,1) 之间", file=sys.stderr)
        return 1

    result = {"test": args.test, "alpha": args.alpha, "power": args.power,
              "sided": args.sided, "version": VERSION}
    try:
        if args.test == "t2s":
            if args.d is None:
                print("t2s 需要 --d（Cohen's d）", file=sys.stderr)
                return 1
            result["d"] = args.d
            if args.n is None:
                n = n_t2s(args.d, args.alpha, args.power, args.sided)
                result.update({"mode": "sample_size", "n_per_group": n,
                               "advice": interpret_n(n, args.alpha, args.power)})
            else:
                result.update({"mode": "power", "n_per_group": args.n,
                               "achieved_power": round(power_t2s(args.d, args.n, args.alpha, args.sided), 4)})
        else:
            if args.p1 is None:
                print("prop2s 需要 --p1（基准组比例）", file=sys.stderr)
                return 1
            result["p1"] = args.p1
            if args.n is None:
                if args.p2 is None:
                    print("算样本量需要 --p2（实验组期望比例）", file=sys.stderr)
                    return 1
                result["p2"] = args.p2
                n = n_prop2s(args.p1, args.p2, args.alpha, args.power, args.sided)
                result.update({"mode": "sample_size", "n_per_group": n,
                               "absolute_lift": round(args.p2 - args.p1, 6),
                               "relative_lift": round(args.p2 / args.p1 - 1, 4),
                               "advice": interpret_n(n, args.alpha, args.power)})
            elif args.p2 is not None:
                result.update({"mode": "power", "p2": args.p2, "n_per_group": args.n,
                               "achieved_power": round(power_prop2s(args.p1, args.p2, args.n, args.alpha, args.sided), 4)})
            else:
                p2 = mde_prop2s(args.p1, args.n, args.alpha, args.power, args.sided)
                result.update({"mode": "mde", "n_per_group": args.n,
                               "mde_p2": round(p2, 6),
                               "mde_absolute": round(p2 - args.p1, 6),
                               "mde_relative": round(p2 / args.p1 - 1, 4)})
    except ValueError as e:
        print("参数错误：%s" % e, file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("lhg-experiment 功效测算 v%s" % VERSION)
        print("检验：%s（%s 侧）  α=%.3g  目标功效=%.0f%%"
              % ({"t2s": "两组均值比较", "prop2s": "两组比例比较"}[args.test],
                 "双" if args.sided == 2 else "单", args.alpha, args.power * 100))
        m = result["mode"]
        if m == "sample_size":
            print("→ 每组需要样本量：%d" % result["n_per_group"])
            if "relative_lift" in result:
                print("   绝对提升 %.4f，相对提升 %.1f%%"
                      % (result["absolute_lift"], result["relative_lift"] * 100))
            print("   " + result["advice"])
        elif m == "power":
            print("→ 每组 %d 样本时，实际功效：%.1f%%"
                  % (result["n_per_group"], result["achieved_power"] * 100))
        else:
            print("→ 每组 %d 样本时，最小可检出：p2=%.4f（绝对提升 %.4f，相对提升 %.1f%%）"
                  % (result["n_per_group"], result["mde_p2"],
                     result["mde_absolute"], result["mde_relative"] * 100))
        print("注：正态近似公式，每组 n>30 时足够准；小样本请用精确方法复核。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
