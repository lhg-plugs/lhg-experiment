<!-- About 简介（推送后填写到仓库 About 栏）：
小白也能做靠谱实验：假设→设计→功效测算→结果解读一条龙 ｜ 一键安装：/plugin marketplace add lhg-plugs/lhg-experiment
-->
<!-- topics（推送后打）：claude-code, claude-plugin, agent-skills, experiment, ab-test, statistics -->

# lhg-experiment：实验设计专家，小白也能做靠谱实验

> **一句话介绍**：给 AI 编程助手装上"实验设计专家"——研究假设 → 实验设计选择 → 功效测算（自带纯 Python 脚本）→ 结果解读一条龙；**确定性审计专抓 p-hacking，样本量不再拍脑袋**。
>
> **一键安装**：在 Claude Code 里运行
> ```
> /plugin marketplace add lhg-plugs/lhg-experiment
> /plugin install lhg-experiment@lhg-plugs
> ```

## 它是什么

`lhg-experiment` 是一个 Claude Code 插件（plugin 为主、skill 为辅）：

- **3 个命令**（小白入口）：`experiment` 实验一条龙（假设→设计→测算→解读），`power` 功效测算专项（算样本量/算功效/算 MDE），`ab-test` A/B 测试专项（分流/时长/SRM/显著性判定）
- **3 个平台中立 skill**（方法论，可移植到豆包/Workbuddy 等 agent 平台）：`exp-design` 实验设计选择框架（最小可用决策树）、`power-analysis` 功效分析原理与效应量三设定法、`result-read` 结果四步解读法与 p-hacking 识别手册
- **3 个专家 agent**：实验设计顾问、功效测算师、结果审查专家（魔鬼代言人）
- **2 个硬门 hook**：commit 前跑实验审计（有 blocker 拦截，可一键关闭）；写实验报告时"只报 p 值无效应量"提醒
- **20 条确定性审计规则**（`experiment_audit.py`）：无对照组/无功效测算/样本不足拦截；多重比较未校正/偷看提前停/只报 p 值/事后分组挖掘预警
- **核心资产 `power_calc.py`**：纯 Python 标准库功效测算脚本（两样本 t 检验 / 两组比例检验），算样本量、算功效、算 MDE 三种模式，零第三方依赖

## 3 个命令用法

| 命令 | 作用 | 示例 |
|---|---|---|
| `/lhg-experiment:experiment` | 实验一条龙：假设→设计→功效测算→执行清单→结果解读 | `/lhg-experiment:experiment "首页改版能不能提升转化率"` |
| `/lhg-experiment:power` | 功效测算专项：算样本量 / 算功效 / 算 MDE | `/lhg-experiment:power prop2s --p1 0.05 --p2 0.06` |
| `/lhg-experiment:ab-test` | A/B 测试专项：分流方案→时长→SRM→显著性判定 | `/lhg-experiment:ab-test "新文案 vs 老文案"` |

## 目录结构

```
lhg-experiment/
├── .claude-plugin/          # plugin.json（插件清单）+ marketplace.json（本仓即市场）
├── commands/                # 3 个命令：experiment / power / ab-test
├── skills/                  # 3 个平台中立 skill（exp-design / power-analysis / result-read）
├── agents/                  # 3 个专家 agent（designer / power-calculator / result-reviewer）
├── hooks/                   # commit 审计硬门 + 写报告提醒（fail-open，可一键关闭）
├── scripts/audit/           # power_calc.py（功效测算）+ experiment_audit.py（20 条规则）
├── fixtures/                # 好/坏对照用例（bad/good）
├── smoke_test.py            # 冒烟测试（49 项）
├── ATTRIBUTION.md           # 灵感来源声明
└── LICENSE                  # MIT
```

## 功效测算脚本速览

```bash
# 比例型：基准转化率 5%，期望提升到 6%，每组要多少样本？
python3 scripts/audit/power_calc.py --test prop2s --p1 0.05 --p2 0.06
# → 每组需要样本量：8158

# 均值型：期望小效应 d=0.2
python3 scripts/audit/power_calc.py --test t2s --d 0.2
# → 每组需要样本量：393

# 已有 8000 样本，能检出多小的变化？（MDE）
python3 scripts/audit/power_calc.py --test prop2s --p1 0.05 --n 8000
# → MDE：相对提升约 21.6%
```

## 什么时候用 / 什么时候不用（FAQ）

**Q：和 lhg-growth-lab（增长实验专家）有什么区别？**
A：growth-lab 面向增长黑客的线上快速试错；本插件面向**科研/产品人的严谨实验**：实验设计类型选择（随机/区组/析因/准实验）、功效测算脚本、p-hacking 防范。做论文、做产品决策评审、需要"结论站得住"时用本插件。

**Q：我完全不懂统计学，能用吗？**
A：能，这正是本插件的定位。skill 里不堆公式：决策树是选择题，效应量有三种设定法（含"最小业务价值法"这种业务语言），样本量是脚本算的。你只需要回答"改了什么、看什么指标、提升多少才值得做"三个问题。

**Q：样本量算出来太大，流量不够怎么办？**
A：三条路：① 换更高频的指标（如用点击率代替转化率）；② 接受更大的 MDE（只测大变化）；③ 放弃实验。插件会诚实告诉你"做不出来"，而不是让你做一个注定检不出的实验。

**Q：一定要用 Claude Code 吗？**
A：`skills/` 下的方法论是平台中立的纯 Markdown，可直接搬到豆包、Workbuddy 等 agent 平台用；`power_calc.py` 是纯 Python 脚本，任何地方都能跑。只有 commands/agents/hooks 需要 Claude Code。

**Q：hook 把我的 commit 拦了怎么办？**
A：两种处理：① 按审计报告修掉 blocker（推荐）；② 紧急情况 `export LHG_EXPERIMENT_HOOKS_OFF=1` 单次豁免。注意：豁免不等于问题消失，只是你决定自己承担。

**Q：能用于医学/金融风控等高风险实验吗？**
A：本插件是通用方法论工具，不构成专业领域决策建议。人体试验、医疗、金融等高风险场景请务必咨询持证专业人士，并遵守相关法规与伦理审查要求。

## 自检与反馈

本插件自带质检：每次使用后可跑 `python3 smoke_test.py` 一键验证（JSON 合法、skill/command/agent 完整性、20 条审计规则、fixtures 埋点命中、power_calc 三种模式、hooks 行为）。

发现 bug 或有改进建议，以 `[QC] <一句话问题>` 为标题提交到 https://github.com/lhg-plugs/lhg-experiment/issues，正文写清"复现步骤 → 实际表现 → 期望表现"。

## lhg-plugs 插件矩阵

| 插件 | 一句话 | 安装 |
|---|---|---|
| [lhg-fullstack](https://github.com/lhg-plugs/lhg-fullstack) | 小白一句话 → 高质量全栈应用 | `/plugin install lhg-fullstack@lhg-plugs` |
| [lhg-experiment](https://github.com/lhg-plugs/lhg-experiment) | 实验设计专家：假设→设计→功效测算→结果解读一条龙 | `/plugin install lhg-experiment@lhg-plugs` |
| [lhg-patent](https://github.com/lhg-plugs/lhg-patent) | 专利撰写助手：交底书→权利要求书→说明书→新创性自检 | `/plugin install lhg-patent@lhg-plugs` |

> 完整矩阵见 [lhg-plugs/marketplace](https://github.com/lhg-plugs/marketplace)。

## 出品：刘洪光

本插件由真人出镜 IP「刘洪光」（安徽合肥）出品，归属 [lhg-skills](https://github.com/lhg-skills)。

- GitHub 主页：https://github.com/lhg-skills —— 全部 skill 开源在此，欢迎 star
- 视频号：搜「刘洪光实名上网」
- 微信：lhgsmsw
