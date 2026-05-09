---
name: transaction_analysis_skill
description: Analyze transaction history for frequency, anomalies, and concentration
version: 0.2.0

input_schema:
  type: object
  required: [transactions]
  properties:
    transactions: { type: array }

output_schema:
  type: object
  properties:
    frequency_summary: { type: string }
    anomalies: { type: array }
    concentration_risk: { type: string }
    recommendations: { type: array }

ai:
  temperature: 0.2
  max_tokens: 1500
---

# System

You are a transaction analysis assistant. Return JSON only.

# Prompt

Analyze the following transaction list for patterns, anomalies, and concentration risks.
Transactions: {{ transactions | tojson }}

Return JSON with keys frequency_summary, anomalies, concentration_risk, recommendations.
