# OKX末日战车交易系统

## ⚠️ 极端风险警告
- **可能几天内亏损50-100%本金**
- **仅适用于愿意承担极高风险的小资金**
- **必须做好全部亏光的心理准备**
- **建议初始资金：100-500 USDT（亏光不影响生活）**

## 🎯 策略目标
- **月利润目标**：50%+
- **交易频率**：每日10-20次
- **杠杆倍数**：10倍
- **仓位大小**：25%本金/次
- **侧重方向**：75%做空（熊市优化）

## 📋 系统要求

### 硬件要求
- **VPS服务器**（推荐）：香港/新加坡节点，<50ms延迟
- **或本地电脑**：需要24小时开机，稳定网络
- **内存**：至少2GB
- **硬盘**：至少10GB空间

### 软件要求
- **Python 3.8+**
- **pip包管理工具**
- **Git（可选）**

## 🚀 快速开始

### 步骤1：环境准备

```bash
# 1. 安装Python依赖
pip install ccxt pandas numpy ta-lib

# 2. 安装TA-Lib（需要编译）
# Ubuntu/Debian:
sudo apt-get update
sudo apt-get install build-essential
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib
./configure --prefix=/usr
make
sudo make install

# 或使用pip安装（可能不包含所有功能）
pip install TA-Lib

# 3. 下载策略代码
# 如果通过Git下载
git clone [代码仓库地址]
cd okx_doomsday_trader
```

### 步骤2：获取OKX API密钥

1. **登录OKX**：访问 https://www.okx.com
2. **进入API管理**：右上角头像 → API
3. **创建API密钥**：
   - 名称：`DoomsdayTrader`
   - **权限设置**：
     - ✅ 读取
     - ✅ 交易
     - ✅ 合约交易
     - ❌ 提现（绝对不能开启！）
   - 交易密码：输入你的OKX交易密码
   - IP绑定：建议绑定VPS IP（可选）
4. **保存API信息**：
   - API Key
   - Secret Key
   - Passphrase（交易密码）

### 步骤3：配置系统

1. **修改配置文件** `config.ini`：
```ini
[OKX]
api_key = 你的API_KEY
api_secret = 你的API_SECRET
api_password = 你的API_PASSWORD

[Trading]
# 新手建议从保守参数开始
leverage = 5          # 5倍杠杆
position_size_pct = 0.15  # 15%仓位
enable_trading = false  # 先设为false测试
test_mode = true      # 测试模式
```

### 步骤4：测试运行

```bash
# 1. 测试API连接
python test_okx_connection.py

# 2. 测试信号生成
python test_signal_generator.py

# 3. 运行测试模式（不下单）
python okx_doomsday_trader.py
```

检查`logs/`目录下的日志文件，确认系统正常运行。

### 步骤5：模拟盘测试

1. 在OKX创建一个**模拟交易账户**
2. 获取模拟账户的API密钥
3. 修改`config.ini`使用模拟账户API
4. 运行系统测试24小时
5. 分析日志，评估信号质量

### 步骤6：极小实盘（100 USDT）

1. **存入100 USDT**到OKX合约账户
2. 修改`config.ini`：
```ini
[Trading]
leverage = 5
position_size_pct = 0.10  # 10%仓位
enable_trading = true
test_mode = false

[Risk]
max_daily_loss_pct = 0.20  # 每日最大亏损20%
max_total_loss_pct = 0.40  # 总最大亏损40%
```
3. **运行系统**：
```bash
nohup python okx_doomsday_trader.py > trader.log 2>&1 &
```
4. **监控运行**：
```bash
tail -f logs/doomsday_*.log
```

## ⚙️ 参数说明

### 保守参数（新手推荐）
```ini
leverage = 5
position_size_pct = 0.15
stoploss_pct = 0.20
takeprofit_pct = 0.25
max_daily_loss_pct = 0.20
```

### 激进参数（经验者）
```ini
leverage = 10
position_size_pct = 0.25
stoploss_pct = 0.25
takeprofit_pct = 0.30
max_daily_loss_pct = 0.30
```

### 极端参数（高风险）
```ini
leverage = 15
position_size_pct = 0.30
stoploss_pct = 0.30
takeprofit_pct = 0.40
max_daily_loss_pct = 0.40
```

## 📊 风险管理

### 硬性止损规则
1. **单日亏损20-30%** → 当日停止交易
2. **总亏损40-50%** → 永久停止策略
3. **保证金率<20%** → 强制减仓
4. **连续亏损5次** → 暂停1天复盘

### 资金管理建议
1. **准备3份本金**（如100×3=300 USDT）
2. **第1份**：测试验证（可能亏光）
3. **第2份**：优化后使用（目标回本）
4. **第3份**：稳定后扩大（目标盈利）

## 🛠️ 系统架构

```
okx_doomsday_trader.py    # 主程序
├── Config                 # 配置管理
├── DoomsdaySignalGenerator # 信号生成
├── OKXDoomsdayTrader      # 交易执行
└── 日志系统
```

### 信号逻辑
1. **做多信号**：
   - 强势突破 + 成交量确认
   - 超跌反弹 + RSI背离
   - 趋势跟随 + 动量确认

2. **做空信号（侧重）**：
   - 弱势突破 + 成交量确认
   - 超买回调 + RSI背离
   - 趋势跟随 + 动量确认

## 📈 绩效评估

### 每日检查
1. **胜率**：应>30%
2. **盈亏比**：应>1.2
3. **夏普比率**：应>1.0
4. **最大回撤**：应<30%

### 每周优化
1. 分析信号质量
2. 调整参数
3. 优化过滤条件
4. 评估市场适应性

## 🔧 故障排除

### 常见问题

**Q: API连接失败**
```
检查：1. API密钥是否正确 2. 网络连接 3. IP绑定
```

**Q: 无法下单**
```
检查：1. 合约账户余额 2. 杠杆设置 3. 交易权限
```

**Q: 信号质量差**
```
调整：1. 动量阈值 2. RSI参数 3. 做空侧重
```

**Q: 延迟过高**
```
解决：1. 使用VPS 2. 简化信号计算 3. 增加检查间隔
```

### 日志分析
```bash
# 查看错误日志
grep -i error logs/doomsday_*.log

# 查看交易记录
grep -i "下单\|平仓" logs/doomsday_*.log

# 查看信号统计
grep -i "信号统计" logs/doomsday_*.log
```

## 📞 紧急停止

### 手动停止
```bash
# 1. 找到进程ID
ps aux | grep okx_doomsday_trader

# 2. 停止进程
kill [进程ID]

# 3. 强制平仓
python emergency_close.py
```

### 自动保护
- 达到亏损限额自动停止
- 网络断开自动停止
- 系统异常自动停止

## 📚 学习资源

### 必读知识
1. **合约交易基础**：杠杆、保证金、强平
2. **技术分析**：RSI、动量、布林带
3. **风险管理**：仓位管理、止损策略

### 推荐工具
1. **监控工具**：Grafana, Prometheus
2. **回测工具**：Backtrader, Zipline
3. **数据分析**：Jupyter, Pandas

## ⚖️ 免责声明

1. 本策略为高风险策略，可能造成重大资金损失
2. 使用者需自行承担所有交易风险
3. 作者不对任何资金损失负责
4. 仅适用于能够承受全部本金损失的资金

## 🚨 最后警告

**再次强调：**
- 可能几天内亏损50-100%本金
- 从小资金开始（100 USDT）
- 做好全部亏光的心理准备
- 严格遵守风险管理规则

**如果无法承受以上风险，请勿使用本系统！**

---

**开始即表示你已充分了解并接受所有风险。**