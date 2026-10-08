# 数据与身份

raw/保存12个月官方Yellow Taxi全量Parquet；reference/保存区域字典、边界ZIP、ERA5日度天气及边界转换参数；processed/保存月度行程标记、区域小时、特征、逐小时预测及模拟结果。tmp/用于DuckDB溢出、测试和Notebook运行，不作为发布产物。

source_manifest.json记录每个来源URL、下载时间、文件大小、SHA256、行数及字段。SHA256为本地计算，不是TLC提供的发布者校验值。处理前必须12个月齐备、缓存身份一致；缺失月份停止而不补零。月份身份以源文件名和源行号保留，非唯一订单编号。

Power BI仅导入reports/tables中的汇总与测试/模拟结果，不读取原始行程。从GitHub下载后运行`python -m src.restore_powerbi_data`还原两个大CSV，移机刷新需修改ProjectRoot。原始行程文件、环境、模型权重和行级中间产物不加入公开仓库，可运行完整流程重建。来源清单保留这些本地文件的身份记录；区域、天气和汇总数据保留来源与适用许可。
