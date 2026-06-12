/**
 * PARWA Variant Instance Store
 *
 * Direct SQLite access for variant instance management.
 * Used as a fallback when the backend API is unavailable or returns errors.
 *
 * BC-001: All queries are scoped by company_id.
 * BC-012: Structured JSON responses.
 *
 * This module reads/writes to the backend's SQLite database directly
 * since the variant_instances table may not exist in the backend's
 * migration state yet. Creates it on first use if needed.
 */

import Database from 'better-sqlite3';
import { randomUUID } from 'crypto';
import path from 'path';

const DB_PATH = path.join(process.cwd(), 'backend', 'parwa_dev.db');

// Variant capacity defaults per type
const VARIANT_DEFAULTS: Record<string, {
  maxConcurrent: number;
  techniqueTier: number;
  model: string;
  accuracyRate: number;
  avgLatencyMs: number;
  costPerQuery: number;
}> = {
  mini_parwa: {
    maxConcurrent: 50,
    techniqueTier: 1,
    model: 'gpt-4o-mini',
    accuracyRate: 92.5,
    avgLatencyMs: 340,
    costPerQuery: 0.012,
  },
  parwa: {
    maxConcurrent: 200,
    techniqueTier: 2,
    model: 'gpt-4o',
    accuracyRate: 96.8,
    avgLatencyMs: 520,
    costPerQuery: 0.034,
  },
  parwa_high: {
    maxConcurrent: 500,
    techniqueTier: 3,
    model: 'claude-3.5-sonnet',
    accuracyRate: 98.2,
    avgLatencyMs: 680,
    costPerQuery: 0.058,
  },
};

// Display names
const VARIANT_NAMES: Record<string, string> = {
  mini_parwa: 'Mini PARWA',
  parwa: 'PARWA',
  parwa_high: 'PARWA High',
};

function getDb(): Database.Database {
  const db = new Database(DB_PATH);
  db.pragma('journal_mode = WAL');
  return db;
}

/**
 * Ensure the variant_instances table exists.
 * Idempotent — safe to call multiple times.
 */
export function ensureVariantInstancesTable(): void {
  const db = getDb();
  try {
    db.exec(`
      CREATE TABLE IF NOT EXISTS variant_instances (
        id TEXT PRIMARY KEY,
        company_id TEXT NOT NULL,
        instance_name TEXT NOT NULL,
        variant_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        channel_assignment TEXT NOT NULL DEFAULT '[]',
        capacity_config TEXT NOT NULL DEFAULT '{}',
        active_tickets_count INTEGER NOT NULL DEFAULT 0,
        total_tickets_handled INTEGER NOT NULL DEFAULT 0,
        last_activity_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE INDEX IF NOT EXISTS ix_var_inst_comp_type
        ON variant_instances(company_id, variant_type);

      CREATE INDEX IF NOT EXISTS ix_var_inst_comp_status
        ON variant_instances(company_id, status);
    `);
  } finally {
    db.close();
  }
}

/**
 * Insert a new variant instance for a company.
 * Returns the created instance data.
 */
export function insertVariantInstance(params: {
  companyId: string;
  variantType: string;
  instanceName?: string;
  channelAssignment?: string;
  capacityConfig?: Record<string, unknown>;
}): Record<string, unknown> {
  ensureVariantInstancesTable();

  const {
    companyId,
    variantType,
    instanceName = VARIANT_NAMES[variantType] || 'PARWA',
    channelAssignment = 'all',
    capacityConfig,
  } = params;

  const id = randomUUID();
  const defaults = VARIANT_DEFAULTS[variantType] || VARIANT_DEFAULTS.parwa;
  const config = capacityConfig || { max_concurrent: defaults.maxConcurrent };

  const db = getDb();
  try {
    db.prepare(`
      INSERT INTO variant_instances (
        id, company_id, instance_name, variant_type, status,
        channel_assignment, capacity_config,
        active_tickets_count, total_tickets_handled,
        last_activity_at, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, datetime('now'), datetime('now'), datetime('now'))
    `).run(
      id,
      companyId,
      instanceName,
      variantType,
      'active',
      JSON.stringify(channelAssignment === 'all'
        ? ['email', 'chat', 'sms']
        : Array.isArray(channelAssignment) ? channelAssignment : [channelAssignment]),
      JSON.stringify(config),
    );

    return getVariantInstance(companyId, id) as Record<string, unknown>;
  } finally {
    db.close();
  }
}

/**
 * Get a single variant instance by ID.
 */
export function getVariantInstance(
  companyId: string,
  instanceId: string,
): Record<string, unknown> | null {
  ensureVariantInstancesTable();

  const db = getDb();
  try {
    const row = db.prepare(`
      SELECT * FROM variant_instances
      WHERE id = ? AND company_id = ?
    `).get(instanceId, companyId) as Record<string, unknown> | undefined;

    if (!row) return null;

    return serializeRow(row);
  } finally {
    db.close();
  }
}

/**
 * List all variant instances for a company.
 * Returns array of VariantInstance objects matching the dashboard's expected format.
 */
export function listVariantInstances(
  companyId: string,
  status?: string,
): Record<string, unknown>[] {
  ensureVariantInstancesTable();

  const db = getDb();
  try {
    let rows: Record<string, unknown>[];

    if (status) {
      rows = db.prepare(`
        SELECT * FROM variant_instances
        WHERE company_id = ? AND status = ?
        ORDER BY created_at
      `).all(companyId, status) as Record<string, unknown>[];
    } else {
      rows = db.prepare(`
        SELECT * FROM variant_instances
        WHERE company_id = ?
        ORDER BY created_at
      `).all(companyId) as Record<string, unknown>[];
    }

    return rows.map(serializeRow);
  } finally {
    db.close();
  }
}

/**
 * Serialize a DB row to the format expected by the dashboard.
 */
function serializeRow(row: Record<string, unknown>): Record<string, unknown> {
  const variantType = String(row.variant_type || 'parwa');
  const defaults = VARIANT_DEFAULTS[variantType] || VARIANT_DEFAULTS.parwa;

  let channelAssignment: string[] = [];
  try {
    const raw = row.channel_assignment;
    channelAssignment = typeof raw === 'string' ? JSON.parse(raw) : Array.isArray(raw) ? raw : [];
  } catch { /* ignore */ }

  let capacityConfig: Record<string, unknown> = {};
  try {
    const raw = row.capacity_config;
    capacityConfig = typeof raw === 'string' ? JSON.parse(raw) : (raw as Record<string, unknown>) || {};
  } catch { /* ignore */ }

  const maxConcurrent = Number(capacityConfig.max_concurrent || defaults.maxConcurrent);
  const activeTickets = Number(row.active_tickets_count || 0);

  return {
    id: row.id,
    name: row.instance_name,
    variant_type: variantType,
    status: row.status || 'active',
    channel_assignment: channelAssignment.length === 1 && channelAssignment[0] === 'all'
      ? 'all'
      : channelAssignment.join(', '),
    capacity_config: { max_concurrent: maxConcurrent },
    current_load: Math.round((activeTickets / maxConcurrent) * 100),
    accuracy_rate: defaults.accuracyRate,
    avg_latency_ms: defaults.avgLatencyMs,
    cost_per_query: defaults.costPerQuery,
    technique_tier: defaults.techniqueTier,
    model: defaults.model,
    active_tickets_count: activeTickets,
    total_tickets_handled: Number(row.total_tickets_handled || 0),
    last_activity_at: row.last_activity_at,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

/**
 * Delete all variant instances for a company (for cleanup).
 */
export function deleteVariantInstances(companyId: string): number {
  ensureVariantInstancesTable();

  const db = getDb();
  try {
    const result = db.prepare(`
      DELETE FROM variant_instances WHERE company_id = ?
    `).run(companyId);
    return result.changes;
  } finally {
    db.close();
  }
}
