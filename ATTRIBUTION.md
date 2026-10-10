# 灵感来源与致谢（Attribution）

本插件的**方法论灵感**来自以下公开的统计学常识与优秀开源项目，**所有实现代码、检测规则与文案均为原创**，未复制任何第三方的原文案或代码。

| 来源 | 说明 | 借鉴了什么思路 |
|---|---|---|
| 经典实验设计教材（Fisher《实验设计》、Box/Hunter/Hunter《统计学 for experimenters》） | 公有领域统计学常识 | 随机对照/区组/析因设计的基本思想；本插件的决策树为原创的"最小可用"简化版 |
| Cohen《Statistical Power Analysis for the Behavioral Sciences》 | 效应量惯例（d=0.2/0.5/0.8） | 效应量分档参照；样本量公式为教科书标准公式的独立实现 |
| 《Trustworthy Online Controlled Experiments》（Kohavi 等） | 在线实验最佳实践 | SRM 检查、新奇效应、偷看数据（peeking）危害的问题意识；具体规则与文案均为原创 |
| impeccable（Paul Bakaus，Apache-2.0） | https://github.com/pbakaus/impeccable | "确定性检测规则 + 规则引擎"架构思想；本插件审计脚本的规则注册表模式受其启发，**规则条目全部自研** |
| lhg-plugs/lhg-fullstack（本组织模板仓，MIT） | https://github.com/lhg-plugs/lhg-fullstack | 插件目录结构、hooks 硬门模式、smoke_test 框架（按本领域重写内容） |

## 方法论原创性说明

- 功效测算脚本 `power_calc.py`：公式为教科书标准公式（正态近似），代码独立实现，仅依赖 Python 标准库 `statistics`。
- 审计规则（EXP-*）：针对"实验设计文档 + 结果报告"的原创检查规则，灵感来自 Kohavi 等人指出的问题域，具体判定逻辑均为独立设计。
- 三个 skill 的文案（决策树、效应量三设定法、四步解读法）为面向小白的原创简化表达。

## 本插件自身的许可

本插件原创部分采用 MIT 许可（见 `LICENSE` 文件），版权所有：刘洪光（https://github.com/lhg-skills）。

## 合规提醒

本插件提供的是实验设计方法论与统计测算工具，不构成学术/医疗/金融等专业领域的决策建议。
涉及人体试验、医疗、金融风控等高风险场景，请务必咨询相应领域的持证专业人士。
