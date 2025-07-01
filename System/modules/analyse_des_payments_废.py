
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

import plotly.express as px

from modules.data_loader import load_supplier_data

# 实际付款金额
def analyse_des_payments():
    

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



    # 假设已有 df_gestion_unpaid
    df_paid = df_gestion_unpaid.copy()

    # 数据清理
    df_paid_cheques = df_paid.dropna(subset=['开支票日期', '实际支付金额'])
    paid_df = df_paid_cheques[df_paid_cheques['实际支付金额'].notna()]
    paid_df['开支票日期'] = pd.to_datetime(paid_df['开支票日期'])
    paid_df['月份'] = paid_df['开支票日期'].dt.to_period('M').astype(str)

    # 月度汇总
    # 第1步：按“部门”和“月份”进行分组，汇总每组的“实际支付金额”总和
    # groupby(['部门', '月份'])：以“部门”和“月份”这两个字段作为分组键
    # ['实际支付金额']：指定我们只对“实际支付金额”这一列进行操作
    # .sum()：对每个分组计算“实际支付金额”的总和
    # .reset_index()：将分组后的索引还原为普通列（否则结果会是层级索引 MultiIndex）
    paid_summary = paid_df.groupby(['部门', '月份'])['实际支付金额'].sum().reset_index()

    # 第2步：只按“月份”进行分组，计算每个月的总支付金额（不区分部门）
    # 这用于后续计算每个部门在当月付款中的占比
    monthly_totals = paid_df.groupby('月份')['实际支付金额'].sum().reset_index()

    # 第3步：将 monthly_totals 转为字典，以便快速查找某个月份的总金额
    # .set_index('月份')：把“月份”列设置为索引，以便后续按月份快速查值
    # ['实际支付金额']：取出“实际支付金额”这一列作为值
    # .to_dict()：将 Series 转换为字典，格式为 {月份字符串: 实际支付金额总和}
    monthly_totals_dict = monthly_totals.set_index('月份')['实际支付金额'].to_dict()


    # 配色
    # 第1步：提取所有“部门”的唯一值，并按字母顺序排序
    # paid_summary['部门']：提取“部门”这一列（Series）
    # .unique()：提取唯一的部门名称，返回一个 NumPy 数组
    # sorted(...)：将这些部门名按字母顺序进行排序（保证颜色分配一致且可控）
    unique_departments_paid = sorted(paid_summary['部门'].unique())
    
    # 第2步：从 Plotly 提供的内置颜色列表中选择一个配色方案
    # px.colors.qualitative.Dark24：这是 Plotly 提供的一个高对比度的 24 种分类颜色列表，适合用于分类变量（如部门）
    # 每种颜色是一个 HEX 色值字符串，例如 '#2E91E5'
    colors_paid = px.colors.qualitative.Dark24


    # 第3步：为每个部门分配一种颜色，并建立一个“部门 → 颜色”的映射字典
    # 使用枚举 enumerate() 对所有部门及其索引编号进行遍历
    # i % len(colors_paid)：为了避免部门数超过颜色数，使用取模操作实现颜色循环（重复利用颜色）
    # 最终生成 color_map_paid 结构如：{'财务部': '#2E91E5', '销售部': '#E15F99', ...}
    color_map_paid = {
        dept: colors_paid[i % len(colors_paid)]
        for i, dept in enumerate(unique_departments_paid)
    }



    # 添加提示信息（用于 hover）

    # 为每一行添加两列：一列是总支付金额（该月所有部门合计），一列是图表用的悬浮提示信息（HTML格式）

    # 第1步：根据“月份”映射出当月的总支付金额，生成“总支付金额”列
    # map(monthly_totals_dict)：根据月份查找 monthly_totals_dict 中的值，例如 '2025-06' → 182000
    # 最终每一行都有自己对应月份的总支付金额，用于后续计算占比
    paid_summary['总支付金额'] = paid_summary['月份'].map(monthly_totals_dict)

    # 第2步：构建悬浮提示信息（hover tooltip），用于 Plotly 图表中展示每行数据的详细内容
    # apply(..., axis=1)：对 DataFrame 的每一行执行 lambda 函数，拼接格式化的 HTML 字符串
    paid_summary['提示信息'] = paid_summary.apply(
        lambda row: f"🔹 {row['月份'][:4]}年{row['月份'][5:]}月 <br>"                  # 提示标题，例如 "2025年06月"
                    f"支付总金额：{monthly_totals_dict[row['月份']]:,.0f}<br><br>"    # 显示该月所有部门的总支付金额，千位加逗号
                    f"部门：{row['部门']}<br>"                                        # 当前行对应的部门名
                    f"付款金额：{row['实际支付金额']:,.0f}<br>"                        # 当前部门该月的付款金额
                    f"占比：{row['实际支付金额'] / monthly_totals_dict.get(row['月份'], 1):.1%}",  # 当前部门占该月总付款的百分比（例如 12.5%）
        axis=1
    )


    # 图1：绘制月度付款图（折线图）
    fig_paid_month = px.line(
        paid_summary,                    # 输入的数据源 DataFrame，已按“部门”、“月份”汇总
        x="月份",                        # X轴：月份（字符串格式，如 '2025-06'）
        y="实际支付金额",                # Y轴：各部门在该月的付款金额
        color="部门",                    # 按部门分配不同颜色的线
        title="各部门每月实际付款金额",   # 图表标题
        markers=True,                    # 显示折线上各点的标记圆点
        labels={                         # 设置坐标轴标签的中文显示
            "实际支付金额": "实际付款金额",
            "月份": "月份"
        },
        line_shape="linear",             # 折线图线条为直线连接（默认也是 linear）
        color_discrete_map=color_map_paid,  # 自定义颜色映射字典：部门 → 颜色（例如 {"财务部": "#2E91E5", ...}）
        hover_data={'提示信息': True}   # 指定将“提示信息”列添加到 hover 提示中，customdata[0] 即为这一列的值
    )


    # 调整图表中的每条线的样式（使用 Graph Objects 层级操作）
    fig_paid_month.update_traces(
        text=paid_summary["实际支付金额"].round(0).astype(int),  # 点上显示数值标签，四舍五入后为整数
        textposition="top center",                              # 标签显示在点上方居中
        hovertemplate="%{customdata[0]}"                        # 自定义 hover 格式，仅显示提示信息中内容（HTML）
        # 注：customdata[0] 来自 hover_data 中的 '提示信息'，支持 HTML 标签
    )


    st.info("**付款金额**：根据已有付款支票金额进行统计分析。")
    st.info("**付款金额**：对于 PPA / Debit /ETF 则默认 发票日期后10天自动完成付款。")

    # 创建选择视图按钮
    chart_type = st.radio(
        "请选择视图：", 
        ['📆 部门月度付款', '📅 部门周度付款', '🏢 周度公司付款'], 
        index=0, 
        horizontal=True
    )


    # 图2：周度付款图（仅当用户选择周度时生成）
    if chart_type == '📅 部门周度付款':
        valid_months = sorted(paid_df['月份'].unique())
        current_month_str = datetime.now().strftime("%Y-%m")
        default_index = valid_months.index(current_month_str) if current_month_str in valid_months else len(valid_months) - 1
        selected_month = st.selectbox("🔎 选择查看具体周数据的月份", valid_months, index=default_index)

        # 周计算

        # 第1步：计算“周开始”列（即每笔付款所在周的星期一日期）
        # .dt.weekday：返回开支票日期是星期几（0 = 周一，6 = 周日）
        # pd.to_timedelta(..., unit='D')：将 weekday 转换为天数的时间差
        # 用 开支票日期 - weekday天 → 得到该日期所在周的星期一
        paid_df['周开始'] = paid_df['开支票日期'] - pd.to_timedelta(paid_df['开支票日期'].dt.weekday, unit='D')

        # 第2步：计算“周结束”列（即该周的星期日日期）
        # “周开始” + 6天，即为同一周的星期日
        paid_df['周结束'] = paid_df['周开始'] + timedelta(days=6)

        # 第3步：生成“周范围”列（字符串格式），用于图表的 X 轴标签或分组显示
        # 形式为 "2025-06-03 ~ 2025-06-09"
        paid_df['周范围'] = (
            paid_df['周开始'].dt.strftime('%Y-%m-%d') +
            ' ~ ' +
            paid_df['周结束'].dt.strftime('%Y-%m-%d')
        )


        # 筛选所选月份
        


        # 第1步：从已清洗好的付款数据中筛选出用户选择的月份（例如 '2025-06'）对应的所有记录
        # paid_df['月份'] == selected_month：布尔过滤条件，保留只有当前选中月份的数据
        # 目的是只对某一月的数据进行周度分析
        weekly_summary_filtered = paid_df[paid_df['月份'] == selected_month].groupby(
                
                # 第2步：按4个字段分组（每一组将合并为一条记录，求和“实际支付金额”）
                ['部门',       # 部门名（如：财务部、采购部等）
                '周范围',     # 字符串格式的周区间，如 '2025-06-17 ~ 2025-06-23'
                '周开始',     # datetime 类型的本周周一日期，后面用于排序
                '周结束'      # datetime 类型的本周周日日期，仅用于展示完整周范围
                ]
            )['实际支付金额'].sum().reset_index()     # 指定只对“实际支付金额”列进行聚合

            # 第3步：将 groupby 的分组汇总结果转为常规 DataFrame（非层级索引）
            # sum()：对每组计算实际支付金额的总和
            # reset_index()：重建 DataFrame 索引，便于后续使用和绘图
            


        weekly_summary_filtered['周开始'] = pd.to_datetime(weekly_summary_filtered['周开始'])
        weekly_summary_filtered = weekly_summary_filtered.sort_values(by='周开始').reset_index(drop=True)
        weekly_summary_filtered['周范围'] = weekly_summary_filtered['周开始'].dt.strftime('%Y-%m-%d') + ' ~ ' + weekly_summary_filtered['周结束'].dt.strftime('%Y-%m-%d')

        #st.dataframe(paid_df)

        weekly_totals = weekly_summary_filtered.groupby('周范围')['实际支付金额'].sum().reset_index()
        weekly_totals_dict = weekly_totals.set_index('周范围')['实际支付金额'].to_dict()

        weekly_summary_filtered['提示信息'] = weekly_summary_filtered.apply(
            lambda row: f"所选周总支付金额：{weekly_totals_dict[row['周范围']]:,.0f}<br>"
                        f"部门：{row['部门']}<br>"
                        f"实际付款金额：{row['实际支付金额']:,.0f}<br>"
                        f"占比：{row['实际支付金额'] / weekly_totals_dict.get(row['周范围'], 1):.1%}",
            axis=1
        )

        fig_paid_week = px.line(
            weekly_summary_filtered,
            x="周范围",
            y="实际支付金额",
            color="部门",
            title=f"{selected_month} 每周各部门实际付款金额",
            markers=True,
            labels={"实际支付金额": "实际付款金额", "周范围": "周"},
            line_shape="linear",
            color_discrete_map=color_map_paid,
            hover_data={'提示信息': True},
            category_orders={"周范围": list(weekly_summary_filtered['周范围'].unique())}
        )

        fig_paid_week.update_traces(
            text=weekly_summary_filtered["实际支付金额"].round(0).astype(int),
            textposition="top center",
            hovertemplate="%{customdata[0]}"
        )

        st.plotly_chart(fig_paid_week, key="weekly_paid_chart001")


    elif chart_type == '🏢 周度公司付款':
        st.markdown("### 🏢 选择月份和部门，查看公司付款趋势")

        # 月份选择
        valid_months = sorted(paid_df['月份'].unique())
        current_month_str = datetime.now().strftime("%Y-%m")
        default_index = valid_months.index(current_month_str) if current_month_str in valid_months else len(valid_months) - 1
        selected_month = st.selectbox("📅 选择月份", valid_months, index=default_index)

        # 部门选择
        # 获取部门列表并排序
        department_options = sorted(paid_df['部门'].unique())

        # 设置默认索引为“杂货”的位置，如果存在
        default_dept_index = department_options.index("杂货") if "杂货" in department_options else 0

        # 创建选择框，默认选中“杂货”
        selected_dept = st.selectbox("🏷️ 选择部门", department_options, index=default_dept_index)

        # 筛选数据
        df_filtered = paid_df[(paid_df['月份'] == selected_month) & (paid_df['部门'] == selected_dept)]

        # 计算“周开始”和“周结束”
        df_filtered['周开始'] = df_filtered['开支票日期'] - pd.to_timedelta(df_filtered['开支票日期'].dt.weekday, unit='D')
        df_filtered['周结束'] = df_filtered['周开始'] + timedelta(days=6)
        df_filtered['周范围'] = df_filtered['周开始'].dt.strftime('%Y-%m-%d') + ' ~ ' + df_filtered['周结束'].dt.strftime('%Y-%m-%d')

        # 分组：公司 + 周范围
        company_week_summary = df_filtered.groupby(
            ['公司名称', '周范围', '周开始', '周结束']
        )['实际支付金额'].sum().reset_index()

        # 排序 + 重建周范围列
        company_week_summary = company_week_summary.sort_values(by='周开始').reset_index(drop=True)
        company_week_summary['周范围'] = (
            company_week_summary['周开始'].dt.strftime('%Y-%m-%d') +
            ' ~ ' +
            company_week_summary['周结束'].dt.strftime('%Y-%m-%d')
        )

        # 周总额（用于占比提示）
        week_total_dict = company_week_summary.groupby('周范围')['实际支付金额'].sum().to_dict()

        # 提示信息（用于 hover）
        company_week_summary['提示信息'] = company_week_summary.apply(
            lambda row: f"所选周总支付金额：{week_total_dict[row['周范围']]:,.0f}<br>"
                        f"公司名称：{row['公司名称']}<br>"
                        f"实际付款金额：{row['实际支付金额']:,.0f}<br>"
                        f"占比：{row['实际支付金额'] / week_total_dict.get(row['周范围'], 1):.1%}",
            axis=1
        )

        # 绘图
        fig_company_week = px.line(
            company_week_summary,
            x="周范围",
            y="实际支付金额",
            color="公司名称",
            title=f"{selected_month} - {selected_dept} 各公司每周付款趋势",
            markers=True,
            labels={"实际支付金额": "实际付款金额", "周范围": "周"},
            hover_data={"提示信息": True},
            category_orders={"周范围": list(company_week_summary['周范围'].unique())}
        )

        fig_company_week.update_traces(
            text=company_week_summary["实际支付金额"].round(0).astype(int),
            textposition="top center",
            hovertemplate="%{customdata[0]}"
        )

        st.plotly_chart(fig_company_week, use_container_width=True, key="company_week_chart001")

        #st.dataframe(df_filtered)

    else:
        st.plotly_chart(fig_paid_month, key="monthly_paid_chart001")
