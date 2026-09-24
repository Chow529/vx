-- ============================================================
-- 知问库 MySQL 建表脚本
-- 由当前 SQLAlchemy 模型转换而来
-- 引擎: InnoDB  字符集: utf8mb4 (支持中文 / emoji)
-- 说明: 所有字段均带 COMMENT；外键列均声明 FOREIGN KEY 约束
--       ON DELETE 规则：
--         CASCADE  —— 从记录随主记录一并删除（帖子/评论/点赞/标签关联等）
--         SET NULL —— 允许悬空引用，被删后置空（题目引用社区帖子）
--       注意: 本脚本需在建库前执行；已有库请 DROP DATABASE 后重建，
--             否则 CREATE TABLE IF NOT EXISTS 会跳过、外键不会生效
-- ============================================================

CREATE DATABASE IF NOT EXISTS vx
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_general_ci;

USE vx;

-- ------------------------------------------------------------
-- 1. 用户表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID，自增',
    openid      VARCHAR(128) NOT NULL COMMENT '微信 openid，用户唯一标识',
    nickname    VARCHAR(64)  DEFAULT '' COMMENT '用户昵称',
    avatar_url  VARCHAR(512) DEFAULT '' COMMENT '头像图片 URL',
    reputation  INT          DEFAULT 0  COMMENT '声望值（回答被采纳 +10）',
    is_admin    TINYINT(1)   DEFAULT 0  COMMENT '是否管理员：0否 1是（首个注册用户自动为管理员）',
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    UNIQUE KEY uk_users_openid (openid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户';

-- ------------------------------------------------------------
-- 2. 标签表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags (
    id        INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID，自增',
    name      VARCHAR(32) NOT NULL COMMENT '标签名，全局唯一',
    category  VARCHAR(32) DEFAULT 'tech' COMMENT '标签分类：tech=技术栈 / difficulty=难度 / custom=自定义',
    UNIQUE KEY uk_tags_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标签';

-- ------------------------------------------------------------
-- 3. 社区帖子表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posts (
    id            INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID，自增',
    user_id       INT NOT NULL COMMENT '发布者用户 ID（外键→users.id）',
    title         VARCHAR(256) NOT NULL COMMENT '帖子标题（题干）',
    content       TEXT NOT NULL COMMENT '帖子正文（题目描述，支持 Markdown）',
    answer        TEXT COMMENT '参考答案（发布时可不填）',
    images        VARCHAR(1024) DEFAULT '' COMMENT '图片列表，JSON 数组字符串',
    tech_stack    VARCHAR(64)  DEFAULT '其他' COMMENT '所属技术栈分类',
    difficulty    INT          DEFAULT 1 COMMENT '难度：1简单 2中等 3困难',
    is_solved     TINYINT(1)   DEFAULT 0 COMMENT '是否已解决：0否 1是',
    like_count    INT          DEFAULT 0 COMMENT '点赞数（冗余计数，切换式点赞维护）',
    comment_count INT          DEFAULT 0 COMMENT '评论数（含楼中楼，冗余计数）',
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '发布时间',
    KEY idx_posts_user (user_id),
    KEY idx_posts_tech (tech_stack),
    CONSTRAINT fk_posts_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='社区帖子';

-- ------------------------------------------------------------
-- 4. 帖子-标签 多对多关联表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS post_tags (
    post_id INT NOT NULL COMMENT '帖子 ID（外键→posts.id）',
    tag_id  INT NOT NULL COMMENT '标签 ID（外键→tags.id）',
    PRIMARY KEY (post_id, tag_id),
    KEY idx_post_tags_tag (tag_id),
    CONSTRAINT fk_post_tags_post FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE,
    CONSTRAINT fk_post_tags_tag FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='帖子标签关联';

-- ------------------------------------------------------------
-- 4b. 帖子点赞关联表（点赞只能一次，再点取消）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS post_likes (
    post_id    INT NOT NULL COMMENT '被点赞的帖子 ID（外键→posts.id）',
    user_id    INT NOT NULL COMMENT '点赞用户 ID（外键→users.id）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '点赞时间',
    PRIMARY KEY (post_id, user_id),
    KEY idx_post_likes_user (user_id),
    CONSTRAINT fk_post_likes_post FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE,
    CONSTRAINT fk_post_likes_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='帖子点赞关联';

-- ------------------------------------------------------------
-- 5. 评论表（楼中楼用 parent_id 自关联）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comments (
    id         INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID，自增',
    post_id    INT NOT NULL COMMENT '所属帖子 ID（外键→posts.id）',
    user_id    INT NOT NULL COMMENT '评论者用户 ID（外键→users.id）',
    content    TEXT NOT NULL COMMENT '评论内容',
    parent_id  INT DEFAULT NULL COMMENT '父评论 ID（外键→comments.id），NULL 表示顶级评论',
    is_adopted TINYINT(1) DEFAULT 0 COMMENT '是否被采纳为最佳答案：0否 1是',
    like_count INT DEFAULT 0 COMMENT '点赞数（冗余计数，切换式点赞维护）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '评论时间',
    KEY idx_comments_post (post_id),
    KEY idx_comments_user (user_id),
    KEY idx_comments_parent (parent_id),
    CONSTRAINT fk_comments_post FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_parent FOREIGN KEY (parent_id) REFERENCES comments (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='帖子评论';

-- ------------------------------------------------------------
-- 5b. 评论点赞关联表（同一人对同一评论只能点赞一次，再点取消）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comment_likes (
    comment_id INT NOT NULL COMMENT '被点赞的评论 ID（外键→comments.id）',
    user_id    INT NOT NULL COMMENT '点赞用户 ID（外键→users.id）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '点赞时间',
    PRIMARY KEY (comment_id, user_id),
    KEY idx_comment_likes_user (user_id),
    CONSTRAINT fk_comment_likes_comment FOREIGN KEY (comment_id) REFERENCES comments (id) ON DELETE CASCADE,
    CONSTRAINT fk_comment_likes_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评论点赞关联';

-- ------------------------------------------------------------
-- 6. 个人题库题目表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questions (
    id                INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID，自增',
    user_id           INT NOT NULL COMMENT '所属用户 ID（外键→users.id）',
    title             VARCHAR(256) NOT NULL COMMENT '题目标题（题干）',
    content           TEXT NOT NULL COMMENT '题目内容（描述/选项）',
    answer            TEXT COMMENT '参考答案',
    tech_stack        VARCHAR(64) DEFAULT '其他' COMMENT '所属技术栈分类',
    difficulty        INT         DEFAULT 1 COMMENT '难度：1简单 2中等 3困难',
    mastery           INT         DEFAULT 0 COMMENT '掌握程度：0未掌握 1学习中 2已掌握',
    source            VARCHAR(32) DEFAULT 'manual' COMMENT '来源：file_import=文件导入 / community=社区收藏 / manual=手动录入',
    source_post_id    INT DEFAULT NULL COMMENT '社区收藏来源帖子 ID（外键→posts.id），帖子删除后置空',
    published_post_id INT DEFAULT NULL COMMENT '已发布到社区的帖子 ID（外键→posts.id），帖子删除后置空',
    is_archived       TINYINT(1) DEFAULT 0 COMMENT '是否已归档（设为已掌握后自动归档）：0否 1是',
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    KEY idx_questions_user (user_id),
    KEY idx_questions_tech (tech_stack),
    KEY idx_questions_archived (is_archived),
    KEY idx_questions_source_post (source_post_id),
    KEY idx_questions_published_post (published_post_id),
    CONSTRAINT fk_questions_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_questions_source_post FOREIGN KEY (source_post_id) REFERENCES posts (id) ON DELETE SET NULL,
    CONSTRAINT fk_questions_published_post FOREIGN KEY (published_post_id) REFERENCES posts (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='个人题库题目';

-- ------------------------------------------------------------
-- 7. 题目-标签 多对多关联表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS question_tags (
    question_id INT NOT NULL COMMENT '题目 ID（外键→questions.id）',
    tag_id      INT NOT NULL COMMENT '标签 ID（外键→tags.id）',
    PRIMARY KEY (question_id, tag_id),
    KEY idx_question_tags_tag (tag_id),
    CONSTRAINT fk_question_tags_question FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE,
    CONSTRAINT fk_question_tags_tag FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='题目标签关联';

-- ------------------------------------------------------------
-- 8. 公共题库题目表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public_questions (
    id            INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID，自增',
    user_id       INT NOT NULL COMMENT '上传者用户 ID（外键→users.id）',
    title         VARCHAR(256) NOT NULL COMMENT '题目标题（题干）',
    content       TEXT NOT NULL COMMENT '题目内容（描述/选项）',
    answer        TEXT COMMENT '参考答案',
    tech_stack    VARCHAR(64) DEFAULT '其他' COMMENT '所属技术栈分类',
    difficulty    INT DEFAULT 1 COMMENT '难度：1简单 2中等 3困难',
    view_count    INT DEFAULT 0 COMMENT '浏览次数',
    comment_count INT DEFAULT 0 COMMENT '评论数（冗余计数）',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    KEY idx_pubq_user (user_id),
    KEY idx_pubq_tech (tech_stack),
    CONSTRAINT fk_pubq_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='公共题库题目';

-- ------------------------------------------------------------
-- 9. 公共题库评论表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public_comments (
    id          INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键 ID，自增',
    question_id INT NOT NULL COMMENT '所属公共题目 ID（外键→public_questions.id）',
    user_id     INT NOT NULL COMMENT '评论者用户 ID（外键→users.id）',
    content     TEXT NOT NULL COMMENT '评论内容',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '评论时间',
    KEY idx_pubc_question (question_id),
    KEY idx_pubc_user (user_id),
    CONSTRAINT fk_pubc_question FOREIGN KEY (question_id) REFERENCES public_questions (id) ON DELETE CASCADE,
    CONSTRAINT fk_pubc_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='公共题库评论';
