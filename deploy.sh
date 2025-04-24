#!/bin/bash

# 定义变量
LOCAL_APP_FILE="app.py" # 本地 app.py 文件路径，根据实际情况修改
REMOTE_USER="root" # 远程服务器用户名
REMOTE_HOST="" # 服务器IP地址
REMOTE_DIR="/root/PlumeMapleBlogAPI/" # 远程后端目录

# 显示部署信息
echo "===== 后端部署脚本 ====="
echo "将部署文件: $LOCAL_APP_FILE"
echo "目标服务器: $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR"

# 确认部署
read -p "确认部署？(y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "部署已取消"
    exit 1
fi

# 检查本地文件是否存在
if [ ! -f "$LOCAL_APP_FILE" ]; then
    echo "错误: 本地文件 $LOCAL_APP_FILE 不存在!"
    exit 1
fi

# 使用 SCP 上传 app.py 文件
echo "开始上传 app.py 文件..."
scp "$LOCAL_APP_FILE" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR"

# 检查上传结果
if [ $? -eq 0 ]; then
    echo "app.py 文件上传成功!"
else
    echo "上传失败，请检查错误信息"
    exit 1
fi

# 连接到服务器，确保 comments.json 文件存在（如果需要）
echo "检查 comments.json 文件..."
ssh $REMOTE_USER@$REMOTE_HOST "
    if [ ! -f \"${REMOTE_DIR}comments.json\" ]; then
        echo '创建空的 comments.json 文件...'
        echo '[]' > \"${REMOTE_DIR}comments.json\"
        chmod 666 \"${REMOTE_DIR}comments.json\"
    else
        echo 'comments.json 文件已存在'
    fi
"

# 重启后端服务
echo "重启后端服务..."
ssh $REMOTE_USER@$REMOTE_HOST "
    echo '正在重启 blog_api 服务...'
    sudo systemctl restart blog_api
    
    # 检查服务状态
    if systemctl is-active --quiet blog_api; then
        echo '服务已成功重启'
    else
        echo '警告: 服务可能未成功重启，请检查状态'
        systemctl status blog_api
    fi
"

echo "后端部署完成!"