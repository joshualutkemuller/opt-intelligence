# Front-End Prototype

Static browser prototype for the Decision Intelligence guided chat demo.

Open:

```text
frontend/prototype/index.html
```

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

This prototype is static and uses mocked browser data. The next build step is
to connect it to the FastAPI wrapper described in
`docs/features/FrontEnd_UI_PlanHandoff.md`.
