---
name: natural_language_understanding_skill
description: Extract structured trade parameters from natural language input
version: 0.2.0

input_schema:
  type: object
  required: [text]
  properties:
    text: { type: string }

output_schema:
  type: object
  properties:
    intent: { type: string }
    language: { type: string }
    transaction_type: { type: string }
    parameters: { type: object }
    missing_fields: { type: array }

pre_tools:
  - tool: parse_natural_language
    args:
      text: "{{ text }}"
    output_var: rule_result
    short_circuit_if: "rule_result.ok and not rule_result.result.missing_fields"
    short_circuit_return: "{{ rule_result.result }}"

ai:
  temperature: 0.2
  max_tokens: 1500
  on_failure: return_var
  on_failure_var: rule_result.result
---

# System

You are a financial NLU assistant. Return JSON only.

# Prompt

Extract trade parameters from the user input.
User input: {{ text }}
Partial rule-based result (may have gaps): {{ rule_result.result | tojson if rule_result else '{}' }}

Return JSON with keys intent, language, transaction_type, parameters, missing_fields.
The parameters object should include asset_code, direction, quantity, unit_price, trade_currency, trade_time.
