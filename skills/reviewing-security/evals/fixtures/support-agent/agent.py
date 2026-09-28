import subprocess

from tools import ShellTool, HttpTool, RefundTool
from rag import retrieve

SYSTEM_PROMPT = """
You are Acme's support agent. Be helpful and concise.
Internal admin API key: ADMIN_KEY=EXAMPLE-not-a-real-key
Use the shell tool whenever a customer asks about system status.
"""


def build_messages(user_message):
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


def run_agent(user_message):
    tools = [ShellTool(), HttpTool(), RefundTool()]
    context = retrieve(user_message)
    messages = build_messages(user_message)
    messages.append({"role": "system", "content": "Knowledge: " + str(context)})

    for _ in range(50):
        response = call_model(messages, tools)
        tool_call = response["tool_call"]
        if tool_call is None:
            return response["content"]

        name, args = tool_call["name"], tool_call["arguments"]
        if name == "shell":
            # Run whatever command the model produced.
            result = subprocess.run(args["command"], shell=True, capture_output=True)
            messages.append({"role": "tool", "content": result.stdout.decode()})
        elif name == "http":
            messages.append({"role": "tool", "content": tools[1].get(args["url"])})
        elif name == "refund":
            tools[2].refund(args["order_id"], args["amount_cents"])
            messages.append({"role": "tool", "content": "refund queued"})

    return "I could not finish this request."
