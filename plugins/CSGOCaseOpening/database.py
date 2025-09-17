import sqlite3
import logging
import os
from typing import Dict, List, Tuple, Optional
from datetime import datetime

_log = logging.getLogger(__name__)

class CSGODatabase:
    """CSGO开箱数据库管理类"""
    
    def __init__(self):
        self.db_path = "data/csgo_opening.db"
        self.ensure_data_dir()
        self.init_database()
    
    def ensure_data_dir(self):
        """确保data目录存在"""
        os.makedirs("data", exist_ok=True)
    
    def init_database(self):
        """初始化数据库表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 用户开箱记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_opening_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        group_id TEXT NOT NULL,
                        case_name TEXT NOT NULL,
                        case_type TEXT NOT NULL,
                        amount INTEGER NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 开箱结果表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS opening_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        record_id INTEGER NOT NULL,
                        skin_name TEXT NOT NULL,
                        rarity TEXT NOT NULL,
                        wear TEXT,
                        is_rare INTEGER DEFAULT 0,
                        FOREIGN KEY (record_id) REFERENCES user_opening_records (id)
                    )
                ''')
                
                # 用户统计表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_statistics (
                        user_id TEXT PRIMARY KEY,
                        total_openings INTEGER DEFAULT 0,
                        total_cases INTEGER DEFAULT 0,
                        rare_items INTEGER DEFAULT 0,
                        legendary_items INTEGER DEFAULT 0,
                        last_opening DATETIME,
                        best_item TEXT,
                        best_rarity TEXT
                    )
                ''')
                
                conn.commit()
                _log.info("CSGO开箱数据库初始化完成")
                
        except Exception as e:
            _log.error(f"数据库初始化失败: {e}")
    
    def record_opening(self, user_id: str, group_id: str, case_name: str, 
                      case_type: str, amount: int, results: List[Dict]) -> int:
        """记录开箱操作"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 插入开箱记录
                cursor.execute('''
                    INSERT INTO user_opening_records 
                    (user_id, group_id, case_name, case_type, amount)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, group_id, case_name, case_type, amount))
                
                record_id = cursor.lastrowid
                
                # 插入开箱结果
                rare_count = 0
                legendary_count = 0
                best_item = None
                best_rarity_level = 0
                
                rarity_levels = {
                    "消费级": 1, "工业级": 2, "军规级": 3, "受限": 4,
                    "保密": 5, "隐秘": 6, "违禁": 7, "非凡": 8
                }
                
                for result in results:
                    skin_name = result.get('name', '')
                    rarity = result.get('rarity', '')
                    wear = result.get('wear', '')
                    
                    # 判断是否为稀有物品（受限及以上）
                    is_rare = 1 if rarity in ["受限", "保密", "隐秘", "违禁", "非凡"] else 0
                    if is_rare:
                        rare_count += 1
                    
                    # 判断是否为传说物品（隐秘及以上）
                    if rarity in ["隐秘", "违禁", "非凡"]:
                        legendary_count += 1
                    
                    # 记录最好的物品
                    current_level = rarity_levels.get(rarity, 0)
                    if current_level > best_rarity_level:
                        best_rarity_level = current_level
                        best_item = skin_name
                        best_rarity = rarity
                    
                    cursor.execute('''
                        INSERT INTO opening_results 
                        (record_id, skin_name, rarity, wear, is_rare)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (record_id, skin_name, rarity, wear, is_rare))
                
                # 更新用户统计
                self._update_user_statistics(
                    cursor, user_id, amount, rare_count, legendary_count,
                    best_item if best_rarity_level > 0 else None,
                    best_rarity if best_rarity_level > 0 else None
                )
                
                conn.commit()
                _log.info(f"记录用户 {user_id} 开箱: {amount}个 {case_name}")
                return record_id
                
        except Exception as e:
            _log.error(f"记录开箱失败: {e}")
            return 0
    
    def _update_user_statistics(self, cursor, user_id: str, amount: int, 
                               rare_count: int, legendary_count: int,
                               best_item: str = None, best_rarity: str = None):
        """更新用户统计信息"""
        cursor.execute('''
            INSERT OR REPLACE INTO user_statistics 
            (user_id, total_openings, total_cases, rare_items, legendary_items, 
             last_opening, best_item, best_rarity)
            VALUES (
                ?, 
                COALESCE((SELECT total_openings FROM user_statistics WHERE user_id = ?), 0) + 1,
                COALESCE((SELECT total_cases FROM user_statistics WHERE user_id = ?), 0) + ?,
                COALESCE((SELECT rare_items FROM user_statistics WHERE user_id = ?), 0) + ?,
                COALESCE((SELECT legendary_items FROM user_statistics WHERE user_id = ?), 0) + ?,
                CURRENT_TIMESTAMP,
                COALESCE(?, (SELECT best_item FROM user_statistics WHERE user_id = ?)),
                COALESCE(?, (SELECT best_rarity FROM user_statistics WHERE user_id = ?))
            )
        ''', (user_id, user_id, user_id, amount, user_id, rare_count, 
              user_id, legendary_count, best_item, user_id, best_rarity, user_id))
    
    def get_user_statistics(self, user_id: str) -> Dict:
        """获取用户统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT total_openings, total_cases, rare_items, legendary_items,
                           last_opening, best_item, best_rarity
                    FROM user_statistics 
                    WHERE user_id = ?
                ''', (user_id,))
                
                result = cursor.fetchone()
                if result:
                    total_openings, total_cases, rare_items, legendary_items, \
                    last_opening, best_item, best_rarity = result
                    
                    # 计算概率
                    rare_rate = (rare_items / total_cases * 100) if total_cases > 0 else 0
                    legendary_rate = (legendary_items / total_cases * 100) if total_cases > 0 else 0
                    
                    return {
                        'total_openings': total_openings,
                        'total_cases': total_cases,
                        'rare_items': rare_items,
                        'legendary_items': legendary_items,
                        'rare_rate': rare_rate,
                        'legendary_rate': legendary_rate,
                        'last_opening': last_opening,
                        'best_item': best_item,
                        'best_rarity': best_rarity
                    }
                else:
                    return {
                        'total_openings': 0, 'total_cases': 0, 'rare_items': 0,
                        'legendary_items': 0, 'rare_rate': 0, 'legendary_rate': 0,
                        'last_opening': None, 'best_item': None, 'best_rarity': None
                    }
                    
        except Exception as e:
            _log.error(f"获取用户统计失败: {e}")
            return {}
    
    def get_global_statistics(self) -> Dict:
        """获取全局统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 总体统计
                cursor.execute('''
                    SELECT 
                        COUNT(DISTINCT user_id) as total_users,
                        SUM(total_openings) as total_openings,
                        SUM(total_cases) as total_cases,
                        SUM(rare_items) as total_rare_items,
                        SUM(legendary_items) as total_legendary_items
                    FROM user_statistics
                ''')
                
                result = cursor.fetchone()
                if result:
                    total_users, total_openings, total_cases, total_rare_items, total_legendary_items = result
                    
                    # 计算全局概率
                    global_rare_rate = (total_rare_items / total_cases * 100) if total_cases > 0 else 0
                    global_legendary_rate = (total_legendary_items / total_cases * 100) if total_cases > 0 else 0
                    
                    return {
                        'total_users': total_users or 0,
                        'total_openings': total_openings or 0,
                        'total_cases': total_cases or 0,
                        'total_rare_items': total_rare_items or 0,
                        'total_legendary_items': total_legendary_items or 0,
                        'global_rare_rate': global_rare_rate,
                        'global_legendary_rate': global_legendary_rate
                    }
                else:
                    return {
                        'total_users': 0, 'total_openings': 0, 'total_cases': 0,
                        'total_rare_items': 0, 'total_legendary_items': 0,
                        'global_rare_rate': 0, 'global_legendary_rate': 0
                    }
                    
        except Exception as e:
            _log.error(f"获取全局统计失败: {e}")
            return {}
    
    def get_top_users(self, limit: int = 10) -> List[Tuple]:
        """获取开箱排行榜"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT user_id, total_cases, rare_items, legendary_items,
                           ROUND(rare_items * 100.0 / total_cases, 2) as rare_rate
                    FROM user_statistics 
                    WHERE total_cases > 0
                    ORDER BY total_cases DESC, rare_items DESC
                    LIMIT ?
                ''', (limit,))
                
                return cursor.fetchall()
                
        except Exception as e:
            _log.error(f"获取排行榜失败: {e}")
            return []
