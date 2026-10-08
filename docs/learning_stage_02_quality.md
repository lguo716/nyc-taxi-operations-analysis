# 阶段02：质量控制

本页命令均在项目根目录执行，`python`指本项目独立环境；未激活时用 `.\.venv\Scripts\python.exe` 替代。代码中的教学小例子不用于业务结论。

## 要理解的问题

质量控制先回答记录是否可用于某个问题，再决定是否进入对应分母。本项目要求需求记录的上车时间属于源月份、上车区域可映射且不是明确作废；负金额、零里程或速度异常分别影响费用与效率指标，不自动删除该条需求记录。这样不会把某类支付或记录异常误当成需求突然下降。

## 本项目的做法

查看 sql/01_trip_model.sql。需求、车费、效率、小费各有有效标记。车费要求支付类型0/1/2、正费用且非负金额或极端费用；效率要求0<时长<=180分钟、0<里程<=100英里、速度<=130km/h。费用筛查上限为计价车费1000美元、总支付2000美元、小费1000美元，它们只是项目质量阈值。夏令时过渡日采用保守效率排除。相同原字段记录只计数、不删除。

## 自检练习

练习：用一条负金额、一条现金支付、一条零里程记录，分别说明它们进入哪些分母。然后核对原始记录=源月份之外+明确作废+未知上车区域+有效需求记录。

[查看实际产物](../reports/tables/data_quality_monthly.csv) · [完整流程](project_complete_walkthrough.md)

## 动手步骤与检查点

运行 `python -m src.run_pipeline --stage prepare --seed 42`，阅读 sql/01_trip_model.sql 和 data_quality_monthly.csv。按顺序核对：原始范围→源月内记录→作废标记→未知上车区→有效需求。负金额、时长、距离和速度是可同时出现的标记，其数量不能直接相加当排除量。

```python
import pandas as pd
q = pd.read_csv('reports/tables/data_quality_monthly.csv')
assert (q.raw_rows == q.outside_source_month + q.voided_in_scope
        + q.unknown_pickup + q.demand_rows).all()
print(q[['source_month','raw_rows','demand_rows','negative_amount']])
```

练习答案：时间和区域有效的负金额行仍可进入需求，费用分母排除它；有效现金支付可进入费用及效率分母，但不进入银行卡小费率；零里程行可进入需求、可进入有效费用，效率分母排除它。每个答案仍需同时检查其他质量条件。

相同原字段只能说明记录相同，不能证明是同一订单的重复上传。没有唯一订单号时，删除它可能误删真实记录。检查 identical_field_extra_rows，而不是直接使用 drop_duplicates。
