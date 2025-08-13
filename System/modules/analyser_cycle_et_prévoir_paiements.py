import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
from modules.data_loader import load_supplier_data


def analyser_cycle_et_prévoir_paiements():


    df = load_supplier_data()


    # 1.1 首先排除出 直接用信用卡VISA-1826 进行支付的，信用卡支付的不是公司支票账户
    #df = df[~df['公司名称'].isin(['SLEEMAN', 'Arc-en-ciel','Ferme vallee verte'])]
    df = df[~df['公司名称'].isin(['SLEEMAN', 'Arc-en-ciel'])]

    # 过滤掉 “发票金额”和“实际支付金额”两列的 都为0的数据行
    # 发票金额 = 实际支付金额 = 0， 表示void 取消的的支票，不再纳入我们的统计中
    # 因为会影响后续 付款账期计算 以及 统计该公司的 发票数量
    df = df[~((df['发票金额'] == 0) & (df['实际支付金额'] == 0))]


    df['发票日期'] = pd.to_datetime(df['发票日期'], errors='coerce')
    df['开支票日期'] = pd.to_datetime(df['开支票日期'], errors='coerce')

    # 2️⃣ 获取当前日期
    current_date = pd.to_datetime(datetime.today().date())

    df_gestion_unpaid = df.copy()

    # 管理版中，应付未付的统计口径是看是否有 开支票日期， 如果存在 开支票日期 ， 则默认已经支付成功了
    # 对于 【公司名*】 自动扣款的，这个 开支票日期 就需要自动设置

    # 会计版，相对复杂，统计口径以 银行对账单为准

    

    # 3️⃣ 筛选结尾为 "*" 的公司名，且开支票日期为空的行 ==> 我们要自动处理这些自动扣款的业务
    # 结尾为 "*" 的公司代表 这些公司使用的 自动扣款模式，因此我们要自动化处理扣款支付
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
    df_gestion_unpaid.loc[condition_overdue, '付款支票总额'] = df_gestion_unpaid.loc[condition_overdue, '发票金额']

    # 6️⃣ 新建列【应付未付】
    # 实际这一步转换可以省略，因为我们在导入数据时data_loader.py 中已经进行了强制 数值转换
    amount_cols = ['发票金额', '实际支付金额']
    df_gestion_unpaid[amount_cols] = df_gestion_unpaid[amount_cols].apply(pd.to_numeric, errors='coerce')

    df_gestion_unpaid['应付未付'] = df_gestion_unpaid['发票金额'].fillna(0) - df_gestion_unpaid['实际支付金额'].fillna(0)


    #st.markdown("### df_gestion_unpaid")
    #st.dataframe(df_gestion_unpaid)


    #st.markdown("<br>", unsafe_allow_html=True)  # 插入1行空白
    st.markdown(f"### ⌛ 各公司付款周期分析 - 天数统计")

    # 计算付款周期的时候，使用的是之前调整的 df_gestion_unpaid 完整数据
    df_paid_days = df_gestion_unpaid[df_gestion_unpaid['开支票日期'].notna() & df_gestion_unpaid['发票日期'].notna()]

    # 1. 计算每张发票的付款天数
    df_paid_days['付款天数'] = (df_paid_days['开支票日期'] - df_paid_days['发票日期']).dt.days

    #st.dataframe(df_paid_days)


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

    #st.info('df_due_this_week')
    #st.dataframe(df_due_this_week)

    total_due_this_week = df_due_this_week['应付未付'].sum()

    by_department_pay_this_week = df_due_this_week.groupby('部门')['应付未付'].sum().reset_index().sort_values(by='应付未付', ascending=False)
    by_department_company_pay_this_week = df_due_this_week.groupby(['部门', '公司名称'])['应付未付'].sum().reset_index().sort_values(by='应付未付', ascending=False)
    

    # 四舍五入保留两位小数
    total_due_this_week = round(total_due_this_week, 2)
    by_department_pay_this_week['应付未付'] = by_department_pay_this_week['应付未付'].round(2)
    by_department_company_pay_this_week['应付未付'] = by_department_company_pay_this_week['应付未付'].round(2)
    
    #st.dataframe(by_department_pay_this_week)
    #st.dataframe(by_department_company_pay_this_week)
    #st.info("df_paid_forest")
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
    forecast_view = st.radio("请选择要查看的付款预测图表：", ["按部门汇总", "查看部门下公司明细", "预测付款明细"], horizontal=True)

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


    # -----------------------------
    # ✅ 逻辑入口：查看部门下公司明细
    # -----------------------------
    if forecast_view == "查看部门下公司明细":

        # ✅ 1. 用户选择部门
        selected_forecast_dept = st.selectbox(
            "📌 请选择一个部门查看公司预测明细：",
            by_department_pay_this_week['部门'].dropna().unique()
        )

        # ✅ 2. 准备 df_paid_days 中最近的发票日期、支票日期、支票号、支票总额
        df_invoice_date = df_paid_days.copy()

        # 确保日期为 datetime 类型
        df_invoice_date['发票日期'] = pd.to_datetime(df_invoice_date['发票日期'], errors='coerce')
        df_invoice_date['开支票日期'] = pd.to_datetime(df_invoice_date['开支票日期'], errors='coerce')

        # ✅ 提取每个（部门，公司）组最近的一条记录
        latest_invoice_info = (
            df_invoice_date
            .sort_values(by=['发票日期', '开支票日期'], ascending=False)
            .dropna(subset=['发票日期', '开支票日期'])
            .groupby(['部门', '公司名称'], as_index=False)
            .first()[['部门', '公司名称', '发票日期', '开支票日期', '付款支票号', '付款支票总额']]
        )

        # ✅ 3. 选定部门下的数据并合并最近发票信息
        filtered_forecast = by_department_company_pay_this_week[
            by_department_company_pay_this_week['部门'] == selected_forecast_dept
        ].copy()

        filtered_forecast = filtered_forecast.merge(
            latest_invoice_info,
            on=['部门', '公司名称'],
            how='left'
        )

        # ✅ 4. 构建 hover 提示文本
        filtered_forecast['hover_text'] = (
            "应付款: " + filtered_forecast['应付未付'].map('{:,.2f}'.format) + " 元<br>" +
            "最近付款发票日期: " + filtered_forecast['发票日期'].astype(str) + "<br>" +
            "最近开支票日期: " + filtered_forecast['开支票日期'].astype(str) + "<br>" +
            "支票号: " + filtered_forecast['付款支票号'].astype(str) + "<br>" +
            "付款支票总额: " + filtered_forecast['付款支票总额'].map('{:,.2f}'.format)
        )

        # ✅ 5. 创建柱状图
        fig_company = px.bar(
            filtered_forecast,
            x='公司名称',
            y='应付未付',
            text='应付未付',
            color='应付未付',
            color_continuous_scale='Oranges',
            labels={'应付未付': '应付款金额'},
            title=f"{selected_forecast_dept} 部门 - 本周应付款公司明细",
            hover_data={'hover_text': True, '应付未付': False, '公司名称': False}
        )

        # ✅ 6. 图表美化
        fig_company.update_traces(
            texttemplate='%{text:.2f}',
            textposition='outside',
            hovertemplate='%{customdata[0]}<extra></extra>'
        )
        fig_company.update_layout(xaxis_tickangle=-30)

        # ✅ 7. 展示图表
        st.plotly_chart(fig_company, use_container_width=True)
        

        # -----------------------------
    # ✅ 逻辑入口：查看部门下公司明细
    # -----------------------------
    if forecast_view == "预测付款明细":


        # ✅ 1. 汇总本周每家公司的应付未付金额（从 df_due_this_week）
        by_company_pay_this_week = (
            df_due_this_week
            .groupby('公司名称')['应付未付']
            .sum()
            .reset_index()
            .sort_values(by='应付未付', ascending=False)
        )

        # ✅ 显示中间数据（可选）
        #st.info("📊 每家公司本周应付款汇总")
        #st.dataframe(by_company_pay_this_week)

        # ✅ 2. 从 df_paid_days 提取每家公司最近的付款发票记录
        df_invoice_date = df_paid_days.copy()


        # ✅ 每家公司：取最近一条记录（按发票日期 + 开支票日期倒序排序）
        latest_invoice_info = (
            df_invoice_date
            .sort_values(by=['发票日期', '开支票日期'], ascending=False)
            .dropna(subset=['发票日期', '开支票日期'])
            .groupby('公司名称', as_index=False)
            .first()[['公司名称', '发票日期', '开支票日期', '付款支票号', '付款支票总额']]
        )

        # ✅ 3. 从 df_paid_days 提取付款天数中位数
        result_paid_days_company = (
            df_paid_days
            .groupby('公司名称')
            .agg(付款天数中位数=('付款天数', 'median'))
            .reset_index()
            .round(2)
        )

        # ✅ 4. 合并以上三表构造最终预测表：filtered_forecast
        filtered_forecast = (
            by_company_pay_this_week
            .merge(latest_invoice_info, on='公司名称', how='left')
            .merge(result_paid_days_company, on='公司名称', how='left')
        )

        # ✅ 展示结果
        #st.subheader("📋 公司级别 - 应付款 + 最近付款记录 + 支付周期")
        #st.dataframe(filtered_forecast, use_container_width=True)

        #st.dataframe(result_paid_days_company)


        #st.info(f"filtered_forecast")
        #st.dataframe(filtered_forecast)

        # ✅ 4. 构建 hover 提示文本
        filtered_forecast['hover_text'] = (
            "公司名称: " + filtered_forecast['公司名称'].astype(str) + "<br>" +
            "应付款: " + filtered_forecast['应付未付'].map('{:,.2f}'.format) + " 元<br>" +
            "付款账期中位数: " + filtered_forecast['付款天数中位数'].map('{:,.0f}'.format) + " 天<br><br>" +  # ← 添加额外换行
            "最近付款发票日期: " + filtered_forecast['发票日期'].astype(str) + "<br>" +
            "最近开支票日期: " + filtered_forecast['开支票日期'].astype(str) + "<br>" +
            "支票号: " + filtered_forecast['付款支票号'].astype(str) + "<br>" +
            "付款支票总额: " + filtered_forecast['付款支票总额'].map('{:,.2f}'.format)
        )


        # ✅ 5. 创建柱状图
        fig_company = px.bar(
            filtered_forecast,
            x='公司名称',
            y='应付未付',
            text='应付未付',
            color='应付未付',
            color_continuous_scale='Oranges',
            labels={'应付未付': '应付款金额'},
            #title=f"{selected_forecast_dept} 部门 - 本周应付款公司明细",
            hover_data={'hover_text': True, '应付未付': False, '公司名称': True}
        )

        # ✅ 6. 图表美化
        fig_company.update_traces(
            texttemplate='%{text:.2f}',
            textposition='outside',
            hovertemplate='%{customdata[0]}<extra></extra>'
        )
        fig_company.update_layout(xaxis_tickangle=-30)

        # ✅ 7. 展示图表
        st.plotly_chart(fig_company, use_container_width=True)


        #st.info("⚠️ 注意：以下图表仅展示本周应付未付金额大于 0 的公司。")
        #st.dataframe(df_gestion_unpaid)


        # ✅ 1. 筛选出“是否本周应付”为 True 的数据
        df_this_week = df_paid_forest[df_paid_forest['是否本周应付'] == True].copy()

        # ✅ 2. 按“发票号”分组并汇总发票金额和实际支付金额
        grouped_cheque = df_this_week.groupby('发票号', as_index=False)[
            ['发票金额', '实际支付金额']
        ].sum().round(2)

        # ✅ 3. 计算“应付未付”字段
        grouped_cheque['应付未付'] = grouped_cheque['发票金额'] - grouped_cheque['实际支付金额']

        # ✅ 4. 过滤掉“应付未付”为 0 的行
        grouped_cheque = grouped_cheque[grouped_cheque['应付未付'] != 0]

        # ✅ 5. 获取这些“发票号”作为布林码条件
        valid_invoice_ids = grouped_cheque['发票号'].unique()

        # ✅ 6. 回到原始数据中，筛选出这些发票号对应的明细行
        filtered_invoice_details = df_this_week[df_this_week['发票号'].isin(valid_invoice_ids)].copy()

        # ✅ 7. 展示最终筛选出的原始数据
        #st.subheader("📋 存在应付未付的发票明细")
        #st.dataframe(filtered_invoice_details, use_container_width=True)

        # ✅ 指定需要显示的字段
        display_columns = [
            '公司名称', '部门', '发票号', '发票日期','发票金额', '应付未付',
            '预计付款日', '付款支票号', '实际支付金额', '付款支票总额'
        ]

        # ✅ 确保日期字段格式正确
        date_columns = ['预计付款日','发票日期']
        for col in date_columns:
            filtered_invoice_details[col] = pd.to_datetime(filtered_invoice_details[col], errors='coerce').dt.strftime('%Y-%m-%d')   
        
        
        # ✅ 折叠模块
        with st.expander("📂 点击展开查看本周存在应付未付的发票详情", expanded=False):

            # ✅ 选择查看模式：预测未付 or 全部应付未付
            view_mode = st.radio(
                "请选择查看模式：",
                ["📈 预测应付未付", "📑 全部应付未付", "💵 已付信息查询", "🧾 已付支票号查询"],
                horizontal=True
            )

            # ✅ 模式 1：预测未付应付（使用原始 filtered_invoice_details）
            if view_mode == "📈 预测应付未付":

                # 公司选择器
                selected_company = st.selectbox(
                    "🔍 请选择要查看的公司（预测数据）：",
                    options=sorted(filtered_invoice_details['公司名称'].dropna().unique().tolist()),
                    index=None,
                    placeholder="输入或选择公司名称"
                )

                if selected_company:
                    company_df = (
                        filtered_invoice_details[filtered_invoice_details['公司名称'] == selected_company]
                        .copy().sort_values(by='发票日期')
                    )
                    display_df = company_df[display_columns].copy()

                    # 汇总行
                    amount_cols = ['发票金额', '应付未付', '实际支付金额', '付款支票总额']
                    summary_row = display_df[amount_cols].sum().round(2)
                    summary_row['公司名称'] = '总计'
                    summary_row['部门'] = ''
                    summary_row['发票号'] = ''
                    summary_row['预计付款日'] = ''
                    summary_row['付款支票号'] = ''
                    display_df = pd.concat([display_df, pd.DataFrame([summary_row])], ignore_index=True)

                    # 样式
                    def highlight_total_row(row):
                        return ['background-color: #e6f0ff'] * len(row) if row['公司名称'] == '总计' else [''] * len(row)

                    styled_df = (
                        display_df
                        .style
                        .apply(highlight_total_row, axis=1)
                        .format({col: '{:,.2f}' for col in amount_cols})
                    )

                    st.dataframe(styled_df, use_container_width=True)

            # ✅ 模式 2：全部应付未付（来自 df_gestion_unpaid）
            elif view_mode == "📑 全部应付未付":

                # 数据处理
                df_unpaid_total = df_gestion_unpaid.copy()
                df_unpaid_total = df_unpaid_total.groupby('发票号', as_index=False).agg({
                    '发票金额': 'sum',
                    'TPS': 'sum',
                    'TVQ': 'sum',
                    '应付未付': 'sum',
                    '公司名称': 'first',
                    '部门': 'first',
                    '发票日期': 'first'
                })
                df_unpaid_total = df_unpaid_total[df_unpaid_total['应付未付'] != 0]

                # 公司选择器
                selected_company_all = st.selectbox(
                    "🔍 请选择要查看的公司（全部应付未付）：",
                    options=sorted(df_unpaid_total['公司名称'].dropna().unique().tolist()),
                    index=None,
                    placeholder="输入或选择公司名称"
                )

                if selected_company_all:
                    company_df = (
                        df_unpaid_total[df_unpaid_total['公司名称'] == selected_company_all]
                        .copy().sort_values(by='发票日期')
                    )

                    # 补全 display_columns 中没有的列
                    for col in display_columns:
                        if col not in company_df.columns:
                            company_df[col] = ''

                    display_df = company_df[display_columns].copy()

                    # # 汇总
                    # amount_cols = ['发票金额', '应付未付']
                    # for col in amount_cols:
                    #     if col not in display_df.columns:
                    #         display_df[col] = 0.0

                    # summary_row = display_df[amount_cols].sum().round(2)
                    # summary_row['公司名称'] = '总计'
                    # summary_row['部门'] = ''
                    # summary_row['发票号'] = ''
                    # summary_row['发票日期'] = ''
                    # display_df = pd.concat([display_df, pd.DataFrame([summary_row])], ignore_index=True)

                    # display_df['发票日期'] = pd.to_datetime(display_df['发票日期'], errors='coerce').dt.strftime('%Y-%m-%d')




                    # 增加 预测付款日期 以及 付款天数中位数 两列信息，方便用户查看使用
                    
                    # 首先使用 本节部分的数据集 display_df， 以及在开始时计算的 result_paid_days 按照 部门 + 公司名称 计算出来的付款天数中位数
                    # 将两个数据集进行 merge 合并
                    display_df = display_df.merge(
                        result_paid_days[['部门', '公司名称', '付款天数中位数']],
                        on=['部门', '公司名称'],
                        how='left'
                    )

                    # 因为涉及到后面的日期相加，因此不必须保证是 日期格式 和 数值格式 
                    # 发票日期必须是 datetime 类型
                    display_df['发票日期'] = pd.to_datetime(display_df['发票日期'], errors='coerce')

                    # 中位付款天数必须是数字
                    display_df['付款天数中位数'] = pd.to_numeric(display_df['付款天数中位数'], errors='coerce')

                    # 生成 timedelta 类型
                    timedelta_days = pd.to_timedelta(display_df['付款天数中位数'], unit='D')


                    # 构造掩码：只有在发票日期和付款天数都存在时才进行运算
                    mask_valid = display_df['发票日期'].notna() & timedelta_days.notna()

                    # 初始化结果列为 NaT
                    display_df['预计付款日'] = pd.NaT

                    # 执行有效行的加法操作
                    display_df.loc[mask_valid, '预计付款日'] = display_df.loc[mask_valid, '发票日期'] + timedelta_days[mask_valid]

                    # 为了显示，将日期转换为字符串
                    display_df['发票日期'] = pd.to_datetime(display_df['发票日期'], errors='coerce').dt.strftime('%Y-%m-%d')
                    display_df['预计付款日'] = display_df['预计付款日'].dt.strftime('%Y-%m-%d')
                    
                    # 在 Streamlit 中直接格式化显示 不想显示为50.0000000  而只是显示为 50
                    # .round(0).astype('Int64') 
                    # 是否会影响数值计算？   ✅ 会 改变原始的浮点数精度，但只要你不再需要小数部分，就不会有问题。
                    display_df['付款天数中位数'] = display_df['付款天数中位数'].round(0).astype('Int64')


                    # 删除 0 的行, 因为公式计算可能出现 -0.00 的情况，为了规避这个问题，注意 0 =/= -0
                    # 我们采用 display_df[~np.isclose(display_df['应付未付'], 0, atol=1e-6)]
                    display_df['应付未付'] = pd.to_numeric(display_df['应付未付'], errors='coerce')
                    display_df = display_df[~np.isclose(display_df['应付未付'], 0, atol=1e-6)]




                    # ✅ 新增 累计未付金额 列， 统计 累计未付金额 总额 

                    # ✅ 第1步：确保“应付未付”为数值型，并计算“累计未付金额”
                    display_df['应付未付'] = pd.to_numeric(display_df['应付未付'], errors='coerce').fillna(0)
                    # ⬆️ 把“应付未付”这一列转为数值型（如果有无法识别的内容就转成NaN），并用0填充缺失值

                    display_df['累计未付金额'] = display_df['应付未付'].cumsum().round(2)
                    # ⬆️ 新增一列“累计未付金额”，为“应付未付”的累计和，并保留两位小数

                    # ✅ 第2步：指定要显示的列顺序，并排除不存在的列
                    desired_order = [
                        '公司名称', '部门', '发票号', '发票日期', '发票金额',
                        '应付未付', '累计未付金额', '预计付款日', '付款天数中位数'
                    ]
                    display_df = display_df[[col for col in desired_order if col in display_df.columns]]
                    # ⬆️ 只保留并重新排列指定的列，如果某列不存在，则自动跳过，避免报错

                    # ✅ 第3步：添加“总计”行，但不汇总“累计未付金额”
                    total_row = {
                        '公司名称': '总计',                  # 显示为“总计”
                        '部门': '',                        # 空字符串避免显示NaN
                        '发票号': '',
                        '发票日期': '',
                        '发票金额': display_df['发票金额'].sum(),     # 发票金额求和
                        '应付未付': display_df['应付未付'].sum(),     # 应付未付求和
                        '累计未付金额': np.nan,               # 设置为空值，避免显示累计值
                        '预计付款日': '',
                        '付款天数中位数': ''
                    }
                    display_df = pd.concat([display_df, pd.DataFrame([total_row])], ignore_index=True)
                    # ⬆️ 将“总计”这一行添加到表格最后，并重新索引

                    # ✅ 第4步：定义样式函数，为“总计”行设置浅蓝色背景
                    def highlight_total_row(row):
                        return ['background-color: #e6f0ff'] * len(row) if row['公司名称'] == '总计' else [''] * len(row)
                    # ⬆️ 如果某行“公司名称”为“总计”，就整行变为浅蓝色，否则保持默认

                    # ✅ 第5步：格式化金额列（包括累计未付金额），保留千分位与小数点后两位
                    styled_df = (
                        display_df
                        .style
                        .apply(highlight_total_row, axis=1)  # 应用背景色函数
                        .format({
                            '发票金额': '{:,.2f}',
                            '应付未付': '{:,.2f}',
                            '累计未付金额': '{:,.2f}'        # 虽然不参与总计，但也需要格式美化
                        })
                    )

                    # ✅ 第6步：使用 Streamlit 显示美化后的表格
                    st.dataframe(styled_df, use_container_width=True)
                    # ⬆️ 表格占满宽度显示





            
            elif view_mode == "💵 已付信息查询":
                
                # 假设 df_paid_days 已加载
                df_paid = df_paid_days.copy()

                # ✅ 设定展示字段
                display_columns = [
                    '公司名称', '发票号', '发票日期', '发票金额',
                    '付款支票号', '实际支付金额', '付款支票总额',
                    '开支票日期', '银行对账日期'
                ]

                # ✅ 公司名称搜索框
                company_list = sorted(df_paid['公司名称'].dropna().unique().tolist())
                selected_company = st.selectbox(
                    "🔍 请输入或选择公司名称查看已开支票信息：",
                    options=company_list,
                    index=None,
                    placeholder="输入公司名称..."
                )

                # ✅ 过滤并显示结果
                if selected_company:
                    filtered_df = df_paid[df_paid['公司名称'] == selected_company].copy()

                    # ⏰ 转换日期列格式
                    date_cols = ['发票日期', '开支票日期', '银行对账日期']
                    for col in date_cols:
                        filtered_df[col] = pd.to_datetime(filtered_df[col], errors='coerce').dt.strftime('%Y-%m-%d')

                    # 📌 按发票日期从大到小排序
                    filtered_df = filtered_df.sort_values(by='发票日期', ascending=False)

                    # 📋 提取所需字段
                    result_df = filtered_df[display_columns]


                    ### 增加 计算 付款差额 的功能

                    # 新增列：付款差额 = 发票金额 - 实际支付金额
                    result_df['付款差额'] = result_df['发票金额'] - result_df['实际支付金额']
                    # 新增列：累计付款差额 = 付款差额的累计值，保留两位小数
                    result_df['累计付款差额'] = result_df['付款差额'].cumsum().round(2)
                    # 写一个提示 st.info
                    st.info(
                        f"⚠️ 提示：本公司累计付款差额为：{result_df['付款差额'].sum():,.2f}"
                        + "\u00A0" * 15 +
                        "负：我方多付" 
                        + "\u00A0" * 9 + 
                        "正：我方少付"
                    )


                    # 控制在最终显示的时候，数值列的数值为 保留 2位小数，这种方式不会改变 原始数列的数据结构
                    # result_df 本身 不变，依然保持 float 类型，可以随时再计算。
                    # .style.format() 只是告诉 Pandas 在渲染时用什么格式显示这些列。
                    # {col: "{:,.2f}" for col in amount_cols} 会为每个指定列应用千分位 + 两位小数格式

                    amount_cols = ['发票金额', '实际支付金额', '付款支票总额','付款差额', '累计付款差额']
                    
                    st.dataframe(
                        result_df.style.format({col: "{:,.2f}" for col in amount_cols}),
                        use_container_width=True
                    )

                

            elif view_mode == "🧾 已付支票号查询":


                # 假设 df_paid_days 已加载
                df_cheque = df_paid_days.copy()

                # ✅ 设定展示字段
                display_columns = [
                    '公司名称', '发票号', '发票日期', '发票金额',
                    '付款支票号', '实际支付金额', '付款支票总额',
                    '开支票日期', '银行对账日期'
                ]

                # ✅ 支票号搜索框
                cheque_list = sorted(df_cheque['付款支票号'].dropna().astype(str).unique().tolist())
                selected_cheque = st.selectbox(
                    "🔍 请输入或选择支票号查看付款信息：",
                    options=cheque_list,
                    index=None,
                    placeholder="输入支票号..."
                )

                # ✅ 若选择了支票号，显示对应信息
                if selected_cheque:
                    filtered_df = df_cheque[df_cheque['付款支票号'] == selected_cheque].copy()

                    # ⏰ 格式化日期列
                    date_cols = ['发票日期', '开支票日期', '银行对账日期']
                    for col in date_cols:
                        filtered_df[col] = pd.to_datetime(filtered_df[col], errors='coerce').dt.strftime('%Y-%m-%d')

                    # 💰 保留两位小数的金额列
                    amount_cols = ['发票金额', '实际支付金额', '付款支票总额']
                    for col in amount_cols:
                        filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce').round(2)

                    # ➕ 计算差额列 = 发票金额 - 实际支付金额
                    filtered_df['差额'] = (filtered_df['发票金额'] - filtered_df['实际支付金额']).round(2)

                    # 📌 按发票日期从大到小排序
                    filtered_df = filtered_df.sort_values(by='发票日期', ascending=False)

                    # ✅ 自定义字段顺序，将“差额”插入到“付款支票总额”之后
                    base_columns = [
                        '公司名称', '发票号', '发票日期', '发票金额',
                        '付款支票号', '实际支付金额', '付款支票总额'
                    ]
                    final_columns = base_columns + ['差额', '开支票日期', '银行对账日期']

                    result_df = filtered_df[final_columns]

                    st.dataframe(result_df, use_container_width=True)










