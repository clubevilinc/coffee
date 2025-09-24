import os
import json
import platform
import subprocess
import typer
import re
from rich.console import Console
from groq import Groq

# Local imports
from .context_manager import add_message, get_messages, save_context, add_system_command, get_config

# --- Setup ---
console = Console()
app = typer.Typer(add_completion=False)
OS_TYPE = platform.system().lower()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
CURRENT_WORKING_DIRECTORY = os.getcwd()

# --- AI System Prompts ---
SYSTEM_PROMPT = f"""
You are Coffee, a terminal assistant.
You are a friendly assistant who talks nicely to the users, created by Chaitanya Saxena (cxaiiii).
You have one main responsibility: suggesting shell commands to help with system inspection and troubleshooting.
DONT BE RUDE OR DONT COME UP DIRECTLY WITH NEGATIVE MESSAGE, INSTEAD BE FRIENDLY AND BUILD A CONVERSATION WITH USER.

Output rules:
1. SINGLE COMMAND → JSON only: {{"command": "SHELL COMMAND", "explanation": "short explanation"}}
2. MULTI-STEP TASK → JSON only: {{"plan": [
   {{"command": "step1 command", "explanation": "what this does"}},
   {{"write_file": {{"path": "filename", "content": "file content"}}, "explanation": "creating file"}},
   {{"command": "step3 command", "explanation": "final step"}}
]}}
3. TASK COMPLETE → JSON only: {{"done": true, "explanation": "what was accomplished"}}
4. NORMAL CHAT → plain text response (no JSON)

For file creation tasks (like creating HTML, CSS, JS files), ALWAYS use write_file in a plan.
For the user request "create me a html css and js based landing page", you should respond with a plan that includes:
- Creating an HTML file with write_file
- Creating a CSS file with write_file
- Creating a JS file with write_file
- Each as separate write_file steps with actual file content

For troubleshooting, you'll be given stdout, stderr, and return code.
If no further action is required, respond with {{"done": true, "explanation": "..."}}.

Rules:
- The current working directory is: {CURRENT_WORKING_DIRECTORY}
- Use PowerShell on Windows, bash on Linux/macOS. OS: {OS_TYPE}.
- Prefer safe, minimal commands. No destructive defaults.
- DO NOT RECALL MEMORY UNLESS USER ASKED VERY SPECIFIC RELATED TO PREVIOUS MESSAGES.
- Be friendly and have a genuine conversation with user
- For file creation tasks, ALWAYS use write_file in a plan, not shell commands
- When creating multiple related files, use a multi-step plan
- Include actual file content in write_file steps, not placeholder text
- INSTEAD OF ONLY SUGGESTING COMMANDS EXECUTE THEM BY ITSELF BEFORE USER HAVE TO ASK YOU AGAIN TO DO SO
- BE POLITE BUT DONT DENY ANYTHING STRAIGHT ESPECIALLY WHEN ASKED TO DO
- MAKE SURE YOU ARE EASY TO UNDERSTAND EVEN TO A NEWBIE WITHOUT ANY TECH KNOWLEDGE
"""

TROUBLESHOOTING_PROMPT = """
A user tried to run the command: `{command}` to accomplish the following task: "{user_message}".

The command failed with the following error:
---
{stderr}
---

Please analyze the error and suggest a corrected command.
Respond in the following JSON format:
{{
  "command": "CORRECTED SHELL COMMAND",
  "explanation": "short explanation of what was wrong and how you fixed it"
}}
If you cannot suggest a fix, respond with a plain text message explaining the issue.
"""

# --- Helpers ---

def _extract_json_from_text(text: str):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', text, re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    m = re.search(r'(\{[\s\S]*\})', text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    return None


# --- Core Functions ---

def get_ai_summary(command: str, stdout: str, stderr: str, return_code: int, user_message: str = None) -> str:
    """Generate a plain contextual sentence about the command's result."""
    if not stdout and not stderr:
        return "The command finished with no visible output."

    status = "succeeded" if return_code == 0 else "failed"

    summary_prompt = f"""
The user asked: "{user_message or 'No specific request provided'}"
The system then ran the command: `{command}`, which {status}.

STDOUT (first 2000 chars):
---
{stdout[:2000]}
---

STDERR (first 2000 chars):
---
{stderr[:2000]}
---

Write one short, natural sentence that directly answers the user's request in context.
Do not mention AI, do not use words like 'summary' or 'explanation'. Just say what happened plainly.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You explain terminal results in plain, concise sentences. Always user-friendly, no meta labels."},
                {"role": "user", "content": summary_prompt}
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"(Could not generate result: {e})"


def run_shell_command(cmd: str, timeout: int = 60, user_message: str = None) -> dict:
    """Execute a shell command and return a structured result."""
    console.print(f"[cyan]Running:[/cyan] {cmd}")
    try:
        if "windows" in OS_TYPE:
            if cmd.startswith("touch "):
                filename = cmd.split(" ", 1)[1]
                cmd = f"New-Item {filename} -ItemType File"
        if "windows" in OS_TYPE:
            proc = subprocess.run(
                ["powershell", "-Command", cmd],
                capture_output=True, text=True, timeout=timeout,
                encoding='utf-8', errors='replace',
                cwd=CURRENT_WORKING_DIRECTORY
            )
        else:
            proc = subprocess.run(
                cmd, shell=True,
                capture_output=True, text=True, timeout=timeout,
                encoding='utf-8', errors='replace',
                cwd=CURRENT_WORKING_DIRECTORY
            )

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        return_code = proc.returncode

        if stdout:
            console.print(f"\n[green]Output:[/green]\n{stdout.strip()}")
        if stderr:
            console.print(f"\n[red]Error:[/red]\n{stderr.strip()}")

        summary = get_ai_summary(cmd, stdout, stderr, return_code, user_message)
        console.print(f"\n[yellow]{summary}[/yellow]\n")

        return {
            "command": cmd,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": return_code,
            "summary": summary,
        }

    except subprocess.TimeoutExpired:
        msg = "The command took too long and was stopped."
        console.print(f"[red]{msg}[/red]")
        return {"command": cmd, "stdout": "", "stderr": msg, "return_code": -1, "summary": msg}
    except Exception as e:
        console.print(f"[red]Failed to execute: {e}[/red]")
        return {"command": cmd, "stdout": "", "stderr": str(e), "return_code": -1, "summary": str(e)}


# --- Planning and Flow Execution ---

def plan_tasks(user_request: str):
    """Ask the model to break down the user's request into a flow tree plan."""
    planning_prompt = f"""
The user wants to: "{user_request}"
The current working directory is: "{CURRENT_WORKING_DIRECTORY}"

Create a step-by-step plan in JSON format to achieve this.
Each step should be one of:
- {{"command": "...", "explanation": "..."}}
- {{"write_file": {{"path": "...", "content": "..."}}, "explanation": "..."}}
- {{"read_file": {{"path": "..."}}, "explanation": "..."}}

Make sure steps are clear, sequential, and safe. Use `cd` to change directories when necessary.
"""
    response = call_groq(planning_prompt)
    return _extract_json_from_text(response)


def execute_plan(plan: dict, user_message: str):
    steps = plan.get("plan", [])
    if not steps:
        console.print("[red]No valid plan generated.[/red]")
        return

    console.print(f"[cyan]Executing {len(steps)} steps...[/cyan]\n")

    for idx, step in enumerate(steps, start=1):
        explanation = step.get("explanation", f"Step {idx}")

        if "command" in step:
            cmd = step["command"]
            console.print(f"[bold cyan]Step {idx}/{len(steps)}:[/bold cyan] {explanation}")
            if cmd.startswith("cd "):
                global CURRENT_WORKING_DIRECTORY
                try:
                    target_dir = cmd.split(" ", 1)[1]
                    if target_dir == "~":
                        target_dir = os.path.expanduser("~")
                    
                    if not os.path.isabs(target_dir):
                        target_dir = os.path.join(CURRENT_WORKING_DIRECTORY, target_dir)
                    
                    os.chdir(target_dir)
                    CURRENT_WORKING_DIRECTORY = os.getcwd()
                    console.print(f"[green]Changed directory to: {CURRENT_WORKING_DIRECTORY}[/green]")
                except FileNotFoundError:
                    console.print(f"[red]Error: Directory not found: {target_dir}[/red]")
                except Exception as e:
                    console.print(f"[red]Error changing directory: {e}[/red]")
                continue

            result = run_shell_command(cmd, user_message=user_message)

            if result["return_code"] != 0:
                console.print(f"[red]Step {idx} failed, stopping execution.[/red]")
                break
        elif "write_file" in step:
            wf = step["write_file"]
            path, content = wf.get("path"), wf.get("content", "")
            console.print(f"[bold cyan]Step {idx}/{len(steps)}:[/bold cyan] Writing file {path}")
            console.print(f"[dim]{explanation}[/dim]")
            try:
                if not os.path.isabs(path):
                    path = os.path.join(CURRENT_WORKING_DIRECTORY, path)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                console.print(f"[green]✅ File {path} written successfully ({len(content)} characters).[/green]\n")
            except Exception as e:
                console.print(f"[red]❌ Failed to write file {path}: {e}[/red]\n")
                break

        elif "read_file" in step:
            rf = step["read_file"]
            path = rf.get("path")
            console.print(f"[bold cyan]Step {idx}/{len(steps)}:[/bold cyan] Reading file {path}")
            console.print(f"[dim]{explanation}[/dim]")
            try:
                if not os.path.isabs(path):
                    path = os.path.join(CURRENT_WORKING_DIRECTORY, path)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                console.print(f"[green]✅ File {path} read successfully ({len(content)} characters).[/green]\n")
            except Exception as e:
                console.print(f"[red]❌ Failed to read file {path}: {e}[/red]\n")
                break

    console.print("\n[bold green]✅ Flow completed.[/bold green]\n")


# --- Response Handling ---

def troubleshoot_and_retry(failed_result, user_query):
    """Attempt to troubleshoot a failed command."""
    console.print("\n[bold yellow]The command failed. Attempting to troubleshoot...[/bold yellow]")
    
    prompt = TROUBLESHOOTING_PROMPT.format(
        command=failed_result["command"],
        stderr=failed_result["stderr"],
        user_message=user_query
    )
    
    ai_suggestion = call_groq(prompt)
    
    if ai_suggestion:
        console.print("\n[bold cyan]I have a suggestion for a fix:[/bold cyan]")
        process_ai_response(ai_suggestion, user_query)
    else:
        console.print("[red]Sorry, I couldn't figure out how to fix the command.[/red]")

def process_ai_response(ai_out: str, user_query: str):
    action = _extract_json_from_text(ai_out)
    
    if not action:
        console.print(f"[yellow]{ai_out}[/yellow]")
        add_message("assistant", ai_out)
        return

    if "plan" in action:
        plan_steps = action.get("plan", [])
        console.print(f"[cyan]📋 Plan detected with {len(plan_steps)} steps:[/cyan]")
        
        for i, step in enumerate(plan_steps, 1):
            if "command" in step:
                console.print(f"  {i}. [bold]Command:[/bold] {step.get('command', 'N/A')}")
                console.print(f"     [dim]{step.get('explanation', 'No explanation')}[/dim]")
            elif "write_file" in step:
                wf = step["write_file"]
                path = wf.get("path", "N/A")
                content_preview = wf.get("content", "")[:100] + "..." if len(wf.get("content", "")) > 100 else wf.get("content", "")
                console.print(f"  {i}. [bold]Write file:[/bold] {path}")
                console.print(f"     [dim]{step.get('explanation', 'No explanation')}[/dim]")
                console.print(f"     [dim]Content preview: {content_preview}[/dim]")
            elif "read_file" in step:
                rf = step["read_file"]
                console.print(f"  {i}. [bold]Read file:[/bold] {rf.get('path', 'N/A')}")
                console.print(f"     [dim]{step.get('explanation', 'No explanation')}[/dim]")
            else:
                console.print(f"  {i}. [bold]Unknown step:[/bold] {step}")
        
        if typer.confirm("\nExecute this plan?", default=True):
            execute_plan(action, user_query)
            add_message("assistant", f"Executed plan with {len(plan_steps)} steps for: {user_query}")
        else:
            console.print("[yellow]Plan execution cancelled.[/yellow]")
        return

    if "command" in action:
        cmd = action.get("command")
        explanation = action.get("explanation", "")
        if explanation:
            console.print(f"[cyan]{explanation}[/cyan]")

        # NEW: Handle `cd` before confirmation
        if cmd.startswith("cd "):
            global CURRENT_WORKING_DIRECTORY
            try:
                target_dir = cmd.split(" ", 1)[1]
                if target_dir == "~":
                    target_dir = os.path.expanduser("~")
                
                if not os.path.isabs(target_dir):
                    target_dir = os.path.join(CURRENT_WORKING_DIRECTORY, target_dir)
                
                os.chdir(target_dir)
                CURRENT_WORKING_DIRECTORY = os.getcwd()
                console.print(f"[green]Changed directory to: {CURRENT_WORKING_DIRECTORY}[/green]")
            except FileNotFoundError:
                console.print(f"[red]Error: Directory not found: {target_dir}[/red]")
            except Exception as e:
                console.print(f"[red]Error changing directory: {e}[/red]")
            return

        if typer.confirm("Run this command?", default=False):
            result = run_shell_command(cmd, user_message=user_query)
            add_system_command(user_query, {"command": cmd, "explanation": explanation})
            add_message("assistant", result.get("summary"))
            if result["return_code"] != 0:
                troubleshoot_and_retry(result, user_query)
        else:
            console.print("[yellow]Command not executed.[/yellow]")
        return

    if "done" in action and action.get("done"):
        explanation = action.get("explanation", "Task completed")
        console.print(f"[green]✅ {explanation}[/green]")
        add_message("assistant", explanation)
        return

    console.print(f"[red]Unrecognized response format: {action}[/red]")
    console.print(f"[yellow]{ai_out}[/yellow]")
    add_message("assistant", ai_out)


def call_groq(prompt: str):
    if not os.environ.get("GROQ_API_KEY"):
        console.print("[red]GROQ_API_KEY not set.[/red]")
        return None

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(get_messages())
    messages.append({"role": "user", "content": prompt})
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=messages, 
            temperature=0.2,
            max_tokens=4000
        )
        ai_reply = response.choices[0].message.content.strip()
        add_message("user", prompt)
        return ai_reply
    except Exception as e:
        console.print(f"[red]Groq API Error: {e}[/red]")
        return None


# --- Main Application Shell ---

def coffee_shell():
    global CURRENT_WORKING_DIRECTORY
    console.print("\n[bold cyan]☕ Coffee Terminal — Interactive Shell[/bold cyan]\n")
    console.print("[dim]Type a request or prefix with '/' to run a direct command.[/dim]")
    console.print("[dim]Type 'exit' or 'quit' to leave.\n[/dim]")

    while True:
        try:
            prompt_path = CURRENT_WORKING_DIRECTORY.replace(os.path.expanduser("~"), "~")
            query = console.input(f"[bold green]coffee ({prompt_path})> [/bold green]").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit"]:
                break
            
            # NEW: Direct handling for clear/cls
            if query.lower() in ["clear", "cls"]:
                if "windows" in OS_TYPE:
                    os.system("cls")
                else:
                    os.system("clear")
                continue

            if query.startswith('/'):
                command_to_run = query[1:].strip()
                if command_to_run and typer.confirm(f"Run command: {command_to_run}?", default=False):
                    run_shell_command(command_to_run, user_message=query)
                continue

            if query.startswith("cd "):
                try:
                    target_dir = query.split(" ", 1)[1]
                    if target_dir == "~":
                        target_dir = os.path.expanduser("~")
                    
                    if not os.path.isabs(target_dir):
                        target_dir = os.path.join(CURRENT_WORKING_DIRECTORY, target_dir)

                    os.chdir(target_dir)
                    CURRENT_WORKING_DIRECTORY = os.getcwd()
                except FileNotFoundError:
                    console.print(f"[red]Error: Directory not found: {target_dir}[/red]")
                except Exception as e:
                    console.print(f"[red]Error changing directory: {e}[/red]")
                continue

            ai_response = call_groq(query)
            if ai_response:
                process_ai_response(ai_response, query)

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            console.print(f"[red]Unexpected error: {e}[/red]")

    console.print("\n[bold cyan]☕ Goodbye![/bold cyan]\n")


# --- CLI Commands ---

@app.command()
def hi():
    """Start the interactive Coffee shell"""
    coffee_shell()


@app.command()
def reset():
    """Clear conversation memory"""
    save_context({"messages": [], "chat_history": []})
    console.print("[yellow]Conversation memory cleared.[/yellow]")


@app.command()
def version():
    """Show Coffee version"""
    console.print("[cyan]☕ Coffee Terminal Assistant v1.5[/cyan]")
    console.print("[dim]Created by Chaitanya Saxena (cxaiiii)[/dim]")


if __name__ == "__main__":
    app()