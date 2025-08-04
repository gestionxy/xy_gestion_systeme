import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from modules.data_loader import load_supplier_data
from modules.data_loader import get_ordered_departments


# ** df_gestion_unpaid ** 是目前处理的最完整的表格，所有的后续处理均使用这张表格

def analyse_des_impayes():

    df = load_supplier_data()


    # 此步骤处理与 analyser_cycle_et_prevoir_paiements.py 中，处理逻辑一致

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
        #selected_dept = st.selectbox("请选择一个部门查看其公司明细：", by_department['部门'].unique())
        #filtered = by_department_company[by_department_company['部门'] == selected_dept]

        # ✅ 定义你希望优先显示的部门顺序
        # 定义的部门顺序函数 位于 data_loader.py， 函数名：get_ordered_departments，可前往查看详细版本
        #departments, default_dept_index = get_ordered_departments(by_department_company)
        #selected_dept = st.selectbox("🏷️ 选择部门", departments, index=default_dept_index, key="dept_select")

        # ✅ 使用统一排序函数获取部门列表和默认选项
        departments, default_dept_index = get_ordered_departments(by_department_company)
        selected_dept = st.selectbox("🏷️ 选择部门查看公司明细", departments, index=default_dept_index, key="dept_detail_select")

        # ✅ 按部门筛选数据
        filtered = by_department_company[by_department_company['部门'] == selected_dept]



        # ✅ 判断公司数量，若超过20，仅显示应付未付金额前20的公司
        company_count = filtered['公司名称'].nunique()
        if company_count > 20:
            top_companies = (
                filtered.groupby('公司名称')['应付未付']
                .sum()
                .sort_values(ascending=False)
                .head(20)
                .index.tolist()
            )
            filtered = filtered[filtered['公司名称'].isin(top_companies)]


        st.info("⚠️ 若部门下属的公司超过20家，则仅显示应付未付金额前20的公司。")



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





   