import pandas as pd
import asyncio
import aiohttp
import json
from tqdm import tqdm
from typing import List, Dict, Tuple
import os
from pathlib import Path
from .config import Config

class CommentAnalyzer:
    def __init__(self, api_key: str, csv_path: str, batch_size: int = 10, 
                 output_dir: str = None, rules: Dict = None):
        """
        初始化评论分析器
        :param api_key: DeepSeek API密钥
        :param csv_path: CSV文件路径
        :param batch_size: 并发批处理大小
        :param output_dir: 输出目录
        :param rules: 自定义规则
        """
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.csv_path = Path(csv_path)
        self.batch_size = min(max(batch_size, Config.MIN_BATCH_SIZE), Config.MAX_BATCH_SIZE)
        self.output_dir = Path(output_dir) if output_dir else self.csv_path.parent
        self.rules = rules if rules else Config.DEFAULT_RULES.copy()
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def get_output_path(self, filename: str) -> Path:
        """获取输出文件的完整路径"""
        return self.output_dir / filename

    def is_valid_comment(self, comment: str) -> bool:
        """
        根据规则判断评论是否有效
        """
        if not comment or len(comment) < self.rules["min_length"]:
            return False
            
        # 检查是否为默认好评
        if self.rules["exclude_default_comment"]:
            default_comments = ["默认好评", "系统默认好评", "好评"]
            if any(comment.strip() == dc for dc in default_comments):
                return False

        # 检查负面关键词
        if any(kw in comment for kw in self.rules["negative_keywords"]):
            return False
            
        # 检查正面关键词（如果配置了的话）
        if self.rules["positive_keywords"]:
            if not any(kw in comment for kw in self.rules["positive_keywords"]):
                return False
                
        return True
        
    def load_data(self, max_comments: int = None) -> bool:
        """加载CSV文件并预处理评论数据"""
        try:
            self.df = pd.read_csv(self.csv_path, encoding='utf-8-sig', low_memory=False)
            
            comments = []
            for _, row in self.df.iterrows():
                # 处理初评
                if pd.notna(row['初评内容']):
                    comment_text = str(row['初评内容'])
                    if self.is_valid_comment(comment_text):
                        comments.append({
                            'SKU': row['SKU'],
                            'SKUID': row['SKUID'],
                            'content': comment_text,
                            'type': '初评',
                            'date': row['评价日期']
                        })
                
                # 处理追评
                if pd.notna(row['追评']):
                    comment_text = str(row['追评'])
                    if self.is_valid_comment(comment_text):
                        comments.append({
                            'SKU': row['SKU'],
                            'SKUID': row['SKUID'],
                            'content': comment_text,
                            'type': '追评',
                            'date': row['评价日期']
                        })
            
            total_comments = len(self.df)
            valid_comments = len(comments)
            
            # 限制评论数量
            if max_comments is not None:
                comments = comments[:max_comments]
            
            self.comments = comments
            print(f"CSV文件共有{total_comments}条评论")
            print(f"其中符合规则的有{valid_comments}条评论")
            print(f"将处理{len(self.comments)}条评论")
            return True
        except Exception as e:
            print(f"加载CSV文件失败: {str(e)}")
            return False

    async def process_single_comment(self, session: aiohttp.ClientSession, 
                                   comment: Dict) -> Tuple[bool, str]:
        """处理单条评论"""
        prompt = f"""请判断以下评论是否有用。判断规则：
        1. 提具体意见是有用的
        2. 有用与没用最大的区别是是否具体详细，好是怎么好，坏是怎么坏
        3. 任何提及客服和物流的评论都视为无效
        
        评论内容：{comment['content']}
        评论类型：{comment['type']}
        
        请以JSON格式返回，包含两个字段：
        - is_useful: true/false
        - reason: 判断原因
        """

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个评论分析助手，你需要判断评论是否有用。请直接返回JSON格式的结果，不要包含markdown标记。"},
                {"role": "user", "content": prompt}
            ]
        }

        try:
            async with session.post(self.base_url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    content = content.replace('```json', '').replace('```', '').strip()
                    parsed_content = json.loads(content)
                    return parsed_content['is_useful'], parsed_content['reason']
                else:
                    response_text = await response.text()
                    print(f"API请求失败，状态码: {response.status}")
                    print(f"响应内容: {response_text}")
                    return False, f"API请求失败: {response.status}"
        except Exception as e:
            print(f"处理评论时发生错误: {str(e)}")
            return False, f"处理出错: {str(e)}"

    async def process_batch(self, comments: List[Dict]) -> List[Dict]:
        """并发处理一批评论"""
        async with aiohttp.ClientSession(headers=self.headers) as session:
            tasks = []
            for comment in comments:
                task = asyncio.create_task(self.process_single_comment(session, comment))
                tasks.append(task)
            results = await asyncio.gather(*tasks)
            
            return [
                {**comment, 'is_useful': is_useful, 'reason': reason}
                for (comment, (is_useful, reason)) in zip(comments, results)
            ]

    async def analyze_comments(self):
        """分析评论是否有用"""
        all_results = []
        
        with tqdm(total=len(self.comments), desc="正在分析评论") as pbar:
            for i in range(0, len(self.comments), self.batch_size):
                batch = self.comments[i:i + self.batch_size]
                results = await self.process_batch(batch)
                all_results.extend(results)
                pbar.update(len(batch))

        # 保存分析结果
        results_df = pd.DataFrame(all_results)
        output_path = self.get_output_path('analysis_results.csv')
        results_df.to_csv(output_path, index=False, encoding='utf-8-sig')

        useful_comments = [r for r in all_results if r['is_useful']]
        print(f"\n共发现{len(useful_comments)}条有用评论")
        print(f"分析结果已保存到 {output_path}")
        
        return all_results

    async def summarize_requirements_async(self, session: aiohttp.ClientSession, 
                                         useful_comments: List[Dict]) -> str:
        """异步总结需求"""
        sku_comments = {}
        for comment in useful_comments:
            if comment['SKU'] not in sku_comments:
                sku_comments[comment['SKU']] = []
            sku_comments[comment['SKU']].append(
                f"[{comment['type']}] {comment['content']}"
            )

        summaries = []
        for sku, comments in sku_comments.items():
            comments_text = "\n".join(comments)
            prompt = f"""请分析以下关于商品(SKU: {sku})的评论，并总结用户需求：
            
            评论内容：
            {comments_text}
            
            请提取关键需求点，并按照重要性排序。要求：
            1. 合并相似需求
            2. 提取具体改进建议
            3. 分析需求优先级
            4. 区分初评和追评中的反馈
            """

            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是一个需求分析专家，善于从用户反馈中提取核心需求。"},
                    {"role": "user", "content": prompt}
                ]
            }

            try:
                async with session.post(self.base_url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        summaries.append(f"\n== SKU: {sku} 需求分析 ==\n" + 
                                      result['choices'][0]['message']['content'])
            except Exception as e:
                summaries.append(f"\n== SKU: {sku} 需求分析失败 ==\n{str(e)}")

        return "\n\n".join(summaries)

    async def summarize_all(self, all_results: List[Dict]):
        """总结需求"""
        useful_comments = [r for r in all_results if r['is_useful']]
        
        if not useful_comments:
            print("\n未发现有用评论，无法总结需求")
            return

        print(f"\n开始总结{len(useful_comments)}条有用评论的需求...")
        
        sku_comments = {}
        for comment in useful_comments:
            if comment['SKU'] not in sku_comments:
                sku_comments[comment['SKU']] = []
            sku_comments[comment['SKU']].append(comment)

        summaries = []
        with tqdm(total=len(sku_comments), desc="正在总结需求") as pbar:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                for sku, comments in sku_comments.items():
                    requirement = await self.summarize_requirements_async(session, comments)
                    summaries.append(requirement)
                    pbar.update(1)

        # 保存总结结果
        output_path = self.get_output_path('requirements_summary.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n\n".join(summaries))
        print(f"\n需求总结已保存到 {output_path}")