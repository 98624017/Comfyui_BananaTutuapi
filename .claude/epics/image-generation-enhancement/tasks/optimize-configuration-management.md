---
name: optimize-configuration-management
epic: image-generation-enhancement
status: todo
priority: medium
created: 2025-09-17T16:16:26Z
estimated_hours: 8
phase: 2
depends_on: [integrate-apicore-basic-support]
tags: [configuration, api-keys, validation, security]
---

# Task: 优化配置管理

## Overview
改进 API 密钥配置管理，添加 APICore.ai 支持，增强密钥验证和安全性，提供更好的用户配置体验。

## Technical Details

### Configuration Enhancements

#### 1. 扩展配置文件结构
```json
// Tutuapi.json 新结构
{
    "comfly_api_key": "your_comfly_api_key_here",
    "openrouter_api_key": "your_openrouter_api_key_here",
    "apicore_api_key": "your_apicore_api_key_here",
    "config_version": "2.0",
    "default_provider": "ai.comfly.chat"
}
```

#### 2. 配置加载增强
```python
def load_api_keys():
    """加载和验证 API 配置"""
    config_path = os.path.join(os.path.dirname(__file__), "Tutuapi.json")

    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = json.load(file)

        # 配置版本迁移
        if config.get('config_version', '1.0') < '2.0':
            config = migrate_config_v2(config)

        return config
    except Exception as e:
        # 创建默认配置
        return create_default_config()
```

#### 3. 密钥验证机制
```python
def validate_api_key(provider, api_key):
    """验证 API 密钥格式和可用性"""
    if not api_key or api_key.endswith("_here"):
        return False, f"{provider} API 密钥未配置"

    # 基础格式验证
    format_checks = {
        "APICore.ai": lambda k: k.startswith("sk-") and len(k) > 20,
        "OpenRouter": lambda k: k.startswith("sk-") and len(k) > 20,
        "ai.comfly.chat": lambda k: len(k) > 10
    }

    if provider in format_checks:
        if not format_checks[provider](api_key):
            return False, f"{provider} API 密钥格式无效"

    return True, "密钥格式有效"

def test_api_connection(provider, api_key):
    """测试 API 连接可用性（可选的轻量级测试）"""
    # 实现简单的连接测试
    pass
```

#### 4. 配置安全性改进
```python
def secure_log_config(config):
    """安全地记录配置信息，隐藏敏感数据"""
    safe_config = {}
    for key, value in config.items():
        if 'key' in key.lower():
            # 只显示前4个和后4个字符
            if len(value) > 8:
                safe_config[key] = f"{value[:4]}...{value[-4:]}"
            else:
                safe_config[key] = "***"
        else:
            safe_config[key] = value
    return safe_config
```

### Error Handling Improvements

#### 1. 配置错误处理
```python
class ConfigurationError(Exception):
    """配置相关的异常"""
    pass

def get_api_key_for_provider(provider):
    """获取指定提供商的 API 密钥，带完整错误处理"""
    config = load_api_keys()
    key_mapping = {
        "ai.comfly.chat": "comfly_api_key",
        "OpenRouter": "openrouter_api_key",
        "APICore.ai": "apicore_api_key"
    }

    key_name = key_mapping.get(provider)
    if not key_name:
        raise ConfigurationError(f"不支持的 API 提供商: {provider}")

    api_key = config.get(key_name, "")
    is_valid, message = validate_api_key(provider, api_key)

    if not is_valid:
        raise ConfigurationError(f"配置错误: {message}")

    return api_key
```

#### 2. 用户友好的错误信息
```python
def get_config_help_message(provider):
    """为不同提供商提供配置帮助信息"""
    help_messages = {
        "APICore.ai": """
APICore.ai 配置说明:
1. 访问 APICore.ai 官网获取 API 密钥
2. 在 Tutuapi.json 中设置 'apicore_api_key' 字段
3. 密钥格式应为 'sk-' 开头的字符串
""",
        "OpenRouter": "OpenRouter 配置说明...",
        "ai.comfly.chat": "Comfly 配置说明..."
    }
    return help_messages.get(provider, "请检查 API 密钥配置")
```

### Testing and Migration

#### 1. 配置迁移测试
- 测试从旧版配置文件的平滑迁移
- 验证新字段的正确添加
- 确保向后兼容性

#### 2. 密钥验证测试
- 测试各种无效密钥格式的处理
- 验证错误信息的准确性
- 测试安全日志输出

## Acceptance Criteria
- [ ] Tutuapi.json 正确支持 APICore.ai 密钥配置
- [ ] 密钥格式验证工作正常
- [ ] 提供清晰的配置错误信息和帮助
- [ ] 日志中不泄露完整的 API 密钥信息
- [ ] 支持从旧版配置的平滑迁移
- [ ] 测试密钥在完成后被安全移除

## Risk Factors
- **低风险**: 配置管理相对独立，影响有限
- **安全风险**: 需要确保 API 密钥不在日志中泄露
- **缓解**: 完善的安全日志机制和配置验证

## Dependencies
- 依赖 Task 2 (integrate-apicore-basic-support) 的基础结构
- 需要测试用的有效 API 密钥

## Estimated Effort
- **配置结构扩展**: 2小时
- **验证机制实现**: 3小时
- **安全性改进**: 2小时
- **测试验证**: 1小时
- **总计**: 8小时 (1个工作日)