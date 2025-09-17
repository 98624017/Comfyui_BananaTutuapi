---
name: implement-multi-image-reference
epic: image-generation-enhancement
status: todo
priority: medium
created: 2025-09-17T16:16:26Z
estimated_hours: 12
phase: 2
depends_on: [integrate-apicore-basic-support]
tags: [multi-image, reference, apicore, prompt-format]
---

# Task: 实现多图片参考功能

## Overview
为 APICore.ai 提供商实现多图片参考功能，支持用户提供的多图片 URL 格式输入，实现更丰富的图像生成控制。

## Technical Details

### Feature Specification
支持用户输入格式：
```
"https://filesystem.site/cdn/20250807/图片1.jpeg https://filesystem.site/cdn/20250807/图片2.jpeg https://filesystem.site/cdn/20250807/图片3.png 将图片1和图片2的角色放在图片3的场景"
```

### Implementation Approach

#### 1. 提示词解析
```python
def parse_multi_image_prompt(prompt):
    """
    解析包含多个图片URL的提示词
    返回: (image_urls, text_description)
    """
    import re

    # 匹配 URL 模式
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, prompt)

    # 提取纯文本描述
    text_only = re.sub(url_pattern, '', prompt).strip()

    return urls, text_only
```

#### 2. APICore.ai 专用请求格式
```python
if api_provider == "APICore.ai":
    urls, description = parse_multi_image_prompt(prompt)

    if urls:
        # 多图片参考格式
        enhanced_prompt = f"{' '.join(urls)} {description}"
    else:
        # 标准文本提示
        enhanced_prompt = prompt

    data = {
        "prompt": enhanced_prompt,
        "model": clean_model_name,
        "size": "1x1",
        "n": num_images
    }
```

#### 3. 输入验证
- 验证 URL 格式的有效性
- 检查图片 URL 的可访问性（可选）
- 限制最大图片数量（如最多5张）
- 提供格式错误的友好提示

#### 4. UI 体验优化
- 在提示词输入框添加格式说明
- 提供示例格式的工具提示
- 区分 APICore.ai 和其他提供商的输入方式

### Code Integration Points

#### 修改提示词处理逻辑
```python
# 在 TutuGeminiAPI.generate 方法中
if api_provider == "APICore.ai":
    # 特殊处理多图片参考格式
    processed_prompt = handle_apicore_prompt(prompt)
else:
    # 现有的提示词处理逻辑
    processed_prompt = handle_standard_prompt(prompt)
```

#### 兼容性考虑
- 确保多图片功能不影响其他提供商
- 保持向后兼容，普通文本提示仍然有效
- 提供清晰的功能边界说明

### Testing Strategy
1. **格式解析测试**: 验证 URL 和文本正确分离
2. **多图片生成测试**: 使用示例格式测试实际生成
3. **边界测试**: 测试无 URL、单 URL、多 URL 各种情况
4. **兼容性测试**: 确保不影响其他提供商功能

## Acceptance Criteria
- [ ] 支持示例格式的多图片 URL 输入
- [ ] 正确解析和分离 URL 与文本描述
- [ ] 多图片参考生成的图像符合预期
- [ ] 提供清晰的格式说明和错误提示
- [ ] 不影响其他提供商的正常功能
- [ ] 普通文本提示在 APICore.ai 下仍然有效

## Risk Factors
- **低风险**: 功能相对独立，影响范围有限
- **中风险**: URL 解析逻辑可能有边界情况
- **缓解**: 充分的单元测试和格式验证

## Dependencies
- 依赖 Task 2 (integrate-apicore-basic-support) 完成
- 需要 APICore.ai 的多图片参考功能正常工作

## Estimated Effort
- **提示词解析**: 4小时
- **API 集成**: 4小时
- **UI 优化**: 2小时
- **测试验证**: 2小时
- **总计**: 12小时 (1.5个工作日)