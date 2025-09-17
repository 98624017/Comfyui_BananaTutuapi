---
name: refactor-and-cleanup-codebase
epic: image-generation-enhancement
status: todo
priority: low
created: 2025-09-17T16:16:26Z
estimated_hours: 14
phase: 3
depends_on: [fix-num-images-functionality, integrate-apicore-basic-support, implement-multi-image-reference, optimize-configuration-management, unify-error-handling]
tags: [refactoring, cleanup, performance, maintainability]
---

# Task: 重构和清理代码库

## Overview
在完成所有功能开发后，进行代码重构和清理，移除废弃代码，优化性能，提升代码维护性和质量。

## Technical Details

### Code Cleanup Scope

#### 1. 移除废弃和无效代码
```python
# 目标清理内容：
- 未使用的导入语句
- 注释掉的废弃代码块
- 未使用的函数和变量
- 重复的代码逻辑
- 过时的注释和文档
```

#### 2. 简化复杂的 SSE 解析逻辑
当前 `Tutu.py` 第460-800行包含复杂的 SSE 流解析逻辑：
```python
# 重构目标：
def simplify_sse_parsing():
    """简化流式响应解析"""
    # 分析 APICore.ai 是否需要 SSE
    # 如果不需要，为 APICore.ai 实现标准 JSON 解析
    # 保留并优化现有提供商的 SSE 解析
    # 减少代码复杂度和维护成本
```

#### 3. 性能优化
```python
# 优化重点：
- 减少不必要的图像转换操作
- 优化内存使用，及时释放资源
- 减少重复的网络请求
- 缓存配置读取结果
- 优化图像处理管道
```

#### 4. 代码结构优化
```python
# 重构架构：
class APIProviderFactory:
    """API 提供商工厂类"""
    @staticmethod
    def create_provider(provider_name):
        providers = {
            "ai.comfly.chat": ComflyProvider,
            "OpenRouter": OpenRouterProvider,
            "APICore.ai": APICoreProvider
        }
        return providers.get(provider_name)

class BaseAPIProvider:
    """API 提供商基类"""
    def authenticate(self):
        raise NotImplementedError

    def format_request(self, prompt, num_images):
        raise NotImplementedError

    def parse_response(self, response):
        raise NotImplementedError
```

### Refactoring Strategy

#### 1. 模块化 API 提供商
```python
# 将每个 API 提供商封装为独立类
class APICoreProvider(BaseAPIProvider):
    def __init__(self, api_key):
        self.api_key = api_key
        self.endpoint = "https://ismaque.org/v1/images/generations"

    def authenticate(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def format_request(self, prompt, num_images, model):
        return {
            "prompt": prompt,
            "model": model,
            "size": "1x1",
            "n": num_images
        }

    def parse_response(self, response):
        # 标准 JSON 响应解析
        return extract_images_from_json(response)
```

#### 2. 统一接口设计
```python
def generate_images(provider, prompt, num_images, model):
    """统一的图像生成接口"""
    api_provider = APIProviderFactory.create_provider(provider)

    try:
        # 格式化请求
        request_data = api_provider.format_request(prompt, num_images, model)

        # 发送请求
        response = send_api_request(
            api_provider.endpoint,
            request_data,
            api_provider.authenticate()
        )

        # 解析响应
        images = api_provider.parse_response(response)
        return validate_and_convert_images(images, num_images)

    except Exception as e:
        return handle_api_error(e, provider)
```

#### 3. 配置管理重构
```python
class ConfigManager:
    """配置管理器"""
    _instance = None
    _config = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_api_key(self, provider):
        if self._config is None:
            self._config = self.load_config()
        return self._config.get(f"{provider.lower()}_api_key")

    def load_config(self):
        # 缓存配置读取结果
        # 实现配置热重载
        pass
```

### Quality Improvements

#### 1. 代码风格统一
```python
# 应用统一的代码风格：
- 使用一致的命名约定
- 统一缩进和格式
- 添加类型提示（如果项目支持）
- 完善函数文档字符串
```

#### 2. 错误处理完善
```python
# 统一错误处理模式：
def safe_api_call(func):
    """装饰器：安全的 API 调用"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"API 调用失败: {func.__name__} - {str(e)}")
            return create_error_output(str(e))
    return wrapper
```

#### 3. 性能监控
```python
import time
from functools import wraps

def measure_performance(func):
    """性能监控装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()

        logger.info(f"{func.__name__} 执行时间: {end_time - start_time:.2f}s")
        return result
    return wrapper
```

### Testing and Validation

#### 1. 重构验证
- 确保所有现有功能保持不变
- 验证性能确实有所提升
- 检查代码复杂度指标
- 运行完整的回归测试套件

#### 2. 代码质量检查
```bash
# 使用代码质量工具：
- flake8: 代码风格检查
- pylint: 代码质量分析
- radon: 圈复杂度计算
- bandit: 安全检查
```

## Acceptance Criteria
- [ ] 代码行数减少至少 15%
- [ ] 圈复杂度降低到 < 10
- [ ] 移除所有未使用的导入和函数
- [ ] 无静态代码分析警告
- [ ] 所有现有功能正常工作
- [ ] 性能测试显示响应时间减少 ≥ 20%
- [ ] 代码结构更清晰，更易于维护

## Risk Factors
- **高风险**: 大规模重构可能引入回归错误
- **中风险**: 性能优化可能影响功能稳定性
- **缓解**: 全面的测试覆盖，渐进式重构

## Dependencies
- 依赖所有前面的功能任务完成
- 需要完整的测试套件来验证重构结果

## Estimated Effort
- **代码清理**: 4小时
- **SSE 逻辑简化**: 4小时
- **架构重构**: 4小时
- **性能优化**: 2小时
- **总计**: 14小时 (1.75个工作日)