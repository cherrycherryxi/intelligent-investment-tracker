---
name: risk_assessment_skill
description: Assess portfolio risk level, drivers, and diversification suggestions
version: 0.2.0

input_schema:
  type: object
  required: [positions]
  properties:
    positions: { type: array }
    volatility_data: { type: object }

output_schema:
  type: object
  required: [risk_level]
  properties:
    risk_level: { type: string }
    factors: { type: array }
    diversification_suggestions: { type: array }

ai:
  temperature: 0.2
  max_tokens: 1500
---

# System

You are a portfolio risk assessment assistant. Return JSON only.

# Prompt

Assess the portfolio risk.
Positions: {{ positions | tojson }}
Volatility data: {{ volatility_data | tojson if volatility_data else '{}' }}

Return JSON with keys risk_level, factors, diversification_suggestions.
