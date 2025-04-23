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
STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.json")
COMMENTS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "comments.json"
)

# 确保统计文件存在
if not os.path.exists(STATS_FILE):
    with open(STATS_FILE, "w") as f:
        json.dump({"visitors": 0, "totalVisits": 0, "articles": {}}, f)

# 确保评论文件存在
if not os.path.exists(COMMENTS_FILE):
    with open(COMMENTS_FILE, "w") as f:
        json.dump({}, f)


def get_stats():
    with open(STATS_FILE, "r") as f:
        return json.load(f)


def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)


def get_comments():
    with open(COMMENTS_FILE, "r") as f:
        return json.load(f)


def save_comments(comments):
    with open(COMMENTS_FILE, "w") as f:
        json.dump(comments, f, indent=2)


# 访客统计相关API
@app.route("/api/record-visitor", methods=["GET"])
def record_visitor():
    visitor_id = request.cookies.get("visitor_id")

    # 如果没有访客cookie，说明是新访客
    if not visitor_id:
        stats = get_stats()
        stats["visitors"] += 1
        save_stats(stats)

        resp = make_response(
            jsonify({"success": True, "visitorCount": stats["visitors"]})
        )

        # 设置cookie，有效期1年
        expiration = datetime.now() + timedelta(days=365)
        resp.set_cookie(
            "visitor_id",
            str(uuid.uuid4()),
            expires=expiration,
            httponly=True,
            samesite="Lax",
            path="/",
        )
        return resp

    # 老访客，不增加计数
    stats = get_stats()
    return jsonify({"success": True, "visitorCount": stats["visitors"]})


@app.route("/api/record-article-visit", methods=["POST"])
def record_article_visit():
    data = request.json
    article_id = data.get("articleId")
    visitor_id = request.cookies.get("visitor_id")

    if not visitor_id or not article_id:
        return jsonify({"success": False, "message": "缺少访客ID或文章ID"}), 400

    stats = get_stats()

    # 如果文章不在列表中，初始化
    if article_id not in stats["articles"]:
        stats["articles"][article_id] = {"views": 0, "visitors": []}

    # 检查访客是否已访问过该文章
    if visitor_id not in stats["articles"][article_id]["visitors"]:
        stats["articles"][article_id]["visitors"].append(visitor_id)
        stats["totalVisits"] += 1  # 总访问量+1（去重）
        save_stats(stats)

    return jsonify({"success": True, "totalVisits": stats["totalVisits"]})


@app.route("/api/record-page-view", methods=["POST"])
def record_page_view():
    data = request.json
    article_id = data.get("articleId")

    if not article_id:
        return jsonify({"success": False, "message": "缺少文章ID"}), 400

    stats = get_stats()

    # 如果文章不在列表中，初始化
    if article_id not in stats["articles"]:
        stats["articles"][article_id] = {"views": 0, "visitors": []}

    # 增加页面浏览量
    stats["articles"][article_id]["views"] += 1
    save_stats(stats)

    return jsonify(
        {"success": True, "pageViews": stats["articles"][article_id]["views"]}
    )


@app.route("/api/stats", methods=["GET"])
def get_statistics():
    article_id = request.args.get("articleId")
    stats = get_stats()

    if article_id:
        # 返回特定文章的统计
        article_stats = stats["articles"].get(article_id, {"views": 0, "visitors": []})
        return jsonify(
            {
                "visitorCount": stats["visitors"],
                "totalVisits": stats["totalVisits"],
                "pageViews": article_stats["views"],
            }
        )

    # 返回全站统计
    return jsonify(
        {"visitorCount": stats["visitors"], "totalVisits": stats["totalVisits"]}
    )


# 评论系统相关API - 简化版，自动处理用户标识
@app.route("/api/comments/get", methods=["GET"])
def get_comments_api():
    path = request.args.get("path", "")

    if not path:
        return jsonify({"success": False, "message": "缺少页面路径"}), 400

    comments_data = get_comments()

    # 如果该页面没有评论，返回空列表
    if path not in comments_data:
        return jsonify([])

    # 按时间排序返回评论（时间戳从小到大，即从早到晚）
    page_comments = sorted(comments_data[path], key=lambda x: x["date"])
    return jsonify(page_comments)


@app.route("/api/comments/post", methods=["POST"])
def post_comment():
    try:
        data = request.json
        visitor_id = request.cookies.get("visitor_id")

        # 打印调试信息
        print("提交评论数据:", data)
        print("访客ID:", visitor_id)

        # 基本参数验证
        if not data or "content" not in data or "path" not in data:
            return jsonify({"success": False, "message": "缺少必要参数"}), 400

        content = data["content"]
        path = data["path"]
        parent_id = int(data.get("parent_id", 0))
        # 新增: 回复目标ID
        reply_to_id = int(data.get("reply_to_id", parent_id))

        # 如果没有访客ID，创建一个
        if not visitor_id:
            visitor_id = str(uuid.uuid4())

        # 简单内容验证
        if len(content.strip()) == 0:
            return jsonify({"success": False, "message": "评论内容不能为空"}), 400

        # 获取当前评论数据
        comments_data = get_comments()

        # 如果该页面没有评论，初始化
        if path not in comments_data:
            comments_data[path] = []

        # 生成评论ID
        comment_id = 1
        if comments_data[path]:
            comment_id = max(comment["id"] for comment in comments_data[path]) + 1

        # 获取访客数据，用于确定访客编号
        visitor_indices = {}
        current_index = 1

        # 检查这个visitor_id是否已经有评论，如果有，复用原来的编号
        visitor_found = False

        for page_path in comments_data:
            for comment in comments_data[page_path]:
                if (
                    "visitor_id" in comment
                    and comment["visitor_id"] not in visitor_indices
                ):
                    visitor_indices[comment["visitor_id"]] = current_index
                    current_index += 1

                if "visitor_id" in comment and comment["visitor_id"] == visitor_id:
                    visitor_found = True

        # 如果是新访客，分配新的编号
        visitor_index = visitor_indices.get(visitor_id)
        if not visitor_index:
            visitor_index = current_index

        # 创建评论对象
        comment = {
            "id": comment_id,
            "author": f"游客 {visitor_index}",
            "content": content,
            "parent_id": parent_id,
            "reply_to_id": reply_to_id,  # 保存回复目标ID
            "visitor_id": visitor_id,
            "date": int(datetime.now().timestamp()),  # 使用Unix时间戳
        }

        # 添加评论
        comments_data[path].append(comment)
        save_comments(comments_data)

        # 创建响应
        response = jsonify({"success": True, **comment})

        # 如果是新创建的访客ID，设置cookie
        if not request.cookies.get("visitor_id"):
            expiration = datetime.now() + timedelta(days=365)
            response.set_cookie(
                "visitor_id",
                visitor_id,
                expires=expiration,
                httponly=True,
                samesite="Lax",
                path="/",
            )

        return response

    except Exception as e:
        print("评论提交错误:", str(e))
        return jsonify({"success": False, "message": f"服务器处理错误: {str(e)}"}), 500


# 健康检查端点
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
