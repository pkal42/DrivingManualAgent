# Copilot Instructions for DrivingManualAgent

This guide provides essential instructions and best practices  for the DrivingManualAgent repository. It summarizes core structure, infrastructure, and workflow conventions.

---

## 1. Overview & Repository Structure

- Python project structure:
  - `src/agent/` — Agent Framework v2 implementation (multimodal RAG expert agent)
  - `src/indexing/` — Azure AI Search indexer pipeline code
  - `tests/` — Unit and integration tests
  - `infra/bicep/` — Modular Bicep IaC templates
  - `data/manuals/` — Sample driving manual PDFs for testing
  - `.github/workflows/` — CI/CD and agent workflows
  - `config/` — Hierarchical configuration profiles
  - `docs/` — Architecture, configuration guides, workflow docs
  - `scripts/` — Automation/rollback scripts

---

## 2. Infrastructure as Code (IaC) — Bicep Templates

- **All Bicep templates MUST** contain comprehensive **inline comments**:
  - Azure resource purpose
  - Parameter choices and trade-offs
  - Security configuration and managed identities (no keys/secrets)
  - Network and RBAC settings (least privilege)
- Required modules:
  - `main.bicep`: Orchestrates modules, env parameters
  - `modules/foundry-project.bicep`: AI Foundry project setup
  - `modules/model-deployments.bicep`: Model deployments (gpt-4o, text-embedding-3-large, etc.)
  - `modules/ai-search.bicep`: Azure AI Search w/ semantic and vector configs
  - `modules/storage.bicep`: Data Lake Gen2, blob containers for PDFs & extracted images
  - `modules/role-assignments.bicep`: RBAC (Scoped Contributor roles)
  - Search skillset/indexer/data source modules
  - Example param files (`parameters/dev.bicepparam`, `parameters/prod.bicepparam`)

---

## 3. Configuration Management

- **config/base-config.json**: Main configuration (detailed comments for every section)
- **Profile overrides**: `cost-optimized.json`, `performance-optimized.json`
- **Type-safe loader** (`src/agent/config_loader.py`), environment variable overrides (.env.example).
- **Validation Script**: (`scripts/validate_config.py`) checks schema, field completeness, model/Bicep template sync.
- **Documentation**: All configuration options, override hierarchy, troubleshooting in `docs/configuration-guide.md`.

---

## 4. Agent Construction & Core Conventions

- Use Azure AI Agent Framework v2 patterns (`src/agent/client.py`, `agent_factory.py`)
- All functions and classes must have **detailed type hints, docstrings, and inline comments**
- **Agent instructions**: Clear prompt specifying citation/formatting, multimodal response logic, and state-specific handling
- **Search integration**: Custom index configuration, hybrid keyword+vector, filter support
- **Image inclusion**: Keyword heuristics (see agent/image_relevance.py), optional LLM-as-judge
- **Multimodal response**: Citations, image references, streaming output support
- **Error handling and logging**: Structured, context-rich, retries w/ backoff, graceful degradation

---

## 5. Indexer Pipeline & Document Ingestion

- **Python scripts** (src/indexing/*.py): Comprehensive docstrings/comments
- **GitHub Actions workflow** (`ingest-documents.yml`): End-to-end automation for upload, indexer trigger, validation, notifications (step comments required)
- **Validation/monitoring**: Check enrichment, field completeness, anomalies

---

## 6. CI/CD, Testing, and Deployment

- **Workflows**:
  - `.github/workflows/deploy-infrastructure.yml`: Bicep validation, what-if preview, deployment (OIDC, manual/prod gates, environment separation)
  - `.github/workflows/test.yml`: PR checks—lint, typing, security, coverage, config validation, Bicep validation
  - `.github/workflows/deploy-agent.yml`: Agent build, test, containerize, deploy-to-foundry, canary rollout (comprehensive step comments)
  - `.github/workflows/deploy-indexer.yml`: Indexer change detection, backup, schema deployment
- **Testing standards**:
  - 80%+ unit test coverage for agent and indexer scripts
  - Integration testing for live agent/index
  - Evaluation suite (retrieval quality, faithfulness, citation accuracy)
- **Monitoring**: OpenTelemetry in `src/agent/telemetry.py`, log/metrics integration with Application Insights

---

## 7. Secure Automation & Environment Setup

- **OIDC Workload Identity**: Required for all deployment jobs, no stored secrets; setup documented in `docs/oidc-setup.md`
- **GitHub environments**: `development` (no approval) & `production` (manual approval, secrets, cooldown)
- **Rollback scripts**: `scripts/rollback-agent.ps1`, `scripts/rollback-index.ps1` (detailed comments on criteria and logic)

---

## 8. Documentation Standards

- **All code and YAML/workflow steps must be documented with detailed comments explaining rationale, choices, and trade-offs.**
- All docs should provide architecture diagrams, setup guides, and troubleshooting steps.
- README must be clear for onboarding, infra/agent quickstart, configuration examples.

---

## 9. Copilot Coding Agent Usage Tips

- Always resolve issue dependencies before starting.
- Use managed identities for all resource authentication.
- Modularize infrastructure for easy extension and rollback.
- Use comprehensive comments and validation in all code, YAML, and scripts.
- When implementing new features or workflows—refer to existing templates, configuration, and documentation conventions described above.

---

## References

- Please always review open issues (https://github.com/pkal42/DrivingManualAgent/issues) for up-to-date requirements
- Workflow and IaC setup conventions (see infra/bicep/ and .github/workflows/)
- Validation and troubleshooting scripts (scripts/, docs/)

---

**For further details, always consult the `README.md` and related documentation files. Reach out on PR comment threads with questions!**
