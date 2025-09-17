---
name: fix-num-images-functionality
epic: image-generation-enhancement
status: todo
priority: critical
created: 2025-09-17T16:16:26Z
estimated_hours: 16
phase: 1
depends_on: []
tags: [core-fix, num-images, api-request]
---

# Task: 修复 num_images 批量生成功能

## Overview
修复当前 num_images 参数无法正确生成指定数量图片的核心问题。确保用户设置 num_images=3 时能实际生成 3 张不同的图片。

## Technical Details

### Root Cause Analysis
- API 请求中的 `"n"` 参数未正确传递 num_images 值
- 响应解析逻辑可能无法处理多图片返回格式
- 输出格式需要符合 ComfyUI 标准张量格式

### Implementation Approach

#### 1. 修复请求参数传递
```python
# 在 Tutu.py 中的 API 请求部分
data = {
    "model": selected_model,
    "messages": messages,
    "n": num_images,  # 确保正确传递
    "stream": True
}
```

#### 2. 优化响应解析
- 检查当前 SSE 流解析逻辑（第460-800行）
- 确保能正确处理包含多张图片的响应
- 验证 JSON 解析的健壮性

#### 3. 标准化输出格式
- 确保返回的图片列表符合 ComfyUI 的张量格式
- 维护现有的 tensor2pil/pil2tensor 转换机制
- 处理图片数量不匹配的异常情况

### Key Files to Modify
- `Tutu.py`: 主要的 API 调用和响应处理逻辑
- 重点关注 `TutuGeminiAPI` 类的实现

### Testing Strategy
1. **单图测试**: num_images=1，验证不影响现有功能
2. **多图测试**: num_images=2,3,4，验证每种情况
3. **边界测试**: 测试 num_images 边界值处理
4. **错误测试**: 测试 API 返回数量不匹配的情况

## Acceptance Criteria
- [ ] num_images=1 时生成 1 张图片（向后兼容）
- [ ] num_images=2 时生成 2 张不同图片
- [ ] num_images=3 时生成 3 张不同图片
- [ ] num_images=4 时生成 4 张不同图片
- [ ] 所有现有提供商（ai.comfly.chat, OpenRouter）都支持
- [ ] 生成的图片格式符合 ComfyUI 标准
- [ ] 错误情况下提供清晰的错误信息

## Risk Factors
- **高风险**: 修改可能影响现有单图生成功能
- **中风险**: SSE 解析逻辑复杂，可能引入新bug
- **缓解**: 充分的回归测试，逐步验证

## Dependencies
- 需要有效的 API 密钥进行测试
- 依赖现有的 utils.py 图像转换函数

## Estimated Effort
- **分析调试**: 4小时
- **代码修改**: 8小时
- **测试验证**: 4小时
- **总计**: 16小时 (2个工作日)