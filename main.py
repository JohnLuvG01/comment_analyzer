import asyncio
import os
import sys
from pathlib import Path
from src.analyzer import CommentAnalyzer
from src.config import Config
import json

def input_with_default(prompt: str, default_value: str = "") -> str:
    """带默认值的输入函数"""
    if default_value:
        user_input = input(f"{prompt} [默认: {default_value}]: ").strip()
        return user_input if user_input else default_value
    return input(prompt).strip()

def config_rules() -> dict:
    """配置分析规则"""
    print("\n=== 规则配置 ===")
    print("1. 使用默认规则")
    print("2. 自定义规则")
    print("3. 从文件加载规则")
    
    choice = input("请选择 (1-3): ").strip()
    
    if choice == "1":
        return Config.DEFAULT_RULES
    
    elif choice == "2":
        rules = Config.DEFAULT_RULES.copy()
        
        # 配置正面关键词
        print("\n输入正面关键词（用逗号分隔，直接回车跳过）:")
        keywords = input().strip()
        if keywords:
            rules["positive_keywords"] = [k.strip() for k in keywords.split(",")]
        
        # 配置负面关键词
        print("\n输入负面关键词（用逗号分隔，直接回车使用默认）:")
        print(f"默认值: {', '.join(Config.DEFAULT_RULES['negative_keywords'])}")
        keywords = input().strip()
        if keywords:
            rules["negative_keywords"] = [k.strip() for k in keywords.split(",")]
        
        # 配置最小评论长度
        try:
            min_length = int(input_with_default(
                "\n输入最小评论长度", 
                str(Config.DEFAULT_RULES["min_length"])
            ))
            rules["min_length"] = min_length
        except ValueError:
            print("使用默认最小长度")
        
        # 配置是否排除默认好评
        exclude = input_with_default(
            "\n是否排除默认好评 (y/n)", 
            "y" if Config.DEFAULT_RULES["exclude_default_comment"] else "n"
        ).lower()
        rules["exclude_default_comment"] = exclude.startswith("y")
        
        # 保存规则配置
        save = input("\n是否保存规则配置到文件? (y/n): ").lower()
        if save.startswith("y"):
            file_path = input("输入保存路径 [默认: rules.json]: ").strip() or "rules.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            print(f"规则已保存到: {file_path}")
        
        return rules
    
    elif choice == "3":
        while True:
            file_path = input("\n输入规则文件路径: ").strip()
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    rules = json.load(f)
                if Config.validate_rules(rules):
                    return rules
                else:
                    print("无效的规则文件格式")
            except Exception as e:
                print(f"加载规则文件失败: {str(e)}")
                retry = input("是否重试? (y/n): ").lower()
                if not retry.startswith('y'):
                    print("使用默认规则")
                    return Config.DEFAULT_RULES
    
    else:
        print("无效选择，使用默认规则")
        return Config.DEFAULT_RULES

def config_batch_size() -> int:
    """配置并发批处理大小"""
    while True:
        try:
            batch_size = int(input_with_default(
                f"\n请输入并发批处理大小 ({Config.MIN_BATCH_SIZE}-{Config.MAX_BATCH_SIZE})",
                str(Config.DEFAULT_BATCH_SIZE)
            ))
            if Config.validate_batch_size(batch_size):
                return batch_size
            else:
                print(f"请输入 {Config.MIN_BATCH_SIZE} 到 {Config.MAX_BATCH_SIZE} 之间的数字")
        except ValueError:
            print("请输入有效的数字")

async def main():
    print("=== 评论分析系统 ===\n")
    
    # 获取API密钥
    api_key = Config.API_KEY
    while not Config.validate_api_key(api_key):
        api_key = input("请输入DeepSeek API密钥 (sk-开头): ").strip()
        if not api_key:
            print("API密钥不能为空")
            continue
        if not Config.validate_api_key(api_key):
            print("API密钥格式无效")
            continue
    
    # 获取CSV文件路径
    csv_path = None
    while not csv_path or not Config.validate_file_path(csv_path):
        csv_path = input("\n请输入CSV文件路径: ").strip()
        if not csv_path:
            print("文件路径不能为空")
            continue
        if not Config.validate_file_path(csv_path):
            print("文件路径无效或不是CSV文件")
            continue
    
    # 配置规则和批处理大小
    rules = config_rules()
    batch_size = config_batch_size()
    
    # 创建分析器实例
    analyzer = CommentAnalyzer(
        api_key=api_key,
        csv_path=csv_path,
        batch_size=batch_size,
        rules=rules
    )
    
    # 存储全局分析结果
    global_results = None
    
    while True:
        print("\n=== 主菜单 ===")
        print("1. 分析评论")
        print("2. 总结需求")
        print("3. 修改规则")
        print("4. 修改并发数")
        print("5. 退出")
        
        choice = input("\n请选择操作 (1-5): ").strip()
        
        if choice == "1":
            # 获取要分析的评论数量
            while True:
                try:
                    max_comments = input("\n请输入要分析的评论数量 (直接回车分析全部): ").strip()
                    if max_comments == "":
                        max_comments = None
                    else:
                        max_comments = int(max_comments)
                        if max_comments <= 0:
                            print("请输入大于0的数字")
                            continue
                    break
                except ValueError:
                    print("请输入有效的数字")
            
            # 加载并分析数据
            if analyzer.load_data(max_comments):
                global_results = await analyzer.analyze_comments()
                
        elif choice == "2":
            if global_results is None:
                print("\n请先进行评论分析（选项1）")
                continue
                
            await analyzer.summarize_all(global_results)
            
        elif choice == "3":
            # 更新规则
            analyzer.rules = config_rules()
            global_results = None  # 重置分析结果
            print("\n规则已更新，需要重新进行分析")
            
        elif choice == "4":
            # 更新并发数
            analyzer.batch_size = config_batch_size()
            print(f"\n并发数已更新为: {analyzer.batch_size}")
            
        elif choice == "5":
            print("\n感谢使用！")
            break
            
        else:
            print("\n无效的选择，请重试")

if __name__ == "__main__":
    try:
        if sys.platform.startswith('win'):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n程序已被用户中断")
    except Exception as e:
        print(f"\n程序发生错误: {str(e)}")
    finally:
        print("\n程序已退出")