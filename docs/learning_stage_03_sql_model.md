# 阶段03：SQL建模

本页命令均在项目根目录执行，`python`指本项目独立环境；未激活时用 `.\.venv\Scripts\python.exe` 替代。代码中的教学小例子不用于业务结论。

## 要理解的问题

行程表用于追溯与独立核对；区域小时表用于运营与预测；路线表用于区域流向。地区、日期和小时都是维度。需求聚合粒度必须唯一，否则连接维表时会重复计算订单。dim_zone 的 zone_id 是唯一键，fact_zone_hour 每个区域、日期、小时至多一行。

## 本项目的做法

DuckDB直接扫描每月Parquet，以4线程和8GB内存上限处理。结果仍按月保存为Parquet，再建立统一视图。费用和效率聚合同时保留总和与有效记录数。多个区域的平均车费必须用总车费/总有效次数，不应平均各区域的平均数。银行卡小费率也用合计小费/对应计价车费。

## 自检练习

练习：运行 sql/03_business_metrics.sql，独立算出某月总记录和小费率；故意平均各区域的平均车费，比较它与正确加权结果的差异。

[查看实际产物](../sql/03_business_metrics.sql) · [完整流程](project_complete_walkthrough.md)

## 动手步骤与检查点

打开 data/processed/nyc_taxi.duckdb；fact_trip 是分月标记Parquet的统一视图。先确认事实粒度与维表唯一键，再跑下面的独立核对：

```python
from pathlib import Path
import duckdb
con = duckdb.connect('data/processed/nyc_taxi.duckdb', read_only=True)
sql = Path('sql/03_business_metrics.sql').read_text(encoding='utf-8')
print(con.execute(sql).fetchdf())
con.close()
```

将结果与 monthly_metrics.csv、sql_monthly_verification.csv 比较。路线汇总使用上车区和下车区两个键，含未知下车区的流向应单独解释；不能因下车区未知就抹掉已知上车需求。

练习答案示例（教学数字）：A区两单车费各10元、B区一单100元，正确均值为120/3=40元；平均两区均值会得到55元。DAX及SQL必须保留120这个总量与3这个有效次数。真实结果以CSV为准。
