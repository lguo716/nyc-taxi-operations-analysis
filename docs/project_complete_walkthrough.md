# 完整分析流程与学习入口

项目依次经历数据下载、分月质量处理、运营汇总、区域小时特征、滚动验证与重训、独立测试、模拟、报告与验收。入口是 `python -m src.run_pipeline --stage all --seed 42`。生产入口对缺少月份或缓存身份变化直接报错；没有演示数据替代真实数据的分支。

## 阶段与输入输出

| 程序阶段 | 输入 | 输出与目的 |
|---|---|---|
| download | TLC、Open-Meteo官方文件 | source_manifest、12个月原始Parquet、字典、边界、日度天气 |
| prepare | 完整来源清单与原始文件 | 月度行程标记、区域小时事实、路线、维表、GeoJSON |
| analyze | 区域小时事实与维表 | 月/日/时/区域指标、天气分层、对账 |
| features | 完整月份内的上车记录 | 263区域本地小时网格、严格过去特征、共同有效样本 |
| train | 1—11月特征 | 3滚动窗口×2模型、基准、锁定记录、最终模型与12月预测 |
| evaluate | 锁定模型测试预测 | WAPE/MAE/RMSE与区域、行政区、小时误差 |
| simulate | 12月预测与历史权重 | 三策略×三名额的逐小时分配及守恒结果 |
| report | 全部真实结果 | 分析图、README、业务报告、学习材料、Notebook、PBIP |
| verify | 原始数据及最终产物 | SQL独立对账、模型重新加载、测试重算、模拟一致性 |

## 九阶段学习

| 阶段 | 学习文档 |
|---|---|
| 01 | [业务与数据](learning_stage_01_business_and_data.md) |
| 02 | [质量控制](learning_stage_02_quality.md) |
| 03 | [SQL建模](learning_stage_03_sql_model.md) |
| 04 | [运营诊断](learning_stage_04_operations.md) |
| 05 | [特征工程](learning_stage_05_features.md) |
| 06 | [滚动验证](learning_stage_06_validation.md) |
| 07 | [预测评估](learning_stage_07_evaluation.md) |
| 08 | [调度模拟](learning_stage_08_dispatch.md) |
| 09 | [Power BI与复现](learning_stage_09_powerbi_reproducibility.md) |

## 推荐阅读顺序

先读README和业务报告，把结论与限制说清楚；再读指标字典和质量控制，理解每个分母；最后从features、models和simulate追踪决策依据。Notebook适合逐单元查看实际结果，完整训练由统一程序完成。Power BI显示的是离线已计算结果，刷新不重新训练模型。

## 可复现性边界

TLC不提供发布者SHA256，本项目计算本地身份并保留文件大小、行数、字段和全扫描核对。未来官方若替换同名文件，它可以成为新数据版本，不能冒充旧版本。跨机器浮点结果可能有微小差异；在本机使用固定依赖、种子、线程数和保存模型，独立进程验证容差。数据月度发布不能证明实时到达，因此未建设在线服务、漂移监控或企业调度系统。
