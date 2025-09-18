#!/usr/bin/env python3
"""
完整集成测试套件 - Issue #2
验证所有功能的完整性、性能和向后兼容性
"""

import os
import sys
import time
import json
import traceback
import gc
import psutil
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入核心模块
from Tutu import TutuGeminiAPI, get_config, save_config, pil2tensor, tensor2pil
from utils import pil2tensor as utils_pil2tensor, tensor2pil as utils_tensor2pil
import torch
from PIL import Image
import numpy as np

class TestResult:
    """测试结果封装"""
    def __init__(self, success=False, images=None, error_message="", response_time=0.0):
        self.success = success
        self.images = images or []
        self.error_message = error_message
        self.response_time = response_time

class IntegrationTestSuite:
    """集成测试套件"""

    def __init__(self):
        self.test_results = []
        self.api_instance = TutuGeminiAPI()
        self.start_time = time.time()

        # 性能指标
        self.performance_metrics = {
            "single_image_success_count": 0,
            "single_image_total_count": 0,
            "multi_image_success_count": 0,
            "multi_image_total_count": 0,
            "total_response_times": [],
            "memory_usage_samples": []
        }

        print(f"[测试] 开始集成测试套件...")
        print(f"[测试] 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    def log_test(self, test_name, success, details="", duration=0.0):
        """记录测试结果"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"[测试] {status} {test_name} ({duration:.2f}s) - {details}")

        self.test_results.append({
            "name": test_name,
            "success": success,
            "details": details,
            "duration": duration,
            "timestamp": time.time()
        })

    def generate_test_image(self, provider, model=None, num_images=1, prompt="测试图像生成"):
        """执行测试图像生成"""
        try:
            start_time = time.time()

            # 根据提供商选择默认模型
            if not model:
                if provider == "APICore.ai":
                    model = "[APICore] gemini-2.5-flash-image"
                elif provider == "OpenRouter":
                    model = "[OpenRouter] google/gemini-2.5-flash-image-preview"
                else:  # ai.comfly.chat
                    model = "[Comfly] gemini-2.5-flash-image-preview"

            print(f"[测试生成] 提供商: {provider}, 模型: {model}, 数量: {num_images}")
            print(f"[测试生成] 提示词: {prompt}")

            # 执行生成
            result_tensor, response_text, image_url = self.api_instance.process(
                prompt=prompt,
                api_provider=provider,
                model=model,
                num_images=num_images,
                temperature=1.0,
                top_p=0.95,
                timeout=60  # 测试时使用较短的超时
            )

            end_time = time.time()
            response_time = end_time - start_time

            # 验证结果
            if result_tensor is not None:
                # 检查tensor维度
                if len(result_tensor.shape) == 4:  # [batch, height, width, channels]
                    batch_size = result_tensor.shape[0]
                    if batch_size == num_images:
                        print(f"[测试生成] ✅ 成功生成 {batch_size} 张图像")
                        return TestResult(
                            success=True,
                            images=[result_tensor[i] for i in range(batch_size)],
                            response_time=response_time
                        )
                    else:
                        print(f"[测试生成] ❌ 生成数量不匹配: 期望{num_images}, 实际{batch_size}")
                        return TestResult(
                            success=False,
                            error_message=f"生成数量不匹配: 期望{num_images}, 实际{batch_size}",
                            response_time=response_time
                        )
                else:
                    print(f"[测试生成] ✅ 单张图像生成成功")
                    return TestResult(
                        success=True,
                        images=[result_tensor],
                        response_time=response_time
                    )
            else:
                print(f"[测试生成] ❌ 未生成图像")
                return TestResult(
                    success=False,
                    error_message="未生成图像",
                    response_time=response_time
                )

        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            error_msg = f"生成失败: {str(e)}"
            print(f"[测试生成] ❌ {error_msg}")
            print(f"[测试生成] 错误详情: {traceback.format_exc()}")

            return TestResult(
                success=False,
                error_message=error_msg,
                response_time=response_time
            )

    def test_phase_1_basic_functionality(self):
        """阶段1: 基础功能测试"""
        print(f"\n[测试阶段1] 基础功能测试")
        print("=" * 50)

        # 1.1 配置加载测试
        start_time = time.time()
        try:
            config = get_config()
            self.log_test("配置加载", True, f"配置版本: {config.get('config_version', 'unknown')}", time.time() - start_time)
        except Exception as e:
            self.log_test("配置加载", False, str(e), time.time() - start_time)

        # 1.2 API实例创建测试
        start_time = time.time()
        try:
            api = TutuGeminiAPI()
            self.log_test("API实例创建", True, "成功创建TutuGeminiAPI实例", time.time() - start_time)
        except Exception as e:
            self.log_test("API实例创建", False, str(e), time.time() - start_time)

        # 1.3 提供商选择测试
        providers = ["ai.comfly.chat", "OpenRouter", "APICore.ai"]
        for provider in providers:
            start_time = time.time()
            try:
                # 测试端点获取
                endpoint = self.api_instance._get_api_endpoint(provider)
                success = endpoint is not None and endpoint.startswith("http")
                details = f"端点: {endpoint}" if success else "端点获取失败"
                self.log_test(f"提供商{provider}端点", success, details, time.time() - start_time)
            except Exception as e:
                self.log_test(f"提供商{provider}端点", False, str(e), time.time() - start_time)

    def test_phase_2_num_images_functionality(self):
        """阶段2: num_images功能测试"""
        print(f"\n[测试阶段2] num_images功能测试")
        print("=" * 50)

        # 测试各种数量的图像生成
        test_counts = [1, 2, 3, 4]
        providers = ["APICore.ai"]  # 主要测试APICore.ai，因为它是新功能

        for provider in providers:
            for count in test_counts:
                start_time = time.time()

                try:
                    result = self.generate_test_image(
                        provider=provider,
                        num_images=count,
                        prompt=f"生成{count}张不同的风景图片"
                    )

                    # 更新性能指标
                    if count == 1:
                        self.performance_metrics["single_image_total_count"] += 1
                        if result.success:
                            self.performance_metrics["single_image_success_count"] += 1
                    else:
                        self.performance_metrics["multi_image_total_count"] += 1
                        if result.success and len(result.images) == count:
                            self.performance_metrics["multi_image_success_count"] += 1

                    self.performance_metrics["total_response_times"].append(result.response_time)

                    # 验证结果
                    success = result.success and len(result.images) == count
                    details = f"期望{count}张, 实际{len(result.images)}张, 耗时{result.response_time:.2f}s"

                    self.log_test(
                        f"{provider}生成{count}张图像",
                        success,
                        details,
                        result.response_time
                    )

                except Exception as e:
                    self.log_test(
                        f"{provider}生成{count}张图像",
                        False,
                        f"异常: {str(e)}",
                        time.time() - start_time
                    )

    def test_phase_3_apicore_specific(self):
        """阶段3: APICore.ai特定功能测试"""
        print(f"\n[测试阶段3] APICore.ai特定功能测试")
        print("=" * 50)

        # 3.1 基础生成测试
        start_time = time.time()
        result = self.generate_test_image(
            provider="APICore.ai",
            model="[APICore] gemini-2.5-flash-image",
            num_images=1,
            prompt="生成一只可爱的猫咪"
        )

        self.log_test(
            "APICore.ai基础生成",
            result.success,
            f"响应时间: {result.response_time:.2f}s",
            result.response_time
        )

        # 3.2 高清模型测试
        start_time = time.time()
        result = self.generate_test_image(
            provider="APICore.ai",
            model="[APICore] gemini-2.5-flash-image-hd",
            num_images=1,
            prompt="高质量自然风景"
        )

        self.log_test(
            "APICore.ai高清模型",
            result.success,
            f"响应时间: {result.response_time:.2f}s",
            result.response_time
        )

        # 3.3 多图片参考功能测试（使用ComfyUI输入端口模拟）
        start_time = time.time()
        try:
            # 创建测试图像tensor
            test_image1 = torch.rand(1, 512, 512, 3)  # 随机测试图像
            test_image2 = torch.rand(1, 512, 512, 3)  # 随机测试图像

            result_tensor, response_text, image_url = self.api_instance.process(
                prompt="将第一张图片的风格应用到第二张图片上",
                api_provider="APICore.ai",
                model="[APICore] gemini-2.5-flash-image",
                num_images=1,
                temperature=1.0,
                top_p=0.95,
                timeout=60,
                input_image_1=test_image1,
                input_image_2=test_image2
            )

            duration = time.time() - start_time
            success = result_tensor is not None

            self.log_test(
                "APICore.ai多图片参考",
                success,
                f"双图输入处理, 响应时间: {duration:.2f}s",
                duration
            )

        except Exception as e:
            self.log_test(
                "APICore.ai多图片参考",
                False,
                f"异常: {str(e)}",
                time.time() - start_time
            )

    def test_phase_4_performance_metrics(self):
        """阶段4: 性能指标测试"""
        print(f"\n[测试阶段4] 性能指标测试")
        print("=" * 50)

        # 4.1 响应时间基准测试
        max_response_time = 30.0  # 30秒基准

        if self.performance_metrics["total_response_times"]:
            avg_response_time = sum(self.performance_metrics["total_response_times"]) / len(self.performance_metrics["total_response_times"])
            max_actual_time = max(self.performance_metrics["total_response_times"])

            response_time_ok = avg_response_time <= max_response_time

            self.log_test(
                "响应时间基准",
                response_time_ok,
                f"平均: {avg_response_time:.2f}s, 最大: {max_actual_time:.2f}s, 基准: {max_response_time}s",
                0
            )
        else:
            self.log_test("响应时间基准", False, "无响应时间数据", 0)

        # 4.2 成功率计算
        if self.performance_metrics["single_image_total_count"] > 0:
            single_success_rate = self.performance_metrics["single_image_success_count"] / self.performance_metrics["single_image_total_count"]
            single_rate_ok = single_success_rate >= 0.95

            self.log_test(
                "单图生成成功率",
                single_rate_ok,
                f"{single_success_rate:.2%} (目标: ≥95%)",
                0
            )

        if self.performance_metrics["multi_image_total_count"] > 0:
            multi_success_rate = self.performance_metrics["multi_image_success_count"] / self.performance_metrics["multi_image_total_count"]
            multi_rate_ok = multi_success_rate >= 0.95

            self.log_test(
                "多图生成成功率",
                multi_rate_ok,
                f"{multi_success_rate:.2%} (目标: ≥95%)",
                0
            )

        # 4.3 内存使用测试
        start_time = time.time()
        try:
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB

            # 执行多次生成测试内存使用
            for i in range(3):
                result = self.generate_test_image("APICore.ai", num_images=2)
                if result.images:
                    # 强制垃圾回收
                    del result
                    gc.collect()

            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            memory_ok = memory_increase < 100  # 小于100MB增长

            self.log_test(
                "内存使用测试",
                memory_ok,
                f"初始: {initial_memory:.1f}MB, 最终: {final_memory:.1f}MB, 增长: {memory_increase:.1f}MB",
                time.time() - start_time
            )

        except Exception as e:
            self.log_test("内存使用测试", False, f"异常: {str(e)}", time.time() - start_time)

    def test_phase_5_error_handling(self):
        """阶段5: 错误处理测试"""
        print(f"\n[测试阶段5] 错误处理测试")
        print("=" * 50)

        # 5.1 无效API密钥测试
        start_time = time.time()
        try:
            # 保存原始配置
            original_config = get_config()

            # 设置无效密钥
            test_config = original_config.copy()
            test_config["apicore_api_key"] = "invalid_key_test"
            save_config(test_config)

            # 尝试生成（应该失败但有合理错误处理）
            result = self.generate_test_image("APICore.ai", num_images=1)

            # 恢复原始配置
            save_config(original_config)

            # 错误处理应该是优雅的
            error_handled_well = not result.success and "密钥" in result.error_message

            self.log_test(
                "无效密钥错误处理",
                error_handled_well,
                f"错误信息: {result.error_message[:100]}...",
                time.time() - start_time
            )

        except Exception as e:
            self.log_test("无效密钥错误处理", False, f"异常: {str(e)}", time.time() - start_time)

        # 5.2 模型不匹配测试
        start_time = time.time()
        try:
            result = self.generate_test_image(
                provider="APICore.ai",
                model="[OpenRouter] google/gemini-2.5-flash-image-preview",  # 错误的提供商标签
                num_images=1
            )

            # 应该有错误处理
            error_handled = not result.success and ("模型" in result.error_message or "选择错误" in result.error_message)

            self.log_test(
                "模型不匹配错误处理",
                error_handled,
                f"错误信息: {result.error_message[:100]}...",
                time.time() - start_time
            )

        except Exception as e:
            self.log_test("模型不匹配错误处理", False, f"异常: {str(e)}", time.time() - start_time)

    def test_phase_6_backward_compatibility(self):
        """阶段6: 向后兼容性测试"""
        print(f"\n[测试阶段6] 向后兼容性测试")
        print("=" * 50)

        # 6.1 旧提供商兼容性测试
        start_time = time.time()
        try:
            result = self.generate_test_image(
                provider="ai.comfly.chat",
                model="[Comfly] gemini-2.5-flash-image-preview",
                num_images=1,
                prompt="测试向后兼容性"
            )

            self.log_test(
                "ai.comfly.chat兼容性",
                result.success,
                f"响应时间: {result.response_time:.2f}s",
                result.response_time
            )

        except Exception as e:
            self.log_test("ai.comfly.chat兼容性", False, f"异常: {str(e)}", time.time() - start_time)

        # 6.2 配置文件兼容性测试
        start_time = time.time()
        try:
            config = get_config()

            # 检查必要字段存在
            required_fields = ["comfly_api_key", "openrouter_api_key", "apicore_api_key", "config_version"]
            all_fields_present = all(field in config for field in required_fields)

            self.log_test(
                "配置文件兼容性",
                all_fields_present,
                f"配置版本: {config.get('config_version', 'unknown')}",
                time.time() - start_time
            )

        except Exception as e:
            self.log_test("配置文件兼容性", False, f"异常: {str(e)}", time.time() - start_time)

    def generate_final_report(self):
        """生成最终测试报告"""
        print(f"\n[最终报告] 集成测试总结")
        print("=" * 70)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests

        total_duration = time.time() - self.start_time

        print(f"测试总数: {total_tests}")
        print(f"通过: {passed_tests} (绿色)")
        print(f"失败: {failed_tests} (红色)")
        print(f"成功率: {passed_tests/total_tests:.1%}")
        print(f"总耗时: {total_duration:.2f} 秒")

        # 性能指标摘要
        if self.performance_metrics["total_response_times"]:
            avg_time = sum(self.performance_metrics["total_response_times"]) / len(self.performance_metrics["total_response_times"])
            print(f"平均响应时间: {avg_time:.2f} 秒")

        if self.performance_metrics["single_image_total_count"] > 0:
            single_rate = self.performance_metrics["single_image_success_count"] / self.performance_metrics["single_image_total_count"]
            print(f"单图生成成功率: {single_rate:.1%}")

        if self.performance_metrics["multi_image_total_count"] > 0:
            multi_rate = self.performance_metrics["multi_image_success_count"] / self.performance_metrics["multi_image_total_count"]
            print(f"多图生成成功率: {multi_rate:.1%}")

        # 关键验收标准检查
        print(f"\n验收标准检查:")
        print("=" * 30)

        criteria_met = 0
        total_criteria = 4

        # 1. 功能测试通过率 ≥ 90%
        functional_pass_rate = passed_tests / total_tests
        if functional_pass_rate >= 0.9:
            print(f"✅ 功能测试通过率: {functional_pass_rate:.1%} (≥90%)")
            criteria_met += 1
        else:
            print(f"❌ 功能测试通过率: {functional_pass_rate:.1%} (目标: ≥90%)")

        # 2. 单图生成成功率 ≥ 95%
        if self.performance_metrics["single_image_total_count"] > 0:
            single_rate = self.performance_metrics["single_image_success_count"] / self.performance_metrics["single_image_total_count"]
            if single_rate >= 0.95:
                print(f"✅ 单图生成成功率: {single_rate:.1%} (≥95%)")
                criteria_met += 1
            else:
                print(f"❌ 单图生成成功率: {single_rate:.1%} (目标: ≥95%)")
        else:
            print(f"⚠️  单图生成成功率: 无数据")

        # 3. 平均响应时间 ≤ 30秒
        if self.performance_metrics["total_response_times"]:
            avg_time = sum(self.performance_metrics["total_response_times"]) / len(self.performance_metrics["total_response_times"])
            if avg_time <= 30.0:
                print(f"✅ 平均响应时间: {avg_time:.2f}s (≤30s)")
                criteria_met += 1
            else:
                print(f"❌ 平均响应时间: {avg_time:.2f}s (目标: ≤30s)")
        else:
            print(f"⚠️  平均响应时间: 无数据")

        # 4. 向后兼容性
        backward_compatible = any(result["name"].startswith("ai.comfly.chat") and result["success"] for result in self.test_results)
        if backward_compatible:
            print(f"✅ 向后兼容性: 通过")
            criteria_met += 1
        else:
            print(f"❌ 向后兼容性: 未通过")

        print(f"\n总体验收状态: {criteria_met}/{total_criteria} 项符合标准")

        if criteria_met >= 3:
            print(f"🎉 集成测试总体通过! 可以进行部署。")
            return True
        else:
            print(f"⚠️  集成测试未完全通过，需要修复关键问题。")
            return False

    def run_complete_test_suite(self):
        """运行完整的测试套件"""
        print(f"🚀 开始完整集成测试")
        print(f"测试开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # 运行所有测试阶段
            self.test_phase_1_basic_functionality()
            self.test_phase_2_num_images_functionality()
            self.test_phase_3_apicore_specific()
            self.test_phase_4_performance_metrics()
            self.test_phase_5_error_handling()
            self.test_phase_6_backward_compatibility()

            # 生成最终报告
            success = self.generate_final_report()

            return success

        except Exception as e:
            print(f"❌ 测试套件执行失败: {str(e)}")
            print(f"错误详情: {traceback.format_exc()}")
            return False

def main():
    """主测试入口"""
    print("=" * 70)
    print("ComfyUI BananaTutu API - 完整集成测试套件")
    print("Issue #2: comprehensive-integration-testing")
    print("=" * 70)

    # 创建并运行测试套件
    test_suite = IntegrationTestSuite()
    success = test_suite.run_complete_test_suite()

    # 返回适当的退出码
    exit_code = 0 if success else 1
    print(f"\n测试完成，退出码: {exit_code}")

    return exit_code

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)