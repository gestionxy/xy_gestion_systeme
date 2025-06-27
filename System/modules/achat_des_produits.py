import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import plotly.express as px
from modules.data_loader import load_supplier_data

# 采购数据分析 
def achat_des_produits():
#def achat_des_produits():
    # 🔄 加载供应商数据
    df = load_supplier_data()


    # 假设 df 是采购数据，包含：公司名称、部门、发票日期、发票金额
    # 示例结构：df = pd.read_csv("purchase_data.csv")

    # 数据预处理
    # 确保日期字段为 datetime 格式，删除发票金额为空的行
    df['发票日期'] = pd.to_datetime(df['发票日期'], errors='coerce')
    df = df.dropna(subset=['发票金额', '发票日期'])
    df['月份'] = df['发票日期'].dt.to_period('M').astype(str)

    
    st.info("**采购金额**：根据已有发票金额进行统计分析。")
    
    # 视图选择按钮
    chart_type = st.radio(
        "请选择采购视图：", 
        ['📆 部门月度采购', '📅 部门周度采购', '🏢 公司周度采购'], 
        index=0, 
        horizontal=True
    )

    if chart_type == '📆 部门月度采购':
        purchase_summary = df.groupby(['部门', '月份'])['发票金额'].sum().reset_index()
        monthly_totals = df.groupby('月份')['发票金额'].sum().reset_index()
        monthly_totals_dict = monthly_totals.set_index('月份')['发票金额'].to_dict()

        unique_departments = sorted(purchase_summary['部门'].unique())
        colors = px.colors.qualitative.Dark24
        color_map = {dept: colors[i % len(colors)] for i, dept in enumerate(unique_departments)}

        purchase_summary['总采购金额'] = purchase_summary['月份'].map(monthly_totals_dict)
        purchase_summary['提示信息'] = purchase_summary.apply(
            lambda row: f"🔹 {row['月份'][:4]}年{row['月份'][5:]}月 <br>"
                        f"总采购金额：{row['总采购金额']:,.0f}<br><br>"
                        f"部门：{row['部门']}<br>"
                        f"采购金额：{row['发票金额']:,.0f}<br>"
                        f"占比：{row['发票金额'] / row['总采购金额']:.1%}",
            axis=1
        )

        fig_month = px.line(
            purchase_summary,
            x="月份",
            y="发票金额",
            color="部门",
            title="各部门每月采购金额",
            markers=True,
            labels={"发票金额": "采购金额", "月份": "月份"},
            line_shape="linear",
            color_discrete_map=color_map,
            hover_data={'提示信息': True}
        )
        fig_month.update_traces(
            text=purchase_summary["发票金额"].round(0).astype(int),
            textposition="top center",
            hovertemplate="%{customdata[0]}"
        )
        st.plotly_chart(fig_month, key="monthly_purchase_chart")

    elif chart_type == '📅 部门周度采购':
        df['周开始'] = df['发票日期'] - pd.to_timedelta(df['发票日期'].dt.weekday, unit='D')
        df['周结束'] = df['周开始'] + timedelta(days=6)
        df['周范围'] = df['周开始'].dt.strftime('%Y-%m-%d') + ' ~ ' + df['周结束'].dt.strftime('%Y-%m-%d')

        valid_months = sorted(df['月份'].unique())
        current_month_str = datetime.now().strftime("%Y-%m")
        default_index = valid_months.index(current_month_str) if current_month_str in valid_months else len(valid_months)-1
        selected_month = st.selectbox("📅 选择月份", valid_months, index=default_index)

        weekly_summary = df[df['月份'] == selected_month].groupby(
            ['部门', '周范围', '周开始', '周结束']
        )['发票金额'].sum().reset_index().sort_values('周开始')

        weekly_totals = weekly_summary.groupby('周范围')['发票金额'].sum().to_dict()
        weekly_summary['提示信息'] = weekly_summary.apply(
            lambda row: f"周总采购金额：{weekly_totals[row['周范围']]:,.0f}<br>"
                        f"部门：{row['部门']}<br>"
                        f"采购金额：{row['发票金额']:,.0f}<br>"
                        f"占比：{row['发票金额'] / weekly_totals.get(row['周范围'], 1):.1%}",
            axis=1
        )

        fig_week = px.line(
            weekly_summary,
            x="周范围",
            y="发票金额",
            color="部门",
            title=f"{selected_month} 各部门每周采购金额",
            markers=True,
            labels={"发票金额": "采购金额", "周范围": "周"},
            hover_data={'提示信息': True},
            category_orders={"周范围": list(weekly_summary['周范围'].unique())}
        )
        fig_week.update_traces(
            text=weekly_summary["发票金额"].round(0).astype(int),
            textposition="top center",
            hovertemplate="%{customdata[0]}"
        )
        st.plotly_chart(fig_week, key="weekly_purchase_chart")

    elif chart_type == '🏢 公司周度采购':
        st.markdown("### 🏢 选择月份和部门，查看公司周度采购趋势")

        valid_months = sorted(df['月份'].unique())
        current_month_str = datetime.now().strftime("%Y-%m")
        default_index = valid_months.index("2025-06") if "2025-06" in valid_months else len(valid_months)-1
        selected_month = st.selectbox("📅 选择月份", valid_months, index=default_index)

        dept_list = sorted(df['部门'].unique())
        default_dept_index = dept_list.index("杂货") if "杂货" in dept_list else 0
        selected_dept = st.selectbox("🏷️ 选择部门", dept_list, index=default_dept_index)

        df_filtered = df[(df['月份'] == selected_month) & (df['部门'] == selected_dept)].copy()
        df_filtered['周开始'] = df_filtered['发票日期'] - pd.to_timedelta(df_filtered['发票日期'].dt.weekday, unit='D')
        df_filtered['周结束'] = df_filtered['周开始'] + timedelta(days=6)
        df_filtered['周范围'] = df_filtered['周开始'].dt.strftime('%Y-%m-%d') + ' ~ ' + df_filtered['周结束'].dt.strftime('%Y-%m-%d')

        company_week_summary = df_filtered.groupby(
            ['公司名称', '周范围', '周开始', '周结束']
        )['发票金额'].sum().reset_index().sort_values('周开始')

        weekly_totals = company_week_summary.groupby('周范围')['发票金额'].sum().to_dict()
        company_week_summary['提示信息'] = company_week_summary.apply(
            lambda row: f"周总采购金额：{weekly_totals[row['周范围']]:,.0f}<br>"
                        f"公司名称：{row['公司名称']}<br>"
                        f"采购金额：{row['发票金额']:,.0f}<br>"
                        f"占比：{row['发票金额'] / weekly_totals.get(row['周范围'], 1):.1%}",
            axis=1
        )

        fig_company_week = px.line(
            company_week_summary,
            x="周范围",
            y="发票金额",
            color="公司名称",
            title=f"{selected_month} - {selected_dept} 各公司每周采购金额",
            markers=True,
            labels={"发票金额": "采购金额", "周范围": "周"},
            hover_data={'提示信息': True},
            category_orders={"周范围": list(company_week_summary['周范围'].unique())}
        )
        fig_company_week.update_traces(
            text=company_week_summary["发票金额"].round(0).astype(int),
            textposition="top center",
            hovertemplate="%{customdata[0]}"
        )
        st.plotly_chart(fig_company_week, key="company_week_chart")