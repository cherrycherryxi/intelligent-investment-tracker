# 需求文档：智能外汇与债券投资追踪 Agent

## 介绍

智能外汇与债券投资追踪 Agent 是一个自动化投资管理系统，旨在帮助用户追踪和分析招商银行的外汇和柜台债交易。系统通过 OCR 技术识别交易截图，爬取历史汇率数据计算持仓成本，并使用 AI 推理模型提供投资建议。

## 术语表

- **System**: 智能外汇与债券投资追踪 Agent 系统
- **OCR_Engine**: 光学字符识别引擎，用于从图像中提取文本信息
- **Transaction_Parser**: 交易解析器，将 OCR 提取的文本转换为结构化交易数据
- **Exchange_Rate_Crawler**: 汇率爬虫，获取历史和实时汇率数据
- **Position_Calculator**: 持仓计算器，计算持仓成本、盈亏和收益率
- **Investment_Advisor**: 投资顾问模块，使用 AI 推理模型生成投资建议
- **Transaction_Repository**: 交易数据仓库，存储所有交易记录和持仓信息
- **Natural_Language_Processor**: 自然语言处理器，解析用户的自然语言交易输入
- **Screenshot**: 招商银行 APP 的交易历史记录截图
- **Position**: 持仓，包括外汇或债券的持有数量、成本和当前价值
- **Transaction**: 交易记录，包括买入/卖出、币种/债券、数量、价格、时间等信息
- **Historical_Exchange_Rate**: 历史汇率，特定时间点的货币兑换比率
- **Cost_Basis**: 成本基础，使用历史汇率计算的买入成本
- **PnL**: 盈亏（Profit and Loss），当前价值与成本基础的差额

## 需求

### 需求 1：批量截图导入与 OCR 识别

**用户故事：** 作为投资者，我想要上传多张招商银行 APP 的交易截图，以便系统自动识别并构建我的持仓数据。

#### 验收标准

1. WHEN 用户上传一张或多张交易截图，THE OCR_Engine SHALL 提取截图中的文本内容
2. WHEN OCR 提取完成，THE Transaction_Parser SHALL 解析文本并识别交易类型（外汇或柜台债）
3. WHEN 解析交易类型后，THE Transaction_Parser SHALL 提取交易字段（币种/债券代码、数量、价格、交易时间、交易方向）
4. IF OCR 识别置信度低于 80%，THEN THE System SHALL 标记该交易为待人工确认
5. WHEN 所有截图处理完成，THE System SHALL 生成交易记录摘要供用户审核
6. THE System SHALL 支持批量上传至少 50 张截图
7. WHEN 用户确认交易记录，THE Transaction_Repository SHALL 存储所有交易数据

### 需求 2：自然语言交易输入

**用户故事：** 作为投资者，我想要通过自然语言告诉系统新的交易信息，以便快速更新持仓数据而无需上传截图。

#### 验收标准

1. WHEN 用户输入自然语言交易描述，THE Natural_Language_Processor SHALL 解析交易意图
2. WHEN 解析交易意图后，THE Natural_Language_Processor SHALL 提取交易参数（币种/债券、数量、价格、时间、方向）
3. IF 交易参数不完整，THEN THE System SHALL 询问用户补充缺失信息
4. WHEN 交易参数完整，THE System SHALL 创建交易记录并显示给用户确认
5. WHEN 用户确认交易，THE Transaction_Repository SHALL 存储交易记录并更新持仓
6. THE Natural_Language_Processor SHALL 支持中文和英文输入
7. THE Natural_Language_Processor SHALL 识别常见交易表达（例如："买入 1000 美元"、"卖出 500 欧元"、"购买债券 123456"）

### 需求 3：历史汇率数据爬取

**用户故事：** 作为投资者，我想要系统自动获取交易时间点的历史汇率，以便准确计算我的买入成本。

#### 验收标准

1. WHEN 系统需要历史汇率数据，THE Exchange_Rate_Crawler SHALL 从可靠数据源爬取汇率数据
2. WHEN 爬取历史汇率时，THE Exchange_Rate_Crawler SHALL 使用交易时间戳作为查询参数
3. WHEN 爬取的汇率数据包含多个货币对，THE Exchange_Rate_Crawler SHALL 存储所有相关货币对的汇率
4. IF 特定时间点的汇率数据不可用，THEN THE Exchange_Rate_Crawler SHALL 使用最近可用时间点的汇率并标记为估算值
5. THE Exchange_Rate_Crawler SHALL 支持至少 10 种主要货币（USD、EUR、GBP、JPY、HKD、AUD、CAD、CHF、SGD、CNY）
6. THE Exchange_Rate_Crawler SHALL 缓存已爬取的汇率数据以减少重复请求
7. WHEN 爬取失败，THE Exchange_Rate_Crawler SHALL 重试最多 3 次，间隔 5 秒

### 需求 4：持仓成本计算

**用户故事：** 作为投资者，我想要系统使用历史汇率计算我的买入成本，以便了解真实的投资成本基础。

#### 验收标准

1. WHEN 计算外汇持仓成本，THE Position_Calculator SHALL 使用交易时间点的历史汇率转换为基准货币（CNY）
2. WHEN 存在多笔买入交易，THE Position_Calculator SHALL 使用加权平均法计算平均成本
3. WHEN 计算债券持仓成本，THE Position_Calculator SHALL 使用买入价格和数量计算总成本
4. THE Position_Calculator SHALL 计算每个持仓的成本基础（Cost_Basis）
5. THE Position_Calculator SHALL 计算每个持仓的当前价值（使用最新汇率或债券价格）
6. THE Position_Calculator SHALL 计算每个持仓的未实现盈亏（当前价值 - 成本基础）
7. THE Position_Calculator SHALL 计算每个持仓的收益率百分比（盈亏 / 成本基础 × 100%）

### 需求 5：持仓盈亏分析

**用户故事：** 作为投资者，我想要查看详细的持仓盈亏分析，以便了解我的投资表现。

#### 验收标准

1. WHEN 用户请求持仓分析，THE System SHALL 显示所有当前持仓的列表
2. WHEN 显示持仓列表时，THE System SHALL 包含币种/债券、持有数量、平均成本、当前价值、盈亏金额、收益率
3. THE System SHALL 计算并显示总投资成本
4. THE System SHALL 计算并显示总当前价值
5. THE System SHALL 计算并显示总盈亏金额和总收益率
6. THE System SHALL 支持按币种/债券类型筛选持仓
7. THE System SHALL 支持按盈亏金额或收益率排序持仓
8. THE System SHALL 提供持仓盈亏的可视化图表（饼图或柱状图）

### 需求 6：实时汇率更新

**用户故事：** 作为投资者，我想要系统定期更新实时汇率，以便查看最新的持仓价值。

#### 验收标准

1. THE Exchange_Rate_Crawler SHALL 每 15 分钟自动爬取最新汇率数据
2. WHEN 最新汇率更新后，THE Position_Calculator SHALL 重新计算所有外汇持仓的当前价值
3. WHEN 持仓价值更新后，THE System SHALL 通知用户持仓价值已更新
4. THE System SHALL 显示最后汇率更新时间
5. THE System SHALL 允许用户手动触发汇率更新
6. IF 汇率更新失败，THEN THE System SHALL 使用上次成功获取的汇率并显示警告

### 需求 7：AI 投资建议生成

**用户故事：** 作为投资者，我想要获得基于 AI 推理的投资建议，以便做出更明智的投资决策。

#### 验收标准

1. WHEN 用户请求投资建议，THE Investment_Advisor SHALL 分析当前持仓结构
2. WHEN 分析持仓结构时，THE Investment_Advisor SHALL 考虑持仓分布、盈亏状况、风险敞口
3. WHEN 分析完成后，THE Investment_Advisor SHALL 使用 AI 推理模型生成投资建议
4. THE Investment_Advisor SHALL 提供具体的操作建议（持有、买入、卖出）
5. THE Investment_Advisor SHALL 解释建议的理由和风险提示
6. THE Investment_Advisor SHALL 考虑市场趋势和历史汇率波动
7. WHERE 用户设置了风险偏好，THE Investment_Advisor SHALL 根据风险偏好调整建议策略

### 需求 8：交易历史查询

**用户故事：** 作为投资者，我想要查询历史交易记录，以便回顾我的交易决策。

#### 验收标准

1. WHEN 用户请求交易历史，THE System SHALL 显示所有交易记录列表
2. THE System SHALL 支持按时间范围筛选交易记录
3. THE System SHALL 支持按币种/债券筛选交易记录
4. THE System SHALL 支持按交易方向（买入/卖出）筛选交易记录
5. THE System SHALL 显示每笔交易的详细信息（时间、币种/债券、数量、价格、汇率、成本）
6. THE System SHALL 支持导出交易历史为 CSV 或 Excel 格式
7. THE System SHALL 按时间倒序显示交易记录（最新的在前）

### 需求 9：数据持久化与备份

**用户故事：** 作为投资者，我想要系统安全地存储我的交易数据，以便数据不会丢失。

#### 验收标准

1. THE Transaction_Repository SHALL 将所有交易记录持久化到数据库
2. THE Transaction_Repository SHALL 将所有持仓数据持久化到数据库
3. THE System SHALL 每天自动备份数据库
4. THE System SHALL 保留最近 30 天的数据库备份
5. THE System SHALL 提供数据导出功能（JSON 格式）
6. THE System SHALL 提供数据导入功能以恢复备份
7. WHEN 数据库操作失败，THE System SHALL 记录错误日志并通知用户

### 需求 10：RESTful API 接口

**用户故事：** 作为开发者，我想要通过 RESTful API 访问系统功能，以便集成到其他应用中。

#### 验收标准

1. THE System SHALL 提供 RESTful API 接口使用 FastAPI 框架
2. THE System SHALL 提供上传截图的 API 端点（POST /api/transactions/upload）
3. THE System SHALL 提供添加交易的 API 端点（POST /api/transactions）
4. THE System SHALL 提供查询持仓的 API 端点（GET /api/positions）
5. THE System SHALL 提供查询交易历史的 API 端点（GET /api/transactions）
6. THE System SHALL 提供获取投资建议的 API 端点（GET /api/advice）
7. THE System SHALL 提供 API 文档（OpenAPI/Swagger）
8. THE System SHALL 对所有 API 请求进行身份验证
9. WHEN API 请求失败，THE System SHALL 返回标准 HTTP 错误码和错误消息

### 需求 11：MCP Server 工具集成

**用户故事：** 作为系统架构师，我想要使用 MCP Server 架构组织工具层，以便实现模块化和可扩展性。

#### 验收标准

1. THE System SHALL 实现 MCP Server 架构作为工具层
2. THE System SHALL 提供 OCR 识别工具（mcp_tool: ocr_extract）
3. THE System SHALL 提供汇率查询工具（mcp_tool: get_exchange_rate）
4. THE System SHALL 提供持仓计算工具（mcp_tool: calculate_position）
5. THE System SHALL 提供交易解析工具（mcp_tool: parse_transaction）
6. THE System SHALL 提供投资建议工具（mcp_tool: generate_advice）
7. THE System SHALL 确保所有 MCP 工具可独立测试和调用
8. THE System SHALL 提供 MCP 工具的标准输入输出格式

### 需求 12：错误处理与日志记录

**用户故事：** 作为系统管理员，我想要系统记录详细的错误日志，以便快速诊断和解决问题。

#### 验收标准

1. WHEN 系统发生错误，THE System SHALL 记录错误详情到日志文件
2. THE System SHALL 记录所有 API 请求和响应
3. THE System SHALL 记录所有 OCR 识别结果和置信度
4. THE System SHALL 记录所有汇率爬取请求和结果
5. THE System SHALL 使用结构化日志格式（JSON）
6. THE System SHALL 支持日志级别配置（DEBUG、INFO、WARNING、ERROR）
7. THE System SHALL 自动轮转日志文件（每天或每 100MB）
8. WHEN 发生严重错误，THE System SHALL 发送告警通知

### 需求 13：配置管理

**用户故事：** 作为系统管理员，我想要通过配置文件管理系统参数，以便灵活调整系统行为。

#### 验收标准

1. THE System SHALL 从配置文件加载系统参数
2. THE System SHALL 支持配置 OCR 引擎参数（API 密钥、置信度阈值）
3. THE System SHALL 支持配置汇率数据源 URL
4. THE System SHALL 支持配置 AI 模型参数（API 密钥、模型名称、温度）
5. THE System SHALL 支持配置数据库连接参数
6. THE System SHALL 支持配置汇率更新频率
7. THE System SHALL 支持配置日志级别和日志路径
8. WHEN 配置文件格式错误，THE System SHALL 使用默认配置并记录警告

### 需求 14：用户界面（可选）

**用户故事：** 作为投资者，我想要通过友好的用户界面使用系统，以便更方便地管理投资。

#### 验收标准

1. WHERE 提供用户界面，THE System SHALL 提供上传截图的界面
2. WHERE 提供用户界面，THE System SHALL 提供输入自然语言交易的界面
3. WHERE 提供用户界面，THE System SHALL 提供查看持仓分析的仪表板
4. WHERE 提供用户界面，THE System SHALL 提供查看交易历史的界面
5. WHERE 提供用户界面，THE System SHALL 提供查看投资建议的界面
6. WHERE 提供用户界面，THE System SHALL 提供可视化图表（持仓分布、盈亏趋势）
7. WHERE 提供用户界面，THE System SHALL 支持响应式设计（桌面和移动设备）

### 需求 15：数据验证与一致性

**用户故事：** 作为投资者，我想要系统验证交易数据的正确性，以便确保持仓计算准确无误。

#### 验收标准

1. WHEN 添加交易记录时，THE System SHALL 验证交易数量大于零
2. WHEN 添加交易记录时，THE System SHALL 验证交易价格大于零
3. WHEN 添加交易记录时，THE System SHALL 验证交易时间不晚于当前时间
4. WHEN 添加卖出交易时，THE System SHALL 验证卖出数量不超过当前持仓
5. WHEN 计算持仓时，THE System SHALL 验证买入总量减去卖出总量等于当前持仓
6. IF 数据验证失败，THEN THE System SHALL 拒绝交易并返回验证错误消息
7. THE System SHALL 定期执行数据一致性检查并报告异常

## 非功能性需求

### 性能需求

1. THE OCR_Engine SHALL 在 5 秒内处理单张截图
2. THE System SHALL 在 30 秒内处理 50 张截图的批量上传
3. THE Exchange_Rate_Crawler SHALL 在 3 秒内返回单个汇率查询结果
4. THE Position_Calculator SHALL 在 2 秒内计算所有持仓的盈亏
5. THE Investment_Advisor SHALL 在 10 秒内生成投资建议

### 可靠性需求

1. THE System SHALL 达到 99% 的正常运行时间
2. THE System SHALL 在数据库故障时自动切换到备份数据库
3. THE System SHALL 在外部服务（OCR、汇率 API）不可用时降级运行

### 安全性需求

1. THE System SHALL 加密存储用户的敏感数据（API 密钥、交易记录）
2. THE System SHALL 使用 HTTPS 协议进行所有网络通信
3. THE System SHALL 实现用户身份验证和授权机制
4. THE System SHALL 记录所有安全相关事件（登录、数据访问）

### 可维护性需求

1. THE System SHALL 使用模块化架构以便独立更新各个组件
2. THE System SHALL 提供完整的单元测试覆盖率（至少 80%）
3. THE System SHALL 提供 API 文档和开发者指南
4. THE System SHALL 使用版本控制管理代码和配置

## 约束条件

1. 系统必须使用 Python 3.9 或更高版本
2. 系统必须使用 FastAPI 框架构建 RESTful API
3. 系统必须实现 MCP Server 架构作为工具层
4. 系统必须支持 Claude API 或 DeepSeek-R1 作为推理模型
5. 系统必须支持招商银行 APP 的交易截图格式
6. 系统必须支持至少 10 种主要货币的外汇交易
7. 系统必须支持柜台债交易

## 假设与依赖

1. 假设用户上传的截图清晰可读，OCR 识别率可达 80% 以上
2. 假设历史汇率数据可从公开数据源获取（如中国人民银行、外汇管理局）
3. 假设用户具有基本的投资知识，能理解投资建议
4. 依赖第三方 OCR 服务（如 Tesseract、百度 OCR、腾讯 OCR）
5. 依赖第三方汇率数据 API（如 ExchangeRate-API、Fixer.io）
6. 依赖 AI 推理模型 API（Claude API 或 DeepSeek-R1）
