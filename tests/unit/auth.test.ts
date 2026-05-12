import AuthService from "../../backend/src/services/auth.service";
import AuthController from "../../backend/src/controllers/auth.controller";
import { query } from "../../backend/src/config/database";
import { Request, Response } from "express";

let mockReq: Partial<Request>;
let mockRes: Partial<Response>;

beforeEach(() => {
    mockReq = {};
    mockRes = {
        status: jest.fn().mockReturnThis(),
        json: jest.fn().mockReturnThis(),
    };
});

describe("Authentication Module Unit Tests", () => {

    describe("AuthService Tests", () => {
        // Test Case ID: TC_AUTH_001
        it("TC_AUTH_001: Register user successfully", async () => {
            const result = await AuthService.register("testuser", "password123", "test@test.com");
            expect(result.user).toBeDefined();
            expect(result.token).toBeDefined();
            expect(result.user.email).toBe("test@test.com");

            // CheckDB
            const dbCheck = await query(`SELECT * FROM "user" WHERE email = 'test@test.com'`);
            expect(dbCheck.rows.length).toBe(1);
        });

        // Test Case ID: TC_AUTH_002
        it("TC_AUTH_002: Register with existing email throws ERROR", async () => {
            await AuthService.register("testuser1", "password123", "exist@test.com");
            
            await expect(
                AuthService.register("testuser2", "password456", "exist@test.com")
            ).rejects.toThrow("EMAIL_EXISTS");
        });

        // Test Case ID: TC_AUTH_003
        it("TC_AUTH_003: Login with non-existent email throws USER_NOT_FOUND", async () => {
            await expect(
                AuthService.login("notfound@test.com", "password")
            ).rejects.toThrow("USER_NOT_FOUND");
        });

        // Test Case ID: TC_AUTH_004
        it("TC_AUTH_004: Login with correct email but wrong password throws INVALID_PASSWORD", async () => {
            await AuthService.register("testuser4", "correctpwd", "wrongpwd@test.com");

            await expect(
                AuthService.login("wrongpwd@test.com", "wrongpwd")
            ).rejects.toThrow("INVALID_PASSWORD");
        });

        // Test Case ID: TC_AUTH_005
        it("TC_AUTH_005: Login with locked account throws USER_NOT_AVAILABLE", async () => {
            // Setup DB directly to make available = false
            await query(`INSERT INTO "user" (user_name, email, password_hash, available) VALUES ('lockeduser', 'locked@test.com', 'hash', false)`);
            
            await expect(
                AuthService.login("locked@test.com", "password")
            ).rejects.toThrow("USER_NOT_AVAILABLE");
        });

        // Test Case ID: TC_AUTH_006
        it("TC_AUTH_006: Login successfully", async () => {
            await AuthService.register("testuser6", "password123", "success@test.com");

            const result = await AuthService.login("success@test.com", "password123");
            expect(result.user).toBeDefined();
            expect(result.token).toBeDefined();
            expect(result.permissions).toBeDefined();
            expect(result.user.email).toBe("success@test.com");
        });
        // Test Case ID: TC_AUTH_012
        it("TC_AUTH_012: Register with empty email throws constraint/validation ERROR", async () => {
            await expect(
                AuthService.register("emptyemail", "pwd", "")
            ).rejects.toThrow();
        });

        // Test Case ID: TC_AUTH_013
        it("TC_AUTH_013: Login with SQL Injection attempt (' OR '1'='1) is securely rejected", async () => {
             await expect(
                AuthService.login("admin' OR '1'='1", "password")
            ).rejects.toThrow("USER_NOT_FOUND");
        });

        // Test Case ID: TC_AUTH_009
        it("TC_AUTH_009: Register with null user_name throws constraint/validation ERROR", async () => {
            await expect(
                AuthService.register(null as any, "password123", "nulluser@test.com")
            ).rejects.toThrow();
        });

        // Test Case ID: TC_AUTH_010
        it("TC_AUTH_010: Register with null password throws validation ERROR", async () => {
            await expect(
                AuthService.register("nullpwd", null as any, "nullpwd@test.com")
            ).rejects.toThrow();
        });

        // Test Case ID: TC_AUTH_011
        it("TC_AUTH_011: Register with null email throws validation ERROR", async () => {
            await expect(
                AuthService.register("nullemail", "password123", null as any)
            ).rejects.toThrow();
        });

        // Test Case ID: TC_AUTH_014
        it("TC_AUTH_014: Login with null email throws USER_NOT_FOUND", async () => {
            await expect(
                AuthService.login(null as any, "password")
            ).rejects.toThrow();
        });

        // Test Case ID: TC_AUTH_015
        it("TC_AUTH_015: Login with null password throws error", async () => {
             await AuthService.register("nullpwdlogin", "password123", "nullpwdlogin@test.com");
             await expect(
                AuthService.login("nullpwdlogin@test.com", null as any)
            ).rejects.toThrow();
        });

        // Test Case ID: TC_AUTH_019
        it("TC_AUTH_019: Login with ADMIN_ROLE_ID returns admin permissions", async () => {
            const hash = await require("bcrypt").hash("adminpwd", 10);
            await query(`INSERT INTO "user" (user_name, email, password_hash, available, role_id) VALUES ('adminuser', 'admin@test.com', $1, true, 2)`, [hash]);
            
            const result = await AuthService.login("admin@test.com", "adminpwd");
            expect(result.permissions["admin:access"]).toBe(true);
            expect(result.permissions["*"]).toBe(true);
        });

        // Test Case ID: TC_AUTH_020
        it("TC_AUTH_020: Login with normal role_id returns empty permissions", async () => {
            await AuthService.register("normaluser", "pwd", "normal@test.com");
            const result = await AuthService.login("normal@test.com", "pwd");
            expect(Object.keys(result.permissions).length).toBe(0);
        });
    });

    describe("AuthController Tests", () => {
        // Test Case ID: TC_AUTH_007
        it("TC_AUTH_007: Controller register success returns 201", async () => {
            mockReq.body = { user_name: "ctrluser", password: "pwd", email: "ctrl@test.com" };

            await AuthController.register(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(201);
            expect(mockRes.json).toHaveBeenCalledWith(expect.objectContaining({
                status: 201,
                message: "Đăng ký thành công"
            }));
        });

        // Test Case ID: TC_AUTH_008
        it("TC_AUTH_008: Controller login success returns 200", async () => {
            await AuthService.register("loginctrl", "pwd", "loginctrl@test.com");

            mockReq.body = { email: "loginctrl@test.com", password: "pwd" };
            await AuthController.login(mockReq as Request, mockRes as Response);

            expect(mockRes.status).toHaveBeenCalledWith(200);
            expect(mockRes.json).toHaveBeenCalledWith(expect.objectContaining({
                status: 200,
                message: "Đăng nhập thành công"
            }));
        });

        // Test Case ID: TC_AUTH_016
        it("TC_AUTH_016: Controller register maps EMAIL_EXISTS error to 400", async () => {
            await AuthService.register("existctrl", "pwd", "existctrl@test.com");
            mockReq.body = { user_name: "existctrl2", password: "pwd", email: "existctrl@test.com" };

            await AuthController.register(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(400);
            expect(mockRes.json).toHaveBeenCalledWith(expect.objectContaining({
                status: 400,
                message: "Email đã tồn tại. Vui lòng chọn email khác!"
            }));
        });

        // Test Case ID: TC_AUTH_017
        it("TC_AUTH_017: Controller login maps USER_NOT_FOUND error to 404", async () => {
            mockReq.body = { email: "notfoundctrl@test.com", password: "pwd" };

            await AuthController.login(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(404);
            expect(mockRes.json).toHaveBeenCalledWith(expect.objectContaining({
                status: 404,
                message: "Không tìm thấy người dùng"
            }));
        });

        // Test Case ID: TC_AUTH_018
        it("TC_AUTH_018: Controller login maps INVALID_PASSWORD error to 401", async () => {
            await AuthService.register("invalidpwdctrl", "pwd123", "invalidpwdctrl@test.com");
            mockReq.body = { email: "invalidpwdctrl@test.com", password: "wrongpwd" };

            await AuthController.login(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(401);
            expect(mockRes.json).toHaveBeenCalledWith(expect.objectContaining({
                status: 401,
                message: "Mật khẩu không đúng"
            }));
        });

        // Test Case ID: TC_AUTH_021
        it("TC_AUTH_021: Controller register handles unexpected errors as 500", async () => {
            mockReq.body = { user_name: null, password: "pwd", email: "unexpected@test.com" }; // Will throw NOT NULL constraint
            await AuthController.register(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(500);
        });

        // Test Case ID: TC_AUTH_022
        it("TC_AUTH_022: Controller login handles unexpected errors as 500", async () => {
            mockReq.body = { email: "some@test.com", password: null }; // Will throw bcrypt error
            await AuthController.login(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(500);
        });
    });
});
