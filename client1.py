import asyncio
import sys
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage
import json
import os

load_dotenv()

SERVERS = { 
    "math": {
        "transport": "http",
        "command": sys.executable,
        # "args": ["-u", r"C:\Users\MANGISETTY BHARGAV\python\MCP\fastmcp-demo-server\main.py"]
        "args": ["-u", "https://scattered-coffee-shark.fastmcp.app/mcp"]
    }
}

async def main():
    
    client = MultiServerMCPClient(SERVERS)
    tools = await client.get_tools()


    named_tools = {}
    for tool in tools:
        named_tools[tool.name] = tool

    print("Available tools:", named_tools.keys())

    # If no OpenAI API key is set, do a direct tool smoke-test instead of calling the LLM
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set — running a direct tool smoke-test.")
        res = await named_tools["list_expenses"].ainvoke({"start_date": "2000-01-01", "end_date": "2100-01-01"})
        print("list_expenses result:", res)
        return

    llm = ChatOpenAI(model="gpt-5")
    llm_with_tools = llm.bind_tools(tools)

    prompt = "Add an expense of Rs 5000 as shopping on 2024-01-15 with note 'New shoes', and then list all expenses between 2024-01-01 and 2024-12-31."
    response = await llm_with_tools.ainvoke(prompt)
    print("LLM raw response repr:", repr(response))
    print("LLM tool_calls:", getattr(response, "tool_calls", None))
    print("LLM content repr:", repr(getattr(response, 'content', None)))
       
    if not getattr(response, "tool_calls", None):
        print("\nLLM Reply:", response.content)
        return

    tool_messages = []
    for tc in response.tool_calls:
        selected_tool = tc["name"]
        selected_tool_args = tc.get("args") or {}
        selected_tool_id = tc["id"]
        print("LLM requested tool:", selected_tool, "id:", selected_tool_id, "args:", selected_tool_args)

        result = await named_tools[selected_tool].ainvoke(selected_tool_args)
        print("Tool result for", selected_tool, ":", result)
        tool_messages.append(ToolMessage(tool_call_id=selected_tool_id, content=json.dumps(result)))
        

    print("Calling LLM with tool results. tool_messages:", tool_messages)
    final_response = await llm_with_tools.ainvoke([prompt, response, *tool_messages])
    print("Final response repr:", repr(final_response))
    print(f"Final response content repr: {repr(getattr(final_response, 'content', None))}")


if __name__ == '__main__':
    asyncio.run(main())