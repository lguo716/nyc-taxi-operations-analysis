# 数据来源、许可与引用

## 行程与区域

NYC Taxi & Limousine Commission，2025年1—12月 Yellow Taxi Trip Records、Taxi Zone Lookup及Taxi Zone边界：[官方入口](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)、[字段字典](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf)、[使用指南](https://www.nyc.gov/assets/tlc/downloads/pdf/trip_record_user_guide.pdf)。TLC说明数据由技术提供方提供，不保证准确性。本项目未将公开数据另行声明为CC0或MIT；使用与再发布应保留官方来源和适用条款。

下载日期2026-10-08，来源身份见data/source_manifest.json。TLC没有发布预期SHA256，本项目记录本地计算SHA256、字节数、字段、元数据行数，并完成全文件扫描核对。同名文件可能由发布方更新，不能把不同哈希当作同一版本。

## 天气

日度天气由[Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)提供，选择ERA5模型，纽约代表点40.7812,-73.9665，2025全年，America/New_York本地日期。天气是再分析而非当时发布的预测，仅用于描述性分析。数据按[CC BY 4.0及Open-Meteo使用条款](https://open-meteo.com/en/terms)使用，归属Open-Meteo及其ERA5上游数据提供者；本项目用于非商业数据分析与方法复现。

## 日历、地图与工具

联邦节假日来自[OPM 2025日历](https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/#url=2025)，不声称覆盖纽约学校、州、市或私人机构的全部休假。Taxi Zone边界从EPSG:2263转换为EPSG:4326，按LocationID合并并轻量简化，保留来源和处理参数。

Power BI原生Shape Map支持自定义GeoJSON，参见[Microsoft说明](https://learn.microsoft.com/en-us/power-bi/visuals/power-bi-shape-map)。Microsoft基础主题与报告工具由已安装官方工具提供，Microsoft及依赖许可证仍适用于相应资产。自写代码采用MIT（LICENSE），不覆盖第三方数据、字体或主题。
