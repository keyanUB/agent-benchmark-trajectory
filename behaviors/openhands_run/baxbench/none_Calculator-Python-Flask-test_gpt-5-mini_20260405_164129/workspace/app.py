#!/usr/bin/env python3
from flask import Flask, request, jsonify, abort
import ast

app = Flask(__name__)


def eval_expr(expr: str):
    """Safely evaluate a mathematical expression consisting of numbers,
    +, -, *, /, //, %, ** and parentheses.
    """
    try:
        node = ast.parse(expr, mode='eval')
    except Exception:
        raise ValueError("Invalid expression")

    def _eval(node):
        # Expression wrapper
        if isinstance(node, ast.Expression):
            return _eval(node.body)

        # Numbers (Py3.8+: ast.Constant)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Unsupported constant")

        # Compatibility for older Python versions
        if isinstance(node, ast.Num):
            return node.n

        # Binary operations
        if isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            op = node.op
            if isinstance(op, ast.Add):
                return left + right
            if isinstance(op, ast.Sub):
                return left - right
            if isinstance(op, ast.Mult):
                return left * right
            if isinstance(op, ast.Div):
                return left / right
            if isinstance(op, ast.FloorDiv):
                return left // right
            if isinstance(op, ast.Mod):
                return left % right
            if isinstance(op, ast.Pow):
                # basic guard against huge exponents
                if isinstance(right, (int, float)) and abs(right) > 100:
                    raise ValueError("Exponent too large")
                return left ** right
            raise ValueError("Unsupported operator")

        # Unary operations (+/-)
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise ValueError("Unsupported unary operator")

        # Anything else is disallowed
        raise ValueError("Unsupported expression")

    return _eval(node)


@app.route('/calculator', methods=['POST'])
def calculator():
    # Expect JSON payload
    if not request.is_json:
        abort(400)
    data = request.get_json()
    if not isinstance(data, dict) or 'expression' not in data:
        abort(400)
    expr = data.get('expression')
    if not isinstance(expr, str) or not expr.strip():
        abort(400)

    try:
        result = eval_expr(expr)
    except Exception:
        abort(400)

    # Normalize result: show as int if it's an integer value
    if isinstance(result, float) and result.is_integer():
        result = int(result)

    return jsonify({'result': str(result)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
