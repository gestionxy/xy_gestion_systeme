import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from modules.data_loader import load_supplier_data


# ** df_gestion_unpaid ** 是目前处理的最完整的表格，所有的后续处理均使用这张表格

def analyse_des_impayes():

    df = load_supplier_data()

    df['发票日期'] = pd.to_datetime(df['发票日期'], errors='coerce')
    df['开支票日期'] = pd.to_datetime(df['开支票日期'], errors='coerce')



    # 2️⃣ 获取当前日期
    current_date = pd.to_datetime(datetime.today().date())


    df_gestion_unpaid = df.copy()


    # 3️⃣ 筛选结尾为 "*" 的公司名，且开支票日期为空的行
    mask_star_company = df_gestion_unpaid['公司名称'].astype(str).str.endswith("*")
    mask_no_cheque_date = df_gestion_unpaid['开支票日期'].isna()
    mask_star_and_pending = mask_star_company & mask_no_cheque_date

    # 4️⃣ 判断发票日期+10天是否小于当前日期，并处理
    condition_overdue = (
        mask_star_and_pending &
        (df_gestion_unpaid['发票日期'] + pd.Timedelta(days=10) < current_date)
    )

    # 5️⃣ 对满足条件的行进行赋值操作
    df_gestion_unpaid.loc[condition_overdue, '开支票日期'] = df_gestion_unpaid.loc[condition_overdue, '发票日期'] + pd.Timedelta(days=10)
    df_gestion_unpaid.loc[condition_overdue, '实际支付金额'] = df_gestion_unpaid.loc[condition_overdue, '发票金额']
    df_gestion_unpaid.loc[condition_overdue, '付款支票总金额'] = df_gestion_unpaid.loc[condition_overdue, '发票金额']

    # 6️⃣ 新建列【应付未付】
    df_gestion_unpaid['应付未付'] = df_gestion_unpaid['发票金额'].fillna(0) - df_gestion_unpaid['实际支付金额'].fillna(0)

    # 7️⃣ 汇总应付未付总额、各部门汇总、各公司汇总
    total_unpaid = df_gestion_unpaid['应付未付'].sum()

    # 部门汇总
    by_department = (
        df_gestion_unpaid
        .groupby('部门')['应付未付']
        .sum()
        .reset_index()
        .sort_values(by='应付未付', ascending=False)
        .round({'应付未付': 2})  # ← 保留两位小数
    )

    # 部门 + 公司名称汇总
    by_department_company = (
        df_gestion_unpaid
        .groupby(['部门', '公司名称'])['应付未付']
        .sum()
        .reset_index()
        .sort_values(by='应付未付', ascending=False)
        .round({'应付未付': 2})  # ← 同样处理
    )
    #st.dataframe(by_department_company)


    # ------------------------------
    # 💰 展示总应付未付金额（使用 HTML 卡片）
    # ------------------------------
    st.markdown(f"""
        <div style='background-color:#FDEDEC; padding:20px; border-radius:10px'>
            <h2 style='color:#C0392B;'>当前应付未付总额：${total_unpaid:,.2f}</h2>
        </div>
    """, unsafe_allow_html=True)


    st.markdown("<br>", unsafe_allow_html=True)  # 插入1行空白
    st.markdown(f"### 🧾  各部门及各公司未付款项")
    
    
    # ------------------------------
    # 🎛️ 用户选择视图类型
    # ------------------------------
    view_option = st.radio("请选择要查看的图表：", ["查看各部门汇总", "查看部门下公司明细"], horizontal=True)

    # ------------------------------
    # 📊 部门汇总图表
    # ------------------------------
    if view_option == "查看各部门汇总":
        fig = px.bar(
            by_department,
            x='部门',
            y='应付未付',
            text='应付未付',
            color='应付未付',
            color_continuous_scale='Oranges',
            labels={'应付未付': '应付未付金额'},
            title="各部门应付未付金额总览"
        )
        fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
        fig.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)

    # ------------------------------
    # 📋 选择部门查看公司明细
    # ------------------------------
    elif view_option == "查看部门下公司明细":
        selected_dept = st.selectbox("请选择一个部门查看其公司明细：", by_department['部门'].unique())
        filtered = by_department_company[by_department_company['部门'] == selected_dept]

        fig = px.bar(
            filtered,
            x='公司名称',
            y='应付未付',
            text='应付未付',
            color='应付未付',
            color_continuous_scale='Blues',
            labels={'应付未付': '应付未付金额'},
            title=f"{selected_dept} 部门 - 公司应付未付明细"
        )
        fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
        fig.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)





   