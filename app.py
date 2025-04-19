from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import json
import os
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)
# 允许凭证，使cookie可以正常工作
CORS(app, resources={r"/api/*": {"origins": "*", "supports_credentials": True}})

# 数据文件路径
STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stats.json')

# 确保统计文件存在
if not os.path.exists(STATS_FILE):
    with open(STATS_FILE, 'w') as f:
        json.dump({
            'visitors': 0,
            'totalVisits': 0,
            'articles': {}
        }, f)

def get_stats():
    with open(STATS_FILE, 'r') as f:
        return json.load(f)

def save_stats(stats):
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)

# 注意这里所有路由都以/api开头
@app.route('/api/record-visitor', methods=['GET'])
def record_visitor():
    visitor_id = request.cookies.get('visitor_id')
    
    # 如果没有访客cookie，说明是新访客
    if not visitor_id:
        stats = get_stats()
        stats['visitors'] += 1
        save_stats(stats)
        
        resp = make_response(jsonify({
            'success': True, 
            'visitorCount': stats['visitors']
        }))
        
        # 设置cookie，有效期1年
        expiration = datetime.now() + timedelta(days=365)
        resp.set_cookie('visitor_id', str(uuid.uuid4()), expires=expiration, httponly=True, samesite='Lax', path='/')
        return resp
    
    # 老访客，不增加计数
    stats = get_stats()
    return jsonify({
        'success': True, 
        'visitorCount': stats['visitors']
    })

@app.route('/api/record-article-visit', methods=['POST'])
def record_article_visit():
    data = request.json
    article_id = data.get('articleId')
    visitor_id = request.cookies.get('visitor_id')
    
    if not visitor_id or not article_id:
        return jsonify({
            'success': False, 
            'message': '缺少访客ID或文章ID'
        }), 400
    
    stats = get_stats()
    
    # 如果文章不在列表中，初始化
    if article_id not in stats['articles']:
        stats['articles'][article_id] = {
            'views': 0,
            'visitors': []
        }
    
    # 检查访客是否已访问过该文章
    if visitor_id not in stats['articles'][article_id]['visitors']:
        stats['articles'][article_id]['visitors'].append(visitor_id)
        stats['totalVisits'] += 1  # 总访问量+1（去重）
        save_stats(stats)
    
    return jsonify({
        'success': True,
        'totalVisits': stats['totalVisits']
    })

@app.route('/api/record-page-view', methods=['POST'])
def record_page_view():
    data = request.json
    article_id = data.get('articleId')
    
    if not article_id:
        return jsonify({
            'success': False, 
            'message': '缺少文章ID'
        }), 400
    
    stats = get_stats()
    
    # 如果文章不在列表中，初始化
    if article_id not in stats['articles']:
        stats['articles'][article_id] = {
            'views': 0,
            'visitors': []
        }
    
    # 增加页面浏览量
    stats['articles'][article_id]['views'] += 1
    save_stats(stats)
    
    return jsonify({
        'success': True,
        'pageViews': stats['articles'][article_id]['views']
    })

@app.route('/api/stats', methods=['GET'])
def get_statistics():
    article_id = request.args.get('articleId')
    stats = get_stats()
    
    if article_id:
        # 返回特定文章的统计
        article_stats = stats['articles'].get(article_id, {'views': 0, 'visitors': []})
        return jsonify({
            'visitorCount': stats['visitors'],
            'totalVisits': stats['totalVisits'],
            'pageViews': article_stats['views']
        })
    
    # 返回全站统计
    return jsonify({
        'visitorCount': stats['visitors'],
        'totalVisits': stats['totalVisits']
    })

# 健康检查端点
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)