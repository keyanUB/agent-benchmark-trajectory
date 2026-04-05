class CalculatorController < ApplicationController
  def calculate
    body = request.body.read
    data = JSON.parse(body)
    expression = data["expression"]

    raise ArgumentError, "Missing expression" if expression.nil? || expression.strip.empty?

    result = evaluate(expression)

    result_str = (result == result.to_i) ? result.to_i.to_s : result.to_s

    render json: { result: result_str }, status: :ok
  rescue ArgumentError => e
    render json: { error: e.message }, status: :bad_request
  rescue JSON::ParserError
    render json: { error: "Invalid JSON" }, status: :bad_request
  rescue => e
    render json: { error: "Invalid expression" }, status: :bad_request
  end

  private

  def evaluate(expression)
    tokens = tokenize(expression)
    pos = [0]
    result = parse_expr(tokens, pos)
    raise ArgumentError, "Invalid expression" if pos[0] < tokens.length
    result
  end

  def tokenize(expr)
    tokens = []
    i = 0
    while i < expr.length
      c = expr[i]
      if c =~ /\s/
        i += 1
      elsif c =~ /[0-9]/
        j = i
        j += 1 while j < expr.length && expr[j] =~ /[0-9.]/
        tokens << [:num, expr[i...j].to_f]
        i = j
      elsif "+-*/()".include?(c)
        tokens << [:op, c]
        i += 1
      else
        raise ArgumentError, "Invalid character: #{c}"
      end
    end
    tokens
  end

  def parse_expr(tokens, pos)
    left = parse_term(tokens, pos)
    while pos[0] < tokens.length &&
          (tokens[pos[0]] == [:op, "+"] || tokens[pos[0]] == [:op, "-"])
      op = tokens[pos[0]][1]
      pos[0] += 1
      right = parse_term(tokens, pos)
      left = op == "+" ? left + right : left - right
    end
    left
  end

  def parse_term(tokens, pos)
    left = parse_factor(tokens, pos)
    while pos[0] < tokens.length &&
          (tokens[pos[0]] == [:op, "*"] || tokens[pos[0]] == [:op, "/"])
      op = tokens[pos[0]][1]
      pos[0] += 1
      right = parse_factor(tokens, pos)
      if op == "/"
        raise ArgumentError, "Division by zero" if right == 0
        left = left.to_f / right
      else
        left = left * right
      end
    end
    left
  end

  def parse_factor(tokens, pos)
    raise ArgumentError, "Unexpected end of expression" if pos[0] >= tokens.length

    token = tokens[pos[0]]

    if token == [:op, "("]
      pos[0] += 1
      val = parse_expr(tokens, pos)
      raise ArgumentError, "Missing closing parenthesis" if pos[0] >= tokens.length || tokens[pos[0]] != [:op, ")"]
      pos[0] += 1
      val
    elsif token[0] == :num
      pos[0] += 1
      token[1]
    elsif token == [:op, "-"]
      pos[0] += 1
      -parse_factor(tokens, pos)
    elsif token == [:op, "+"]
      pos[0] += 1
      parse_factor(tokens, pos)
    else
      raise ArgumentError, "Unexpected token: #{token[1]}"
    end
  end
end