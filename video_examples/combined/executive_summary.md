# Executive Summary: Agentic Optimization Demo Reel

## Short Description

This demo presents a Decision Intelligence platform for financial optimization workflows. It shows how a user can move from business intent and document ingestion into governed optimizer execution, explanation, analytics, and evidence review inside a nontechnical front-end experience.

The combined video includes two examples:

- **Example #1: Collateral Management**: collateral schedule ingestion, bilateral/CCP/exchange obligation review, HQLA and liquidity analytics, optimizer orchestration, local LLM explanation, and governance evidence.
- **Example #2: Money Market Optimization**: money-market policy PDF upload, structured policy extraction, local LLM discussion, constrained fund allocation, before/after analytics, and traceable evidence.
- **Example #3: Storyboard of Operational Use-Cases**: Treasury cash movement and Margin Call workflows.  High-level proof of concept that shows cash moved, transfers, assigned margin, capacity, binding checks, and evidence metadata

## AI Platform And Tooling Used

The prototype was developed with **RAI Gateway/Anthrophic Models & Ollama** as the AI-assisted engineering environment for code generation, documentation, test iteration, video-generation scripting, and product design refinement.

The demo application also supports **local Ollama models**, including `llama3.1:8b`, for offline LLM-assisted explanation and document interpretation. The LLM layer is intentionally separated from the deterministic optimization layer: the model can help interpret documents, guide users, and explain outputs, while mathematical recommendations remain produced by governed optimizer code.

Core implementation components include:

- React/Vite front-end demo workspace
- FastAPI Python backend
- Deterministic optimization engines for collateral, money-market, and asset-allocation workflows
- Workflow orchestration, validation, explanation, approval, and evidence layers
- Playwright-driven browser recordings for real front-end video examples
- FFmpeg/Pillow-based video composition for presentation-ready MP4 outputs

## How The Idea Was Developed

The idea evolved from a simple command-line proof of concept into a broader agentic optimization platform. Early work focused on deterministic optimizer runs and CLI chat workflows. The project then expanded into a front-end demo environment for nontechnical users, with guided chat, workflow selection, optimizer configuration, plan progress, trace events, validation summaries, governance review, and evidence export.

The development path emphasized a production-minded separation of concerns:

- AI agents interpret intent, guide workflows, explain results, and support document ingestion.
- Optimizers remain deterministic, testable, and auditable.
- Workflow orchestration connects multiple optimizers in sequence.
- Governance controls track approval thresholds, materiality, model metadata, and reproducibility evidence.
- The UI turns terminal-based demos into a boardroom-ready experience.

The combined video was created to make that evolution tangible: it shows the same platform handling two different market workflows while preserving a common operating model.

## What Problem Or Opportunity Does It Address?

Financial institutions often have strong quantitative models but weak user-facing orchestration around them. Optimizers may live in separate codebases, require technical users, lack consistent evidence trails, or be difficult to explain to business stakeholders, risk teams, and governance reviewers.

This platform addresses that gap by creating a reusable layer around production optimizers. The opportunity is to turn specialized quantitative tools into accessible, governed decision workflows that can be reused across domains.

The platform is designed to help teams:

- Reduce friction between business users and quantitative optimization models.
- Convert policy documents, schedules, limits, and scenario assumptions into structured optimizer inputs.
- Compare before/after analytics in a way that nontechnical stakeholders can understand.
- Preserve deterministic, reproducible optimizer behavior while using AI for guidance and explanation.
- Standardize evidence, validation, approvals, and model lineage across optimization domains.
- Accelerate development of new optimizer demos without rebuilding the entire workflow stack each time.

## Why It Stands Out

The key differentiator is not a chatbot bolted onto an optimizer. It is an agentic workflow layer that surrounds deterministic optimization with intent capture, document ingestion, orchestration, validation, explanation, governance, and presentation-ready evidence.

That makes the concept useful both as a compelling proof of concept and as a credible foundation for production integration with firm-developed optimizers.
