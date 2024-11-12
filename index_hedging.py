import akshare as ak
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone

def fetch_futures_fees_info():
    error_placeholder = st.empty()  # 创建一个占位符
    for i in range(10):  # 尝试10次
        try:
            data = ak.futures_fees_info()
        except Exception as e:
            error_placeholder.write(f"第 {i+1} 次获取期货数据失败，正在重试...")
        else:
            error_placeholder.empty()  # 清除错误信息
            return data
    error_placeholder.write("多次尝试获取期货数据失败，请检查网络后重试。")
    return pd.DataFrame()

def generate_table(long_money):
    """生成表格"""
    long_money *= 10000
    futures_fees_info_df = fetch_futures_fees_info()
    
    if futures_fees_info_df.empty:
        return pd.DataFrame(), None

    # 以下为表格计算代码
    futures_fees_info_df = futures_fees_info_df[futures_fees_info_df['合约代码'].str.contains('IM|IC', regex=True)]
    for index, row in futures_fees_info_df.iterrows():
        row["最新价"] = row["最新价"] if row["最新价"] > 100 else row["上日收盘价"]
        futures_fees_info_df.loc[index,"最新价"] = row["最新价"]
        futures_fees_info_df.loc[index,"1手市值"] = int(row["最新价"] * row["合约乘数"])
        futures_fees_info_df.loc[index,"做多1手保证金"] = int(row["最新价"] * row["合约乘数"] * row["做多保证金率（按金额）"])

    futures_fees_info_df["最新价"] = futures_fees_info_df["最新价"].astype(float)
    futures_fees_info_df["实时涨跌幅"] = (futures_fees_info_df["最新价"] / futures_fees_info_df["上日收盘价"] - 1).apply(lambda x: f"{x:+.2%}")
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
                                                              "上日收盘价", "最新价", "实时涨跌幅", "持仓量", "合约乘数", "保证金率", "做多1手保证金"])
    futures_fees_info_df = futures_fees_info_df.rename(columns={"1手市值":"1手合约市值（元）", "持仓量":"市场总持仓量"})
    return futures_fees_info_df, update_time

# Streamlit 界面
st.title("LCD对冲策略计算器")
st.subheader("请输入您的多头持仓，然后点击计算按钮")

long_money = st.text_input("多头持仓（万元）：", "")

if "button_clicked" not in st.session_state:
    st.session_state.button_clicked = False

if st.button("计算", disabled=st.session_state.button_clicked):
    st.session_state.button_clicked = True

    with st.spinner("计算中，请稍候..."):
        try:
            long_money = float(long_money)
        except ValueError:
            st.write("多头持仓输入不合法，请重新输入！")
        else:
            if isinstance(long_money, (int, float)) and long_money > 0:
                beijing_tz = timezone(timedelta(hours=8))
                compute_time_obj = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
                futures_fees_info_df, update_time = generate_table(long_money)
                
                if not futures_fees_info_df.empty:
                    st.write(f"点击计算时间：{compute_time_obj}")
                    st.write(f"期货数据更新时间：{update_time}")
                    st.write("")
                    st.dataframe(futures_fees_info_df.set_index("合约代码", drop=True), use_container_width=True)
                else:
                    st.write("无法获取期货数据，请检查网络连接或稍后重试。")
            else:
                st.write("多头持仓输入不合法，请重新输入！")

    st.session_state.button_clicked = False  # 解锁button
