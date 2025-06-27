import streamlit as st
from ui.sidebar import render_sidebar
from ui.sidebar import render_sidebar, render_refresh_button
from modules.data_loader import load_supplier_data  # 你需要创建这个模块
from modules.analyser_cycle_et_prévoir_paiements import analyser_cycle_et_prévoir_paiements
from modules.analyse_des_impayes import analyse_des_impayes
from modules.analyse_des_payments import analyse_des_payments
from modules.achat_des_produits import achat_des_produits




from modules.ap_unpaid import ap_unpaid_query
from modules.paid_cheques import paid_cheques_query
from modules.company_invoice_query import company_invoice_query
from modules.cheque_ledger_query import cheque_ledger_query






st.set_page_config(page_title="新亚超市采购及付款管理系统", layout="wide")

# 页面标题
st.markdown("""
    <h2 style='color:#1A5276;'>新亚超市采购及付款管理系统</h2>
""", unsafe_allow_html=True)


# ✅ 手动刷新数据按钮，显示在左侧最上方
refresh_triggered = render_refresh_button(load_supplier_data)


# 左侧导航
selected = render_sidebar()

# 根据选项运行对应功能
#if selected == "应付未付账单查询(管理版)":
    #ap_unpaid_query()


if selected == "未付款项分析":
    analyse_des_impayes()

#if selected == "付款支票信息查询":
    #paid_cheques_query()

if selected == "付款周期及付款预测":
    analyser_cycle_et_prévoir_paiements()

if selected == "超市采购分析":
    achat_des_produits()

#if selected == "按公司查询":
    #company_invoice_query()

#if selected == "当前支票总账":
    #cheque_ledger_query()

if selected == "公司付款分析":
    analyse_des_payments()

