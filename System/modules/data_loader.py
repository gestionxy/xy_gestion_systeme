import pandas as pd
import streamlit as st

# 加载数据函数，设置缓存时间为 10 秒
@st.cache_data(ttl=3600)

def load_supplier_data():
    # Google Sheet 文件的 ID（你提供的链接）
    file_id = "1qH_odKEPlDrLTM8B8UfsMzW6Uu9ciDUW"

    # Google Sheet 的 CSV 导出地址
    csv_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"

    # 读取 CSV 数据（从 Google Sheets）
    df = pd.read_csv(csv_url)
    df = df.dropna(how='all')

    # 自动转换常用日期字段为 datetime 类型（可按需扩展）
    date_columns = ['开支票日期', '发票日期','银行对账日期']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # 强制转换为字符串以避免 Streamlit 警告
    string_columns = ['付款支票号', '发票号', '公司名称']
    for col in string_columns:
        if col in df.columns:
            df[col] = df[col].astype(str)

    return df


def load_cash_data():
    # Google Sheet 文件的 ID（你提供的链接）
    file_id = "1U6Xx5mhzCkjd6l4UQ7rOjFq4WQkNpQEK"

    # Google Sheet 的 CSV 导出地址
    csv_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"

    # 读取 CSV 数据（从 Google Sheets）
    df_data = pd.read_csv(csv_url)


    # ✅ 步骤 1：读取 Excel 文件
    df_data = df_data.dropna(how='all')  # 删除完全为空的行

    # ✅ 步骤 2：统一日期和金额格式
    df_data['小票日期'] = pd.to_datetime(df_data['小票日期'], errors='coerce').dt.strftime('%Y-%m-%d')  # 格式化为 yyyy-mm-dd 字符串
    df_data['开票日期'] = pd.to_datetime(df_data['开票日期'], errors='coerce')  # 保持为 datetime 类型以便后续提取年月
    
    # 会计核算日期 指 这些现金账 具体放在哪个月份进行处理
    df_data['会计核算日期'] = pd.to_datetime(df_data['会计核算日期'], errors='coerce') 

    # ✅ 保留“开票日期”非空的数据
    #df_data = df_data[df_data['开票日期'].notna()]
    df_data = df_data[df_data['会计核算日期'].notna()]

    # ✅ 金额字段转换为浮点并保留两位小数
    for col in ['总金额', 'TPS', 'TVQ', '支票金额']:
        df_data[col] = pd.to_numeric(df_data[col], errors='coerce').round(2)

    # ✅ 步骤 3：添加“年月”列（格式：2025-02）
    #df_data['年月'] = df_data['开票日期'].dt.to_period('M').astype(str)
    df_data['年月'] = df_data['会计核算日期'].dt.to_period('M').astype(str)

    # ✅ 步骤 4 : 添加 净值 列
    # 只要其中任意一个值为 NaN，该行计算出的 '净值' 也会是 NaN。 这是因为在 Pandas 中，任何数值与 NaN 参与运算，结果都将是 NaN。
    # .fillna(0) 在这里只是返回一个临时替换了空值的新 Series，并没有写回原来的 DataFrame， 即不改变原数据库内容。
    df_data['净值'] = df_data['总金额'] - df_data['TPS'].fillna(0) - df_data['TVQ'].fillna(0)



    # 强制转换为字符串以避免 Streamlit 警告
    string_columns = ['支票号', '公司名称']
    for col in string_columns:
        if col in df_data.columns:
            df_data[col] = df_data[col].astype(str)

    return df_data

def get_ordered_departments(df, column_name="部门", priority_order=None, default_name="杂货"):
    """
    根据给定的优先顺序对部门进行排序。
    
    参数：
    - df: 包含部门列的 DataFrame
    - column_name: 部门列的列名（默认为 "部门"）
    - priority_order: 优先排序的部门列表（None 时使用默认顺序）
    - default_name: 默认选中的部门名称（默认为 "杂货"）

    返回：
    - departments: 排序后的部门列表
    - default_index: 默认部门在列表中的索引位置
    """

    if priority_order is None:
        priority_order = ["杂货", "菜部", "冻部", "肉部", "鱼部", "厨房", "牛奶生鲜", "酒水", "面包"]

    # 1. 获取所有不为空的唯一部门
    all_departments = sorted(df[column_name].dropna().unique())

    # 2. 先保留出现在数据库中的优先部门
    ordered_preferred = [dept for dept in priority_order if dept in all_departments]

    # 3. 其他剩余部门按字母排序
    remaining_departments = sorted([dept for dept in all_departments if dept not in ordered_preferred])

    # 4. 拼接最终排序列表
    departments = ordered_preferred + remaining_departments

    # 5. 确定默认部门索引
    default_index = departments.index(default_name) if default_name in departments else 0

    return departments, default_index
