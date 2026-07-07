"""데모 데이터 생성 — 각 기능의 샘플 데이터를 생성하여 UI 미리보기 가능"""

import os
import cv2
import numpy as np
import random
from datetime import datetime, timedelta
import database
from paths import DATA_DIR

DEMO_NAMES = ["김철수", "이영희", "박민준", "최수진", "정하늘"]
DEMO_COLORS = [
    (255, 120, 80),   # 주황
    (80, 200, 120),   # 초록
    (100, 150, 255),  # 파랑
    (220, 180, 60),   # 노랑
    (180, 100, 220),  # 보라
]


def _generate_face_image(name: str, color: tuple, size: int = 128) -> np.ndarray:
    """이름 이니셜이 있는 컬러 아바타 이미지 생성"""
    img = np.zeros((size, size, 3), dtype=np.uint8)

    # 배경 그라디언트
    for y in range(size):
        ratio = y / size
        r = int(color[0] * (0.3 + 0.7 * ratio))
        g = int(color[1] * (0.3 + 0.7 * ratio))
        b = int(color[2] * (0.3 + 0.7 * ratio))
        img[y, :] = (b, g, r)

    # 원형 마스크
    center = (size // 2, size // 2)
    cv2.circle(img, center, size // 2 - 4, (int(color[2] * 0.8), int(color[1] * 0.8), int(color[0] * 0.8)), -1)

    # 이니셜 텍스트
    initial = name[0] if name else "?"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 2.0
    thickness = 3
    (tw, th), _ = cv2.getTextSize(initial, font, scale, thickness)
    tx = (size - tw) // 2
    ty = (size + th) // 2
    cv2.putText(img, initial, (tx, ty), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

    return img


def _generate_dummy_embedding() -> np.ndarray:
    """랜덤 512차원 임베딩 (데모용, 실제 매칭에는 사용 불가)"""
    emb = np.random.randn(512).astype(np.float32)
    emb /= np.linalg.norm(emb)
    return emb


def generate_demo_data():
    """전체 데모 데이터 생성"""
    database.init_db()

    # 이미 데모 데이터가 있는지 확인
    existing = database.get_all_visitors()
    if existing and len(existing) >= 3:
        return False  # 이미 데이터 있음

    now = datetime.now()

    # ── 1. 등록된 방문자 (5명) ──
    thumb_dir = os.path.join(DATA_DIR, "data", "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)

    visitor_ids = []
    for i, (name, color) in enumerate(zip(DEMO_NAMES, DEMO_COLORS)):
        vid = database.add_visitor(name)
        visitor_ids.append(vid)

        # 얼굴 이미지 저장
        face_img = _generate_face_image(name, color)
        face_path = os.path.join(thumb_dir, f"demo_{name}.jpg")
        cv2.imwrite(face_path, face_img)

        # 임베딩 2~3개 등록 (다중 각도 시뮬레이션)
        for j in range(random.randint(2, 4)):
            emb = _generate_dummy_embedding()
            database.add_embedding(vid, emb.tobytes())

    # ── 2. 방문 로그 (최근 7일) ──
    for day_offset in range(7):
        date = now - timedelta(days=day_offset)
        visit_count = random.randint(3, 12)
        for _ in range(visit_count):
            hour = random.randint(8, 18)
            minute = random.randint(0, 59)
            visit_time = date.replace(hour=hour, minute=minute, second=random.randint(0, 59))

            vid_idx = random.randint(0, len(visitor_ids) - 1)
            is_reg = random.random() > 0.3
            v_name = DEMO_NAMES[vid_idx] if is_reg else "미등록"
            v_id = visitor_ids[vid_idx] if is_reg else None

            # 썸네일
            color = DEMO_COLORS[vid_idx] if is_reg else (128, 128, 128)
            thumb_img = _generate_face_image(v_name, color, 80)
            ts_str = visit_time.strftime("%Y%m%d_%H%M%S")
            t_path = os.path.join(thumb_dir, f"demo_visit_{ts_str}.jpg")
            cv2.imwrite(t_path, thumb_img)

            database.execute(
                """INSERT INTO visit_logs (visitor_id, visitor_name, timestamp,
                   confidence, thumbnail_path, is_registered)
                   VALUES (?,?,?,?,?,?)""",
                (v_id, v_name, visit_time.strftime("%Y-%m-%d %H:%M:%S"),
                 round(random.uniform(0.6, 0.98), 2), t_path, 1 if is_reg else 0))

    # ── 3. 미등록 캡처 (pending_faces, 5개) ──
    pending_dir = os.path.join(DATA_DIR, "data", "pending_faces")
    os.makedirs(pending_dir, exist_ok=True)

    unknown_names = ["방문자A", "방문자B", "방문자C", "배달기사", "택배기사"]
    for i, uname in enumerate(unknown_names):
        color = (
            random.randint(100, 220),
            random.randint(100, 220),
            random.randint(100, 220),
        )
        face_img = _generate_face_image(uname, color, 100)
        capture_time = now - timedelta(hours=random.randint(1, 48))
        ts_str = capture_time.strftime("%Y%m%d_%H%M%S")
        img_path = os.path.join(pending_dir, f"demo_pending_{ts_str}_{i}.jpg")
        cv2.imwrite(img_path, face_img)

        emb = _generate_dummy_embedding()
        database.execute(
            "INSERT INTO pending_faces (image_path, embedding, captured_at, status) VALUES (?,?,?,?)",
            (img_path, emb.tobytes(), capture_time.strftime("%Y-%m-%d %H:%M:%S"), "pending"))

    # 휴지통에도 2개
    for i in range(2):
        color = (100, 100, 100)
        face_img = _generate_face_image("?", color, 100)
        ts_str = (now - timedelta(days=2, hours=i)).strftime("%Y%m%d_%H%M%S")
        img_path = os.path.join(pending_dir, f"demo_deleted_{ts_str}.jpg")
        cv2.imwrite(img_path, face_img)

        emb = _generate_dummy_embedding()
        database.execute(
            "INSERT INTO pending_faces (image_path, embedding, captured_at, status) VALUES (?,?,?,?)",
            (img_path, emb.tobytes(),
             (now - timedelta(days=2, hours=i)).strftime("%Y-%m-%d %H:%M:%S"), "deleted"))

    # ── 4. 녹화 샘플 (DB 레코드만, 파일은 더미) ──
    rec_dir = os.path.join(DATA_DIR, "recordings")
    os.makedirs(rec_dir, exist_ok=True)

    for i in range(4):
        rec_time = now - timedelta(days=i, hours=random.randint(0, 5))
        ts_str = rec_time.strftime("%Y%m%d_%H%M%S")
        rec_path = os.path.join(rec_dir, f"demo_rec_{ts_str}.avi")

        # 작은 더미 파일 생성 (실제 동영상은 아님)
        with open(rec_path, "wb") as f:
            f.write(b"\x00" * random.randint(1024 * 100, 1024 * 500))

        size = os.path.getsize(rec_path)
        end_time = rec_time + timedelta(minutes=random.randint(5, 30))
        database.execute(
            "INSERT INTO recordings (file_path, start_time, end_time, size_bytes) VALUES (?,?,?,?)",
            (rec_path, rec_time.strftime("%Y-%m-%d %H:%M:%S"),
             end_time.strftime("%Y-%m-%d %H:%M:%S"), size))

    return True


def clear_demo_data():
    """데모 데이터 삭제"""
    thumb_dir = os.path.join(DATA_DIR, "data", "thumbnails")
    pending_dir = os.path.join(DATA_DIR, "data", "pending_faces")
    rec_dir = os.path.join(DATA_DIR, "recordings")

    # demo_ 접두사 파일만 삭제
    for d in [thumb_dir, pending_dir, rec_dir]:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.startswith("demo_"):
                    os.remove(os.path.join(d, f))

    # 데모 데이터만 삭제 (실 데이터 보호)
    demo_names = tuple(DEMO_NAMES)
    placeholders = ",".join("?" * len(demo_names))

    # 데모 방문자 ID 조회
    demo_visitors = database.execute(
        f"SELECT id FROM visitors WHERE name IN ({placeholders})",
        demo_names, fetch="all")
    demo_vids = [r["id"] for r in (demo_visitors or [])]

    if demo_vids:
        vid_ph = ",".join("?" * len(demo_vids))
        database.execute(f"DELETE FROM visit_logs WHERE visitor_id IN ({vid_ph})", tuple(demo_vids))
        database.execute(f"DELETE FROM face_embeddings WHERE visitor_id IN ({vid_ph})", tuple(demo_vids))
        database.execute(f"DELETE FROM visitors WHERE id IN ({vid_ph})", tuple(demo_vids))

    # 미등록 방문 로그 (데모 썸네일 경로 패턴)
    database.execute("DELETE FROM visit_logs WHERE thumbnail_path LIKE '%demo_%'")

    # 데모 pending_faces / 녹화 (demo_ 접두사 경로)
    database.execute("DELETE FROM pending_faces WHERE image_path LIKE '%demo_%'")
    database.execute("DELETE FROM recordings WHERE file_path LIKE '%demo_%'")
