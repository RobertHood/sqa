/**
 * tests/helpers/redis.ts
 *
 * Tiện ích cleanup Redis key được tạo trong quá trình test.
 * Đảm bảo các test không bị nhiễm cache từ test trước (cross-test pollution).
 */

import { redis } from "../../../backend/src/config/redis";

/**
 * Xoá toàn bộ key Redis liên quan đến một exam cụ thể.
 * Bao gồm: cache full exam, ranking sorted set, ranking data cache,
 *           my-rank cache, user score hash.
 *
 * @param examId - ID của exam cần xoá cache
 */
export async function clearExamCache(examId: number): Promise<void> {
  // Tìm tất cả key theo pattern rồi xoá
  const pattern = `exam:${examId}:*`;
  const keys = await redis.keys(pattern);
  if (keys.length > 0) {
    await redis.del(...keys);
  }
}

/**
 * Xoá cache nhiều exam cùng lúc.
 *
 * @param examIds - Mảng exam ID
 */
export async function clearMultipleExamCaches(examIds: number[]): Promise<void> {
  for (const id of examIds) {
    await clearExamCache(id);
  }
}

/**
 * Kiểm tra key Redis có tồn tại không.
 *
 * @param key - Redis key cần kiểm tra
 * @returns true nếu key tồn tại
 */
export async function keyExists(key: string): Promise<boolean> {
  const result = await redis.exists(key);
  return result === 1;
}

/**
 * Seed dữ liệu ranking cho một exam vào Redis.
 * Dùng trong các test kiểm tra list (top3) và getExamRanking.
 *
 * @param examId   - ID exam
 * @param entries  - Danh sách user với điểm và thời gian làm
 */
export async function seedExamRanking(
  examId: number,
  entries: Array<{
    user_id: number;
    user_name: string;
    score: number;
    time_test: number;
  }>
): Promise<void> {
  const rankingKey = `exam:${examId}:ranking`;

  for (const e of entries) {
    // final_score = floor(score*1000)*1_000_000 + (1_000_000 - time_test)
    const scoreInt = Math.floor(e.score * 1000);
    const finalScore = scoreInt * 1_000_000 + (1_000_000 - e.time_test);

    await redis.zadd(
      rankingKey,
      finalScore,
      JSON.stringify({ user_id: e.user_id, user_name: e.user_name })
    );

    // Hash lưu chi tiết cho mỗi user
    await redis.hset(`exam:${examId}:user:${e.user_id}`, {
      score: e.score,
      time_test: e.time_test,
    });
  }
}

/**
 * Đóng kết nối Redis (gọi trong afterAll).
 */
export async function closeRedis(): Promise<void> {
  await redis.quit();
}
