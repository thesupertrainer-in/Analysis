"""
DMLT Consolidation Agent — main agent class.

Implements a two-phase workflow:
  Phase 1 (deterministic): Run all 5 calc tools sequentially
  Phase 2 (AI reasoning): Run AI analysis on confirmed results
  Phase 3: Generate Excel report and POST callback to CAP backend
"""
import json
import logging
from dataclasses import dataclass
from typing import AsyncGenerator, Literal, Sequence

import httpx
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent as create_agent
from langchain_litellm import ChatLiteLLM
try:
    from sap_cloud_sdk.agent_decorators import agent_config, agent_model, prompt_section
    from sap_cloud_sdk.agent_memory.factory.langgraph_checkpoint import create_checkpointer
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False
    # Lightweight stubs so decorators are no-ops in local dev
    def agent_config(**kw):
        return lambda fn: fn
    def agent_model(**kw):
        return lambda fn: fn
    def prompt_section(**kw):
        return lambda fn: fn
    def create_checkpointer(**kw):
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()

from tools.calc_tools import get_calc_tools
from tools.ai_analysis_tools import get_ai_analysis_tools
from tools.excel_tool import get_excel_tool

logger = logging.getLogger(__name__)


@agent_model(
    key="config.model",
    label="LLM Model",
    description="The language model powering this agent",
)
def get_model_name() -> str:
    return "sap/anthropic--claude-4.5-sonnet"


@agent_config(
    key="config.temperature",
    label="LLM Temperature",
    description="Controls randomness of responses (0.0 = deterministic, 1.0 = creative)",
)
def get_temperature() -> float:
    return 0.0


@agent_config(
    key="config.checkpointer.ttl_seconds",
    label="Thread TTL (seconds)",
    description="Evict inactive conversation threads after this period of inactivity.",
)
def thread_ttl_seconds() -> int:
    return 3600  # 1 hour


@prompt_section(
    key="prompts.system",
    label="System Prompt",
    description="The full system prompt defining the agent's role and behavior",
    validation={"format": "markdown", "max_length": 5000},
)
def get_system_prompt() -> str:
    return """\
You are a DMLT Consolidation Study Assistant — an expert SAP technical agent for \
analysing and planning SAP system consolidations.

## Core Rules
1. **Deterministic first**: Always run all 5 calc_* tools before any analysis tools.
2. **AI on confirmed data only**: analysis tools must receive the EXACT JSON output \
from calc tools — never fabricate or estimate values.
3. **Full pipeline**: For a DMLT run, always complete ALL steps:
   - calc_hardware_sizing → analyse_sizing
   - calc_company_code_collisions → analyse_collisions
   - calc_number_range_conflicts → analyse_nriv
   - calc_growth_trends → analyse_growth
   - calc_system_profiles → (feed into generate_executive_summary)
   - generate_executive_summary (with all 5 calc results)
   - generate_excel_report (with original sections)

## Inputs
When invoked with a JSON payload containing 'sections' and 'callbackUrl', \
execute the full pipeline, then POST results to callbackUrl.

## Output Format
Return a structured JSON summary of all findings when the pipeline completes.

IMPORTANT: You MUST use tools to perform calculations. Never guess or estimate \
numerical results.
"""


@dataclass
class AgentResponse:
    status: Literal["input_required", "completed", "error"]
    message: str


class DmltAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        ttl = thread_ttl_seconds()
        self.llm = ChatLiteLLM(model=get_model_name(), temperature=get_temperature())
        self._checkpointer = create_checkpointer(ttl_seconds=ttl or None)
        # All tools — deterministic + AI analysis + Excel
        self._all_tools = (
            get_calc_tools()
            + get_ai_analysis_tools()
            + get_excel_tool()
        )

    async def stream(
        self,
        query: str,
        context_id: str,
        tools: Sequence[BaseTool] | None = None,
    ) -> AsyncGenerator[dict, None]:
        yield {
            "is_task_complete": False,
            "require_user_input": False,
            "content": "Starting DMLT analysis pipeline...",
        }

        try:
            effective_tools = list(tools) if tools else self._all_tools
            system_prompt = get_system_prompt()
            if not effective_tools:
                system_prompt += "\n\nIMPORTANT: No tools available. Explain this to the user."

            graph = create_agent(
                self.llm,
                tools=effective_tools,
                prompt=system_prompt,
                checkpointer=self._checkpointer,
            )
            config = {"configurable": {"thread_id": context_id}}
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=query)]}, config
            )
            response = result["messages"][-1].content

            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": response,
            }

        except Exception:
            logger.exception("DmltAgent.stream() failed")
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": "I encountered an error while processing your request. Please try again.",
            }

    async def invoke(
        self,
        query: str,
        context_id: str,
        tools: Sequence[BaseTool] | None = None,
    ) -> AgentResponse:
        last: dict = {}
        async for chunk in self.stream(query, context_id, tools=tools):
            last = chunk
        if last.get("is_task_complete"):
            return AgentResponse(status="completed", message=last["content"])
        if last.get("require_user_input"):
            return AgentResponse(status="input_required", message=last["content"])
        return AgentResponse(status="error", message=last.get("content", "Unknown error"))
