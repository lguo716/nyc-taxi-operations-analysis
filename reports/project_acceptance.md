# 本地交付验收记录

验收日期：2026-10-08。范围为2025全年 Yellow Taxi；所有业务结果来自本地全量运行。源码、报告、学习材料和Power BI成果见[GitHub项目仓库](https://github.com/lguo716/nyc-taxi-operations-analysis)。

公开版中fact_zone_hour.csv与simulation_hourly.csv以随附ZIP发布，`python -m src.restore_powerbi_data`可按大小和SHA256无损还原。原始行程数据、本地环境、模型权重、行级中间产物和日志仍在本地；此处的完整验收与交付身份清单包含这些本地产物。公开版保留源码、全部分析汇总、实际PBIX、可编辑PBIP及学习材料。

## 必需项目与证据

| 验收项 | 状态 | 证据与核对结果 |
|---|---|---|
| 12个月真实官方数据 | 通过 | [来源清单](../data/source_manifest.json)：下载身份、文件大小、SHA256、行数和字段齐备；原始记录48,722,602条 |
| 质量分母与SQL对账 | 通过 | [60项产物验收](artifact_verification.json)、[分月SQL核对](tables/sql_monthly_verification.csv)：原始=214条源月外+0条作废+103,043条未知上车区+48,619,345条有效需求 |
| 流式分月处理与数据模型 | 通过 | DuckDB扫描月度Parquet；行程、区域小时、路线及日期/小时/区域维表齐备；均值保留总量和有效次数 |
| 历史天气与运营分析 | 通过 | 365天ERA5代表点天气、月/星期分层对比及真实区域/流向指标；天气未进入预测特征 |
| 预测协议与时间隔离 | 通过 | [特征协议](../models/feature_protocol.json)、[选择记录](../models/model_selection.json)：263区域、2,303,880小时网格、三个扩展验证月、12月独立测试 |
| 模型与逐小时预测 | 通过 | 保存6个验证模型和2个最终模型、验证/测试逐小时预测、实际值与指标；独立重加载全部测试预测一致 |
| 调度分配及名额守恒 | 通过 | 三策略×三预算，744个12月小时；逐小时预算与需求守恒；零权重和并列规则测试通过 |
| 边界测试 | 通过 | [测试报告](test_results.xml)：21项测试；覆盖缺月、未知区域、真实零值、夏令时、滞后泄漏、时间隔离、名额守恒及零预测/并列 |
| 独立进程统一入口重跑 | 通过 | [重跑证据](reproducibility_verification.json)：`python -m src.run_pipeline --stage all --seed 42`退出0；7项关键模型/预测/结果SHA256逐字节一致 |
| 中文报告与学习材料 | 通过 | README、业务报告、指标字典、完整流程、九阶段材料、方法说明与项目摘要 |
| 三份已执行Notebook | 通过 | [执行核对](notebook_verification.json)：5/6/5个代码单元全部执行，0个错误 |
| 可编辑PBIP及实际PBIX | 通过 | [PBIP](../powerbi/Taxi.pbip)、[PBIX](../powerbi/nyc_taxi_operations.pbix)：由Desktop另存为；独立实例重新打开、读取本地CSV刷新后再次保存 |
| Power BI计算与交互 | 通过 | [39项DAX核对](../powerbi/desktop_verification.json)、[UI核对](../powerbi/ui_verification.json)：金额/分母、区域/月份、模型误差与三档预算均和分析结果一致 |
| 四页高清截图 | 通过 | [总览](figures/powerbi/report_overview.png)、[区域](figures/powerbi/report_regions.png)、[预测](figures/powerbi/report_forecast.png)、[模拟](figures/powerbi/report_dispatch.png)：均从重新打开并刷新后的真实PBIX捕获，逐页人工视觉检查 |

## Desktop实际验收过程

首次导入PBIP，刷新全部13张模型表。区域Shape Map从本地GeoJSON加载263个唯一区域键，不依赖在线底图。点击JFK（132）后，矩阵显示2,062,443条记录、平均车费$63.96；卡片显示平均距离24.55公里、平均速度37.68km/h、效率有效数1,988,789，与区域汇总一致。地图及其他图表可联动。

模拟名额切换为500时，覆盖364,942、闲置7,058、相对历史差1,338；切换2000时，覆盖1,325,757、闲置162,243、差8,384；恢复1000后为706,548、37,452、3,621。三策略矩阵保留相同名额总量。

将报告保存为nyc_taxi_operations.pbix后，在独立Desktop实例（验收PID 18036）重新打开，执行全部CSV刷新。通过只读DAX连接再次核对39项结果。重开的PBIX选择2025-01时，上车记录3,465,683、平均计价车费$18.01、银行卡小费率22.82%；再次恢复全年48,619,345条记录。最终保存状态见[Desktop文件状态](../powerbi/desktop_final_state.json)，无未保存更改。先前创建的实例已关闭，文件占用问题已排除。

运营/区域页默认全年、全部行政区及区域；预测/模拟页固定2025-12，模拟名额默认1000。高清截图来自刷新后的PBIX，分辨率3344×1880。标题、单位、颜色、默认筛选、地图、图表和表格已逐页检查；长区域表/质量表可滚动，未将滚动隐藏行视为数据缺失。

## 未通过的附加检查与限制

**附加静态CLI校验未通过，不能记为通过。** Microsoft报告作者工具0.4.0保留4项`PBIR_FILLRULE_STOP_DOUBLE_WRAP`诊断和1项新版2.13.0视觉容器Schema无法获取的警告，详见[原始诊断](../powerbi/validation.json)。四项均针对两个Shape Map原生渐变色端点的包装格式。采用工具建议的裸Literal会在本机Desktop触发渲染错误；当前保留Desktop实际可渲染、可保存、重新打开后可加载的原生Shape Map格式。真实Desktop截图、地图点击和PBIX重开验收通过，但不能以此宣称该附加静态工具校验通过，或保证所有旧版Desktop兼容。

TLC未提供发布者SHA256；本地哈希用于缓存身份核对，不构成发布者签名。所有验证模型的最佳轮数均达到2000轮上限，最终中位重训轮数也是2000；仅比较既定的31/63叶配置，未声称全局最优或已经充分收敛。

记录量是已完成行程的代理；月度发布不能证明实时小时记录可及时获得。ERA5代表点并不覆盖城市全部局地天气。模拟不含车辆位置、基础运力、跨区移动和真实成本，不能声称真实空驶率或成本收益。新数据版本、跨机器依赖或旧版Desktop需要重新验收。

## 主要结果追溯

选定模型：LightGBM（63叶）。12月WAPE16.4044%、MAE3.6028、RMSE10.3188，来自[test_metrics.csv](tables/test_metrics.csv)。默认1000名额模拟覆盖706,548、未覆盖3,590,835、闲置37,452，来自[simulation_summary.csv](tables/simulation_summary.csv)。源记录及排除记录来自[data_quality_monthly.csv](tables/data_quality_monthly.csv)。最终文件身份见[交付清单](delivery_manifest.json)。
