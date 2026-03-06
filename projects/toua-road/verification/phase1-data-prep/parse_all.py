#!/usr/bin/env python3
"""
全Excelファイルを自動検出・解析してAzure AI Search用JSONに変換

Usage:
    python parse_all.py                    # 全ファイルを一括解析
    python parse_all.py --folders 岩手 宮城  # 特定フォルダのみ
    python parse_all.py --dry-run          # パターン検出のみ（解析なし）
"""

import argparse
from parsers.dispatcher import parse_all_files


def main():
    parser = argparse.ArgumentParser(
        description="Excel パーサーディスパッチャー: 全Excelを自動検出・解析してJSON出力"
    )
    parser.add_argument(
        "--folders", nargs="+",
        help="解析対象フォルダ（指定しない場合は全フォルダ）"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="パターン検出のみ（解析なし）"
    )
    args = parser.parse_args()

    parse_all_files(folders=args.folders, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
