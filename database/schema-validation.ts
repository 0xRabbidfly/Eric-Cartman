/**
 * Schema Validation for AI-HUB-Portal Entities
 * Using Zod for runtime type validation
 */

import { z } from 'zod';

/**
 * Base Entity Schema
 * All Azure Table Storage entities have these fields
 */
const BaseEntitySchema = z.object({
  partitionKey: z.string(),
  rowKey: z.string(),
  timestamp: z.date().optional(),
  etag: z.string().optional(),
});

/**
 * Portal Page Entity Schema
 * Represents navigation pages in the portal
 */
export const PortalPageSchema = BaseEntitySchema.extend({
  partitionKey: z.literal('page'),
  rowKey: z.string().min(1, 'Page ID is required'),
  titleEn: z.string().min(1, 'English title is required'),
  titleFr: z.string().min(1, 'French title is required'),
  descriptionEn: z.string().optional(),
  descriptionFr: z.string().optional(),
  route: z.string().regex(/^\/[a-z0-9\-\/]*$/, 'Route must start with / and contain only lowercase letters, numbers, hyphens, and slashes'),
  parentPageId: z.string().nullable(),
  pillarId: z.string().nullable(),
  displayOrder: z.number().int().min(0, 'Display order must be non-negative'),
  isPublished: z.boolean(),
  lastModified: z.string().datetime(),
});

export type PortalPage = z.infer<typeof PortalPageSchema>;

/**
 * Pillar Entity Schema
 * Represents the four main content pillars
 */
export const PillarSchema = BaseEntitySchema.extend({
  partitionKey: z.literal('pillar'),
  rowKey: z.enum(['people-enablement', 'sales-enablement', 'ip-solutions', 'partnerships'], {
    errorMap: () => ({ message: 'Invalid pillar ID' })
  }),
  nameEn: z.string().min(1, 'English name is required'),
  nameFr: z.string().min(1, 'French name is required'),
  descriptionEn: z.string().min(1, 'English description is required'),
  descriptionFr: z.string().min(1, 'French description is required'),
  route: z.string().regex(/^\/[a-z\-]+$/, 'Route must be lowercase with hyphens'),
  icon: z.string(),
  color: z.string().regex(/^#[0-9A-Fa-f]{6}$/, 'Color must be a valid hex code'),
  displayOrder: z.number().int().min(1).max(4, 'Display order must be between 1 and 4'),
  isActive: z.boolean(),
  contactEmails: z.array(z.string().email()).optional(),
});

export type Pillar = z.infer<typeof PillarSchema>;

/**
 * Subcategory Entity Schema
 * Represents topic areas within pillars
 */
export const SubcategorySchema = BaseEntitySchema.extend({
  partitionKey: z.literal('subcategory'),
  rowKey: z.string().min(1, 'Subcategory ID is required'),
  pillarId: z.enum(['people-enablement', 'sales-enablement', 'ip-solutions', 'partnerships']),
  nameEn: z.string().min(1, 'English name is required'),
  nameFr: z.string().min(1, 'French name is required'),
  descriptionEn: z.string().optional(),
  descriptionFr: z.string().optional(),
  route: z.string().regex(/^\/[a-z0-9\-]+$/, 'Route must be lowercase with hyphens'),
  displayOrder: z.number().int().min(0),
  isActive: z.boolean(),
  featuredLinks: z.array(z.object({
    titleEn: z.string(),
    titleFr: z.string(),
    url: z.string().url(),
    descriptionEn: z.string().optional(),
    descriptionFr: z.string().optional(),
  })).optional(),
});

export type Subcategory = z.infer<typeof SubcategorySchema>;

/**
 * Content Item Entity Schema
 * Represents searchable content from SharePoint/Graph
 */
export const ContentItemSchema = BaseEntitySchema.extend({
  partitionKey: z.literal('content'),
  rowKey: z.string().min(1, 'Content ID is required'),
  titleEn: z.string().optional(),
  titleFr: z.string().optional(),
  title: z.string().min(1, 'Title is required'),
  url: z.string().url(),
  type: z.enum(['document', 'page', 'list-item', 'video', 'link']),
  pillarIds: z.array(z.string()),
  subcategoryIds: z.array(z.string()),
  tags: z.array(z.string()),
  summary: z.string().optional(),
  lastModified: z.string().datetime(),
  author: z.string().optional(),
});

export type ContentItem = z.infer<typeof ContentItemSchema>;

/**
 * Type Guards
 */

export function isPortalPage(entity: unknown): entity is PortalPage {
  return PortalPageSchema.safeParse(entity).success;
}

export function isPillar(entity: unknown): entity is Pillar {
  return PillarSchema.safeParse(entity).success;
}

export function isSubcategory(entity: unknown): entity is Subcategory {
  return SubcategorySchema.safeParse(entity).success;
}

export function isContentItem(entity: unknown): entity is ContentItem {
  return ContentItemSchema.safeParse(entity).success;
}

/**
 * Validation Functions
 */

export function validatePortalPage(entity: unknown): PortalPage {
  const result = PortalPageSchema.safeParse(entity);

  if (!result.success) {
    throw new Error(`Invalid PortalPage entity: ${result.error.message}`);
  }

  return result.data;
}

export function validatePillar(entity: unknown): Pillar {
  const result = PillarSchema.safeParse(entity);

  if (!result.success) {
    throw new Error(`Invalid Pillar entity: ${result.error.message}`);
  }

  return result.data;
}

export function validateSubcategory(entity: unknown): Subcategory {
  const result = SubcategorySchema.safeParse(entity);

  if (!result.success) {
    throw new Error(`Invalid Subcategory entity: ${result.error.message}`);
  }

  return result.data;
}

export function validateContentItem(entity: unknown): ContentItem {
  const result = ContentItemSchema.safeParse(entity);

  if (!result.success) {
    throw new Error(`Invalid ContentItem entity: ${result.error.message}`);
  }

  return result.data;
}

/**
 * Business Logic Validation
 */

/**
 * Validate navigation hierarchy depth doesn't exceed maximum
 * @param pages - All portal pages
 * @param pageId - Page ID to validate
 * @param maxDepth - Maximum allowed depth (default: 4)
 */
export function validateNavigationDepth(
  pages: PortalPage[],
  pageId: string,
  maxDepth: number = 4
): boolean {
  const pageMap = new Map(pages.map(p => [p.rowKey, p]));

  let depth = 0;
  let currentPageId: string | null = pageId;

  while (currentPageId && depth < maxDepth) {
    const page = pageMap.get(currentPageId);
    if (!page) {
      throw new Error(`Page not found: ${currentPageId}`);
    }

    currentPageId = page.parentPageId;
    depth++;
  }

  if (currentPageId !== null && depth === maxDepth) {
    throw new Error(
      `Navigation depth exceeds ${maxDepth} levels for page ${pageId}`
    );
  }

  return true;
}

/**
 * Validate route is unique across all pages
 */
export function validateUniqueRoute(pages: PortalPage[], newRoute: string, excludePageId?: string): boolean {
  const conflictingPage = pages.find(
    p => p.route === newRoute && p.rowKey !== excludePageId
  );

  if (conflictingPage) {
    throw new Error(
      `Route ${newRoute} is already used by page ${conflictingPage.rowKey}`
    );
  }

  return true;
}

/**
 * Validate pillar display orders are sequential (1, 2, 3, 4)
 */
export function validatePillarOrdering(pillars: Pillar[]): boolean {
  const orders = pillars.map(p => p.displayOrder).sort((a, b) => a - b);
  const expectedOrders = [1, 2, 3, 4];

  if (orders.length !== 4) {
    throw new Error('Must have exactly 4 pillars');
  }

  if (!orders.every((order, index) => order === expectedOrders[index])) {
    throw new Error('Pillar display orders must be 1, 2, 3, 4 (no duplicates or gaps)');
  }

  return true;
}

/**
 * Validate entity relationships
 */
export function validateRelationships(entity: PortalPage | Subcategory, pillars: Pillar[]): boolean {
  if ('pillarId' in entity && entity.pillarId) {
    const pillarExists = pillars.some(p => p.rowKey === entity.pillarId);

    if (!pillarExists) {
      throw new Error(
        `Referenced pillar ${entity.pillarId} does not exist`
      );
    }
  }

  return true;
}
