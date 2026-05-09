---
name: ocr_parsing_skill
description: Convert OCR text or screenshot images into structured transaction data
version: 0.2.0

input_schema:
  type: object
  properties:
    ocr_text: { type: string }
    image_base64: { type: string }
    image_path: { type: string }
    transaction_type: { type: string }
    language: { type: string }

output_schema:
  type: object
  required: [asset_code, direction]
  properties:
    asset_code: { type: string }
    asset_name: { type: [string, "null"] }
    quantity: { type: number }
    unit_price: { type: number }
    trade_time: { type: string }
    direction: { type: string }

pre_tools:
  - tool: ocr_extract
    when: "not ocr_text and (image_base64 or image_path)"
    args:
      image_base64: "{{ image_base64 }}"
      image_path: "{{ image_path }}"
      language: "{{ language or 'zh-CN' }}"
    output_var: ocr_extraction
    map_to_context:
      ocr_text: "{{ ocr_extraction.result.text }}"

ai:
  temperature: 0.2
  max_tokens: 2000
---

# System

You are a financial OCR parsing assistant. Return JSON only.

# Prompt

Extract a structured transaction from the OCR text.
Transaction type hint: {{ transaction_type or 'unknown' }}
OCR text: {{ ocr_text }}

Return JSON with keys asset_code, asset_name, quantity, unit_price, trade_time, direction.
