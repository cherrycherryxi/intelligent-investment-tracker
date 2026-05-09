---
name: investment_advice_skill
description: Generate AI-based portfolio advice with a deterministic portfolio summary
version: 0.2.0

input_schema:
  type: object
  required: [positions]
  properties:
    positions: { type: array }
    market_data: { type: object }
    risk_preference: { type: string }

output_schema:
  type: object
  required: [advice, portfolio_summary]
  properties:
    advice: { type: object }
    portfolio_summary: { type: object }

pre_tools:
  - tool: build_portfolio_summary
    args:
      positions: "{{ positions }}"
    output_var: summary_result
    map_to_context:
      portfolio_summary: "{{ summary_result.result.portfolio_summary }}"

ai:
  temperature: 0.2
  max_tokens: 2000
---

# System

You are a cautious investment advisor. Return JSON only with keys: advice, portfolio_summary.

# Prompt

Generate investment advice as JSON.
Risk preference: {{ risk_preference or 'balanced' }}
Portfolio summary: {{ portfolio_summary | tojson }}
Market data: {{ market_data | tojson if market_data else '{}' }}

Return JSON shaped as:
{
  "portfolio_summary": <copy of the input portfolio_summary>,
  "advice": {
    "summary": <string>,
    "risk_level": <string>,
    "actions": [{ "asset_code": <string>, "action": <string>, "rationale": <string> }],
    "reasoning": <string>,
    "warnings": [<string>]
  }
}
