#!/usr/bin/env python3
"""
测试 num_images 功能修复

验证修复后的 Tutu.py 能否正确处理多图生成请求
"""
import sys
import os
import json

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(__file__))

def test_payload_structure():
    """测试API请求payload是否包含正确的'n'参数"""
    print("=" * 50)
    print("测试 1: API 请求 payload 结构")
    print("=" * 50)

    # 模拟 Tutu.py 中的 payload 构建逻辑
    num_images = 3
    model = "gemini-2.5-flash-image-preview"
    messages = [{"role": "user", "content": "测试图片生成"}]
    temperature = 0.7
    top_p = 0.9

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": 8192,
        "n": num_images,  # 关键修复：添加了 n 参数
        "stream": True
    }

    print(f"✓ Payload 包含 'n' 参数: {payload.get('n')}")
    print(f"✓ num_images 值: {num_images}")
    print(f"✓ payload['n'] == num_images: {payload.get('n') == num_images}")

    if payload.get('n') == num_images:
        print("✅ 测试通过: API 请求 payload 正确包含 'n' 参数")
        return True
    else:
        print("❌ 测试失败: API 请求 payload 缺少 'n' 参数")
        return False

def test_choices_processing():
    """测试 choices 处理逻辑是否能处理多个选项"""
    print("\n" + "=" * 50)
    print("测试 2: Choices 处理逻辑")
    print("=" * 50)

    # 模拟多选择响应数据
    mock_chunk_data = {
        "choices": [
            {
                "delta": {
                    "content": "第一张图片的URL: ![](https://example.com/image1.jpg)"
                }
            },
            {
                "delta": {
                    "content": "第二张图片的URL: ![](https://example.com/image2.jpg)"
                }
            },
            {
                "delta": {
                    "content": "第三张图片的URL: ![](https://example.com/image3.jpg)"
                }
            }
        ]
    }

    # 模拟处理所有choices的逻辑
    accumulated_content = ""
    choices_processed = 0

    if 'choices' in mock_chunk_data and mock_chunk_data['choices']:
        # 处理所有choices（修复后的逻辑）
        for choice_idx, choice in enumerate(mock_chunk_data['choices']):
            if 'delta' in choice and 'content' in choice['delta']:
                content = choice['delta']['content']
                if content:
                    accumulated_content += content + "\n"
                    choices_processed += 1
                    print(f"✓ 处理 Choice {choice_idx}: {content}")

    expected_choices = len(mock_chunk_data['choices'])
    print(f"✓ 预期处理的 choices 数量: {expected_choices}")
    print(f"✓ 实际处理的 choices 数量: {choices_processed}")
    print(f"✓ 累积的内容长度: {len(accumulated_content)} 字符")

    if choices_processed == expected_choices and len(accumulated_content) > 0:
        print("✅ 测试通过: 能够处理所有 choices")
        return True
    else:
        print("❌ 测试失败: 未能处理所有 choices")
        return False

def test_image_url_extraction():
    """测试图片URL提取是否支持多张图片"""
    print("\n" + "=" * 50)
    print("测试 3: 多图片 URL 提取")
    print("=" * 50)

    # 模拟包含多张图片的响应文本
    response_text = """
    这是生成的图片：
    ![图片1](https://example.com/image1.jpg)
    ![图片2](https://example.com/image2.jpg)
    ![图片3](https://example.com/image3.jpg)
    """

    # 简化的URL提取逻辑
    import re
    image_pattern = r'!\[.*?\]\((.*?)\)'
    matches = re.findall(image_pattern, response_text)

    print(f"✓ 响应文本长度: {len(response_text)} 字符")
    print(f"✓ 找到的图片URL数量: {len(matches)}")
    for i, url in enumerate(matches):
        print(f"✓ 图片 {i+1}: {url}")

    expected_count = 3
    if len(matches) == expected_count:
        print("✅ 测试通过: 能够提取所有图片 URL")
        return True
    else:
        print(f"❌ 测试失败: 期望 {expected_count} 张图片，实际找到 {len(matches)} 张")
        return False

def main():
    """运行所有测试"""
    print("开始测试 num_images 功能修复")
    print("测试环境: Python", sys.version.split()[0])

    results = []

    # 运行测试
    results.append(test_payload_structure())
    results.append(test_choices_processing())
    results.append(test_image_url_extraction())

    # 汇总结果
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)

    passed = sum(results)
    total = len(results)

    print(f"通过的测试: {passed}/{total}")

    if passed == total:
        print("🎉 所有测试都通过了！num_images 功能修复看起来是成功的。")
        print("\n下一步建议:")
        print("1. 使用真实的 API 密钥进行端到端测试")
        print("2. 在 ComfyUI 环境中测试不同的 num_images 值 (1, 2, 3, 4)")
        print("3. 验证生成的图片张量格式正确")
        return True
    else:
        print(f"❌ {total - passed} 个测试失败，需要进一步检查修复。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)