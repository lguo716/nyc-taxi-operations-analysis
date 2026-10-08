"""Build genuine editable PBIP/PBIR and a CSV-refreshable semantic model."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
REPORT = ROOT / "Taxi.Report"
MODEL = ROOT / "Taxi.SemanticModel"
PAGES = REPORT / "definition/pages"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def lit(value):
    return {"expr": {"Literal": {"Value": str(value).lower() if isinstance(value, bool) else "'" + value.replace("'", "''") + "'" if isinstance(value, str) else str(value) + "D"}}}


def color(value):
    return {"solid": {"color": lit(value)}}


def col(table, name):
    return table, name, "column"


def met(name):
    return "Metrics", name, "measure"


def field(spec, alias=False):
    table, name, kind = spec[:3]
    return {"Measure" if kind == "measure" else "Column": {"Expression": {"SourceRef": {"Source": "s"} if alias else {"Entity": table}}, "Property": name}}


def filter_in(spec, values):
    key = hashlib.sha1((str(spec) + str(values)).encode()).hexdigest()[:20]
    literals = [{"Literal": {"Value": str(v).lower() if isinstance(v, bool) else "'" + str(v).replace("'", "''") + "'"}} for v in values]
    return {"name": key, "field": field(spec), "type": "Categorical", "filter": {"Version": 2, "From": [{"Name": "s", "Entity": spec[0], "Type": 0}], "Where": [{"Condition": {"In": {"Expressions": [field(spec, True)], "Values": [[v] for v in literals]}}}]}}


def visual(page_id, key, kind, title, position, roles=None, objects=None, filters=None, sort=None):
    x, y, width, height = position
    content = {"$schema": SCHEMA + "visualContainer/2.9.0/schema.json", "name": key, "position": {"x": x, "y": y, "z": 0, "height": height, "width": width, "tabOrder": 0}, "visual": {"visualType": kind, "drillFilterOtherVisuals": True, "visualContainerObjects": {"title": [{"properties": {"show": lit(bool(title)), "text": lit(title), "fontSize": lit(12), "fontFamily": lit("Microsoft YaHei"), "fontColor": color("#0F172A")}}], "subTitle": [{"properties": {"show": lit(False)}}], "background": [{"properties": {"show": lit(True), "color": color("#FFFFFF"), "transparency": lit(0)}}], "border": [{"properties": {"show": lit(False)}}]}}}
    if roles:
        content["visual"]["query"] = {"queryState": {role: {"projections": [{"field": field(spec), "queryRef": spec[0] + "." + spec[1], "nativeQueryRef": spec[1], "displayName": spec[3] if len(spec) > 3 else spec[1]} for spec in specs]} for role, specs in roles.items()}}
        if sort:
            content["visual"]["query"]["sortDefinition"] = {"sort": [{"field": field(sort[0]), "direction": sort[1]}], "isDefaultSort": True}
    if objects:
        content["visual"]["objects"] = objects
    if filters:
        copied = json.loads(json.dumps(filters))
        for item in copied:
            item["name"] = hashlib.sha1((page_id + key + item["name"]).encode()).hexdigest()[:20]
        content["filterConfig"] = {"filters": copied}
    write(PAGES / page_id / "visuals" / key / "visual.json", content)
    return content


def text(page_id, key, content, position, size=12, foreground="#475569", bold=False):
    value = visual(page_id, key, "textbox", "", position)
    value["visual"]["objects"] = {"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": content, "textStyle": {"fontFamily": "Microsoft YaHei", "fontSize": f"{size}pt", "color": foreground, "fontWeight": "bold" if bold else "normal"}}]}]}}]}
    value["visual"]["visualContainerObjects"]["background"][0]["properties"]["transparency"] = lit(100)
    write(PAGES / page_id / "visuals" / key / "visual.json", value)


def card(page_id, key, measure, label, position):
    visual(page_id, key, "card", label, position, {"Values": [(*met(measure), label)]}, {"labels": [{"properties": {"fontSize": lit(25), "labelDisplayUnits": lit(1), "color": color("#2563EB")}}], "categoryLabels": [{"properties": {"show": lit(False)}}]})


def matrix(page_id, key, title, position, rows, measures):
    visual(page_id, key, "pivotTable", title, position, {"Rows": rows, "Values": [(*met(name), label) for name, label in measures]}, {"grid": [{"properties": {"textSize": lit(10)}}], "rowHeaders": [{"properties": {"fontSize": lit(10)}}], "columnHeaders": [{"properties": {"fontSize": lit(10)}}], "values": [{"properties": {"fontSize": lit(10)}}], "subTotals": [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}]})


def slicer(page_id,key,spec,title,position,default=None):
    objects={"data":[{"properties":{"mode":lit("Dropdown")}}],"header":[{"properties":{"show":lit(False)}}],"selection":[{"properties":{"singleSelect":lit(True)}}]}
    if default is not None:
        objects["general"]=[{"properties":{"filter":{"filter":filter_in(spec,[default])["filter"]}}}]
    visual(page_id,key,"slicer",title,position,{"Values":[spec]},objects)


def page(name,title,subtitle,test=False):
    content={"$schema":SCHEMA+"page/2.1.0/schema.json","name":name,"displayName":title,"displayOption":"FitToPage","height":900,"width":1600,"objects":{"background":[{"properties":{"color":color("#F1F5F9"),"transparency":lit(0)}}]}}
    if test:
        test_filter=filter_in(col("dim_date","month_label"),["2025-12"])
        test_filter["name"]="test_month_"+name
        content["filterConfig"]={"filters":[test_filter]}
    write(PAGES/name/"page.json",content)
    text(name,"heading",title,(24,8,1180,56),24,"#0F172A",True)
    text(name,"subtitle",subtitle,(24,68,1180,36),11)
    slicer(name,"borough_slicer",col("dim_zone","borough"),"行政区（全部）",(1240,12,336,72))
    slicer(name,"zone_slicer",col("dim_zone","zone_label"),"区域（全部）",(24,116,470,70))
    if not test:
        slicer(name,"month_slicer",col("dim_date","month_label"),"月份（全年）",(514,116,334,70))
    return name


def shape_map(page_id,key,title,position,measure):
    geometry=json.loads((ROOT/"taxi_zones.geojson").read_text(encoding="utf-8"))
    write(REPORT/"StaticResources/RegisteredResources/taxi_zones.geojson",geometry)
    packaged_map={"geoJson":{"type":lit("packaged"),"name":lit("taxi_zones.geojson"),"content":{"expr":{"ResourcePackageItem":{"PackageName":"RegisteredResources","PackageType":1,"ItemName":"taxi_zones.geojson"}}}}}
    objects={"shape":[{"properties":{"datasourceType":lit("file_upload"),"map":packaged_map,"projectionEnum":lit("mercator")}}],"legend":[{"properties":{"show":lit(False)}}],"defaultColors":[{"properties":{"defaultColor":color("#2563EB")}}]}
    objects["defaultColors"][0]["properties"].update(defaultColor=color("#E2E8F0"),borderColor=color("#94A3B8"),borderThickness=lit(.5))
    # Shape Map stores its native color stops as wrapped expressions. Desktop
    # round-trip verified; generic gradient validators may expect bare literals.
    gradient={"linearGradient2":{"min":{"color":lit("#DBEAFE")},"max":{"color":lit("#1D4ED8")}}}
    objects["dataPoint"]=[{"properties":{"fillRule":gradient}}]
    visual(page_id,key,"shapeMap",title,position,{"Category":[col("dim_zone","zone_key")],"Value":[met(measure)],"Tooltips":[met("Trips"),met("Avg Fare")]},objects)


def build_model():
    import duckdb
    connection=duckdb.connect()
    sim_path=PROJECT/"reports/tables/simulation_hourly.csv"
    connection.execute(f"COPY (SELECT * FROM read_parquet('{(PROJECT/'data/processed/simulation_detail.parquet').as_posix()}')) TO '{sim_path.as_posix()}' (FORMAT CSV,HEADER TRUE)")
    connection.close()
    inputs=["dim_zone","dim_date","dim_hour","fact_zone_hour","forecast_hourly","test_metrics","validation_metrics","test_zone_metrics","simulation_hourly","dim_budget","dim_strategy","data_quality_monthly"]
    tables=[]
    for name in inputs:
        frame=pd.read_csv(PROJECT/"reports/tables"/f"{name}.csv",nrows=1500)
        columns,conversions=[],[]
        for column in frame:
            force_string=column in ["zone_key","zone_label","zone","borough","holiday_name","model","model_label","strategy","strategy_label","source_month","month_label","hour_label","budget_label","weather_group","day_type","split"]
            force_double=column.endswith("_sum") or column in ["predicted","absolute_error","squared_error","wape","mae","rmse","bias","temperature_2m_mean","precipitation_sum","snowfall_sum","wind_speed_10m_max"]
            dtype="dateTime" if column=="date" else "string" if force_string else "double" if force_double else "boolean" if pd.api.types.is_bool_dtype(frame[column]) else "int64" if pd.api.types.is_integer_dtype(frame[column]) else "double" if pd.api.types.is_numeric_dtype(frame[column]) else "string"
            mtype={"dateTime":"type date","boolean":"type logical","int64":"Int64.Type","double":"type number","string":"type text"}[dtype]
            item={"name":column,"dataType":dtype,"sourceColumn":column,"summarizeBy":"none"}
            if dtype=="dateTime":item["formatString"]="yyyy-MM-dd"
            if dtype=="int64":item["formatString"]="#,0"
            if dtype=="double":item["formatString"]="0.00%" if column=="wape" else "#,0.00"
            if name=="dim_zone" and column=="zone_id" or name=="dim_date" and column=="date" or name=="dim_hour" and column=="hour" or name=="dim_strategy" and column=="strategy":item["isKey"]=True
            if name=="dim_budget" and column=="budget_label":item["sortByColumn"]="budget"
            if name=="dim_hour" and column=="hour_label":item["sortByColumn"]="hour"
            columns.append(item);conversions.append('{"'+column+'", '+mtype+'}')
        expression='let\n Source=Csv.Document(File.Contents(ProjectRoot & "\\reports\\tables\\'+name+'.csv"),[Delimiter=",",Encoding=65001,QuoteStyle=QuoteStyle.Csv]),\n Headers=Table.PromoteHeaders(Source,[PromoteAllScalars=true]),\n Typed=Table.TransformColumnTypes(Headers,{'+', '.join(conversions)+'},"en-US")\nin Typed'
        tables.append({"name":name,"columns":columns,"partitions":[{"name":name,"mode":"import","source":{"type":"m","expression":expression}}]})
    container={"name":"Metrics","columns":[{"name":"Placeholder","type":"calculatedTableColumn","dataType":"string","isHidden":True,"sourceColumn":"[Placeholder]"}],"partitions":[{"name":"Metrics","mode":"import","source":{"type":"calculated","expression":'DATATABLE("Placeholder",STRING,{{""}})'}}],"measures":[]}
    definitions=[]
    def measure(name,expression,fmt="#,0.00"):
        container["measures"].append({"name":name,"expression":expression,"formatString":fmt,"displayFolder":"出行运营"})
        definitions.append(name+" =\n"+expression+"\n")
    measure("Trips","SUM(fact_zone_hour[trips])","#,0")
    measure("Fare N","SUM(fact_zone_hour[fare_n])","#,0")
    measure("Total Charge","SUM(fact_zone_hour[total_charge_sum])","$#,0")
    measure("Avg Fare","DIVIDE(SUM(fact_zone_hour[fare_sum]),[Fare N])","$0.00")
    measure("Avg Total Charge","DIVIDE([Total Charge],[Fare N])","$0.00")
    measure("Efficiency N","SUM(fact_zone_hour[efficiency_n])","#,0")
    for label,column in [("Avg Distance","distance_km_sum"),("Avg Duration","duration_min_sum"),("Avg Speed","speed_kmh_sum")]:measure(label,f"DIVIDE(SUM(fact_zone_hour[{column}]),[Efficiency N])")
    measure("Card Tip Rate","DIVIDE(SUM(fact_zone_hour[tip_sum]),SUM(fact_zone_hour[tip_fare_sum]))","0.00%")
    measure("Flagged N","SUM(fact_zone_hour[flagged_n])","#,0")
    measure("Flag Rate","DIVIDE([Flagged N],[Trips])","0.00%")
    measure("Raw Rows","SUM(data_quality_monthly[raw_rows])","#,0")
    measure("Unknown Pickup","SUM(data_quality_monthly[unknown_pickup])","#,0")
    measure("Negative Amount Rows","SUM(data_quality_monthly[negative_amount])","#,0")
    measure("Recorded Duplicates","SUM(data_quality_monthly[identical_field_extra_rows])","#,0")
    selection=json.loads((PROJECT/"models/model_selection.json").read_text(encoding="utf-8"))
    measure("Selected Model",'"'+selection["selected_label"]+'"',"")
    measure("Forecast Actual","SUM(forecast_hourly[actual])","#,0")
    measure("Forecast Predicted","SUM(forecast_hourly[predicted])","#,0")
    measure("Forecast WAPE","DIVIDE(SUM(forecast_hourly[absolute_error]),[Forecast Actual])","0.00%")
    measure("Forecast MAE","DIVIDE(SUM(forecast_hourly[absolute_error]),COUNTROWS(forecast_hourly))")
    measure("Forecast RMSE","SQRT(DIVIDE(SUM(forecast_hourly[squared_error]),COUNTROWS(forecast_hourly)))")
    measure("Test WAPE","MAX(test_metrics[wape])","0.00%")
    measure("Test MAE","MAX(test_metrics[mae])")
    measure("Test RMSE","MAX(test_metrics[rmse])")
    measure("Selected Budget","SELECTEDVALUE(dim_budget[budget],1000)","#,0")
    for label,column in [("Sim Actual","actual"),("Sim Allocation","allocation"),("Sim Served","served"),("Sim Uncovered","uncovered"),("Sim Idle","idle")]:
        measure(label,'VAR B=[Selected Budget] RETURN CALCULATE(SUM(simulation_hourly['+column+']),simulation_hourly[budget]=B)',"#,0")
    measure("Sim Coverage","DIVIDE([Sim Served],[Sim Actual])","0.00%")
    measure("Sim Utilization","DIVIDE([Sim Served],[Sim Allocation])","0.00%")
    for name,base in [("Forecast Served","Sim Served"),("Forecast Coverage","Sim Coverage"),("Forecast Idle","Sim Idle")]:
        measure(name,'CALCULATE(['+base+'],dim_strategy[strategy]="forecast")',"0.00%" if "Coverage" in name else "#,0")
    measure("Forecast Advantage",'CALCULATE([Sim Served],dim_strategy[strategy]="forecast")-CALCULATE([Sim Served],dim_strategy[strategy]="history")',"#,0")
    tables.append(container)
    relationships=[]
    for fact in ["fact_zone_hour","forecast_hourly","simulation_hourly"]:
        for dim,key in [("dim_date","date"),("dim_zone","zone_id"),("dim_hour","hour")]:
            relationships.append({"name":fact+"_"+dim,"fromTable":fact,"fromColumn":key,"toTable":dim,"toColumn":key,"crossFilteringBehavior":"oneDirection"})
    relationships.append({"name":"simulation_strategy","fromTable":"simulation_hourly","fromColumn":"strategy","toTable":"dim_strategy","toColumn":"strategy","crossFilteringBehavior":"oneDirection"})
    write(MODEL/"model.bim",{"name":"Taxi","compatibilityLevel":1601,"model":{"culture":"zh-CN","defaultPowerBIDataSourceVersion":"powerBI_V3","tables":tables,"relationships":relationships,"expressions":[{"name":"ProjectRoot","kind":"m","expression":'"'+str(PROJECT).replace('\\','/')+'" meta [IsParameterQuery=true,Type="Text",IsParameterQueryRequired=true]'}],"annotations":[{"name":"__PBI_TimeIntelligenceEnabled","value":"0"}]}})
    write(MODEL/"definition.pbism",{"$schema":"https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json","version":"1.0","settings":{"qnaEnabled":False}})
    (ROOT/"measures.dax").write_text("\n".join(definitions),encoding="utf-8")


def main():
    build_model()
    write(ROOT/"Taxi.pbip",{"$schema":"https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json","version":"1.0","artifacts":[{"report":{"path":"Taxi.Report"}}],"settings":{"enableAutoRecovery":True}})
    write(REPORT/"definition.pbir",{"$schema":"https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json","version":"4.0","datasetReference":{"byPath":{"path":"../Taxi.SemanticModel"}}})
    for folder,kind,identity in [(REPORT,"Report","9ae724ca-d649-4b97-a3db-a6e09c3e221c"),(MODEL,"SemanticModel","72f04e9c-2b93-42d9-b547-90a6d0369cad")]:
        write(folder/".platform",{"$schema":"https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json","metadata":{"type":kind,"displayName":"城市出行运营分析"},"config":{"version":"2.0","logicalId":identity}})
    write(REPORT/"definition/version.json",{"$schema":SCHEMA+"versionMetadata/1.0.0/schema.json","version":"2.0.0"})
    theme={"name":"Taxi_Portfolio","dataColors":["#2563EB","#0D9488","#D97706","#64748B","#8B5CF6"],"background":"#FFFFFF","foreground":"#0F172A","tableAccent":"#2563EB"}
    write(ROOT/"taxi-theme.json",theme)
    write(REPORT/"StaticResources/RegisteredResources/Taxi_Portfolio.json",{**theme,"name":"Taxi_Portfolio.json"})
    write(REPORT/"definition/report.json",{"$schema":SCHEMA+"report/3.3.0/schema.json","themeCollection":{"baseTheme":{"name":"Fluent2-CY26SU09","reportVersionAtImport":{"visual":"2.13.0","report":"3.4.0","page":"2.3.1"},"type":"SharedResources"},"customTheme":{"name":"Taxi_Portfolio.json","reportVersionAtImport":{"visual":"2.13.0","report":"3.4.0","page":"2.3.1"},"type":"RegisteredResources"}},"resourcePackages":[{"name":"SharedResources","type":"SharedResources","items":[{"name":"Fluent2-CY26SU09","path":"BaseThemes/Fluent2-CY26SU09.json","type":"BaseTheme"}]},{"name":"RegisteredResources","type":"RegisteredResources","items":[{"name":"Taxi_Portfolio.json","path":"Taxi_Portfolio.json","type":"CustomTheme"}]}],"settings":{"useStylableVisualContainerHeader":True,"exportDataMode":"AllowSummarized","defaultDrillFilterOtherVisuals":True}})
    ids=[]
    p=page("overview","01 城市出行运营总览","2025全年 Yellow Taxi · 已记录上车量与运营指标 · 金额单位美元、里程公里、时长分钟");ids.append(p)
    for i,(measure,label) in enumerate([("Trips","有效区域上车记录"),("Avg Fare","平均计价车费"),("Avg Duration","平均行程时长 / 分钟"),("Card Tip Rate","银行卡小费率")]):card(p,"kpi_"+str(i),measure,label,(24+i*394,206,376,108))
    visual(p,"monthly","lineChart","月度上车记录趋势",(24,332,748,272),{"Category":[col("dim_date","month_label")],"Y":[met("Trips")]},sort=(col("dim_date","month_label"),"Ascending"))
    visual(p,"hours","clusteredColumnChart","小时需求分布",(788,332,788,272),{"Category":[col("dim_hour","hour_label")],"Y":[met("Trips")]},sort=(col("dim_hour","hour"),"Ascending"))
    visual(p,"weather","clusteredColumnChart","每个日历日平均记录量：历史天气分组",(24,620,748,208),{"Category":[col("dim_date","weather_group")],"Y":[met("Trips")]})
    # Weather chart uses a daily exposure denominator, defined after model build below.
    visual(p,"days","clusteredColumnChart","工作日、周末与节假日：日均上车记录",(788,620,788,208),{"Category":[col("dim_date","day_type")],"Y":[met("Daily Avg Trips")]})
    weather_file=PAGES/p/"visuals/weather/visual.json"
    obj=json.loads(weather_file.read_text(encoding="utf-8"));obj["visual"]["query"]["queryState"]["Y"]["projections"][0].update(field=field(met("Daily Avg Trips")),queryRef="Metrics.Daily Avg Trips",nativeQueryRef="Daily Avg Trips");write(weather_file,obj)
    text(p,"footnote","记录量代表已完成出行的代理，不能直接测量未满足需求。历史天气对比不代表因果效应；机场、外部区域与未知区域有独立口径。",(24,844,1552,40),10)
    p=page("regions","02 区域效率与数据异常","区域热度、有效指标分母与质量标记 · 费用和时长异常分开处理，不由慢速推断真实空驶");ids.append(p)
    for i,(measure,label) in enumerate([("Avg Distance","平均里程 / 公里"),("Avg Speed","平均行程速度 / km/h"),("Flag Rate","有效需求记录标记率"),("Efficiency N","效率指标有效记录数")]):card(p,"kpi_"+str(i),measure,label,(24+i*394,206,376,108))
    shape_map(p,"zone_map","区域上车热度：本地边界文件",(24,332,710,496),"Trips")
    top=pd.read_csv(PROJECT/"reports/tables/zone_metrics.csv").nlargest(12,"trips").zone_label.tolist()
    matrix(p,"regions_table","全年需求前12区域（筛选后指标）",(752,332,824,300),[(*col("dim_zone","zone_label"),"区域")],[("Trips","上车记录"),("Avg Fare","车费"),("Avg Duration","分钟"),("Flag Rate","标记率")])
    path=PAGES/p/"visuals/regions_table/visual.json";obj=json.loads(path.read_text(encoding="utf-8"));obj["filterConfig"]={"filters":[filter_in(col("dim_zone","zone_label"),top)]};write(path,obj)
    matrix(p,"quality_table","全年源记录质量（独立口径）",(752,648,824,180),[(*col("data_quality_monthly","source_month"),"源月份")],[("Raw Rows","源记录"),("Unknown Pickup","未知上车区"),("Negative Amount Rows","负金额")])
    text(p,"footnote","地图可点击联动区域指标。全年源质量表不受区域或月份筛选；金额阈值是质量筛查规则，不代表违规收费。夏令时过渡日排除效率指标。",(24,844,1552,40),10)
    p=page("forecast","03 区域下一小时需求预测","独立测试：2025年12月 · 9/10/11月滚动验证锁定模型 · 预测时仅使用已完成小时的记录与已知日历",test=True);ids.append(p)
    for i,(measure,label) in enumerate([("Selected Model","验证集选定方案"),("Forecast WAPE","所选区域 WAPE"),("Forecast MAE","平均绝对误差 / 次"),("Forecast RMSE","均方根误差 / 次")]):card(p,"kpi_"+str(i),measure,label,(24+i*394,206,376,108))
    visual(p,"trend","lineChart","测试月逐日合计：实际与逐小时预测汇总",(24,332,960,280),{"Category":[col("dim_date","date")],"Y":[(*met("Forecast Actual"),"实际记录"),(*met("Forecast Predicted"),"选定方案预测")]},sort=(col("dim_date","date"),"Ascending"))
    visual(p,"comparison","clusteredBarChart","全区域测试 WAPE：五种方案",(1000,332,576,280),{"Category":[col("test_metrics","model_label")],"Y":[met("Test WAPE")]},sort=(met("Test WAPE"),"Ascending"))
    shape_map(p,"forecast_map","12月各区域预测量",(24,628,710,200),"Forecast Predicted")
    visual(p,"hour_error","clusteredColumnChart","所选区域：小时平均绝对误差",(752,628,824,200),{"Category":[col("dim_hour","hour_label")],"Y":[met("Forecast MAE")]},sort=(col("dim_hour","hour"),"Ascending"))
    text(p,"footnote","区域筛选影响趋势、误差卡片与地图；五方案比较固定展示完整测试集。历史数据只支持离线评估，未证明实时数据到达与上线效果。",(24,844,1552,40),10)
    p=page("dispatch","04 调度名额分配模拟","独立测试：2025年12月 · 固定服务名额的区域分配 · 不含基础运力、车辆位置、空驶与跨区移动时间",test=True);ids.append(p)
    slicer(p,"budget_slicer",col("dim_budget","budget_label"),"每小时模拟名额（默认1,000）",(514,116,500,70),"1,000 名额/小时")
    for i,(measure,label) in enumerate([("Forecast Served","预测方案模拟覆盖记录"),("Forecast Coverage","预测方案模拟覆盖率"),("Forecast Idle","预测方案闲置名额"),("Forecast Advantage","相对历史方案多覆盖记录")]):card(p,"kpi_"+str(i),measure,label,(24+i*394,206,376,108))
    visual(p,"strategies","clusteredColumnChart","相同名额下三种策略的模拟覆盖率",(24,332,748,280),{"Category":[col("dim_strategy","strategy_label")],"Y":[met("Sim Coverage")]})
    visual(p,"daily","lineChart","逐日模拟覆盖：三种名额分配策略",(788,332,788,280),{"Category":[col("dim_date","date")],"Y":[met("Sim Served")],"Series":[col("dim_strategy","strategy_label")]},{"legend":[{"properties":{"show":lit(True)}}]},sort=(col("dim_date","date"),"Ascending"))
    matrix(p,"simulation","所选名额下的离线模拟结果",(24,628,1060,200),[(*col("dim_strategy","strategy_label"),"分配策略")],[("Sim Allocation","名额"),("Sim Served","覆盖"),("Sim Uncovered","未覆盖"),("Sim Idle","闲置")])
    text(p,"limits","每区覆盖=min(实际记录,分配名额)\n按预测或历史权重比例分配\n最大余数法保证整数名额守恒\n\n结果属于假设下的策略模拟。",(1100,636,470,188),13)
    text(p,"footnote","名额均为每小时可服务订单数量，不能换算成真实车辆数。区域筛选只展示全区域既定分配的子集，不在看板里重新分配总名额。",(24,844,1552,40),10)
    write(PAGES/"pages.json",{"$schema":SCHEMA+"pagesMetadata/1.1.0/schema.json","pageOrder":ids,"activePageName":ids[0]})
    report_config=json.loads((REPORT/"definition/report.json").read_text(encoding="utf-8"))
    registered=next(package for package in report_config["resourcePackages"] if package["name"]=="RegisteredResources")
    registered["items"].append({"name":"taxi_zones.geojson","path":"taxi_zones.geojson","type":"ShapeMap"})
    write(REPORT/"definition/report.json",report_config)
    model=json.loads((MODEL/"model.bim").read_text(encoding="utf-8"))
    metric=next(table for table in model["model"]["tables"] if table["name"]=="Metrics")
    metric["measures"].append({"name":"Daily Avg Trips","expression":"DIVIDE([Trips],COUNTROWS(dim_date))","formatString":"#,0","displayFolder":"出行运营"})
    write(MODEL/"model.bim",model)
    with (ROOT/"measures.dax").open("a",encoding="utf-8") as output:output.write("\nDaily Avg Trips = DIVIDE([Trips],COUNTROWS(dim_date))\n")
    print("Created editable PBIP",ROOT/"Taxi.pbip")


if __name__=="__main__":
    main()


