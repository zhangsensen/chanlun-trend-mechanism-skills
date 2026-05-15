# Data Schema

The bundled scripts expect local parquet files arranged by timeframe:

```text
data/index/derived/
  5m/SYMBOL.parquet
  15m/SYMBOL.parquet
  30m/SYMBOL.parquet
  60m/SYMBOL.parquet
  120m/SYMBOL.parquet
  1d/SYMBOL.parquet
  2d/SYMBOL.parquet
  1w/SYMBOL.parquet
  2w/SYMBOL.parquet
```

Required columns:

- `close`
- one timestamp column: `datetime`, `trade_date`, or `period_end`
- `ma20` or `mid`
- `ma55`

Optional columns:

- `ma233`
- `macd_dif`, `macd_dea`, `macd_hist`
- `ts_code`, `open`, `high`, `low`, `volume`, `amount`

Timestamp policy:

- Minute bars use `datetime`.
- Daily or higher bars may use `trade_date`; the analyzer treats date-only rows as 15:00 closed bars.
- The analyzer selects the latest row whose timestamp is less than or equal to `--as-of`.

MACD policy:

- Use fixed 12/26/9 parameters.
- `macd_hist = macd_dif - macd_dea`.
- MACD is auxiliary context only; it must not change background, operating level, support ladder, or structure clarity.
