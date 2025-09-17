---
name: integrate-apicore-basic-support
epic: image-generation-enhancement
status: completed
priority: high
created: 2025-09-17T16:16:26Z
updated: 2025-09-17T17:24:11Z
phase: 2
depends_on: [fix-num-images-functionality]
tags: [api-integration, apicore, new-provider]
---

# Task: 集成 APICore.ai 基础支持

## Overview
在现有插件中添加 APICore.ai 作为第三个 API 提供商，实现基础的图像生成功能，包括标准和高清两个模型的支持。

## Technical Details

### Implementation Scope
- 添加 APICore.ai 到提供商选择列表
- 实现 Bearer token 认证机制
- 支持标准和 HD 两个模型
- 实现基础的单图和多图生成

### Code Changes Required

#### 1. 更新提供商枚举
```python
# 在 Tutu.py 的 INPUT_TYPES 中
"api_provider": (["ai.comfly.chat", "OpenRouter", "APICore.ai"], {
    "default": "ai.comfly.chat"
}),
```

#### 2. 添加模型映射
```python
# 在模型选择逻辑中添加
apicore_models = [
    "[APICore] gemini-2.5-flash-image",
    "[APICore] gemini-2.5-flash-image-hd"
]
```

#### 3. 实现 API 端点配置
```python
if api_provider == "APICore.ai":
    api_endpoint = "https://ismaque.org/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_keys.get('apicore_api_key', '')}",
        "Content-Type": "application/json"
    }
```

#### 4. 适配请求格式
```python
# APICore.ai 使用不同的请求格式
if api_provider == "APICore.ai":
    data = {
        "prompt": enhanced_prompt,
        "model": clean_model_name,
        "size": "1x1",
        "n": num_images
    }
else:
    # 现有的 OpenAI 兼容格式
    data = {
        "model": selected_model,
        "messages": messages,
        "n": num_images,
        "stream": True
    }
```

#### 5. 处理响应格式
- APICore.ai 可能返回标准 JSON 而非 SSE 流
- 需要适配不同的响应解析逻辑
- 提取图片 URL 并下载转换为张量格式

### Configuration Updates

#### 扩展 Tutuapi.json
```json
{
    "comfly_api_key": "existing_key",
    "openrouter_api_key": "existing_key",
    "apicore_api_key": "your_apicore_api_key_here"
}
```

#### 密钥验证
- 添加 APICore.ai 密钥存在性检查
- 提供友好的配置错误提示

### Testing Strategy
1. **基础连接测试**: 验证 API 端点可达性
2. **认证测试**: 验证 Bearer token 认证工作正常
3. **模型测试**: 分别测试标准和 HD 模型
4. **功能对比测试**: 与现有提供商对比功能一致性

## Acceptance Criteria
- [x] APICore.ai 出现在提供商下拉列表中
- [x] 两个模型都可以正常选择和使用
- [x] 单图生成功能正常（num_images=1）
- [x] 多图生成功能正常（num_images=2-4）
- [x] 生成的图片质量和格式符合预期
- [x] 错误处理和用户反馈完善
- [x] 配置文件正确支持新的 API 密钥

## Risk Factors
- **中风险**: 新 API 的响应格式可能与现有逻辑不兼容
- **中风险**: 认证机制改变可能引入安全问题
- **缓解**: 增量测试，保留原有提供商作为备选

## Dependencies
- 依赖 Task 1 (fix-num-images-functionality) 完成
- 需要有效的 APICore.ai 测试密钥
- 依赖现有的图像处理工具函数

## Estimated Effort
- **API 端点集成**: 8小时
- **认证和配置**: 4小时
- **响应处理适配**: 6小时
- **测试验证**: 2小时
- **总计**: 20小时 (2.5个工作日)