import pandas as pd
import json
from sqlalchemy.orm import Session
from ..models import models
from datetime import datetime
import io

class ContactService:
    @staticmethod
    def process_csv(db: Session, file_content: bytes, list_name: str):
        # 尝试不同的编码格式读取
        df = None
        read_errors = []
        
        # 常见编码尝试顺序 (优先尝试 utf-8-sig 以处理 BOM)
        encodings = ['utf-8-sig', 'gb18030', 'gbk', 'utf-16']
        # 常见分隔符
        separators = [',', '\t', ';']
        
        import io
        
        for encoding in encodings:
            if df is not None: break
            for sep in separators:
                try:
                    # 尝试读取
                    temp_df = pd.read_csv(io.BytesIO(file_content), encoding=encoding, sep=sep)
                    
                    # 调试日志
                    print(f"尝试读取 {encoding} | {sep} -> 列名: {list(temp_df.columns)}")

                    # 简单验证：必须读出了列
                    # 关键判定标准：是否包含 EmailAddr (不区分大小写)
                    found_email = False
                    
                    # 检查是否因为分隔符错误导致所有内容挤在第一列
                    if len(temp_df.columns) == 1:
                        col_name = str(temp_df.columns[0])
                        # 如果列名里包含 \t 或 ; 说明分隔符不对，应该跳过当前 sep
                        if '\t' in col_name or ';' in col_name or ',' in col_name:
                            continue
                            
                    for c in temp_df.columns:
                        clean_col = str(c).lower().strip().replace('\ufeff', '')
                        if 'emailaddr' in clean_col:
                            found_email = True
                            break
                    
                    if found_email:
                        df = temp_df
                        print(f"成功识别格式: {encoding} | {sep}")
                        break
                    
                    # 兼容性 fallback: 找 'email'
                    if len(temp_df.columns) > 1:
                         if any('email' in str(c).lower() for c in temp_df.columns):
                             df = temp_df
                             print(f"模糊识别成功 (email): {encoding} | {sep}")
                             break
                except Exception as e:
                    # read_errors.append(f"{encoding}/{sep}: {str(e)}")
                    continue
        
        if df is None:
             # Last resort: 终极手段，手动将所有 Tab 替换为逗号再读取
             try:
                 for enc in ['utf-16', 'utf-8-sig', 'gb18030']:
                     try:
                         text_content = file_content.decode(enc)
                         if '\t' in text_content:
                             # 替换 Tab 为逗号，并处理掉可能干扰的引号
                             csv_ready_text = text_content.replace('\t', ',')
                             df = pd.read_csv(io.StringIO(csv_ready_text))
                             if len(df.columns) > 1 and any('email' in str(c).lower() for c in df.columns):
                                 print(f"终极手段成功：使用 {enc} 并转换 Tab 为逗号")
                                 break
                     except:
                         continue
             except:
                 pass

        if df is None:
             raise ValueError(f"无法解析文件。请确保文件包含 EmailAddr 列。尝试的格式均失败。")

        # 1. 强力补救：如果 df 只有一列，且列名或第一行包含 \t，说明分隔符识别失败，强制 split
        if df is not None and len(df.columns) == 1:
            col_name = str(df.columns[0])
            first_val = str(df.iloc[0, 0]) if not df.empty else ""
            
            # 检测是否含有 Tab
            if '\t' in col_name or '\t' in first_val:
                print("检测到未分割的 Tab 数据，执行强制拆分...")
                # 重新读取，强制使用 sep='\t'
                try:
                    # 注意：这里我们无法得知正确的编码，只能尝试最可能的 utf-16 (常见于 Excel 导出) 或 utf-8
                    # 为了稳妥，我们直接操作现有的 df 数据进行 split
                    # 假设 df 是读进来的那个“单列” DataFrame
                    
                    # 获取原始数据（包括表头）
                    # 这种情况下，Pandas 已经把表头当成了列名。我们需要把列名也当做数据的一部分处理
                    
                    # 简单粗暴法：直接用 python 引擎指定 sep='\t' 重读一遍
                    # 我们需要知道刚才成功读取时的 encoding
                    # 由于上面的循环逻辑比较复杂，这里我们简化：如果列名里有 \t，说明刚才用的 sep 错了。
                    pass 
                except:
                    pass

        # 上面的逻辑比较绕，不如在 process_csv 内部循环里直接判断
        # (由于代码结构限制，我们在这里做后处理)
        
        if df is not None and len(df.columns) == 1 and '\t' in str(df.columns[0]):
             # 这是一个典型的 "Excel 导出的 Unicode 文本"，虽然被 read_csv 读进来了，但没分列
             # 我们尝试把这一列拆开
             try:
                 # 获取这一列的数据系列
                 series = df.iloc[:, 0]
                 # 将列名也作为第一行数据加回去（为了重新构建）
                 header_line = df.columns[0]
                 
                 # 使用 csv 模块解析字符串可能更稳，但这里用 pandas split
                 new_df = series.astype(str).str.split('\t', expand=True)
                 
                 # 处理表头：列名里的 \t 也要拆
                 header_parts = header_line.split('\t')
                 
                 # 如果拆出来的列数和表头数量一致
                 if len(header_parts) == len(new_df.columns):
                     new_df.columns = [h.strip() for h in header_parts]
                     df = new_df
                     print("强制拆分 Tab 成功！")
             except Exception as e:
                 print(f"强制拆分失败: {e}")

        # 1. 标准化列名
        # 创建一个映射，把原本的列名映射为干净的列名
        new_columns = {}
        target_col = None
        
        for c in df.columns:
            clean_name = str(c).strip().replace('\ufeff', '')
            new_columns[c] = clean_name
            if 'emailaddr' in clean_name.lower():
                target_col = c # 记录原始列名
        
        # 重命名所有列
        df.rename(columns=new_columns, inplace=True)

        # 再次确认目标列 (因为上面重命名了)
        final_target_col = None
        for c in df.columns:
            if 'emailaddr' in c.lower():
                final_target_col = c
                break
        
        if not final_target_col:
            # 尝试找 email
            for c in df.columns:
                if 'email' in c.lower():
                    final_target_col = c
                    break
        
        if final_target_col:
            df.rename(columns={final_target_col: 'EmailAddr'}, inplace=True)
        else:
             raise ValueError(f"最终未能定位 EmailAddr 列。检测到的列: {list(df.columns)}")
            
        # 2. 清洗数据：剔除 EmailAddr 为空或格式明显不对的行
        df = df[df['EmailAddr'].notna()]
        # 关键修正：确保 EmailAddr 里的 Tab 被去掉了
        df['EmailAddr'] = df['EmailAddr'].astype(str).str.strip().str.replace('\t', '')
        # 简单正则过滤非邮箱
        df = df[df['EmailAddr'].str.contains('@')]
        
        # 3. 去重
        df.drop_duplicates(subset=['EmailAddr'], keep='first', inplace=True)
        
        if df.empty:
            raise ValueError("CSV 文件中没有有效的收件人数据")

        contact_list = models.ContactList(name=list_name, total_count=len(df))
        db.add(contact_list)
        db.commit()
        db.refresh(contact_list)
        
        contacts = []
        # 获取所有变量列名 (排除 EmailAddr)
        # 确保排除的时候是不区分大小写的比较
        var_columns = [c for c in df.columns if c.lower() != 'emailaddr']
        
        print(f"DEBUG: 解析到的变量列: {var_columns}")
        
        for index, row in df.iterrows():
            # 提取所有变量
            extra_vars = {k: str(row[k]) if pd.notna(row[k]) else "" for k in var_columns}
            
            if index == 0:
                print(f"DEBUG: 第一行数据变量: {extra_vars}")
            
            # 特殊处理：如果有 UserName 列，也映射到 contact.name 方便显示
            # 优先找 UserName，其次找 Name/name
            name_key = next((k for k in extra_vars.keys() if k.lower() == 'username'), None)
            if not name_key:
                name_key = next((k for k in extra_vars.keys() if k.lower() == 'name'), None)
                
            name_val = extra_vars.get(name_key, "") if name_key else ""
            
            contact = models.Contact(
                email=row['EmailAddr'],
                name=name_val,
                extra_vars=json.dumps(extra_vars, ensure_ascii=False),
                list_id=contact_list.id
            )
            contacts.append(contact)
            
        # 分批写入数据库
        batch_size = 1000
        for i in range(0, len(contacts), batch_size):
            db.bulk_save_objects(contacts[i:i + batch_size])
            db.commit()
            
        return contact_list

class CampaignService:
    @staticmethod
    def create_campaign(db: Session, name: str, template_id: int, list_id: int, account_name: str, batch_size: int, interval_minutes: int, scheduled_start_time: datetime = None, from_alias: str = None, provider: str = "aliyun"):
        campaign = Campaign(
            name=name,
            provider=provider,
            template_id=template_id,
            list_id=list_id,
            account_name=account_name,
            batch_size=batch_size,
            interval_minutes=interval_minutes,
            scheduled_start_time=scheduled_start_time,
            from_alias=from_alias,
            status="pending"
        )
        db.add(campaign)
        db.commit()
        return campaign
