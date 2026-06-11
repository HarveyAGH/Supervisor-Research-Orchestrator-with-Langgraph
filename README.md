# LangGraph Supervisor Agent

Multi-agent research pipeline built with LangGraph using the Supervisor pattern.

## Architecture

- **Supervisor** — routes between agents based on task state
- **Researcher** — searches the web, gathers information
- **Writer** — reads research, produces final documents
- **Validator** — validates output quality before completion

## Tech Stack

- **LangGraph** — StateGraph, Supervisor pattern, checkpointing
- **AWS Bedrock** — Claude Haiku via ChatBedrockConverse
- **LangSmith** — Tracing and observability
- **Python 3.12+** — Pydantic, pathlib, async
- **DuckDuckGo** — Web search via `ddgs` package

## Setup

### Prerequisites

- Python 3.12+
- `uv` (Python package manager)
- AWS credentials with Bedrock access
- `.env` file with Bedrock configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0
BEDROCK_REGION=us-east-1
AWS_BEARER_TOKEN_BEDROCK=<your-token>
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=<your-key>
LANGSMITH_PROJECT=<your-project>
```

### Install Dependencies

```bash
uv sync
```

## Running

```bash
uv run python agents4.py
```

This will:
1. Route through Supervisor to Researcher
2. Researcher gathers information via web search
3. Routes back to Supervisor for Writer
4. Writer produces final output
5. Completes with FINISH signal

## Project Structure

```
.
├── README.md              # This file
├── pyproject.toml         # Dependencies and project config
├── .env                   # (git-ignored) Your credentials
├── .gitignore             # Git ignore rules
├── state.py               # Pydantic models: SupervisorState, RouteDecision
├── tools.py               # LangChain tools: search_web, read_file, write_file
├── agents4.py             # Main graph implementation
└── mens_health/           # Output directory for generated files
    └── chroma.sqlite3     # Vector store cache (if used)
```

## Key Files

- **state.py** — Defines the state machine and routing logic
- **tools.py** — Tools available to agents (search, read, write)
- **agents4.py** — Graph builder and execution

## Common Issues

### ReadTimeoutError from Bedrock
The API may timeout on complex tasks. This is expected for large research operations. Consider:
- Increasing timeout in ChatBedrockConverse
- Breaking tasks into smaller subtasks
- Using longer-context models

### Module Not Found: ddgs
Install the package:
```bash
uv pip install ddgs
```

### Environment Variables Not Loading
Ensure `.env` is in the root directory and contains all required variables.

## Future Work

- [ ] Add validation node for output quality checks
- [ ] Implement persistent checkpointing to database
- [ ] Add retry logic with exponential backoff
- [ ] Build eval suite for agent outputs
- [ ] Deploy as API endpoint

## License

MIT
