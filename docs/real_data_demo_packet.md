# Real-Data Demo Packet

The POC includes one anonymized, real-data-style CSV packet:

```text
institutional_liquidity_stress
```

It backs the **Institutional CSV Liquidity Stress** demo preset and replaces the
simulated data generators for all three steps in the liquidity stress workflow.

## Files

```text
examples/data/institutional_liquidity_stress/
├── financing_counterparties.csv
├── financing_needs.csv
├── collateral_assets.csv
├── collateral_obligations.csv
├── mmf_universe.csv
└── cash_position.csv
```

The packet manifest lives at:

```text
config/data_packets/institutional_liquidity_stress.yaml
```

The runnable demo preset lives at:

```text
config/demo_presets/institutional_csv_liquidity_stress.yaml
```

## What It Proves

- Financing, collateral, and money-market optimizers can load CSV inputs through
  the same data-provider layer.
- The sequential workflow contract is unchanged when moving from simulated data
  to CSV-backed inputs.
- The final money-market step can use true MILP fund selection against a CSV fund
  universe.
- The browser demo can surface the data packet, workflow dependencies,
  validation, and explanation in one recording path.

## Run It

Terminal:

```bash
make demo-video
```

Browser:

```bash
make demo-ui
```

Then select **Institutional CSV Liquidity Stress** or click **Load POC Path**.

API catalog endpoint:

```bash
curl http://127.0.0.1:8000/api/demo-data-packets
```
