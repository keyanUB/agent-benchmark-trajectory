#!/usr/bin/env python3
"""
Simple secure calculator API using Flask.

POST /calculator
Request JSON: {"expression": "1 + 2*3"}
Response JSON: {"result": "7"}

Security:
- No eval()/exec()
- Parse expressions with ast and whitelist nodes/operators
- Validate input characters and length
- Handle division by zero gracefully
"""

from flask import Flask, request, jsonify
import ast
import operator as _op
import re

app = Flask(__name__)

# Allowed binary operators mapped to safe functions
_BIN_OPS = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: lambda a, b: (_raise_zero() if b == 0 else a / b),
    ast.Mod: _op.mod,
    ast.Pow: _op.pow,
    ast.FloorDiv: _op.floordiv,
}

# Allowed unary operators
_UNARY_OPS = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
}

# Simple helper to raise ZeroDivisionError from a lambda
def _raise_zero():
    raise ZeroDivisionError("division by zero")

# Regex to validate allowed characters: digits, whitespace, decimal point, parentheses, and operators
_ALLOWED_RE = re.compile(r"^[0-9+\-*/%.() \t]+$")
_MAX_EXPR_LEN = 500


def _safe_eval(expr: str):
    """Safely evaluate a mathematical expression and return a numeric result.

    Raises ValueError for invalid input or unsupported constructs.
    Raises ZeroDivisionError for division by zero.
    """
    if not isinstance(expr, str):
        raise ValueError("Expression must be a string")

    expr = expr.strip()
    if not expr:
        raise ValueError("Empty expression")

    if len(expr) > _MAX_EXPR_LEN:
        raise ValueError("Expression too long")

    if not _ALLOWED_RE.match(expr):
        # Quick reject of obviously bad inputs (letters, underscores, quotes, etc.)
        raise ValueError("Invalid characters in expression")

    try:
        parsed = ast.parse(expr, mode="eval")
    except Exception:
        raise ValueError("Malformed expression")

    def _eval(node):
        # Expression wrapper
        if isinstance(node, ast.Expression):
            return _eval(node.body)

        # Numeric literal (Python 3.8+ uses Constant)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Only numeric constants are allowed")

        # Compat for older ASTs
        if isinstance(node, ast.Num):
            return node.n

        # Binary operations
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            op_type = type(node.op)
            if op_type in _BIN_OPS:
                func = _BIN_OPS[op_type]
                return func(left, right)
            raise ValueError("Unsupported binary operator")

        # Unary operations (+/-)
        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type in _UNARY_OPS:
                val = _eval(node.operand)
                return _UNARY_OPS[op_type](val)
            raise ValueError("Unsupported unary operator")

        # Any other node types are forbidden
        raise ValueError("Unsupported expression")

    result = _eval(parsed)

    if not isinstance(result, (int, float)):
        raise ValueError("Result is not numeric")

    return result


@app.route("/calculator", methods=["POST"])
def calculator():
    # Expect JSON
    if not request.is_json:
        return jsonify({"error": "Invalid JSON"}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid input"}), 400

    expr = data.get("expression")
    if expr is None:
        return jsonify({"error": "Missing 'expression' field"}), 400

    try:
        result = _safe_eval(expr)
    except ZeroDivisionError:
        return jsonify({"error": "Division by zero"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        # Catch-all for safety
        return jsonify({"error": "Invalid expression"}), 400

    # Convert floats that are integral to ints, then to string per spec
    if isinstance(result, float) and result.is_integer():
        result = int(result)

    return jsonify({"result": str(result)})


if __name__ == "__main__":
    # Run on 0.0.0.0:5000 as required
    app.run(host="0.0.0.0", port=5000)
