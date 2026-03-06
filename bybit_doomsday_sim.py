#!/usr/bin/env python3
"""
Bybit末日战车模拟交易系统
在Bybit模拟环境中测试完整策略（做空+杠杆+双向交易）
"""

import os
import sys
import time
import json
import logging
import configparser
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import pandas as pd
import numpy as np
import ccxt
import talib
from dataclasses import dataclass
import random


# ==================== 配置类 ====================
@dataclass
class Config:
    """交易配置"""
    # Bybit API配置
    api_key: str = ""
    api_secret: str = ""
    
    # 交易对
    symbol: str = "ETH/USDT:USDT"  # Bybit永续合约
    base_currency: str = "ETH"
    quote_currency: str = "USDT"
    
    # 杠杆设置
    leverage: int = 10  # 10倍杠杆
    margin_mode: str = "isolated"  # 逐仓模式
    
    # 仓位管理（模拟测试用保守参数）
    position_size_pct: float = 0.15  # 15%仓位
    max_daily_trades: int = 10  # 每日最大10次交易
    max_daily_loss_pct: float = 0.20  # 每日最大亏损20%
    max_total_loss_pct: float = 0.40  # 总最大亏损40%
    
    # 策略参数
    timeframe: str = "5m"  # 5分钟K线
    momentum_period: int = 5
    momentum_threshold_long: float = 0.008  # 做多动量阈值
    momentum_threshold_short: float = -0.008  # 做空动量阈值
    rsi_period: int = 7
    rsi_overbought: int = 70
    rsi_oversold: int = 30
    short_bias: float = 0.75  # 75%做空侧重
    
    # 止损止盈
    stoploss_pct: float = 0.25  # 25%止损
    takeprofit_pct: float = 0.30  # 30%止盈
    
    # 系统设置
    check_interval: int = 60  # 检查间隔(秒)
    enable_trading: bool = True  # 启用交易
    testnet: bool = True  # 使用测试网


# ==================== 信号生成器 ====================
class SignalGenerator:
    """末日战车信号生成器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算交易信号"""
        if len(df) < 100:
            df['signal'] = 'hold'
            df['signal_strength'] = 0
            return df
        
        try:
            # ========== 技术指标 ==========
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
            df['long_signal_raw'] = df['long_breakout'] | df['long_reversal'] | df['long_trend']
            
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
            df['short_signal_raw'] = df['short_breakout'] | df['short_reversal'] | df['short_trend']
            
            # ========== 信号过滤 ==========
            # 避免高波动时交易
            df['volatility_high'] = df['atr_pct'] > df['atr_pct'].rolling(window=20).mean() * 1.5
            df['large_move'] = abs(df['momentum']) > 0.03
            
            # 有效条件
            valid_condition = (~df['volatility_high']) & (~df['large_move']) & (df['volume'] > 0)
            
            # 应用做空侧重：随机过滤部分做多信号
            np.random.seed(int(time.time()) % 1000)
            random_filter = np.random.random(len(df)) < self.config.short_bias
            
            # 最终信号
            df['signal'] = 'hold'
            df['signal_strength'] = 0
            
            # 做多信号（应用过滤）
            long_condition = df['long_signal_raw'] & valid_condition & (~random_filter)
            df.loc[long_condition, 'signal'] = 'long'
            df.loc[long_condition, 'signal_strength'] = 1
            
            # 做空信号
            short_condition = df['short_signal_raw'] & valid_condition
            df.loc[short_condition, 'signal'] = 'short'
            df.loc[short_condition, 'signal_strength'] = -1
            
            # 信号强度计算
            df.loc[df['signal'] == 'long', 'signal_strength'] = self._calculate_strength(df, 'long')
            df.loc[df['signal'] == 'short', 'signal_strength'] = self._calculate_strength(df, 'short')
            
            # 统计
            long_count = (df['signal'] == 'long').sum()
            short_count = (df['signal'] == 'short').sum()
            self.logger.info(f"信号统计: long={long_count}, short={short_count}, hold={len(df)-long_count-short_count}")
            
        except Exception as e:
            self.logger.error(f"计算信号失败: {e}")
            df['signal'] = 'hold'
            df['signal_strength'] = 0
        
        return df
    
    def _calculate_strength(self, df: pd.DataFrame, signal_type: str) -> float:
        """计算信号强度"""
        if signal_type == 'long':
            strength = (
                df['momentum'].abs() * 10 +
                df['volume_ratio'] * 0.5 +
                (df['rsi'] - 30) / 40 * 2
            )
        else:  # short
            strength = (
                df['momentum'].abs() * 10 +
                df['volume_ratio'] * 0.5 +
                (70 - df['rsi']) / 40 * 2
            )
        return strength.clip(0, 10)
    
    def get_current_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """获取最新信号"""
        if len(df) == 0:
            return 'hold', 0
        latest = df.iloc[-1]
        return latest['signal'], latest['signal_strength']


# ==================== Bybit交易器 ====================
class BybitDoomsdayTrader:
    """Bybit末日战车交易执行器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 初始化交易所
        self.exchange = self._init_exchange()
        
        # 状态变量
        self.position = None
        self.today_trades = 0
        self.today_pnl = 0.0
        self.total_pnl = 0.0
        self.last_trade_date = None
        self.is_running = True
        
        # 信号生成器
        self.signal_generator = SignalGenerator(config)
        
        # 交易统计
        self.long_trades = 0
        self.short_trades = 0
        self.long_wins = 0
        self.short_wins = 0
        
        self.logger.info("Bybit末日战车模拟交易系统初始化完成")
        self.logger.info(f"交易对: {config.symbol}, 杠杆: {config.leverage}x, 仓位: {config.position_size_pct*100}%")
        self.logger.info(f"做空侧重: {config.short_bias*100}%, 测试网: {config.testnet}")
    
    def _init_exchange(self):
        """初始化Bybit交易所"""
        exchange_config = {
            'apiKey': self.config.api_key,
            'secret': self.config.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'contract',  # 合约交易
                'test': self.config.testnet,  # 测试网
            }
        }
        
        exchange = ccxt.bybit(exchange_config)
        
        # 测试连接
        try:
            exchange.fetch_balance()
            self.logger.info("Bybit连接成功")
        except Exception as e:
            self.logger.error(f"Bybit连接失败: {e}")
            raise
        
        return exchange
    
    def set_leverage(self):
        """设置杠杆"""
        try:
            # Bybit设置杠杆的方式
            self.exchange.set_leverage(
                leverage=self.config.leverage,
                symbol=self.config.symbol
            )
            self.logger.info(f"设置杠杆: {self.config.leverage}x")
        except Exception as e:
            self.logger.warning(f"设置杠杆失败（可能已设置）: {e}")
    
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
            self.logger.error(f"获取K线失败: {e}")
            return pd.DataFrame()
    
    def fetch_position(self):
        """获取当前持仓"""
        try:
            positions = self.exchange.fetch_positions([self.config.symbol])
            for pos in positions:
                if pos['symbol'] == self.config.symbol.replace('/', '').replace(':', ''):
                    if abs(pos.get('contracts', 0)) > 0.001:
                        self.position = pos
                        return
            self.position = None  # 无持仓
        except Exception as e:
            self.logger.error(f"获取持仓失败: {e}")
            self.position = None
    
    def calculate_position_size(self) -> float:
        """计算仓位大小"""
        try:
            # 获取余额
            balance = self.exchange.fetch_balance()
            
            # Bybit余额结构
            if 'USDT' in balance.get('total', {}):
                total_usdt = balance['total']['USDT']
            else:
                # 尝试其他方式
                total_usdt = balance.get('USDT', {}).get('total', 10000)  # 模拟账户默认10000
            
            # 计算仓位金额
            position_value = total_usdt * self.config.position_size_pct
            
            # 获取当前价格
            ticker = self.exchange.fetch_ticker(self.config.symbol)
            current_price = ticker['last']
            
            # 计算合约数量（考虑杠杆）
            contract_size = position_value * self.config.leverage / current_price
            
            self.logger.info(f"仓位计算: 总资金≈{total_usdt:.0f} USDT, 仓位={position_value:.2f} USDT, 合约={contract_size:.4f}")
            
            return contract_size
        except Exception as e:
            self.logger.error(f"计算仓位失败: {e}")
            return 0.01  # 最小仓位
    
    def place_order(self, side: str):
        """下单"""
        if not self.config.enable_trading:
            self.logger.info(f"模拟模式: 下单 {side}")
            return None
        
        # 检查交易限制
        if not self._check_trade_limits():
            return None
        
        try:
            # 计算仓位
            amount = self.calculate_position_size()
            if amount <= 0.001:  # 太小不下单
                self.logger.warning("仓位太小，不下单")
                return None
            
            # Bybit下单参数
            params = {}
            order_type = 'market'  # 市价单
            
            # 下单
            order = self.exchange.create_order(
                symbol=self.config.symbol,
                type=order_type,
                side=side,
                amount=amount,
                params=params
            )
            
            self.logger.info(f"下单成功: {side} {amount:.4f}, 订单ID: {order.get('id', 'N/A')}")
            
            # 更新统计
            self._update_trade_stats(side)
            
            return order
        except Exception as e:
            self.logger.error(f"下单失败: {e}")
            return None
    
    def close_position(self):
        """平仓"""
        if not self.position or abs(self.position.get('contracts', 0)) < 0.001:
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
            
            self.logger.info(f"平仓成功: {side} {amount:.4f}, 订单ID: {order.get('id', 'N/A')}")
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
        
        # 每日交易次数限制
        if self.today_trades >= self.config.max_daily_trades:
            self.logger.warning(f"达到每日交易次数限制: {self.today_trades}/{self.config.max_daily_trades}")
            return False
        
        # 每日亏损限制
        if self.today_pnl <= -self.config.max_daily_loss_pct:
            self.logger.warning(f"达到每日亏损限制: {self.today_pnl:.2%}")
            return False
        
        # 总亏损限制
        if self.total_pnl <= -self.config.max_total_loss_pct:
            self.logger.error(f"达到总亏损限制: {self.total_pnl:.2%}，停止交易")
            self.is_running = False
            return False
        
        return True
    
    def _update_trade_stats(self, side: str):
        """更新交易统计"""
        self.today_trades += 1
        if side == 'buy':
            self.long_trades += 1
        else:
            self.short_trades += 1
    
    def check_stop_loss_take_profit(self, current_price: float) -> Tuple[bool, bool]:
        """检查止损止盈"""
        if not self.position:
            return False, False
        
        entry_price = self.position['entryPrice']
        side = self.position['side']
        
        if side == 'long':
            # 多头
            profit_pct = (current_price - entry_price) / entry_price
            stop_loss = profit_pct <= -self.config.stoploss_pct
            take_profit = profit_pct >= self.config.takeprofit_pct
        else:
            # 空头
            profit_pct = (entry_price - current_price) / entry_price
            stop_loss = profit_pct <= -self.config.stoploss_pct
            take_profit = profit_pct >= self.config.takeprofit_pct
        
        if stop_loss:
            self.logger.warning(f"触发止损: {side} 亏损{profit_pct:.2%}")
        if take_profit:
            self.logger.info(f"触发止盈: {side} 盈利{profit_pct:.2%}")
        
        return stop_loss, take_profit
    
    def run(self):
        """主运行循环"""
        self.logger.info("开始运行末日战车模拟交易")
        
        # 设置杠杆
        self.set_leverage()
        
        while self.is_running:
            try:
                # 获取数据
                df = self.fetch_ohlcv(limit=150)
                if len(df) < 100:
                    self.logger.warning("数据不足，等待...")
                    time.sleep(self.config.check_interval)
                    continue
                
                # 计算信号
                df = self.signal_generator.calculate_signals(df)
                current_signal, signal_strength = self.signal_generator.get_current_signal(df)
                
                # 获取持仓
                self.fetch_position()
                
                # 获取当前价格
                ticker = self.exchange.fetch_ticker(self.config.symbol)
                current_price = ticker['last']
                
                # 检查止损止盈
                if self.position:
                    stop_loss, take_profit = self.check_stop_loss_take_profit(current_price)
                    if stop_loss or take_profit:
                        self.close_position()
                        time.sleep(2)
                        continue
                
                # 根据信号执行交易
                if current_signal == 'long':
                    if not self.position or self.position['side'] != 'long':
                        self.logger.info(f"做多信号，强度: {signal_strength:.2f}")
                        if self.position:  # 有反向持仓，先平仓
                            self.close_position()
                            time.sleep(2)
                        self.place_order('buy')
                
                elif current_signal == 'short':
                    if not self.position or self.position['side'] != 'short':
                        self.logger.info(f"做空信号，强度: {signal_strength:.2f}")
                        if self.position:  # 有反向持仓，先平仓
                            self.close_position()
                            time.sleep(2)
                        self.place_order('sell')
                
                # 记录状态
                self._log_status(current_signal, signal_strength)
                
                # 等待下次检查
                time.sleep(self.config.check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("用户中断，停止交易")
                break
            except Exception as e:
                self.logger.error(f"运行错误: {e}")
                time.sleep(self.config.check_interval)
        
        # 清理
        self.logger.info("停止交易，清理持仓")
        self.close_position()
        
        # 输出统计
        self._print_statistics()
    
    def _log_status(self, signal: str, strength: float):
        """记录状态"""
        status = {
            'time': datetime.now().strftime('%H:%M:%S'),
            'signal': signal,
            'strength': strength,
            'position': self.position['side'] if self.position else 'none',
            'today_trades': self.today_trades,
            'long_trades': self.long_trades,
            'short_trades': self.short_trades,
            'today_pnl': f"{self.today_pnl:.2%}",
            'total_pnl': f"{self.total_pnl:.2%}"
        }
        self.logger.info(f"状态: {json.dumps(status)}")
    
    def _print_statistics(self):
        """输出统计信息"""
        print("\n" + "="*60)
        print("末日战车模拟交易统计")
        print("="*60)
        print(f"做多交易次数: {self.long_trades}")
        print(f"做空交易次数: {self.short_trades}")
        print(f"做空交易占比: {self.short_trades/(self.long_trades+self.short_trades)*100:.1f}%")
        print(f"今日交易次数: {self.today_trades}")
        print(f"今日盈亏: {self.today_pnl:.2%}")
        print(f"总盈亏: {self.total_pnl:.2%}")
        print("="*60)


# ==================== 配置加载 ====================
def load_config() -> Config:
    """加载配置文件"""
    config = Config()
    
    config_file = 'config.ini'
    if not os.path.exists(config_file):
        print(f"配置文件 {config_file} 不存在")
        print("请先创建config.ini并配置Bybit API")
        sys.exit(1)
    
    try:
        parser = configparser.ConfigParser()
        parser.read(config_file)
        
        # Bybit配置
        if 'Bybit' in parser:
            config.api_key = parser['Bybit'].get('api_key', '')
            config.api_secret = parser['Bybit'].get('api_secret', '')
        
        # 交易参数
        if 'Trading' in parser:
            config.symbol = parser['Trading'].get('symbol', config.symbol)
            config.leverage = parser['Trading'].getint('leverage', config.leverage)
            config.position_size_pct = parser['Trading'].getfloat('position_size_pct', config.position_size_pct)
            config.max_daily_trades = parser['Trading'].getint('max_daily_trades', config.max_daily_trades)
            config.max_daily_loss_pct = parser['Trading'].getfloat('max_daily_loss_pct', config.max_daily_loss_pct)
            config.max_total_loss_pct = parser['Trading'].getfloat('max_total_loss_pct', config.max_total_loss_pct)
        
        # 策略参数
        if 'Strategy' in parser:
            config.timeframe = parser['Strategy'].get('timeframe', config.timeframe)
            config.momentum_period = parser['Strategy'].getint('momentum_period', config.momentum_period)
            config.momentum_threshold_long = parser['Strategy'].getfloat('momentum_threshold_long', config.momentum_threshold_long)
            config.momentum_threshold_short = parser['Strategy'].getfloat('momentum_threshold_short', config.momentum_threshold_short)
            config.rsi_period = parser['Strategy'].getint('rsi_period', config.rsi_period)
            config.rsi_overbought = parser['Strategy'].getint('rsi_overbought', config.rsi_overbought)
            config.rsi_oversold = parser['Strategy'].getint('rsi_oversold', config.rsi_oversold)
            config.short_bias = parser['Strategy'].getfloat('short_bias', config.short_bias)
        
        # 风险参数
        if 'Risk' in parser:
            config.stoploss_pct = parser['Risk'].getfloat('stoploss_pct', config.stoploss_pct)
            config.takeprofit_pct = parser['Risk'].getfloat('takeprofit_pct', config.takeprofit_pct)
        
        # 系统设置
        if 'System' in parser:
            config.check_interval = parser['System'].getint('check_interval', config.check_interval)
            config.enable_trading = parser['System'].getboolean('enable_trading', config.enable_trading)
        
    except Exception as e:
        print(f"读取配置失败: {e}")
    
    return config


# ==================== 日志设置 ====================
def setup_logging():
    """设置日志"""
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f'bybit_doomsday_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
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
    print("Bybit末日战车模拟交易系统")
    print("零风险测试完整策略（做空+杠杆+双向交易）")
    print("=" * 60)
    
    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 加载配置
    config = load_config()
    
    # 验证API
    if not config.api_key or config.api_key == 'YOUR_API_KEY_HERE':
        logger.error("请先在config.ini中配置Bybit API密钥")
        sys.exit(1)
    
    print(f"\n配置确认:")
    print(f"  交易对: {config.symbol}")
    print(f"  杠杆: {config.leverage}x")
    print(f"  仓位: {config.position_size_pct*100}%")
    print(f"  做空侧重: {config.short_bias*100}%")
    print(f"  测试网: {config.testnet}")
    
    print("\n开始模拟交易...")
    print(f"日志文件: logs/bybit_doomsday_*.log")
    
    # 创建交易系统
    try:
        trader = BybitDoomsdayTrader(config)
        trader.run()
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()