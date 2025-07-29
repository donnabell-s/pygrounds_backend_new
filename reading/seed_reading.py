from reading.models import ReadingMaterial


ReadingMaterial.objects.create(
    topic="Introduction to Python & IDE Setup",
    subtopic="Installing Python",
    title="Installing Python",
    content="""
## Installing Python

Before you can write Python code, you need to install Python on your machine.

---

### For Windows:
1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download the installer for Windows.
3. During installation, check **"Add Python to PATH"**
4. Click **"Install Now"**

---

### For macOS:
1. Install Homebrew (if you haven't yet):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)
""",
order_in_topic=1
)

ReadingMaterial.objects.create(
topic="Introduction to Python & IDE Setup",
subtopic="Choosing and Setting Up an IDE",
title="Choosing and Setting Up an IDE",
content="""

## Choosing and Setting Up an IDE
An Integrated Development Environment (IDE) makes it easier to write, test, and debug Python code.

Popular Python IDEs:
VS Code → Lightweight, fast, and highly customizable.

PyCharm → Feature-rich and great for large Python projects.

Thonny → Designed for beginners; simple and clean.

Jupyter Notebook → Ideal for data science and quick experiments.

Setting Up VS Code (Recommended)
Download VS Code from code.visualstudio.com

Install the Python Extension:

Open VS Code

Click the Extensions icon (Ctrl+Shift+X)

Search for "Python"

Click Install on the extension by Microsoft

(Optional) Install Code Runner:

Still in Extensions tab, search for "Code Runner"

Click Install

This lets you run .py files with one click

Try running a Python file:

Create a new file named hello.py and paste this code:
print("Hello, Python!")
""",
order_in_topic=2
)

ReadingMaterial.objects.create(
topic="Introduction to Python & IDE Setup",
subtopic="Writing and Running Your First Python Script",
title="Your First Python Program",
content="""

Your First Python Program
Let’s write and run your very first Python program!

Create a Python File
Open your IDE (like VS Code).

Create a new file and name it hello.py.

Write This Code
python
Copy code
print("Hello, world!")
Run Your Program
In VS Code:

Right-click the editor window → "Run Python File in Terminal"

Or use the terminal:

bash
Copy code
python hello.py
""",
order_in_topic=3
)



ReadingMaterial.objects.create(
    topic="Introduction to Python & IDE Setup",
    subtopic="Python Interpreter and File Structure",
    title="Understanding the Python Interpreter and File Structure",
    content="""
## Python Interpreter and File Structure

The Python interpreter is the program that reads and runs your Python code.

---

### What is the Python Interpreter?

- It executes `.py` files line by line.
- Usually accessed using `python` or `python3` in the terminal.

---

### Common Python File Structure

A basic Python project may look like this:

my_project/
├── main.py
├── helpers.py
└── data/
└── input.txt

- `main.py` – your main program file
- `helpers.py` – contains reusable functions
- `data/` – a folder to store files

---

### Running the Interpreter

You can open the Python interpreter directly in your terminal by typing:

```bash
python
Then type Python commands like:
print("Hello!")
Type exit() or Ctrl+D to leave the interpreter.
""",
order_in_topic=4
)


ReadingMaterial.objects.create(
topic="Introduction to Python & IDE Setup",
subtopic="Running Python in Terminal",
title="Running Python Programs in the Terminal",
content="""

Running Python Programs in the Terminal
You can run your .py files directly from the terminal using the Python interpreter.

Steps to Run:
1.Open your terminal or command prompt.
2.Navigate to the folder where your .py file is saved:

cd path/to/your/folder

3. Run the file using:
python filename.py
Example:
python hello.py
Common Errors
python: command not found → You may need to use python3.

Permission denied → Check file permissions or add execution rights.

""",
order_in_topic=5
)

ReadingMaterial.objects.create(
topic="Introduction to Python & IDE Setup",
subtopic="Using Online Python Interpreters",
title="Trying Python Using Online Interpreters",
content="""
Trying Python Using Online Interpreters
No installation? No problem! You can write and run Python code online.

Recommended Sites
-replit.com
-programiz.com/python-programming/online-compiler
-trinket.io
-pythonanywhere.com

Pros:
Fast and accessible from any device
No setup required
Great for practice and small tests

Cons:
Limited file access
May have internet dependency
""",
order_in_topic=6
)

ReadingMaterial.objects.create(
topic="Introduction to Python & IDE Setup",
subtopic="Setting Up Environment Variables",
title="Setting Up Environment Variables for Python",
content="""
Setting Up Environment Variables for Python
Environment variables help your system locate Python and other tools.

Why It Matters?
When you type python in the terminal, your system checks the PATH variable to find it.
How to Set (Windows):
1.Search for "Environment Variables" in Start Menu.
2.Click "Edit system environment variables".
3.Under System Properties, click Environment Variables.
4.In the System Variables section, find Path, then click Edit.
5.Add the path to your Python installation (e.g., C:\\Python39\
    
    How To Check 
    echo $PATH  # macOS/Linux
    echo %PATH% # Windows
    """,
order_in_topic=7
)

ReadingMaterial.objects.create(
topic="Introduction to Python & IDE Setup",
subtopic="python vs python3 Commands",
title="Difference Between python and python3 Commands",
content="""

Difference Between python and python3
You might see two commands: python and python3. Here's why.

On Windows:
python usually refers to Python 3

Only one version is installed by default

On macOS/Linux:
python often points to Python 2 (legacy)

python3 points to Python 3.x

Best Practice
Use python3 when you're unsure, especially on Mac or Linux:
python3 hello.py

To check versions:
python --version
python3 --version
""",
order_in_topic=8
)