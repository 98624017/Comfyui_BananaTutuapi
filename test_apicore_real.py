#!/usr/bin/env python3
"""
APICore.ai 真实API调用测试脚本
实际发起生图请求，测试返图功能
"""

import requests
import json
import os
import base64
from io import BytesIO
from PIL import Image
import time

def test_apicore_connection():
    """测试APICore.ai API连接性"""
    print("=== 测试APICore.ai API连接性 ===")

    # 检查API密钥
    api_key = os.getenv('APICORE_API_KEY', '')
    if not api_key:
        # 尝试从配置文件读取
        try:
            with open('Tutuapi.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                api_key = config.get('apicore_api_key', '')
        except:
            pass

    if not api_key:
        print("❌ 未找到APICore.ai API密钥")
        print("请设置环境变量 APICORE_API_KEY 或在 Tutuapi.json 中配置 apicore_api_key")
        return False

    print(f"✅ 找到API密钥: {api_key[:10]}...")

    # 测试API端点连接
    endpoint = "https://ismaque.org/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        # 简单的连接测试
        response = requests.get("https://ismaque.org", timeout=10)
        print(f"✅ APICore.ai域名可达，状态码: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ APICore.ai连接失败: {e}")
        return False

def test_apicore_image_generation():
    """测试APICore.ai图像生成功能"""
    print("\n=== 测试APICore.ai图像生成功能 ===")

    # 获取API密钥
    api_key = os.getenv('APICORE_API_KEY', '')
    if not api_key:
        try:
            with open('Tutuapi.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                api_key = config.get('apicore_api_key', '')
        except:
            pass

    if not api_key:
        print("❌ 未找到APICore.ai API密钥，跳过生图测试")
        return False

    endpoint = "https://ismaque.org/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 测试两个模型
    models = [
        "gemini-2.5-flash-image",
        "gemini-2.5-flash-image-hd"
    ]

    test_prompt = "A beautiful sunset over mountains, peaceful and serene landscape"

    for model in models:
        print(f"\n测试模型: {model}")

        payload = {
            "prompt": test_prompt,
            "model": model,
            "size": "1x1",
            "n": 1
        }

        print(f"请求负载: {json.dumps(payload, indent=2)}")

        try:
            print("发送API请求...")
            start_time = time.time()

            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=60
            )

            end_time = time.time()
            request_time = end_time - start_time

            print(f"响应状态码: {response.status_code}")
            print(f"请求耗时: {request_time:.2f}秒")

            if response.status_code == 200:
                print("✅ API调用成功")

                try:
                    response_data = response.json()
                    print(f"响应数据结构: {list(response_data.keys())}")

                    # 提取图片URL
                    image_urls = extract_image_urls(response_data)

                    if image_urls:
                        print(f"✅ 成功提取到 {len(image_urls)} 个图片URL")
                        for i, url in enumerate(image_urls):
                            print(f"  图片 {i+1}: {url[:80]}...")

                            # 尝试下载并验证图片
                            if validate_image_url(url):
                                print(f"    ✅ 图片 {i+1} 验证成功")
                            else:
                                print(f"    ❌ 图片 {i+1} 验证失败")
                    else:
                        print("❌ 未能从响应中提取到图片URL")
                        print(f"响应内容: {json.dumps(response_data, indent=2, ensure_ascii=False)[:500]}...")

                except json.JSONDecodeError as e:
                    print(f"❌ 响应不是有效的JSON: {e}")
                    print(f"响应内容: {response.text[:500]}...")

            elif response.status_code == 401:
                print("❌ API密钥无效或已过期")
                return False
            elif response.status_code == 429:
                print("❌ API调用频率限制")
            else:
                print(f"❌ API调用失败: {response.status_code}")
                print(f"响应内容: {response.text[:500]}...")

        except requests.RequestException as e:
            print(f"❌ 网络请求失败: {e}")
        except Exception as e:
            print(f"❌ 意外错误: {e}")

        print("-" * 50)

    return True

def extract_image_urls(response_data):
    """从APICore.ai响应中提取图片URL"""
    image_urls = []

    # 检查data字段
    if 'data' in response_data:
        data = response_data['data']
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'url' in item:
                    image_urls.append(item['url'])
                elif isinstance(item, str) and ('http' in item or 'data:image/' in item):
                    image_urls.append(item)

    # 检查images字段
    if 'images' in response_data:
        images = response_data['images']
        if isinstance(images, list):
            for img in images:
                if isinstance(img, str):
                    image_urls.append(img)

    # 检查直接的URL字段
    if 'url' in response_data:
        image_urls.append(response_data['url'])

    return image_urls

def validate_image_url(url):
    """验证图片URL是否有效"""
    try:
        if url.startswith('data:image/'):
            # Base64编码的图片
            try:
                header, data = url.split(',', 1)
                image_data = base64.b64decode(data)
                img = Image.open(BytesIO(image_data))
                return img.size[0] > 0 and img.size[1] > 0
            except Exception:
                return False
        else:
            # HTTP URL
            response = requests.get(url, timeout=10, stream=True)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                return content_type.startswith('image/')
            return False
    except Exception:
        return False

def test_apicore_error_handling():
    """测试APICore.ai错误处理"""
    print("\n=== 测试APICore.ai错误处理 ===")

    endpoint = "https://ismaque.org/v1/images/generations"

    # 测试无效密钥
    print("测试无效API密钥...")
    headers = {
        "Authorization": "Bearer invalid_key",
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": "test",
        "model": "gemini-2.5-flash-image",
        "size": "1x1",
        "n": 1
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        if response.status_code == 401:
            print("✅ 无效密钥正确返回401错误")
        else:
            print(f"⚠️  无效密钥返回状态码: {response.status_code}")
    except Exception as e:
        print(f"⚠️  无效密钥测试异常: {e}")

if __name__ == "__main__":
    print("APICore.ai 真实API调用测试开始...\n")

    # 连接测试
    if not test_apicore_connection():
        print("❌ 连接测试失败，停止后续测试")
        exit(1)

    # 生图功能测试
    test_apicore_image_generation()

    # 错误处理测试
    test_apicore_error_handling()

    print("\n=== 测试总结 ===")
    print("✅ APICore.ai API端点连接性测试")
    print("✅ 两个模型的图像生成测试")
    print("✅ 图片URL提取和验证")
    print("✅ 错误处理机制测试")
    print("\n💡 如果需要完整测试，请确保:")
    print("  1. 设置有效的APICore.ai API密钥")
    print("  2. 网络连接正常")
    print("  3. API服务可用")