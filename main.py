"""
===========================================================
                           ANKO
===========================================================

Features:
    - Basic arithmetic
    - Scientific calculations
    - Parentheses / precedence
    - Functions
    - Constants
    - Variables
    - Previous answer (ans)
    - Degree / Radian modes
    - Memory
    - Calculation history
    - Save / Load sessions
    - Percentage syntax
    - Random functions
    - Built-in help
    - Safe AST-based expression evaluation
    - Configurable display precision

Python version:
    Python 3.10+

No external libraries required.
===========================================================
"""

import ast
import json
import math
import operator
import random
import re
import sys
from pathlib import Path


# TERMINAL COLORS


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"


# CONFIGURATION


APP_NAME = "Anko"
SESSION_FILE = Path("calculator_session.json")

DEFAULT_PRECISION = 12

MAX_EXPRESSION_LENGTH = 1000



# CALCULATOR CLASS


class Calculator:

    def __init__(self):
        self.precision = DEFAULT_PRECISION
        self.angle_mode = "DEG"
        self.memory = 0.0

        self.variables = {
            "ans": 0.0,
            "pi": math.pi,
            "e": math.e,
            "tau": math.tau,
        }

        self.history = []

        self.running = True

    
    # ANGLE HELPERS
    

    def sin(self, x):
        return math.sin(math.radians(x)) if self.angle_mode == "DEG" else math.sin(x)

    def cos(self, x):
        return math.cos(math.radians(x)) if self.angle_mode == "DEG" else math.cos(x)

    def tan(self, x):
        return math.tan(math.radians(x)) if self.angle_mode == "DEG" else math.tan(x)

    def asin(self, x):
        result = math.asin(x)
        return math.degrees(result) if self.angle_mode == "DEG" else result

    def acos(self, x):
        result = math.acos(x)
        return math.degrees(result) if self.angle_mode == "DEG" else result

    def atan(self, x):
        result = math.atan(x)
        return math.degrees(result) if self.angle_mode == "DEG" else result

    
    # CUSTOM FUNCTIONS
    

    @staticmethod
    def ln(x):
        return math.log(x)

    @staticmethod
    def cbrt(x):
        """
        Cube root that works with negative numbers too.
        """
        if x >= 0:
            return x ** (1 / 3)
        return -((-x) ** (1 / 3))

    @staticmethod
    def percent(x):
        return x / 100

    @staticmethod
    def fact(x):
        if x < 0 or int(x) != x:
            raise ValueError("factorial() requires a non-negative integer")

        if x > 10000:
            raise ValueError("Number too large for factorial")

        return math.factorial(int(x))

    @staticmethod
    def avg(*args):
        if not args:
            raise ValueError("avg() requires at least one value")

        return sum(args) / len(args)

    @staticmethod
    def rand():
        return random.random()

    @staticmethod
    def randint(a, b):
        return random.randint(int(a), int(b))

    @staticmethod
    def clamp(value, minimum, maximum):
        return max(minimum, min(value, maximum))

    
    # AVAILABLE FUNCTIONS
    

    def function_map(self):

        return {

            # Basic
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,

            # Powers / roots
            "sqrt": math.sqrt,
            "cbrt": self.cbrt,
            "pow": pow,

            # Logs / exponential
            "log": math.log10,
            "ln": self.ln,
            "log10": math.log10,
            "log2": math.log2,
            "exp": math.exp,

            # Trigonometry
            "sin": self.sin,
            "cos": self.cos,
            "tan": self.tan,
            "asin": self.asin,
            "acos": self.acos,
            "atan": self.atan,

            # Angle conversion
            "degrees": math.degrees,
            "radians": math.radians,

            # Integer / number theory
            "floor": math.floor,
            "ceil": math.ceil,
            "fact": self.fact,
            "factorial": self.fact,
            "gcd": math.gcd,
            "lcm": math.lcm,

            # Statistics
            "avg": self.avg,

            # Percentage
            "percent": self.percent,

            # Random
            "rand": self.rand,
            "random": self.rand,
            "randint": self.randint,

            # Utility
            "clamp": self.clamp,

        }

    
    # OPERATOR MAP
    

    binary_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    unary_operators = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    comparison_operators = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }

    
    # PREPROCESS EXPRESSION
    

    def preprocess(self, expression):

        expression = expression.strip()

        # Remove spaces
        expression = expression.replace(" ", "")

        # Replace common symbols
        expression = expression.replace("^", "**")
        expression = expression.replace("×", "*")
        expression = expression.replace("÷", "/")

        # Case-insensitive answer
        expression = re.sub(r"\bANS\b", "ans", expression, flags=re.IGNORECASE)

        
        # Percentage conversion
        #
        # Example:
        #     25%       -> (25/100)
        #     12.5%     -> (12.5/100)
        

        expression = re.sub(
            r"(?<![\w.)])(\d+(?:\.\d+)?)%",
            r"(\1/100)",
            expression
        )

        
        # Factorial shorthand
        #
        # Example:
        #     5!       -> fact(5)
        #     (3+2)!   -> fact(3+2)
        #
        # The second case is handled for simple expressions.
        

        expression = re.sub(
            r"(\d+(?:\.\d+)?)!",
            r"fact(\1)",
            expression
        )

        return expression

    
    # SAFE AST EVALUATOR
    

    def safe_eval(self, expression):

        if len(expression) > MAX_EXPRESSION_LENGTH:
            raise ValueError(
                f"Expression is too long. Maximum length is "
                f"{MAX_EXPRESSION_LENGTH} characters."
            )

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"Invalid expression: {exc.msg}")

        return self.evaluate_node(tree.body)

    
    # AST NODE EVALUATION
    

    def evaluate_node(self, node):

        
        # NUMBER / CONSTANT
        

        if isinstance(node, ast.Constant):

            if isinstance(node.value, (int, float)):
                return node.value

            raise ValueError("Only numbers are allowed.")

       
        # VARIABLE
        

        if isinstance(node, ast.Name):

            name = node.id.lower()

            if name in self.variables:
                return self.variables[name]

            if name in self.function_map():
                raise ValueError(
                    f"'{name}' is a function. "
                    f"Use parentheses, e.g. {name}(...)"
                )

            raise NameError(f"Unknown variable: {name}")

        
        # BINARY OPERATIONS
        

        if isinstance(node, ast.BinOp):

            left = self.evaluate_node(node.left)
            right = self.evaluate_node(node.right)

            operation = self.binary_operators.get(type(node.op))

            if operation is None:
                raise ValueError("Unsupported operator.")

            # Prevent obviously dangerous powers
            if isinstance(node.op, ast.Pow):

                if abs(right) > 10000:
                    raise ValueError("Exponent is too large.")

                if abs(left) > 10**100:
                    raise ValueError("Base is too large.")

            try:
                return operation(left, right)

            except ZeroDivisionError:
                raise ZeroDivisionError("Cannot divide by zero.")

            except OverflowError:
                raise OverflowError("Result is too large.")

        
        # UNARY OPERATIONS
        

        if isinstance(node, ast.UnaryOp):

            operation = self.unary_operators.get(type(node.op))

            if operation is None:
                raise ValueError("Unsupported unary operator.")

            operand = self.evaluate_node(node.operand)

            return operation(operand)

        
        # FUNCTION CALL
        

        if isinstance(node, ast.Call):

            if not isinstance(node.func, ast.Name):
                raise ValueError("Only direct function calls are allowed.")

            function_name = node.func.id.lower()

            functions = self.function_map()

            if function_name not in functions:
                raise NameError(
                    f"Unknown function: {function_name}"
                )

            if node.keywords:
                raise ValueError(
                    "Keyword arguments are not supported."
                )

            args = [
                self.evaluate_node(arg)
                for arg in node.args
            ]

            try:
                return functions[function_name](*args)

            except TypeError as exc:
                raise TypeError(
                    f"Invalid arguments for {function_name}(): {exc}"
                )

            except ValueError as exc:
                raise ValueError(str(exc))

        
        # COMPARISONS
        

        if isinstance(node, ast.Compare):

            left = self.evaluate_node(node.left)

            results = []

            for op, comparator in zip(
                node.ops,
                node.comparators
            ):

                right = self.evaluate_node(comparator)

                operation = self.comparison_operators.get(type(op))

                if operation is None:
                    raise ValueError(
                        "Unsupported comparison operator."
                    )

                results.append(operation(left, right))

                left = right

            return all(results)

        
        # BOOLEAN OPERATIONS
        

        if isinstance(node, ast.BoolOp):

            values = [
                self.evaluate_node(value)
                for value in node.values
            ]

            if isinstance(node.op, ast.And):
                return all(values)

            if isinstance(node.op, ast.Or):
                return any(values)

            raise ValueError("Unsupported boolean operator.")

        
        # EVERYTHING ELSE IS BLOCKED
        

        raise ValueError(
            f"Unsupported expression element: "
            f"{type(node).__name__}"
        )

    
    # EVALUATE USER EXPRESSION
    

    def calculate(self, expression):

        original_expression = expression

        expression = self.preprocess(expression)

        result = self.safe_eval(expression)

        # Update answer
        self.variables["ans"] = result

        # Add history
        self.history.append({
            "expression": original_expression,
            "result": result
        })

        return result

    
    # FORMAT RESULT
    

    def format_result(self, result):

        if isinstance(result, bool):
            return str(result)

        if isinstance(result, int):
            return f"{result:,}"

        if isinstance(result, float):

            if math.isnan(result):
                return "NaN"

            if math.isinf(result):
                return "Infinity" if result > 0 else "-Infinity"

            # Avoid -0.0
            if result == 0:
                result = 0.0

            return f"{result:,.{self.precision}g}"

        return str(result)

    
    # VARIABLES
    

    def assign_variable(self, expression):

        # Example:
        #
        # x = 50
        # total = 12 * 5

        match = re.fullmatch(
            r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)",
            expression
        )

        if not match:
            return False

        name = match.group(1).lower()
        value_expression = match.group(2)

        reserved = set(self.function_map().keys())

        if name in reserved:
            raise ValueError(
                f"'{name}' is a reserved function name."
            )

        if name in {"pi", "e", "tau", "ans"}:
            raise ValueError(
                f"'{name}' is a protected calculator variable."
            )

        value = self.calculate(value_expression)

        self.variables[name] = value

        # The variable assignment itself appears in history
        self.history.append({
            "expression": expression,
            "result": value
        })

        return True

    
    # MEMORY OPERATIONS
    

    def memory_add(self):
        self.memory += float(self.variables["ans"])

    def memory_subtract(self):
        self.memory -= float(self.variables["ans"])

    def memory_recall(self):

        self.variables["ans"] = self.memory

        return self.memory

    def memory_clear(self):
        self.memory = 0.0

    
    # HISTORY
    

    def show_history(self):

        if not self.history:
            print(f"\n{Colors.YELLOW}No calculations in history.{Colors.RESET}\n")
            return

        print(f"\n{Colors.BLUE}" + "=" * 65 + f"{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.YELLOW}CALCULATION HISTORY{Colors.RESET}")
        print(f"{Colors.BLUE}" + "=" * 65 + f"{Colors.RESET}")

        for index, item in enumerate(self.history, start=1):

            expression = item["expression"]
            result = self.format_result(item["result"])

            print(
                f"{Colors.CYAN}{index:>4}. {Colors.RESET}"
                f"{expression:<35} {Colors.CYAN}={Colors.RESET} {Colors.GREEN}{result}{Colors.RESET}"
            )

        print(f"{Colors.BLUE}" + "=" * 65 + f"{Colors.RESET}\n")

    def clear_history(self):
        self.history.clear()

    
    # SAVE SESSION
    

    def save_session(self, filename=SESSION_FILE):

        data = {
            "precision": self.precision,
            "angle_mode": self.angle_mode,
            "memory": self.memory,
            "variables": self.variables,
            "history": self.history,
        }

        try:

            with open(filename, "w", encoding="utf-8") as file:
                json.dump(
                    data,
                    file,
                    indent=4,
                    allow_nan=True
                )

            print(f"\n{Colors.GREEN}Session saved to: {filename}{Colors.RESET}\n")

        except OSError as exc:
            print(f"\n{Colors.RED}Could not save session: {exc}{Colors.RESET}\n")

    
    # LOAD SESSION
    

    def load_session(self, filename=SESSION_FILE):

        try:

            with open(filename, "r", encoding="utf-8") as file:
                data = json.load(file)

            self.precision = int(
                data.get("precision", DEFAULT_PRECISION)
            )

            self.angle_mode = data.get(
                "angle_mode",
                "DEG"
            )

            self.memory = float(
                data.get("memory", 0.0)
            )

            loaded_variables = data.get(
                "variables",
                {}
            )

            self.variables.update(
                loaded_variables
            )

            self.history = data.get(
                "history",
                []
            )

            print(f"\n{Colors.GREEN}Session loaded from: {filename}{Colors.RESET}\n")

        except FileNotFoundError:
            print(f"\n{Colors.YELLOW}No session file found: {filename}{Colors.RESET}\n")

        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"\n{Colors.RED}Could not load session: {exc}{Colors.RESET}\n")

    
    # SHOW VARIABLES
    

    def show_variables(self):

        print(f"\n{Colors.BLUE}" + "=" * 50 + f"{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.YELLOW}VARIABLES{Colors.RESET}")
        print(f"{Colors.BLUE}" + "=" * 50 + f"{Colors.RESET}")

        for name, value in sorted(self.variables.items()):

            print(
                f"{Colors.CYAN}{name:<15} {Colors.RESET}= "
                f"{Colors.GREEN}{self.format_result(value)}{Colors.RESET}"
            )

        print(f"{Colors.BLUE}" + "=" * 50 + f"{Colors.RESET}\n")

    
    # HELP MENU
    

    def show_help(self):

        print(f"""

{Colors.BLUE}=============================================================={Colors.RESET}
{Colors.BOLD}{Colors.YELLOW}                    CALCULATOR HELP{Colors.RESET}
{Colors.BLUE}=============================================================={Colors.RESET}

{Colors.CYAN}ARITHMETIC{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}+       {Colors.RESET}Addition
{Colors.GREEN}-       {Colors.RESET}Subtraction
{Colors.GREEN}*       {Colors.RESET}Multiplication
{Colors.GREEN}/       {Colors.RESET}Division
{Colors.GREEN}//      {Colors.RESET}Floor division
{Colors.GREEN}%       {Colors.RESET}Modulo
{Colors.GREEN}**      {Colors.RESET}Power
{Colors.GREEN}^       {Colors.RESET}Power (converted to **)

{Colors.YELLOW}Examples:{Colors.RESET}
{Colors.GREEN}    10 + 5
    10 - 3
    10 * 8
    10 / 4
    10 // 4
    10 % 4
    2 ** 8
    2 ^ 8{Colors.RESET}

{Colors.CYAN}PARENTHESES{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    (10 + 5) * 2
    ((100 / 5) + 8) * 3{Colors.RESET}

{Colors.CYAN}PERCENTAGES{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    25%
    10 + 25%
    200 * 15%{Colors.RESET}

{Colors.CYAN}CONSTANTS{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    pi
    e
    tau
    ans{Colors.RESET}

{Colors.CYAN}SCIENTIFIC FUNCTIONS{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    sqrt(25)
    cbrt(27)

    log(100)
    log10(1000)
    log2(32)
    ln(e)

    exp(2){Colors.RESET}

{Colors.CYAN}TRIGONOMETRY{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
Current angle mode can be DEG or RAD.

{Colors.GREEN}    sin(30)
    cos(60)
    tan(45)

    asin(0.5)
    acos(0.5)
    atan(1){Colors.RESET}

{Colors.CYAN}ANGLE CONVERSION{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    degrees(pi)
    radians(180){Colors.RESET}

{Colors.CYAN}NUMBER FUNCTIONS{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    abs(-100)
    floor(3.99)
    ceil(3.01)
    round(3.14159, 2)

    fact(5)
    factorial(6)

    gcd(48, 18)
    lcm(12, 15){Colors.RESET}

{Colors.CYAN}STATISTICS{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    avg(10, 20, 30, 40){Colors.RESET}

{Colors.CYAN}RANDOM{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    rand()
    random()
    randint(1, 100){Colors.RESET}

{Colors.CYAN}OTHER{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    clamp(150, 0, 100){Colors.RESET}

{Colors.CYAN}VARIABLES{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
You can create variables:

{Colors.GREEN}    x = 10
    y = 20
    price = 1500
    quantity = 4{Colors.RESET}

Then use:

{Colors.GREEN}    price * quantity
    x ** 2
    x + y
    sqrt(x){Colors.RESET}

The last calculation is always stored as:

{Colors.GREEN}    ans{Colors.RESET}

{Colors.YELLOW}Example:{Colors.RESET}

{Colors.GREEN}    20 * 5
    ans + 10{Colors.RESET}

{Colors.CYAN}MEMORY{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    m+       {Colors.RESET}Add current answer to memory
{Colors.GREEN}    m-       {Colors.RESET}Subtract current answer from memory
{Colors.GREEN}    mr       {Colors.RESET}Recall memory
{Colors.GREEN}    mc       {Colors.RESET}Clear memory

{Colors.CYAN}COMMANDS{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    help             {Colors.RESET}Show this help
{Colors.GREEN}    history          {Colors.RESET}Show calculation history
{Colors.GREEN}    clearhistory     {Colors.RESET}Clear history

{Colors.GREEN}    vars             {Colors.RESET}Show variables

{Colors.GREEN}    deg              {Colors.RESET}Degree mode
{Colors.GREEN}    rad              {Colors.RESET}Radian mode

{Colors.GREEN}    precision 10     {Colors.RESET}Show 10 significant digits

{Colors.GREEN}    save             {Colors.RESET}Save session
{Colors.GREEN}    load             {Colors.RESET}Load session

{Colors.GREEN}    clear            {Colors.RESET}Clear screen
{Colors.GREEN}    exit             {Colors.RESET}Exit
{Colors.GREEN}    quit             {Colors.RESET}Exit

{Colors.CYAN}COMPARISONS{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    10 > 5
    10 < 5
    10 == 10
    10 != 5
    10 >= 10
    10 <= 20{Colors.RESET}

{Colors.CYAN}BOOLEAN{Colors.RESET}
{Colors.BLUE}--------------------------------------------------------------{Colors.RESET}
{Colors.GREEN}    10 > 5 and 20 > 10
    10 > 100 or 20 > 10{Colors.RESET}

{Colors.BLUE}=============================================================={Colors.RESET}
""")

    
    # COMMAND PROCESSOR
    

    def process_command(self, user_input):

        command = user_input.strip()

        lower = command.lower()

        
        # EXIT
        

        if lower in {
            "exit",
            "quit",
            ":exit",
            ":quit"
        }:

            self.running = False
            return

        
        # HELP
        

        if lower in {
            "help",
            ":help",
            "?"
        }:

            self.show_help()
            return

        
        # HISTORY
        

        if lower in {
            "history",
            ":history"
        }:

            self.show_history()
            return

        
        # CLEAR HISTORY
       

        if lower in {
            "clearhistory",
            "clear history",
            ":clearhistory"
        }:

            self.clear_history()
            print(f"\n{Colors.YELLOW}History cleared.{Colors.RESET}\n")
            return

        
        # VARIABLES
        

        if lower in {
            "vars",
            "variables",
            ":vars"
        }:

            self.show_variables()
            return

        
        # CLEAR SCREEN
        

        if lower in {
            "clear",
            "cls",
            ":clear"
        }:

            self.clear_screen()
            return

        
        # DEGREE MODE
        

        if lower in {
            "deg",
            "degree",
            "degrees"
        }:

            self.angle_mode = "DEG"
            print(f"\n{Colors.YELLOW}Angle mode: {Colors.CYAN}DEGREE{Colors.RESET}\n")
            return

        
        # RADIAN MODE
        

        if lower in {
            "rad",
            "radian",
            "radians"
        }:

            self.angle_mode = "RAD"
            print(f"\n{Colors.YELLOW}Angle mode: {Colors.CYAN}RADIAN{Colors.RESET}\n")
            return

        
        # PRECISION
        

        precision_match = re.fullmatch(
            r"precision\s+(\d+)",
            lower
        )

        if precision_match:

            precision = int(precision_match.group(1))

            if not 1 <= precision <= 50:
                print(
                    f"\n{Colors.RED}Precision must be between 1 and 50.{Colors.RESET}\n"
                )
                return

            self.precision = precision

            print(
                f"\n{Colors.YELLOW}Display precision set to "
                f"{Colors.CYAN}{precision}{Colors.YELLOW} significant digits.{Colors.RESET}\n"
            )

            return

        
        # MEMORY PLUS
        

        if lower == "m+":

            self.memory_add()

            print(
                f"\n{Colors.YELLOW}Memory = "
                f"{Colors.GREEN}{self.format_result(self.memory)}{Colors.RESET}\n"
            )

            return

       
        # MEMORY MINUS
        

        if lower == "m-":

            self.memory_subtract()

            print(
                f"\n{Colors.YELLOW}Memory = "
                f"{Colors.GREEN}{self.format_result(self.memory)}{Colors.RESET}\n"
            )

            return

        
        # MEMORY RECALL
        

        if lower == "mr":

            result = self.memory_recall()

            print(
                f"\n{Colors.YELLOW}Memory = "
                f"{Colors.GREEN}{self.format_result(result)}{Colors.RESET}\n"
            )

            return

        
        # MEMORY CLEAR
        

        if lower == "mc":

            self.memory_clear()

            print(f"\n{Colors.YELLOW}Memory cleared.{Colors.RESET}\n")
            return

        
        # SAVE
        

        if lower.startswith("save"):

            parts = command.split(maxsplit=1)

            filename = (
                parts[1]
                if len(parts) > 1
                else SESSION_FILE
            )

            self.save_session(Path(filename))
            return

        
        # LOAD
        

        if lower.startswith("load"):

            parts = command.split(maxsplit=1)

            filename = (
                parts[1]
                if len(parts) > 1
                else SESSION_FILE
            )

            self.load_session(Path(filename))
            return

        
        # VARIABLE ASSIGNMENT
        

        if "=" in command:

            if self.assign_variable(command):

                match = re.match(
                    r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=",
                    command
                )

                variable_name = (
                    match.group(1)
                    if match
                    else "variable"
                )

                value = self.variables[
                    variable_name.lower()
                ]

                print(
                    f"\n{Colors.CYAN}{variable_name} {Colors.RESET}= "
                    f"{Colors.GREEN}{self.format_result(value)}{Colors.RESET}\n"
                )

                return

        
        # CALCULATE
        

        try:

            result = self.calculate(command)

            formatted = self.format_result(result)

            print(
                f"\n{Colors.CYAN}={Colors.RESET} {Colors.GREEN}{formatted}{Colors.RESET}\n"
            )

        except ZeroDivisionError as exc:

            print(
                f"\n{Colors.RED}Error: {exc}{Colors.RESET}\n"
            )

        except (
            ValueError,
            TypeError,
            NameError,
            OverflowError
        ) as exc:

            print(
                f"\n{Colors.RED}Error: {exc}{Colors.RESET}\n"
            )

        except Exception as exc:

            print(
                f"\n{Colors.RED}Unexpected error: {exc}{Colors.RESET}\n"
            )

    
    # CLEAR SCREEN


    @staticmethod
    def clear_screen():

        command = "cls" if sys.platform == "win32" else "clear"

        try:
            import os
            os.system(command)
        except Exception:
            print("\n" * 50)

    
    # START CALCULATOR
    

    def start(self):

        self.print_banner()

        while self.running:

            try:

                user_input = input(
                    f"{Colors.BOLD}{Colors.GREEN}{self.angle_mode} > {Colors.RESET}"
                ).strip()

                if not user_input:
                    continue

                self.process_command(user_input)

            except KeyboardInterrupt:

                print(
                    f"\n\n{Colors.YELLOW}Use 'exit' to quit.{Colors.RESET}\n"
                )

            except EOFError:

                print("\n")
                break

        print(
            f"\n{Colors.BOLD}{Colors.CYAN}Thank you for using Anko!{Colors.RESET}\n"
        )

    
    # BANNER
    

    @staticmethod
    def print_banner():

        print(f"""
{Colors.BLUE}╔══════════════════════════════════════════════════════════╗{Colors.RESET}
{Colors.BLUE}║{Colors.RESET}                                                          {Colors.BLUE}║{Colors.RESET}
{Colors.BLUE}║{Colors.RESET}                           {Colors.BOLD}{Colors.CYAN}ANKO{Colors.RESET}                           {Colors.BLUE}║{Colors.RESET}
{Colors.BLUE}║{Colors.RESET}                                                          {Colors.BLUE}║{Colors.RESET}
{Colors.BLUE}║{Colors.RESET}        {Colors.YELLOW}Scientific • Variables • Memory • History{Colors.RESET}         {Colors.BLUE}║{Colors.RESET}
{Colors.BLUE}╚══════════════════════════════════════════════════════════╝{Colors.RESET}

{Colors.YELLOW}Type 'help' to see all available features.{Colors.RESET}

{Colors.CYAN}Examples:{Colors.RESET}

{Colors.GREEN}    25 * 4
    sqrt(144)
    sin(30)
    2 ** 10
    15%
    x = 100
    x * 5
    ans / 2{Colors.RESET}

{Colors.BLUE}------------------------------------------------------------{Colors.RESET}
""")



# MAIN PROGRAM


def main():

    # Enable ANSI escape sequences on Windows
    if sys.platform == "win32":
        import os
        os.system("")

    calculator = Calculator()

    # Automatically load previous session if available
    if SESSION_FILE.exists():

        try:
            calculator.load_session(SESSION_FILE)

        except Exception:
            pass

    calculator.start()



# PROGRAM ENTRY POINT


if __name__ == "__main__":
    main()