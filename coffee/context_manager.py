# context_manager.py
import os
import json
import re
import time

CONTEXT_FILE = os.path.expanduser("~/.coffee_context.json")

DEFAULT_CONTEXT = {
    "messages": [],
    "chat_history": []
}

def load_context():
    """Load context safely with defaults"""
    if not os.path.exists(CONTEXT_FILE):
        return DEFAULT_CONTEXT.copy()

    try:
        with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return DEFAULT_CONTEXT.copy()

    # ✅ Ensure required keys exist
    for k, v in DEFAULT_CONTEXT.items():
        if k not in data:
            data[k] = v
    return data

def save_context(context):
    os.makedirs(os.path.dirname(CONTEXT_FILE), exist_ok=True)
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2)

def is_json_command(content):
    """Check if content looks like a JSON command to avoid polluting chat history"""
    try:
        data = json.loads(content)
        return isinstance(data, dict) and "command" in data
    except json.JSONDecodeError:
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{[\s\S]*?"command"[\s\S]*?\})'
        ]
        return any(re.search(pattern, content, re.DOTALL) for pattern in json_patterns)

def add_message(role, content):
    """Add message to chat history (skip JSON commands)"""
    if is_json_command(content):
        return
    context = load_context()
    context["chat_history"].append({"role": role, "content": content})
    context["chat_history"] = context["chat_history"][-10:]  # keep last 10
    save_context(context)

def get_messages():
    """Return only chat history"""
    return get_chat_history()

def add_chat_message(role, content):
    """Alias for add_message"""
    add_message(role, content)

def get_chat_history():
    """Get chat history safely"""
    ctx = load_context()
    return ctx.get("chat_history", [])

def add_system_command(user_query, command_data):
    """Store executed commands separately"""
    context = load_context()
    context["messages"].append({
        "user_query": user_query,
        "command": command_data.get("command"),
        "explanation": command_data.get("explanation"),
        "timestamp": time.time()
    })
    context["messages"] = context["messages"][-5:]  # keep last 5
    save_context(context)

def get_recent_commands():
    return load_context().get("messages", [])

def clear_messages():
    save_context(DEFAULT_CONTEXT.copy())

def get_message_count():
    ctx = load_context()
    return len(ctx.get("messages", [])) + len(ctx.get("chat_history", []))

def get_config():
    config_file = os.path.expanduser("~/.coffeerc")
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            return json.load(f)
    return {
        "search_max_results": 20,
        "exclude_dirs": [".git", "node_modules", "venv", "__pycache__"],
        "use_native_tools": True
    }
