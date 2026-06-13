from pathlib import Path

from langgraph.graph import START, END, StateGraph
from langchain_aws import ChatBedrockConverse 
from state import SupervisorState, ValidationRouting
from tools import WRITER_TOOLS, RESEARCH_TOOLS
from langchain_core.messages import  SystemMessage, AIMessage, HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
import psycopg
from langchain_core.tools import tool
from langchain.agents import create_agent
from dotenv import load_dotenv
import os

load_dotenv()

BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

haiku = ChatBedrockConverse(model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION)


RESEARCHER_PROMPT = """You are a researcher. Your ONLY job is to search for information using your tools.
        
Rules:
- Use search_web to find information
- Return a SHORT summary of what you found — facts, sources, key points only
- Do NOT write documents, reports or any markdown files.
- Do NOT say 'let me create' or 'now I will write'
- When done searching, end with: RESEARCH COMPLETE: researched_data.md can be located in the disk.
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
           
        content = Path("final_output.md").read_text(encoding="utf-8")
        result =  structured_llm.invoke([SystemMessage(content=VALIDATOR_PROMPT), HumanMessage(content=f"Validate this Document: {content}")]) 
        
        
        print("🔎🔬 PYDANTIC STRUCTURED OUTPUT")
        print(f" type ❓: {type(result)}")
        print(f" status 🔃: {result.status}")
        print(f" reason 🫡: {result.reason[:100]}")
        print(f" raw 🍖: {result}")
        
        
        
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
        - use read_file tool to read "researched_data.md"
        - use write_file tool to produce the final polished document given by the researcher_agent.
        - Ensure that for every document getting created shall be named "final_output.md"
        
        
        DO NOT EVER:
        - route back to the research_agent again once research has been given.
        When validator returns criticism, NEVER route to research_agent.
       
        
        ONLY RETURN: 
        FILE CREATION IS COMPLETE: READY FOR validator_agent" .
        """)
    
    )
    
    def writer_agent(state: SupervisorState) -> dict:
        result = writer.invoke({"messages": state["messages"]})
        return {"messages": [AIMessage(content="THE FILE HAS BEEN SUCCESSFULLY GENERATED: final_output.md READY FOR THE VALIDATOR AGENT.", name= "writer_agent")]
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

        Path("researched_data.md").write_text(full_output, encoding="utf-8")
        return {"messages": [AIMessage(content="RESEARCH COMPLETE, Full findings saved to researched_data.md", name="researcher_agent")]}
        
    return research_agent
    

def build_graph(haiku):
    
    
    writer_node = make_writer_node(haiku)
    research_node = make_research_node(haiku)
    validator_node = validator_agent(haiku)
    
    
    graph = StateGraph(SupervisorState)
    
    
    graph.add_node("writer", writer_node)
    graph.add_node("researcher", research_node)
    graph.add_node("validator", validator_node)
    
    graph.add_edge(START, "researcher")
    graph.add_edge("researcher", "writer")
    graph.add_edge("writer", "validator")
    graph.add_conditional_edges("validator", validator_route,
    {
        "writer_agent": "writer",
        END : END
    })
   
 
    
    return graph





POSTGRES_URI = os.getenv("POSTGRES_URI")
_conn = psycopg.connect(POSTGRES_URI, autocommit=True)
_checkpointer = PostgresSaver(_conn)
_checkpointer.setup()
app = build_graph(haiku).compile(checkpointer=_checkpointer, interrupt_before=["writer"]) 



if __name__ == "__main__":
    import sys
    THREAD_ID = "persistence_test-1"
    config = {"configurable": {"thread_id": THREAD_ID},
    "metadata": {"pipeline": "research-writer-validator"},
    "tags": ["v1", "deterministic"],
    }
    
    existing = app.get_state(config)
    
    if existing.values and "--resume" in sys.argv:
        print(f"\n⏯️  Resuming thread: {THREAD_ID}")
        print(f"  Next node: {existing.next}")
        
        
         # Show the human what the researcher produced before resuming
        messages = existing.values.get("messages", [])
        if messages:
            print(f"\n📋 Researcher output:\n")
            print(messages[-1].content)
        
        confirm = input("\n✅ Approve and send to writer? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("❌ Cancelled. Run again with --resume to retry.")
            exit(0)

        input_data = None  # None = resume from checkpoint, don't add messages
  
        
    else:
        query = input("Enter your research query here: ").strip()
        if not query:
            print("No query provided")
            exit(1)
        input_data = {"messages": [HumanMessage(content=query)]}
        print(f"\n🆕 Starting new run on thread: {THREAD_ID}")
    
    
    for namespace, step in app.stream(
    input_data,
    config=config,
    stream_mode="updates",
    subgraphs =True
):
        for node_name, update in step.items():
            print(f"\n── [{node_name}] ──")
        if node_name == "__interrupt__":
            print("⏸️  Graph paused. Run with --resume to review and continue.")
        elif isinstance(update, dict):
            for message in update.get("messages", []):
                message.pretty_print()
        print("─" * 40)