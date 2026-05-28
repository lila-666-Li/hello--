#!/usr/bin/env python3
"""
报销搭子 - 智能匹配脚本 v2
用法：
  python3 match.py "我买了键盘和鼠标"
  python3 match.py "出差打车" --top 5
  python3 match.py "请客户吃饭" --interactive
"""
import json
import sys
import os
import re
import argparse

DATA_FILE = os.path.join(os.path.dirname(__file__), 'expense-categories.json')

# 常见场景预设
SCENARIOS = {
    "出差": {"场景": "差旅", "关键词": ["出差", "异地", "外地", "出差"]},
    "加班": {"场景": "加班相关", "关键词": ["加班", "晚上", "深夜", "延时"]},
    "请客": {"场景": "商务招待", "关键词": ["请客", "招待", "宴请"]},
    "游戏": {"场景": "业务宣传", "关键词": ["游戏", "玩家", "投放", "素材", "推广"]},
    "办公": {"场景": "办公采购", "关键词": ["办公", "文具", "日用品", "办公用品"]},
    "软件": {"场景": "软件采购", "关键词": ["数据库", "MySQL", "Oracle", "SaaS", "软件授权", "云服务", "软件会员", "软件购买", "软件续费"]},
    "邮寄": {"场景": "邮寄快递", "关键词": ["顺丰", "快递", "寄", "EMS", "邮寄", "中通", "圆通", "韵达", "速递"]},
    "节日": {"场景": "节日福利", "关键词": ["中秋", "月饼", "端午", "粽子", "春节", "年货", "节日", "福利品"]},
    "展会": {"场景": "展会参展", "关键词": ["展会", "参展", "行业展会", "展会门票"]},
}

# 开票信息查询链接
INVOICE_INFO_URL = "https://lx3qcyzne8.feishu.cn/base/COcMb4UiDaugJBs5CqocnKaanmh?table=tbllN6TSrefLEj9a&view=vewuxh5NZ6"

# 关键词自动指引
KEYWORD_GUIDE = {
    "开票信息": "🧾 开票信息查询：\n" + INVOICE_INFO_URL,
    "开票资料": "🧾 开票信息查询：\n" + INVOICE_INFO_URL,
    "发票信息": "🧾 开票信息查询：\n" + INVOICE_INFO_URL,
    "开发票": "🧾 开票信息查询：\n" + INVOICE_INFO_URL,
    "报销科目": "💡 不确定报什么科目？来财帮你查！直接告诉我你买了什么/做了什么就行 😊",
    "报什么科目": "💡 不确定报什么科目？来财帮你查！直接告诉我你买了什么/做了什么就行 😊",
    "费用科目": "💡 不确定报什么科目？来财帮你查！直接告诉我你买了什么/做了什么就行 😊",
    "附件清单": "📎 报销附件清单：\n• 付款申请：盖章版合约 + 请款单/报价单/验收单\n• 差旅费：出差申请单 + 付款截图\n• 交通费：外勤申请单 + 付款截图",
    "报销附件": "📎 报销附件清单：\n• 付款申请：盖章版合约 + 请款单/报价单/验收单\n• 差旅费：出差申请单 + 付款截图\n• 交通费：外勤申请单 + 付款截图",
    "费用说明": "📝 费用说明参考：\n• 差旅费：「出差-地点-事由」\n• 交通费：「外勤-事由」\n• 办公费：「办公用品-品名」\n来财也可以帮你生成 😊",
}

def load_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def tokenize(text):
    """分词：提取中文词、英文词，同时生成单字词/双字词/全词三级词库"""
    words = re.findall(r'[\u4e00-\u9fff]{2,10}|[a-zA-Z]+', text)
    tokens = set()
    for w in words:
        tokens.add(w)
        # 双字词
        for i in range(len(w)-1):
            tokens.add(w[i:i+2])
        # 三字词（如果是长词）
        if len(w) >= 4:
            for i in range(len(w)-2):
                tokens.add(w[i:i+3])
    return tokens

def match(query, data, top_k=3):
    query_tokens = tokenize(query)
    query_lower = query.lower()
    if not query_tokens:
        return []
    
    # 场景预判
    scenario_hints = set()
    for name, info in SCENARIOS.items():
        for kw in info['关键词']:
            if kw in query_lower:
                scenario_hints.update(info['关键词'])
    
    scores = []
    for item in data:
        score = 0
        desc_lower = item['description'].lower()
        kw_lower = item['keywords'].lower()
        cat_lower = item['category'].lower()
        searchable = f"{cat_lower} {desc_lower} {kw_lower}"
        
        # 1. 精确匹配 description（最高权重）
        for token in query_tokens:
            if token in desc_lower:
                score += 20
            elif token in kw_lower:
                score += 10
            elif token in cat_lower:
                score += 5
            elif token in searchable:
                score += 2
        
        # 2. 场景加成
        for hint in scenario_hints:
            if hint in searchable:
                score += 8
        
        # 3. 双字词精准匹配加成
        bigrams = {t for t in query_tokens if len(t) == 2}
        for bg in bigrams:
            if bg in desc_lower:
                score += 15
            elif bg in kw_lower:
                score += 8
        
        if score > 0:
            scores.append((score, item))
    
    scores.sort(key=lambda x: (-x[0], x[1]['category']))
    return scores[:top_k]

def format_result(results, query=""):
    if not results:
        return (
            f"❌ 未找到「{query}」匹配的报销科目\n\n"
            "💡 试试这样说：\n"
            "  • 「出差的XX费用」→ 差旅费\n"
            "  • 「办公室的XX」→ 办公用品/办公费\n"
            "  • 「请客户XX」→ 招待费\n"
            "  • 「玩家/游戏相关」→ 业务宣传费\n"
            "  • 「加班XX」→ 员工福利/市内交通费"
        )
    
    lines = [f"📋 **报销建议**（查询：「{query}」）\n"]
    
    for i, (score, item) in enumerate(results):
        if i == 0:
            lines.append(f"🏷️ **推荐科目**：{item['category']}")
            lines.append(f"📝 **费用说明**：{item['description']}")
            if item['keywords']:
                # 只显示前50字关键词
                kw = item['keywords']
                if len(kw) > 50:
                    kw = kw[:50] + "..."
                lines.append(f"💡 **关键词**：{kw}")
            lines.append(f"📊 匹配度：{score}分")
        else:
            lines.append(f"\n--- 备选{i+1} ---")
            lines.append(f"🏷️ {item['category']}")
            lines.append(f"📝 {item['description']}")
    
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description='请款报销管家')
    parser.add_argument('query', nargs='?', help='费用描述')
    parser.add_argument('--top', type=int, default=3, help='返回结果数量')
    parser.add_argument('--interactive', action='store_true', help='交互模式')
    args = parser.parse_args()
    
    if not args.query and not args.interactive:
        print("用法：python3 match.py \"费用描述\"")
        print("示例：python3 match.py \"我买了键盘和鼠标\"")
        print("交互：python3 match.py --interactive")
        sys.exit(1)
    
    data = load_data()
    
    if args.interactive:
        print("🦐 请款报销管家 - 交互模式")
        print("输入费用描述，按回车查询。输入 q 退出。\n")
        while True:
            try:
                query = input("💬 > ").strip()
                if query.lower() in ('q', 'quit', 'exit', '退出'):
                    print("👋 再见！")
                    break
                if not query:
                    continue
                
                # 检查关键词指引
                for kw, response in KEYWORD_GUIDE.items():
                    if kw in query:
                        print(response)
                        print()
                        break
                else:
                    results = match(query, data, args.top)
                    print(format_result(results, query))
                    print()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 再见！")
                break
    else:
        # 检查关键词指引
        for kw, response in KEYWORD_GUIDE.items():
            if kw in args.query:
                print(response)
                sys.exit(0)
        results = match(args.query, data, args.top)
        print(format_result(results, args.query))

if __name__ == '__main__':
    main()
