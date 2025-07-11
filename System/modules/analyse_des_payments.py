
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

import plotly.express as px

from modules.data_loader import load_supplier_data
from modules.data_loader import get_ordered_departments

# 实际付款金额
def analyse_des_payments():
    """
    📊 analyse_des_payments 函数：付款数据分析模块

    功能说明：
    --------------------
    1. 从数据源加载供应商付款数据；
    2. 清洗发票与支票日期字段；
    3. 对标记为“待付款”的公司，模拟“发票后10天自动付款”逻辑；
    4. 计算应付未付金额；
    5. 提取已付款数据，生成付款月份字段，为图表等后续分析做准备；
    6. 提供说明信息。

    使用依赖：
    - 函数 `load_supplier_data()`：从本地或外部源加载付款数据。
    - Streamlit、Pandas、Plotly。
    """

    # 1️⃣ 加载原始数据
    df = load_supplier_data()

    # 2️⃣ 转换日期字段为 pandas datetime 类型
    df['发票日期'] = pd.to_datetime(df['发票日期'], errors='coerce')
    df['开支票日期'] = pd.to_datetime(df['开支票日期'], errors='coerce')

    # 3️⃣ 获取当前日期（用于计算“发票后+10天”的截止逻辑）
    current_date = pd.to_datetime(datetime.today().date())

    # 4️⃣ 构建部门颜色映射字典（用于后续图表显示）
    unique_departments_paid = sorted(df['部门'].dropna().unique())
    colors_paid = px.colors.qualitative.Dark24  # Plotly内置高对比色板（24色）

    color_map_paid = {
        dept: colors_paid[i % len(colors_paid)]
        for i, dept in enumerate(unique_departments_paid)
    }

    # 5️⃣ 复制原始数据用于模拟付款逻辑
    df_gestion_unpaid = df.copy()

    # 6️⃣ 识别【公司名称结尾为 *】且尚未付款（无开支票日期）的行
    mask_star_company = df_gestion_unpaid['公司名称'].astype(str).str.endswith("*")
    mask_no_cheque_date = df_gestion_unpaid['开支票日期'].isna()
    mask_star_and_pending = mask_star_company & mask_no_cheque_date

    # 7️⃣ 找出逾期未付款：发票日期 + 10天 < 当前日期
    condition_overdue = (
        mask_star_and_pending &
        (df_gestion_unpaid['发票日期'] + pd.Timedelta(days=10) < current_date)
    )

    # 8️⃣ 对逾期行设置模拟“自动付款”
    df_gestion_unpaid.loc[condition_overdue, '开支票日期'] = \
        df_gestion_unpaid.loc[condition_overdue, '发票日期'] + pd.Timedelta(days=10)

    df_gestion_unpaid.loc[condition_overdue, '实际支付金额'] = \
        df_gestion_unpaid.loc[condition_overdue, '发票金额']

    df_gestion_unpaid.loc[condition_overdue, '付款支票总金额'] = \
        df_gestion_unpaid.loc[condition_overdue, '发票金额']

    # 9️⃣ 计算“应付未付金额”列
    df_gestion_unpaid['应付未付'] = (
        df_gestion_unpaid['发票金额'].fillna(0) - df_gestion_unpaid['实际支付金额'].fillna(0)
    )

    # 🔟 创建付款分析专用副本（仅包含有效付款数据）
    df_paid = df_gestion_unpaid.copy()

    # 🔄 清理数据：仅保留已付款记录（有开支票日期与实际支付金额）
    df_paid_cheques = df_paid.dropna(subset=['开支票日期', '实际支付金额'])
    paid_df = df_paid_cheques[df_paid_cheques['实际支付金额'].notna()]

    # 🗓️ 添加付款月份字段（用于图表按月聚合分析）
    paid_df['开支票日期'] = pd.to_datetime(paid_df['开支票日期'])  # 保底确保为时间格式
    paid_df['月份'] = paid_df['开支票日期'].dt.to_period('M').astype(str)

    # ✅ 展示说明文字
    st.info("📌 **付款金额说明：** 以上数据基于实际付款记录进行分析。")
    st.info("💡 **自动付款规则：** 对于付款方式为 PPA / Debit / ETF 的供应商，默认在发票开出后 10 天视为已付款。")

    # 创建选择视图按钮
    chart_type = st.radio(
        "请选择视图：", 
        ['📆 部门月度付款趋势', '📅 部门周度付款趋势', '🏢 公司周度付款状态','📊 公司付款时间间隔与金额分布'], 
        index=0, 
        horizontal=True
    )




    # 图1：周度付款图（仅当用户选择周度时生成）
    if chart_type == '📆 部门月度付款趋势':
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
        #unique_departments_paid = sorted(paid_summary['部门'].unique())
        

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

        st.plotly_chart(fig_paid_month, key="monthly_paid_chart001")



    # 图2：周度付款图（仅当用户选择周度时生成）
    if chart_type == '📅 部门周度付款趋势':
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


    elif chart_type == '🏢 公司周度付款状态':
        st.markdown("### 🏢 选择月份和部门，查看公司付款趋势")

        # 月份选择
        valid_months = sorted(paid_df['月份'].unique())
        current_month_str = datetime.now().strftime("%Y-%m")
        default_index = valid_months.index(current_month_str) if current_month_str in valid_months else len(valid_months) - 1
        selected_month = st.selectbox("📅 选择月份", valid_months, index=default_index)

        # 部门选择
        # 此处引用 data_loader.py 中的 get_ordered_departments 函数, 使用的是 paid_df 数据库
        departments, default_dept_index = get_ordered_departments(paid_df)
        selected_dept = st.selectbox("🏷️ 选择部门", departments, index=default_dept_index, key="dept_select")

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
        # ❌ 原始写法为什么出错？ 你用了 week_total_dict[row['周范围']]，当某个“周范围”不在字典中时，会抛出 KeyError，
        # 导致 .apply() 执行失败，返回了异常结构，不能赋值给一列 → 报错。
        # .get() 会在找不到键时返回一个默认值（比如 0），不会报错，这样 .apply() 就能顺利对每一行返回一个字符串，最终结果是 一列字符串数据，可以正常赋值。
        company_week_summary['提示信息'] = company_week_summary.apply(
            lambda row: #f"所选周总支付金额：{week_total_dict[row['周范围']]:,.0f}<br>"
                        f"所选周总支付金额：{week_total_dict.get(row['周范围'], 0):,.0f}<br>"
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
            title=f"{selected_month} - {selected_dept} 各公司每周付款状态",
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



    elif chart_type == '📊 公司付款时间间隔与金额分布':
        
        paid_df['周开始'] = paid_df['开支票日期'] - pd.to_timedelta(paid_df['开支票日期'].dt.weekday, unit='D')
        paid_df['周结束'] = paid_df['周开始'] + timedelta(days=6)
        paid_df['周范围'] = paid_df['周开始'].dt.strftime('%Y-%m-%d') + ' ~ ' + paid_df['周结束'].dt.strftime('%Y-%m-%d')


        # 2. 交互组件

        # ✅ 定义你希望优先显示的部门顺序
        # 定义的部门顺序函数 位于 data_loader.py， 函数名：get_ordered_departments，可前往查看详细版本
        departments, default_dept_index = get_ordered_departments(paid_df)
        selected_dept = st.selectbox("🏷️ 选择部门", departments, index=default_dept_index, key="dept_select")


        company_list = sorted(df[df['部门'] == selected_dept]['公司名称'].unique())
        company_list = ['全部'] + company_list  # 添加“全部”选项至顶部

        company_mode = st.selectbox("公司选择模式", ["全部公司", "手动选择公司"])

        if company_mode == "全部公司":
            selected_companies = company_list[1:]  # 自动全选全部公司（排除“全部”）
        else:
            selected_companies = st.multiselect("🏢 手动选择公司", company_list[1:], default=company_list[1:])


        date_range = st.date_input("📆 选择日期范围", [df['发票日期'].min(), df['发票日期'].max()])


        # 3. 数据筛选
        filtered_df = paid_df[(paid_df['部门'] == selected_dept) &
                        (paid_df['公司名称'].isin(selected_companies)) &
                        (paid_df['开支票日期'] >= pd.to_datetime(date_range[0])) &
                        (paid_df['开支票日期'] <= pd.to_datetime(date_range[1]))]

        if filtered_df.empty:
            st.warning("❗ 当前筛选条件下没有数据。请调整部门、公司或时间范围。")
            st.stop()

        # 分组聚合后用于绘图的数据
        scatter_df = (
            filtered_df.groupby(['公司名称', '周范围', '周开始'])['实际支付金额']
            .sum()
            .reset_index()
        )

        scatter_df['实际支付金额'] = scatter_df['实际支付金额'].round(2)

        #st.dataframe(scatter_df)

        # 为了避免在气泡图（scatter bubble chart）中出现无效或报错的点，因为 size= 参数要求必须是正数。
        scatter_df = scatter_df[scatter_df['实际支付金额'] > 0]

        # 自动判断显示的公司数量逻辑
        company_counts = scatter_df['公司名称'].nunique()

        if company_counts <= 20:
            companies_to_show = scatter_df['公司名称'].unique()
        else:
            # 仅保留采购金额前20的公司
            companies_to_show = (
                scatter_df.groupby('公司名称')['实际支付金额'].sum()
                .sort_values(ascending=False)
                .head(20)
                .index.tolist()
            )

        # 过滤数据，仅保留要显示的公司
        scatter_df = scatter_df[scatter_df['公司名称'].isin(companies_to_show)]

        # ✅ 手动计算公司总采购金额排序
        company_order = (
            scatter_df.groupby("公司名称")["实际支付金额"]
            .sum()
            .sort_values(ascending=True)
            .index.tolist()
        )

        # ✅ 设置公司名称为有序分类变量，顺序由总金额决定（从大到小）
        # 使用 pd.Categorical()，给“公司名称”列明确指定一个排序顺序 company_order（比如金额从高到低），并声明这是有序的
        
        scatter_df["公司名称"] = pd.Categorical(
            scatter_df["公司名称"],         # 要处理的列
            categories=company_order,      # 自定义排序的公司顺序列表
            ordered=True                   # 表明这些公司是有顺序关系的
        )

        #st.dataframe(scatter_df)

        # ✅ 排序周开始字段，确保 X 轴按时间排列
        scatter_df = scatter_df.sort_values(by='周开始')

        #st.dataframe(scatter_df)

        # 绘制气泡图
        fig = px.scatter(
            scatter_df,
            x="周开始",
            y="公司名称",
            size="实际支付金额",
            color="公司名称",
            hover_data={"实际支付金额": True, "周范围": True, "周开始": False},
            title="公司实际付款时间间隔与金额分布"
        )

        # ✅ 去掉 Plotly 的自动排序，否则会干扰我们手动设定的顺序
        fig.update_layout(
            yaxis=dict(categoryorder="array", categoryarray=company_order),
            height=max(500, len(companies_to_show) * 30)
        )



        st.info("⚠️ y 轴表示公司名称，按实际支付金额从大到小排序。若公司数超过 20，仅显示前 20 家。")


        st.plotly_chart(fig, use_container_width=True)
        #st.dataframe(scatter_df[['公司名称', '发票金额']].groupby('公司名称').sum().sort_values('发票金额', ascending=False))


