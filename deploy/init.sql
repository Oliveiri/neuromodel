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

-- 1.1 认证会话表
CREATE TABLE IF NOT EXISTS auth_session (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    token VARCHAR(512) NOT NULL,
    expire_at DATETIME NOT NULL,
    status INT DEFAULT 1,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_token (token),
    INDEX idx_user (user_id)
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
    level_sizes JSON DEFAULT NULL COMMENT '每层真实尺寸 [{level,w,h}]',
    scan_level INT DEFAULT 2 COMMENT 'M1四分类扫描层级（自动选最接近10×的层）',
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
    current_wsi_id BIGINT DEFAULT NULL COMMENT '当前正在查看的WSI',
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
    message_type VARCHAR(32) DEFAULT 'text' COMMENT 'text / report',
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

-- 7. 病理诊断报告表
CREATE TABLE IF NOT EXISTS report (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    wsi_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    conversation_id BIGINT DEFAULT NULL COMMENT '来源对话（可选）',
    title VARCHAR(256) DEFAULT '病理AI辅助诊断报告',
    status VARCHAR(32) DEFAULT 'GENERATING' COMMENT 'GENERATING / DRAFT / FINAL / FAILED',
    content JSON DEFAULT NULL COMMENT '结构化报告正文',
    error_message TEXT DEFAULT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_wsi (wsi_id),
    INDEX idx_user (user_id),
    INDEX idx_conv (conversation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. 全片肿瘤分类缓存表
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

-- 9. WSI 高级别区域预计算分析表（M1 完成后手动触发）
CREATE TABLE IF NOT EXISTS wsi_region_analysis (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    wsi_id BIGINT NOT NULL,
    level0_x INT NOT NULL,
    level0_y INT NOT NULL,
    level0_width INT NOT NULL,
    level0_height INT NOT NULL,
    ccrcc_json JSON COMMENT 'M2 ccRCC 完整RLE+统计',
    prcc_json JSON COMMENT 'M2 pRCC 完整RLE+统计',
    nuclei_json JSON COMMENT 'M3 核形态完整结果',
    cd3_image_url VARCHAR(512) COMMENT 'M4 CD3 染色图URL',
    cd3_viz_json JSON COMMENT 'M4 CD3 vizData',
    pax5_image_url VARCHAR(512) COMMENT 'M4 PAX5 染色图URL',
    pax5_viz_json JSON COMMENT 'M4 PAX5 vizData',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_wsi (wsi_id),
    INDEX idx_xy (wsi_id, level0_x, level0_y)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
