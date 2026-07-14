# Repository Bootstrap Plan
## Agentic Optimization Platform

## 1. Objective

Create a single repository that can initially serve as:

- The architecture and handoff source of truth
- The home for common framework interfaces
- The registry for domain optimizers
- The future implementation repository for agents, optimization services, forecasting models, APIs, governance, and deployment assets

The first milestone is not to build production logic. It is to establish a clean, extensible structure with starter contracts, placeholder packages, configuration files, and tests.

---

## 2. Recommended Repository Name

```text
decision-intelligence-platform
```

Alternative:

```text
agentic-optimization-platform
```

---

## 3. Initial Repository Structure

```text
decision-intelligence-platform/
├── README.md
├── pyproject.toml
├── .gitignore
├── .env.example
├── Makefile
├── LICENSE
│
├── docs/
│   ├── architecture.md
│   ├── product_scope.md
│   ├── roadmap.md
│   ├── governance.md
│   └── glossary.md
│
├── src/
│   └── decision_intelligence/
│       ├── __init__.py
│       │
│       ├── contracts/
│       │   ├── __init__.py
│       │   ├── requests.py
│       │   ├── results.py
│       │   ├── objectives.py
│       │   ├── constraints.py
│       │   └── scenarios.py
│       │
│       ├── orchestrator/
│       │   ├── __init__.py
│       │   ├── service.py
│       │   ├── router.py
│       │   ├── registry.py
│       │   └── state_machine.py
│       │
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── intent_agent.py
│       │   ├── planning_agent.py
│       │   ├── constraint_agent.py
│       │   ├── validation_agent.py
│       │   └── explanation_agent.py
│       │
│       ├── optimization/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── solver.py
│       │   ├── validation.py
│       │   └── explanation.py
│       │
│       ├── optimizers/
│       │   ├── __init__.py
│       │   ├── collateral/
│       │   │   ├── __init__.py
│       │   │   ├── optimizer.py
│       │   │   ├── model.py
│       │   │   ├── constraints.py
│       │   │   └── objective.py
│       │   ├── money_market/
│       │   │   ├── __init__.py
│       │   │   ├── optimizer.py
│       │   │   ├── model.py
│       │   │   ├── constraints.py
│       │   │   └── objective.py
│       │   └── financing/
│       │       ├── __init__.py
│       │       ├── optimizer.py
│       │       ├── model.py
│       │       ├── constraints.py
│       │       └── objective.py
│       │
│       ├── forecasting/
│       │   ├── __init__.py
│       │   ├── recall.py
│       │   ├── liquidity.py
│       │   ├── rates.py
│       │   └── demand.py
│       │
│       ├── data/
│       │   ├── __init__.py
│       │   ├── interfaces.py
│       │   ├── adapters.py
│       │   ├── lineage.py
│       │   └── quality.py
│       │
│       ├── governance/
│       │   ├── __init__.py
│       │   ├── approvals.py
│       │   ├── audit.py
│       │   ├── policies.py
│       │   └── permissions.py
│       │
│       └── api/
│           ├── __init__.py
│           ├── app.py
│           ├── routes.py
│           └── schemas.py
│
├── configs/
│   ├── local.yaml
│   ├── test.yaml
│   └── optimizer_registry.yaml
│
├── examples/
│   ├── collateral_request.json
│   ├── money_market_request.json
│   └── financing_request.json
│
├── tests/
│   ├── unit/
│   │   ├── test_contracts.py
│   │   ├── test_registry.py
│   │   └── test_router.py
│   ├── integration/
│   │   └── test_orchestrator_flow.py
│   └── fixtures/
│       └── sample_requests.py
│
├── scripts/
│   ├── bootstrap_repo.py
│   ├── validate_config.py
│   └── run_local.py
│
└── deployment/
    ├── docker/
    │   └── Dockerfile
    ├── databricks/
    │   └── README.md
    └── github_actions/
        └── ci.yml
```

---

## 4. Minimum Starter Files

The first commit should contain working placeholders for the following files.

### `src/decision_intelligence/optimization/base.py`

Define the common optimizer interface:

```python
from abc import ABC, abstractmethod
from typing import Any


class OptimizationCapability(ABC):
    name: str
    version: str

    @abstractmethod
    def validate_request(self, request: Any) -> None:
        pass

    @abstractmethod
    def prepare_problem(self, request: Any, context: Any) -> Any:
        pass

    @abstractmethod
    def solve(self, problem: Any) -> Any:
        pass

    @abstractmethod
    def validate_solution(self, problem: Any, solution: Any) -> Any:
        pass

    @abstractmethod
    def explain(self, problem: Any, solution: Any) -> Any:
        pass
```

### `src/decision_intelligence/orchestrator/registry.py`

Create a simple capability registry:

```python
class OptimizerRegistry:
    def __init__(self) -> None:
        self._optimizers = {}

    def register(self, name: str, optimizer: object) -> None:
        if name in self._optimizers:
            raise ValueError(f"Optimizer already registered: {name}")
        self._optimizers[name] = optimizer

    def get(self, name: str) -> object:
        if name not in self._optimizers:
            raise KeyError(f"Unknown optimizer: {name}")
        return self._optimizers[name]

    def list_capabilities(self) -> list[str]:
        return sorted(self._optimizers)
```

### `src/decision_intelligence/contracts/requests.py`

Start with a typed request model:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OptimizationRequest:
    request_id: str
    domain: str
    portfolio_id: str
    objective: dict[str, Any]
    constraints: list[dict[str, Any]] = field(default_factory=list)
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    execution_mode: str = "recommendation_only"
```

### Domain optimizer placeholders

Each domain optimizer should:

- Inherit from `OptimizationCapability`
- Expose `name` and `version`
- Raise `NotImplementedError` for unbuilt methods
- Include a module docstring describing the intended optimization problem

---

## 5. Build Sequence

### Step 1: Initialize the repository

```bash
mkdir decision-intelligence-platform
cd decision-intelligence-platform
git init
```

Create the top-level folders and starter files.

### Step 2: Configure Python packaging

Use a `src/` layout and define dependencies in `pyproject.toml`.

Initial development dependencies:

```text
pytest
pytest-cov
ruff
mypy
pydantic
pyyaml
```

Avoid adding solver, LLM, Databricks, or cloud dependencies until the interfaces are stable.

### Step 3: Build the common contracts

Implement:

- `OptimizationRequest`
- `OptimizationResult`
- `Objective`
- `Constraint`
- `Scenario`
- `ValidationResult`

These should be domain-neutral.

### Step 4: Build the optimizer interface and registry

Implement:

- `OptimizationCapability`
- `OptimizerRegistry`
- Simple domain router
- Duplicate-registration protection
- Unknown-capability errors

### Step 5: Add three placeholder domain optimizers

Register:

- `CollateralOptimizer`
- `MoneyMarketOptimizer`
- `FinancingOptimizer`

Do not build optimization math yet. Confirm only that they can be registered, selected, and invoked through a shared interface.

### Step 6: Build a deterministic orchestrator skeleton

The first orchestrator should:

1. Accept an `OptimizationRequest`
2. Read the request domain
3. Retrieve the correct optimizer
4. Validate the request
5. Call the optimizer
6. Return a structured placeholder result

Do not add an LLM in this phase.

### Step 7: Add examples and tests

Create one JSON request per domain.

Tests should confirm:

- Contracts can be instantiated
- Optimizers can be registered
- The router selects the correct optimizer
- Invalid domains fail clearly
- The orchestrator returns a structured result

### Step 8: Add CI

The first CI workflow should run:

```bash
ruff check .
mypy src
pytest --cov=decision_intelligence
```

---

## 6. First Milestone Definition of Done

The repository bootstrap is complete when:

- The package installs locally
- All imports resolve
- Three optimizer placeholders are registered
- The orchestrator can route one request to each optimizer
- Example requests exist for all three domains
- Unit tests pass
- CI passes
- The README explains how to install and run the starter application
- No business logic, credentials, or production data are embedded in the repository

---

## 7. Recommended First Pull Requests

### PR 1 — Repository Foundation

- Folder structure
- `pyproject.toml`
- README
- linting and testing configuration
- CI workflow

### PR 2 — Shared Contracts

- Request and result models
- Objective, constraint, and scenario models
- Contract tests

### PR 3 — Optimization Framework

- Base optimizer interface
- Registry
- Router
- Registry tests

### PR 4 — Domain Placeholders

- Collateral optimizer
- Money-market optimizer
- Financing optimizer
- Example requests

### PR 5 — Orchestrator Skeleton

- Deterministic orchestration service
- End-to-end placeholder workflow
- Integration test

---

## 8. What Not to Build Yet

Defer the following until the repository foundation is stable:

- Multi-agent workflows
- LLM prompt chains
- Autonomous execution
- Joint optimization
- Production solver integrations
- Databricks jobs
- Event streaming
- Persistent memory
- Regulatory-document extraction
- Full user interface

The initial repository should prove the architecture and interfaces, not the end-state platform.

---

## 9. Immediate Next Milestone

After the bootstrap is accepted, implement one thin vertical slice:

```text
Sample Collateral Request
        ↓
Deterministic Orchestrator
        ↓
Collateral Optimizer Adapter
        ↓
Toy Linear Optimization Model
        ↓
Validation
        ↓
Structured Result
```

This validates the framework using a real optimization problem before introducing AI agents or additional infrastructure.
