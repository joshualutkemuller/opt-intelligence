# IPS Ingestion Demo Packet

This packet demonstrates an Investment Policy Statement (IPS) or policy text
being ingested, interpreted, and converted into workflow-ready optimization
inputs.

The default demo is deterministic and does not require an LLM. The same
contract also supports an LLM-assisted mode for messier policy language. In both
modes, the output is validated by deterministic code before it becomes a
workflow context patch.

## What It Proves

- A nontechnical policy statement can populate optimizer and workflow inputs.
- Extracted values are reviewable before they are applied.
- Evidence snippets are returned with each extracted field.
- The same contract supports text input today and base64 PDF input when the
  optional PDF dependency is installed.
- The workflow context patch can be merged into registered workflows before a
  governed optimization run.

## Demo Files

```text
examples/policies/sample_mvo_ips.txt
examples/policies/sample_liquidity_ips.txt
examples/policies/sample_collateral_policy.txt
examples/policies/sample_full_ips.pdf
examples/run_ips_ingestion_demo.py
examples/run_ollama_ips_ingestion_demo.py
```

## Primary Story: MVO IPS to Workflow Inputs

Use this sample for a portfolio construction demo:

```text
examples/policies/sample_mvo_ips.txt
```

It includes the following policy language:

```text
The portfolio value is $250 million. The objective is to construct a diversified
multi-asset allocation with a target annual return of 5.25%. Risk aversion
lambda is 3.5 for the current review cycle.

Single asset class exposure must not exceed 40%. Cash floor must be at least
3% of portfolio value to preserve operating liquidity.

Governance: Materiality notional is $250 million. This review is a production constraint change because the approved concentration limit is being revised.
```

The ingestion response maps that language into:

| Extracted input | Interpreted value |
|---|---:|
| `portfolio_id` | `PORT_MVO_900` |
| `asset_allocation.portfolio_notional` | `250000000` |
| `asset_allocation.target_return` | `0.0525` |
| `asset_allocation.risk_aversion` | `3.5` |
| `asset_allocation.max_single_asset_weight` | `0.40` |
| `asset_allocation.min_cash_weight` | `0.03` |
| `governance.materiality_notional` | `250000000` |
| `governance.production_constraint_change` | `true` |

## Terminal Demo

Run the bundled MVO sample:

```bash
python examples/run_ips_ingestion_demo.py
```

Run all bundled samples:

```bash
python examples/run_ips_ingestion_demo.py --all
```

Print raw JSON:

```bash
python examples/run_ips_ingestion_demo.py --all --json
```

Run a specific sample:

```bash
python examples/run_ips_ingestion_demo.py \
  --workflow liquidity_stress_funding_workflow \
  examples/policies/sample_liquidity_ips.txt
```

Run the full sample PDF with local Ollama as the LLM-assisted extractor:

```bash
ollama serve
ollama pull llama3.1:8b
python examples/run_ollama_ips_ingestion_demo.py \
  --model llama3.1:8b \
  --pdf examples/policies/sample_full_ips.pdf
```

Ollama proposes the extracted fields. The IPS ingestion layer still filters
unsupported keys, coerces percentages/currencies, rejects impossible values, and
marks the response with `backend: llm`.

## API Demo

Start the local API:

```bash
make api
```

Then call the ingestion endpoint:

```bash
curl -X POST http://127.0.0.1:8000/api/policy/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "portfolio_rebalance_mvo",
    "backend": "deterministic",
    "filename": "sample_mvo_ips.txt",
    "text": "Portfolio PORT_MVO_900 has portfolio notional $250 million. Target annual return should be 5.25%. Risk aversion lambda is 3.5. Single asset exposure must not exceed 40%. Cash floor at least 3%. Materiality notional $250 million. This is a production constraint change."
  }'
```

LLM-assisted Ollama API call:

```bash
curl -X POST http://127.0.0.1:8000/api/policy/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "portfolio_rebalance_mvo",
    "backend": "llm",
    "provider": "openai",
    "model": "llama3.1:8b",
    "base_url": "http://localhost:11434/v1",
    "api_key": "not-needed",
    "filename": "sample_full_ips.pdf",
    "pdf_base64": "<base64-encoded PDF>"
  }'
```

Expected response shape:

```json
{
  "workflow_id": "portfolio_rebalance_mvo",
  "source_type": "text",
  "input_values": {
    "portfolio_id": "PORT_MVO_900",
    "asset_allocation.target_return": "0.0525"
  },
  "context_patch": {
    "asset_allocation": {
      "target_return": 0.0525
    },
    "policy_ingestion": {
      "filename": "sample_mvo_ips.txt",
      "source_type": "text",
      "backend": "deterministic"
    }
  },
  "extracted_fields": [],
  "review_summary": {
    "ready": true,
    "backend": "deterministic",
    "missing_required": []
  }
}
```

The live response includes all extracted fields, evidence snippets, confidence
scores, and the complete context patch.

Note: the deterministic parser expects key phrases and numeric values to remain
in the same sentence. For clean demos, avoid inserting line breaks between a
constraint phrase and its value.

## Extraction Modes

| Mode | What interprets the IPS? | What validates the result? | Best use |
|---|---|---|---|
| `deterministic` | Regex/rule extraction | Deterministic validator | Repeatable demos and known policy templates |
| `llm` | Configured `LLMProvider` such as local Ollama | Deterministic validator | Messier policy wording |
| `auto` | LLM if configured, otherwise deterministic | Deterministic validator | Environment-driven demos |

For local Ollama, use the OpenAI-compatible provider configuration:

```bash
export DI_LLM_PROVIDER=openai
export DI_LLM_MODEL=llama3.1:8b
export DI_LLM_BASE_URL=http://localhost:11434/v1
export DI_LLM_API_KEY=not-needed
```

## Browser Demo Talk Track

Use this as the presenter narrative until the frontend upload affordance is
wired directly to `/api/policy/ingest`.

1. Open the workflow selector and choose **Balanced MVO Rebalance**.
2. Say: "Instead of typing these constraints manually, I can ingest the IPS."
3. Show `examples/policies/sample_mvo_ips.txt`.
4. Run the terminal or API ingestion command.
5. Point to the extracted field table and evidence snippets.
6. Say: "These values become the workflow context patch, but they are still
   reviewable before the optimization runs."
7. Copy the interpreted values into the UI preset fields if presenting live.
8. Run the workflow and point to governance tiering caused by the production
   constraint change.

## Supported Workflow IDs

The current deterministic extraction map supports:

```text
portfolio_rebalance_mvo
liquidity_stress_funding_workflow
funding_capacity_shock
collateral_liquidity_review
```

## Next UI Enhancement

The highest-value follow-on is to wire an **Ingest IPS** panel in the browser:

- text area and optional file picker
- workflow selector
- extraction mode selector: deterministic, auto, or local Ollama
- extracted field review table
- apply/reject toggles per field
- one-click "Apply to workflow inputs"
- evidence saved into the run package
