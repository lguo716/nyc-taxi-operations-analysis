# 阶段09：Power BI与复现

本页命令均在项目根目录执行，`python`指本项目独立环境；未激活时用 `.\.venv\Scripts\python.exe` 替代。代码中的教学小例子不用于业务结论。

## 要理解的问题

看板导入汇总数据，不导入全年原始行程；度量用总和与有效次数计算。区域与日期维表单向过滤事实表，模拟名额表是独立参数，DAX读取所选名额。区域筛选展示全区域既定分配的子集，不在看板里重新分配1000个名额。

## 本项目的做法

PBIP保存可编辑报告与语义模型源文件，PBIX保存实际Desktop报告。迁移项目时修改ProjectRoot再刷新。四页分别回答规模、区域效率、下一小时预测和模拟决策。打开后应检验月份/行政区/区域筛选，地图点击与500/1000/2000参数，最后保存并重新打开。源文件验证不能代替实际Desktop验收。

## 自检练习

练习：在独立进程运行 python -m src.run_pipeline --stage verify，对照SQL核对、模型重新加载、测试预测重算和名额守恒记录。查看验收文档，不把未通过项改写为已完成。

[查看实际产物](../reports/project_acceptance.md) · [完整流程](project_complete_walkthrough.md)

## 动手步骤与检查点

1. 直接打开 powerbi/nyc_taxi_operations.pbix；运营页全年、预测与模拟页12月，模拟名额默认1000。
2. 改月份和区域，观察卡片、曲线和地图联动；源质量表及五方案测试比较有独立口径，查看页脚说明。
3. 在模拟页切换500/1000/2000，与 simulation_summary.csv 对照。区域筛选不会触发Python重新分配。
4. 移动项目后修改 Power Query 的 ProjectRoot 参数，刷新并保存；不需要重新下载原始数据就能查看当前结果。
5. 复现核心流程时使用固定依赖、种子和线程，检查 artifact_verification.json、reproducibility_verification.json 和 notebook_verification.json。

练习参考：源文件结构检查、数据计算检查和实际Desktop显示是三个不同检查。四页截图不能证明筛选可操作；PBIP存在不能证明PBIX已保存；训练日志存在也不能证明模型重加载预测一致。验收记录分别给出证据，并保留静态工具对新版Shape Map格式的未通过诊断。

`report`阶段会重建自动材料、未执行Notebook和PBIP；自己的手工编辑要先保存。重建后执行 `python -m src.execute_notebooks`，再刷新与保存Desktop。统一流水线不自动驾驶Desktop界面。
