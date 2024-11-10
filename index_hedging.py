import akshare as ak
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone

def generate_table(long_money):
    """生成表格"""
    long_money = long_money*10000
    futures_fees_info_df = ak.futures_fees_info()
    futures_fees_info_df = futures_fees_info_df[futures_fees_info_df['合约代码'].str.contains('IM|IC', regex=True)]
    for index, row in futures_fees_info_df.iterrows():
        row["最新价"] = row["最新价"] if row["最新价"] > 100 else row["上日收盘价"]
        futures_fees_info_df.loc[index,"最新价"] = row["最新价"]
        futures_fees_info_df.loc[index,"1手市值"] = int(row["最新价"] * row["合约乘数"])
        futures_fees_info_df.loc[index,"做多1手保证金"] = int(row["最新价"] * row["合约乘数"] * row["做多保证金率（按金额）"])
    futures_fees_info_df["最新价"] = futures_fees_info_df["最新价"].astype(float)
    update_time = futures_fees_info_df["更新时间"].iloc[-1]

    futures_fees_info_df["需做空（手）"] = (long_money // futures_fees_info_df["1手市值"]).astype(int)
    futures_fees_info_df["已对冲总金额"] = (futures_fees_info_df["需做空（手）"] * futures_fees_info_df["1手市值"]).astype(int)
    futures_fees_info_df["未对冲总金额"] = (long_money - futures_fees_info_df["已对冲总金额"]).astype(int)
    futures_fees_info_df["对冲账户所需保证金"] = (futures_fees_info_df["已对冲总金额"] * row["做空保证金率（按金额）"]).astype(int)
    futures_fees_info_df["对冲账户所需可用余额（追保资金）"] = (futures_fees_info_df["已对冲总金额"]*0.08).astype(int)
    futures_fees_info_df["对冲账户所需总权益"] = futures_fees_info_df["对冲账户所需保证金"] + futures_fees_info_df["对冲账户所需可用余额（追保资金）"] 
    futures_fees_info_df = futures_fees_info_df.filter(items=["合约代码", "合约名称", "1手市值",
                                                              "需做空（手）", "已对冲总金额", "未对冲总金额",
                                                              "对冲账户所需总权益", "对冲账户所需保证金", "对冲账户所需可用余额（追保资金）",
                                                              "上日收盘价", "最新价", "持仓量", "合约乘数", "保证金率", "做多1手保证金"])
    futures_fees_info_df = futures_fees_info_df.rename(columns={"1手市值":"1手合约市值", "持仓量":"市场总持仓量"})
    return futures_fees_info_df, update_time


# 设置 Streamlit 界面
st.title("LCD对冲策略计算器")
st.subheader("请输入您的多头持仓，然后点击查询按钮")

# 输入框，用于用户输入多头持仓
long_money = st.text_input("多头持仓（万元）：", "")
try:
    long_money = float(long_money) if long_money != "" else 0.0
except ValueError:
    st.write("多头持仓输入不合法，请重新输入！")

# 计算按钮
if st.button("计算"):
    # 如果输入框中有内容且点击查询按钮
    if long_money > 0:
        try:
            # 获取当前的时间和表格数据
            beijing_tz = timezone(timedelta(hours=8))
            compute_time_obj = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
            futures_fees_info_df, update_time = generate_table(long_money)
            
            # 显示查询时间和表格
            st.write(f"点击计算时间：{compute_time_obj}")
            st.write(f"期货数据更新时间：{update_time}")
            st.write(futures_fees_info_df.reset_index(drop=True))
        except Exception:
            st.write("获取当前期货数据失败，请重试！")
    else:
        st.write("多头持仓输入不合法，请重新输入！")
