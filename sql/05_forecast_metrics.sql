-- prediction table is loaded from data/processed/test_predictions.parquet by src.verify.
SELECT count(*) AS n,sum(y) AS actual_sum,
 sum(abs(selected_prediction-y))/nullif(sum(y),0) AS wape,
 avg(abs(selected_prediction-y)) AS mae,
 sqrt(avg(pow(selected_prediction-y,2))) AS rmse FROM predictions;
