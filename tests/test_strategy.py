#!/usr/bin/env python3
"""
OKX末日战车策略测试文件
"""

import unittest
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

class TestStrategyImports(unittest.TestCase):
    """测试策略文件导入"""
    
    def test_import_main_strategy(self):
        """测试主策略文件导入"""
        try:
            import strategies.okx_doomsday_optimized_v2_ml_integrated as strategy
            self.assertIsNotNone(strategy)
            print("✅ 主策略文件导入成功")
        except ImportError as e:
            self.fail(f"导入主策略文件失败: {e}")
    
    def test_import_ml_collector(self):
        """测试ML数据收集器导入"""
        try:
            import utils.ml_data_collector as ml
            self.assertIsNotNone(ml)
            print("✅ ML数据收集器导入成功")
        except ImportError as e:
            self.fail(f"导入ML数据收集器失败: {e}")
    
    def test_import_multi_timeframe(self):
        """测试多时间框架验证导入"""
        try:
            import utils.multi_timeframe_validation as mtf
            self.assertIsNotNone(mtf)
            print("✅ 多时间框架验证导入成功")
        except ImportError as e:
            self.fail(f"导入多时间框架验证失败: {e}")

class TestConfig(unittest.TestCase):
    """测试配置文件"""
    
    def test_config_template_exists(self):
        """测试配置文件模板存在"""
        config_path = os.path.join(os.path.dirname(__file__), '../src/config/config_template.ini')
        self.assertTrue(os.path.exists(config_path), "配置文件模板不存在")
        print("✅ 配置文件模板存在")
    
    def test_config_content(self):
        """测试配置文件内容"""
        config_path = os.path.join(os.path.dirname(__file__), '../src/config/config_template.ini')
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键配置项
        self.assertIn('[OKX]', content, "缺少OKX配置部分")
        self.assertIn('[Trading]', content, "缺少Trading配置部分")
        self.assertIn('[Strategy]', content, "缺少Strategy配置部分")
        self.assertIn('[Risk]', content, "缺少Risk配置部分")
        self.assertIn('[Optimization]', content, "缺少Optimization配置部分")
        
        print("✅ 配置文件内容完整")

class TestDependencies(unittest.TestCase):
    """测试依赖包"""
    
    def test_requirements_exists(self):
        """测试requirements文件存在"""
        req_path = os.path.join(os.path.dirname(__file__), '../requirements.txt')
        self.assertTrue(os.path.exists(req_path), "requirements.txt文件不存在")
        print("✅ requirements.txt文件存在")
    
    def test_requirements_content(self):
        """测试requirements文件内容"""
        req_path = os.path.join(os.path.dirname(__file__), '../requirements.txt')
        with open(req_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键依赖
        required_packages = ['ccxt', 'pandas', 'numpy', 'requests', 'talib']
        for package in required_packages:
            self.assertIn(package, content.lower(), f"缺少依赖包: {package}")
        
        print("✅ requirements.txt内容完整")

class TestProjectStructure(unittest.TestCase):
    """测试项目结构"""
    
    def test_directory_structure(self):
        """测试目录结构"""
        base_dir = os.path.join(os.path.dirname(__file__), '..')
        
        required_dirs = [
            'src',
            'src/strategies',
            'src/utils', 
            'src/config',
            'tools',
            'docs',
            'tests'
        ]
        
        for dir_path in required_dirs:
            full_path = os.path.join(base_dir, dir_path)
            self.assertTrue(os.path.exists(full_path), f"缺少目录: {dir_path}")
        
        print("✅ 项目目录结构完整")
    
    def test_required_files(self):
        """测试必需文件"""
        base_dir = os.path.join(os.path.dirname(__file__), '..')
        
        required_files = [
            'README.md',
            'requirements.txt',
            '.gitignore',
            'LICENSE',
            'setup.py',
            'src/strategies/okx_doomsday_optimized_v2_ml_integrated.py',
            'src/utils/ml_data_collector.py',
            'src/utils/multi_timeframe_validation.py',
            'src/config/config_template.ini',
            'docs/strategy_documentation.md'
        ]
        
        for file_path in required_files:
            full_path = os.path.join(base_dir, file_path)
            self.assertTrue(os.path.exists(full_path), f"缺少文件: {file_path}")
        
        print("✅ 项目文件完整")

def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("OKX末日战车策略 - 项目测试")
    print("=" * 60)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestStrategyImports))
    suite.addTests(loader.loadTestsFromTestCase(TestConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestDependencies))
    suite.addTests(loader.loadTestsFromTestCase(TestProjectStructure))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 60)
    print(f"测试结果: {result.testsRun}个测试")
    print(f"通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("🎉 所有测试通过！")
        return 0
    else:
        print("❌ 测试失败，请检查问题")
        return 1

if __name__ == '__main__':
    sys.exit(run_tests())