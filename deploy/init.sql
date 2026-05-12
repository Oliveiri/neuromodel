-- ===================================================================
-- Neuro Demo 数据库初始化（7 张表）
-- MySQL 容器首次启动时自动执行
-- ===================================================================

-- 1. 用户表
CREATE TABLE IF NOT EXISTS `user` (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    password VARCHAR(256) NOT NULL,
    nickname VARCHAR(64) DEFAULT NULL,
    status INT DEFAULT 1 COMMENT '1=正常 0=禁用',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted INT DEFAULT 0,
    UNIQUE INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. WSI 切片表
CREATE TABLE IF NOT EXISTS wsi_slide (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    wsi_name VARCHAR(256) DEFAULT NULL,
    original_filename VARCHAR(256) DEFAULT NULL,
    tile_root_path VARCHAR(512) DEFAULT NULL,
    thumbnail_path VARCHAR(512) DEFAULT NULL,
    original_width INT DEFAULT NULL,
    original_height INT DEFAULT NULL,
    mpp DOUBLE DEFAULT 0,
    total_levels INT DEFAULT NULL,
    tile_size INT DEFAULT 256,
    preprocess_status INT DEFAULT 0 COMMENT '0=未处理 1=处理中 2=已完成 3=失败',
    scan_status INT DEFAULT 0 COMMENT '0=未扫描 1=扫描中 2=已完成 3=失败',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. 用户对话表
CREATE TABLE IF NOT EXISTS user_conversation (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    conversation_name VARCHAR(256) DEFAULT NULL,
    is_deleted INT DEFAULT 0,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    task_id BIGINT DEFAULT NULL,
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. 对话消息表
CREATE TABLE IF NOT EXISTS conversation_message (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversation_id BIGINT NOT NULL,
    role VARCHAR(16) NOT NULL COMMENT 'user / assistant / system',
    content TEXT,
    message_order INT NOT NULL,
    is_deleted INT DEFAULT 0,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    structured_data JSON DEFAULT NULL COMMENT '{toolName: {vizData, summaryForAgent}}',
    INDEX idx_conv_order (conversation_id, is_deleted, message_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. 对话关联 WSI 表
CREATE TABLE IF NOT EXISTS conversation_wsi (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversation_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    wsi_id BIGINT NOT NULL,
    wsi_level INT DEFAULT NULL,
    wsi_x INT DEFAULT NULL,
    wsi_y INT DEFAULT NULL,
    target_width INT DEFAULT NULL,
    target_height INT DEFAULT NULL,
    is_deleted INT DEFAULT 0,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conv (conversation_id),
    INDEX idx_msg (message_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. 分析任务表
CREATE TABLE IF NOT EXISTS analysis_task (
    task_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    wsi_slide_id BIGINT NOT NULL,
    status VARCHAR(32) DEFAULT 'PENDING',
    current_stage VARCHAR(32) DEFAULT NULL,
    low_power_result TEXT DEFAULT NULL,
    high_power_result TEXT DEFAULT NULL,
    result TEXT DEFAULT NULL,
    error_msg TEXT DEFAULT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    start_time DATETIME DEFAULT NULL,
    end_time DATETIME DEFAULT NULL,
    user_id BIGINT DEFAULT NULL,
    INDEX idx_wsi (wsi_slide_id),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. 全片肿瘤分类缓存表
CREATE TABLE IF NOT EXISTS wsi_tile_classification (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    wsi_id BIGINT NOT NULL,
    level INT NOT NULL DEFAULT 2,
    tile_x INT NOT NULL,
    tile_y INT NOT NULL,
    tile_width INT NOT NULL DEFAULT 256,
    tile_height INT NOT NULL DEFAULT 256,
    pred_class VARCHAR(64) DEFAULT NULL,
    confidence DOUBLE DEFAULT NULL,
    probs JSON DEFAULT NULL,
    is_tumor TINYINT(1) GENERATED ALWAYS AS (
      pred_class IN ('tumor_low_grade','tumor_high_grade')
    ) STORED,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_wsi_level (wsi_id, level),
    INDEX idx_wsi_tumor (wsi_id, is_tumor)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
