# **☕ Say "Hi" to Coffee\!**

Coffee is a friendly, interactive terminal assistant designed to help you with system inspection, troubleshooting, and executing shell commands. It's built to be intuitive, even for users without extensive tech knowledge, and provides a conversational interface for interacting with your command line.

## **🚀 Use Cases**

* **System Inspection**: Quickly find files, check system status, or get information about your current working environment.  
* **Troubleshooting**: If a command fails, Coffee can analyze the error and suggest a corrected command to get you back on track.  
* **File Manipulation**: Create, read, and write files directly from the chat interface, including multi-file projects like landing pages.  
* **Automated Tasks**: Define multi-step plans to execute a series of commands, such as setting up a new project or running a build process.

## **✨ Features**

* **Interactive Shell**: An easy-to-use, interactive shell that provides a conversational way to run commands.  
* **AI-Powered Suggestions**: Utilizes the **Groq Llama 3.1 model** to understand your requests and provide intelligent command suggestions.  
* **Plan Execution**: For complex tasks, Coffee can generate a multi-step plan and execute it for you, handling everything from directory changes to file creation.  
* **Error Troubleshooting**: When a command fails, Coffee will automatically attempt to troubleshoot the issue and provide a corrected command.  
* **Context-Aware Conversations**: Maintains a short-term memory of your conversation to provide relevant follow-up suggestions.

## **🛠️ Tech Stack**

* **Python**: The core language used for the assistant.  
* **Typer**: For creating a clean and user-friendly command-line interface.  
* **Rich**: To render beautiful and informative output in the terminal, with colors and formatting.  
* **Groq**: Provides the high-speed LLM inference for understanding natural language and generating command suggestions.

## **⚙️ How It Works**

Coffee is designed around a few core components:

* **Main Application (main.py)**: This is the entry point of the application and handles the main interactive shell. It processes user input, calls the Groq API for AI-powered suggestions, and manages the overall flow of the conversation.  
* **Context Manager (context\_manager.py)**: This module is responsible for managing the conversation history and context. It stores a short history of messages and executed commands in a local JSON file (\~/.coffee\_context.json) to provide context-aware responses.  
* **AI Integration**: When you enter a request, Coffee sends it to the Groq API along with the current context. The AI model then returns a JSON object containing a command, a multi-step plan, or a simple text response. The application then processes this response to execute the command, display the plan, or print the chat message.

## **🚀 Getting Started**

### **Installation:**

git clone \[https://github.com/your-username/coffee-terminal-assistant.git\](https://github.com/your-username/coffee-terminal-assistant.git)  
cd coffee-terminal-assistant  
pip install \-r requirements.txt

### **Configuration:**

Set your Groq API key as an environment variable:

export GROQ\_API\_KEY="your-api-key"

(Optional) Create a \~/.coffeerc file to customize settings.

### **Run the Assistant:**

python \-m coffee.main hi

## **📝 Commands**

* hi: Starts the interactive Coffee shell.  
* reset: Clears the conversation memory.  
* version: Shows the current version of the assistant.