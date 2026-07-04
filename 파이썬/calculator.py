"""간단한 GUI 계산기 (tkinter)"""

import ast
import operator
import tkinter as tk
from tkinter import font


OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def safe_evaluate(expression: str) -> float:
    """허용된 연산만 사용해 수식을 계산합니다."""

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        raise ValueError("허용되지 않은 수식입니다.")

    tree = ast.parse(expression.replace("×", "*").replace("÷", "/").replace("−", "-"), mode="eval")
    return _eval(tree)


def format_number(num: str) -> str:
    """숫자 문자열에 천 단위 구분 쉼표를 추가합니다."""
    if num in ("", "-"):
        return num

    negative = num.startswith("-")
    body = num[1:] if negative else num
    prefix = "-" if negative else ""

    if body.startswith("."):
        return f"{prefix}{body}"
    if body.endswith("."):
        integer_part = body[:-1] or "0"
        return f"{prefix}{int(integer_part):,}."
    if "." in body:
        integer_part, decimal_part = body.split(".", 1)
        integer_part = integer_part or "0"
        return f"{prefix}{int(integer_part):,}.{decimal_part}"

    return f"{prefix}{int(body):,}"


def format_expression(expression: str) -> str:
    """수식 문자열의 숫자 부분에 천 단위 구분 쉼표를 추가합니다."""
    if not expression:
        return "0"
    if expression == "Error":
        return "Error"

    formatted: list[str] = []
    index = 0
    length = len(expression)

    while index < length:
        char = expression[index]
        if char in "+*/%":
            formatted.append(char)
            index += 1
            continue

        if char == "-" and index > 0 and (expression[index - 1].isdigit() or expression[index - 1] == "."):
            formatted.append("-")
            index += 1
            continue

        start = index
        if char == "-":
            index += 1
        while index < length and (expression[index].isdigit() or expression[index] == "."):
            index += 1

        number = expression[start:index]
        formatted.append(format_number(number) if number not in ("", "-") else number)

    return "".join(formatted)


class Calculator:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("파이썬 계산기")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        self.expression = ""
        self.display_var = tk.StringVar(value="0")

        self._build_ui()
        self._bind_keys()
        self.root.focus_set()

    def _build_ui(self) -> None:
        display_font = font.Font(family="Segoe UI", size=28, weight="bold")
        button_font = font.Font(family="Segoe UI", size=16)

        display = tk.Entry(
            self.root,
            textvariable=self.display_var,
            font=display_font,
            justify="right",
            bd=0,
            readonlybackground="#313244",
            fg="#cdd6f4",
            insertbackground="#cdd6f4",
            state="readonly",
        )
        display.grid(row=0, column=0, columnspan=4, padx=12, pady=(12, 8), ipady=16, sticky="nsew")

        buttons = [
            ("C", 1, 0, self.clear, "#f38ba8", "#1e1e2e"),
            ("⌫", 1, 1, self.backspace, "#f38ba8", "#1e1e2e"),
            ("%", 1, 2, lambda: self.append("%"), "#fab387", "#1e1e2e"),
            ("÷", 1, 3, lambda: self.append("/"), "#fab387", "#1e1e2e"),
            ("7", 2, 0, lambda: self.append("7"), "#45475a", "#cdd6f4"),
            ("8", 2, 1, lambda: self.append("8"), "#45475a", "#cdd6f4"),
            ("9", 2, 2, lambda: self.append("9"), "#45475a", "#cdd6f4"),
            ("×", 2, 3, lambda: self.append("*"), "#fab387", "#1e1e2e"),
            ("4", 3, 0, lambda: self.append("4"), "#45475a", "#cdd6f4"),
            ("5", 3, 1, lambda: self.append("5"), "#45475a", "#cdd6f4"),
            ("6", 3, 2, lambda: self.append("6"), "#45475a", "#cdd6f4"),
            ("−", 3, 3, lambda: self.append("-"), "#fab387", "#1e1e2e"),
            ("1", 4, 0, lambda: self.append("1"), "#45475a", "#cdd6f4"),
            ("2", 4, 1, lambda: self.append("2"), "#45475a", "#cdd6f4"),
            ("3", 4, 2, lambda: self.append("3"), "#45475a", "#cdd6f4"),
            ("+", 4, 3, lambda: self.append("+"), "#fab387", "#1e1e2e"),
            ("±", 5, 0, self.toggle_sign, "#585b70", "#cdd6f4"),
            ("0", 5, 1, lambda: self.append("0"), "#45475a", "#cdd6f4"),
            (".", 5, 2, lambda: self.append("."), "#45475a", "#cdd6f4"),
            ("=", 5, 3, self.calculate, "#a6e3a1", "#1e1e2e"),
        ]

        for text, row, col, command, bg, fg in buttons:
            btn = tk.Button(
                self.root,
                text=text,
                font=button_font,
                command=command,
                bg=bg,
                fg=fg,
                activebackground=bg,
                activeforeground=fg,
                bd=0,
                width=5,
                height=2,
                cursor="hand2",
                takefocus=0,
            )
            btn.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

        for i in range(4):
            self.root.grid_columnconfigure(i, weight=1)

    def _bind_char(self, char: str) -> str:
        self.append(char)
        return "break"

    def _bind_action(self, action) -> str:
        action()
        return "break"

    def _on_key_press(self, event: tk.Event) -> str | None:
        char_map = {
            **{str(i): str(i) for i in range(10)},
            **{f"KP_{i}": str(i) for i in range(10)},
            "period": ".",
            "KP_Decimal": ".",
            "plus": "+",
            "KP_Add": "+",
            "minus": "-",
            "KP_Subtract": "-",
            "asterisk": "*",
            "KP_Multiply": "*",
            "slash": "/",
            "KP_Divide": "/",
            "percent": "%",
        }

        keysym = event.keysym
        if keysym in char_map:
            return self._bind_char(char_map[keysym])
        if keysym in ("Return", "KP_Enter", "equal"):
            return self._bind_action(self.calculate)
        if keysym == "BackSpace":
            return self._bind_action(self.backspace)
        if keysym == "Escape":
            return self._bind_action(self.clear)
        return None

    def _bind_keys(self) -> None:
        self.root.bind("<Key>", self._on_key_press)

    def _update_display(self) -> None:
        self.display_var.set(format_expression(self.expression))

    def append(self, char: str) -> None:
        if self.expression == "0" and char not in "+-*/%.":
            self.expression = char
        elif self.expression == "Error":
            self.expression = char if char not in "+-*/%." else ""
            if char in "+-*/%.":
                self.expression += char
        else:
            self.expression += char
        self._update_display()

    def clear(self) -> None:
        self.expression = ""
        self._update_display()

    def backspace(self) -> None:
        if self.expression and self.expression != "Error":
            self.expression = self.expression[:-1]
        self._update_display()

    def toggle_sign(self) -> None:
        if not self.expression or self.expression == "Error":
            return
        if self.expression.startswith("-"):
            self.expression = self.expression[1:]
        else:
            self.expression = "-" + self.expression
        self._update_display()

    def calculate(self) -> None:
        if not self.expression or self.expression == "Error":
            return

        try:
            result = safe_evaluate(self.expression)
            if result.is_integer():
                result = int(result)
            self.expression = str(result)
        except ZeroDivisionError:
            self.expression = "Error"
        except (ValueError, SyntaxError, TypeError, OverflowError):
            self.expression = "Error"

        self._update_display()


def main() -> None:
    root = tk.Tk()
    Calculator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
