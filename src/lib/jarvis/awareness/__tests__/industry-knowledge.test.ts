/**
 * Industry Knowledge Loader Tests
 * 
 * Tests for industry-specific knowledge loading and awareness.
 */

import {
  IndustryKnowledgeLoader,
  createIndustryKnowledgeLoader,
  getIndustryKnowledgeLoader,
} from '../industry-knowledge-loader';
import type { Industry } from '../../integration/types';

describe('IndustryKnowledgeLoader', () => {
  let loader: IndustryKnowledgeLoader;

  beforeEach(() => {
    loader = createIndustryKnowledgeLoader();
  });

  describe('loadIndustryKnowledge', () => {
    it('should load knowledge for ecommerce industry', async () => {
      const knowledge = await loader.loadIndustryKnowledge('ecommerce');
      
      expect(knowledge.industry).toBe('ecommerce');
      expect(knowledge.terminology).toBeDefined();
      expect(knowledge.commonQueries).toBeDefined();
      expect(knowledge.escalationTriggers).toBeDefined();
      expect(knowledge.responseTemplates).toBeDefined();
    });

    it('should load knowledge for saas industry', async () => {
      const knowledge = await loader.loadIndustryKnowledge('saas');
      
      expect(knowledge.industry).toBe('saas');
      expect(knowledge.terminology['subscription']).toBe('Recurring plan');
      expect(knowledge.terminology['mrr']).toBe('Monthly revenue');
    });

    it('should load knowledge for logistics industry', async () => {
      const knowledge = await loader.loadIndustryKnowledge('logistics');
      
      expect(knowledge.industry).toBe('logistics');
      expect(knowledge.terminology['shipment']).toBe('Package delivery');
      expect(knowledge.terminology['pod']).toBe('Delivery confirmation');
    });

    it('should return default knowledge for null industry', async () => {
      const knowledge = await loader.loadIndustryKnowledge(null);
      
      expect(knowledge.industry).toBeNull();
      expect(knowledge.terminology).toEqual({});
      expect(knowledge.commonQueries).toEqual([]);
    });

    it('should return default knowledge for undefined industry', async () => {
      const knowledge = await loader.loadIndustryKnowledge(undefined);
      
      expect(knowledge.industry).toBeNull();
    });
  });

  describe('getTerminology', () => {
    it('should return ecommerce terminology', () => {
      const terminology = loader.getTerminology('ecommerce');
      
      expect(terminology['order']).toBe('Purchase transaction');
      expect(terminology['cart']).toBe('Shopping basket');
      expect(terminology['sku']).toBe('Product identifier');
    });

    it('should return empty object for null industry', () => {
      const terminology = loader.getTerminology(null);
      expect(terminology).toEqual({});
    });
  });

  describe('getCommonQueries', () => {
    it('should return common queries for ecommerce', () => {
      const queries = loader.getCommonQueries('ecommerce');
      
      expect(queries).toContain('Where is my order?');
      expect(queries).toContain('I want to return this item');
      expect(queries.length).toBeGreaterThan(0);
    });

    it('should return common queries for saas', () => {
      const queries = loader.getCommonQueries('saas');
      
      expect(queries).toContain('How do I upgrade my plan?');
      expect(queries).toContain('I forgot my password');
    });
  });

  describe('hasEscalationTrigger', () => {
    it('should detect escalation trigger for ecommerce', () => {
      const hasTrigger = loader.hasEscalationTrigger('ecommerce', 'I want to report fraud');
      expect(hasTrigger).toBe(true);
    });

    it('should detect legal escalation trigger', () => {
      const hasTrigger = loader.hasEscalationTrigger('ecommerce', 'I am contacting my attorney');
      expect(hasTrigger).toBe(true);
    });

    it('should not trigger for normal message', () => {
      const hasTrigger = loader.hasEscalationTrigger('ecommerce', 'Where is my order?');
      expect(hasTrigger).toBe(false);
    });

    it('should detect BBB mention for ecommerce', () => {
      const hasTrigger = loader.hasEscalationTrigger('ecommerce', 'I will report to the BBB');
      expect(hasTrigger).toBe(true);
    });

    it('should return false for null industry', () => {
      const hasTrigger = loader.hasEscalationTrigger(null, 'fraud');
      expect(hasTrigger).toBe(false);
    });
  });

  describe('getResponseTemplate', () => {
    it('should return order status template for ecommerce', () => {
      const template = loader.getResponseTemplate('ecommerce', 'order_status');
      
      expect(template).toBeDefined();
      expect(template).toContain('{order_id}');
      expect(template).toContain('{status}');
    });

    it('should return subscription updated template for saas', () => {
      const template = loader.getResponseTemplate('saas', 'subscription_updated');
      
      expect(template).toBeDefined();
      expect(template).toContain('{plan}');
    });

    it('should return null for unknown scenario', () => {
      const template = loader.getResponseTemplate('ecommerce', 'unknown_scenario');
      expect(template).toBeNull();
    });

    it('should return null for null industry', () => {
      const template = loader.getResponseTemplate(null, 'order_status');
      expect(template).toBeNull();
    });
  });

  describe('caching', () => {
    it('should cache knowledge after first load', async () => {
      const loader = createIndustryKnowledgeLoader();
      
      // First load
      const knowledge1 = await loader.loadIndustryKnowledge('ecommerce');
      
      // Second load should return cached value
      const knowledge2 = await loader.loadIndustryKnowledge('ecommerce');
      
      expect(knowledge1).toBe(knowledge2);
    });

    it('should clear cache', async () => {
      const loader = createIndustryKnowledgeLoader();
      
      await loader.loadIndustryKnowledge('ecommerce');
      loader.clearCache();
      
      // After clearing, should load fresh
      const knowledge = await loader.loadIndustryKnowledge('ecommerce');
      expect(knowledge).toBeDefined();
    });
  });

  describe('singleton', () => {
    it('should return same instance from getIndustryKnowledgeLoader', () => {
      const loader1 = getIndustryKnowledgeLoader();
      const loader2 = getIndustryKnowledgeLoader();
      
      expect(loader1).toBe(loader2);
    });
  });

  describe('all industries', () => {
    const industries: Industry[] = [
      'saas', 'ecommerce', 'logistics', 'finance', 'education',
      'real_estate', 'manufacturing', 'consulting', 'agency',
      'nonprofit', 'hospitality', 'retail', 'other'
    ];

    it.each(industries)('should load knowledge for %s industry', async (industry) => {
      const knowledge = await loader.loadIndustryKnowledge(industry);
      
      expect(knowledge.industry).toBe(industry);
      expect(knowledge.terminology).toBeDefined();
      expect(knowledge.commonQueries).toBeDefined();
      expect(knowledge.escalationTriggers).toBeDefined();
    });
  });
});
