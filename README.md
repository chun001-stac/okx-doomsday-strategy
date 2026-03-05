# OKX末日战车策略 - 优化版 v2

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Strategy](https://img.shields.io/badge/Strategy-High%20Frequency%20Trading-orange)
![Status](https://img.shields.io/badge/Status-Testnet%20Verified-yellow)

## 🚀 项目概述

基于动量、成交量、RSI、多时间框架确认的ETH-USDT永续合约高频交易策略。集成6个优化点，包含完整的机器学习数据收集管道。

> ⚠️ **极端高风险警告**: 本策略为极高风险策略，可能几天内亏损50-100%本金。仅供学习和研究使用，实盘前务必充分测试。

## 📊 核心功能

### 🔧 6个优化点集成
1. **信号强度阈值调整** - 动态过滤低质量信号
2. **信号强度权重优化** - 8维度综合评分系统
3. **动态仓位分配** - 根据信号强度调整仓位大小
4. **多时间框架确认** - 5分钟主框架 + 1小时趋势过滤
5. **止损止盈优化** - 波动率和趋势自适应调整
6. **机器学习数据收集** - 完整的数据收集管道

### 🤖 机器学习集成
- 自动交易数据收集
- 特征提取和标签生成
- 为未来模型训练准备数据
- 支持xgboost、随机森林等模型

### 📈 技术指标
- 动量指标（5分钟周期）
- RSI（7周期）
- 成交量比率
- 布林带位置
- ATR波动率
- 多时间框架趋势

## 🏗️ 项目结构

```
okx-doomsday-strategy/
├── src/
│   ├── strategies/
│   │   ├── okx_doomsday_optimized_v2_ml_integrated.py  # 主策略文件
│   │   └── okx_doomsday_optimized_v2.py               # 原优化版策略
│   ├── utils/
│   │   ├── ml_data_collector.py                       # ML数据收集器
│   │   └── multi_timeframe_validation.py              # 多时间框架验证
│   └── config/
│       └── config_template.ini                        # 配置文件模板
├── tools/
│   ├── backtest_doomsday_optimized.py                 # 回测引擎
│   ├── parameter_tuning.py                            # 参数调优工具
│   └── quick_backtest_30d.py                          # 快速回测
├── docs/
│   └── strategy_documentation.md                      # 策略文档
├── tests/
│   └── test_strategy.py                               # 测试文件
├── requirements.txt                                    # 依赖包
├── README.md                                          # 本文件
├── .gitignore                                         # Git忽略文件
└── setup.py                                           # 安装脚本
```

## 🚀 快速开始

### 1. 安装依赖
```bash
# 克隆项目
git clone https://github.com/yourusername/okx-doomsday-strategy.git
cd okx-doomsday-strategy

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置API
```bash
# 复制配置文件模板
cp src/config/config_template.ini config.ini

# 编辑配置文件，填入您的OKX API信息
# 使用文本编辑器打开config.ini，填入：
# api_key = YOUR_API_KEY_HERE
# api_secret = YOUR_API_SECRET_HERE
# api_password = YOUR_API_PASSWORD_HERE
```

### 3. 运行策略
```bash
# 在测试网运行策略
python src/strategies/okx_doomsday_optimized_v2_ml_integrated.py --config config.ini

# 或者使用默认配置文件（如果已重命名为config.ini）
python src/strategies/okx_doomsday_optimized_v2_ml_integrated.py
```

## 📊 策略参数

### 核心参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| 时间框架 | 5m | 5分钟K线 |
| 杠杆 | 10x | 合约杠杆倍数 |
| 基础仓位 | 30% | 基础仓位大小 |
| 止损 | 5% | 单笔止损比例 |
| 止盈 | 9% | 单笔止盈比例 |
| 信号强度阈值 | 15分 | 信号过滤阈值 |

### 风控参数
- 每日最大交易次数：30次
- 每日最大亏损：25%
- 总最大亏损：40%
- 冷却时间：2分钟（连续亏损后）

### 优化参数
- 动态做空侧重：50%基准，根据舆情动态调整
- 多时间框架权重：30%
- 信号强度指数：1.5
- ML数据收集：启用

## 📈 性能表现

### 回测结果（30天模拟数据）
| 指标 | 数值 | 评价 |
|------|------|------|
| 总收益率 | +9.18% | ✅ 盈利 |
| 年化收益率 | 156% | 📊 基于外推 |
| 最大回撤 | -19.39% | ✅ 风险可控 |
| 夏普比率 | 0.13 | 📈 需提升 |
| 胜率 | 41.7% | 📊 接近目标 |
| 盈亏比 | 1.75:1 | 🎯 优秀 |
| 交易次数 | 38次 | ⚡ 合理 |

### 优化点效果
1. **信号过滤**：过滤率20-30%，信号质量提升
2. **多时间框架**：信号成功率提升1.1%
3. **动态仓位**：资金效率提升15-20%
4. **风险控制**：平均亏损降低0.94%

## 🔧 工具使用

### 回测验证
```bash
# 30天快速回测
python tools/quick_backtest_30d.py

# 完整回测（参数可调）
python tools/backtest_doomsday_optimized.py --days 90 --no-plot
```

### 参数调优
```bash
# 自动参数调优
python tools/parameter_tuning.py
```

### 多时间框架验证
```bash
# 验证1h趋势对5m信号的确认效果
python src/utils/multi_timeframe_validation.py
```

### ML数据收集测试
```bash
# 测试ML数据收集器
python src/utils/ml_data_collector.py
```

## 🤖 机器学习流程

### 数据收集阶段
1. **自动收集**：策略运行时自动记录交易数据
2. **特征提取**：从原始数据提取ML特征
3. **标签生成**：自动生成成功/质量标签
4. **数据存储**：保存到`ml_data/`目录

### 模型训练（未来扩展）
- 需要1000+交易样本
- 支持xgboost、随机森林等模型
- 自动特征重要性分析
- 定期重新训练

## ⚠️ 风险控制

### 内置风控机制
1. **仓位限制**：最大仓位30%，最小5%
2. **亏损控制**：每日/总亏损限制
3. **冷却机制**：连续亏损后暂停交易
4. **信号过滤**：多重条件过滤低质量信号

### 使用建议
1. **始终使用测试网**验证策略
2. **从小资金开始**，逐步增加
3. **监控日志**，及时发现问题
4. **定期检查**风控指标

## 📚 技术文档

### 信号生成逻辑
```
1. 获取5分钟OHLCV数据
2. 计算8个维度的技术指标
3. 生成原始交易信号
4. 计算信号强度（0-100分）
5. 多时间框架趋势确认
6. 动态概率过滤
7. 执行交易
```

### 8维度信号评分
1. **动量分数**（0-100）：价格动量强度
2. **成交量分数**（0-100）：成交量异常
3. **RSI分数**（0-100）：超买超卖状态
4. **趋势分数**（0-100）：多时间框架趋势
5. **布林带分数**（0-100）：价格在布林带位置
6. **波动率分数**（0-100）：ATR波动率
7. **多时间框架分数**（0-100）：高时间框架确认
8. **舆情分数**（0-100）：市场情绪指数

## 🔄 开发计划

### 已完成
- ✅ 基础策略框架
- ✅ 6个优化点集成
- ✅ ML数据收集管道
- ✅ 回测验证系统
- ✅ 参数调优工具

### 计划中
- 🔄 ML模型训练和集成
- 🔄 实时监控面板
- 🔄 更多交易所支持
- 🔄 社区贡献指南

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 支持与联系

如有问题或建议，请：
1. 查看 [Issues](https://github.com/yourusername/okx-doomsday-strategy/issues)
2. 提交新的Issue
3. 或通过其他方式联系

## ⚠️ 免责声明

本策略仅供学习和研究使用，不构成投资建议。加密货币交易风险极高，可能导致全部资金损失。使用者应自行承担风险，作者不对任何损失负责。

**永远不要投入你无法承受损失的资金！**

---

**Made with ❤️ for the crypto trading community**