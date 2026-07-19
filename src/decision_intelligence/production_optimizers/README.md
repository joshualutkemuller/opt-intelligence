# Production Optimizer Adapters

This package is the intentionally identifiable home for integrating
firm-developed production optimizers.

Current scaffold:

- `adapter.py` defines the formal optimizer adapter lifecycle:
  `validate_inputs`, `build_problem`, `solve`, `explain_outputs`, and
  `serialize_evidence`.
- `adapters/asset_allocation` wraps the current Asset Allocation MVO optimizer
  behind the production adapter lifecycle.
- `adapters/collateral` wraps the current Collateral optimizer behind the
  production adapter lifecycle.
- `adapters/money_market` wraps the current Money Market optimizer behind the
  production adapter lifecycle.
- `adapters/cash_movement` provides a treasury operations scaffold for routing
  cash movements across accounts and payment rails.
- `adapters/margin_call` provides a margin operations scaffold for prioritizing
  margin-call workflow actions inside team capacity.
- `contracts.py` defines richer model configuration, data contracts, execution
  isolation, preflight, normalized result, and evidence contracts.
- `execution.py` defines the execution-isolation boundary for in-process,
  subprocess, REST/gRPC, batch, and containerized optimizers.
- `registry.py` defines a registry for production adapters.

This scaffold does not replace the current POC optimizers. It gives production
models a stable integration target that can later be bridged into the existing
`OptimizationOrchestrator`, workflow registry, governance, and evidence exports.
