from reading.models import ReadingMaterial

## topic 1
ReadingMaterial.objects.get_or_create(    
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

ReadingMaterial.objects.get_or_create(   
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

ReadingMaterial.objects.get_or_create(   
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

print("Hello, world!")
Run Your Program
In VS Code:

Right-click the editor window → "Run Python File in Terminal"

Or use the terminal:


python hello.py
""",
order_in_topic=3
)


ReadingMaterial.objects.get_or_create(   
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


ReadingMaterial.objects.get_or_create(   
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

ReadingMaterial.objects.get_or_create(   
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

ReadingMaterial.objects.get_or_create(   
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

ReadingMaterial.objects.get_or_create(   
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

##topic 2
ReadingMaterial.objects.get_or_create(   
    topic="Variables and Data Types",
    subtopic="Declaring Variables in Python",
    title="Declaring Variables in Python",
    content="""
## Declaring Variables in Python

In Python, variables are created when you assign a value to them — no need to declare the data type.

---

### Example:


x = 5
name = "Alice"
price = 19.99

You can assign any value to a variable, and Python automatically detects its type.

Reassigning Variables: 

x = 10        #Initially an integer
x = "ten"     # Now it's a string

Pyhton is dynamically typed, meaning variable types can change at runtime. """,

order_in_topic =1
)

ReadingMaterial.objects.get_or_create(   
topic="Variables and Data Types",
subtopic="Data Types Overview",
title="Understanding Python Data Types",
content="""

Understanding Python Data Types
Python has several built-in data types. Here are the most common:


Basic Types: 
int -> Whole numbers (example 10)
float -> Decimal number (example: 3.14)
str -> Text (example "Hello")
bool -> Boolean values (True, False)

Collection Tyoes:
list -> Ordered, changeable, allows duplicates
Example: fruits = ["apple", "banana"]
tuple -> Ordered, unchangeable, allows duplicates
Example: coords = (10, 20)

set -> Unordered, no duplicates
Example: unique_nums = {1, 2, 3}

dict -> Key-value pairs 
Example: person = {"name": "John", "age": 30}
""",
order_in_topic=2
)

ReadingMaterial.objects.get_or_create(   
topic="Variables and Data Types",
subtopic="Type Conversion",
title="Converting Between Data Types",
content="""


Converting Between Data Types
You can convert from one data type to another using Python's built-in functions.

Common Conversions:
x = 5
str_x = str(x)      # Converts int to string → "5"
float_x = float(x)  # Converts int to float → 5.0
int_str = int("10")  # Converts string to int → 10

Be Careful:
Not all conversions are valid:
int("abc")  # Error!

""",
order_in_topic=3
)

ReadingMaterial.objects.get_or_create(   
topic="Variables and Data Types",
subtopic="Constants and Naming Conventions",
title="Using Constants and Variable Naming Rules",
content="""

Using Constants and Variable Naming Rules
Python doesn't have built-in constant support, but by convention, uppercase variable names are treated as constants.

Example:
PI = 3.14159
MAX_USERS = 100

Naming Conventions:  
-Use lowercase letters and underscores for variables: user_name

-Constants should be in uppercase: TOTAL_SCORE

-Variable names must:
 Start with a letter or underscore

Not start with a number

Not contain spaces
""",
order_in_topic=4
)

ReadingMaterial.objects.get_or_create(   
topic="Variables and Data Types",
subtopic="Using the type() Function",
title="Checking Variable Types with type()",
content="""

Checking Variable Types with type()
The type() function lets you check what data type a variable holds.

Example:

x = 42
print(type(x))       # <class 'int'>

name = "Alice"
print(type(name))    # <class 'str'>

This is useful for debugging and understanding your data.
""",
order_in_topic=5
)

ReadingMaterial.objects.get_or_create(   
    topic="Variables and Data Types",
    subtopic="Booleans and Logical Expressions",
    title="Understanding Booleans and Logical Expressions",
    content="""
## Understanding Booleans and Logical Expressions

Booleans represent **True** or **False** values in Python.

---

### Boolean Values:


is_student = True
has_paid = False
They are commonly used in conditions and logic.
Logical Expressions:
Logical expressions combine comparisons and return boolean results.

Examples:
age = 20
print(age > 18)       # True
print(age < 18)       # False

You can also combine them using logical operators:

x = 5
print(x > 3 and x < 10)   # True
print(not x == 5)         # False

""",
order_in_topic=6
)
ReadingMaterial.objects.get_or_create(   
    topic="Variables and Data Types",
    subtopic="Type Checking with isinstance()",
    title="Using isinstance() for Type Checking",
    content="""
## Using isinstance() for Type Checking

The `isinstance()` function checks if a variable is a specific type.


Syntax:


isinstance(variable, type)

Examples:
x = 10
print(isinstance(x, int))      # True

name = "Alice"
print(isinstance(name, str))   # True

data = [1, 2, 3]
print(isinstance(data, list))  # True

This is helpful when validating input or writing conditional logic based on types.
""",
order_in_topic=7
)

##topic 3
ReadingMaterial.objects.get_or_create(   
    topic="Basic Input and Output",
    subtopic="Using the input() Function",
    title="Getting User Input with input()",
    content="""
## Getting User Input with `input()`

The `input()` function allows you to get input from the user through the keyboard.

---

### Basic Example:


name = input("What is your name? ")
print("Hello,", name)


The text inside input() is called a prompt — it shows up before the user types.



Note:
All input is treated as a string by default:

age = input("Enter your age: ")
print(type(age))  # <class 'str'>

To convert to number:

age = int(age)

""",
order_in_topic=1
)
## Subtopic 2: Displaying Output with print()

ReadingMaterial.objects.get_or_create(   
topic="Basic Input and Output",
subtopic="Displaying Output with print()",
title="Displaying Output with print()",
content="""

Displaying Output with print()
The print() function shows text or variable values in the output (usually the terminal).

Basic Usage:

print("Hello, world!")

You can also print multiple items:

name = "Alice"
age = 20
print("Name:", name, "Age:", age)

Print with separator:

print("A", "B", "C", sep="-") 

Print with end:

print("Hello", end=" ")
print("World")  ##Output: Hello World

""",
order_in_topic=2
)

ReadingMaterial.objects.get_or_create(   
topic="Basic Input and Output",
subtopic="Using f-Strings for Formatting",
title="Formatting Output with f-Strings",
content="""
Formatting Output with f-Strings
f-strings make it easy to include variables inside strings.
Example:
name = "John Doe"
age = 21

print(f"My name is {name} and I am {age} years old.")

You can also do inline expressions:
print(f"In 5 years, I’ll be {age + 5}")

f-Strings require Python 3.6 or higher.
""",
order_in_topic=3
)


ReadingMaterial.objects.get_or_create(   
topic="Basic Input and Output",
subtopic="Escape Characters in Strings",
title="Using Escape Characters in Strings",
content="""

Using Escape Characters in Strings
Escape characters let you add special characters inside a string.
Common Escape Characters:

Code                        Meaning
\\n                         New Line
\\t                         Tab
\\\"                        Double qoute
\\\\                        Backslash

Examples:

print("Line 1\\nLine 2")
print("She said: \\\"Hello!\\\"")
print("C:\\\\Users\\\\John Doe)
""",
order_in_topic=4
)

ReadingMaterial.objects.get_or_create(   
topic="Basic Input and Output",
subtopic="Printing Multiple Lines",
title="Printing Multiple Lines and Line Breaks",
content="""

Printing Multiple Lines and Line Breaks
There are a few ways to print multiple lines in Python.
Using \\n (newline):
print("This is line one.\\nThis is line two.")

Using triple quotes:
print(\"\"\"This is line one.
This is line two.
This is line three.\"\"\")

Using multiple print() calls:
print("Line one")
print("Line two")
print("Line three")

""",
order_in_topic=5
)

ReadingMaterial.objects.get_or_create(
    topic="Basic Input and Output",
    subtopic="Multi-line Input and Output",
    title="Working with Multi-line I/O",
    content="""
Sometimes, you may need to collect or display multiple lines of text.

### Multi-line Input:
You can use a loop or special characters to capture multiple lines.

Example using a loop:
lines = []
for _ in range(3):
    lines.append(input("Enter a line: "))

print("You entered:")
for line in lines:
    print(line)

### Multi-line Output:
You can use triple quotes or multiple print statements.

Example:
print(\"\"\"This is
a multi-line
output.\"\"\")
""", 
order_in_topic=6

)

ReadingMaterial.objects.get_or_create(
    topic="Basic Input and Output",
    subtopic="Best Practices for User-Friendly I/O",
    title="Improving User Interaction",
    content="""
Writing input and output code that is friendly and clear enhances user experience.

### Tips:
- Always add prompts: `input("Enter your name: ")`
- Use clear messages: `print("Processing...")`
- Validate input and provide helpful feedback.
- Format output cleanly using f-strings.

Example:
name = input("What is your name? ")
print(f"Hello, {name}! Welcome to PyGrounds.")
""", 
order_in_topic=7
)

## topic 4

ReadingMaterial.objects.get_or_create(   
    topic="Operators",
    subtopic="Arithmetic Operators",
    title="Using Arithmetic Operators in Python",
    content="""
## Using Arithmetic Operators in Python

Arithmetic operators are used to perform basic math operations.

---

### List of Arithmetic Operators:

| Operator | Description     | Example       |
|----------|-----------------|---------------|
| `+`      | Addition         | `3 + 2 = 5`   |
| `-`      | Subtraction      | `5 - 1 = 4`   |
| `*`      | Multiplication   | `4 * 2 = 8`   |
| `/`      | Division         | `6 / 2 = 3.0` |
| `//`     | Floor Division   | `7 // 2 = 3`  |
| `%`      | Modulus (remainder) | `7 % 3 = 1` |
| `**`     | Exponentiation   | `2 ** 3 = 8`  |

---

### Example:


a = 10
b = 3

print(a + b)
print(a % b)
""",
order_in_topic=1
)
 ##Subtopic 2: Comparison Operators
ReadingMaterial.objects.get_or_create(   
topic="Operators",
subtopic="Comparison Operators",
title="Using Comparison Operators in Python",
content="""

Using Comparison Operators in Python
Comparison operators are used to compare two values and return True or False.

List of Comparison Operators:

| Operator | Description     | Example   |
|----------|-----------------|-----------|
|   ==     | Equal           | a == b    |
|   !=     | Not equal       | a != b    |
|   >      | Greater than    | a > b     |
|   <      | Less than       | a < b     |
|   >=     | Greater or equal| a >= b    |
|   <=     | Less or equal   | a <= b    |


Example:

x = 5
y = 8

print(x == y)   False
print(x < y)    True

""",
order_in_topic=2
)


ReadingMaterial.objects.get_or_create(   
topic="Operators",
subtopic="Assignment Operators",
title="Understanding Assignment Operators",
content="""

Understanding Assignment Operators
Assignment operators are used to assign values to variables.
Some also perform operations before assigning.

List of Assignment Operators:

| Operator | Description           | Example     |
|----------|-----------------------|-------------|
|   =      | Assign                | x = 5       |
|   +=     | Add and assign        | x += 2      |
|   -=     | Subtract and assign   | x -= 3      |
|   *=     | Multiply and assign   | x *= 4      |
|   /=     | Divide and assign     | x /= 2      |
|   %=     | Modulo and assign     | x %= 3      |
|   **=    | Exponent and assign   | x **= 2     |

Example:

x = 10
x += 5
print(x)  # Output: 15

""",
order_in_topic=3
)


ReadingMaterial.objects.get_or_create(   
topic="Operators",
subtopic="Logical Operators",
title="Using Logical Operators in Python",
content="""

Using Logical Operators in Python
Logical operators combine conditional statements.

Operators:

Operator	Description
and	        Returns True if both are True
or	        Returns True if at least one is True
not     	Reverses the result

Example:

x = 5
print(x > 2 and x < 10)   # True
print(x < 2 or x > 3)     # True
print(not(x > 4))         # False
""",
order_in_topic=4
)

ReadingMaterial.objects.get_or_create(   
topic="Operators",
subtopic="Operator Precedence",
title="Understanding Operator Precedence",
content="""

Understanding Operator Precedence
When multiple operators are used in a single expression, Python follows operator precedence rules to evaluate the result.

Example:
result = 3 + 2 * 5
print(result)  # Output: 13 (not 25!)
Multiplication happens before addition.

Order of Precedence (High to Low):
1.() — Parentheses
2.** — Exponent
3.* / // % — Multiply, Divide, Modulus
34.+ - — Add, Subtract
5.== != > < >= <= — Comparisons
6.not
7.and
8.or
Use parentheses () to control the order explicitly:

result = (3 + 2) * 5  # Output: 25

""",
order_in_topic=5
)


ReadingMaterial.objects.get_or_create(   
    topic="Operators",
    subtopic="Membership and Identity Operators",
    title="Using Membership and Identity Operators in Python",
    content="""
## Membership and Identity Operators in Python

These operators help check if a value exists in a sequence, or whether two variables refer to the same object.

---

### Membership Operators:

| Operator | Description                    | Example            |
|----------|--------------------------------|--------------------|
| `in`     | Returns True if value is found | `"a" in "apple"`   |
| `not in` | Returns True if not found      | `"x" not in "box"` |

---

### Examples:


fruits = ["apple", "banana", "cherry"]
print("apple" in fruits)      # True
print("orange" not in fruits)  # True

Identity Operators:

Operator	Description	                                Example
is	        True if both refer to the same object	    x is y
is not	    True if they do NOT refer to same object	x is not y

Example:
a = [1, 2, 3]
b = a
c = [1, 2, 3]

print(a is b)     # True (same object)
print(a is c)     # False (same values, different objects)
""",
order_in_topic=6
)


ReadingMaterial.objects.get_or_create(   
    topic="Operators",
    subtopic="Bitwise Operators",
    title="Introduction to Bitwise Operators (Advanced)",
    content="""
## Introduction to Bitwise Operators (Advanced)

Bitwise operators work on bits (0s and 1s) of integers.

They are mostly used in low-level programming or advanced math operations.

---

### Bitwise Operators:

| Operator | Name         | Example    | Result |
|----------|--------------|------------|--------|
| `&`      | AND          | 5 & 3      | 1      |
| `|`      | OR           | 5 \| 3     | 7      |
| `^`      | XOR          | 5 ^ 3      | 6      |
| `~`      | NOT          | ~5         | -6     |
| `<<`     | Left Shift   | 5 << 1     | 10     |
| `>>`     | Right Shift  | 5 >> 1     | 2      |

---

### Example:


a = 5      # 0101
b = 3      # 0011

print(a & b)   # 1 (0001)
print(a | b)   # 7 (0111)
print(a ^ b)   # 6 (0110)
Bitwise operations are optional for beginners but useful in performance-sensitive code.
""",
order_in_topic=7
)

# topic 5 Comments & Code Readability

ReadingMaterial.objects.get_or_create (
    topic="Comments & Code Readability",
    subtopic="Single-line vs Multi-line Comments",
    title="Using Single-line and Multi-line Comments",
    content="""
## Using Single-line and Multi-line Comments

Comments help explain what your code does. Python ignores comments during execution.

### Single-line Comment

Use `#` to start a single-line comment.

# This is a single-line comment
print("Hello!")  # This is also a comment

Multi-line Comment
Use triple quotes ''' or """ '''for multi-line comments (often used for docstrings).'''
'''
This is a
multi-line comment
''' 
'''print("Multi-line done!")'''
'''Best Practice: Use comments to clarify why something is done, not just what.'''
"""""",
order_in_topic=1
)

ReadingMaterial.objects.get_or_create(
topic="Comments & Code Readability",
subtopic="Docstrings and Inline Documentation",
title="Writing Effective Docstrings and Inline Docs",
content="""
Writing Effective Docstrings and Inline Documentation
Docstrings are special comments used to describe functions, classes, and modules.

Function Docstring Example
def greet(name):
    '''
    Greets a user by name.
    '''
    return f"Hello, {name}!"
Inline Docs
# Calculate the square of a number
result = 5 ** 2

Best Practice: Use docstrings for functions and classes; use inline docs for logic blocks.
""",
order_in_topic=2
)

ReadingMaterial.objects.get_or_create(
topic="Comments & Code Readability",
subtopic="Code Indentation and Block Structure",
title="Maintaining Proper Indentation and Blocks",
content="""

Maintaining Proper Indentation and Blocks

Python uses indentation to define blocks of code. Incorrect indentation will cause errors.

Correct Indentation:


if True:
    print("Indented correctly")
else:
    print("Also correctly indented")

Incorrect Indentation:

if True:
print("This will raise an IndentationError")

Use 4 spaces per indentation level (recommended by PEP8).
""",
order_in_topic=3
)

ReadingMaterial.objects.get_or_create(
topic="Comments & Code Readability",
subtopic="Naming Conventions (PEP8 Guidelines)",
title="Following Python Naming Conventions",
content="""

Following Python Naming Conventions (PEP8)
Variable and Function Names
Use lowercase_with_underscores:

user_name = "Alex"
get_user_input()


Constants
Use UPPERCASE letters:

MAX_USERS = 100

Classes
Use CapitalizedWords:

class UserProfile:
    pass

Consistent naming improves code readability and professionalism.
""",
order_in_topic=4
)

ReadingMaterial.objects.get_or_create(
topic="Comments & Code Readability",
subtopic="Structuring Code for Readability",
title="Organizing Code for Better Readability",
content="""

Organizing Code for Better Readability
Readable code is easier to understand and maintain.

Tips:
Break code into functions

Group related lines

Add space between sections
Example:

# Load data
data = [1, 2, 3]

# Process data
squared = [x**2 for x in data]

# Output result
print(squared)

Clean structure helps you and others understand the flow easily.
""",
order_in_topic=5
)

ReadingMaterial.objects.get_or_create(
topic="Comments & Code Readability",
subtopic="Avoiding Magic Numbers and Hardcoding",
title="Avoiding Magic Numbers and Hardcoded Values",
content="""

voiding Magic Numbers and Hardcoded Values
Magic numbers are unexplained numbers used directly in code.

Bad Practice:

price = 100
discount = price * 0.2  # What does 0.2 mean?

Better:

DISCOUNT_RATE = 0.2
discount = price * DISCOUNT_RATE


Always give names to important numbers or strings to make them meaningful.
""",
order_in_topic=6
)

ReadingMaterial.objects.get_or_create(
topic="Comments & Code Readability",
subtopic="Writing Self-Documenting Code",
title="Writing Clear and Self-Documenting Code",
content="""

Writing Clear and Self-Documenting Code
Code should explain itself without needing extra comments.
Bad:
a = 10
b = a * 12.5

 Good:
 monthly_salary = 10
annual_salary = monthly_salary * 12.5

Use descriptive variable names and function names that reflect their purpose.
""",
order_in_topic=7
)

## topic 6 Conditional Statements 
ReadingMaterial.objects.get_or_create(
    topic="Conditional Statements",
    subtopic="if Statement Syntax and Structure",
    title="Using Basic if Statements",
    content="""
## Using Basic if Statements

The `if` statement is used to execute code only if a certain condition is true.

### Syntax:

if condition:
    # code block
Example:
age = 18
if age >= 18:
    print("You are an adult.")

Indentation is critical. Python uses indentation (usually 4 spaces) to define the block of code inside the if.
""",
order_in_topic=1
)
ReadingMaterial.objects.get_or_create(
topic="Conditional Statements",
subtopic="if-else and elif Ladder",
title="Creating if-else and elif Chains",
content="""

Creating if-else and elif Chains
Use if-else when you want two possible outcomes. Use elif for multiple conditions.

Example:
score = 75

if score >= 90:
    print("Grade: A")
elif score >= 80:
    print("Grade: B")
elif score >= 70:
    print("Grade: C")
else:
    print("Grade: D or below")
The conditions are checked from top to bottom. The first True condition's block will run.
""",
order_in_topic=2
)

ReadingMaterial.objects.get_or_create(
topic="Conditional Statements",
subtopic="Nested Conditional Statements",
title="Writing Nested Conditions",
content="""

Writing Nested Conditions
Nested if statements allow you to check a second condition only if the first is true.

Example:

x = 10
y = 5

if x > 0:
    if y > 0:
        print("Both x and y are positive.")
Be careful with indentation to avoid errors and confusion in nested logic.
""",
order_in_topic=3
)

ReadingMaterial.objects.get_or_create(
topic="Conditional Statements",
subtopic="Boolean Logic in Conditions",
title="Using Boolean Logic (and, or, not)",
content="""

Using Boolean Logic (and, or, not)
Combine multiple conditions using logical operators.

Operators:
and: All conditions must be true.

or: At least one condition must be true.

not: Inverts a boolean value.

Example:

age = 20
has_id = True

if age >= 18 and has_id:
    print("Allowed to enter.")
Use parentheses to group complex expressions for clarity.
""",
order_in_topic=4
)

ReadingMaterial.objects.get_or_create(
topic="Conditional Statements",
subtopic="Ternary Operators (One-liner conditionals)",
title="Using Ternary Operators in Python",
content="""

Using Ternary Operators in Python
Ternary operators let you write a simple if-else in one line.

Syntax:
value_if_true if condition else value_if_false
Example:

age = 17
status = "Adult" if age >= 18 else "Minor"
print(status)
Ternary expressions are useful for short conditions.
""",
order_in_topic=5
)

ReadingMaterial.objects.get_or_create(
topic="Conditional Statements",
subtopic="Using Conditions with Input",
title="Combining Conditions with User Input",
content="""

Combining Conditions with User Input
You can use input values directly in conditions.

Example:

age = int(input("Enter your age: "))

if age >= 18:
    print("Access granted.")
else:
    print("Access denied.")
Always convert the input to the correct type (e.g., int) before comparing.
""",
order_in_topic=6
)

ReadingMaterial.objects.get_or_create(
topic="Conditional Statements",
subtopic="Common Logic Pitfalls and Debugging",
title="Common Mistakes in Conditional Logic",
content="""

Common Mistakes in Conditional Logic
Even simple logic can go wrong. Let’s look at common mistakes and how to avoid them.

Mistake 1: Using = instead of ==

if x = 5:   # This is assignment, not comparison!
Fix:


if x == 5:
Mistake 2: Forgetting Indentation

if x > 0:
print("Positive")  #  Not indented
Fix:

if x > 0:
    print("Positive")
Mistake 3: Complex Logic Without Parentheses

if x > 5 or x < 2 and y == 3:  # May behave unexpectedly
Fix:


if (x > 5 or x < 2) and y == 3:
Always test your logic and use print() to debug if needed!
""",
order_in_topic=7
)


 ## topic 7 Error Handling
ReadingMaterial.objects.get_or_create(
    topic="Error Handling",
    subtopic="Understanding Common Runtime Errors",
    title="What Are Runtime Errors in Python?",
    content="""
## What Are Runtime Errors in Python?

Runtime errors are mistakes that occur while the program is running. These errors will cause your program to crash unless handled properly.

### Common Runtime Errors:
- `ZeroDivisionError`: Dividing by zero.
- `NameError`: Using a variable that hasn't been defined.
- `TypeError`: Mismatched data types.
- `IndexError`: Accessing an invalid index in a list.

### Example:

number = 10
print(number / 0)  # ZeroDivisionError


To handle these, we use try-except blocks, which we'll explore next.
""",
order_in_topic=1
)

ReadingMaterial.objects.get_or_create(
topic="Error Handling",
subtopic="Try-Except Block Structure",
title="Using try-except to Handle Errors",
content="""

Using try-except to Handle Errors
Python provides a try-except block to catch and handle errors gracefully without crashing the program.

Syntax:

try:
    # Code that may cause an error
except SomeError:
    # What to do if that error occurs
Example:

try:
    result = 10 / 0
except ZeroDivisionError:
    print("You can't divide by zero!")

Helps prevent unexpected crashes and allows fallback behavior.
""",
order_in_topic=2
)

ReadingMaterial.objects.get_or_create(
topic="Error Handling",
subtopic="Catching Multiple Exceptions",
title="Handling Multiple Exceptions",
content="""

Handling Multiple Exceptions
You can handle different types of errors using multiple except blocks or combine them in one.

Multiple excepts:

try:
    x = int("abc")
except ValueError:
    print("Invalid number!")
except TypeError:
    print("Wrong type!")
Catching multiple in one block:

try:
    # risky operation
except (ValueError, TypeError):
    print("An error occurred.")
Use this when multiple exceptions need the same handling.
""",
order_in_topic=3
)

ReadingMaterial.objects.get_or_create(
topic="Error Handling",
subtopic="else and finally Clauses in Error Handling",
title="else and finally in try-except Blocks",
content="""

else and finally in try-except Blocks
You can extend error handling using else and finally.

else: Runs if no exception was raised.

finally: Runs no matter what (useful for cleanup).

Example:
try:
    x = 5
    print(x / 1)
except ZeroDivisionError:
    print("Can't divide by zero.")
else:
    print("Division successful.")
finally:
    print("Finished!")
Use finally to close files or release resources.
""",
order_in_topic=4
)

ReadingMaterial.objects.get_or_create(
topic="Error Handling",
subtopic="Raising Custom Exceptions",
title="Raising Your Own Exceptions",
content="""

Raising Your Own Exceptions
You can trigger errors on purpose using the raise keyword.

Example:

def withdraw(amount):
    if amount < 0:
        raise ValueError("Amount must be positive.")

withdraw(-100)
This is useful for validating user input or enforcing constraints.

You can also create your own exception classes by extending Exception.
""",
order_in_topic=5
)

ReadingMaterial.objects.get_or_create(
topic="Error Handling",
subtopic="Using assert Statements",
title="Using assert for Quick Checks",
content="""

Using assert for Quick Checks
assert is a keyword that tests if a condition is True. If not, it raises an AssertionError.

Example:

age = 18
assert age >= 0, "Age cannot be negative"
Use assertions for internal checks during development, not for handling user errors.

Good for debugging assumptions in your code.
""",
order_in_topic=6
)

ReadingMaterial.objects.get_or_create(
topic="Error Handling",
subtopic="Error Messages and Debugging Tools",
title="Reading Error Messages and Debugging",
content="""

Reading Error Messages and Debugging
When Python shows an error, it gives a traceback. Understanding it is key to fixing issues.

Example:

Traceback (most recent call last):
  File "main.py", line 2, in <module>
    print(10 / 0)
ZeroDivisionError: division by zero
Tools for Debugging:
Use print() to trace values.

Use IDE features like breakpoints and step-through.

Use the pdb module for interactive debugging.

Learn to read tracebacks and isolate the line causing the issue.
""",
order_in_topic=7
)

##topic 8 loops 



ReadingMaterial.objects.get_or_create(
    topic="Loops",
    subtopic="for Loop with range()",
    title="Using for Loops with range()",
    content="""
The `for` loop is commonly used to repeat a block of code a specific number of times. Python’s `range()` function helps generate a sequence of numbers.

Example:

for i in range(5):
    print(i)
This prints numbers from 0 to 4.
""",
order_in_topic =1
)

ReadingMaterial.objects.get_or_create(
topic="Loops",
subtopic="Iterating Over Lists, Tuples, and Strings",
title="Looping Through Collections",
content="""
Python allows iteration over lists, tuples, and even strings using for.

Example:


fruits = ['apple', 'banana', 'cherry']
for fruit in fruits:
    print(fruit)
You can also iterate over characters in a string:

for char in "hello":
    print(char)
""",
order_in_topic =2
)

ReadingMaterial.objects.get_or_create(
topic="Loops",
subtopic="while Loop and Loop Conditions",
title="Using while Loops",
content="""
while loops continue to run as long as a condition remains True.

Example:

i = 0
while i < 3:
    print(i)
    i += 1
Be careful to avoid infinite loops by ensuring your condition eventually becomes False.
""", 
order_in_topic =3
)

ReadingMaterial.objects.get_or_create(
topic="Loops",
subtopic="break, continue, and pass Statements",
title="Controlling Loops",
content="""

break exits the loop early.

continue skips the current iteration.

pass is a placeholder and does nothing.

Example:


for i in range(5):
    if i == 3:
        break
    print(i)
""",
order_in_topic =4
)

ReadingMaterial.objects.get_or_create(
topic="Loops",
subtopic="Looping with enumerate() and zip()",
title="Advanced Looping Tools",
content="""

enumerate() gives index and value.

zip() allows parallel iteration.

Example:


names = ['Ana', 'Bob']
ages = [20, 25]
for name, age in zip(names, ages):
    print(name, age)
""",
order_in_topic =5
)

ReadingMaterial.objects.get_or_create(
topic="Loops",
subtopic="Infinite Loops and Loop Safety",
title="Avoiding Infinite Loops",
content="""
An infinite loop runs forever unless interrupted.

Example:


while True:
    print("This will run forever")
Use keyboard interrupt (Ctrl+C) to stop in terminal or add conditions to break out safely.
""",
order_in_topic =6
)

ReadingMaterial.objects.get_or_create(
topic="Loops",
subtopic="Comparing for and while Loops",
title="Choosing Between for and while",
content="""

Use for when you know how many times to loop.

Use while when the condition depends on runtime state.

Example comparison:


# for loop
for i in range(3):
    print(i)

# while loop
i = 0
while i < 3:
    print(i)
    i += 1
""", order_in_topic =7
)



### topic 9 Nested Loops

ReadingMaterial.objects.get_or_create(
    topic="Nested Loops",
    subtopic="Syntax of Nested for Loops",
    title="Basic Nested for Loops",
    content="""
Nested loops allow you to run an inner loop for every iteration of the outer loop.

Example:

for i in range(2):
    for j in range(3):
        print(i, j)
""",
order_in_topic =1
)

ReadingMaterial.objects.get_or_create(
topic="Nested Loops",
subtopic="Nested while and Mixed Loops",
title="Mixing Nested Loops",
content="""
You can nest while inside for, or vice versa.

Example:


i = 0
while i < 2:
    for j in range(2):
        print(i, j)
    i += 1
""",
order_in_topic =2
)

ReadingMaterial.objects.get_or_create(
topic="Nested Loops",
subtopic="Printing Patterns (e.g., triangle, pyramid)",
title="Pattern Printing with Nested Loops",
content="""
You can use nested loops to print patterns.

Example (triangle):


for i in range(1, 6):
    print('*' * i)
""",
order_in_topic =3
)

ReadingMaterial.objects.get_or_create(
topic="Nested Loops",
subtopic="Matrix Traversal and Processing",
title="Working with Matrices",
content="""
Nested loops are useful for accessing 2D lists (matrices).

Example:


matrix = [[1,2], [3,4]]
for row in matrix:
    for val in row:
        print(val)
""",
order_in_topic =4
)

ReadingMaterial.objects.get_or_create(
topic="Nested Loops",
subtopic="Loop Depth and Performance Considerations",
title="Performance of Deeply Nested Loops",
content="""
More nested loops = more time. A triple nested loop may become very slow for large inputs.

Keep loops shallow when possible, and look for optimizations.
""",
order_in_topic =5
)

ReadingMaterial.objects.get_or_create(
topic="Nested Loops",
subtopic="Managing Inner vs Outer Loop Variables",
title="Handling Variables in Nested Loops",
content="""
Use clear names to avoid confusion between outer and inner loop variables.

Example:


for row in range(3):
    for col in range(2):
        print(f"Row {row}, Col {col}")
""",
order_in_topic =6
)

ReadingMaterial.objects.get_or_create(
topic="Nested Loops",
subtopic="Avoiding Logical Errors in Nested Structures",
title="Common Mistakes in Nested Loops",
content="""
Common mistakes:

Resetting counters inside loops

Misplaced indentations

Using wrong variable from the wrong loop

Always test your nested loop logic carefully.
""",
order_in_topic =7
)

##topic 10 String and String Methods



ReadingMaterial.objects.get_or_create(
    topic="Strings & String Methods",
    subtopic="String Indexing and Slicing",
    title="Accessing and Slicing Strings",
    content="""
Strings are sequences of characters, so you can access parts of them using indexing or slicing.

Example:

text = "Python"
print(text[0])    # P
print(text[1:4])  # yth
Indexing starts at 0. Negative indexes start from the end.
""",
order_in_topic =1
)

ReadingMaterial.objects.get_or_create(
topic="Strings & String Methods",
subtopic="String Immutability",
title="Understanding String Immutability",
content="""
Strings in Python are immutable, meaning you cannot change them in place.

Example:


text = "hello"
text[0] = "H"  # This will cause an error
Instead, create a new string:


text = "hello"
text = "H" + text[1:]  # 
""",
order_in_topic =2
)

ReadingMaterial.objects.get_or_create(
topic="Strings & String Methods",
subtopic="Case Conversion Methods (lower(), upper(), etc.)",
title="Changing String Case",
content="""
Use .lower() and .upper() to convert string case.

Example:


name = "Alice"
print(name.upper())  # ALICE
print(name.lower())  # alice
""",
order_in_topic =3
)

ReadingMaterial.objects.get_or_create(
topic="Strings & String Methods",
subtopic="Searching and Replacing Text",
title="Find and Replace in Strings",
content="""
You can use .find() and .replace() to search and replace parts of a string.

Example:


msg = "hello world"
print(msg.find("world"))     # 6
print(msg.replace("world", "Python"))  # hello Python
""",
order_in_topic =4
)

ReadingMaterial.objects.get_or_create(
topic="Strings & String Methods",
subtopic="String Splitting and Joining",
title="Split and Join Strings",
content="""
Use .split() to divide a string and .join() to combine.

Example:


sentence = "a b c"
parts = sentence.split(" ")  # ['a', 'b', 'c']
print("-".join(parts))       # a-b-c
""",
order_in_topic =5
)

ReadingMaterial.objects.get_or_create(
topic="Strings & String Methods",
subtopic="Validating and Cleaning Input Strings",
title="Input Validation with Strings",
content="""
Use methods like .strip(), .isdigit(), and .isalpha() for validation.

Example:


name = " Alice "
print(name.strip())  # "Alice"
print(name.strip().isalpha())  # True
""",
order_in_topic =6
)

ReadingMaterial.objects.get_or_create(
topic="Strings & String Methods",
subtopic="Escape Sequences and Raw Strings",
title="Working with Escape Sequences",
content="""
Escape characters like \\n, \\t, and \\\" are used for formatting.

Example:


print("Hello\\nWorld")
Use raw strings to ignore escape sequences:


path = r"C:\\Users\\Name"
print(path)
""",
order_in_topic =7
)

## Topic11 Lists & Tuples
ReadingMaterial.objects.get_or_create(
topic="Lists & Tuples",
subtopic="Creating and Modifying Lists",
title="Creating Lists in Python",
content="""
Lists are ordered collections of items.

Example:


fruits = ["apple", "banana"]
fruits.append("cherry")
print(fruits)  # ['apple', 'banana', 'cherry']
""",
order_in_topic =1
)

ReadingMaterial.objects.get_or_create(
topic="Lists & Tuples",
subtopic="List Methods (append(), remove(), sort(), etc.)",
title="Common List Methods",
content="""
List methods include:

.append() — add item

.remove() — remove item

.sort() — sort the list

Example:


nums = [3, 1, 2]
nums.sort()
print(nums)  # [1, 2, 3]
""",
order_in_topic =2
)

ReadingMaterial.objects.get_or_create(
topic="Lists & Tuples",
subtopic="List Indexing, Slicing, and Comprehension",
title="Advanced List Access",
content="""
You can access lists with indexing or slicing. Comprehensions are compact ways to create lists.

Example:

print(numbers[1:3])  # [2, 3]

squares = [x*x for x in numbers]
""",
order_in_topic =3
)

ReadingMaterial.objects.get_or_create(
topic="Lists & Tuples",
subtopic="Tuples and Their Immutability",
title="Working with Tuples",
content="""
Tuples are like lists, but immutable (can't be changed).

Example:


point = (3, 4)
print(point[0])  # 3
""",
order_in_topic =4
)

ReadingMaterial.objects.get_or_create(
topic="Lists & Tuples",
subtopic="Tuple Unpacking and Multiple Assignment",
title="Unpacking Tuples",
content="""
Tuple unpacking allows assigning values at once.

Example:

x, y = (1, 2)
print(x, y)  # 1 2
""",
order_in_topic =5
)

ReadingMaterial.objects.get_or_create(
topic="Lists & Tuples",
subtopic="Iterating Through Lists and Tuples",
title="Looping Over Lists and Tuples",
content="""
Use for loops to iterate.

Example:


colors = ["red", "blue"]
for color in colors:
    print(color)
""",
order_in_topic =6
)

ReadingMaterial.objects.get_or_create(
topic="Lists & Tuples",
subtopic="When to Use Lists vs Tuples",
title="Choosing Between Lists and Tuples",
content="""
Use lists when you need to modify data.

Use tuples when data should not change (constants).
""",
order_in_topic =7
)

##Topic12 Sets
ReadingMaterial.objects.get_or_create(
topic="Sets",
subtopic="Creating and Using Sets",
title="Working with Sets",
content="""
Sets are unordered collections with no duplicates.

Example:

my_set = {1, 2, 3, 3}
print(my_set)  # {1, 2, 3}
""", 
order_in_topic =1
)

ReadingMaterial.objects.get_or_create(
topic="Sets",
subtopic="Set Operations (union, intersection, difference, etc.)",
title="Set Math Operations",
content="""
Common set operations:

| union

& intersection

- difference

Example:

a = {1, 2, 3}
b = {2, 3, 4}
print(a | b)  # {1, 2, 3, 4}
""",
order_in_topic =2
)

ReadingMaterial.objects.get_or_create(
topic="Sets",
subtopic="Set Methods (add(), remove(), etc.)",
title="Modifying Sets",
content="""
Use .add(), .remove() to change sets.

Example:


s = set()
s.add(5)
s.remove(5)
""",
order_in_topic =3
)

ReadingMaterial.objects.get_or_create(
topic="Sets",
subtopic="Working with Duplicates and Membership",
title="Membership and Uniqueness",
content="""
Sets automatically remove duplicates.

Check for item using in:

s = {1, 2, 3}
print(2 in s)  # True
""",
order_in_topic =4
)

ReadingMaterial.objects.get_or_create(
topic="Sets",
subtopic="Frozen Sets and Hashing",
title="Frozen Sets",
content="""
Frozen sets are immutable sets.

Example:

fs = frozenset([1, 2, 3])
Used as dictionary keys or in other sets.
""",
order_in_topic =5
)

ReadingMaterial.objects.get_or_create(
topic="Sets",
subtopic="Performance Benefits of Sets",
title="Efficiency of Sets",
content="""
Set membership tests are fast (O(1)) compared to lists (O(n)).

Useful for large data.
""",
order_in_topic =6
)

ReadingMaterial.objects.get_or_create(
topic="Sets",
subtopic="Converting Between Sets and Other Types",
title="Converting Sets",
content="""
Convert between list/set/tuple:


s = set([1, 2, 3])
l = list(s)
""",
order_in_topic =7
)

##Topic13 Functions
ReadingMaterial.objects.get_or_create(
topic="Functions",
subtopic="Defining Functions with def",
title="Creating a Function",
content="""
Use def to define functions.

Example:

def greet():
    print("Hello")
""",
order_in_topic =1
)

ReadingMaterial.objects.get_or_create(
topic="Functions",
subtopic="Parameters, Arguments, and Return Values",
title="Function Inputs and Outputs",
content="""
Functions can take inputs (parameters) and return values.

Example:


def add(a, b):
    return a + b
""",
order_in_topic =2
)

ReadingMaterial.objects.get_or_create(
topic="Functions",
subtopic="Variable Scope and global/nonlocal",
title="Understanding Scope",
content="""
Variables inside functions are local.

Use global or nonlocal to modify outer variables.

Example:

x = 10
def change():
    global x
    x = 5
""",
order_in_topic =3
)

ReadingMaterial.objects.get_or_create(
topic="Functions",
subtopic="Default and Keyword Arguments",
title="Optional Parameters",
content="""
Functions can have default values.

Example:

def greet(name="Guest"):
    print(f"Hello, {name}")
""",
order_in_topic =4
)

ReadingMaterial.objects.get_or_create(
topic="Functions",
subtopic="Docstrings and Function Annotations",
title="Documenting Functions",
content="""
Use docstrings to explain purpose:

def greet():
    \"\"\"This greets the user.\"\"\"
    print("Hi")
Annotations add type hints:

def add(a: int, b: int) -> int:
    return a + b
""",
order_in_topic =5
)

ReadingMaterial.objects.get_or_create(
topic="Functions",
subtopic="Lambda Functions and Anonymous Functions",
title="Using Lambda Functions",
content="""
Lambda functions are short, inline functions.

Example:


add = lambda x, y: x + y
print(add(2, 3))
""",
order_in_topic =6
)

ReadingMaterial.objects.get_or_create(
topic="Functions",
subtopic="Higher-Order Functions and Functional Programming Basics",
title="Advanced Functional Tools",
content="""
Functions like map(), filter(), reduce() use other functions.

Example:

nums = [1, 2, 3]
squares = list(map(lambda x: x**2, nums))
""",
order_in_topic =7
)

##Topic14 Dictionaries
ReadingMaterial.objects.get_or_create(
topic="Dictionaries",
subtopic="Creating and Accessing Dictionary Items",
title="Using Dictionaries",
content="""
Dictionaries store key-value pairs.

Example:

person = {"name": "Alice", "age": 25}
print(person["name"])
""",
order_in_topic =1
)

ReadingMaterial.objects.get_or_create(
topic="Dictionaries",
subtopic="Adding, Updating, and Deleting Keys",
title="Modifying Dictionaries",
content="""
You can add, change, or delete key-value pairs.

Example:

person["city"] = "Cebu"
del person["age"]
""",
order_in_topic =2
)

ReadingMaterial.objects.get_or_create(
topic="Dictionaries",
subtopic="Looping Through Keys, Values, and Items",
title="Iterating Over Dictionaries",
content="""
Use .items(), .keys(), .values() to loop.

Example:

for key, value in person.items():
    print(key, value)
""",
order_in_topic =3
)

ReadingMaterial.objects.get_or_create(
topic="Dictionaries",
subtopic="Dictionary Methods (get(), pop(), update(), etc.)",
title="Common Dictionary Methods",
content="""
Examples:

person.get("name")
person.pop("city")
person.update({"age": 30})
""",
order_in_topic =4

)

ReadingMaterial.objects.get_or_create(
topic="Dictionaries",
subtopic="Nesting Dictionaries",
title="Nested Dictionaries",
content="""
Dictionaries can hold other dictionaries.

Example:

students = {
    "A": {"math": 90},
    "B": {"math": 85}
}
""",
order_in_topic =5
)

ReadingMaterial.objects.get_or_create(
topic="Dictionaries",
subtopic="Using Dictionaries for Counting (e.g., frequency maps)",
title="Dictionaries as Counters",
content="""
Use dictionaries to count values.

Example:


text = "hello"
freq = {}
for char in text:
    freq[char] = freq.get(char, 0) + 1
""",
order_in_topic =6
)

ReadingMaterial.objects.get_or_create(
topic="Dictionaries",
subtopic="Dictionary Comprehensions",
title="Comprehensions with Dictionaries",
content="""
You can create dictionaries with a single line.

Example:


squares = {x: x**2 for x in range(5)}
""",
order_in_topic =7
)

