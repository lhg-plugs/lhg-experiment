---
description: 功效测算专项：算样本量 / 算功效 / 算最小可检出效应，纯 Python 脚本零依赖。
argument-hint: [t2s|prop2s] [--d 效应量 | --p1 基准比例 --p2 期望比例] [--n 样本量]
---

# /lhg-experiment:power —— 功效测算专项

用户输入在 `$ARGUMENTS` 中：`[t2s|prop2s] [参数]`。三种模式（加载 power-analysis 全程指导）：

## 模式一：算样本量（最常用）
```bash
# 比例型（转化率/点击率/留存率）
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/audit/power_calc.py --test prop2s --p1 0.05 --p2 0.06
# 均值型（停留时长/客单价）
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/audit/power_calc.py --test t2s --d 0.2
```
先帮用户定效应量（power-analysis 第 3 节：历史数据 / 最小业务价值 / 文献三选一），
再跑脚本。**不许直接拿用户随口说的数字算**——先问依据。

## 模式二：已知样本量，算功效
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/audit/power_calc.py --test prop2s --p1 0.05 --p2 0.06 --n 3000
```
功效 <80% → 给三个选项：加样本 / 接受低功效（写进 plan 备注）/ 放弃实验。

## 模式三：已知样本量，算最小可检出效应（MDE）
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/audit/power_calc.py --test prop2s --p1 0.05 --n 8000
```
MDE 大于业务期望的提升 → 直接告诉用户"这个实验做不出来"，别浪费流量。

## 输出
测算结论三行：**每组需要 n=？/ 当前 n 下功效=？% / MDE=？**，附效应量依据说明。
结论存入 `plan.json` 的 `sample_size_basis` 字段（含完整命令，可复现）。

## 硬规则
- α、功效目标必须明示（默认 α=0.05、功效 80% 也要写出来）。
- 算完提醒：实际执行按分流比例与预计流失再上浮 10%~20%。
