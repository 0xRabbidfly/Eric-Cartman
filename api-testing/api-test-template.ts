import { describe, it, expect, beforeAll, afterEach, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { GET, POST } from '@/app/api/ROUTE_PATH/route';
import { TableClient } from '@azure/data-tables';
import { getServerSession } from 'next-auth';

/**
 * API Route Test Template
 *
 * Replace ROUTE_PATH with your actual route (e.g., pages, search, health)
 */

// Mock authentication
vi.mock('next-auth', () => ({
  getServerSession: vi.fn()
}));

describe('API Route: /api/ROUTE_PATH', () => {
  let tableClient: TableClient;

  beforeAll(async () => {
    // Initialize Azurite test database
    tableClient = TableClient.fromConnectionString(
      'UseDevelopmentStorage=true',
      'TestTable'
    );
    await tableClient.createTable();
  });

  afterEach(async () => {
    // Clean up test data after each test
    const entities = tableClient.listEntities();
    for await (const entity of entities) {
      await tableClient.deleteEntity(entity.partitionKey, entity.rowKey);
    }
  });

  describe('GET', () => {
    it('should return 200 with valid data', async () => {
      // Seed test data
      await tableClient.createEntity({
        partitionKey: 'test',
        rowKey: '1',
        name: 'Test Item'
      });

      // Create request
      const request = new NextRequest('http://localhost:3000/api/ROUTE_PATH');

      // Call handler
      const response = await GET(request);

      // Assertions
      expect(response.status).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('success', true);
      expect(data.items).toHaveLength(1);
    });

    it('should return 401 when not authenticated', async () => {
      // Mock unauthenticated session
      vi.mocked(getServerSession).mockResolvedValue(null);

      const request = new NextRequest('http://localhost:3000/api/ROUTE_PATH');
      const response = await GET(request);

      expect(response.status).toBe(401);

      const data = await response.json();
      expect(data.error).toBe('Unauthorized');
    });

    it('should filter by query parameters', async () => {
      // Seed test data
      await tableClient.createEntity({
        partitionKey: 'page',
        rowKey: '1',
        pillarId: 'people-enablement'
      });
      await tableClient.createEntity({
        partitionKey: 'page',
        rowKey: '2',
        pillarId: 'sales-enablement'
      });

      // Request with query parameter
      const request = new NextRequest(
        'http://localhost:3000/api/ROUTE_PATH?pillarId=people-enablement'
      );

      const response = await GET(request);
      const data = await response.json();

      expect(data.items).toHaveLength(1);
      expect(data.items[0].pillarId).toBe('people-enablement');
    });
  });

  describe('POST', () => {
    beforeEach(() => {
      // Mock authenticated session
      vi.mocked(getServerSession).mockResolvedValue({
        user: {
          email: 'test@example.com',
          name: 'Test User',
          id: 'test-user-id'
        },
        expires: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
      });
    });

    it('should create a new entity', async () => {
      const requestBody = {
        name: 'New Item',
        description: 'Test description'
      };

      const request = new NextRequest('http://localhost:3000/api/ROUTE_PATH', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });

      const response = await POST(request);

      expect(response.status).toBe(201);

      const data = await response.json();
      expect(data).toHaveProperty('id');
      expect(data.name).toBe('New Item');
    });

    it('should return 400 for invalid input', async () => {
      const invalidBody = {
        name: '',  // Empty name (invalid)
      };

      const request = new NextRequest('http://localhost:3000/api/ROUTE_PATH', {
        method: 'POST',
        body: JSON.stringify(invalidBody)
      });

      const response = await POST(request);

      expect(response.status).toBe(400);

      const data = await response.json();
      expect(data).toHaveProperty('error');
    });

    it('should return 401 when not authenticated', async () => {
      vi.mocked(getServerSession).mockResolvedValue(null);

      const request = new NextRequest('http://localhost:3000/api/ROUTE_PATH', {
        method: 'POST',
        body: JSON.stringify({ name: 'Test' })
      });

      const response = await POST(request);

      expect(response.status).toBe(401);
    });
  });

  describe('Error Handling', () => {
    it('should return 500 when database fails', async () => {
      // Mock database error
      vi.spyOn(tableClient, 'listEntities').mockImplementation(() => {
        throw new Error('Database connection failed');
      });

      const request = new NextRequest('http://localhost:3000/api/ROUTE_PATH');
      const response = await GET(request);

      expect(response.status).toBe(500);

      const data = await response.json();
      expect(data.error).toBe('Internal server error');
    });
  });
});
