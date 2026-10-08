# 四页 Power BI 看板

打开Taxi.pbip查看可编辑源文件；nyc_taxi_operations.pbix是实际Desktop保存的完整报告。四页为运营总览、区域效率与异常、区域下一小时需求预测、调度名额分配模拟。真实打开、刷新、保存、DAX与交互证据见../reports/project_acceptance.md。

## 数据与刷新

从GitHub下载后，先在项目根目录运行`python -m src.restore_powerbi_data`，无损还原随附ZIP中的fact_zone_hour.csv与simulation_hourly.csv。还原入口使用Python标准库，逐个核对SHA256；已有正确文件会复用。查看PBIX已有结果无需执行此步骤，刷新或从PBIP导入时需要。

模型导入reports/tables中的CSV，ProjectRoot参数指向项目根目录。移机后在转换数据→管理参数修改它，关闭并应用后刷新。UTF-8 CSV使用en-US转换数值，日期为2025日历日期。刷新只读取离线产物，不重新训练或重新分配名额。重新运行分析后再刷新Desktop。

使用Python重新生成：`.\.venv\Scripts\python.exe powerbi\build_dashboard.py`。此命令会重写自动生成PBIP源文件；手工编辑版本需先保留。本项目自己包含Microsoft基础主题，不依赖另一个项目目录。

## 模型关系

dim_date、dim_zone、dim_hour单向过滤fact_zone_hour、forecast_hourly和simulation_hourly；dim_strategy过滤模拟事实。dim_budget是独立参数，DAX按Selected Budget（默认1000）过滤模拟事实。没有双向连接事实表。test_metrics的五方案比较固定展示完整12月，独立于区域筛选；全年源质量表也不受区域/月份影响，页面标题明确说明。

区域键1—263与本地taxi_zones.geojson一一对应，264/265不在地图上。Shape Map使用嵌入的本地边界，不需要在线底图。区域1为Newark Airport，归属EWR而不是五个纽约行政区。

## 页面默认与交互

运营和区域页默认全年、全部行政区及区域。预测和模拟页固定独立测试2025年12月；区域和行政区筛选作用于对应事实。预测页图表是每小时一步预测汇总，不是次日一次预测。模拟默认1000名额，支持500/2000；区域筛选展示全区域既定分配的子集，不能重新分配全部预算。

## 度量口径

完整DAX见measures.dax。均值重新用总量/有效次数计算，银行卡小费率是同口径小费合计/计价车费合计。WAPE是绝对误差合计/实际合计，MAE和RMSE使用区域小时样本数。模拟覆盖=min(观察记录,区域名额)，覆盖率分母为观察记录；跨策略实际量重复，不跨策略相加。总支付不是平台收入，模拟名额不是车辆数。

package.json固定Microsoft报告工具版本，pnpm-lock.yaml锁定依赖。只需查看PBIX时不必安装Node依赖；需要重新验证/捕获时，在项目根目录执行`pnpm --dir powerbi install --frozen-lockfile`。实际保存与交互应由Desktop验收，结构验证不能代替真实显示效果。

本机Desktop已通过地图显示、筛选联动、PBIX重开及刷新验收。附加静态作者工具0.4.0仍报告4项Shape Map渐变格式兼容性诊断和1项Schema警告，未记为通过；原始诊断与处理依据见[完整验收记录](../reports/project_acceptance.md)。
