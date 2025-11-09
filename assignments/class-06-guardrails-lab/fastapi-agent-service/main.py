"""FastAPI chat service with a LangGraph ReAct agent using only the Tavily search tool."""

import os
from typing import Any, Optional
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler

from tavily import TavilyClient

from guardrails import Guard, OnFailAction
from guardrails.hub import ReadingTime, RestrictToTopic

# Load environment variables from .env file
load_dotenv()


# Pydantic python data models to ensure data integrity and validity
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    source: str
    monitored: bool
    session_id: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    message: str
    token: str


# Initializes the FastAPI
app = FastAPI(title="Class 5 Agent API", description="ReAct agent with tool access and monitoring.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.active_tokens: dict[str, str] = {}

# --- Setup helpers ---------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

LANGFUSE_PUBLIC = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST")
LANGFUSE_ENV = os.getenv("LANGFUSE_TRACING_ENVIRONMENT", "development")
AGENT_API_USERNAME = os.getenv("AGENT_API_USERNAME")
AGENT_API_PASSWORD = os.getenv("AGENT_API_PASSWORD")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not AGENT_API_USERNAME or not AGENT_API_PASSWORD:
    print("[Auth] Warning: AGENT_API_USERNAME or AGENT_API_PASSWORD is missing. Login will fail until both are set.")


# --- Guardrail Functions ------------------------------------------------------
def apply_reading_time_guardrail(response_text: str):
    """Ensure the assistant's response can be read in under 15 seconds."""
    FIFTEEN_SECONDS = 15 / 60  # reading_time is in minutes
    guard = Guard().use(
        ReadingTime,
        reading_time=FIFTEEN_SECONDS,
        on_fail=OnFailAction.EXCEPTION
    )

    try:
        return guard.validate(response_text)
    except Exception as e:
        print("[Guardrail: ReadingTime] Triggered:", e)
        return "GUARDRAILS ERROR"


def apply_topic_guardrail(prompt: str):
    """Restrict all conversations to Streamlit, FastAPI, and Programming."""
    guard = Guard().use(
        RestrictToTopic(
            valid_topics=["streamlit", "fastapi", "programming"],
            invalid_topics=["politics", "music", "sports"],
            disable_classifier=True,
            disable_llm=False,
            on_fail=OnFailAction.EXCEPTION
        )
    )

    try:
        return guard.validate(prompt)
    except Exception as e:
        print("[Guardrail: RestrictToTopic] Triggered:", e)
        return "GUARDRAILS ERROR"



def build_tools():
    """Create helper tools the agent can call, including Tavily search."""
    if tool is None:
        return []

    @tool
    def tavily_search(query: str) -> str:
        """Perform a web search using Tavily and summarize key sources."""
        if not TAVILY_API_KEY:
            return "Tavily API key not configured."
        client = TavilyClient(api_key=TAVILY_API_KEY)
        print("[Tool] tavily_search called")
        try:
            results = client.search(query)
            snippets = []
            for item in results.get("results", [])[:3]:
                snippets.append(f"- {item.get('title', '')}: {item.get('url', '')}")
            return "Tavily search results:\n" + "\n".join(snippets)
        except Exception as e:
            return f"Error calling Tavily: {e}"

    return [tavily_search]


def build_agent_runner():
    """Instantiate the LangGraph ReAct agent if dependencies and keys exist."""

    if not (OPENAI_API_KEY and create_react_agent and ChatOpenAI):
        return None

    tools = build_tools()
    if not tools:
        return None

    try:
        llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0, api_key=OPENAI_API_KEY)
        return create_react_agent(llm, tools)
    except Exception as exc:  # keep the API functional without the agent
        print(f"[LangGraph] could not create agent, using rule-based replies. Error: {exc}")
        return None


agent_runner = build_agent_runner()


def run_agent(message: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """Ask the LangGraph agent for a reply; return None if unavailable."""

    # Initialize Langfuse CallbackHandler for Langchain (tracing)
    langfuse_handler = CallbackHandler()

    if agent_runner is None:
        return None

    messages = []
    if system_prompt:
        messages.append(("system", system_prompt))
    messages.append(("user", message))

    try:
        result = agent_runner.invoke({"messages": messages}, config={"callbacks": [langfuse_handler]})
    except Exception as exc:  # fall back to rule-based helper on errors
        print(f"[LangGraph] agent invocation failed: {exc}")
        return None

    messages = result.get("messages") if isinstance(result, dict) else None
    if not messages:
        return None

    last_message = messages[-1]
    content = getattr(last_message, "content", last_message)
    return _content_to_text(content)


def _content_to_text(content: Any) -> Optional[str]:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                chunks.append(str(item["text"]))
            elif isinstance(item, str):
                chunks.append(item)
        return "\n".join(chunks).strip() if chunks else None
    if isinstance(content, dict) and "text" in content:
        return str(content["text"])
    return str(content) if content is not None else None


# --- Fallback replies ------------------------------------------------------
def build_offline_reply(message: str) -> str:
    text = message.lower()
    if "streamlit" in text:
        return "Streamlit reruns your script after every click. Keep anything you need in st.session_state."
    if "fastapi" in text:
        return "FastAPI ships with automatic docs at /docs. Try them once the server is running!"
    if "langfuse" in text or "monitor" in text:
        return "Langfuse links inputs and outputs. Set the keys to see traces pop up in the dashboard."
    if "deploy" in text:
        return "Deploy the API first, then point your Streamlit app to the live URL to share it."
    return "I am in offline mode. Ask about Streamlit, FastAPI, or Langfuse to see directed tips."


def invoke_agent(message: str, langfuse_client: Langfuse, session_id: str, system_prompt: Optional[str] = None) -> tuple[str, str]:
    with langfuse_client.start_as_current_span(name="🤖-fastapi-agent") as span:
        span.update_trace(input=message, session_id=session_id)

        agent_reply = run_agent(message, system_prompt)

        span.update_trace(output=agent_reply)

    if agent_reply:
        return agent_reply, f"langgraph:{OPENAI_MODEL}"
    return build_offline_reply(message), "rule-based"


# Generate token for authentication
def create_token(username: str) -> str:
    return f"token-{uuid4()}-{username}"


# Persist the token on the "memory" of the API
def save_token(token: str, username: str) -> None:
    app.state.active_tokens[token] = username


# Validate if the token passed by the user matches the one that was generated by the API
def verify_token(x_auth_token: str = Header(..., convert_underscores=False)) -> str:
    username = app.state.active_tokens.get(x_auth_token)
    if not username:
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")
    return username


# --- Routes -----------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest) -> LoginResponse:
    if not AGENT_API_USERNAME or not AGENT_API_PASSWORD:
        raise HTTPException(status_code=500, detail="Server credentials are not configured")

    if credentials.username != AGENT_API_USERNAME or credentials.password != AGENT_API_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_token(credentials.username)
    save_token(token, credentials.username)
    return LoginResponse(message=f"Welcome back, {credentials.username}!", token=token)


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, username: str = Depends(verify_token)) -> ChatResponse:
    """Main chat endpoint with topic and reading-time guardrails."""

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message cannot be empty")

    session_id = payload.session_id

    langfuse_client = get_client()
    if langfuse_client.auth_check():
        print("Langfuse client is authenticated and ready!")
        monitored = True
    else:
        print("Authentication failed. Please check your credentials and host.")
        monitored = False

    guard_topic_result = apply_topic_guardrail(message)
    if guard_topic_result == "GUARDRAILS ERROR":
        print("[Guardrail] Restricted topic triggered.")
        return ChatResponse(
            reply=(
                "Sorry, I can only discuss topics related to Streamlit, "
                "FastAPI, or general programming. Please adjust your question."
            ),
            source="guardrail:topic",
            monitored=False,
            session_id=session_id
        )

    SYSTEM_PROMPT = """
        You are a deployment assistant for Class 6 demos. 
        Explain environment setup, FastAPI backend deployment, and Streamlit UI integration clearly. 
        Use the Tavily search tool for recent context and cite sources when useful. 
    """

    reply, source = invoke_agent(
        message=message,
        langfuse_client=langfuse_client,
        session_id=session_id,
        system_prompt=SYSTEM_PROMPT
    )

    guard_length_result = apply_reading_time_guardrail(reply)
    if guard_length_result == "GUARDRAILS ERROR":
        print("[Guardrail] Reading time exceeded.")
        return ChatResponse(
            reply=(
                "The generated answer would take longer than 15 seconds to read. "
                "Please simplify or narrow down your question so I can provide a "
                "concise and focused response."
            ),
            source="guardrail:reading_time",
            monitored=monitored,
            session_id=session_id
        )

    return ChatResponse(
        reply=reply,
        source=source,
        monitored=monitored,
        session_id=session_id
    )
