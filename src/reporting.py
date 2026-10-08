import json
import subprocess
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
from pathlib import Path

from .config import ROOT, LABELS
from .utils import read_json, csv
from .learning import learning

def table(frame):
    rows=["| "+" | ".join(frame.columns)+" |","|"+"---|"*len(frame.columns)]
    for _,row in frame.iterrows():
        values=["" if pd.isna(value) else f"{value:.5g}" if isinstance(value,(float,np.floating)) else str(value) for value in row]
        rows.append("| "+" | ".join(values)+" |")
    return "\n".join(rows)

def figures():
    plt.rcParams.update({"font.family":"Microsoft YaHei","axes.unicode_minus":False,"axes.spines.top":False,"axes.spines.right":False,"figure.facecolor":"white","axes.facecolor":"white","font.size":11})
    out=ROOT/"reports/figures"
    def save(fig,name,note):
        fig.text(.01,.01,note,fontsize=8,color="#64748B")
        fig.tight_layout(rect=(0,.035,1,1));fig.savefig(out/name,dpi=220);plt.close(fig)
    month=pd.read_csv(ROOT/"reports/tables/monthly_metrics.csv")
    fig,ax=plt.subplots(figsize=(11,5));ax.plot(month.month_label,month.trips/1e6,marker="o",color="#2563EB",lw=2);ax.set(title="2025 年 Yellow Taxi 月度有效区域上车记录",ylabel="上车记录 / 百万次",xlabel="源月份");ax.tick_params(axis="x",rotation=40)
    save(fig,"01_monthly_demand.png",f"NYC TLC · 2025全年 · 有效区域上车记录 N={int(month.trips.sum()):,} · 不是全部潜在需求")
    heat=pd.read_csv(ROOT/"reports/tables/weekday_hour.csv").pivot(index="weekday",columns="hour",values="trips")/1000
    fig,ax=plt.subplots(figsize=(12,5));im=ax.imshow(heat,aspect="auto",cmap="Blues");ax.set(yticks=range(7),yticklabels=["周一","周二","周三","周四","周五","周六","周日"],xticks=range(0,24,2),xticklabels=[f"{x:02d}" for x in range(0,24,2)],xlabel="纽约本地小时",title="星期 × 小时：全年上车记录合计");fig.colorbar(im,ax=ax,label="千次 / 该星期小时的全年合计")
    save(fig,"02_weekday_hour.png","NYC TLC · 2025全年 · 展示合计而非每小时平均，节假日包含在对应星期")
    zone=pd.read_csv(ROOT/"reports/tables/zone_metrics.csv")
    geometry=read_json(ROOT/"powerbi/taxi_zones.geojson")
    counts=dict(zip(zone.zone_id,zone.trips));patches,values=[],[]
    for feature in geometry["features"]:
        geom=feature["geometry"];polygons=[geom["coordinates"]] if geom["type"]=="Polygon" else geom["coordinates"]
        for polygon in polygons:
            patches.append(Polygon(polygon[0],closed=True));values.append(max(1,counts.get(int(feature["id"]),0)))
    fig,ax=plt.subplots(figsize=(8,9));collection=PatchCollection(patches,cmap="Blues",norm=LogNorm(vmin=1,vmax=max(values)),edgecolor="#94A3B8",linewidth=.25);collection.set_array(np.array(values));ax.add_collection(collection);ax.autoscale_view();ax.set_aspect(1/np.cos(np.deg2rad(40.7)));ax.axis("off");ax.set_title("2025 年区域上车记录热度（对数色阶）");fig.colorbar(collection,ax=ax,shrink=.65,label="全年上车记录 / 次")
    save(fig,"03_zone_map.png","TLC区域边界 · EPSG:4326 · 263实体区域（含Newark） · 264/265未知区域不映射")
    top=zone.nlargest(30,"trips")
    fig,ax=plt.subplots(figsize=(11,5));ax.scatter(top.avg_duration_min,top.avg_fare,s=top.trips/top.trips.max()*700,alpha=.55,color="#0D9488");ax.set(title="需求前30区域：行程时长与平均计价车费",xlabel="平均行程时长 / 分钟（效率有效分母）",ylabel="平均计价车费 / USD（费用有效分母）")
    for _,r in top[top.zone_id.isin([132,138])].iterrows():
        ax.annotate(f"{r.zone_id} {r.zone}",(r.avg_duration_min,r.avg_fare),xytext=(8,0),textcoords="offset points",fontsize=8)
    ax.annotate("曼哈顿主要区域",(15,17),xytext=(21,28),fontsize=9,arrowprops={"arrowstyle":"->","color":"#64748B"})
    save(fig,"04_zone_efficiency.png","NYC TLC · 2025全年 · 气泡面积表示上车记录规模；两项均值使用不同有效分母")
    daily=pd.read_csv(ROOT/"reports/tables/daily_metrics.csv")
    daily["relative_trips"]=daily.trips/daily.groupby(["month","weekday"]).trips.transform("mean")
    weather=daily.groupby("weather_group").agg(mean=("relative_trips","mean"),days=("date","size")).reset_index()
    fig,ax=plt.subplots(figsize=(9,5));ax.bar(weather.weather_group,weather["mean"]*100,color=["#2563EB","#0D9488","#64748B"]);ax.axhline(100,color="#94A3B8",ls="--");ax.set(title="历史天气分组：相对于同月同星期平均需求",ylabel="归一化需求指数 / %（同月同星期均值=100）")
    for i,row in weather.iterrows():ax.text(i,row["mean"]*100+1,f"{row['mean']*100:.1f}%\n{int(row.days)}天",ha="center",fontsize=10)
    ax.set_ylim(0,120)
    save(fig,"05_weather_comparison.png","2025年365天 · NYC代表点ERA5再分析 · 控制月份/星期仍有混杂，仅描述性比较")
    validation=pd.read_csv(ROOT/"reports/tables/validation_metrics.csv").groupby("model_label",as_index=False).wape.mean().sort_values("wape")
    fig,ax=plt.subplots(figsize=(10,5));ax.barh(validation.model_label,validation.wape*100,color="#2563EB");ax.invert_yaxis();ax.set(title="9/10/11 月滚动验证：三个月等权平均 WAPE",xlabel="WAPE / %（越低越好）")
    save(fig,"06_rolling_validation.png","扩展窗口 · 相同有效区域小时样本 · 12月未参与选择")
    test=pd.read_csv(ROOT/"reports/tables/test_metrics.csv").sort_values("wape")
    fig,ax=plt.subplots(figsize=(10,5));ax.barh(test.model_label,test.wape*100,color=["#0D9488" if x else "#64748B" for x in test.selected]);ax.invert_yaxis();ax.set(title="2025 年12月独立测试：五种方案 WAPE",xlabel="WAPE / %（越低越好）")
    save(fig,"07_test_comparison.png",f"独立测试 N={int(test.iloc[0]['n']):,} 区域小时 · 绿色为验证预先选定方案")
    pred=pd.read_csv(ROOT/"reports/tables/forecast_hourly.csv").groupby("date",as_index=False)[["actual","predicted"]].sum()
    fig,ax=plt.subplots(figsize=(12,5));ax.plot(pred.date,pred.actual/1000,label="实际",color="#64748B");ax.plot(pred.date,pred.predicted/1000,label="选定方案",color="#2563EB");ax.set(xticks=range(0,len(pred),3),xticklabels=pred.date.iloc[::3],title="12 月逐日合计：实际与下一小时预测汇总",ylabel="上车记录 / 千次");ax.tick_params(axis="x",rotation=35);ax.legend()
    save(fig,"08_test_trend.png","逐小时一步滚动预测后汇总为天；不是前一天一次性预测次日需求")
    sim=pd.read_csv(ROOT/"reports/tables/simulation_summary.csv")
    fig,ax=plt.subplots(figsize=(10,5))
    for strategy,part in sim.groupby("strategy_label"):ax.plot(part.budget,part.coverage*100,marker="o",label=strategy)
    ax.set(title="12 月服务名额分配：同预算模拟覆盖率",xlabel="每小时模拟可服务订单名额",ylabel="模拟覆盖 / 观察记录（%）",xticks=[500,1000,2000]);ax.legend()
    save(fig,"09_dispatch_simulation.png","均匀/历史/选定预测；无真实车辆状态、基础运力或移动成本，不能解释为实际调度收益")

def notebooks():
    import nbformat
    from nbformat.v4 import new_notebook,new_markdown_cell as md,new_code_cell as code
    setup="from pathlib import Path\nimport json\nimport pandas as pd\nROOT=Path.cwd()\nassert (ROOT/'src').exists()\npd.set_option('display.max_columns',20)"
    definitions=[("01_operations",[
        md("# 运营与数据质量\n\n读取真实全年产物，追溯来源、清洗分母和经营规律。完整处理入口为 `python -m src.run_pipeline --stage all --seed 42`。"),code(setup),
        code("manifest=json.loads((ROOT/'data/source_manifest.json').read_text(encoding='utf-8'))\nprint('完整来源:',manifest['complete'])\nprint('原始记录:',sum(x['rows'] for x in manifest['files'] if x['kind']=='trip'))\nquality=pd.read_csv(ROOT/'reports/tables/data_quality_monthly.csv')\nquality"),
        code("assert (quality.raw_rows==quality.outside_source_month+quality.voided_in_scope+quality.unknown_pickup+quality.demand_rows).all()\nprint('分月源记录、排除记录与需求记录对账通过')\npd.read_csv(ROOT/'reports/tables/kpi_summary.csv')"),
        code("pd.read_csv(ROOT/'reports/tables/zone_metrics.csv').nlargest(10,'trips')[['zone_id','zone','trips','avg_fare','avg_duration_min','flag_rate']]"),
        code("from IPython.display import Image,display\ndisplay(Image(filename=str(ROOT/'reports/figures/02_weekday_hour.png'),width=900))"),
        md("解释：这里的规模是已记录上车记录，不是全部潜在需求。小费率只有银行卡口径，未知区域和效率分母另计。天气比较为描述性，不能归因为天气造成了需求变化。")]),
        ("02_forecasting",[md("# 下一小时预测与独立验证\n\n训练程序负责三个扩展窗口与最终重训；本Notebook检查已实际执行的结果和无泄漏边界。"),code(setup),
        code("protocol=json.loads((ROOT/'models/feature_protocol.json').read_text(encoding='utf-8'))\nprotocol"),
        code("selection=json.loads((ROOT/'models/model_selection.json').read_text(encoding='utf-8'))\nassert selection['test_used_for_selection'] is False\npd.DataFrame(selection['splits'])"),
        code("validation=pd.read_csv(ROOT/'reports/tables/validation_metrics.csv')\nvalidation.pivot(index='model_label',columns='month',values='wape')"),
        code("test=pd.read_csv(ROOT/'reports/tables/test_metrics.csv')\nprint('验证选定:',selection['selected_label'])\ntest[['model_label','selected','n','wape','mae','rmse']]"),
        code("from src.features import zone_features\nimport numpy as np\nidx=pd.date_range('2025-01-01',periods=1400,freq='h')\na=pd.Series(np.arange(1400)%13,index=idx)\nb=a.copy();b.iloc[1000:]=999\npd.testing.assert_frame_equal(zone_features(a,1).loc[:1000,protocol['features']],zone_features(b,1).loc[:1000,protocol['features']])\nprint('改变未来数据不影响过去特征：通过')"),
        md("逐小时预测可以使用此前已经结束的测试小时，但不能利用目标小时的真实订单，也不能在12月上重新选模型。五种方案共享同一有效样本，零分母WAPE为空。")]),
        ("03_dispatch",[md("# 固定服务名额的区域分配模拟\n\n所有实测结果来自12月独立测试。名额是可服务订单数量，不是真实车辆。"),code(setup),
        code("from src.simulate import allocate\n# 明确标注的算法演示输入，不是业务结果\nprint('零预测回退与编号并列处理:',allocate([0,0,0],2,[3,1,2]).tolist())"),
        code("summary=pd.read_csv(ROOT/'reports/tables/simulation_summary.csv')\nsummary[['budget','strategy_label','actual','allocation','served','uncovered','idle','coverage','utilization']]"),
        code("assert (summary.served+summary.uncovered==summary.actual).all()\nassert (summary.served+summary.idle==summary.allocation).all()\nassert (summary.served<=summary.actual).all()\nprint('需求和名额守恒检查通过')"),
        code("from IPython.display import Image,display\ndisplay(Image(filename=str(ROOT/'reports/figures/09_dispatch_simulation.png'),width=900))"),
        md("看板的区域筛选只显示全区域既定分配的子集，不重新分配总名额。未建模车辆途中状态、跨区行驶和基础运力，所以不能将覆盖差额写成企业实际成本节省。")])]
    for name,cells in definitions:
        nb=new_notebook(cells=cells,metadata={"kernelspec":{"name":"nyc-taxi","display_name":"NYC Taxi Python 3.12","language":"python"},"language_info":{"name":"python","version":"3.12.10"}})
        nbformat.write(nb,ROOT/"notebooks"/f"{name}.ipynb")

def report(*, docs_only=False):
    if not docs_only:
        figures();learning();notebooks()
    quality=pd.read_csv(ROOT/"reports/tables/data_quality_monthly.csv").drop(columns="source_month").sum()
    kpi=pd.read_csv(ROOT/"reports/tables/kpi_summary.csv").iloc[0]
    zones=pd.read_csv(ROOT/"reports/tables/zone_metrics.csv").sort_values("trips",ascending=False)
    borough=pd.read_csv(ROOT/"reports/tables/borough_metrics.csv")
    monthly=pd.read_csv(ROOT/"reports/tables/monthly_metrics.csv")
    selection=read_json(ROOT/"models/model_selection.json")
    test=pd.read_csv(ROOT/"reports/tables/test_metrics.csv")
    selected=test.query("selected==1").iloc[0]
    best_baseline=test[test.model.isin(["daily_naive","weekly_naive","four_week_mean"])].sort_values("wape").iloc[0]
    improvement=(best_baseline.wape-selected.wape)/best_baseline.wape
    simulation=pd.read_csv(ROOT/"reports/tables/simulation_summary.csv")
    budget=simulation.query("budget==1000").set_index("strategy")
    delta=int(budget.loc["forecast","served"]-budget.loc["history","served"])
    manhattan=borough.loc[borough.borough=="Manhattan","trips"].sum()/kpi.trips
    results=table(test[["model_label","selected","n","wape","mae","rmse"]])
    daily=pd.read_csv(ROOT/"reports/tables/daily_metrics.csv")
    day_types=daily.groupby("day_type",as_index=False).agg(days=("date","nunique"),trips=("trips","sum"),fare_sum=("fare_sum","sum"),fare_n=("fare_n","sum"))
    day_types["daily_avg_trips"]=day_types.trips/day_types.days
    day_types["avg_fare"]=day_types.fare_sum/day_types.fare_n
    csv(day_types,"day_type_summary")
    day_display=day_types[["day_type","days","trips","daily_avg_trips","avg_fare"]].rename(columns={"day_type":"日类型","days":"日历天数","trips":"上车记录","daily_avg_trips":"日均记录","avg_fare":"平均计价车费USD"})
    routes=pd.read_csv(ROOT/"reports/tables/route_monthly.csv")
    routes=routes[routes.zone_id.between(1,263)&routes.dropoff_zone_id.between(1,263)].groupby(["zone_id","dropoff_zone_id"],as_index=False)[["trips","efficiency_n","duration_min_sum"]].sum().nlargest(10,"trips")
    names=zones.set_index("zone_id").zone
    routes["pickup_zone"]=routes.zone_id.map(names)
    routes["dropoff_zone"]=routes.dropoff_zone_id.map(names)
    routes["avg_duration_min"]=routes.duration_min_sum/routes.efficiency_n.replace(0,float("nan"))
    csv(routes,"route_top_annual")
    route_display=routes[["zone_id","pickup_zone","dropoff_zone_id","dropoff_zone","trips","avg_duration_min"]].rename(columns={"zone_id":"上车区ID","pickup_zone":"上车区","dropoff_zone_id":"下车区ID","dropoff_zone":"下车区","trips":"上车记录","avg_duration_min":"有效平均分钟"})
    errors=pd.read_csv(ROOT/"reports/tables/test_errors_by_group.csv")
    selected_errors=errors[errors.model==selection["selected_model"]]
    borough_errors=selected_errors[selected_errors.dimension=="borough"].sort_values("absolute_error_sum",ascending=False)
    hour_errors=selected_errors[selected_errors.dimension=="hour"].nlargest(5,"mae")
    zone_errors=pd.read_csv(ROOT/"reports/tables/test_zone_metrics.csv")
    zone_errors=zone_errors[zone_errors.model==selection["selected_model"]].nlargest(5,"absolute_error_sum")
    zone_errors=zone_errors.assign(zone=zone_errors.zone_id.map(names))
    csv(borough_errors,"selected_error_borough");csv(hour_errors,"selected_error_hour_top");csv(zone_errors,"selected_error_zone_top")
    def error_display(frame):
        frame=frame[["group","actual_sum","absolute_error_sum","wape","mae","rmse"]].copy()
        frame["wape"]=frame.wape.map(lambda value:"" if pd.isna(value) else f"{value:.2%}")
        return frame.rename(columns={"group":"分组","actual_sum":"实际记录","absolute_error_sum":"绝对误差合计","wape":"WAPE","mae":"MAE","rmse":"RMSE"})
    zone_display=zone_errors[["zone_id","zone","actual_sum","absolute_error_sum","wape","mae","rmse"]].copy()
    zone_display.wape=zone_display.wape.map(lambda value:"" if pd.isna(value) else f"{value:.2%}")
    findings=f"""# 城市出行运营分析与区域需求预测：业务报告

## 结论与建议

2025年12个月共扫描 **{int(quality.raw_rows):,}条原始记录**，有效区域上车记录 **{int(kpi.trips):,}次**。Manhattan占比 **{manhattan:.2%}**，需求最高区域是 **{zones.iloc[0].zone}（{int(zones.iloc[0].zone_id)}）**。建议先按小时和区域检查需求集中程度，再结合真实车辆数据判断是否应调度；本数据不能直接测量未满足需求。

三个扩展验证月选定 **{selection['selected_label']}**。12月独立测试 **{int(selected['n']):,}个区域小时**，WAPE **{selected.wape:.4%}**、MAE **{selected.mae:.4f}次/区域小时**、RMSE **{selected.rmse:.4f}次/区域小时**。相对测试中最佳简单基准“{best_baseline.model_label}”，WAPE相对变化为 **{improvement:.2%}的降低**；该比较只描述独立测试结果，未用来重新选择模型。

默认每小时1000名额的模拟中，预测方案覆盖 **{int(budget.loc['forecast','served']):,}次**，历史方案覆盖 **{int(budget.loc['history','served']):,}次**，差额 **{delta:+,}次**。预测方案模拟覆盖率 **{budget.loc['forecast','coverage']:.2%}**。这些是固定假设下的分配结果，不能推断真实空驶率、车辆数或成本节省。

## 数据与质量

数据来源为[TLC官方2025年Yellow Taxi月度Parquet](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)、Taxi Zone字典/边界，以及[Open-Meteo ERA5日度天气](https://open-meteo.com/en/docs/historical-weather-api)。来源文件SHA256由本地计算，发布者未提供预期SHA256；保留完整下载身份、字段、行数和全扫描核对。节假日来自[OPM 2025日历](https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/#url=2025)。

原始记录排除拆分：源月份以外 **{int(quality.outside_source_month):,}**、明确作废 **{int(quality.voided_in_scope):,}**、无法映射上车区域 **{int(quality.unknown_pickup):,}**，剩余进入需求口径。相同原字段的月内额外记录 **{int(quality.identical_field_extra_rows):,}**，保留而不据此认定重复订单。原始数据负金额标记 **{int(quality.negative_amount):,}**，不自动删除需求记录。

有效费用样本 **{int(kpi.fare_n):,}**，平均计价车费 **${kpi.avg_fare:.2f}**，平均乘客总支付 **${kpi.avg_total_charge:.2f}**。效率有效样本 **{int(kpi.efficiency_n):,}**，平均里程 **{kpi.avg_distance_km:.2f}km**、时长 **{kpi.avg_duration_min:.2f}分钟**、速度 **{kpi.avg_speed_kmh:.2f}km/h**。银行卡小费率 **{kpi.tip_rate:.2%}**，分子与分母来自同一tip_valid样本，不含现金小费。

![月度需求](figures/01_monthly_demand.png)

## 区域、时段与天气

月份最高为 **{monthly.loc[monthly.trips.idxmax(),'month_label']}**，记录 **{int(monthly.trips.max()):,}次**。全年合计受月份天数、节假日与活动影响，不直接视为单独的季节因果效应。区域、工作日和小时规律见真实汇总表；机场与不同费率区域应分开解释。

![星期小时](figures/02_weekday_hour.png)
![区域地图](figures/03_zone_map.png)

按互斥日期分类，节假日优先于周末；以下日均分母为各类实际日历天数，费用仍按有效费用记录加权。节假日使用2025联邦节假日口径，不能直接推广为纽约所有活动日。

{table(day_display)}

全年上车至下车区域流向前十名如下，来自route_monthly的12个月合计，仅此表限定上下车区域均为1—263。未知下车区仍保留在原路线表及上车需求中。区域内行程可能在同一区上下车，因此同区组合不能解释为零距离。

{table(route_display)}

路线热度适合提出接驳或分区服务假设；它不包含车辆空驶路径，也无法直接计算回程载客概率。

天气采用纽约代表点的日度再分析，按月份与星期分层报告天数和日均记录。图中对同月同星期均值归一化，仍有活动和乘客结构混杂；没有天气因果结论，也没有在模型中使用未来天气。

![天气](figures/05_weather_comparison.png)

## 时间验证与独立结果

截至8/9/10月训练，分别验证9/10/11月，以三个月等权平均WAPE锁定方案。LightGBM Poisson为31/63叶、学习率0.05，上限2000轮、L1早停100轮。最终用1—11月重训，轮数为各验证最佳轮数中位数。12月不参与选择或早停。所有方案使用相同有效样本，零需求分母WAPE为空。

{results}

![测试比较](figures/07_test_comparison.png)
![测试趋势](figures/08_test_trend.png)

预测[t,t+1)时只使用已完成小时与已知日历，测试期间此前结束的小时可以用于下一小时滞后。数据按月发布，所以这是假设历史小时计数及时可得的离线评估，不是已上线实时系统。夏令时歧义及其滞后/滚动影响样本排除，完整月内真实无记录区域小时补零。

### 选定方案的误差切片

行政区结果按绝对误差贡献排序；全区域WAPE不能取下表WAPE的简单平均。EWR为Newark服务区域，单独解释。

{table(error_display(borough_errors))}

MAE最高的五个本地目标小时如下；这是区域小时平均误差，不能解释为这些小时的全部需求预测总量误差。

{table(error_display(hour_errors))}

绝对误差贡献最高的五个区域如下。重点改善高频区域有利于总量误差，但低频区域仍应单独检查，不能只追求一个全局WAPE。

{table(zone_display)}

## 调度情景与局限

{table(simulation[['budget','strategy_label','served','uncovered','idle','coverage','utilization']])}

![分配模拟](figures/09_dispatch_simulation.png)

名额按区域权重比例分配，再用最大余数法整数化；同分按区域编号，零预测回到均匀。覆盖=min(实际,名额)，所有分配、需求和闲置守恒。结果没有考虑基础运力、司机行为、车辆途中状态或跨区移动，不写成真实收益。

预测优势不等于因果效果，低频区域的WAPE可能为空。公开记录受提供方质量影响，不能代表纽约全部出行市场。地理热度与收费异常都是排查线索，需要真实运营数据进一步验证。
"""
    (ROOT/"reports/findings.md").write_text(findings,encoding="utf-8")
    summary=f"""# 项目摘要

**城市出行运营分析与区域需求预测｜DuckDB SQL、Python、LightGBM、Power BI**

- 分月处理TLC 2025全年{quality.raw_rows/1e6:.2f}百万条Yellow Taxi公开记录，建立行程、区域小时与路线模型，分离需求、费用和效率分母，完成来源身份校验、质量标记及SQL对账。
- 构建263区域下一小时需求特征，采用三个扩展时间窗口比较三种朴素基准与两种LightGBM Poisson配置；验证锁定{selection['selected_label']}，独立12月测试WAPE为{selected.wape:.2%}、MAE为{selected.mae:.2f}次/区域小时。
- 在500/1000/2000服务名额假设下比较三种区域分配策略，默认1000名额时预测方案相对四周历史方案模拟覆盖差额为{delta:+,}次；制作四页Power BI展示运营、区域、预测和策略，明确结果属于公开数据离线评估及模拟。

结果与复现证据见[完整验收记录](project_acceptance.md)。模拟覆盖差额不能解释为真实成本节省、车辆增加或实际部署效果。
"""
    (ROOT/"reports/project_summary.md").write_text(summary,encoding="utf-8")
    (ROOT/"reports/methodology_faq.md").write_text(f"""# 方法说明与常见问题

## 分析流程概述

本项目使用纽约TLC 2025年{quality.raw_rows/1e6:.2f}百万条出租车公开记录，分析区域小时需求规律、下一小时预测和名额分配三个问题。DuckDB分月扫描Parquet，保留原记录身份，把需求、费用、效率和小费分母分开。预测比较三个朴素基准和两种LightGBM Poisson配置，用9/10/11月扩展窗口选择，12月独立验收。最终选定{selection['selected_label']}，测试WAPE {selected.wape:.2%}。模拟部分采用每小时500/1000/2000个服务名额，按均匀、历史和预测权重分配，报告覆盖和闲置。四页Power BI展示运营分析、区域诊断、预测误差与模拟结果；这些结果不能解释为真实车辆调度收益。

## 方法与结果问答

**为什么不随机划分？** 随机划分会让未来季节模式进入过去；扩展窗口更接近时间顺序。12月不参与早停或方案选择。

**为什么不能算空驶率？** 没有公开车辆唯一身份、空驶轨迹和可用状态，慢速或区域流入流出不等于空驶。

**怎么防止泄漏？** 预测目标小时t先shift再rolling；只用t之前完整小时。天气再分析只用于描述。改变未来数据的测试保证过去特征不变。

**零订单与缺数据如何区分？** 12个月源文件必须完整；完整月内没有记录的区域小时才补0。缺月份直接报错。夏令时歧义设NaN，不冒充零。

**为什么负金额不直接删？** 它可能是退款或更正，不能仅凭金额断定没有记录过上车。费用分母排除，但需求口径保留；这个选择及其限制都明确披露。

**为什么不用深度学习？** 先做有业务含义的基准，LightGBM处理区域、日历与滞后特征。方法复杂不保证更准确；本次结果由独立验证决定。

**结果如何落地？** 先接入可用车辆、数据延迟和移动成本，再做受约束调度及真实实验。本项目只提供离线优先级和容量分配证据。
""",encoding="utf-8")
    readme=f"""# 城市出行运营分析与区域需求预测

**DuckDB SQL · Python · LightGBM · Power BI · 2025全年公开行程**

[GitHub项目仓库](https://github.com/lguo716/nyc-taxi-operations-analysis)

从{int(quality.raw_rows):,}条TLC Yellow Taxi源记录，分析出行规模、区域效率与质量，并预测263区域下一小时的已记录上车量。完成三个扩展验证窗口、独立12月测试和固定服务名额的区域分配模拟。结果均来自实际运行，不预设预测提升。

## 主要结果

| 指标 | 实际结果 |
|---|---:|
| 源记录 | {int(quality.raw_rows):,} |
| 有效区域上车记录 | {int(kpi.trips):,} |
| 实体区域 / 小时网格 | 263 / 2,303,880 |
| 验证选定方案 | {selection['selected_label']} |
| 12月独立测试区域小时 | {int(selected['n']):,} |
| 测试WAPE / MAE | {selected.wape:.4%} / {selected.mae:.4f}次 |
| 1000名额：预测相对历史模拟覆盖差 | {delta:+,}次 |

![预测比较](reports/figures/07_test_comparison.png)

## 数据、粒度与质量

[TLC官方来源](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)按月全量扫描，来源、SHA256、字节数、行数、字段保存在[data/source_manifest.json](data/source_manifest.json)。天气来自[Open-Meteo ERA5](https://open-meteo.com/en/docs/historical-weather-api)，只做历史分组分析；许可与引用见[NOTICE](NOTICE.md)。

行程、区域小时、路线事实及日期/小时/区域维表，保留各指标总量和有效次数。负金额、未知区域、时间/里程/速度异常分别标记；相同原字段不直接删除。上车量是已完成出行的代理，不是潜在总需求。区域1为Newark，264/265单独统计。[完整口径](docs/metric_definitions.md)

## 模型与业务建议

按9/10/11月扩展验证选择方案，用1—11月重训，12月只评估。对比前一天、前一周、四周同星期小时均值与31/63叶LightGBM Poisson。仅使用过去小时、区域和已知日历，夏令时歧义及其窗口排除。报告WAPE/MAE/RMSE及区域/行政区/小时误差，简单基准优势如实保留。[业务报告](reports/findings.md)

调度模拟每小时500/1000/2000个订单服务名额，比较均匀、历史和预测分配，计算覆盖、未覆盖和闲置；没有车辆位置、基础运力和移动成本，不声称空驶或成本收益。

## 复现

Windows / Python 3.12，项目根目录运行：

```powershell
python -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe -m src.run_pipeline --stage all --seed 42
.\\.venv\\Scripts\\python.exe -m pytest -q
.\\.venv\\Scripts\\python.exe -m src.execute_notebooks
```

首次联网下载约0.8GB原始数据，后续校验缓存；DuckDB设置4线程/8GB内存上限。阶段可用download/prepare/analyze/features/train/evaluate/simulate/report/verify单独运行，时长和日志见reports/stage_timings.json、logs/。`report`重建自动报告和PBIP，手工修改前保留自己的版本。`verify`在独立进程重新计算SQL、加载模型并重算完整测试预测。

## Power BI与学习入口

下载仓库后可直接打开PBIX查看四页结果。刷新PBIX或打开PBIP前，在项目根目录运行`python -m src.restore_powerbi_data`，从随附的[汇总表压缩包](reports/tables/powerbi_large_tables.zip)还原两个较大的CSV，逐个校验大小和SHA256，再将Power BI的ProjectRoot参数改为自己的项目路径。此步骤仅需Python标准库，无需下载原始行程或重训模型。

[四页可编辑PBIP](powerbi/Taxi.pbip) · [完整PBIX](powerbi/nyc_taxi_operations.pbix) · [看板说明](powerbi/README.md) · [实际验收](reports/project_acceptance.md)

![运营总览](reports/figures/powerbi/report_overview.png)

[完整流程与九阶段学习](docs/project_complete_walkthrough.md) · [运营Notebook](notebooks/01_operations.ipynb) · [预测Notebook](notebooks/02_forecasting.ipynb) · [模拟Notebook](notebooks/03_dispatch.ipynb) · [方法说明与常见问题](reports/methodology_faq.md) · [项目摘要](reports/project_summary.md)

仅查看结果无需下载原始数据。Power BI导入reports/tables；看板刷新不训练模型。公开仓库包含源码、汇总结果、PBIP/PBIX、已执行Notebook及图表，原始行程数据、本地环境、模型权重、行级中间产物与运行日志留在本地，可通过完整流程重建。两个超大CSV以ZIP发布并可无损还原；[本地验收清单](reports/delivery_manifest.json)也记录未纳入仓库的本地产物身份。
"""
    (ROOT/"README.md").write_text(readme,encoding="utf-8")
    if not docs_only:
        subprocess.run([sys.executable,str(ROOT/"powerbi/build_dashboard.py")],check=True,cwd=ROOT)
        from .restore_powerbi_data import pack
        pack()
