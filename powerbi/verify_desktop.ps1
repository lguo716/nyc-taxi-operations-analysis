param([Parameter(Mandatory=$true)][int]$DesktopPid)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$engine = @(Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe'" | Where-Object { $_.ParentProcessId -eq $DesktopPid })
if ($engine.Count -ne 1) { throw 'Expected one analysis engine for the verified Taxi Desktop PID.' }
$match = [regex]::Match($engine[0].CommandLine, '-s "([^"]+)"')
if (-not $match.Success) { throw 'No analysis workspace returned.' }
$port = [int]([System.IO.File]::ReadAllText((Join-Path $match.Groups[1].Value 'msmdsrv.port.txt'),[System.Text.Encoding]::Unicode).Trim())
Add-Type -Path 'D:\ATools\bin\Microsoft.PowerBI.Amo.Core.dll'
Add-Type -Path 'D:\ATools\bin\Microsoft.PowerBI.Tabular.dll'
Add-Type -Path 'D:\ATools\bin\Microsoft.PowerBI.AdomdClient.dll'
$server = New-Object Microsoft.AnalysisServices.Tabular.Server
$server.Connect("localhost:$port")
try {
    if ($server.Databases.Count -ne 1) { throw 'Expected one database.' }
    $database = $server.Databases[0]
    if ($null -eq $database.Model.Tables.Find('fact_zone_hour') -or $null -eq $database.Model.Tables.Find('simulation_hourly')) { throw 'Endpoint is not Taxi project.' }
    $connection = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
    $connection.Open()
    $queries = [ordered]@{
        annual = 'EVALUATE ROW("trips",[Trips],"fare_n",[Fare N],"fare",[Avg Fare],"charge",[Total Charge],"duration",[Avg Duration],"speed",[Avg Speed],"tip_rate",[Card Tip Rate],"raw",[Raw Rows],"unknown",[Unknown Pickup])'
        january = 'EVALUATE CALCULATETABLE(ROW("trips",[Trips],"fare",[Avg Fare],"tip_rate",[Card Tip Rate]),dim_date[month_label]="2025-01")'
        zone161 = 'EVALUATE CALCULATETABLE(ROW("trips",[Trips],"fare",[Avg Fare],"wape",[Forecast WAPE]),dim_zone[zone_id]=161)'
        forecast = 'EVALUATE ROW("actual",[Forecast Actual],"predicted",[Forecast Predicted],"wape",[Forecast WAPE],"mae",[Forecast MAE],"rmse",[Forecast RMSE],"model",[Selected Model])'
        budget500 = 'EVALUATE CALCULATETABLE(ROW("budget",[Selected Budget],"served",[Forecast Served],"coverage",[Forecast Coverage],"idle",[Forecast Idle],"advantage",[Forecast Advantage]),dim_budget[budget]=500)'
        budget1000 = 'EVALUATE CALCULATETABLE(ROW("budget",[Selected Budget],"served",[Forecast Served],"coverage",[Forecast Coverage],"idle",[Forecast Idle],"advantage",[Forecast Advantage]),dim_budget[budget]=1000)'
        budget2000 = 'EVALUATE CALCULATETABLE(ROW("budget",[Selected Budget],"served",[Forecast Served],"coverage",[Forecast Coverage],"idle",[Forecast Idle],"advantage",[Forecast Advantage]),dim_budget[budget]=2000)'
        counts = 'EVALUATE ROW("zones",COUNTROWS(dim_zone),"dates",COUNTROWS(dim_date),"hours",COUNTROWS(dim_hour),"forecast_rows",COUNTROWS(forecast_hourly),"simulation_rows",COUNTROWS(simulation_hourly))'
    }
    $results = [ordered]@{}
    foreach ($entry in $queries.GetEnumerator()) {
        $command = $connection.CreateCommand(); $command.CommandText = $entry.Value
        $reader = $command.ExecuteReader(); $rows = @()
        while ($reader.Read()) {
            $row = [ordered]@{}
            for ($i=0; $i -lt $reader.FieldCount; $i++) { $row[$reader.GetName($i)] = if ($reader.IsDBNull($i)) { $null } else { $reader.GetValue($i) } }
            $rows += [pscustomobject]$row
        }
        $reader.Close(); $results[$entry.Key] = $rows
    }
    $connection.Close()
    $checks = @()
    function Number($value) { [double]::Parse($value,[System.Globalization.CultureInfo]::InvariantCulture) }
    function Compare-Number($group,$field,$expected) {
        $actual = $results[$group][0].PSObject.Properties["[$field]"].Value
        $tolerance = [Math]::Max(0.0000001,[Math]::Abs([double]$expected)*0.0000000001)
        $passed = $null -ne $actual -and [Math]::Abs([double]$actual-[double]$expected) -le $tolerance
        $script:checks += [pscustomobject]@{check="$group.$field";passed=$passed;actual=$actual;expected=$expected;tolerance=$tolerance}
    }
    $kpi = Import-Csv -LiteralPath (Join-Path $projectRoot 'reports/tables/kpi_summary.csv')
    foreach ($mapping in @(@('trips','trips'),@('fare_n','fare_n'),@('fare','avg_fare'),@('charge','total_charge_sum'),@('duration','avg_duration_min'),@('speed','avg_speed_kmh'),@('tip_rate','tip_rate'))) { Compare-Number 'annual' $mapping[0] (Number $kpi.($mapping[1])) }
    $quality = Import-Csv -LiteralPath (Join-Path $projectRoot 'reports/tables/data_quality_monthly.csv')
    Compare-Number 'annual' 'raw' (($quality | ForEach-Object { Number $_.raw_rows } | Measure-Object -Sum).Sum)
    Compare-Number 'annual' 'unknown' (($quality | ForEach-Object { Number $_.unknown_pickup } | Measure-Object -Sum).Sum)
    $january = Import-Csv -LiteralPath (Join-Path $projectRoot 'reports/tables/monthly_metrics.csv') | Where-Object month_label -eq '2025-01'
    Compare-Number 'january' 'trips' (Number $january.trips); Compare-Number 'january' 'fare' (Number $january.avg_fare); Compare-Number 'january' 'tip_rate' (Number $january.tip_rate)
    $zone = Import-Csv -LiteralPath (Join-Path $projectRoot 'reports/tables/zone_metrics.csv') | Where-Object zone_id -eq '161'
    Compare-Number 'zone161' 'trips' (Number $zone.trips); Compare-Number 'zone161' 'fare' (Number $zone.avg_fare)
    $selection = Get-Content -LiteralPath (Join-Path $projectRoot 'models/model_selection.json') -Raw | ConvertFrom-Json
    $test = Import-Csv -LiteralPath (Join-Path $projectRoot 'reports/tables/test_metrics.csv') | Where-Object selected -eq '1'
    foreach ($mapping in @(@('actual','actual_sum'),@('predicted','prediction_sum'),@('wape','wape'),@('mae','mae'),@('rmse','rmse'))) { Compare-Number 'forecast' $mapping[0] (Number $test.($mapping[1])) }
    $checks += [pscustomobject]@{check='forecast.model';passed=($results.forecast[0].'[model]' -eq $selection.selected_label);actual=$results.forecast[0].'[model]';expected=$selection.selected_label}
    $summary = Import-Csv -LiteralPath (Join-Path $projectRoot 'reports/tables/simulation_summary.csv')
    foreach ($budget in @(500,1000,2000)) {
        $forecast = $summary | Where-Object { $_.budget -eq "$budget" -and $_.strategy -eq 'forecast' }
        $history = $summary | Where-Object { $_.budget -eq "$budget" -and $_.strategy -eq 'history' }
        Compare-Number "budget$budget" 'budget' $budget
        foreach ($field in @('served','coverage','idle')) { Compare-Number "budget$budget" $field (Number $forecast.$field) }
        Compare-Number "budget$budget" 'advantage' ((Number $forecast.served)-(Number $history.served))
    }
    Compare-Number 'counts' 'zones' 265; Compare-Number 'counts' 'dates' 365; Compare-Number 'counts' 'hours' 24; Compare-Number 'counts' 'forecast_rows' (Number $test.n)
    $passed = @($checks | Where-Object { -not $_.passed }).Count -eq 0
    [ordered]@{pid=$DesktopPid;verified_at=(Get-Date).ToUniversalTime().ToString('o');passed=$passed;checks=$checks;results=$results} | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'desktop_verification.json') -Encoding utf8
    Write-Output "Desktop DAX checks: $(@($checks | Where-Object passed).Count)/$($checks.Count)"
    if (-not $passed) { throw 'DAX differs from pipeline output; see desktop_verification.json' }
} finally { $server.Disconnect() }
