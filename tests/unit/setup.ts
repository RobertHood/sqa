import "dotenv/config";
import { PoolClient } from "pg";
import pool from "../../backend/src/config/database";

let client: PoolClient;

beforeAll(async () => {
    // Acquire a single connection from the pool to use across all transactions in this file
    client = await pool.connect();
    
    // Trap `pool.query` so that all application code calling `pool.query(...)` 
    // will actually use our SINGLE transactional `client` instead.
    jest.spyOn(pool, 'query').mockImplementation((text: any, params?: any) => {
        return client.query(text, params);
    });
});

beforeEach(async () => {
    // Bắt đầu một transaction bảo vệ dữ liệu DB trên mỗi unit test
    await client.query("BEGIN;");
});

afterEach(async () => {
    // Rollback mọi query đã insert/update/delete vào DB sau mỗi test để đưa DB về nguyên trạng
    await client.query("ROLLBACK;");
});

afterAll(async () => {
    // Giải phóng spy và trả kết nối lại cho pool
    jest.restoreAllMocks();
    client.release();
    await pool.end();
});
