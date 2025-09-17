import os
import io
import math
import random
import torch
import requests
import time
import numpy as np
from PIL import Image
from io import BytesIO
import json
import comfy.utils
import re
import aiohttp
import asyncio
import base64
import uuid
import folder_paths
import mimetypes
import cv2
import shutil
from .utils import pil2tensor, tensor2pil
from comfy.utils import common_upscale
from comfy.comfy_types import IO


def get_config():
    try:
        config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'Tutuapi.json')
        with open(config_path, 'r') as f:  
            config = json.load(f)
        return config
    except:
        return {}

def save_config(config):
    config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'Tutuapi.json')
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)

def clean_model_name(model_with_tag):
    """清理模型名称，移除提供商标签"""
    if not model_with_tag.startswith('['):
        return model_with_tag

    try:
        tag_end = model_with_tag.find(']')
        if tag_end == -1:
            return model_with_tag
        return model_with_tag[tag_end + 2:]  # 去掉"] "
    except:
        return model_with_tag


# ===== 预设管理系统 =====
def get_presets_file():
    """获取预设文件路径"""
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), 'presets.json')

def load_presets():
    """加载预设配置"""
    try:
        with open(get_presets_file(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # 如果文件不存在，创建默认结构
        default_presets = {
            "gemini": []
        }
        save_all_presets(default_presets)
        return default_presets
    except json.JSONDecodeError:
        print("[Tutu] 预设文件格式错误，使用默认配置")
        return {"gemini": []}

def save_all_presets(presets):
    """保存所有预设到文件"""
    with open(get_presets_file(), 'w', encoding='utf-8') as f:
        json.dump(presets, f, indent=2, ensure_ascii=False)

def save_preset(category, name, config, description=""):
    """保存单个预设"""
    if not name.strip():
        raise ValueError("预设名称不能为空")
        
    presets = load_presets()
    if category not in presets:
        presets[category] = []
    
    # 检查是否已存在同名预设
    existing_names = [p["name"] for p in presets[category]]
    if name in existing_names:
        # 如果存在同名，添加时间戳后缀
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        name = f"{name}_{timestamp}"
    
    preset = {
        "id": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "config": config,
        "created_time": time.time(),
        "created_date": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    presets[category].append(preset)
    save_all_presets(presets)
    return preset["id"]

def delete_preset(category, preset_id):
    """删除指定预设"""
    presets = load_presets()
    if category not in presets:
        return False
    
    original_count = len(presets[category])
    presets[category] = [p for p in presets[category] if p["id"] != preset_id]
    
    if len(presets[category]) < original_count:
        save_all_presets(presets)
        return True
    return False

def get_preset_by_name(category, name):
    """根据名称获取预设"""
    presets = load_presets()
    if category not in presets:
        return None
    
    for preset in presets[category]:
        if preset["name"] == name:
            return preset
    return None

def get_preset_by_id(category, preset_id):
    """根据ID获取预设"""
    presets = load_presets()
    if category not in presets:
        return None
    
    for preset in presets[category]:
        if preset["id"] == preset_id:
            return preset
    return None

def get_preset_names(category):
    """获取指定分类的所有预设名称"""
    presets = load_presets()
    if category not in presets:
        return []
    return [p["name"] for p in presets[category]]

def update_preset(category, preset_id, new_config=None, new_name=None, new_description=None):
    """更新现有预设"""
    presets = load_presets()
    if category not in presets:
        return False
    
    for preset in presets[category]:
        if preset["id"] == preset_id:
            if new_config is not None:
                preset["config"] = new_config
            if new_name is not None:
                preset["name"] = new_name
            if new_description is not None:
                preset["description"] = new_description
            preset["updated_time"] = time.time()
            preset["updated_date"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            save_all_presets(presets)
            return True
    return False

# ===== 预设管理系统结束 =====

# ===== 基础视频适配器类 =====
class ComflyVideoAdapter:
    def __init__(self, url):
        self.url = url if url else ""
        
    def __str__(self):
        return self.url


############################# Gemini ###########################

class TutuGeminiAPI:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"forceInput": True}),
                "api_provider": (
                    [
                        "ai.comfly.chat",
                        "OpenRouter",
                        "APICore.ai"
                    ],
                    {"default": "ai.comfly.chat"}
                ),
                "model": (
                    [
                        "[Comfly] gemini-2.5-flash-image-preview",
                        "[Comfly] gemini-2.0-flash-preview-image-generation",
                        "[OpenRouter] google/gemini-2.5-flash-image-preview",
                        "[APICore] gemini-2.5-flash-image",
                        "[APICore] gemini-2.5-flash-image-hd"
                    ],
                    {"default": "[Comfly] gemini-2.5-flash-image-preview"}
                ),

                "num_images": ("INT", {"default": 1, "min": 1, "max": 4, "step": 1}),
                "temperature": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.01}),
                "top_p": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01}),
                "timeout": ("INT", {"default": 120, "min": 10, "max": 600, "step": 10}),
            },
            "optional": {
                "comfly_api_key": ("STRING", {
                    "default": "", 
                    "placeholder": "ai.comfly.chat API Key (optional, leave blank to use config)"
                }),
                "openrouter_api_key": ("STRING", {
                    "default": "",
                    "placeholder": "OpenRouter API Key (optional, leave blank to use config)"
                }),
                "apicore_api_key": ("STRING", {
                    "default": "",
                    "placeholder": "APICore.ai API Key (optional, leave blank to use config)"
                }),
                "input_image_1": ("IMAGE",),  
                "input_image_2": ("IMAGE",),
                "input_image_3": ("IMAGE",),
                "input_image_4": ("IMAGE",),
                "input_image_5": ("IMAGE",),
            }
        }
    
    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("generated_images", "response", "image_url")
    FUNCTION = "process"
    CATEGORY = "Tutu"

    def __init__(self):
        config = get_config()
        self.comfly_api_key = config.get('comfly_api_key', config.get('api_key', ''))  # 向后兼容
        self.openrouter_api_key = config.get('openrouter_api_key', '')
        self.apicore_api_key = config.get('apicore_api_key', '')
        self.timeout = 120
    
    def _truncate_base64_in_response(self, text, max_base64_len=100):
        """截断响应文本中的base64内容以避免刷屏"""
        import re
        
        def replace_base64(match):
            full_base64 = match.group(0)
            prefix = full_base64.split(',')[0] + ','  # 保留 data:image/xxx;base64, 部分
            base64_data = full_base64[len(prefix):]
            
            if len(base64_data) > max_base64_len:
                truncated = base64_data[:max_base64_len] + f"... [truncated {len(base64_data) - max_base64_len} chars]"
                return prefix + truncated
            return full_base64
        
        # 匹配 data:image/xxx;base64,xxxxxx 格式
        pattern = r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+'
        result = re.sub(pattern, replace_base64, text)
        
        return result
    
    def _sanitize_content_for_debug(self, content):
        """为调试输出清理内容（移除敏感数据）"""
        if isinstance(content, str):
            # 如果内容包含base64图片，截断显示
            if 'data:image/' in content:
                parts = content.split('data:image/')
                if len(parts) > 1:
                    # 只显示第一部分文本 + base64开头
                    base64_start = parts[1][:50] + "..." if len(parts[1]) > 50 else parts[1]
                    return parts[0] + f"data:image/{base64_start}"
            return content[:200] + "..." if len(content) > 200 else content
        elif isinstance(content, list):
            return [self._sanitize_content_for_debug(item) for item in content]
        elif isinstance(content, dict):
            return {k: self._sanitize_content_for_debug(v) for k, v in content.items()}
        else:
            return content

    def get_current_api_key(self, api_provider):
        """根据API提供商获取对应的API key"""
        if api_provider == "OpenRouter":
            return self.openrouter_api_key
        elif api_provider == "APICore.ai":
            return self.apicore_api_key
        else:
            return self.comfly_api_key
            
    def display_preset_list(self):
        """显示所有预设的详细信息"""
        print(f"\n[Tutu] 📋 ======== 预设列表 ========")
        
        try:
            presets = load_presets()
            gemini_presets = presets.get("gemini", [])
            
            if not gemini_presets:
                print(f"[Tutu] ⚪ 当前没有保存的预设")
                print(f"[Tutu] 💡 提示：在 'save_as_preset' 中输入名称来保存预设")
                return
            
            print(f"[Tutu] 📊 总共 {len(gemini_presets)} 个预设:")
            print(f"[Tutu] " + "-" * 50)
            
            for i, preset in enumerate(gemini_presets, 1):
                name = preset.get("name", "未知名称")
                description = preset.get("description", "无描述")
                created_date = preset.get("created_date", "未知时间")
                
                print(f"[Tutu] {i}. 名称: {name}")
                print(f"[Tutu]    描述: {description}")
                print(f"[Tutu]    创建时间: {created_date}")
                
                # 显示提示词模板（如果有）
                config = preset.get("config", {})
                if "prompt_template" in config:
                    template = config["prompt_template"]
                    # 截断长模板以便显示
                    if len(template) > 100:
                        template_preview = template[:100] + "..."
                    else:
                        template_preview = template
                    print(f"[Tutu]    模板: {template_preview}")
                
                print(f"[Tutu] " + "-" * 30)
                
        except Exception as e:
            print(f"[Tutu] ❌ 获取预设列表时出错: {str(e)}")
        
        print(f"[Tutu] 📋 ======== 预设列表结束 ========\n")

    def get_headers(self, api_provider="ai.comfly.chat"):
        current_api_key = self.get_current_api_key(api_provider)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {current_api_key}"
        }

        # OpenRouter需要额外的headers
        if api_provider == "OpenRouter":
            headers.update({
                "HTTP-Referer": "https://comfyui.com",
                "X-Title": "ComfyUI Tutu Nano Banana"
            })
        # APICore.ai使用标准Bearer认证
        elif api_provider == "APICore.ai":
            # APICore.ai使用标准headers，无需额外配置
            pass

        print(f"[Tutu DEBUG] Generated headers for {api_provider}: {headers}")
        return headers

    def image_to_base64(self, image):
        """将图片转换为base64，保持原始质量"""
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def upload_image(self, image, max_retries=3):
        """上传图像到临时托管服务，支持多个备选服务"""
        
        # 准备图像数据
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        buffered.seek(0)
        
        # 备选上传服务列表（按优先级排序，使用最简单可靠的服务）
        upload_services = [
            {
                "name": "0x0.st",
                "url": "https://0x0.st",
                "method": "POST",
                "files_key": "file", 
                "response_key": "url"
            },
            {
                "name": "tmpfiles.org", 
                "url": "https://tmpfiles.org/api/v1/upload",
                "method": "POST", 
                "files_key": "file",
                "response_key": "data.url"
            },
            {
                "name": "uguu.se",
                "url": "https://uguu.se/upload",
                "method": "POST",
                "files_key": "files[]",
                "response_key": "url"
            },
            {
                "name": "x0.at",
                "url": "https://x0.at",
                "method": "POST",
                "files_key": "file",
                "response_key": "url"
            }
        ]
        
        for service in upload_services:
            for attempt in range(max_retries):
                try:
                    print(f"[Tutu DEBUG] 尝试上传到 {service['name']} (尝试 {attempt + 1}/{max_retries})...")
                    
                    # 重置buffer位置
                    buffered.seek(0)
                    
                    # 准备文件上传
                    files = {service['files_key']: ('image.png', buffered.getvalue(), 'image/png')}
                    
                    # 准备额外数据（如果需要）
                    data = service.get('extra_data', {})
                    
                    # 发送上传请求
                    response = requests.post(
                        service['url'], 
                        files=files,
                        data=data,
                        timeout=30,
                        headers={'User-Agent': 'ComfyUI-Tutu/1.0'}
                    )
                    
                    if response.status_code == 200:
                        # 根据服务类型提取URL
                        if service['name'] in ["0x0.st", "x0.at"]:
                            # 这些服务返回纯文本URL
                            image_url = response.text.strip()
                        elif service['name'] == "uguu.se":
                            # uguu.se 返回JSON数组
                            try:
                                result = response.json()
                                if isinstance(result, list) and len(result) > 0:
                                    image_url = result[0].get('url', '')
                                else:
                                    image_url = result.get('url', '')
                            except:
                                image_url = response.text.strip()
                        else:
                            # 其他服务返回JSON
                            try:
                                result = response.json()
                                if service['name'] == "tmpfiles.org" and 'data' in result:
                                    image_url = result['data'].get('url', '')
                                else:
                                    # 通用解析
                                    keys = service['response_key'].split('.')
                                    image_url = result
                                    for key in keys:
                                        if isinstance(image_url, dict):
                                            image_url = image_url.get(key, '')
                                        else:
                                            image_url = ''
                                            break
                                        if not image_url:
                                            break
                            except Exception as e:
                                print(f"[Tutu DEBUG] JSON解析失败: {str(e)}")
                                # JSON解析失败，尝试纯文本
                                image_url = response.text.strip()
                        
                        if image_url and image_url.startswith('http'):
                            print(f"[Tutu DEBUG] 成功上传到 {service['name']}: {image_url}")
                            return image_url
                        else:
                            print(f"[Tutu DEBUG] {service['name']} 响应格式异常: {result}")
                    else:
                        print(f"[Tutu DEBUG] {service['name']} 上传失败，状态码: {response.status_code}")
                        
                except Exception as e:
                    print(f"[Tutu DEBUG] {service['name']} 上传出错 (尝试 {attempt + 1}): {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(1)  # 等待1秒后重试
                    continue
                    
        # 所有服务都失败，返回None
        print(f"[Tutu DEBUG] 所有上传服务都失败，将使用压缩的base64格式")
        return None

    def process_apicore_response(self, response):
        """处理APICore.ai的标准JSON响应"""
        try:
            print(f"[Tutu DEBUG] 开始处理APICore.ai标准JSON响应...")

            # 解析JSON响应
            response_data = response.json()
            print(f"[Tutu DEBUG] APICore.ai响应数据结构: {list(response_data.keys())}")

            # 提取图片URL - APICore.ai可能使用不同的响应格式
            image_content = ""

            # 常见的APICore.ai响应格式检查
            if 'data' in response_data:
                data = response_data['data']
                print(f"[Tutu DEBUG] 找到data字段，类型: {type(data)}")

                if isinstance(data, list):
                    # 如果data是数组，遍历每个元素
                    for i, item in enumerate(data):
                        print(f"[Tutu DEBUG] 处理data[{i}]: {list(item.keys()) if isinstance(item, dict) else type(item)}")

                        if isinstance(item, dict):
                            # 查找图片URL字段
                            for url_field in ['url', 'image_url', 'generated_image', 'data']:
                                if url_field in item:
                                    url = item[url_field]
                                    print(f"[Tutu DEBUG] 🎯 在data[{i}].{url_field}找到图片URL: {url[:50] if isinstance(url, str) else type(url)}...")
                                    if isinstance(url, str):
                                        image_content += url + " "
                        elif isinstance(item, str) and ('http' in item or 'data:image/' in item):
                            # 如果数组元素直接是URL字符串
                            print(f"[Tutu DEBUG] 🎯 data[{i}]直接是URL: {item[:50]}...")
                            image_content += item + " "

                elif isinstance(data, dict):
                    # 如果data是字典，直接查找URL字段
                    print(f"[Tutu DEBUG] data是字典: {list(data.keys())}")
                    for url_field in ['url', 'image_url', 'generated_image', 'data']:
                        if url_field in data:
                            url = data[url_field]
                            print(f"[Tutu DEBUG] 🎯 在data.{url_field}找到图片URL: {url[:50] if isinstance(url, str) else type(url)}...")
                            if isinstance(url, str):
                                image_content += url + " "

            # 检查顶级字段中的图片URL
            for url_field in ['url', 'image_url', 'generated_image', 'images', 'choices']:
                if url_field in response_data:
                    value = response_data[url_field]
                    print(f"[Tutu DEBUG] 检查顶级字段{url_field}: {type(value)}")

                    if isinstance(value, str) and ('http' in value or 'data:image/' in value):
                        print(f"[Tutu DEBUG] 🎯 在顶级{url_field}找到图片URL: {value[:50]}...")
                        image_content += value + " "
                    elif isinstance(value, list):
                        for i, item in enumerate(value):
                            if isinstance(item, str) and ('http' in item or 'data:image/' in item):
                                print(f"[Tutu DEBUG] 🎯 在{url_field}[{i}]找到图片URL: {item[:50]}...")
                                image_content += item + " "
                            elif isinstance(item, dict):
                                # 查找嵌套的URL字段
                                for nested_field in ['url', 'image_url', 'generated_image']:
                                    if nested_field in item and isinstance(item[nested_field], str):
                                        url = item[nested_field]
                                        print(f"[Tutu DEBUG] 🎯 在{url_field}[{i}].{nested_field}找到图片URL: {url[:50]}...")
                                        image_content += url + " "

            # 如果仍然没有找到图片，尝试在整个响应中搜索
            if not image_content.strip():
                print(f"[Tutu DEBUG] 未在标准字段找到图片，搜索整个响应...")
                response_str = json.dumps(response_data)

                # 使用正则表达式查找可能的图片URL
                import re
                patterns = [
                    r'data:image/[^",\s]+',  # base64 图片
                    r'https?://[^",\s]+\.(?:png|jpg|jpeg|gif|webp)',  # 图片URL
                    r'https?://[^",\s]+/[^",\s]*[iI]mage[^",\s]*',  # 包含image的URL
                ]

                for pattern in patterns:
                    urls = re.findall(pattern, response_str)
                    if urls:
                        print(f"[Tutu DEBUG] 🎯 用正则表达式{pattern}找到: {len(urls)}个URL")
                        for url in urls:
                            print(f"[Tutu DEBUG] 🎯 提取URL: {url[:50]}...")
                            image_content += url + " "
                        break

            # 如果找到了图片内容，返回
            if image_content.strip():
                print(f"[Tutu DEBUG] APICore.ai响应处理成功，找到{len(image_content.split())}个图片URL")
                return image_content.strip()
            else:
                # 如果没有找到图片，返回原始响应用于调试
                print(f"[Tutu DEBUG] APICore.ai响应中未找到图片URL，返回原始响应")
                print(f"[Tutu DEBUG] 完整响应结构: {json.dumps(response_data, indent=2)[:500]}...")
                return json.dumps(response_data, ensure_ascii=False)

        except json.JSONDecodeError as e:
            print(f"[Tutu ERROR] APICore.ai响应JSON解析失败: {e}")
            # 尝试直接返回文本内容
            response_text = response.text
            print(f"[Tutu DEBUG] 尝试处理纯文本响应: {response_text[:200]}...")
            return response_text
        except Exception as e:
            print(f"[Tutu ERROR] APICore.ai响应处理出错: {e}")
            return f"APICore.ai响应处理错误: {str(e)}"

    def process_sse_stream(self, response, api_provider="ai.comfly.chat"):
        """Process Server-Sent Events (SSE) stream from the API with provider-specific handling"""
        accumulated_content = ""
        chunk_count = 0
        raw_response_parts = []
        current_json_buffer = ""
        
        print(f"[Tutu DEBUG] 开始处理SSE流 (API: {api_provider})...")
        
        # Different APIs might have different response structures
        is_comfly = api_provider == "ai.comfly.chat"
        is_openrouter = api_provider == "OpenRouter"
        is_apicore = api_provider == "APICore.ai"
        
        try:
            for line in response.iter_lines(decode_unicode=True, chunk_size=None):
                if line:
                    print(f"[Tutu DEBUG] SSE原始行: {repr(line[:100])}")
                    
                if line and line.startswith('data: '):
                    chunk_count += 1
                    data_content = line[6:]  # Remove 'data: ' prefix
                    
                    print(f"[Tutu DEBUG] 处理第{chunk_count}个数据块...")
                    
                    if data_content.strip() == '[DONE]':
                        print(f"[Tutu DEBUG] 收到结束信号[DONE]")
                        break
                    
                    # 累积可能被分割的JSON数据
                    current_json_buffer += data_content
                    
                    try:
                        # 尝试解析累积的JSON
                        chunk_data = json.loads(current_json_buffer)
                        print(f"[Tutu DEBUG] JSON解析成功: {list(chunk_data.keys())}")
                        
                        # 清空缓冲区，因为JSON解析成功了
                        current_json_buffer = ""
                        
                        # Extract content from the chunk
                        if 'choices' in chunk_data and chunk_data['choices']:
                            # 处理所有choices，支持多图生成
                            for choice_idx, choice in enumerate(chunk_data['choices']):
                                print(f"[Tutu DEBUG] Choice {choice_idx} 结构: {choice}")

                                # 检查delta中的所有字段
                                if 'delta' in choice:
                                    delta = choice['delta']
                                    print(f"[Tutu DEBUG] Choice {choice_idx} Delta所有字段: {list(delta.keys())}")

                                    # 检查content字段
                                    if 'content' in delta:
                                        content = delta['content']
                                        print(f"[Tutu DEBUG] Choice {choice_idx} Delta.content: {repr(content[:200]) if content else 'None/Empty'}")
                                        if content:
                                            # 修复编码问题
                                            try:
                                                if isinstance(content, str):
                                                    content = content.encode('latin1').decode('utf-8')
                                            except (UnicodeDecodeError, UnicodeEncodeError):
                                                pass
                                            accumulated_content += content
                                            print(f"[Tutu DEBUG] 添加choice {choice_idx} delta.content: {repr(content[:100])}")

                                    # 检查是否有其他包含图片数据的字段
                                    for key, value in delta.items():
                                        if key != 'content' and isinstance(value, str):
                                            print(f"[Tutu DEBUG] Delta.{key}: {repr(value[:200]) if len(str(value)) > 200 else repr(value)}")
                                            # 检查是否是图片数据
                                            if 'data:image/' in str(value) or 'base64,' in str(value):
                                                print(f"[Tutu DEBUG] 🎯找到图片数据在delta.{key}中!")
                                                accumulated_content += str(value)
                                                print(f"[Tutu DEBUG] 添加图片数据: {len(str(value))}字符")

                                # 检查message中的内容
                                elif 'message' in choice:
                                    message = choice['message']
                                    print(f"[Tutu DEBUG] Choice {choice_idx} Message所有字段: {list(message.keys())}")

                                    if 'content' in message:
                                        content = message['content']
                                        print(f"[Tutu DEBUG] Choice {choice_idx} Message.content: {repr(content[:200]) if content else 'None/Empty'}")
                                        if content:
                                            try:
                                                if isinstance(content, str):
                                                    content = content.encode('latin1').decode('utf-8')
                                            except (UnicodeDecodeError, UnicodeEncodeError):
                                                pass
                                            accumulated_content += content
                                        print(f"[Tutu DEBUG] 添加message.content: {repr(content[:100])}")
                                
                                # 检查message中的其他字段
                                for key, value in message.items():
                                    if key != 'content' and isinstance(value, str):
                                        print(f"[Tutu DEBUG] Message.{key}: {repr(value[:200]) if len(str(value)) > 200 else repr(value)}")
                                        # 检查是否是图片数据
                                        if 'data:image/' in str(value) or 'base64,' in str(value):
                                            print(f"[Tutu DEBUG] 🎯找到图片数据在message.{key}中!")
                                            accumulated_content += str(value)
                                            print(f"[Tutu DEBUG] 添加图片数据: {len(str(value))}字符")
                            
                            # 检查choice的其他字段，可能图片数据在别处
                            for key, value in choice.items():
                                if key not in ['delta', 'message', 'index', 'finish_reason', 'native_finish_reason', 'logprobs']:
                                    if isinstance(value, str) and ('data:image/' in value or 'base64,' in value):
                                        print(f"[Tutu DEBUG] 🎯找到图片数据在choice.{key}中!")
                                        accumulated_content += value
                                        print(f"[Tutu DEBUG] 添加图片数据: {len(value)}字符")
                                    elif value:
                                        print(f"[Tutu DEBUG] Choice.{key}: {repr(str(value)[:200])}")
                        
                        # 检查整个chunk中是否有图片数据 - 针对不同API提供商
                        chunk_str = json.dumps(chunk_data)
                        
                        if is_comfly:
                            # comfly可能把图片数据放在不同的位置
                            print(f"[Tutu DEBUG] 🔍 comfly专用检查: 搜索整个响应块")
                            
                            # 检查是否有任何图片相关的字段
                            for key, value in chunk_data.items():
                                if key not in ['id', 'object', 'created', 'model', 'system_fingerprint', 'choices', 'usage']:
                                    if isinstance(value, str) and ('data:image/' in value or 'http' in value):
                                        print(f"[Tutu DEBUG] 🎯 comfly在{key}字段发现可能的图片数据!")
                                        accumulated_content += " " + value
                                    elif value:
                                        print(f"[Tutu DEBUG] comfly额外字段{key}: {repr(str(value)[:100])}")
                            
                            # 检查choices之外的图片数据
                            if 'data:image/' in chunk_str or 'generated_image' in chunk_str or 'image_url' in chunk_str:
                                print(f"[Tutu DEBUG] 🎯 comfly JSON中发现图片相关数据!")
                                print(f"[Tutu DEBUG] 完整chunk (前500字符): {chunk_str[:500]}")
                                
                                # 尝试提取所有可能的图片URL
                                import re
                                patterns = [
                                    r'data:image/[^",\s]+',  # base64 图片
                                    r'https?://[^",\s]+\.(?:png|jpg|jpeg|gif|webp)',  # 图片URL
                                    r'"image_url":\s*"([^"]+)"',  # JSON中的image_url字段
                                    r'"generated_image":\s*"([^"]+)"'  # 生成图片字段
                                ]
                                
                                for pattern in patterns:
                                    urls = re.findall(pattern, chunk_str)
                                    if urls:
                                        print(f"[Tutu DEBUG] 🎯 comfly用模式 {pattern} 找到: {len(urls)}个URL")
                                        for url in urls:
                                            if url.startswith('data:image/'):
                                                print(f"[Tutu DEBUG] 🎯 comfly提取base64图片")
                                            else:
                                                print(f"[Tutu DEBUG] 🎯 comfly提取URL: {url[:50]}...") 
                                            accumulated_content += " " + url
                                            
                        elif is_openrouter:
                            # OpenRouter的原有处理逻辑
                            if 'data:image/' in chunk_str:
                                print(f"[Tutu DEBUG] 🎯 OpenRouter在JSON中发现图片数据!")
                                import re
                                image_urls_in_chunk = re.findall(r'data:image/[^"]+', chunk_str)
                                if image_urls_in_chunk:
                                    for url in image_urls_in_chunk:
                                        if url.startswith('data:image/'):
                                            print(f"[Tutu DEBUG] 🎯 OpenRouter提取base64图片")
                                        else:
                                            print(f"[Tutu DEBUG] 🎯 OpenRouter提取URL: {url[:50]}...")
                                        accumulated_content += " " + url

                        elif is_apicore:
                            # APICore.ai 专用处理逻辑
                            print(f"[Tutu DEBUG] 🔍 APICore.ai专用检查: 搜索图片数据")

                            # 检查是否有任何图片相关的字段
                            for key, value in chunk_data.items():
                                if key not in ['id', 'object', 'created', 'model', 'system_fingerprint', 'choices', 'usage']:
                                    if isinstance(value, str) and ('data:image/' in value or 'http' in value):
                                        print(f"[Tutu DEBUG] 🎯 APICore.ai在{key}字段发现图片数据!")
                                        accumulated_content += " " + value
                                    elif value:
                                        print(f"[Tutu DEBUG] APICore.ai额外字段{key}: {repr(str(value)[:100])}")

                            # 全面搜索APICore.ai中的图片数据
                            if 'data:image/' in chunk_str or 'generated_image' in chunk_str or 'image_url' in chunk_str:
                                print(f"[Tutu DEBUG] 🎯 APICore.ai JSON中发现图片相关数据!")
                                import re
                                patterns = [
                                    r'data:image/[^",\s]+',  # base64 图片
                                    r'https?://[^",\s]+\.(?:png|jpg|jpeg|gif|webp)',  # 图片URL
                                    r'"image_url":\s*"([^"]+)"',  # JSON中的image_url字段
                                    r'"generated_image":\s*"([^"]+)"'  # 生成图片字段
                                ]

                                for pattern in patterns:
                                    urls = re.findall(pattern, chunk_str)
                                    if urls:
                                        print(f"[Tutu DEBUG] 🎯 APICore.ai用模式找到: {len(urls)}个URL")
                                        for url in urls:
                                            if url.startswith('data:image/'):
                                                print(f"[Tutu DEBUG] 🎯 APICore.ai提取base64图片")
                                            else:
                                                print(f"[Tutu DEBUG] 🎯 APICore.ai提取URL: {url[:50]}...")
                                            accumulated_content += " " + url
                        
                        # 保存完整的响应数据用于调试
                        raw_response_parts.append(chunk_data)
                                
                    except json.JSONDecodeError as e:
                        print(f"[Tutu DEBUG] JSON解析失败: {e}")
                        print(f"[Tutu DEBUG] 当前缓冲区内容: {repr(current_json_buffer[:200])}")
                        # 不要清空缓冲区，可能还有更多数据到来
                        
                elif line:
                    # 处理不以"data: "开头的行，它们可能是JSON的续行
                    print(f"[Tutu DEBUG] 非data行: {repr(line[:100])}")
                    if current_json_buffer:
                        # 如果有未完成的JSON，尝试添加这行
                        # 先尝试修复编码问题
                        try:
                            # 如果line包含二进制数据，尝试解码
                            if isinstance(line, str) and '\\x' in repr(line):
                                # 尝试修复UTF-8编码问题
                                fixed_line = line.encode('latin1').decode('utf-8')
                                print(f"[Tutu DEBUG] 编码修复后: {repr(fixed_line)}")
                            else:
                                fixed_line = line
                        except (UnicodeDecodeError, UnicodeEncodeError):
                            fixed_line = line
                        
                        current_json_buffer += fixed_line
                        try:
                            chunk_data = json.loads(current_json_buffer)
                            print(f"[Tutu DEBUG] 续行JSON解析成功: {list(chunk_data.keys())}")
                            
                            # 清空缓冲区
                            current_json_buffer = ""
                            
                            # 处理这个合并后的chunk_data（重要！）
                            if 'choices' in chunk_data and chunk_data['choices']:
                                # 处理所有choices，支持多图生成
                                for choice_idx, choice in enumerate(chunk_data['choices']):
                                    print(f"[Tutu DEBUG] 续行Choice {choice_idx} 结构: {choice}")

                                    # 检查delta中的所有字段
                                    if 'delta' in choice:
                                        delta = choice['delta']
                                        print(f"[Tutu DEBUG] 续行Choice {choice_idx} Delta所有字段: {list(delta.keys())}")

                                        # 检查content字段
                                        if 'content' in delta:
                                            content = delta['content']
                                            print(f"[Tutu DEBUG] 续行Choice {choice_idx} Delta.content: {repr(content[:200]) if content else 'None/Empty'}")
                                            if content:
                                                try:
                                                    if isinstance(content, str):
                                                        content = content.encode('latin1').decode('utf-8')
                                                except (UnicodeDecodeError, UnicodeEncodeError):
                                                    pass
                                                accumulated_content += content
                                                print(f"[Tutu DEBUG] 从续行添加choice {choice_idx} delta.content: {repr(content[:100])}")

                                        # 检查其他字段中的图片数据
                                        for key, value in delta.items():
                                            if key != 'content' and isinstance(value, str):
                                                print(f"[Tutu DEBUG] 续行Delta.{key}: {repr(value[:200]) if len(str(value)) > 200 else repr(value)}")
                                                if 'data:image/' in str(value) or 'base64,' in str(value):
                                                    print(f"[Tutu DEBUG] 🎯续行中找到图片数据在delta.{key}!")
                                                    accumulated_content += str(value)
                                                print(f"[Tutu DEBUG] 从续行添加图片数据: {len(str(value))}字符")
                                        
                                # 检查message中的内容
                                elif 'message' in choice:
                                    message = choice['message']
                                    print(f"[Tutu DEBUG] 续行Message所有字段: {list(message.keys())}")
                                    
                                    if 'content' in message:
                                        content = message['content']
                                        print(f"[Tutu DEBUG] 续行Message.content: {repr(content[:200]) if content else 'None/Empty'}")
                                        if content:
                                            try:
                                                if isinstance(content, str):
                                                    content = content.encode('latin1').decode('utf-8')
                                            except (UnicodeDecodeError, UnicodeEncodeError):
                                                pass
                                            accumulated_content += content
                                            print(f"[Tutu DEBUG] 从续行添加message.content: {repr(content[:100])}")
                                    
                                    # 检查message中的其他字段
                                    for key, value in message.items():
                                        if key != 'content' and isinstance(value, str):
                                            if 'data:image/' in str(value) or 'base64,' in str(value):
                                                print(f"[Tutu DEBUG] 🎯续行中找到图片数据在message.{key}!")
                                                accumulated_content += str(value)
                                                print(f"[Tutu DEBUG] 从续行添加图片数据: {len(str(value))}字符")
                                
                                # 检查choice中的其他字段
                                for key, value in choice.items():
                                    if key not in ['delta', 'message', 'index', 'finish_reason', 'native_finish_reason', 'logprobs']:
                                        if isinstance(value, str) and ('data:image/' in value or 'base64,' in value):
                                            print(f"[Tutu DEBUG] 🎯续行中找到图片数据在choice.{key}!")
                                            accumulated_content += value
                                            print(f"[Tutu DEBUG] 从续行添加图片数据: {len(value)}字符")
                            
                            # 续行中的图片数据检查 - 针对不同API提供商
                            chunk_str = json.dumps(chunk_data)
                            
                            if is_comfly:
                                # comfly续行处理
                                print(f"[Tutu DEBUG] 🔍 comfly续行检查: 搜索图片数据")
                                
                                # 检查顶级字段中的图片数据
                                for key, value in chunk_data.items():
                                    if key not in ['id', 'object', 'created', 'model', 'system_fingerprint', 'choices', 'usage']:
                                        if isinstance(value, str) and ('data:image/' in value or 'http' in value):
                                            print(f"[Tutu DEBUG] 🎯 comfly续行在{key}发现图片数据!")
                                            accumulated_content += " " + value
                                
                                # 全面搜索续行中的图片数据
                                if 'data:image/' in chunk_str or 'generated_image' in chunk_str or 'image_url' in chunk_str:
                                    print(f"[Tutu DEBUG] 🎯 comfly续行JSON中发现图片相关数据!")
                                    import re
                                    patterns = [
                                        r'data:image/[^",\s]+',
                                        r'https?://[^",\s]+\.(?:png|jpg|jpeg|gif|webp)',
                                        r'"image_url":\s*"([^"]+)"',
                                        r'"generated_image":\s*"([^"]+)"'
                                    ]
                                    
                                    for pattern in patterns:
                                        urls = re.findall(pattern, chunk_str)
                                        if urls:
                                            print(f"[Tutu DEBUG] 🎯 comfly续行用模式找到: {len(urls)}个URL")
                                            for url in urls:
                                                if url.startswith('data:image/'):
                                                    print(f"[Tutu DEBUG] 🎯 comfly续行提取base64图片")
                                                else:
                                                    print(f"[Tutu DEBUG] 🎯 comfly续行提取URL: {url[:50]}...")
                                                accumulated_content += " " + url
                                                
                            elif is_openrouter:
                                # OpenRouter续行处理
                                if 'data:image/' in chunk_str:
                                    print(f"[Tutu DEBUG] 🎯 OpenRouter续行中发现图片数据!")
                                    import re
                                    image_urls_in_chunk = re.findall(r'data:image/[^"]+', chunk_str)
                                    if image_urls_in_chunk:
                                        for url in image_urls_in_chunk:
                                            if url.startswith('data:image/'):
                                                print(f"[Tutu DEBUG] 🎯 OpenRouter续行提取base64图片")
                                            else:
                                                print(f"[Tutu DEBUG] 🎯 OpenRouter续行提取URL: {url[:50]}...")
                                            accumulated_content += " " + url
                            elif is_apicore:
                                # APICore.ai续行处理
                                print(f"[Tutu DEBUG] 🔍 APICore.ai续行检查: 搜索图片数据")

                                # 检查顶级字段中的图片数据
                                for key, value in chunk_data.items():
                                    if key not in ['id', 'object', 'created', 'model', 'system_fingerprint', 'choices', 'usage']:
                                        if isinstance(value, str) and ('data:image/' in value or 'http' in value):
                                            print(f"[Tutu DEBUG] 🎯 APICore.ai续行在{key}发现图片数据!")
                                            accumulated_content += " " + value

                                # 全面搜索续行中的图片数据
                                if 'data:image/' in chunk_str or 'generated_image' in chunk_str or 'image_url' in chunk_str:
                                    print(f"[Tutu DEBUG] 🎯 APICore.ai续行JSON中发现图片相关数据!")
                                    import re
                                    patterns = [
                                        r'data:image/[^",\s]+',
                                        r'https?://[^",\s]+\.(?:png|jpg|jpeg|gif|webp)',
                                        r'"image_url":\s*"([^"]+)"',
                                        r'"generated_image":\s*"([^"]+)"'
                                    ]

                                    for pattern in patterns:
                                        urls = re.findall(pattern, chunk_str)
                                        if urls:
                                            print(f"[Tutu DEBUG] 🎯 APICore.ai续行用模式找到: {len(urls)}个URL")
                                            for url in urls:
                                                if url.startswith('data:image/'):
                                                    print(f"[Tutu DEBUG] 🎯 APICore.ai续行提取base64图片")
                                                else:
                                                    print(f"[Tutu DEBUG] 🎯 APICore.ai续行提取URL: {url[:50]}...")
                                                accumulated_content += " " + url
                            
                            # 保存完整的响应数据用于调试
                            raw_response_parts.append(chunk_data)
                            
                        except json.JSONDecodeError as e:
                            print(f"[Tutu DEBUG] 续行JSON仍然解析失败: {e}")
                            # 仍然不完整，继续等待
                            pass
                        
        except Exception as e:
            print(f"[Tutu ERROR] SSE流处理错误: {e}")
            
        print(f"[Tutu DEBUG] SSE处理完成:")
        print(f"[Tutu DEBUG] - 总共处理了{chunk_count}个数据块")
        print(f"[Tutu DEBUG] - 累积内容长度: {len(accumulated_content)}")
        
        # 简单截断长内容，避免base64刷屏
        if 'data:image/' in accumulated_content:
            base64_count = accumulated_content.count('data:image/')
            print(f"[Tutu DEBUG] - 累积内容: 包含{base64_count}个base64图片 + 文本({len(accumulated_content)}字符)")
        elif len(accumulated_content) > 200:
            print(f"[Tutu DEBUG] - 累积内容: {repr(accumulated_content[:200])}...")
        else:
            print(f"[Tutu DEBUG] - 累积内容: {repr(accumulated_content)}")
        
        print(f"[Tutu DEBUG] - 完整响应块数: {len(raw_response_parts)}")
            
        return accumulated_content

    def extract_image_urls(self, response_text):
        print(f"[Tutu DEBUG] 开始提取图片URL...")
        print(f"[Tutu DEBUG] 响应文本长度: {len(response_text)}")
        
        # 简单处理响应文本，避免base64刷屏
        if 'data:image/' in response_text:
            base64_count = response_text.count('data:image/')
            print(f"[Tutu DEBUG] 响应文本: 包含{base64_count}个base64图片({len(response_text)}字符)")
        elif len(response_text) > 500:
            print(f"[Tutu DEBUG] 响应文本内容: {response_text[:500]}...")
        else:
            print(f"[Tutu DEBUG] 响应文本内容: {response_text}")
        
        # Check for markdown image format
        print(f"[Tutu DEBUG] 1. 检查markdown图片格式...")
        image_pattern = r'!\[.*?\]\((.*?)\)'
        matches = re.findall(image_pattern, response_text)
        if matches:
            # 简单显示URL数量，避免刷屏
            base64_count = sum(1 for url in matches if url.startswith('data:image/'))
            http_count = len(matches) - base64_count
            print(f"[Tutu DEBUG] 找到markdown图片: {base64_count}个base64图片, {http_count}个HTTP链接")
            return matches

        # Check for direct HTTP image URLs  
        print(f"[Tutu DEBUG] 2. 检查直接HTTP图片URL...")
        url_pattern = r'https?://\S+\.(?:jpg|jpeg|png|gif|webp)'
        matches = re.findall(url_pattern, response_text)
        if matches:
            print(f"[Tutu DEBUG] 找到HTTP图片URL: {len(matches)}个")
            return matches
        
        # Check for any URLs
        print(f"[Tutu DEBUG] 3. 检查任何URL...")
        all_url_pattern = r'https?://[^\s)]+'
        matches = re.findall(all_url_pattern, response_text)
        if matches:
            print(f"[Tutu DEBUG] 找到一般URL: {len(matches)}个")
            return matches
            
        # Check for base64 data URLs
        print(f"[Tutu DEBUG] 4. 检查base64数据URL...")
        base64_pattern = r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+'
        matches = re.findall(base64_pattern, response_text)
        if matches:
            print(f"[Tutu DEBUG] 找到base64 URL: {len(matches)}个")
            return matches
        
        print(f"[Tutu DEBUG] 未找到任何图片URL")
        return []

    def resize_to_target_size(self, image, target_size):
        """Resize image to target size while preserving aspect ratio with padding"""

        img_width, img_height = image.size
        target_width, target_height = target_size

        width_ratio = target_width / img_width
        height_ratio = target_height / img_height
        scale = min(width_ratio, height_ratio)

        new_width = int(img_width * scale)
        new_height = int(img_height * scale)

        resized_img = image.resize((new_width, new_height), Image.LANCZOS)

        new_img = Image.new("RGB", (target_width, target_height), (255, 255, 255))

        paste_x = (target_width - new_width) // 2
        paste_y = (target_height - new_height) // 2
 
        new_img.paste(resized_img, (paste_x, paste_y))
        
        return new_img

    def parse_resolution(self, resolution_str):
        """Parse resolution string (e.g., '1024x1024') to width and height"""
        width, height = map(int, resolution_str.split('x'))
        return (width, height)

    def _sanitize_content_for_debug(self, content):
        """Sanitize content for debug logging"""
        if isinstance(content, str):
            # String format (comfly)
            return content[:200] + ('...' if len(content) > 200 else '')
        elif isinstance(content, list):
            # Array format (OpenRouter)
            sanitized = []
            for item in content:
                if item.get('type') == 'text':
                    text = item.get('text', '')[:100]
                    sanitized.append({
                        'type': 'text',
                        'text': text + ('...' if len(item.get('text', '')) > 100 else '')
                    })
                elif item.get('type') == 'image_url':
                    sanitized.append({
                        'type': 'image_url',
                        'image_url': '[IMAGE_DATA]'
                    })
            return sanitized
        else:
            return '[UNKNOWN_CONTENT_TYPE]'

    def _parse_and_validate_model(self, model_with_tag, api_provider):
        """解析带标签的模型名称并验证是否与API提供商匹配"""
        # 模型格式：[Provider] model_name
        if not model_with_tag.startswith('['):
            # 如果没有标签，直接返回（向后兼容）
            return model_with_tag

        try:
            # 解析标签和模型名
            tag_end = model_with_tag.find(']')
            if tag_end == -1:
                return model_with_tag

            provider_tag = model_with_tag[1:tag_end]  # 去掉方括号
            actual_model = model_with_tag[tag_end + 2:]  # 去掉"] "

            # 验证提供商匹配
            if api_provider == "OpenRouter" and provider_tag != "OpenRouter":
                print(f"[Tutu WARNING] 选择了OpenRouter但模型是{provider_tag}的")
                return None
            elif api_provider == "ai.comfly.chat" and provider_tag != "Comfly":
                print(f"[Tutu WARNING] 选择了ai.comfly.chat但模型是{provider_tag}的")
                return None
            elif api_provider == "APICore.ai" and provider_tag != "APICore":
                print(f"[Tutu WARNING] 选择了APICore.ai但模型是{provider_tag}的")
                return None

            print(f"[Tutu DEBUG] 解析模型: {provider_tag} -> {actual_model}")
            return actual_model

        except Exception as e:
            print(f"[Tutu ERROR] 模型名称解析失败: {e}")
            return model_with_tag

    def _get_model_suggestions(self, api_provider):
        """根据API提供商获取推荐的模型选择"""
        if api_provider == "OpenRouter":
            return "• [OpenRouter] google/gemini-2.5-flash-image-preview (推荐，支持图片生成)"
        elif api_provider == "APICore.ai":
            return "• [APICore] gemini-2.5-flash-image (标准模型)\n• [APICore] gemini-2.5-flash-image-hd (高清模型，推荐)"
        else:  # ai.comfly.chat
            return "• [Comfly] gemini-2.5-flash-image-preview (推荐)\n• [Comfly] gemini-2.0-flash-preview-image-generation"

    def _get_api_key_error_message(self, api_provider, current_api_key):
        """生成详细的API密钥错误信息"""
        if api_provider == "APICore.ai":
            return f"""❌ **APICore.ai API密钥配置问题**

**当前状态**: {'API密钥为空' if not current_api_key else f'API密钥过短 ({len(current_api_key)} 字符)'}

**📋 配置方法**:

**方法1 - 在节点中直接输入**:
1. 在节点的 "apicore_api_key" 输入框中输入您的API密钥
2. 密钥格式通常为: sk-xxxxx...

**方法2 - 修改配置文件**:
1. 编辑文件: Tutuapi.json
2. 将 "apicore_api_key" 字段的值替换为您的真实API密钥
3. 保存文件后重新运行

**获取APICore.ai API密钥**:
• 访问 APICore.ai 官网注册账户
• 在控制台中生成API密钥
• 复制密钥到配置中

**示例配置**:
```json
{{
    "comfly_api_key": "your_comfly_api_key_here",
    "openrouter_api_key": "your_openrouter_api_key_here",
    "apicore_api_key": "sk-your-apicore-key-here"
}}
```

**注意**: API密钥是敏感信息，请妥善保管，不要分享给他人。"""

        elif api_provider == "OpenRouter":
            return f"""❌ **OpenRouter API密钥配置问题**

**当前状态**: {'API密钥为空' if not current_api_key else f'API密钥过短 ({len(current_api_key)} 字符)'}

**📋 配置方法**:

**方法1 - 在节点中直接输入**:
1. 在节点的 "openrouter_api_key" 输入框中输入您的API密钥

**方法2 - 修改配置文件**:
1. 编辑文件: Tutuapi.json
2. 将 "openrouter_api_key" 字段的值替换为您的真实API密钥

**获取OpenRouter API密钥**:
• 访问 https://openrouter.ai/
• 注册账户并生成API密钥
• 密钥格式: sk-or-v1-xxxxx...

**注意**: API密钥是敏感信息，请妥善保管。"""

        else:  # ai.comfly.chat
            return f"""❌ **ai.comfly.chat API密钥配置问题**

**当前状态**: {'API密钥为空' if not current_api_key else f'API密钥过短 ({len(current_api_key)} 字符)'}

**📋 配置方法**:

**方法1 - 在节点中直接输入**:
1. 在节点的 "comfly_api_key" 输入框中输入您的API密钥

**方法2 - 修改配置文件**:
1. 编辑文件: Tutuapi.json
2. 将 "comfly_api_key" 字段的值替换为您的真实API密钥

**获取ai.comfly.chat API密钥**:
• 访问 https://ai.comfly.chat/
• 注册账户并获取API访问权限

**向后兼容性**: 也支持旧版本的 "api_key" 字段名。

**注意**: API密钥是敏感信息，请妥善保管。"""

    def process(self, prompt, api_provider, model, num_images, temperature, top_p, timeout=120,
                input_image_1=None, input_image_2=None, input_image_3=None, input_image_4=None, input_image_5=None,
                comfly_api_key="", openrouter_api_key="", apicore_api_key=""):

        print(f"\n[Tutu DEBUG] ========== Starting Gemini API Process ==========")
        print(f"[Tutu DEBUG] Parameters:")
        print(f"[Tutu DEBUG] - API Provider: {api_provider}")
        print(f"[Tutu DEBUG] - Model: {model}")
        print(f"[Tutu DEBUG] - Prompt length: {len(prompt) if prompt else 0}")
        print(f"[Tutu DEBUG] - Has input_image_1: {input_image_1 is not None}")
        print(f"[Tutu DEBUG] - Has input_image_2: {input_image_2 is not None}")
        print(f"[Tutu DEBUG] - Has input_image_3: {input_image_3 is not None}")
        print(f"[Tutu DEBUG] - Has input_image_4: {input_image_4 is not None}")
        print(f"[Tutu DEBUG] - Has input_image_5: {input_image_5 is not None}")
        
        # Display model selection guide
        print(f"\n[Tutu INFO] 💡 Model Selection Guide:")
        print(f"[Tutu INFO] • For ai.comfly.chat: Select [Comfly] tagged models")
        print(f"[Tutu INFO] • For OpenRouter: Select [OpenRouter] tagged models")
        print(f"[Tutu INFO] • For APICore.ai: Select [APICore] tagged models")
        print(f"[Tutu INFO] • Current combination: {api_provider} + {model}")

        # 根据API提供商设置端点
        if api_provider == "OpenRouter":
            api_endpoint = "https://openrouter.ai/api/v1/chat/completions"
        elif api_provider == "APICore.ai":
            api_endpoint = "https://ismaque.org/v1/images/generations"
        else:
            api_endpoint = "https://ai.comfly.chat/v1/chat/completions"
        
        print(f"[Tutu DEBUG] API Endpoint: {api_endpoint}")

        # 处理模型选择并验证
        actual_model = self._parse_and_validate_model(model, api_provider)
        if not actual_model:
            suggestions = self._get_model_suggestions(api_provider)
            error_msg = f"❌ 模型选择错误！\n\n当前选择: '{model}'\nAPI提供商: '{api_provider}'\n\n💡 建议选择:\n{suggestions}\n\n请重新选择正确的模型。"
            print(f"[Tutu ERROR] {error_msg}")
            return self.handle_error(input_image_1, input_image_2, input_image_3, input_image_4, input_image_5, error_msg)
        
        model = actual_model
        print(f"[Tutu DEBUG] Using actual model: {model}")

        # Save original prompt for processing
        original_prompt = prompt
        
        # 处理API Key更新和保存
        config_changed = False
        config = get_config()
        
        # 处理 comfly API key
        if comfly_api_key.strip():
            print(f"[Tutu DEBUG] Using provided comfly API key: {comfly_api_key[:10]}...")
            self.comfly_api_key = comfly_api_key
            config['comfly_api_key'] = comfly_api_key
            config_changed = True
            
        # 处理 OpenRouter API key
        if openrouter_api_key.strip():
            print(f"[Tutu DEBUG] Using provided OpenRouter API key: {openrouter_api_key[:10]}...")
            self.openrouter_api_key = openrouter_api_key
            config['openrouter_api_key'] = openrouter_api_key
            config_changed = True

        # 处理 APICore.ai API key
        if apicore_api_key.strip():
            print(f"[Tutu DEBUG] Using provided APICore.ai API key: {apicore_api_key[:10]}...")
            self.apicore_api_key = apicore_api_key
            config['apicore_api_key'] = apicore_api_key
            config_changed = True
            
        # 保存配置
        if config_changed:
            save_config(config)
            
        # 显示当前使用的API key
        current_api_key = self.get_current_api_key(api_provider)
        print(f"[Tutu DEBUG] Using {api_provider} API key: {current_api_key[:10] if current_api_key else 'None'}...")

        self.timeout = timeout
        
        print(f"[Tutu DEBUG] Final parameters:")
        print(f"[Tutu DEBUG] - Model: {model}")
        print(f"[Tutu DEBUG] - Temperature: {temperature}")
        print(f"[Tutu DEBUG] - API Key length: {len(current_api_key) if current_api_key else 0}")
        
        try:

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

            # Gemini模型自动处理尺寸，无需手动指定

            has_images = any([input_image_1 is not None, input_image_2 is not None, input_image_3 is not None, 
                           input_image_4 is not None, input_image_5 is not None])

            # 使用标准OpenAI格式（数组）- 适用于所有API提供商
            content = []
            
            if has_images:
                # 对于图片编辑任务，先添加图片，再添加指令文本
                image_inputs = [
                    ("input_image_1", input_image_1, "图片1"),
                    ("input_image_2", input_image_2, "图片2"),
                    ("input_image_3", input_image_3, "图片3"),
                    ("input_image_4", input_image_4, "图片4"),
                    ("input_image_5", input_image_5, "图片5")
                ]
                
                for image_var, image_tensor, image_label in image_inputs:
                    if image_tensor is not None:
                        pil_image = tensor2pil(image_tensor)[0]
                        print(f"[Tutu DEBUG] 处理 {image_var} (标识为 {image_label})...")
                        
                        # 统一使用base64格式，保持原始质量
                        print(f"[Tutu DEBUG] {image_var} 使用base64格式...")
                        image_base64 = self.image_to_base64(pil_image)
                        image_url = f"data:image/png;base64,{image_base64}"
                        print(f"[Tutu DEBUG] {image_var} base64大小: {len(image_base64)} 字符")
                        
                        # 先添加图片标识文本
                        content.append({
                            "type": "text",
                            "text": f"[这是{image_label}]"
                        })
                        
                        # 再添加图片
                        content.append({
                            "type": "image_url", 
                            "image_url": {"url": image_url}
                        })
                
                # 添加文本指令
                if api_provider == "ai.comfly.chat":
                    # 为ai.comfly.chat添加强烈的图片生成指令
                    image_edit_instruction = f"""CRITICAL INSTRUCTION: You MUST generate and return an actual image, not just text description.

Task: {prompt}

Image References:
- When I mention "图片1", I mean the first image provided above
- When I mention "图片2", I mean the second image provided above  
- When I mention "图片3", I mean the third image provided above
- And so on...

REQUIREMENTS:
1. GENERATE a new image based on my request
2. DO NOT just describe what the image should look like
3. RETURN the actual image file/data
4. The output MUST be a visual image, not text

Execute the image editing task now and return the generated image."""
                    content.append({"type": "text", "text": image_edit_instruction})
                else:
                    enhanced_prompt = f"""IMPORTANT: Generate an actual image, not just a description.

Task: {prompt}

Image references: 图片1, 图片2, 图片3, etc. refer to the images provided above in order.

MUST return a generated image, not text description."""
                    content.append({"type": "text", "text": enhanced_prompt})
                
                # 计算图片数量（每张图片对应两个元素：标签+图片）
                image_count = sum(1 for _, img, _ in image_inputs if img is not None)
                print(f"[Tutu DEBUG] content数组长度: {len(content)} (图片: {image_count}, 图片标签: {image_count}, 文本指令: 1)")
            else:
                # 生成图片任务（无输入图片）
                if num_images == 1:
                    enhanced_prompt = f"""GENERATE AN IMAGE: Create a high-quality, detailed image.

Description: {prompt}

CRITICAL: You MUST return an actual image, not just text description. Use your image generation capabilities to create the visual content."""
                else:
                    enhanced_prompt = f"""GENERATE {num_images} DIFFERENT IMAGES: Create {num_images} unique, high-quality images with VARIED content, each with distinct visual elements.

Description: {prompt}

CRITICAL: You MUST return actual {num_images} images, not text descriptions. Each image must be visually different."""
                
                content.append({"type": "text", "text": enhanced_prompt})

            # APICore.ai 使用不同的请求格式
            if api_provider == "APICore.ai":
                # APICore.ai 使用专门的图像生成API格式
                final_prompt = enhanced_prompt if not has_images else f"{prompt}"

                # 如果有输入图像，APICore.ai可能需要特殊处理
                if has_images:
                    # 对于APICore.ai，将图像信息作为文本描述添加到prompt中
                    image_descriptions = []
                    image_inputs = [
                        ("input_image_1", input_image_1, "参考图片1"),
                        ("input_image_2", input_image_2, "参考图片2"),
                        ("input_image_3", input_image_3, "参考图片3"),
                        ("input_image_4", input_image_4, "参考图片4"),
                        ("input_image_5", input_image_5, "参考图片5")
                    ]

                    for image_var, image_tensor, image_label in image_inputs:
                        if image_tensor is not None:
                            image_descriptions.append(f"基于{image_label}的内容")

                    if image_descriptions:
                        final_prompt = f"{prompt} (参考图像: {', '.join(image_descriptions)})"

                payload = {
                    "prompt": final_prompt,
                    "model": clean_model_name(model),  # 移除[APICore]标签
                    "size": "1x1",  # APICore.ai 的固定格式
                    "n": num_images
                }
                # APICore.ai 不使用流式响应
                use_streaming = False
            else:
                # 其他提供商使用标准ChatCompletion格式
                messages = [{
                    "role": "user",
                    "content": content
                }]

                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": 8192,
                    "n": num_images,
                    "stream": True  # Required for gemini-2.5-flash-image-preview
                }
                use_streaming = True

            # 添加调试日志
            print(f"\n[Tutu DEBUG] API Request Details:")
            print(f"[Tutu DEBUG] API Provider: {api_provider}")
            print(f"[Tutu DEBUG] Model: {model}")
            print(f"[Tutu DEBUG] Has images: {has_images}")
            if api_provider != "APICore.ai":
                print(f"[Tutu DEBUG] Messages count: {len(messages)}")
            print(f"[Tutu DEBUG] Content type: {type(content)}")
            print(f"[Tutu DEBUG] Content length: {len(str(content))}")

            # 记录payload大小（但不打印图片数据）
            payload_copy = payload.copy()
            if api_provider != "APICore.ai" and 'messages' in payload:
                payload_copy['messages'] = [{
                    'role': msg['role'],
                    'content': self._sanitize_content_for_debug(msg['content'])
                } for msg in payload['messages']]
            
            print(f"[Tutu DEBUG] Payload structure: {json.dumps(payload_copy, indent=2, ensure_ascii=False)}")
            
            # 检查API Key
            headers = self.get_headers(api_provider)
            print(f"[Tutu DEBUG] Headers: {dict(headers)}")

            if not current_api_key or len(current_api_key) < 10:
                print(f"[Tutu DEBUG] WARNING: API Key seems invalid: '{current_api_key[:10] if current_api_key else 'None'}...")

                # 提供详细的API密钥配置指导
                key_error_msg = self._get_api_key_error_message(api_provider, current_api_key)
                if not current_api_key:
                    # 如果完全没有API密钥，抛出错误
                    raise Exception(key_error_msg)

            pbar = comfy.utils.ProgressBar(100)
            pbar.update_absolute(10)

            try:
                print(f"[Tutu DEBUG] Sending request to: {api_endpoint}")

                if api_provider == "APICore.ai":
                    # APICore.ai 使用标准JSON响应，不是流式
                    response = requests.post(
                        api_endpoint,
                        headers=headers,
                        json=payload,
                        timeout=self.timeout
                        # 不设置stream=True
                    )
                else:
                    # 其他提供商使用流式响应
                    response = requests.post(
                        api_endpoint,
                        headers=headers,
                        json=payload,
                        timeout=self.timeout,
                        stream=True  # Enable streaming for SSE
                    )

                print(f"[Tutu DEBUG] Response status: {response.status_code}")
                print(f"[Tutu DEBUG] Response headers: {dict(response.headers)}")

                # 如果状态码不是200，尝试读取错误响应
                if response.status_code != 200:
                    try:
                        error_text = response.text[:1000]  # 只读取前1000字符
                        print(f"[Tutu DEBUG] Error response body: {error_text}")
                    except:
                        print(f"[Tutu DEBUG] Could not read error response body")

                response.raise_for_status()

                # 处理响应 - 根据API提供商选择不同的处理方式
                if api_provider == "APICore.ai":
                    # APICore.ai 返回标准JSON响应
                    response_text = self.process_apicore_response(response)
                else:
                    # 其他提供商处理SSE流
                    response_text = self.process_sse_stream(response, api_provider)

                print(f"[Tutu DEBUG] 响应处理完成，获得响应文本长度: {len(response_text)}")

            except requests.exceptions.Timeout:
                print(f"[Tutu DEBUG] Request timeout after {self.timeout} seconds")
                raise TimeoutError(f"API request timed out after {self.timeout} seconds")
            except requests.exceptions.HTTPError as e:
                print(f"[Tutu DEBUG] HTTP Error: {e}")
                print(f"[Tutu DEBUG] Response status: {e.response.status_code}")
                try:
                    error_detail = e.response.text[:500]
                    print(f"[Tutu DEBUG] Error detail: {error_detail}")
                    
                    # 特殊处理404错误（模型不存在）
                    if e.response.status_code == 404 and "No endpoints found" in error_detail:
                        suggestions = self._get_model_suggestions(api_provider)
                        model_error = f"""❌ **模型不存在错误**

**当前选择的模型**: `{model}`
**错误**: 此模型在 {api_provider} 上不可用

**💡 建议选择可用的模型**:
{suggestions}

**解决方案**:
1. 切换到上面推荐的可用模型
2. 确认模型名称拼写正确
3. 检查 {api_provider} 官方文档获取最新支持的模型列表"""
                        raise Exception(model_error)
                    else:
                        raise Exception(f"HTTP {e.response.status_code} Error: {error_detail}")
                except:
                    raise Exception(f"HTTP Error: {str(e)}")
            except requests.exceptions.RequestException as e:
                print(f"[Tutu DEBUG] Request Exception: {str(e)}")
                raise Exception(f"API request failed: {str(e)}")
            
            pbar.update_absolute(40)

            # 简化base64内容以避免刷屏
            truncated_response = self._truncate_base64_in_response(response_text, max_base64_len=100)
            formatted_response = f"**User prompt**: {prompt}\n\n**Response** ({timestamp}):\n{truncated_response}"
            
            print(f"[Tutu DEBUG] 准备提取图片URL，响应文本长度: {len(response_text)}")
            image_urls = self.extract_image_urls(response_text)
            print(f"[Tutu DEBUG] 图片URL提取完成，找到{len(image_urls)}个URL")
            
            if image_urls:
                try:
                    images = []
                    first_image_url = ""  
                    
                    for i, url in enumerate(image_urls):
                        pbar.update_absolute(40 + (i+1) * 50 // len(image_urls))
                        
                        if i == 0:
                            first_image_url = url  
                        
                        try:
                            if url.startswith('data:image/'):
                                # Handle base64 data URL
                                base64_data = url.split(',', 1)[1]
                                image_data = base64.b64decode(base64_data)
                                pil_image = Image.open(BytesIO(image_data))
                            else:
                                # Handle HTTP URL
                                img_response = requests.get(url, timeout=self.timeout)
                                img_response.raise_for_status()
                                pil_image = Image.open(BytesIO(img_response.content))

                            # 直接使用生成的原图，不进行尺寸调整以避免白边
                            img_tensor = pil2tensor(pil_image)
                            images.append(img_tensor)
                            
                        except Exception as img_error:
                            print(f"Error processing image URL {i+1}: {str(img_error)}")
                            continue
                    
                    if images:
                        try:
                            combined_tensor = torch.cat(images, dim=0)
                        except RuntimeError:
                            combined_tensor = images[0] if images else None
                            
                        pbar.update_absolute(100)
                        return (combined_tensor, formatted_response, first_image_url)
                    else:
                        raise Exception("No images could be processed successfully")
                    
                except Exception as e:
                    print(f"Error processing image URLs: {str(e)}")

            # No image URLs found in response - 可能是SSE解析问题
            print(f"[Tutu WARNING] ⚠️  响应中未找到图片URL - 可能是SSE解析问题")
            # 简单显示响应内容，避免base64刷屏
            if 'data:image/' in response_text:
                base64_count = response_text.count('data:image/')
                print(f"[Tutu DEBUG] 📝 当前解析响应: 包含{base64_count}个base64图片({len(response_text)}字符)")
            elif len(response_text) > 200:
                print(f"[Tutu DEBUG] 📝 当前解析响应: {repr(response_text[:200])}...")
            else:
                print(f"[Tutu DEBUG] 📝 当前解析响应: {repr(response_text)}")
            print(f"[Tutu DEBUG] 🔍 Gemini 2.5 Flash Image Preview 支持图片生成，问题可能在数据解析上")
            print(f"[Tutu DEBUG] 💡 检查点:")
            print(f"[Tutu DEBUG]    1. SSE流是否完整解析？")
            print(f"[Tutu DEBUG]    2. JSON数据是否被正确拼接？")
            print(f"[Tutu DEBUG]    3. 编码是否正确处理？")
            
            pbar.update_absolute(100)

            reference_image = None
            for img in [input_image_1, input_image_2, input_image_3, input_image_4, input_image_5]:
                if img is not None:
                    reference_image = img
                    break
                
            # 添加调试说明到响应中
            debug_info = f"""

## 🔧 **调试信息：SSE解析问题**

**当前状态**: 响应解析可能不完整
**解析到的内容**: {response_text}
**问题**: Gemini 2.5 Flash Image Preview 支持图片生成，但我们的SSE流解析可能有bug

**请检查控制台日志获取详细的解析过程**
"""
            formatted_response += debug_info
                
            if reference_image is not None:
                return (reference_image, formatted_response, "")
            else:
                default_image = Image.new('RGB', (1024, 1024), color='white')
                default_tensor = pil2tensor(default_image)
                return (default_tensor, formatted_response, "")
            
        except TimeoutError as e:
            error_message = f"API timeout error: {str(e)}"
            print(f"[Tutu DEBUG] TimeoutError occurred: {error_message}")
            return self.handle_error(input_image_1, input_image_2, input_image_3, input_image_4, input_image_5, error_message)
            
        except Exception as e:
            error_message = f"Error calling Gemini API: {str(e)}"
            print(f"[Tutu DEBUG] Exception occurred:")
            print(f"[Tutu DEBUG] - Type: {type(e).__name__}")
            print(f"[Tutu DEBUG] - Message: {str(e)}")
            print(f"[Tutu DEBUG] - Full error: {repr(e)}")
            
            # 打印更多上下文信息
            print(f"[Tutu DEBUG] Context at error:")
            print(f"[Tutu DEBUG] - Current model: {model if 'model' in locals() else 'undefined'}")
            print(f"[Tutu DEBUG] - API key present: {bool(current_api_key)}")
            print(f"[Tutu DEBUG] - API key length: {len(current_api_key) if current_api_key else 0}")
            
            return self.handle_error(input_image_1, input_image_2, input_image_3, input_image_4, input_image_5, error_message)
    
    def handle_error(self, input_image_1, input_image_2, input_image_3, input_image_4, input_image_5, error_message):
        """Handle errors with appropriate image output"""
        # 按优先级返回第一个可用的图片
        for img in [input_image_1, input_image_2, input_image_3, input_image_4, input_image_5]:
            if img is not None:
                return (img, error_message, "")
        
        # 如果没有输入图片，创建默认图片 (1024x1024)
        default_image = Image.new('RGB', (1024, 1024), color='white')
        default_tensor = pil2tensor(default_image)
        return (default_tensor, error_message, "")


WEB_DIRECTORY = "./web"    
        
NODE_CLASS_MAPPINGS = {
    "TutuGeminiAPI": TutuGeminiAPI,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TutuGeminiAPI": "🚀 Tutu Nano Banana",
}