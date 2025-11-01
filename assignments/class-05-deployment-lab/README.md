# Class 5 Agent API (Extended Demo)

This project extends the **Class 5 FastAPI + LangGraph demo** into a more complete **deployment assistant** that can reason about Streamlit, FastAPI, and monitoring workflows.  
It integrates **LangChain ReAct agents**, **Langfuse** tracing, and the **Tavily** search tool for real-time information retrieval.

The **Streamlit app** remains the same as in the original Class 5 demo but is now deployed on Streamlit Cloud and connects to the FastAPI backend deployed on Render.
This setup demonstrates a realistic end-to-end deployment pipeline, from a hosted frontend to a cloud-based API.

> *The extended functionality, tool integration, and deployment configuration in this version were developed by Catarina Dias as part of the Tutai Module 6 class 5 assignment.*

---

## Overview

The service exposes a `/chat` endpoint that routes user prompts to a **LangChain ReAct agent**.  
The agent can use several built-in tools:

| Tool                   | Purpose |
|------------------------|----------|
| `streamlit_playbook`   | Provides Streamlit UI tips and deployment suggestions |
| `deployment_checklist` | Outlines deployment, monitoring, and API exposure steps |
| `tavily_search`        | Performs live web searches via the Tavily API for up-to-date answers |

All traces (inputs, outputs, tool invocations) are logged via **Langfuse** for monitoring.

## Setup Instructions

### 1. Clone and install dependencies

```bash
git clone <your-repo-url>
cd class5-agent-api
pip install -r requirements.txt
```

### 2. Configure environment variables
Create a .env file in the project root.

Copy the .env.example file, rename it to .env and fill with the necessary environment variables.

### 3. Run locally
```bash
uvicorn main:app --reload
```

Check the health endpoint:
```bash
curl http://127.0.0.1:8000/health
```

Expected response:
```json
{"status": "ok"}
```

### 4. Authenticate and Chat

#### Step 1: Login to get a token
```bash
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "class5", "password": "demo123"}'

```

Expected response:
```json
{"message": "Welcome back, class5!", "token": "token-1234-class5"}
```

#### Step 2: Send a chat message
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -H "x-auth-token: token-1234-class5" \
  -d '{"message": "How do I deploy a FastAPI app on Render?"}'
```

## Key Code Changes from the Original Demo

| Area                     | Change                                                                             | Purpose                                   |
| ------------------------ | ---------------------------------------------------------------------------------- | ----------------------------------------- |
| **Agent builder**        | Uses `create_react_agent` from `langchain.agents` instead of `langgraph.prebuilt`. | Aligns with LangChain ≥ 0.3.x             |
| **Prompt structure**     | Dynamic system prompt injected per `/chat` request.                                | Ensures compatibility and flexibility     |
| **Tooling**              | Added Tavily search, Streamlit, and deployment helpers.                            | Enhances reasoning with real-time data    |
| **Langfuse Integration** | Added tracing via `CallbackHandler` and `get_client()`.                            | Monitors inputs/outputs for observability |


## Example Prompts by Tool

### Streamlit Playbook
| Example Prompt                                               | Expected Behavior                                        |
| ------------------------------------------------------------ | -------------------------------------------------------- |
| “How do I persist state between button clicks in Streamlit?” | Uses `streamlit_playbook` → explains `st.session_state`. |
| “How can I deploy my Streamlit app?”                         | Returns deployment flow for Streamlit Community Cloud.   |


### Deployment Checklist
| Example Prompt                            | Expected Behavior                             |
| ----------------------------------------- | --------------------------------------------- |
| “Give me a FastAPI deployment checklist.” | Returns structured API deployment steps.      |
| “How do I monitor my API with Langfuse?”  | Describes Langfuse trace and debugging setup. |


### Tavily Search
| Example Prompt                                         | Expected Behavior                                 |
| ------------------------------------------------------ | ------------------------------------------------- |
| “What are the latest FastAPI security best practices?” | Invokes `tavily_search` to fetch current sources. |
| “Recent changes in Streamlit 1.40?”                    | Fetches release notes using Tavily results.       |
| “What are the 2025 deployment trends for AI agents?”   | Performs real-time web lookup via Tavily.         |


## API Summary
| Method | Endpoint  | Auth | Description                 |
| ------ | --------- | ---- | --------------------------- |
| `GET`  | `/health` | ❌    | Health check                |
| `POST` | `/login`  | ❌    | Obtain API token            |
| `POST` | `/chat`   | ✅    | Send a message to the agent |


## Deployment Notes
This project can be run locally or accessed via the public demo deployments:

 - Streamlit Frontend (UI): https://tutai-m6-assignments-class5.streamlit.app/

 - FastAPI Backend (API): https://tutai-m6-part2-assignments.onrender.com


Both the local and cloud deployments are functionally equivalent — the Streamlit app communicates with the same FastAPI backend.

### Streamlit Configuration Note
The link for the Render API can be:

 - Added to the .env file of the Streamlit app under a variable such as `API_URL`, or

 - Updated directly in the Streamlit code if you’re testing manually.

To run the Streamlit app locally, execute:
```bash
streamlit run assignments/class-05-deployment-lab/streamlit-chat-ui/app.py
```
This will launch the chat interface locally and connect to the API endpoint you configure.