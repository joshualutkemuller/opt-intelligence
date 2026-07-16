# Front-End Prototype

Static browser prototype for the Decision Intelligence guided chat demo.

For the newer React/Vite demo app, use:

```text
frontend/app/README.md
```

Start the Python API:

```bash
cd "/Users/joshualutkemuller/Documents/Quant Sandbox/opt-intelligence"
source .venv/bin/activate
uvicorn decision_intelligence.api.app:app --reload
```

Then open:

```text
frontend/prototype/index.html
```

The page connects to `http://127.0.0.1:8000` and uses the real
`ChatSession -> OptimizationRequest -> Orchestrator -> Optimizer` flow. If the
API is not running, it falls back to static mock mode.

Demo flow:

```text
I want to optimize money market cash
PORT_204
$500 million
30%
60%
40%
60
50%
4
5%
scipy
lp
stress
yes
```

Included interactions:

- guided chat field collection
- request summary sidebar
- solver selector
- PDF sample parse preview
- optimization result dashboard
- allocation and sensitivity tables
- JSON export mock

This static prototype is kept as a lightweight fallback. The maintainable
React/TypeScript demo now lives in `frontend/app`.
