# QuantInvest — 量化投资框架

集成 A 股 (akshare + baostock)、美股 (yfinance) 数据源与 backtrader 回测引擎。

## 安装

```bash
pip install -e .
# or with dev deps:
pip install -e ".[dev]"
```

## 快速开始

### Python API

```python
from quantinvest.data import QuantData
from quantinvest.strategy import MACrossStrategy
from quantinvest.backtest import BacktestEngine

# 自动选择数据源（A股走 baostock，美股走 yfinance）
data = QuantData.get("600519.SH")
df = data.fetch(start="2023-01-01", end="2024-01-01")

# 运行回测
engine = BacktestEngine(df, cash=100_000)
results = engine.run(MACrossStrategy, short=5, long=20)

print(engine.get_report())
```

### CLI

```bash
# 运行回测
quantinvest backtest --symbol 600519.SH --strategy macross --start 2023-01-01

# 获取数据
quantinvest data --symbol 600519.SH --source baostock
```

## 支持的策略

| 策略 | 模块 |
|------|------|
| 均线交叉 | `MACrossStrategy` |
| MACD | `MACDStrategy` |
| 布林带 | `BollingerStrategy` |

## 数据源

| 类型 | 库 | 适用市场 |
|------|-----|----------|
| A 股实时 | akshare | sh / sz |
| A 股历史 | baostock | sh / sz |
| 美股 / 港股 | yfinance | .US / .HK |
