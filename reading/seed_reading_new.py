from django.utils.text import slugify
from django.db import transaction
from content_ingestion.models import Topic as CITopic, Subtopic as CISubtopic, GameZone
from reading.models import ReadingMaterial


def upsert_topic(name: str, zone_order: int = 1) -> CITopic:
    zone, _ = GameZone.objects.get_or_create(
        order=zone_order,
        defaults={"name": "Default", "description": "Default zone"}
    )

    base_slug = slugify(name) or f"topic-{name.lower().replace(' ', '-')}"
    slug = base_slug
    counter = 1
    while CITopic.objects.filter(slug=slug).exclude(name=name).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    topic, created = CITopic.objects.get_or_create(
        slug=slug,
        defaults={"name": name, "zone": zone, "description": name},
    )

    changed = False
    if topic.name != name:
        topic.name = name
        changed = True
    if topic.zone_id is None:
        topic.zone = zone
        changed = True
    if not topic.description:
        topic.description = name
        changed = True
    if changed:
        topic.save(update_fields=["name", "zone", "description"])

    if created:
        print(f"Created Topic: {topic.name}")
    else:
        print(f"Topic exists: {topic.name}")

    return topic


def upsert_subtopic(topic: CITopic, name: str, order_in_topic: int = 0) -> CISubtopic:
    slug = slugify(name) if name else ""
    sub = CISubtopic.objects.filter(topic=topic, slug=slug).first() or \
          CISubtopic.objects.filter(topic=topic, name=name).first()

    if not sub:
        sub = CISubtopic.objects.create(
            topic=topic,
            name=name,
            slug=slug,
            order_in_topic=order_in_topic
        )
        print(f"Created Subtopic: {name} -> {topic.name}")
    else:
        updates = []
        if not sub.slug:
            sub.slug = slug
            updates.append("slug")
        if sub.name != name:
            sub.name = name
            updates.append("name")
        if order_in_topic is not None and sub.order_in_topic != order_in_topic:
            sub.order_in_topic = order_in_topic
            updates.append("order_in_topic")
        if updates:
            sub.save(update_fields=updates)
            print(f"Updated Subtopic: {name} -> {topic.name}")
        else:
            print(f"Subtopic exists: {name} -> {topic.name}")
    return sub


def upsert_material(topic: CITopic, sub: CISubtopic, title: str, content: str, order_in_topic: int = 0):
    obj, created = ReadingMaterial.objects.get_or_create(
        topic_ref=topic,
        subtopic_ref=sub,
        title=title.strip(),
        defaults={
            "content": (content or "").strip(),
            "order_in_topic": order_in_topic or 0,
        },
    )

    if created:
        print(f"Created ReadingMaterial: {title} -> {topic.name}/{sub.name}")
    else:
        changed = False
        if obj.content != (content or "").strip():
            obj.content = (content or "").strip()
            changed = True
        if obj.order_in_topic != (order_in_topic or 0):
            obj.order_in_topic = order_in_topic or 0
            changed = True
        if changed:
            obj.save(update_fields=["content", "order_in_topic"])
            print(f"Updated ReadingMaterial: {title} -> {topic.name}/{sub.name}")
        else:
            print(f"Already up-to-date: {title} -> {topic.name}/{sub.name}")

    return obj


@transaction.atomic
def run():
    # Topic 1 
    t1 = upsert_topic("Introduction to Python & IDE Setup")

    # 1) Installing Python
    st1_1 = upsert_subtopic(t1, "Installing Python", order_in_topic=1)
    upsert_material(
        t1, st1_1, "Installing Python",
"""
## Installing Python

Before you can write Python code, you need to install Python on your machine.

### Windows
1. Go to https://www.python.org/downloads/
2. Download the Windows installer.
3. During installation, check **"Add Python to PATH"**.
4. Click **Install Now**.

### macOS
1) Install Homebrew:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
Install Python:

bash
brew install python
python3 --version
""".strip(),
order_in_topic=1,
)


# 2) Choosing and Setting Up an IDE
    st1_2 = upsert_subtopic(t1, "Choosing and Setting Up an IDE", order_in_topic=2)
    upsert_material(
    t1, st1_2, "Choosing and Setting Up an IDE",
"""
Choosing and Setting Up an IDE
An Integrated Development Environment (IDE) makes it easier to write, test, and debug Python code.

Popular IDEs

VS Code — Lightweight, fast, and highly customizable.

PyCharm — Feature-rich and great for large projects.

Thonny — Designed for beginners; simple and clean.

Jupyter Notebook — Ideal for data science and quick experiments.

Setting Up VS Code (Recommended)
Download: https://code.visualstudio.com/

Install the Python Extension

Open VS Code → Extensions (Ctrl/Cmd+Shift+X)

Search Python

Install the extension by Microsoft

(Optional) Code Runner

Search Code Runner in Extensions

Install (lets you run .py with one click)

Try running a Python file
Create hello.py:


print("Hello, Python!")
""".strip(),
order_in_topic=2,
)

# 3) Writing and Running Your First Python Script
    st1_3 = upsert_subtopic(t1, "Writing and Running Your First Python Script", order_in_topic=3)
    upsert_material(
    t1, st1_3, "Your First Python Program",
"""
Your First Python Program
Create hello.py:


print("Hello, world!")
Run in VS Code
Right-click the editor → Run Python File in Terminal

Or open the terminal and run:

bash

python hello.py   # or: python3 hello.py
""".strip(),
order_in_topic=1,
)

# 4) Python Interpreter and File Structure
    st1_4 = upsert_subtopic(t1, "Python Interpreter and File Structure", order_in_topic=4)
    upsert_material(
    t1, st1_4, "Understanding the Python Interpreter and File Structure",
"""
Python Interpreter and File Structure
The Python interpreter reads and executes your .py files line by line.

Common Project Layout
css

my_project/
├── main.py
├── helpers.py
└── data/
    └── input.txt
main.py — your main program

helpers.py — reusable functions

data/ — assets and inputs

Interactive Interpreter (REPL)
Open in terminal:


python    # or: python3
Then type:


print("Hello!")
Exit with exit() or Ctrl+D.
""".strip(),
order_in_topic=1,
)

# 5) Running Python in Terminal
    st1_5 = upsert_subtopic(t1, "Running Python in Terminal", order_in_topic=5)
    upsert_material(
    t1, st1_5, "Running Python Programs in the Terminal",
"""
Running Python Programs in the Terminal
Open your terminal / command prompt.

Go to your project folder:

bash

cd path/to/your/folder
Run the script:

bash

python filename.py    # or: python3 filename.py
Common errors

python: command not found → try python3

Permission denied → check file permissions or path
""".strip(),
order_in_topic=1,
)

#6) Using Online Python Interpreters
    st1_6 = upsert_subtopic(t1, "Using Online Python Interpreters", order_in_topic=6)
    upsert_material(
    t1, st1_6, "Trying Python Using Online Interpreters",
"""

Trying Python Using Online Interpreters
No installation? You can code online:

https://replit.com

https://www.programiz.com/python-programming/online-compiler

https://trinket.io

https://www.pythonanywhere.com

Pros

Fast and accessible from any device

No setup required

Great for practice and small tests

Cons

Limited file/system access

Requires internet
""".strip(),
order_in_topic=1,
)

#7) Setting Up Environment Variables
    st1_7 = upsert_subtopic(t1, "Setting Up Environment Variables", order_in_topic=7)
    upsert_material(
    t1, st1_7, "Setting Up Environment Variables for Python",
"""

Setting Up Environment Variables for Python
Environment variables (like PATH) help your system find Python and tools.

Why important?
When you type python in the terminal, your OS searches directories listed in PATH.

Check PATH

bash
ƒ
echo $PATH    # macOS/Linux
On Windows (PowerShell)

powershell

echo $Env:Path
Windows: add Python to PATH

Search Environment Variables in the Start Menu.

Click Edit the system environment variables → Environment Variables.

Edit Path (System variables) → New → add your Python path (e.g. C:\\Python39\\).
""".strip(),
order_in_topic=1,
)

#8) python vs python3 Commands
    st1_8 = upsert_subtopic(t1, "python vs python3 Commands", order_in_topic=8)
    upsert_material(
    t1, st1_8, "Difference Between python and python3 Commands",
"""

Difference Between python and python3
Windows

python usually points to Python 3.

macOS/Linux

python may point to legacy Python 2.

python3 points to Python 3.x.

Best practice



python3 hello.py
Check versions

python --version
python3 --version
""".strip(),
order_in_topic=1,
)


# ===================== Topic 2 =====================
    t2 = upsert_topic("Variables and Data Types")

# 1) Declaring Variables in Python
    st2_1 = upsert_subtopic(t2, "Declaring Variables in Python", order_in_topic=1)
    upsert_material(
        t2, st2_1, "Declaring Variables in Python",
    """
Declaring Variables in Python
In Python, variables are created when you assign a value — no need to declare the type.


x = 5
name = "Alice"
price = 19.99
You can reassign freely:


x = 10        # initially an int
x = "ten"     # now a string
Python is dynamically typed (types can change at runtime).
""".strip(),
order_in_topic=1,
)



# 2) Data Types Overview
    st2_2 = upsert_subtopic(t2, "Data Types Overview", order_in_topic=2)
    upsert_material(
    t2, st2_2, "Understanding Python Data Types",
    """
Understanding Python Data Types
Basic Types

int (e.g., 10)

float (e.g., 3.14)

str (e.g., "Hello")

bool (True, False)

Collection Types

list — ordered, mutable (e.g., ["apple", "banana"])

tuple — ordered, immutable (e.g., (10, 20))

set — unordered, unique (e.g., {1, 2, 3})

dict — key-value (e.g., {"name": "John", "age": 30})
""".strip(),
order_in_topic=1,
)

#3) Type Conversion
    st2_3 = upsert_subtopic(t2, "Type Conversion", order_in_topic=3)
    upsert_material(
        t2, st2_3, "Converting Between Data Types",
"""

Converting Between Data Types

x = 5
str_x = str(x)       # int → str  → "5"
float_x = float(x)   # int → float → 5.0
int_str = int("10")  # str → int   → 10
Be careful


int("abc")  # ValueError
""".strip(),
order_in_topic=1,
)


# 4) Constants and Naming Conventions
    st2_4 = upsert_subtopic(t2, "Constants and Naming Conventions", order_in_topic=4)
    upsert_material(
    t2, st2_4, "Using Constants and Variable Naming Rules",
    """
Using Constants and Variable Naming Rules
Python doesn’t enforce constants, but by convention we use uppercase:


PI = 3.14159
MAX_USERS = 100
Naming

variables: lower_snake_case (e.g., user_name)

constants: UPPER_SNAKE_CASE (e.g., TOTAL_SCORE)

must start with a letter or underscore, no spaces, not start with a number
""".strip(),
order_in_topic=1,
)

#5) Using the type() Function
    st2_5 = upsert_subtopic(t2, "Using the type() Function", order_in_topic=5)
    upsert_material(
        t2, st2_5, "Checking Variable Types with type()",
"""

Checking Variable Types with type()

x = 42
print(type(x))       # <class 'int'>

name = "Alice"
print(type(name))    # <class 'str'>
""".strip(),
order_in_topic=1,
)


#6  Booleans and Logical Expressions
    st2_6 = upsert_subtopic(t2, "Booleans and Logical Expressions", order_in_topic=6)
    upsert_material(
        t2, st2_6, "Understanding Booleans and Logical Expressions",
        """
## Booleans and Logical Expressions

```python
x = 5
print(x > 3 and x < 10)  # True
print(not x == 5)        # False
""".strip(),
order_in_topic=1,
)


# 7) Type Checking with isinstance()
    st2_7 = upsert_subtopic(t2, "Type Checking with isinstance()", order_in_topic=7)
    upsert_material(
        t2, st2_7, "Using isinstance() for Type Checking",
    """
Using isinstance() for Type Checking

x = 10
print(isinstance(x, int))      # True

name = "Alice"
print(isinstance(name, str))   # True

data = [1, 2, 3]
print(isinstance(data, list))  # True
""".strip(),
order_in_topic=1,
)



# ===================== Topic 3 =====================
t3 = upsert_topic("Basic Input and Output")

# 1) Using the input() Function
st3_1 = upsert_subtopic(t3, "Using the input() Function", order_in_topic=1)
upsert_material(
    t3, st3_1, "Getting User Input with input()",
    """
Getting User Input with input()
The input() function reads a line from the keyboard.


name = input("What is your name? ")
print("Hello,", name)
Note: input() returns a string.


age = input("Enter your age: ")
print(type(age))  # <class 'str'>
age = int(age)    # convert to number
""".strip(),
order_in_topic=1,
)


# 2) Displaying Output with print()
st3_2 = upsert_subtopic(t3, "Displaying Output with print()", order_in_topic=2)
upsert_material(
    t3, st3_2, "Displaying Output with print()",
    """
Displaying Output with print()


print("Hello, world!")
name = "Alice"; age = 20
print("Name:", name, "Age:", age)
print("A", "B", "C", sep="-")   # A-B-C
print("Hello", end=" "); print("World")  # Hello World
""".strip(),
order_in_topic=1,
)


# 3) Using f-Strings for Formatting
st3_3 = upsert_subtopic(t3, "Using f-Strings for Formatting", order_in_topic=3)
upsert_material(
    t3, st3_3, "Formatting Output with f-Strings",
    """
Formatting Output with f-Strings

name = "John Doe"
age = 21
print(f"My name is {name} and I am {age} years old.")
print(f"In 5 years, I’ll be {age + 5}")
Requires Python 3.6+
""".strip(),
order_in_topic=1,
)


# 4) Escape Characters in Strings
st3_4 = upsert_subtopic(t3, "Escape Characters in Strings", order_in_topic=4)
upsert_material(
    t3, st3_4, "Using Escape Characters in Strings",
    """
Using Escape Characters in Strings
Code	Meaning
\\n	New line
\\t	Tab
\\\"	Double quote
\\\\	Backslash


print("Line 1\\nLine 2")
print("She said: \\\"Hello!\\\"")
print("C:\\\\Users\\\\John Doe")
""".strip(),
order_in_topic=1,
)

# 5) Printing Multiple Lines
st3_5 = upsert_subtopic(t3, "Printing Multiple Lines", order_in_topic=5)
upsert_material(
    t3, st3_5, "Printing Multiple Lines and Line Breaks",
    """
Printing Multiple Lines and Line Breaks

print("This is line one.\\nThis is line two.")
print(\"\"\"This is line one.
This is line two.
This is line three.\"\"\")
print("Line one"); print("Line two"); print("Line three")
""".strip(),
order_in_topic=1,
)


# 6) Multi-line Input and Output
st3_6 = upsert_subtopic(t3, "Multi-line Input and Output", order_in_topic=6)
upsert_material(
    t3, st3_6, "Working with Multi-line I/O",
    """
Working with Multi-line I/O
Multi-line Input (loop)


lines = []
for _ in range(3):
    lines.append(input("Enter a line: "))

print("You entered:")
for line in lines:
    print(line)
Multi-line Output


print(\"\"\"This is
a multi-line
output.\"\"\")
""".strip(),
order_in_topic=1,
)


# 7) Best Practices for User-Friendly I/O
st3_7 = upsert_subtopic(t3, "Best Practices for User-Friendly I/O", order_in_topic=7)
upsert_material(
    t3, st3_7, "Improving User Interaction",
    """
Improving User Interaction
Always add prompts: input("Enter your name: ")

Use clear messages: print("Processing...")

Validate input and provide helpful feedback.

Format output cleanly using f-strings.

name = input("What is your name? ")
print(f"Hello, {name}! Welcome to PyGrounds.")
""".strip(),
order_in_topic=1,
)

# ===================== Topic 4 =====================
t4 = upsert_topic("Operators")

    # 1) Arithmetic Operators
st4_1 = upsert_subtopic(t4, "Arithmetic Operators", order_in_topic=1)
upsert_material(
        t4, st4_1, "Using Arithmetic Operators in Python",
        """
## Using Arithmetic Operators in Python

Arithmetic operators perform basic math.

| Operator | Description             | Example        |
|---------:|-------------------------|----------------|
| `+`      | Addition                | `3 + 2 == 5`   |
| `-`      | Subtraction             | `5 - 1 == 4`   |
| `*`      | Multiplication          | `4 * 2 == 8`   |
| `/`      | Division (float)        | `6 / 2 == 3.0` |
| `//`     | Floor division          | `7 // 2 == 3`  |
| `%`      | Modulus (remainder)     | `7 % 3 == 1`   |
| `**`     | Exponentiation          | `2 ** 3 == 8`  |

```python
a = 10
b = 3
print(a + b)  # 13
print(a % b)  # 1
""".strip(),
order_in_topic=1,
)

# 2) Comparison Operators
st4_2 = upsert_subtopic(t4, "Comparison Operators", order_in_topic=2)
upsert_material(
    t4, st4_2, "Using Comparison Operators in Python",
    """
Using Comparison Operators in Python
Return True/False when comparing values.

Operator	Meaning	Example
==	equal	a == b
!=	not equal	a != b
>	greater than	a > b
<	less than	a < b
>=	greater or equal	a >= b
<=	less or equal	a <= b

x = 5
y = 8
print(x == y)  # False
print(x < y)   # True
""".strip(),
order_in_topic=2,
)

# 3) Assignment Operators
st4_3 = upsert_subtopic(t4, "Assignment Operators", order_in_topic=3)
upsert_material(
    t4, st4_3, "Understanding Assignment Operators",
    """
Understanding Assignment Operators
Assign and/or update a variable.

Operator	Description	Example
=	assign	x = 5
+=	add and assign	x += 2
-=	subtract and assign	x -= 3
*=	multiply and assign	x *= 4
/=	divide and assign	x /= 2
%=	modulo and assign	x %= 3
**=	exponent and assign	x **= 2

x = 10
x += 5
print(x)  # 15
""".strip(),
order_in_topic=3,
)

# 4) Logical Operators
st4_4 = upsert_subtopic(t4, "Logical Operators", order_in_topic=4)
upsert_material(\
    t4, st4_4, "Using Logical Operators in Python",
    """
Using Logical Operators in Python
Combine conditions.

Operator	Description
and	True if both are True
or	True if at least one is True
not	Inverts the boolean value

x = 5
print(x > 2 and x < 10)  # True
print(x < 2 or x > 3)    # True
print(not (x > 4))       # False
""".strip(),
order_in_topic=4,
)

# 5) Operator Precedence
st4_5 = upsert_subtopic(t4, "Operator Precedence", order_in_topic=5)
upsert_material(
    t4, st4_5, "Understanding Operator Precedence",
    """
Understanding Operator Precedence
When multiple operators appear, Python follows precedence rules.

result = 3 + 2 * 5
print(result)  # 13  (multiplication before addition)
High → Low (common ones)

() parentheses

** exponent

* / // %

+ -

Comparisons == != > < >= <=

not

and

or

Use parentheses to be explicit:

result = (3 + 2) * 5  # 25
""".strip(),
order_in_topic=5,
)

# 6) Membership and Identity Operators
st4_6 = upsert_subtopic(t4, "Membership and Identity Operators", order_in_topic=6)
upsert_material(
    t4, st4_6, "Using Membership and Identity Operators in Python",
    """
Membership and Identity Operators in Python
Membership
Operator	Description	Example
in	True if value is found	"a" in "apple"
not in	True if value not found	"x" not in "box"

fruits = ["apple", "banana", "cherry"]
print("apple" in fruits)       # True
print("orange" not in fruits)  # True
Identity
Operator	Description	Example
is	same object in memory	x is y
is not	not the same object	x is not y

a = [1, 2, 3]
b = a
c = [1, 2, 3]
print(a is b)  # True  (same object)
print(a is c)  # False (equal values, different objects)
""".strip(),
order_in_topic=6,
)

# 7) Bitwise Operators
st4_7 = upsert_subtopic(t4, "Bitwise Operators", order_in_topic=7)
upsert_material(
    t4, st4_7, "Introduction to Bitwise Operators (Advanced)",
    """
Introduction to Bitwise Operators (Advanced)
Operate on the bits of integers.

Op	Name	Example	Result
&	AND	5 & 3	1
`	`	OR	`5
^	XOR	5 ^ 3	6
~	NOT	~5	-6
<<	Left shift	5 << 1	10
>>	Right shift	5 >> 1	2

a = 5  # 0101
b = 3  # 0011
print(a & b)  # 1 (0001)
print(a | b)  # 7 (0111)
print(a ^ b)  # 6 (0110)
Optional for beginners; handy in performance/low-level tasks.
""".strip(),
order_in_topic=7,
)

# ===================== Topic 5 =====================
t5 = upsert_topic("Comments & Code Readability")

# 1) Single-line vs Multi-line Comments
st5_1 = upsert_subtopic(t5, "Single-line vs Multi-line Comments", order_in_topic=1)
upsert_material(
    t5, st5_1, "Using Single-line and Multi-line Comments",
    '''
## Using Single-line and Multi-line Comments

Comments explain intent; Python ignores them at runtime.

### Single-line
```python
# This is a comment
print("Hello!")  # Inline comment
Multi-line / Docstring-style
Python has no true block-comment syntax; we often use triple-quoted strings as docstrings:

def f():
    """
    Explain what the function does.
    """
    pass
Best practice: comment why, not just what.
'''.strip(),
order_in_topic=1,
)


# 2) Docstrings and Inline Documentation
st5_2 = upsert_subtopic(t5, "Docstrings and Inline Documentation", order_in_topic=2)
upsert_material(
    t5, st5_2, "Writing Effective Docstrings and Inline Docs",
    '''
## Writing Effective Docstrings and Inline Documentation

**Function docstring**
```python
def greet(name):
    """Greets a user by name."""
    return f"Hello, {name}!"
Inline docs


# Calculate the square of a number
result = 5 ** 2
Use docstrings for APIs (functions/classes/modules) and concise inline comments for tricky logic.
'''.strip(),
order_in_topic=2,
)

# 3) Code Indentation and Block Structure
st5_3 = upsert_subtopic(t5, "Code Indentation and Block Structure", order_in_topic=3)
upsert_material(
    t5, st5_3, "Maintaining Proper Indentation and Blocks",
    '''
## Maintaining Proper Indentation and Blocks

Python uses indentation to define blocks (PEP8: 4 spaces).

**Correct**
```python
if True:
    print("Indented correctly")
else:
    print("Also correctly indented")
Incorrect


if True:
print("This will raise an IndentationError")
'''.strip(),
order_in_topic=3,
)


# 4) Naming Conventions (PEP8 Guidelines)
st5_4 = upsert_subtopic(t5, "Naming Conventions (PEP8 Guidelines)", order_in_topic=4)
upsert_material(
    t5, st5_4, "Following Python Naming Conventions",
    """
Following Python Naming Conventions (PEP8)
Variables/Functions
lower_snake_case

user_name = "Alex"
get_user_input()
Constants
UPPER_SNAKE_CASE


MAX_USERS = 100
Classes
CapitalizedWords


class UserProfile:
    pass
""".strip(),
order_in_topic=4,
)


# 5) Structuring Code for Readability
st5_5 = upsert_subtopic(t5, "Structuring Code for Readability", order_in_topic=5)
upsert_material(
    t5, st5_5, "Organizing Code for Better Readability",
    """
Organizing Code for Better Readability
Break code into functions

Group related lines

Add whitespace between sections


# Load data
data = [1, 2, 3]

# Process data
squared = [x**2 for x in data]

# Output result
print(squared)
""".strip(),
order_in_topic=5,
)


# 6) Avoiding Magic Numbers and Hardcoding
st5_6 = upsert_subtopic(t5, "Avoiding Magic Numbers and Hardcoding", order_in_topic=6)
upsert_material(
    t5, st5_6, "Avoiding Magic Numbers and Hardcoded Values",
    """
Avoiding Magic Numbers and Hardcoded Values
Bad

price = 100
discount = price * 0.2  # What does 0.2 mean?
Better


DISCOUNT_RATE = 0.2
discount = price * DISCOUNT_RATE
Name important numbers/strings to make intent clear.
""".strip(),
order_in_topic=6,
)

# 7) Writing Self-Documenting Code
st5_7 = upsert_subtopic(t5, "Writing Self-Documenting Code", order_in_topic=7)
upsert_material(
    t5, st5_7, "Writing Clear and Self-Documenting Code",
    """
Writing Clear and Self-Documenting Code
Code should be understandable without extra comments.

Bad


a = 10
b = a * 12.5
Good


monthly_salary = 10
annual_salary = monthly_salary * 12.5
Use descriptive names for variables and functions.
""".strip(),
order_in_topic=7,
)


# ===================== Topic 6 =====================
t6 = upsert_topic("Conditional Statements")

# 1) if Statement Syntax and Structure
st6_1 = upsert_subtopic(t6, "if Statement Syntax and Structure", order_in_topic=1)
upsert_material(
    t6, st6_1, "Using Basic if Statements",
    """
Using Basic if Statements

if condition:
    # code block
Example:


age = 18
if age >= 18:
    print("You are an adult.")
Indentation defines the code block.
""".strip(),
order_in_topic=1,
)

# 2) if-else and elif Ladder
st6_2 = upsert_subtopic(t6, "if-else and elif Ladder", order_in_topic=2)
upsert_material(
    t6, st6_2, "Creating if-else and elif Chains",
    """
Creating if-else and elif Chains

score = 75

if score >= 90:
    print("Grade: A")
elif score >= 80:
    print("Grade: B")
elif score >= 70:
    print("Grade: C")
else:
    print("Grade: D or below")
Checked top-to-bottom; the first True branch runs.
""".strip(),
order_in_topic=2,
)

# 3) Nested Conditional Statements
st6_3 = upsert_subtopic(t6, "Nested Conditional Statements", order_in_topic=3)
upsert_material(
    t6, st6_3, "Writing Nested Conditions",
    """
Writing Nested Conditions

x = 10
y = 5

if x > 0:
    if y > 0:
        print("Both x and y are positive.")
Keep indentation clear to avoid confusion.
""".strip(),
order_in_topic=3,
)


# 4) Boolean Logic in Conditions
st6_4 = upsert_subtopic(t6, "Boolean Logic in Conditions", order_in_topic=4)
upsert_material(
    t6, st6_4, "Using Boolean Logic (and, or, not)",
    """
Using Boolean Logic (and, or, not)

age = 20
has_id = True

if age >= 18 and has_id:
    print("Allowed to enter.")
Use parentheses to group complex expressions.
""".strip(),
order_in_topic=4,
)

# 5) Ternary Operators (One-liner conditionals)
st6_5 = upsert_subtopic(t6, "Ternary Operators (One-liner conditionals)", order_in_topic=5)
upsert_material(
    t6, st6_5, "Using Ternary Operators in Python",
    """
Using Ternary Operators in Python
Syntax


value_if_true if condition else value_if_false
Example:

age = 17
status = "Adult" if age >= 18 else "Minor"
print(status)
""".strip(),
order_in_topic=5,
)


# 6) Using Conditions with Input
st6_6 = upsert_subtopic(t6, "Using Conditions with Input", order_in_topic=6)
upsert_material(
    t6, st6_6, "Combining Conditions with User Input",
    """
Combining Conditions with User Input

age = int(input("Enter your age: "))
if age >= 18:
    print("Access granted.")
else:
    print("Access denied.")
Always convert input to the correct type before comparing.
""".strip(),
order_in_topic=6,
)


# 7) Common Logic Pitfalls and Debugging
st6_7 = upsert_subtopic(t6, "Common Logic Pitfalls and Debugging", order_in_topic=7)
upsert_material(
    t6, st6_7, "Common Mistakes in Conditional Logic",
    """
Common Mistakes in Conditional Logic
Mistake 1: Using = instead of ==


# if x = 5:   # assignment! (SyntaxError)
if x == 5:
    ...
Mistake 2: Forgetting indentation


if x > 0:
print("Positive")  
# Fix:
if x > 0:
    print("Positive")
Mistake 3: Complex logic without parentheses

# May behave unexpectedly:
if x > 5 or x < 2 and y == 3:
    ...

# Clearer:
if (x > 5 or x < 2) and y == 3:
    ...
Test your logic and use print() to debug if needed.
""".strip(),
order_in_topic=7,
)

# ===================== Topic 7 =====================
t7 = upsert_topic("Error Handling")

# 1) Understanding Common Runtime Errors
st7_1 = upsert_subtopic(t7, "Understanding Common Runtime Errors", order_in_topic=1)
upsert_material(
    t7, st7_1, "What Are Runtime Errors in Python?",
    '''
## What Are Runtime Errors in Python?

Runtime errors happen **while the program is running** and will crash your app unless handled.

**Common examples**
- `ZeroDivisionError` — dividing by zero
- `NameError` — using an undefined variable
- `TypeError` — wrong data types mixed
- `IndexError` — invalid list index

**Example**
```python
number = 10
print(number / 0)  # ZeroDivisionError
We fix these with try/except, next.
'''.strip(),
order_in_topic=1,
)

#2) Try-Except Block Structure
st7_2 = upsert_subtopic(t7, "Try-Except Block Structure", order_in_topic=2)
upsert_material(
t7, st7_2, "Using try-except to Handle Errors",
'''

Using try-except to Handle Errors
Syntax:

try:
    # code that may fail
except SomeError:
    # how to handle it
Example

try:
    result = 10 / 0
except ZeroDivisionError:
    print("You can't divide by zero!")
'''.strip(),
order_in_topic=1,
)

#3) Catching Multiple Exceptions
st7_3 = upsert_subtopic(t7, "Catching Multiple Exceptions", order_in_topic=3)
upsert_material(
t7, st7_3, "Handling Multiple Exceptions",
'''

Handling Multiple Exceptions
Separate handlers:

try:
    x = int("abc")
except ValueError:
    print("Invalid number!")
except TypeError:
    print("Wrong type!")
Group related ones:

try:
    risky()
except (ValueError, TypeError):
    print("An error occurred.")
'''.strip(),
order_in_topic=1,
)

#4) else and finally Clauses in Error Handling
st7_4 = upsert_subtopic(t7, "else and finally Clauses in Error Handling", order_in_topic=4)
upsert_material(
t7, st7_4, "else and finally in try-except Blocks",
'''

else and finally in try/except
else: runs only if no exception occurred

finally: runs always (cleanup)


try:
    x = 5
    print(x / 1)
except ZeroDivisionError:
    print("Can't divide by zero.")
else:
    print("Division successful.")
finally:
    print("Finished!")
Use finally to close files / release resources.
'''.strip(),
order_in_topic=1,
)

#5) Raising Custom Exceptions
st7_5 = upsert_subtopic(t7, "Raising Custom Exceptions", order_in_topic=5)
upsert_material(
t7, st7_5, "Raising Your Own Exceptions",
'''

Raising Your Own Exceptions
Use raise to signal invalid states.

def withdraw(amount):
    if amount < 0:
        raise ValueError("Amount must be positive.")
You can also define custom classes by subclassing Exception.
'''.strip(),
order_in_topic=1,
)

#6) Using assert Statements
st7_6 = upsert_subtopic(t7, "Using assert Statements", order_in_topic=6)
upsert_material(
t7, st7_6, "Using assert for Quick Checks",
'''

Using assert for Quick Checks
assert condition, "message" raises AssertionError if the condition is false.

age = 18
assert age >= 0, "Age cannot be negative"
Great for internal invariants during development (not user input validation).
'''.strip(),
order_in_topic=1,
)

#7) Error Messages and Debugging Tools
st7_7 = upsert_subtopic(t7, "Error Messages and Debugging Tools", order_in_topic=7)
upsert_material(
t7, st7_7, "Reading Error Messages and Debugging",
'''

Reading Error Messages and Debugging
Understand the traceback to locate the exact failing line:


Traceback (most recent call last):
  File "main.py", line 2, in <module>
    print(10 / 0)
ZeroDivisionError: division by zero
Helpful tools

print() tracing

IDE breakpoints / step-through

pdb module (interactive debugger)
'''.strip(),
order_in_topic=1,
)

#===================== Topic 8 =====================
t8 = upsert_topic("Loops")

#1) for Loop with range()
st8_1 = upsert_subtopic(t8, "for Loop with range()", order_in_topic=1)
upsert_material(
t8, st8_1, "Using for Loops with range()",
'''

for with range()
Repeat actions a set number of times.


for i in range(5):
    print(i)    # 0..4
'''.strip(),
order_in_topic=1,
)

#2) Iterating Over Lists, Tuples, and Strings
st8_2 = upsert_subtopic(t8, "Iterating Over Lists, Tuples, and Strings", order_in_topic=2)
upsert_material(
t8, st8_2, "Looping Through Collections",
'''

Looping Through Collections

fruits = ['apple', 'banana', 'cherry']
for fruit in fruits:
    print(fruit)

for ch in "hello":
    print(ch)
'''.strip(),
order_in_topic=1,
)

#3) while Loop and Loop Conditions
st8_3 = upsert_subtopic(t8, "while Loop and Loop Conditions", order_in_topic=3)
upsert_material(
t8, st8_3, "Using while Loops",
'''

while Loops
Run while a condition stays true.


i = 0
while i < 3:
    print(i)
    i += 1
Avoid infinite loops—ensure the condition eventually becomes False.
'''.strip(),
order_in_topic=1,
)

#4) break, continue, and pass Statements
st8_4 = upsert_subtopic(t8, "break, continue, and pass Statements", order_in_topic=4)
upsert_material(
t8, st8_4, "Controlling Loops",
'''

break, continue, and pass

for i in range(5):
    if i == 3:
        break      # stop loop
    if i == 1:
        continue   # skip this iteration
    pass           # placeholder
    print(i)
'''.strip(),
order_in_topic=1,
)

#5) Looping with enumerate() and zip()
st8_5 = upsert_subtopic(t8, "Looping with enumerate() and zip()", order_in_topic=5)
upsert_material(
t8, st8_5, "Advanced Looping Tools",
'''

enumerate() and zip()

for idx, val in enumerate(['a','b']):
    print(idx, val)

names = ['Ana', 'Bob']
ages  = [20, 25]
for name, age in zip(names, ages):
    print(name, age)
'''.strip(),
order_in_topic=1,
)

#6) Infinite Loops and Loop Safety
st8_6 = upsert_subtopic(t8, "Infinite Loops and Loop Safety", order_in_topic=6)
upsert_material(
t8, st8_6, "Avoiding Infinite Loops",
'''

Avoiding Infinite Loops

while True:
    # ...
    break  # or condition to exit
Stop with Ctrl+C in terminal or ensure a proper exit condition.
'''.strip(),
order_in_topic=1,
)

#7) Comparing for and while Loops
st8_7 = upsert_subtopic(t8, "Comparing for and while Loops", order_in_topic=7)
upsert_material(
t8, st8_7, "Choosing Between for and while",
'''

Choosing Between for and while
Use for for a known count, while for state-based loops.


for i in range(3):
    print(i)

i = 0
while i < 3:
    print(i)
    i += 1
'''.strip(),
order_in_topic=1,
)

# ===================== Topic 9 =====================
t9 = upsert_topic("Nested Loops")

st9_1 = upsert_subtopic(t9, "Syntax of Nested for Loops", order_in_topic=1)
upsert_material(
    t9, st9_1, "Basic Nested for Loops",
    '''
## Basic Nested `for` Loops

Run an inner loop for each iteration of the outer loop.

```python
for i in range(2):
    for j in range(3):
        print(i, j)
'''.strip(),
order_in_topic=1,
)

st9_2 = upsert_subtopic(t9, "Nested while and Mixed Loops", order_in_topic=2)
upsert_material(
t9, st9_2, "Mixing Nested Loops",
'''

Mixing Nested Loops
You can nest while inside for, or vice-versa.


i = 0
while i < 2:
    for j in range(2):
        print(i, j)
    i += 1
'''.strip(),
order_in_topic=1,
)

st9_3 = upsert_subtopic(t9, "Printing Patterns (e.g., triangle, pyramid)", order_in_topic=3)
upsert_material(
t9, st9_3, "Pattern Printing with Nested Loops",
'''

Pattern Printing with Nested Loops

for i in range(1, 6):
    print('*' * i)
'''.strip(),
order_in_topic=1,
)

st9_4 = upsert_subtopic(t9, "Matrix Traversal and Processing", order_in_topic=4)
upsert_material(
t9, st9_4, "Working with Matrices",
'''

Working with Matrices

matrix = [[1, 2], [3, 4]]
for row in matrix:
    for val in row:
        print(val)
'''.strip(),
order_in_topic=1,
)

st9_5 = upsert_subtopic(t9, "Loop Depth and Performance Considerations", order_in_topic=5)
upsert_material(
t9, st9_5, "Performance of Deeply Nested Loops",
'''

Performance of Deeply Nested Loops
More nesting → more time. Keep loops shallow when possible and look for algorithmic optimizations.
'''.strip(),
order_in_topic=1,
)

st9_6 = upsert_subtopic(t9, "Managing Inner vs Outer Loop Variables", order_in_topic=6)
upsert_material(
t9, st9_6, "Handling Variables in Nested Loops",
'''

Handling Variables in Nested Loops
Use clear names to avoid confusion.

for row in range(3):
    for col in range(2):
        print(f"Row {row}, Col {col}")
'''.strip(),
order_in_topic=1,
)

st9_7 = upsert_subtopic(t9, "Avoiding Logical Errors in Nested Structures", order_in_topic=7)
upsert_material(
t9, st9_7, "Common Mistakes in Nested Loops",
'''

Common Mistakes in Nested Loops
Resetting counters inside loops by accident

Misplaced indentations

Using the wrong loop variable

Always test your nested logic carefully.
'''.strip(),
order_in_topic=1,
)

#===================== Topic 10 =====================
t10 = upsert_topic("Strings & String Methods")

st10_1 = upsert_subtopic(t10, "String Indexing and Slicing", order_in_topic=1)
upsert_material(
t10, st10_1, "Accessing and Slicing Strings",
'''

Accessing and Slicing Strings

text = "Python"
print(text[0])    # P
print(text[1:4])  # yth
Indexing starts at 0. Negative indexes count from the end.
'''.strip(),
order_in_topic=1,
)

st10_2 = upsert_subtopic(t10, "String Immutability", order_in_topic=2)
upsert_material(
t10, st10_2, "Understanding String Immutability",
'''

String Immutability
Strings can’t be changed in place.

text = "hello"
# text[0] = "H"  # error
text = "H" + text[1:]
'''.strip(),
order_in_topic=1,
)

st10_3 = upsert_subtopic(t10, "Case Conversion Methods (lower(), upper(), etc.)", order_in_topic=3)
upsert_material(
t10, st10_3, "Changing String Case",
'''

Changing String Case

name = "Alice"
print(name.upper())  # ALICE
print(name.lower())  # alice
'''.strip(),
order_in_topic=1,
)

st10_4 = upsert_subtopic(t10, "Searching and Replacing Text", order_in_topic=4)
upsert_material(
t10, st10_4, "Find and Replace in Strings",
'''

Find and Replace in Strings

msg = "hello world"
print(msg.find("world"))                 # 6
print(msg.replace("world", "Python"))    # hello Python
'''.strip(),
order_in_topic=1,
)

st10_5 = upsert_subtopic(t10, "String Splitting and Joining", order_in_topic=5)
upsert_material(
t10, st10_5, "Split and Join Strings",
'''

Split and Join Strings

sentence = "a b c"
parts = sentence.split(" ")    # ['a','b','c']
print("-".join(parts))         # a-b-c
'''.strip(),
order_in_topic=1,
)

st10_6 = upsert_subtopic(t10, "Validating and Cleaning Input Strings", order_in_topic=6)
upsert_material(
t10, st10_6, "Input Validation with Strings",
'''

Input Validation with Strings

name = " Alice "
print(name.strip())            # "Alice"
print(name.strip().isalpha())  # True
'''.strip(),
order_in_topic=1,
)

st10_7 = upsert_subtopic(t10, "Escape Sequences and Raw Strings", order_in_topic=7)
upsert_material(
t10, st10_7, "Working with Escape Sequences",
'''

Escape Sequences and Raw Strings

print("Hello\\nWorld")
path = r"C:\\Users\\Name"
print(path)
'''.strip(),
order_in_topic=1,
)

#===================== Topic 11 =====================
t11 = upsert_topic("Lists & Tuples")

st11_1 = upsert_subtopic(t11, "Creating and Modifying Lists", order_in_topic=1)
upsert_material(
t11, st11_1, "Creating Lists in Python",
'''

Creating Lists in Python

fruits = ["apple", "banana"]
fruits.append("cherry")
print(fruits)  # ['apple', 'banana', 'cherry']
'''.strip(),
order_in_topic=1,
)

st11_2 = upsert_subtopic(t11, "List Methods (append(), remove(), sort(), etc.)", order_in_topic=2)
upsert_material(
t11, st11_2, "Common List Methods",
'''

Common List Methods

nums = [3, 1, 2]
nums.append(5)
nums.remove(1)
nums.sort()
print(nums)  # [2, 3, 5]
'''.strip(),
order_in_topic=1,
)

st11_3 = upsert_subtopic(t11, "List Indexing, Slicing, and Comprehension", order_in_topic=3)
upsert_material(
t11, st11_3, "Advanced List Access",
'''

Advanced List Access

numbers = [1,2,3,4]
print(numbers[1:3])            # [2, 3]
squares = [x*x for x in numbers]
'''.strip(),
order_in_topic=1,
)

st11_4 = upsert_subtopic(t11, "Tuples and Their Immutability", order_in_topic=4)
upsert_material(
t11, st11_4, "Working with Tuples",
'''

Working with Tuples

point = (3, 4)
print(point[0])  # 3
Tuples are immutable (can’t be changed).
'''.strip(),
order_in_topic=1,
)

st11_5 = upsert_subtopic(t11, "Tuple Unpacking and Multiple Assignment", order_in_topic=5)
upsert_material(
t11, st11_5, "Unpacking Tuples",
'''

Unpacking Tuples

x, y = (1, 2)
print(x, y)  # 1 2
'''.strip(),
order_in_topic=1,
)

st11_6 = upsert_subtopic(t11, "Iterating Through Lists and Tuples", order_in_topic=6)
upsert_material(
t11, st11_6, "Looping Over Lists and Tuples",
'''

Looping Over Lists and Tuples

colors = ["red", "blue"]
for color in colors:
    print(color)
'''.strip(),
order_in_topic=1,
)

st11_7 = upsert_subtopic(t11, "When to Use Lists vs Tuples", order_in_topic=7)
upsert_material(
t11, st11_7, "Choosing Between Lists and Tuples",
'''

Choosing Between Lists and Tuples
Use lists when you need to modify data.

Use tuples when data should be constant (read-only).
'''.strip(),
order_in_topic=1,
)

#===================== Topic 12 =====================
t12 = upsert_topic("Sets")

st12_1 = upsert_subtopic(t12, "Creating and Using Sets", order_in_topic=1)
upsert_material(
t12, st12_1, "Working with Sets",
'''

Working with Sets
Unordered collections with no duplicates.

my_set = {1, 2, 3, 3}
print(my_set)  # {1, 2, 3}
'''.strip(),
order_in_topic=1,
)

st12_2 = upsert_subtopic(t12, "Set Operations (union, intersection, difference, etc.)", order_in_topic=2)
upsert_material(
t12, st12_2, "Set Math Operations",
'''

Set Operations

a = {1, 2, 3}
b = {2, 3, 4}
print(a | b)   # union        -> {1,2,3,4}
print(a & b)   # intersection -> {2,3}
print(a - b)   # difference   -> {1}
'''.strip(),
order_in_topic=1,
)

st12_3 = upsert_subtopic(t12, "Set Methods (add(), remove(), etc.)", order_in_topic=3)
upsert_material(
t12, st12_3, "Modifying Sets",
'''

Modifying Sets

s = set()
s.add(5)
s.remove(5)
'''.strip(),
order_in_topic=1,
)

st12_4 = upsert_subtopic(t12, "Working with Duplicates and Membership", order_in_topic=4)
upsert_material(
t12, st12_4, "Membership and Uniqueness",
'''

Membership and Uniqueness

s = {1, 2, 3}
print(2 in s)  # True
'''.strip(),
order_in_topic=1,
)

st12_5 = upsert_subtopic(t12, "Frozen Sets and Hashing", order_in_topic=5)
upsert_material(
t12, st12_5, "Frozen Sets",
'''

Frozen Sets
Immutable sets:

fs = frozenset([1, 2, 3])
Useful as dict keys or set members.
'''.strip(),
order_in_topic=1,
)

st12_6 = upsert_subtopic(t12, "Performance Benefits of Sets", order_in_topic=6)
upsert_material(
t12, st12_6, "Efficiency of Sets",
'''

Efficiency of Sets
Membership tests in sets are typically O(1) (faster than lists’ O(n)).
'''.strip(),
order_in_topic=1,
)

st12_7 = upsert_subtopic(t12, "Converting Between Sets and Other Types", order_in_topic=7)
upsert_material(
t12, st12_7, "Converting Sets",
'''

Converting Sets

s = set([1, 2, 3])
l = list(s)
t = tuple(s)
'''.strip(),
order_in_topic=1,
)


# ===================== Topic 13 =====================
t13 = upsert_topic("Functions")

st13_1 = upsert_subtopic(t13, "Defining Functions with def", order_in_topic=1)
upsert_material(
    t13, st13_1, "Creating a Function",
    '''
## Creating a Function

Use `def` to define functions.

```python
def greet():
    print("Hello")
'''.strip(),
order_in_topic=1,
)

st13_2 = upsert_subtopic(t13, "Parameters, Arguments, and Return Values", order_in_topic=2)
upsert_material(
t13, st13_2, "Function Inputs and Outputs",
'''

Function Inputs and Outputs
Functions can take inputs (parameters) and return values.

def add(a, b):
    return a + b
'''.strip(),
order_in_topic=1,
)

st13_3 = upsert_subtopic(t13, "Variable Scope and global/nonlocal", order_in_topic=3)
upsert_material(
t13, st13_3, "Understanding Scope",
'''

Understanding Scope
Variables inside functions are local.
Use global or nonlocal to modify outer variables.

x = 10
def change():
    global x
    x = 5
'''.strip(),
order_in_topic=1,
)

st13_4 = upsert_subtopic(t13, "Default and Keyword Arguments", order_in_topic=4)
upsert_material(
t13, st13_4, "Optional Parameters",
'''

Optional Parameters
Functions can have default values and keyword arguments.

def greet(name="Guest"):
    print(f"Hello, {name}")
'''.strip(),
order_in_topic=1,
)

st13_5 = upsert_subtopic(t13, "Docstrings and Function Annotations", order_in_topic=5)
upsert_material(
t13, st13_5, "Documenting Functions",
'''

Documenting Functions
Use docstrings to explain purpose, and annotations for type hints.

def greet():
    """This greets the user."""
    print("Hi")

def add(a: int, b: int) -> int:
    return a + b
'''.strip(),
order_in_topic=1,
)

st13_6 = upsert_subtopic(t13, "Lambda Functions and Anonymous Functions", order_in_topic=6)
upsert_material(
t13, st13_6, "Using Lambda Functions",
'''

Using Lambda Functions
Short, inline functions.

add = lambda x, y: x + y
print(add(2, 3))
'''.strip(),
order_in_topic=1,
)

st13_7 = upsert_subtopic(t13, "Higher-Order Functions and Functional Programming Basics", order_in_topic=7)
upsert_material(
t13, st13_7, "Advanced Functional Tools",
'''

Advanced Functional Tools
map(), filter(), reduce() consume functions.

nums = [1, 2, 3]
squares = list(map(lambda x: x**2, nums))
'''.strip(),
order_in_topic=1,
)

#===================== Topic 14 =====================
t14 = upsert_topic("Dictionaries")

st14_1 = upsert_subtopic(t14, "Creating and Accessing Dictionary Items", order_in_topic=1)
upsert_material(
t14, st14_1, "Using Dictionaries",
'''

Using Dictionaries
Key–value storage.

person = {"name": "Alice", "age": 25}
print(person["name"])
'''.strip(),
order_in_topic=1,
)

st14_2 = upsert_subtopic(t14, "Adding, Updating, and Deleting Keys", order_in_topic=2)
upsert_material(
t14, st14_2, "Modifying Dictionaries",
'''

Modifying Dictionaries
Add, change, or delete key–value pairs.

person = {"name": "Alice", "age": 25}
person["city"] = "Cebu"
del person["age"]
'''.strip(),
order_in_topic=1,
)

st14_3 = upsert_subtopic(t14, "Looping Through Keys, Values, and Items", order_in_topic=3)
upsert_material(
t14, st14_3, "Iterating Over Dictionaries",
'''

Iterating Over Dictionaries

for key, value in person.items():
    print(key, value)
'''.strip(),
order_in_topic=1,
)

st14_4 = upsert_subtopic(t14, "Dictionary Methods (get(), pop(), update(), etc.)", order_in_topic=4)
upsert_material(
t14, st14_4, "Common Dictionary Methods",
'''

Common Dictionary Methods

person.get("name")
person.pop("city", None)
person.update({"age": 30})
'''.strip(),
order_in_topic=1,
)

st14_5 = upsert_subtopic(t14, "Nesting Dictionaries", order_in_topic=5)
upsert_material(
t14, st14_5, "Nested Dictionaries",
'''

Nested Dictionaries

students = {
    "A": {"math": 90},
    "B": {"math": 85}
}
'''.strip(),
order_in_topic=1,
)

st14_6 = upsert_subtopic(t14, "Using Dictionaries for Counting (e.g., frequency maps)", order_in_topic=6)
upsert_material(
t14, st14_6, "Dictionaries as Counters",
'''

Dictionaries as Counters

text = "hello"
freq = {}
for char in text:
    freq[char] = freq.get(char, 0) + 1
'''.strip(),
order_in_topic=1,
)

st14_7 = upsert_subtopic(t14, "Dictionary Comprehensions", order_in_topic=7)
upsert_material(
t14, st14_7, "Comprehensions with Dictionaries",
'''

Comprehensions with Dictionaries

squares = {x: x**2 for x in range(5)}
'''.strip(),
order_in_topic=1,
)

if __name__ == "__main__":
    run()
 