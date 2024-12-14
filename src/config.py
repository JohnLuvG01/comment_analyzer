import os
from pathlib import Path
from typing import List, Dict

class Config:
    # DeepSeek API配置
    API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    
    # 默认批处理配置
    DEFAULT_BATCH_SIZE = 10
    MIN_BATCH_SIZE = 1
    MAX_BATCH_SIZE = 100
    
    # 默认规则配置
    DEFAULT_RULES = {
        "positive_keywords": [],      # 正面关键词
        "negative_keywords": ["客服", "物流", "发货", "快递"],  # 负面关键词
        "min_length": 10,            # 最小评论长度
        "exclude_default_comment": True,  # 是否排除默认好评
    }
    
    # 文件配置
    DEFAULT_ENCODING = 'utf-8-sig'
    
    @staticmethod
    def validate_api_key(api_key: str) -> bool:
        """验证API密钥格式"""
        return bool(api_key and api_key.startswith('sk-'))
    
    @staticmethod
    def validate_file_path(file_path: str) -> bool:
        """验证文件路径"""
        path = Path(file_path)
        return path.exists() and path.is_file() and path.suffix.lower() == '.csv'
    
    @staticmethod
    def validate_batch_size(batch_size: int) -> bool:
        """验证批处理大小是否在合理范围内"""
        return Config.MIN_BATCH_SIZE <= batch_size <= Config.MAX_BATCH_SIZE
    
    @staticmethod
    def validate_rules(rules: Dict) -> bool:
        """验证规则配置是否有效"""
        required_keys = ["positive_keywords", "negative_keywords", "min_length", "exclude_default_comment"]
        return all(key in rules for key in required_keys)