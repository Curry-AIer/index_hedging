import akshare as ak
import pandas as pd
from pypinyin import pinyin, Style
import streamlit as st
from datetime import datetime, timedelta, timezone
import re
import imaplib
import email
from email.utils import parsedate_to_datetime
from email.header import make_header, decode_header
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding, hashes

def hash_string(input_string, algorithm=hashes.SHA512):
    data = input_string.encode('utf-8')
    digest = hashes.Hash(algorithm(), backend=default_backend())
    digest.update(data)
    hash_bytes = digest.finalize()
    return hash_bytes.hex()

def decrypt_string(encrypted_data, key):
    key = key.ljust(16, b'\0')
    iv = encrypted_data[:16]
    ciphertext = encrypted_data[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    original_data = unpadder.update(decrypted_data) + unpadder.finalize()
    return original_data.decode()

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
    long_money = float(long_money)*10000
    futures_fees_info_df = fetch_futures_fees_info()

    if futures_fees_info_df.empty:
        return pd.DataFrame(), None

    # 以下为表格计算代码
    futures_fees_info_df = futures_fees_info_df[futures_fees_info_df['合约代码'].str.contains('IM|IC', regex=True)]
    futures_fees_info_df["做多保证金率（按金额）"] = pd.Series(0.14, index=futures_fees_info_df.index, dtype='float32')
    for index, row in futures_fees_info_df.iterrows():
        row["最新价"] = row["最新价"] if row["最新价"] > 100 else row["上日收盘价"]
        futures_fees_info_df.loc[index,"最新价"] = row["最新价"]
        futures_fees_info_df.loc[index,"1手市值"] = int(row["最新价"] * row["合约乘数"])
        futures_fees_info_df.loc[index,"做多1手保证金"] = int(row["最新价"] * row["合约乘数"] * row["做多保证金率（按金额）"])

    futures_fees_info_df["最新价"] = futures_fees_info_df["最新价"].astype(float)
    futures_fees_info_df["实时涨跌幅"] = (futures_fees_info_df["最新价"] / futures_fees_info_df["上日收盘价"] - 1).apply(lambda x: f"{x:+.2%}")
    update_time = futures_fees_info_df["更新时间"].iloc[-1]

    futures_fees_info_df["需做空（手）"] = ((long_money * 0.79) // futures_fees_info_df["1手市值"]).astype('int64')
    futures_fees_info_df["已对冲总金额"] = (futures_fees_info_df["需做空（手）"] * futures_fees_info_df["1手市值"]).astype('int64')
    futures_fees_info_df["未对冲总金额"] = (long_money * 0.79 - futures_fees_info_df["已对冲总金额"]).astype('int64')
    futures_fees_info_df["对冲账户所需保证金"] = (futures_fees_info_df["已对冲总金额"] * row["做多保证金率（按金额）"]).astype('int64')
    futures_fees_info_df["对冲账户所需总权益"] = pd.Series(int(long_money * 0.21), index=futures_fees_info_df.index, dtype='int64')
    futures_fees_info_df["对冲账户可用余额（追保资金）"] = (futures_fees_info_df["对冲账户所需总权益"] - futures_fees_info_df["对冲账户所需保证金"]).astype('int64')
    futures_fees_info_df = futures_fees_info_df.filter(items=["合约代码", "合约名称", "1手市值",
                                                              "需做空（手）", "已对冲总金额", "未对冲总金额",
                                                              "对冲账户所需总权益", "对冲账户所需保证金", "对冲账户所需可用余额（追保资金）",
                                                              "上日收盘价", "最新价", "实时涨跌幅", "持仓量", "合约乘数", "做多保证金率（按金额）", "做多1手保证金"])
    futures_fees_info_df["做多保证金率（按金额）"] = futures_fees_info_df["做多保证金率（按金额）"].apply(lambda x: f"{x:.2%}")
    futures_fees_info_df = futures_fees_info_df.rename(columns={"1手市值":"1手合约市值（元）", "持仓量":"市场总持仓量", "做多保证金率（按金额）":"保证金率"})
    return futures_fees_info_df, update_time

def extract_email(secret_key):
    email_value_config = {
        'imap_server': b'\xc5\xe5\xa2Q\xd1LQ[\x1b\xda<z\xacf\x8env\x8dH\x90U\x86\xc9^H\xb3\x83\xa1\xb0\x10\x85t',
        'username': b'\x13\x8c:g3\xfa\x84\xb8\xbc\xc2f\x0b\xcd\xe7\xde\x16\x17\x84\xc9\xd5\x9aj\x1elC\x86\x0e\xd4\x87\x19\xa4;\xc9\xb6\x01\xd0\xa5M\xb4\x0e\xbf\xb6"\x9c|)\x1e ',
        'password': b'\x86\x9b([\x0bg\x0f#\xad~c\x13k]\x91\xb6\xde]\xcd\xf6:Uq<T\x0b}!\x89\x06#!\xe79V\x8d\xe4S\xb9}\xc1.\x1c\xc2\x1e\x0f\xebf',
    }
    email_server = imaplib.IMAP4_SSL(decrypt_string(email_value_config['imap_server'], secret_key.encode('utf-8')))
    email_server.login(decrypt_string(email_value_config["username"], secret_key.encode('utf-8')), decrypt_string(email_value_config['password'], secret_key.encode('utf-8')))
    email_server.select('INBOX')  # 选择【收件箱】
    # 选择收件箱
    beijing_time = datetime.utcnow() + timedelta(hours=8)
    eight_days_ago = (beijing_time - timedelta(days=8)).strftime('%d-%b-%Y')
    _typ, _search_data = email_server.search(None,
                                             'SINCE', eight_days_ago,
                                             'SUBJECT', ("净值".encode('utf-8')),
                                             'SUBJECT', ("虚拟".encode('utf-8')))
    # 开始解析
    mailidlist = _search_data[0].split()  # 转成标准列表,获得所有邮件的ID

    # 按日期降序排序
    mail_with_dates = []
    for mail_id in mailidlist:
        # 获取邮件的头部数据
        _typ, msg_data = email_server.fetch(mail_id, '(BODY[HEADER.FIELDS (DATE)])')
        # 提取日期字段
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                # 获取头部信息
                header_data = response_part[1].decode('utf-8')
                # 从头部提取日期
                date_str = header_data.split("Date: ")[-1].strip()
                mail_date = parsedate_to_datetime(date_str)  # 转为 datetime 对象
                mail_with_dates.append((mail_id, mail_date))
    # 按时间降序排序
    sorted_mail_with_dates = sorted(mail_with_dates, key=lambda x: x[1], reverse=True)
    # 提取排序后的邮件 ID 列表
    sorted_mailidlist = [mail[0] for mail in sorted_mail_with_dates]

    # 解析内容：
    han_rong_info, wan_yan_1_info, wan_yan_3_info, zheng_ding_info, hui_jin_info, meng_xi_info = {}, {}, {}, {}, {}, {}
    for mail_id in sorted_mailidlist:
        result, data = email_server.fetch(mail_id, '(RFC822)')  # 通过邮件id获取邮件
        email_message = email.message_from_bytes(data[0][1])  # 邮件内容（未解析）
        subject = make_header(decode_header(email_message['SUBJECT']))  # 主题
        mail_from = make_header(decode_header(email_message['From']))  # 发件人
        mail_dt = parsedate_to_datetime(email_message['Date'])  # 收件时间
        email_info = {
            "主题": str(subject),
            "发件人": str(mail_from),
            "收件时间": mail_dt,
        }
        # print(email_info)

        # 提取邮件正文内容
        # 邮件可能包含多个部分（例如，文本部分和HTML部分），我们需要遍历所有部分

        if email_message.is_multipart():
            for part in email_message.walk():  # 使用 walk() 方法遍历所有部分
                content_type = part.get_content_type()  # 获取当前部分的类型
                content_disposition = str(part.get("Content-Disposition"))  # 获取当前部分的附件信息

                # 如果是文本部分且不是附件，则打印正文内容
                if "attachment" not in content_disposition:
                    if content_type == "text/plain":  # 纯文本邮件
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        # print("邮件正文（纯文本）:")
                        # print(body)
                    elif content_type == "text/html":  # HTML格式邮件
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        # print("净值信息：")
                        get_initials = lambda text: ''.join(
                            map(lambda x: x[0].upper(), pinyin(text, style=Style.FIRST_LETTER))
                        )
                        # #han rong
                        # if re.search(b'\xe7\xbf\xb0\xe8\x8d\xa3'.decode('utf-8'), body):
                        #     td_contents = re.findall(r'<td>(.*?)</td>', body, flags=re.DOTALL)
                        #     # print(td_contents)
                        #     ming_cheng = td_contents[1]
                        #     jing_zhi_ri_qi = datetime.strptime(td_contents[2], "%Y%m%d").strftime("%Y-%m-%d")
                        #     fen_e = float(td_contents[6].replace(',',''))
                        #     dan_wei_jing_zhi = float(td_contents[7].replace(',',''))
                        #     xu_ni_jing_zhi = float(td_contents[10].replace(',',''))
                        #     ji_ti_qian_jin_e = float(td_contents[5].replace(',',''))
                        #     ji_ti_hou_jin_e = ji_ti_qian_jin_e - float(td_contents[9].replace(',',''))
                        #     dang_qi_ye_ji_bao_chou = float(td_contents[9].replace(',',''))
                        #     if not (han_rong_info.get('产品名称', 0)):
                        #         han_rong_info['产品名称'] = get_initials(ming_cheng[:2])
                        #         han_rong_info['净值日期'] = jing_zhi_ri_qi
                        #         han_rong_info['计提前金额'] = ji_ti_qian_jin_e
                        #         han_rong_info['计提后金额'] = ji_ti_hou_jin_e
                        #         han_rong_info['当期业绩报酬'] = dang_qi_ye_ji_bao_chou
                        #         han_rong_info['持有份额'] = fen_e
                        #         han_rong_info['单位净值'] = dan_wei_jing_zhi
                        #         han_rong_info['虚拟净值'] = xu_ni_jing_zhi
                        #wan yan 1
                        if re.search(b'\xe9\xa1\xbd\xe5\xb2\xa9\xe4\xb8\xad\xe8\xaf\x812000\xe6\x8c\x87\xe6\x95\xb0\xe5\xa2\x9e\xe5\xbc\xba1\xe5\x8f\xb7'.decode('utf-8'), body):
                            td_contents = re.findall(r'<td>(.*?)</td>', body, flags=re.DOTALL)
                            # print(td_contents)
                            ming_cheng = td_contents[1]
                            jing_zhi_ri_qi = datetime.strptime(td_contents[2], "%Y%m%d").strftime("%Y-%m-%d")
                            fen_e = float(td_contents[6].replace(',',''))
                            dan_wei_jing_zhi = float(td_contents[7].replace(',',''))
                            xu_ni_jing_zhi = float(td_contents[10].replace(',',''))
                            ji_ti_qian_jin_e = float(td_contents[5].replace(',',''))
                            ji_ti_hou_jin_e = ji_ti_qian_jin_e - float(td_contents[9].replace(',',''))
                            dang_qi_ye_ji_bao_chou = float(td_contents[9].replace(',',''))
                            if not (wan_yan_1_info.get('产品名称', 0)):
                                wan_yan_1_info['产品名称'] = get_initials(ming_cheng[:2] + "1")
                                wan_yan_1_info['净值日期'] = jing_zhi_ri_qi
                                wan_yan_1_info['计提前金额'] = ji_ti_qian_jin_e
                                wan_yan_1_info['计提后金额'] = ji_ti_hou_jin_e
                                wan_yan_1_info['当期业绩报酬'] = dang_qi_ye_ji_bao_chou
                                wan_yan_1_info['持有份额'] = fen_e
                                wan_yan_1_info['单位净值'] = dan_wei_jing_zhi
                                wan_yan_1_info['虚拟净值'] = xu_ni_jing_zhi
                        #wan yan 3
                        if re.search(b'\xe9\xa1\xbd\xe5\xb2\xa9\xe4\xb8\xad\xe8\xaf\x812000\xe6\x8c\x87\xe6\x95\xb0\xe5\xa2\x9e\xe5\xbc\xba3\xe5\x8f\xb7'.decode('utf-8'), body):
                            td_contents = re.findall(r'<td>(.*?)</td>', body, flags=re.DOTALL)
                            # print(td_contents)
                            ming_cheng = td_contents[1]
                            jing_zhi_ri_qi = datetime.strptime(td_contents[2], "%Y%m%d").strftime("%Y-%m-%d")
                            fen_e = float(td_contents[6].replace(',',''))
                            dan_wei_jing_zhi = float(td_contents[7].replace(',',''))
                            xu_ni_jing_zhi = float(td_contents[10].replace(',',''))
                            ji_ti_qian_jin_e = float(td_contents[5].replace(',',''))
                            ji_ti_hou_jin_e = ji_ti_qian_jin_e - float(td_contents[9].replace(',',''))
                            dang_qi_ye_ji_bao_chou = float(td_contents[9].replace(',',''))
                            if not (wan_yan_3_info.get('产品名称', 0)):
                                wan_yan_3_info['产品名称'] = get_initials(ming_cheng[:2] + "3")
                                wan_yan_3_info['净值日期'] = jing_zhi_ri_qi
                                wan_yan_3_info['计提前金额'] = ji_ti_qian_jin_e
                                wan_yan_3_info['计提后金额'] = ji_ti_hou_jin_e
                                wan_yan_3_info['当期业绩报酬'] = dang_qi_ye_ji_bao_chou
                                wan_yan_3_info['持有份额'] = fen_e
                                wan_yan_3_info['单位净值'] = dan_wei_jing_zhi
                                wan_yan_3_info['虚拟净值'] = xu_ni_jing_zhi
                        # #zheng ding
                        # if re.search(b'\xe6\xad\xa3\xe5\xae\x9a'.decode('utf-8'), body): #done
                        #     td_contents = re.findall(r'<td>(.*?)</td>', body, flags=re.DOTALL)
                        #     # print(td_contents)
                        #     ming_cheng = td_contents[2].split('：')[-1]
                        #     jing_zhi_ri_qi = td_contents[4].split('：')[-1]
                        #     fen_e = float(td_contents[7].split('：')[-1].replace(',',''))
                        #     dan_wei_jing_zhi = float(td_contents[8].split('：')[-1].replace(',',''))
                        #     xu_ni_jing_zhi = float(td_contents[10].split('：')[-1].replace(',',''))
                        #     ji_ti_qian_jin_e = round(dan_wei_jing_zhi * fen_e, 2)
                        #     ji_ti_hou_jin_e = round(xu_ni_jing_zhi * fen_e, 2)
                        #     dang_qi_ye_ji_bao_chou = round(ji_ti_qian_jin_e - ji_ti_hou_jin_e, 2)
                        #     if not (zheng_ding_info.get('产品名称', 0)):
                        #         zheng_ding_info['产品名称'] = get_initials(ming_cheng[:2])
                        #         zheng_ding_info['净值日期'] = jing_zhi_ri_qi
                        #         zheng_ding_info['计提前金额'] = ji_ti_qian_jin_e
                        #         zheng_ding_info['计提后金额'] = ji_ti_hou_jin_e
                        #         zheng_ding_info['当期业绩报酬'] = dang_qi_ye_ji_bao_chou
                        #         zheng_ding_info['持有份额'] = fen_e
                        #         zheng_ding_info['单位净值'] = dan_wei_jing_zhi
                        #         zheng_ding_info['虚拟净值'] = xu_ni_jing_zhi
                        # #hui jin
                        # if re.search(b'\xe6\xb1\x87\xe7\x91\xbe'.decode('utf-8'), body): #done
                        #     td_contents = re.findall(r'<td>(.*?)</td>', body, flags=re.DOTALL)
                        #     # print(td_contents)
                        #     ming_cheng = td_contents[2].split('：')[-1]
                        #     jing_zhi_ri_qi = td_contents[4].split('：')[-1]
                        #     fen_e = float(td_contents[7].split('：')[-1].replace(',',''))
                        #     dan_wei_jing_zhi = float(td_contents[8].split('：')[-1].replace(',',''))
                        #     xu_ni_jing_zhi = float(td_contents[10].split('：')[-1].replace(',',''))
                        #     ji_ti_qian_jin_e = round(dan_wei_jing_zhi * fen_e, 2)
                        #     ji_ti_hou_jin_e = round(xu_ni_jing_zhi * fen_e, 2)
                        #     dang_qi_ye_ji_bao_chou = round(ji_ti_qian_jin_e - ji_ti_hou_jin_e, 2)
                        #     if not (hui_jin_info.get('产品名称', 0)):
                        #         hui_jin_info['产品名称'] = get_initials(ming_cheng[:2])
                        #         hui_jin_info['净值日期'] = jing_zhi_ri_qi
                        #         hui_jin_info['计提前金额'] = ji_ti_qian_jin_e
                        #         hui_jin_info['计提后金额'] = ji_ti_hou_jin_e
                        #         hui_jin_info['当期业绩报酬'] = dang_qi_ye_ji_bao_chou
                        #         hui_jin_info['持有份额'] = fen_e
                        #         hui_jin_info['单位净值'] = dan_wei_jing_zhi
                        #         hui_jin_info['虚拟净值'] = xu_ni_jing_zhi
                        #meng xi
                        if re.search(b'\xe8\x92\x99\xe7\x8e\xba'.decode('utf-8'), body): #done
                            td_contents = re.findall(r'yahei="">(.*?)</span>', body, flags=re.DOTALL)
                            # print(td_contents)
                            ming_cheng = td_contents[5]
                            jing_zhi_ri_qi = td_contents[3]
                            fen_e = float(td_contents[8].replace(',',''))
                            dan_wei_jing_zhi = float(td_contents[9].replace(',',''))
                            xu_ni_jing_zhi = round(float(td_contents[12])/fen_e, 4)
                            ji_ti_qian_jin_e = float(td_contents[11])
                            ji_ti_hou_jin_e = float(td_contents[12])
                            dang_qi_ye_ji_bao_chou = ji_ti_qian_jin_e - ji_ti_hou_jin_e
                            if not (meng_xi_info.get('产品名称', 0)):
                                meng_xi_info['产品名称'] = get_initials(ming_cheng[:2])
                                meng_xi_info['净值日期'] = jing_zhi_ri_qi
                                meng_xi_info['计提前金额'] = ji_ti_qian_jin_e
                                meng_xi_info['计提后金额'] = ji_ti_hou_jin_e
                                meng_xi_info['当期业绩报酬'] = dang_qi_ye_ji_bao_chou
                                meng_xi_info['持有份额'] = fen_e
                                meng_xi_info['单位净值'] = dan_wei_jing_zhi
                                meng_xi_info['虚拟净值'] = xu_ni_jing_zhi
    df = pd.DataFrame([wan_yan_1_info, wan_yan_3_info, meng_xi_info])
    df = df.sort_values(by="计提前金额", ascending=False).set_index("产品名称", drop=True)
    ji_ti_qian_zong_jin_e = round(df['计提前金额'].sum(), 2)
    ji_ti_hou_zong_jin_e = round(df['计提后金额'].sum(), 2)
    dang_qi_zong_ye_ji_bao_chou = ji_ti_qian_zong_jin_e - ji_ti_hou_zong_jin_e
    df = df.style.format({
        '计提前金额': '{:,.2f}',
        '计提后金额': '{:,.2f}',
        '当期业绩报酬': '{:,.2f}',
        '持有份额': '{:,.2f}',
        '单位净值': '{:,.4f}',
        '虚拟净值': '{:,.4f}'
    })
    return df, ji_ti_qian_zong_jin_e, ji_ti_hou_zong_jin_e, dang_qi_zong_ye_ji_bao_chou

def show_hedging_calculator():
    # 打印对冲计算器
    st.subheader("对冲计算器")
    long_money = st.text_input("请输入考虑杠杆的资金总额（万元）：", "")

    if "compute_button_clicked" not in st.session_state:
        st.session_state.compute_button_clicked = False

    if st.button("计算", disabled=st.session_state.compute_button_clicked):
        with st.spinner("计算中，请稍候..."):
            try:
                long_money = float(long_money.replace(",", ""))
            except ValueError:
                st.write("多头持仓输入不合法，请重新输入！")
            else:
                if isinstance(long_money, (int, float)) and long_money > 0:
                    beijing_tz = timezone(timedelta(hours=8))
                    compute_time_obj = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
                    futures_fees_info_df, update_time = generate_table(long_money)

                    if not futures_fees_info_df.empty:
                        st.write(f"点击计算时间：{compute_time_obj}")
                        st.write(f"期货数据刷新时间：{update_time}")
                        st.write("")
                        st.dataframe(futures_fees_info_df.set_index("合约代码", drop=True), use_container_width=True)
                    else:
                        st.write("无法获取期货数据，请检查网络连接或稍后重试。")
                else:
                    st.write("多头持仓输入不合法，请重新输入！")
        st.session_state.compute_button_clicked = False  # 解锁button

def main():
    # 打印持仓信息
    st.write("")
    st.write("")
    st.subheader("实时持仓查询")
    if "refresh_button_clicked" not in st.session_state:
        st.session_state.refresh_button_clicked = False
    if "pwd_success" not in st.session_state or not st.session_state.refresh_button_clicked:
        st.session_state["pwd_success"] = False
        secret_key = st.text_input("请输入密码：", type="password", key="pwd_input")
    if st.session_state["pwd_success"]:
        st.session_state["pwd_input"] = ""
        st.session_state.refresh_button_clicked = False
        secret_key = st.text_input("请输入密码：", type="password", key="pwd_input")
    if st.button("查询", disabled=st.session_state.refresh_button_clicked):
        st.session_state.refresh_button_clicked = True
        if secret_key:
            # 用户点击确认提交后验证
            pwd_hash_bytes = "cc0c2d8a98edc8c08b40b7ea6a8828f2686e33aa81b64230b4f75e0f10d4e98599cab16700230dee97151ff23f6925478c456999684eadd7f21e8d97fc495801"
            if hash_string(secret_key) == pwd_hash_bytes:
                st.session_state["pwd_success"] = True
                st.session_state["secret_key"] = secret_key
                if (st.session_state.refresh_button_clicked):
                    st.rerun()
            else:
                st.session_state.refresh_button_clicked = False
                st.error("密码错误！请输入正确的密码。")
                st.write("")
                st.write("")
                show_hedging_calculator()
                return
        else:
            st.session_state.refresh_button_clicked = False
            st.error("输入密码不能为空！请重新输入。")
            st.write("")
            st.write("")
            show_hedging_calculator()
            return
    if (st.session_state["pwd_success"]):
        st.session_state["pwd_success"] = False
        st.session_state.refresh_button_clicked = False
        st.success("密码验证成功！")
        with st.spinner("刷新持仓数据中，请稍候..."):
            # 获取时间和Email信息
            beijing_tz = timezone(timedelta(hours=8))
            extract_email_time = datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
            email_df, ji_ti_qian_zong_jin_e, ji_ti_hou_zong_jin_e, dang_qi_zong_ye_ji_bao_chou \
                = extract_email(st.session_state["secret_key"])
            cheng_ben_zong_jin_e = 11518238.41
            # 打印持仓信息
            st.write(f"持仓数据刷新时间：{extract_email_time}")
            st.write(f"成本总金额：{cheng_ben_zong_jin_e:,.2f}")
            st.write(f"计提前总金额：{ji_ti_qian_zong_jin_e:,.2f}")
            st.write(f"计提后总金额：{ji_ti_hou_zong_jin_e:,.2f}")
            st.write(f"当期总业绩报酬：{dang_qi_zong_ye_ji_bao_chou:,.2f}")
            st.write(f"当期总盈亏(2024年11月8日~至今)：{(ji_ti_hou_zong_jin_e - cheng_ben_zong_jin_e):+,.2f} \({(ji_ti_hou_zong_jin_e - cheng_ben_zong_jin_e)/cheng_ben_zong_jin_e:+.2%}\)")
            # 显示持仓信息表格
            st.write("")
            st.table(email_df)
    st.write("")
    st.write("")
    st.write("")
    st.write("")
    st.write("")
    st.write("")
    show_hedging_calculator()


if __name__ == '__main__':
    main()
