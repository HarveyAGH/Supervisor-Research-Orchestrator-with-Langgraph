from pathlib import Path

from langgraph.graph import START, END, StateGraph
from typing import TypedDict, Annotated, Sequence, Literal
from langgraph.types import Command
from langchain_aws import ChatBedrock, ChatBedrockConverse 
from state import RouteDecision, SupervisorState, ValidationRouting
from tools import WRITER_TOOLS, RESEARCH_TOOLS, VALIDATOR_TOOLS
from langchain_core.messages import  SystemMessage, BaseMessage, AIMessage, ToolMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.tools import tool
from langchain.agents import create_agent
from langgraph.prebuilt import ToolNode
from dotenv import load_dotenv
import os
from operator import add as add_messages

load_dotenv()

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

haiku = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION)

MEMBERS = ["writer_agent", "researcher_agent", "validator_agent"]


SUPERVISOR_PROMPT = f"""You are a supervisor coordinating a team: {MEMBERS}.

Your ONLY job is to decide who acts next.

Workers:
  - researcher_agent: searches the web, reads files, gathers information
  - writer_agent: writes files, produces final documents and reports
  - validator_agent: validates the output brought by the writer_agent to ensure output accuracy, ONLY gets called after the writer_agent's job

  
Rules:
   - Step 1: Route to researcher_agent first to gather information
   - Step 2: After researcher_agent reports and created the research_output file, DO NOT re-route back to the research_agent again.
    route to writer_agent EXPLICITLY after the research agent returns: "RESEARCH COMPLETE" 
  - Step 3: After writer_agent confirms a file was written, ALWAYS route to validator_agent next 
  - Step 4: If validator_agent responds APPROVED, return FINISH
  - Step 5: If validator_agent responds REVISION NEEDED, route back to writer_agent
  - NEVER return FINISH before validator_agent has responded
  - NEVER skip validator_agent after the writer has written a file
  - Do NOT do any work yourself. Only route.
"""


RESEARCHER_PROMPT = """You are a researcher. Your ONLY job is to search for information using your tools.
        
Rules:
- Use search_web to find information
- Return a SHORT summary of what you found — facts, sources, key points only
- Do NOT write documents, reports or any markdown files.
- Do NOT say 'let me create' or 'now I will write'
- When done searching, end with: RESEARCH COMPLETE: research_output.md can be located in the disk.
- Never do the writer's job"""










    
    
VALIDATOR_PROMPT = """You are a validator reviewing a written document.

Check if the output:
1. Actually addresses the original task based off of the query
2. Contains real substantive content
3. Is complete and is relevant to the orignal query
4. if it does include relevancy do not become over strict and pass it

If it passes, respond with: APPROVED -> and FINISH
If it fails, respond with: REVISION NEEDED
"""
    

def validator_agent(haiku):
    structured_llm = haiku.with_structured_output(ValidationRouting)
    
    def validator(state: SupervisorState) -> dict:
           
        content = Path("completed_research.md").read_text(encoding="utf-8")
        result =  structured_llm.invoke([SystemMessage(content=VALIDATOR_PROMPT), HumanMessage(content=f"Validate this Document: {content[:2000]}")]) 
        return {
        "messages": [AIMessage(content=f"{result.status} : {result.reason}", name= "validator_agent")],
        "validator_status" : result.status
            }
    
    return validator
       
def validator_route(state: SupervisorState) -> str:
    if state["validator_status"] == "REVISION_NEEDED":
        return "writer_agent"
    return END

        
    
    
def make_writer_node(haiku):
    writer = create_agent(
        model=haiku,
        tools= WRITER_TOOLS,
        system_prompt= ("""
        DO:
        - use read_file tool to read "research_output.md"
        - use write_file tool to produce the final polished document given by the researcher_agent.
        
        
        DO NOT EVER:
        - route back to the research_agent again once research has been given.
        When validator returns criticism, NEVER route to research_agent.
       
        
        ONLY RETURN: 
        FILE CREATION IS COMPLETE: READY FOR validator_agent" .
        """)
    
    )
    
    def writer_agent(state: SupervisorState) -> dict:
        result = writer.invoke({"messages": state["messages"]})
        return {"messages": [AIMessage(content="THE FILE HAS BEEN SUCCESSFULLY GENERATED: completed_research.md READY FOR THE VALIDATOR AGENT.", name= "writer_agent")]
        }
            
    
    return writer_agent

def make_research_node(haiku):
    researcher = create_agent(
        model=haiku,
        tools= RESEARCH_TOOLS,
        system_prompt=RESEARCHER_PROMPT
    )
    
    def research_agent(state: SupervisorState) -> dict:
        result = researcher.invoke({"messages": state["messages"]})
        raw = result["messages"][-1].content
    
        if isinstance(raw, list):
            full_output = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in raw
            )
        else:
            full_output = raw

        Path("research_output.md").write_text(full_output, encoding="utf-8")
        return {"messages": [AIMessage(content="RESEARCH COMPLETE, Full findings saved to research_output.md", name="researcher_agent")]}
        
    return research_agent
    


def routing_logic(state: SupervisorState) -> str:
    next_node = state["next"]
    if next_node == "FINISH":
        return END
    return next_node


def build_graph(haiku):
    
    
    writer_node = make_writer_node(haiku)
    research_node = make_research_node(haiku)
    validator_node = validator_agent(haiku)
    
    
    graph = StateGraph(SupervisorState)
    
    
    graph.add_node("writer_agent", writer_node)
    graph.add_node("researcher_agent", research_node)
    graph.add_node("validator_agent", validator_node)
    
    graph.add_edge(START, "researcher_agent")
    graph.add_edge("researcher_agent", "writer_agent")
    graph.add_edge("writer_agent", "validator_agent")
    graph.add_conditional_edges("validator_agent", validator_route,
    {
        "writer": "writer_agent",
        END : END
    })
   
 
    
    return graph


def get_app(llm):
    graph = build_graph(llm)
    
    
    checkpointer = InMemorySaver()
    return graph.compile(checkpointer=checkpointer)



if __name__ == "__main__":
    
    haiku = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION)
    app = get_app(haiku)
    config = {"configurable": {"thread_id": "#1"}}
    
    for namespace, step in app.stream(
    {"messages": [HumanMessage(content="Research the latest cutting edge AI engineering stacks i should stick with and what would be more than enough for me to start applying to AI companies for the AI engineering role, my currect stack is Langgraph Supervisor pattern, RAG, Eval+gold datasets, tracing with langsmith, identify any other missing stuff and write a summary to Engineering.md, the year is 2026")]},
    config=config,
    stream_mode="updates",
    subgraphs =True
):
        for node_name, update in step.items():
            print(f"\n── [{node_name}] ──")
        for message in update.get("messages", []):
            message.pretty_print()
        print("─" * 40)