# QuantInvest — 量化投资框架

集成 A 股 (akshare + baostock)、美股 (yfinance) 数据源与 backtrader 回测引擎。

## 安装

```bash
pip install -e .
# or with dev deps:
pip install -e ".[dev]"
```

> **注意**: numpy 必须锁定 1.26.x（2.x 需要 AVX 指令集，旧 CPU 不兼容）。ta-lib 0.6.x wheel 自带 C 库，`pip install` 即可直接使用。

## 支持的策略

| 策略 | 模块 | 技术指标来源 |
|------|------|------------|
| 均线交叉 | `MACrossStrategy` | backtrader 内置 |
| MACD | `MACDStrategy` | backtrader 内置 + RSI 过滤 |
| 布林带 | `BollingerStrategy` | backtrader 内置 |
| 海龟突破 | `TurtleStrategy` | backtrader 内置 |
| Alpha 动量 | `AlphaStrategy` | backtrader 内置 |
| 反转策略 | `ReversalStrategy` | backtrader 内置 |
| 突破策略 | `BreakoutStrategy` | backtrader 内置 |
| 筹码成本交叉 | `CostCrossStrategy` | 自定义实现 |

## 数据源

| 类型 | 库 | 适用市场 |
|------|-----|----------|
| A 股实时 | akshare | sh / sz |
| A 股历史 | baostock | sh / sz |
| 美股 / 港股 | yfinance | .US / .HK |

## 依赖版本

| 库 | 版本 | 备注 |
|----|------|------|
| numpy | 1.26.4 | 锁定版本（无 AVX CPU 兼容） |
| ta-lib | 0.6.8 | wheel 内置 C 库，无需手动安装 |
| pandas | 3.0.3 | |
| backtrader | 1.9.78.123 | 回测引擎 + 内置技术指标 |
| akshare | 1.18.64 | A 股数据源 |
| baostock | 0.9.2 | A 股数据源 |
| yfinance | 1.4.1 | 美股/港股数据源 |
