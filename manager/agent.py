from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool

from .sub_agents.sommelier_agent import sommelier_agent
from .sub_agents.search_agent import search_agent

root_agent = Agent(
    name="manager",
    model="gemini-2.0-flash",
    description="Manager Agent.",
    instruction=(
        "You are the manager agent overseeing wine recommendation tasks. "
        "Delegate to the sommelier agent for wine preferences and to the search agent for additional info."
    ),
    sub_agents=[sommelier_agent],
    tools=[AgentTool(search_agent)],
)
