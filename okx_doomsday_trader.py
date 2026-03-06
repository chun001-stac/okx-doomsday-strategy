#!/usr/bin/env python3
"""
OKX末日战车交易系统
极端激进策略，目标月利润50%+
支持合约交易，双向交易（多空），10倍杠杆

⚠️ 风险警告：
- 可能几天内亏损50-100%本金
- 仅适用于愿意承担极高风险的小资金
- 需要OKX合约交易权限

使用方法：
1. 配置config.ini中的API密钥
2. 运行：python okx_doomsday_trader.py
"""

import os
import sys
import time
import json
import logging
import configparser
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import ccxt
import talib
from dataclasses import dataclass
from enum import Enum


# ==================== 配置类 ====================
@dataclass
class Config:
    """交易配置"""
    # API配置
    api_key: str = ""
    api_secret: str = ""
    api_password: str = ""  # OKX需要passphrase
    
    # 交易对
    symbol: str = "ETH/USDT:USDT"  # USDT保证金合约
    base_currency: str = "ETH"
    quote_currency: str = "USDT"
    
    # 杠杆设置
    leverage: int = 10  # 10倍杠杆
    margin_mode: str = "isolated"  # 逐仓模式
    
    # 仓位管理
    position_size_pct: float = 0.25  # 25%仓位
    max_daily_trades: int = 20  # 每日最大交易次数
    max_daily_loss_pct: float = 0.30  # 每日最大亏损30%
    max_total_loss_pct: float = 0.50  # 总最大亏损50%
    
    # 策略参数
    timeframe: str = "5m"  # 5分钟K线
    momentum_period: int = 5  # 动量周期
    momentum_threshold_long: float = 0.008  # 做多动量阈值
    momentum_threshold_short: float = -0.008  # 做空动量阈值
    rsi_period: int = 7  # RSI周期
    rsi_overbought: int = 70  # 超买线
    rsi_oversold: int = 30  # 超卖线
    short_bias: float = 0.75  # 做空侧重75%
    
    # 止损止盈
    stoploss_pct: float = 0.25  # 25%止损
    takeprofit_pct: float = 0.30  # 30%止盈
    trailing_stop_pct: float = 0.08  # 移动止损8%
    
    # 系统设置
    vps_location: str = "HongKong"  # VPS位置
    check_interval: int = 60  # 检查间隔(秒)
    enable_trading: bool = True  # 是否启用交易
    test_mode: bool = False  # 测试模式（不实际下单）


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"


# ==================== 交易信号类 ====================
class DoomsdaySignalGenerator:
    """末日战车信号生成器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算交易信号
        返回包含信号的DataFrame
        """
        if len(df) < 100:
            self.logger.warning(f"数据不足，只有{len(df)}根K线，需要至少100根")
            df['signal'] = 'hold'
            df['signal_strength'] = 0
            return df
        
        try:
            # ========== 技术指标计算 ==========
            # 动量
            df['momentum'] = df['close'].pct_change(periods=self.config.momentum_period)
            df['momentum_3'] = df['close'].pct_change(periods=3)
            df['momentum_acc'] = df['momentum'].diff()
            
            # 成交量
            df['volume_ma'] = df['volume'].rolling(window=10).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            df['volume_spike'] = df['volume_ratio'] > 2.5
            
            # RSI
            df['rsi'] = talib.RSI(df['close'], timeperiod=self.config.rsi_period)
            
            # 布林带
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
                df['close'], timeperiod=15, nbdevup=2.0, nbdevdn=2.0
            )
            df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
            df['bb_position'] = df['bb_position'].clip(0, 1)
            
            # 突破信号
            df['high_15'] = df['high'].rolling(window=15).max()
            df['low_15'] = df['low'].rolling(window=15).min()
            
            # ATR波动率
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=10)
            df['atr_pct'] = df['atr'] / df['close']
            
            # 均线
            df['ma_fast'] = df['close'].rolling(window=7).mean()
            df['ma_slow'] = df['close'].rolling(window=21).mean()
            df['ma_trend'] = df['close'].rolling(window=50).mean()
            
            # ========== 做多信号 ==========
            # 强势突破做多
            df['long_breakout'] = (
                (df['close'] > df['high_15'].shift(1)) &
                (df['volume_ratio'] > 2.0) &
                (df['momentum'] > self.config.momentum_threshold_long) &
                (df['rsi'] > 40) &
                (df['rsi'] < 70)
            )
            
            # 超跌反弹做多
            df['long_reversal'] = (
                (df['rsi'] < self.config.rsi_oversold) &
                (df['rsi'] > df['rsi'].shift(1)) &
                (df['momentum'] > 0.002) &
                (df['bb_position'] < 0.2) &
                df['volume_spike']
            )
            
            # 趋势跟随做多
            df['long_trend'] = (
                (df['ma_fast'] > df['ma_slow']) &
                (df['ma_slow'] > df['ma_trend']) &
                (df['momentum'] > 0.005) &
                (df['close'] > df['ma_fast'])
            )
            
            # 综合做多信号
            df['long_signal'] = df['long_breakout'] | df['long_reversal'] | df['long_trend']
            
            # ========== 做空信号 ==========
            # 弱势突破做空
            df['short_breakout'] = (
                (df['close'] < df['low_15'].shift(1)) &
                (df['volume_ratio'] > 2.0) &
                (df['momentum'] < self.config.momentum_threshold_short) &
                (df['rsi'] > 30) &
                (df['rsi'] < 80)
            )
            
            # 超买回调做空
            df['short_reversal'] = (
                (df['rsi'] > self.config.rsi_overbought) &
                (df['rsi'] < df['rsi'].shift(1)) &
                (df['momentum'] < -0.002) &
                (df['bb_position'] > 0.8) &
                df['volume_spike']
            )
            
            # 趋势跟随做空
            df['short_trend'] = (
                (df['ma_fast'] < df['ma_slow']) &
                (df['ma_slow'] < df['ma_trend']) &
                (df['momentum'] < -0.005) &
                (df['close'] < df['ma_fast'])
            )
            
            # 综合做空信号
            df['short_signal'] = df['short_breakout'] | df['short_reversal'] | df['short_trend']
            
            # ========== 信号过滤 ==========
            # 避免高波动时交易
            df['volatility_high'] = df['atr_pct'] > df['atr_pct'].rolling(window=20).mean() * 1.5
            
            # 价格变化过大时暂停
            df['large_move'] = abs(df['momentum']) > 0.03
            
            # 有效信号条件
            valid_condition = (~df['volatility_high']) & (~df['large_move']) & (df['volume'] > 0)
            
            # ========== 最终信号生成 ==========
            df['signal'] = 'hold'
            df['signal_strength'] = 0
            
            # 做多信号
            long_condition = df['long_signal'] & valid_condition
            df.loc[long_condition, 'signal'] = 'long'
            df.loc[long_condition, 'signal_strength'] = 1
            
            # 做空信号（应用做空侧重）
            short_condition = df['short_signal'] & valid_condition
            
            # 随机过滤部分做空信号（如果做空侧重<1.0）
            if self.config.short_bias < 1.0:
                np.random.seed(int(time.time()) % 1000)
                random_filter = np.random.random(len(df)) < self.config.short_bias
                short_condition = short_condition & random_filter
            
            df.loc[short_condition, 'signal'] = 'short'
            df.loc[short_condition, 'signal_strength'] = -1
            
            # 信号强度计算
            df.loc[df['signal'] == 'long', 'signal_strength'] = self._calculate_signal_strength(df, 'long')
            df.loc[df['signal'] == 'short', 'signal_strength'] = self._calculate_signal_strength(df, 'short')
            
            self.logger.info(f"信号统计: 做多={df['long_signal'].sum()}, 做空={df['short_signal'].sum()}, "
                           f"最终信号: long={(df['signal']=='long').sum()}, short={(df['signal']=='short').sum()}")
            
        except Exception as e:
            self.logger.error(f"计算信号时出错: {e}", exc_info=True)
            df['signal'] = 'hold'
            df['signal_strength'] = 0
        
        return df
    
    def _calculate_signal_strength(self, df: pd.DataFrame, signal_type: str) -> float:
        """计算信号强度"""
        if signal_type == 'long':
            strength = (
                df['momentum'].abs() * 10 +
                df['volume_ratio'] * 0.5 +
                (df['rsi'] - 30) / 40 * 2  # RSI在30-70之间
            )
        else:  # short
            strength = (
                df['momentum'].abs() * 10 +
                df['volume_ratio'] * 0.5 +
                (70 - df['rsi']) / 40 * 2  # RSI在30-70之间
            )
        return strength.clip(0, 10)
    
    def get_current_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """获取最新信号"""
        if len(df) == 0:
            return 'hold', 0
        
        latest = df.iloc[-1]
        return latest['signal'], latest['signal_strength']


# ==================== OKX交易类 ====================
class OKXDoomsdayTrader:
    """OKX末日战车交易执行器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 初始化交易所连接
        self.exchange = self._init_exchange()
        
        # 状态变量
        self.position = None  # 当前持仓
        self.today_trades = 0  # 今日交易次数
        self.today_pnl = 0.0  # 今日盈亏
        self.total_pnl = 0.0  # 总盈亏
        self.last_trade_date = None  # 最后交易日期
        self.is_running = True
        
        # 信号生成器
        self.signal_generator = DoomsdaySignalGenerator(config)
        
        self.logger.info(f"OKX末日战车交易系统初始化完成")
        self.logger.info(f"交易对: {config.symbol}, 杠杆: {config.leverage}x, 仓位: {config.position_size_pct*100}%")
    
    def _init_exchange(self):
        """初始化OKX交易所连接"""
        exchange = ccxt.okx({
            'apiKey': self.config.api_key,
            'secret': self.config.api_secret,
            'password': self.config.api_password,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # 合约交易
            }
        })
        
        # 测试连接
        try:
            exchange.fetch_balance()
            self.logger.info("OKX连接成功")
        except Exception as e:
            self.logger.error(f"OKX连接失败: {e}")
            raise
        
        return exchange
    
    def set_leverage(self):
        """设置杠杆"""
        try:
            self.exchange.set_leverage(
                leverage=self.config.leverage,
                symbol=self.config.symbol
            )
            self.logger.info(f"设置杠杆: {self.config.leverage}x")
        except Exception as e:
            self.logger.error(f"设置杠杆失败: {e}")
    
    def fetch_ohlcv(self, limit: int = 100) -> pd.DataFrame:
        """获取K线数据"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                self.config.symbol,
                timeframe=self.config.timeframe,
                limit=limit
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
        except Exception as e:
            self.logger.error(f"获取K线数据失败: {e}")
            return pd.DataFrame()
    
    def fetch_position(self):
        """获取当前持仓"""
        try:
            positions = self.exchange.fetch_positions([self.config.symbol])
            for pos in positions:
                if pos['symbol'] == self.config.symbol.replace('/', '').replace(':', ''):
                    self.position = pos
                    break
        except Exception as e:
            self.logger.error(f"获取持仓失败: {e}")
            self.position = None
    
    def calculate_position_size(self) -> float:
        """计算仓位大小"""
        try:
            balance = self.exchange.fetch_balance()
            total_usdt = balance['USDT']['total']
            
            # 计算仓位金额
            position_value = total_usdt * self.config.position_size_pct
            
            # 获取当前价格
            ticker = self.exchange.fetch_ticker(self.config.symbol)
            current_price = ticker['last']
            
            # 计算合约数量
            contract_size = position_value * self.config.leverage / current_price
            
            self.logger.info(f"仓位计算: 总资金={total_usdt:.2f} USDT, "
                           f"仓位={position_value:.2f} USDT, "
                           f"合约数量={contract_size:.4f}")
            
            return contract_size
        except Exception as e:
            self.logger.error(f"计算仓位失败: {e}")
            return 0.0
    
    def place_order(self, side: str, order_type: str = 'market'):
        """下单"""
        if not self.config.enable_trading:
            self.logger.info(f"测试模式: 下单 {side} {order_type}")
            return None
        
        # 检查交易限制
        if not self._check_trade_limits():
            return None
        
        try:
            # 计算仓位
            amount = self.calculate_position_size()
            if amount <= 0:
                self.logger.error("仓位计算错误，不下单")
                return None
            
            # 下单参数
            params = {}
            if side in ['sell', 'short']:
                params['reduceOnly'] = False  # 开空仓
            
            # 下单
            order = self.exchange.create_order(
                symbol=self.config.symbol,
                type=order_type,
                side=side,
                amount=amount,
                params=params
            )
            
            self.logger.info(f"下单成功: {side} {amount:.4f} @ {order_type}, 订单ID: {order['id']}")
            
            # 更新交易统计
            self._update_trade_stats()
            
            return order
        except Exception as e:
            self.logger.error(f"下单失败: {e}")
            return None
    
    def close_position(self):
        """平仓"""
        if not self.position or abs(self.position['contracts']) < 0.001:
            self.logger.info("没有持仓，无需平仓")
            return
        
        try:
            side = 'sell' if self.position['side'] == 'long' else 'buy'
            amount = abs(self.position['contracts'])
            
            order = self.exchange.create_order(
                symbol=self.config.symbol,
                type='market',
                side=side,
                amount=amount,
                params={'reduceOnly': True}
            )
            
            self.logger.info(f"平仓成功: {side} {amount:.4f}, 订单ID: {order['id']}")
            self.position = None
            
        except Exception as e:
            self.logger.error(f"平仓失败: {e}")
    
    def _check_trade_limits(self) -> bool:
        """检查交易限制"""
        # 检查日期重置
        today = datetime.now().date()
        if self.last_trade_date != today:
            self.today_trades = 0
            self.today_pnl = 0.0
            self.last_trade_date = today
        
        # 检查每日交易次数
        if self.today_trades >= self.config.max_daily_trades:
            self.logger.warning(f"达到每日交易次数限制: {self.today_trades}/{self.config.max_daily_trades}")
            return False
        
        # 检查每日亏损限制
        if self.today_pnl <= -self.config.max_daily_loss_pct:
            self.logger.warning(f"达到每日亏损限制: {self.today_pnl:.2%}")
            return False
        
        # 检查总亏损限制
        if self.total_pnl <= -self.config.max_total_loss_pct:
            self.logger.error(f"达到总亏损限制: {self.total_pnl:.2%}，停止交易")
            self.is_running = False
            return False
        
        return True
    
    def _update_trade_stats(self):
        """更新交易统计"""
        self.today_trades += 1
        # 注意：实际盈亏需要从订单执行后获取
    
    def check_stop_loss(self, current_price: float) -> bool:
        """检查止损"""
        if not self.position:
            return False
        
        entry_price = self.position['entryPrice']
        side = self.position['side']
        
        if side == 'long':
            # 多头止损
            loss_pct = (current_price - entry_price) / entry_price
            if loss_pct <= -self.config.stoploss_pct:
                self.logger.warning(f"触发止损: 多头亏损{loss_pct:.2%}")
                return True
        else:
            # 空头止损
            loss_pct = (entry_price - current_price) / entry_price
            if loss_pct <= -self.config.stoploss_pct:
                self.logger.warning(f"触发止损: 空头亏损{loss_pct:.2%}")
                return True
        
        return False
    
    def check_take_profit(self, current_price: float) -> bool:
        """检查止盈"""
        if not self.position:
            return False
        
        entry_price = self.position['entryPrice']
        side = self.position['side']
        
        if side == 'long':
            # 多头止盈
            profit_pct = (current_price - entry_price) / entry_price
            if profit_pct >= self.config.takeprofit_pct:
                self.logger.info(f"触发止盈: 多头盈利{profit_pct:.2%}")
                return True
        else:
            # 空头止盈
            profit_pct = (entry_price - current_price) / entry_price
            if profit_pct >= self.config.takeprofit_pct:
                self.logger.info(f"触发止盈: 空头盈利{profit_pct:.2%}")
                return True
        
        return False
    
    def run(self):
        """主运行循环"""
        self.logger.info("开始运行末日战车交易系统")
        
        # 设置杠杆
        self.set_leverage()
        
        while self.is_running:
            try:
                # 获取当前时间
                now = datetime.now()
                
                # 获取数据
                df = self.fetch_ohlcv(limit=150)
                if len(df) < 100:
                    self.logger.warning("数据不足，等待下次循环")
                    time.sleep(self.config.check_interval)
                    continue
                
                # 计算信号
                df = self.signal_generator.calculate_signals(df)
                current_signal, signal_strength = self.signal_generator.get_current_signal(df)
                
                # 获取当前持仓
                self.fetch_position()
                
                # 获取当前价格
                ticker = self.exchange.fetch_ticker(self.config.symbol)
                current_price = ticker['last']
                
                # 检查止损止盈
                if self.position:
                    if self.check_stop_loss(current_price) or self.check_take_profit(current_price):
                        self.close_position()
                        time.sleep(5)  # 等待平仓完成
                        continue
                
                # 根据信号执行交易
                if current_signal == 'long':
                    if not self.position or self.position['side'] != 'long':
                        self.logger.info(f"做多信号，强度: {signal_strength:.2f}")
                        if self.position:  # 如果有反向持仓，先平仓
                            self.close_position()
                            time.sleep(5)
                        self.place_order('buy')
                
                elif current_signal == 'short':
                    if not self.position or self.position['side'] != 'short':
                        self.logger.info(f"做空信号，强度: {signal_strength:.2f}")
                        if self.position:  # 如果有反向持仓，先平仓
                            self.close_position()
                            time.sleep(5)
                        self.place_order('sell')
                
                else:
                    # hold信号，维持现状
                    pass
                
                # 记录状态
                self._log_status(current_signal, signal_strength)
                
                # 等待下次检查
                time.sleep(self.config.check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("用户中断，停止交易")
                break
            except Exception as e:
                self.logger.error(f"运行错误: {e}", exc_info=True)
                time.sleep(self.config.check_interval)
        
        # 清理：平掉所有持仓
        self.logger.info("停止交易，清理持仓")
        self.close_position()
    
    def _log_status(self, signal: str, strength: float):
        """记录状态"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'signal': signal,
            'signal_strength': strength,
            'position': self.position['side'] if self.position else 'none',
            'today_trades': self.today_trades,
            'today_pnl': self.today_pnl,
            'total_pnl': self.total_pnl
        }
        self.logger.info(f"状态: {json.dumps(status, default=str)}")


# ==================== 配置文件管理 ====================
def load_config(config_file: str = 'config.ini') -> Config:
    """加载配置文件"""
    config = Config()
    
    if not os.path.exists(config_file):
        # 创建默认配置文件
        create_default_config(config_file)
        print(f"已创建默认配置文件: {config_file}")
        print("请修改config.ini中的API密钥和参数后重新运行")
        sys.exit(0)
    
    parser = configparser.ConfigParser()
    parser.read(config_file)
    
    # 加载API配置
    if 'OKX' in parser:
        config.api_key = parser['OKX'].get('api_key', '')
        config.api_secret = parser['OKX'].get('api_secret', '')
        config.api_password = parser['OKX'].get('api_password', '')
    
    # 加载交易参数
    if 'Trading' in parser:
        config.symbol = parser['Trading'].get('symbol', config.symbol)
        config.leverage = parser['Trading'].getint('leverage', config.leverage)
        config.position_size_pct = parser['Trading'].getfloat('position_size_pct', config.position_size_pct)
        config.max_daily_trades = parser['Trading'].getint('max_daily_trades', config.max_daily_trades)
        config.max_daily_loss_pct = parser['Trading'].getfloat('max_daily_loss_pct', config.max_daily_loss_pct)
        config.max_total_loss_pct = parser['Trading'].getfloat('max_total_loss_pct', config.max_total_loss_pct)
    
    # 加载策略参数
    if 'Strategy' in parser:
        config.timeframe = parser['Strategy'].get('timeframe', config.timeframe)
        config.momentum_period = parser['Strategy'].getint('momentum_period', config.momentum_period)
        config.momentum_threshold_long = parser['Strategy'].getfloat('momentum_threshold_long', config.momentum_threshold_long)
        config.momentum_threshold_short = parser['Strategy'].getfloat('momentum_threshold_short', config.momentum_threshold_short)
        config.rsi_period = parser['Strategy'].getint('rsi_period', config.rsi_period)
        config.rsi_overbought = parser['Strategy'].getint('rsi_overbought', config.rsi_overbought)
        config.rsi_oversold = parser['Strategy'].getint('rsi_oversold', config.rsi_oversold)
        config.short_bias = parser['Strategy'].getfloat('short_bias', config.short_bias)
    
    # 加载风险参数
    if 'Risk' in parser:
        config.stoploss_pct = parser['Risk'].getfloat('stoploss_pct', config.stoploss_pct)
        config.takeprofit_pct = parser['Risk'].getfloat('takeprofit_pct', config.takeprofit_pct)
        config.trailing_stop_pct = parser['Risk'].getfloat('trailing_stop_pct', config.trailing_stop_pct)
    
    # 加载系统设置
    if 'System' in parser:
        config.vps_location = parser['System'].get('vps_location', config.vps_location)
        config.check_interval = parser['System'].getint('check_interval', config.check_interval)
        config.enable_trading = parser['System'].getboolean('enable_trading', config.enable_trading)
        config.test_mode = parser['System'].getboolean('test_mode', config.test_mode)
    
    return config


def create_default_config(config_file: str):
    """创建默认配置文件"""
    config = configparser.ConfigParser()
    
    # OKX API配置
    config['OKX'] = {
        '# 从OKX网站获取API密钥': '',
        '# 权限需要：交易、合约交易': '',
        'api_key': 'YOUR_API_KEY_HERE',
        'api_secret': 'YOUR_API_SECRET_HERE',
        'api_password': 'YOUR_API_PASSWORD_HERE',
    }
    
    # 交易参数
    config['Trading'] = {
        '# 交易对': '',
        'symbol': 'ETH/USDT:USDT',
        '# 杠杆倍数 (建议5-10)': '',
        'leverage': '10',
        '# 仓位比例 (建议0.15-0.25)': '',
        'position_size_pct': '0.25',
        '# 每日最大交易次数': '',
        'max_daily_trades': '20',
        '# 每日最大亏损比例': '',
        'max_daily_loss_pct': '0.30',
        '# 总最大亏损比例': '',
        'max_total_loss_pct': '0.50',
    }
    
    # 策略参数
    config['Strategy'] = {
        '# K线时间框架': '',
        'timeframe': '5m',
        '# 动量指标周期': '',
        'momentum_period': '5',
        '# 做多动量阈值': '',
        'momentum_threshold_long': '0.008',
        '# 做空动量阈值': '',
        'momentum_threshold_short': '-0.008',
        '# RSI周期': '',
        'rsi_period': '7',
        '# RSI超买线': '',
        'rsi_overbought': '70',
        '# RSI超卖线': '',
        'rsi_oversold': '30',
        '# 做空侧重 (0.6-0.9)': '',
        'short_bias': '0.75',
    }
    
    # 风险参数
    config['Risk'] = {
        '# 止损比例': '',
        'stoploss_pct': '0.25',
        '# 止盈比例': '',
        'takeprofit_pct': '0.30',
        '# 移动止损比例': '',
        'trailing_stop_pct': '0.08',
    }
    
    # 系统设置
    config['System'] = {
        '# VPS位置': '',
        'vps_location': 'HongKong',
        '# 检查间隔(秒)': '',
        'check_interval': '60',
        '# 是否启用交易': '',
        'enable_trading': 'true',
        '# 测试模式(不下单)': '',
        'test_mode': 'false',
    }
    
    with open(config_file, 'w') as f:
        config.write(f)


# ==================== 日志设置 ====================
def setup_logging():
    """设置日志"""
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f'doomsday_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


# ==================== 主函数 ====================
def main():
    """主函数"""
    print("=" * 60)
    print("OKX末日战车交易系统")
    print("极端激进策略 - 目标月利润50%+")
    print("⚠️  高风险警告：可能几天内亏损50-100%本金")
    print("=" * 60)
    
    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 加载配置
    config = load_config()
    
    # 验证API密钥
    if config.api_key == 'YOUR_API_KEY_HERE' or not config.api_key:
        logger.error("请先在config.ini中配置OKX API密钥")
        sys.exit(1)
    
    # 创建交易系统
    try:
        trader = OKXDoomsdayTrader(config)
        
        # 显示确认信息
        print("\n配置确认:")
        print(f"  交易对: {config.symbol}")
        print(f"  杠杆: {config.leverage}x")
        print(f"  仓位: {config.position_size_pct*100}%")
        print(f"  做空侧重: {config.short_bias*100}%")
        print(f"  启用交易: {config.enable_trading}")
        print(f"  测试模式: {config.test_mode}")
        
        if config.enable_trading and not config.test_mode:
            print("\n⚠️  ⚠️  ⚠️  警告：实盘交易模式已启用！")
            print("   将会进行真实交易，可能造成资金损失！")
            confirm = input("\n确认开始实盘交易？(输入 YES 确认): ")
            if confirm != 'YES':
                print("已取消")
                sys.exit(0)
        
        # 运行交易系统
        print(f"\n开始运行... 日志文件: logs/doomsday_*.log")
        trader.run()
        
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()