# -*- coding: utf-8 -*-
"""專案內所有檔案路徑集中在這裡，腳本從哪個資料夾執行都找得到。"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")                      # 產生出來的網站（不進 repo）
TEMPLATES = os.path.join(ROOT, "templates")            # 前端原始檔（HTML／CSS／JS／PWA）

ARCADES = os.path.join(DATA, "arcades.csv")            # 主資料：所有機廳
MGM_CACHE = os.path.join(DATA, "mgm_cache.csv")        # Music Game Map 快取（台灣中文名／機台）
DATA_DATE = os.path.join(DATA, "data_date.txt")        # 資料更新日（網站頁尾、data.json 用）
SUMMARY = os.path.join(DATA, "update_summary.md")      # update_data.py 的變動摘要（不進 repo）
SCRAPED_JP = os.path.join(DATA, "scraped_jp.csv")      # scrape_jp.py 單獨執行的輸出（不進 repo）
GOOGLE_USAGE = os.path.join(DATA, "google_usage.json") # Google API 本機用量紀錄（不進 repo）
ENV = os.path.join(ROOT, ".env")                       # GOOGLE_MAPS_API_KEY（不進 repo）


def debug_file(name):
    """爬蟲 --test 時存下來的除錯頁，放在專案根目錄（.gitignore 已排除 debug_*.html）。"""
    return os.path.join(ROOT, name)
