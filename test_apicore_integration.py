#!/usr/bin/env python3
"""
APICore.ai集成测试脚本
测试请求响应处理逻辑
"""

import json
import sys
import os

# 添加模块路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Tutu import TutuGeminiAPI, clean_model_name

def test_clean_model_name():
    """测试模型名称清理功能"""
    print("=== 测试模型名称清理功能 ===")

    test_cases = [
        ("[APICore] gemini-2.5-flash-image", "gemini-2.5-flash-image"),
        ("[APICore] gemini-2.5-flash-image-hd", "gemini-2.5-flash-image-hd"),
        ("[Comfly] gemini-2.5-flash-image-preview", "gemini-2.5-flash-image-preview"),
        ("no-tag-model", "no-tag-model"),
        ("[Invalid] model", "model")
    ]

    for input_model, expected in test_cases:
        result = clean_model_name(input_model)
        status = "✓" if result == expected else "✗"
        print(f"{status} {input_model} -> {result} (期望: {expected})")

def test_apicore_request_format():
    """测试APICore.ai请求格式构建"""
    print("\n=== 测试APICore.ai请求格式构建 ===")

    # 创建TutuGeminiAPI实例
    api = TutuGeminiAPI()

    # 测试参数
    test_prompt = "生成一张美丽的风景画"
    test_model = "[APICore] gemini-2.5-flash-image"
    test_num_images = 2

    print(f"测试提示词: {test_prompt}")
    print(f"测试模型: {test_model}")
    print(f"图片数量: {test_num_images}")

    # 模拟APICore.ai请求格式构建
    clean_model = clean_model_name(test_model)

    expected_payload = {
        "prompt": test_prompt,
        "model": clean_model,
        "size": "1x1",
        "n": test_num_images
    }

    print(f"期望的APICore.ai请求格式:")
    print(json.dumps(expected_payload, indent=2, ensure_ascii=False))

    # 验证模型名称清理
    assert clean_model == "gemini-2.5-flash-image", f"模型名称清理失败: {clean_model}"
    print("✓ 模型名称清理正确")

def test_apicore_response_processing():
    """测试APICore.ai响应处理逻辑"""
    print("\n=== 测试APICore.ai响应处理逻辑 ===")

    # 创建TutuGeminiAPI实例
    api = TutuGeminiAPI()

    # 模拟不同格式的APICore.ai响应
    test_responses = [
        {
            "name": "标准data数组格式",
            "data": {
                "data": [
                    {"url": "https://example.com/image1.png"},
                    {"url": "https://example.com/image2.png"}
                ]
            }
        },
        {
            "name": "顶级images字段格式",
            "data": {
                "images": [
                    "https://example.com/image1.png",
                    "https://example.com/image2.png"
                ]
            }
        },
        {
            "name": "base64格式",
            "data": {
                "data": [
                    {"url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="}
                ]
            }
        },
        {
            "name": "错误格式",
            "data": {
                "error": "API key invalid"
            }
        }
    ]

    for test_case in test_responses:
        print(f"\n测试 {test_case['name']}:")

        # 创建模拟response对象
        class MockResponse:
            def __init__(self, data):
                self._data = data

            def json(self):
                return self._data

            @property
            def text(self):
                return json.dumps(self._data)

        mock_response = MockResponse(test_case['data'])

        try:
            result = api.process_apicore_response(mock_response)
            print(f"  处理结果: {result[:100]}...")

            # 检查是否包含图片URL
            if 'http' in result or 'data:image/' in result:
                print("  ✓ 成功提取图片URL")
            else:
                print("  ! 未找到图片URL（可能是错误响应）")

        except Exception as e:
            print(f"  ✗ 处理失败: {e}")

def test_provider_validation():
    """测试API提供商验证逻辑"""
    print("\n=== 测试API提供商验证逻辑 ===")

    api = TutuGeminiAPI()

    test_cases = [
        ("APICore.ai", "[APICore] gemini-2.5-flash-image", True),
        ("APICore.ai", "[Comfly] gemini-2.5-flash-image-preview", False),
        ("APICore.ai", "[OpenRouter] google/gemini-2.5-flash-image-preview", False),
        ("ai.comfly.chat", "[Comfly] gemini-2.5-flash-image-preview", True),
        ("OpenRouter", "[OpenRouter] google/gemini-2.5-flash-image-preview", True)
    ]

    for provider, model, expected_valid in test_cases:
        result = api._parse_and_validate_model(model, provider)
        is_valid = result is not None
        status = "✓" if is_valid == expected_valid else "✗"
        print(f"{status} {provider} + {model} -> {'有效' if is_valid else '无效'} (期望: {'有效' if expected_valid else '无效'})")

if __name__ == "__main__":
    print("APICore.ai 集成测试开始...\n")

    try:
        test_clean_model_name()
        test_apicore_request_format()
        test_apicore_response_processing()
        test_provider_validation()

        print("\n🎉 所有测试完成！")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()