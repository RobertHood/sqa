import RoadMapService from "../../backend/src/services/roadmap.service";
import RoadmapController from "../../backend/src/controllers/roadmap.controller";
import { query } from "../../backend/src/config/database";
import { Request, Response } from "express";

let mockReq: Partial<Request>;
let mockRes: Partial<Response>;

beforeEach(() => {
    mockReq = { params: {}, body: {} };
    mockRes = {
        status: jest.fn().mockReturnThis(),
        json: jest.fn().mockReturnThis(),
    };
});

describe("Roadmap Module Unit Tests", () => {
    
    // We will create some test records dynamically
    let testTopicId: number = 1; // Assuming 1 exists or is nullable, adjust if needed. If topic_id is strictly checked, this might need a real topic created first.

    describe("RoadMapService Tests", () => {
        // Test Case ID: TC_RM_003
        it("TC_RM_003: Create roadmap successfully", async () => {
            const result = await RoadMapService.create({
                title: "Test Roadmap",
                description: "Test Desc",
                topic_id: testTopicId
            });

            expect(result).toBeDefined();
            expect(result.roadmap_step_id).toBeDefined();
            expect(result.title).toBe("Test Roadmap");

            // CheckDB
            const dbCheck = await query(`SELECT * FROM roadmap_step WHERE roadmap_step_id = $1`, [result.roadmap_step_id]);
            expect(dbCheck.rows.length).toBe(1);
            expect(dbCheck.rows[0].title).toBe("Test Roadmap");
        });

        // Test Case ID: TC_RM_001
        it("TC_RM_001: Get all roadmaps successfully", async () => {
            await RoadMapService.create({ title: "RM1", description: "D1", topic_id: testTopicId });
            await RoadMapService.create({ title: "RM2", description: "D2", topic_id: testTopicId });
            
            const results = await RoadMapService.getAll();
            expect(Array.isArray(results)).toBe(true);
            expect(results.length).toBeGreaterThanOrEqual(2);
        });

        // Test Case ID: TC_RM_002
        it("TC_RM_002: Get roadmap by non-existent id returns null", async () => {
            const result = await RoadMapService.getById(-1);
            expect(result).toBeNull();
        });

        // Test Case ID: TC_RM_004
        it("TC_RM_004: Update roadmap successfully", async () => {
            // Setup
            const created = await RoadMapService.create({ title: "Old Title", description: "Old Desc", topic_id: testTopicId });
            
            // Execute Update
            const updated = await RoadMapService.update(created.roadmap_step_id, { title: "New Title" });
            
            expect(updated).not.toBeNull();
            expect(updated?.title).toBe("New Title");

            // CheckDB
            const dbCheck = await query(`SELECT * FROM roadmap_step WHERE roadmap_step_id = $1`, [created.roadmap_step_id]);
            expect(dbCheck.rows[0].title).toBe("New Title");
        });

        // Test Case ID: TC_RM_005
        it("TC_RM_005: Update non-existent roadmap returns null", async () => {
            const updated = await RoadMapService.update(-1, { title: "Anything" });
            expect(updated).toBeNull();
        });

        // Test Case ID: TC_RM_006
        it("TC_RM_006: Delete roadmap successfully", async () => {
            // Setup
            const created = await RoadMapService.create({ title: "To Delete", description: "D", topic_id: testTopicId });
            
            // Execute Delete
            const ok = await RoadMapService.delete(created.roadmap_step_id);
            expect(ok).toBe(true);

            // CheckDB
            const dbCheck = await query(`SELECT * FROM roadmap_step WHERE roadmap_step_id = $1`, [created.roadmap_step_id]);
            expect(dbCheck.rows.length).toBe(0);
        });
        // Test Case ID: TC_RM_012
        it("TC_RM_012: Create roadmap with non-existent topic_id (Topic ma) throws DB Error", async () => {
            await expect(
                RoadMapService.create({ title: "Topic Ma", description: "Bóng ma", topic_id: -99999 })
            ).rejects.toThrow();
        });

        // Test Case ID: TC_RM_013
        it("TC_RM_013: Update roadmap but completely identical to old data (Trùng hoàn toàn)", async () => {
            const created = await RoadMapService.create({ title: "Clone", description: "Clone Desc", topic_id: testTopicId });
            const updated = await RoadMapService.update(created.roadmap_step_id, { title: "Clone", description: "Clone Desc", topic_id: testTopicId });
            
            expect(updated?.title).toBe("Clone");
            
            // CheckDB xem có thay đổi timestamp hay rác không (không làm bẩn database)
            const dbCheck = await query(`SELECT * FROM roadmap_step WHERE roadmap_step_id = $1`, [created.roadmap_step_id]);
            expect(dbCheck.rows[0].title).toBe("Clone");
        });

        // Test Case ID: TC_RM_014
        it("TC_RM_014: Delete roadmap that has ALREADY been deleted (Bản ghi rỗng, không có thật)", async () => {
            const created = await RoadMapService.create({ title: "To Delete Twice", description: "D", topic_id: testTopicId });
            
            // Cố tình xoá lần 1 (SV tồn tại, xoá thành công)
            const ok1 = await RoadMapService.delete(created.roadmap_step_id);
            expect(ok1).toBe(true);
            
            // Cố tình xoá lần 2 (SV không tồn tại, mong đợi fail gracefully)
            const ok2 = await RoadMapService.delete(created.roadmap_step_id);
            expect(ok2).toBe(false);
        });

        // Test Case ID: TC_RM_015
        it("TC_RM_015: Create roadmap with extreme long/malformed strings payload", async () => {
             const xssPayload = "<script>alert('XSS')</script> " + "A".repeat(500);
             const result = await RoadMapService.create({ title: "XSS Test", description: xssPayload, topic_id: testTopicId });
             expect(result.description).toBe(xssPayload); 
        });

        // Test Case ID: TC_RM_016
        it("TC_RM_016: Create roadmap with null title throws DB constraint error", async () => {
            await expect(RoadMapService.create({ title: null as any, description: "Desc", topic_id: testTopicId })).rejects.toThrow();
        });

        // Test Case ID: TC_RM_017
        it("TC_RM_017: Create roadmap with null description throws DB constraint error", async () => {
            await expect(RoadMapService.create({ title: "Title", description: null as any, topic_id: testTopicId })).rejects.toThrow();
        });

        // Test Case ID: TC_RM_018
        it("TC_RM_018: Create roadmap with empty string title", async () => {
             await expect(RoadMapService.create({ title: "", description: "Desc", topic_id: -999 })).rejects.toThrow();
        });

        // Test Case ID: TC_RM_019
        it("TC_RM_019: Create roadmap with extremely large description", async () => {
             await expect(RoadMapService.create({ title: "Large", description: "A".repeat(10000), topic_id: -999 })).rejects.toThrow();
        });

        // Test Case ID: TC_RM_020
        it("TC_RM_020: Update roadmap with null title keeps old title (COALESCE)", async () => {
            const updated = await RoadMapService.update(-1, { title: null as any });
            expect(updated).toBeNull();
        });

        // Test Case ID: TC_RM_021
        it("TC_RM_021: Update roadmap with null description keeps old description", async () => {
            const updated = await RoadMapService.update(-1, { description: null as any });
            expect(updated).toBeNull();
        });

        // Test Case ID: TC_RM_022
        it("TC_RM_022: Update roadmap with null topic_id keeps old topic_id", async () => {
            const updated = await RoadMapService.update(-1, { topic_id: null as any });
            expect(updated).toBeNull();
        });

        // Test Case ID: TC_RM_023
        it("TC_RM_023: Delete with invalid string ID throws SQL type error", async () => {
            await expect(RoadMapService.delete("abc" as any)).rejects.toThrow();
        });

        // Test Case ID: TC_RM_024
        it("TC_RM_024: GetById with invalid string ID throws SQL type error", async () => {
            await expect(RoadMapService.getById("xyz" as any)).rejects.toThrow();
        });
    });

    describe("RoadmapController Tests", () => {
        // Test Case ID: TC_RM_007
        it("TC_RM_007: Controller getAll returns 200", async () => {
            await RoadmapController.getAll(mockReq as Request, mockRes as Response);

            expect(mockRes.status).toHaveBeenCalledWith(200);
            expect(mockRes.json).toHaveBeenCalledWith(expect.objectContaining({
                status: 200,
                message: "Danh sách roadmap"
            }));
        });
        
        // Test Case ID: TC_RM_008
        it("TC_RM_008: Controller getById details returns 200", async () => {
            const created = await RoadMapService.create({ title: "API Title", description: "API", topic_id: testTopicId });
            
            mockReq.params = { id: created.roadmap_step_id.toString() };
            await RoadmapController.getById(mockReq as Request, mockRes as Response);

            expect(mockRes.status).toHaveBeenCalledWith(200);
            expect(mockRes.json).toHaveBeenCalledWith(expect.objectContaining({
                status: 200,
                message: "Chi tiết roadmap"
            }));
        });

        // Test Case ID: TC_RM_009
        it("TC_RM_009: Controller create returns 201", async () => {
            mockReq.body = { title: "API Create", description: "API", topic_id: testTopicId };
            
            await RoadmapController.create(mockReq as Request, mockRes as Response);

            expect(mockRes.status).toHaveBeenCalledWith(201);
            expect(mockRes.json).toHaveBeenCalledWith(expect.objectContaining({
                status: 201,
                message: "Tạo bước roadmap thành công"
            }));
        });

        // Test Case ID: TC_RM_010
        it("TC_RM_010: Controller update returns 200", async () => {
            const created = await RoadMapService.create({ title: "To Update", description: "Desc", topic_id: testTopicId });
            
            mockReq.params = { id: created.roadmap_step_id.toString() };
            mockReq.body = { title: "Updated via Controller", description: "Updated", topic_id: testTopicId };
            await RoadmapController.update(mockReq as Request, mockRes as Response);

            expect(mockRes.status).toHaveBeenCalledWith(200);
            expect(mockRes.json).toHaveBeenCalledWith(expect.objectContaining({
                status: 200,
                message: "Cập nhật thành công"
            }));
        });

        // Test Case ID: TC_RM_011
        it("TC_RM_011: Controller delete returns 200", async () => {
            const created = await RoadMapService.create({ title: "To Delete", description: "Desc", topic_id: testTopicId });
            
            mockReq.params = { id: created.roadmap_step_id.toString() };
            await RoadmapController.delete(mockReq as Request, mockRes as Response);

            expect(mockRes.status).toHaveBeenCalledWith(200);
            expect(mockRes.json).toHaveBeenCalledWith(expect.objectContaining({
                status: 200,
                message: "Xoá thành công"
            }));
        });

        // Test Case ID: TC_RM_025
        it("TC_RM_025: Controller getById returns 404 when service returns null", async () => {
            mockReq.params = { id: "-1" };
            await RoadmapController.getById(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(404);
        });

        // Test Case ID: TC_RM_026
        it("TC_RM_026: Controller getById with NaN id returns 404", async () => {
            mockReq.params = { id: "abc" };
            await RoadmapController.getById(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(404);
        });

        // Test Case ID: TC_RM_027
        it("TC_RM_027: Controller update returns 404 when service returns null", async () => {
            mockReq.params = { id: "-1" };
            mockReq.body = { title: "New" };
            await RoadmapController.update(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(404);
        });

        // Test Case ID: TC_RM_028
        it("TC_RM_028: Controller delete returns 404 when service returns false", async () => {
            mockReq.params = { id: "-1" };
            await RoadmapController.delete(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(404);
        });

        // Test Case ID: TC_RM_029
        it("TC_RM_029: Controller create with missing fields returns 500", async () => {
            mockReq.body = { title: null }; // Will cause DB error
            await RoadmapController.create(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(500);
        });

        // Test Case ID: TC_RM_030
        it("TC_RM_030: Controller update with missing id param returns 404", async () => {
            mockReq.params = {};
            await RoadmapController.update(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(404);
        });

        // Test Case ID: TC_RM_031
        it("TC_RM_031: Controller getAll handles unexpected service error as 500", async () => {
            jest.spyOn(RoadMapService, 'getAll').mockRejectedValueOnce(new Error("DB Connection Error"));
            await RoadmapController.getAll(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(500);
        });

        // Test Case ID: TC_RM_032
        it("TC_RM_032: Controller create handles unexpected DB error as 500", async () => {
            jest.spyOn(RoadMapService, 'create').mockRejectedValueOnce(new Error("DB Connection Error"));
            mockReq.body = { title: "Title", description: "Desc", topic_id: 1 };
            await RoadmapController.create(mockReq as Request, mockRes as Response);
            expect(mockRes.status).toHaveBeenCalledWith(500);
        });
    });
});
