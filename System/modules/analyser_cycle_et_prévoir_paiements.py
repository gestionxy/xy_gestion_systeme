import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from modules.data_loader import load_supplier_data


def analyser_cycle_et_prévoir_paiements():


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


    #st.markdown("<br>", unsafe_allow_html=True)  # 插入1行空白
    st.markdown(f"### ⌛ 各公司付款周期分析 - 天数统计")

    # 计算付款周期的时候，使用的是之前调整的 df_gestion_unpaid 完整数据
    df_paid_days = df_gestion_unpaid[df_gestion_unpaid['开支票日期'].notna() & df_gestion_unpaid['发票日期'].notna()]

    # 1. 计算每张发票的付款天数
    df_paid_days['付款天数'] = (df_paid_days['开支票日期'] - df_paid_days['发票日期']).dt.days

    # 2. 分组统计：每个公司+部门的付款天数指标
    result_paid_days = df_paid_days.groupby(['部门','公司名称',]).agg(
        发票数量=('付款天数', 'count'),
        发票金额 = ('发票金额', 'sum'),
        付款天数中位数=('付款天数', 'median'),
        最短付款天数=('付款天数', 'min'),
        最长付款天数=('付款天数', 'max'),
        平均付款天数=('付款天数', 'mean')
    ).reset_index()

    result_paid_days['发票金额'] = result_paid_days['发票金额'].round(2)
    result_paid_days['付款天数中位数'] = result_paid_days['付款天数中位数'].round(2)
    result_paid_days['最短付款天数'] = result_paid_days['最短付款天数'].round(2)
    result_paid_days['最长付款天数'] = result_paid_days['最长付款天数'].round(2)
    result_paid_days['平均付款天数'] = result_paid_days['平均付款天数'].round(2)

    #st.dataframe(result_paid_days, use_container_width=True)


    # ------------------------------
    # 🎛️ 筛选控件 - 部门选择
    # ------------------------------
    departments = sorted(result_paid_days['部门'].dropna().unique())
    default_index = departments.index("杂货") if "杂货" in departments else 0  # 如果没有菜部则选第一个
    selected_department = st.selectbox("请选择一个部门查看：", departments, index=default_index)

    # ------------------------------
    # 📋 表格展示 - 按选中部门筛选
    # ------------------------------
    filtered_df = result_paid_days[result_paid_days['部门'] == selected_department]
    
    #st.dataframe(filtered_df, use_container_width=True)

    # ------------------------------
    # 📈 图表展示 - 公司 vs 付款天数中位数
    # ------------------------------
    # 按付款中位数从高到低排序，提高可读性
    sort_option = st.radio(
        "请选择柱状图排序依据(由大到小)：",
        options=['付款天数中位数', '发票金额'],
        index=0,
        horizontal=True
    )
    
    st.info("**付款天数中位数**：付款中位数越大，说明付款越慢，付款时长越长。")
    st.info("**发票金额**：将数据按发票金额排序，有助于识别采购金额较大的供应商，并评估其付款周期。")      

    # 根据用户选择的排序方式进行降序排列
    filtered_df = filtered_df.sort_values(by=sort_option, ascending=False)


    fig = px.bar(
        filtered_df,
        x='公司名称',
        y='付款天数中位数',
        color='付款天数中位数',  # 🌡️ 数值决定颜色深浅
        color_continuous_scale='Reds',
        title=f"{selected_department} 部门 - 各公司付款天数 - 中位数",
        labels={
            '付款天数中位数': '付款天数（中位数）',
            '公司名称': '公司',
            '发票数量': '发票数量',
            '发票金额': '发票金额（$）',
            '最短付款天数': '最短付款天数',
            '最长付款天数': '最长付款天数',
            '平均付款天数': '平均付款天数'
        },
        text='付款天数中位数',
        hover_data=[
            '发票数量',
            '发票金额',
            '最短付款天数',
            '最长付款天数',
            '平均付款天数'
        ],
        height=500
    )

    # 显示柱上文字，调整标签角度
    fig.update_traces(textposition='outside')
    fig.update_layout(
        xaxis_tickangle=-30,
        coloraxis_colorbar=dict(title='付款天数')
    )

    # 展示图表
    st.plotly_chart(fig, use_container_width=True)







    st.markdown("<br>", unsafe_allow_html=True)  # 插入1行空白
    st.markdown(f"### 💸 未付款项付款预测")

    df_paid_forest = df_gestion_unpaid.copy()

    # 1️⃣ 筛选应付未付不为0的数据
    df_paid_forest = df_paid_forest[df_paid_forest['应付未付'].fillna(0) != 0].copy()

    # 2️⃣ 合并历史付款中位数数据（按 部门 + 公司名称）
    # 假设 result_paid_days 中列名一致：部门，公司名称，付款天数中位数
    df_paid_forest = df_paid_forest.merge(
        result_paid_days[['部门', '公司名称', '付款天数中位数']],
        on=['部门', '公司名称'],
        how='left'
    )

    # 3️⃣ 计算预计付款日 = 发票日期 + 中位付款天数
    df_paid_forest['预计付款日'] = df_paid_forest['发票日期'] + pd.to_timedelta(df_paid_forest['付款天数中位数'], unit='D')

    # 4️⃣ 当前日期所在自然周的最后一天（周日）
    today = datetime.today().date()
    weekday = today.weekday()  # 周一 = 0, 周日 = 6
    end_of_week = today + timedelta(days=(6 - weekday))  # 本周周日

    # 5️⃣ 标记应付（即预计付款日在当前周内）
    df_paid_forest['是否本周应付'] = df_paid_forest['预计付款日'].dt.date <= end_of_week

    # 6️⃣ 统计总额（仅对是否应付为True的行）
    df_due_this_week = df_paid_forest[df_paid_forest['是否本周应付'] == True].copy()

    total_due_this_week = df_due_this_week['应付未付'].sum()

    by_department_pay_this_week = df_due_this_week.groupby('部门')['应付未付'].sum().reset_index().sort_values(by='应付未付', ascending=False)
    by_department_company_pay_this_week = df_due_this_week.groupby(['部门', '公司名称'])['应付未付'].sum().reset_index().sort_values(by='应付未付', ascending=False)
    

    # 四舍五入保留两位小数
    total_due_this_week = round(total_due_this_week, 2)
    by_department_pay_this_week['应付未付'] = by_department_pay_this_week['应付未付'].round(2)
    by_department_company_pay_this_week['应付未付'] = by_department_company_pay_this_week['应付未付'].round(2)
    
    #st.dataframe(by_department_pay_this_week)
    #st.dataframe(by_department_company_pay_this_week)
    #st.dataframe(df_paid_forest)


    # ------------------------------
    # 💰 展示总应付款金额（HTML 卡片形式）
    # ------------------------------
    st.markdown(f"""
        <div style='background-color:#EBF5FB; padding:20px; border-radius:10px;'>
            <h4 style='color:#2E86C1;'>📅 近期应付款预测总额：<span style='color:#C0392B;'>${total_due_this_week:,.2f}</span></h4>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)  # 插入1行空白
    
    st.info("**应付款项预测**：使用的是未付发票 发票日期 + 付款天数中位数 = 预测付款日期。")

    st.markdown("<br>", unsafe_allow_html=True)  # 插入1行空白

    # ------------------------------
    # 🎛️ 选择展示内容
    # ------------------------------
    forecast_view = st.radio("请选择要查看的付款预测图表：", ["按部门汇总", "查看部门下公司明细"], horizontal=True)

    # ------------------------------
    # 📊 部门级预测图
    # ------------------------------
    if forecast_view == "按部门汇总":
        fig_dept = px.bar(
            by_department_pay_this_week,
            x='部门',
            y='应付未付',
            text='应付未付',
            color='应付未付',
            color_continuous_scale='Blues',
            labels={'应付未付': '应付款金额'},
            title="本周各部门预计应付款总览"
        )
        fig_dept.update_traces(texttemplate='%{text:.2f}', textposition='outside')
        fig_dept.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig_dept, use_container_width=True)

    # ------------------------------
    # 📋 选择部门查看公司明细
    # ------------------------------
    elif forecast_view == "查看部门下公司明细":
        selected_forecast_dept = st.selectbox("请选择一个部门查看公司预测明细：", by_department_pay_this_week['部门'].unique())
        filtered_forecast = by_department_company_pay_this_week[
            by_department_company_pay_this_week['部门'] == selected_forecast_dept
        ]

        fig_company = px.bar(
            filtered_forecast,
            x='公司名称',
            y='应付未付',
            text='应付未付',
            color='应付未付',
            color_continuous_scale='Oranges',
            labels={'应付未付': '应付款金额'},
            title=f"{selected_forecast_dept} 部门 - 本周应付款公司明细"
        )
        fig_company.update_traces(texttemplate='%{text:.2f}', textposition='outside')
        fig_company.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig_company, use_container_width=True)

        
    #st.dataframe(by_department_company_pay_this_week)
    #st.dataframe(df_paid_forest)