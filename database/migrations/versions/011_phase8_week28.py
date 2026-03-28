"""
Phase 8 Week 28 Database Migration.

Creates tables for:
- Category specialists
- Active learning
- A/B testing
- Rollback events
"""

from datetime import datetime
from typing import Optional

# Migration metadata
REVISION = "011"
DOWN_REVISION = "010"
BRANCH_LABELS = None
DEPENDS_ON = None


def upgrade() -> None:
    """
    Apply Phase 8 Week 28 schema changes.
    
    Creates tables for:
    - category_specialists: Specialist model metadata
    - active_learning_samples: Uncertain samples for labeling
    - feedback_items: Human feedback collection
    - experiments: A/B test experiments
    - experiment_variants: Experiment variants
    - rollback_events: Auto-rollback history
    - alerts: Alert history
    """
    
    # Category Specialists Table
    create_category_specialists_table = """
    CREATE TABLE IF NOT EXISTS category_specialists (
        id SERIAL PRIMARY KEY,
        specialist_id VARCHAR(50) UNIQUE NOT NULL,
        domain VARCHAR(50) NOT NULL,
        model_version VARCHAR(50) NOT NULL,
        accuracy FLOAT NOT NULL,
        accuracy_threshold FLOAT DEFAULT 0.92,
        training_samples INTEGER DEFAULT 0,
        last_trained_at TIMESTAMP WITH TIME ZONE,
        compliance_tags JSONB DEFAULT '[]',
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        CONSTRAINT valid_accuracy CHECK (accuracy >= 0 AND accuracy <= 1)
    );
    
    CREATE INDEX IF NOT EXISTS idx_specialists_domain ON category_specialists(domain);
    CREATE INDEX IF NOT EXISTS idx_specialists_accuracy ON category_specialists(accuracy);
    """
    
    # Active Learning Samples Table
    create_active_learning_samples_table = """
    CREATE TABLE IF NOT EXISTS active_learning_samples (
        id SERIAL PRIMARY KEY,
        sample_id VARCHAR(100) UNIQUE NOT NULL,
        client_id VARCHAR(50) NOT NULL,
        query TEXT NOT NULL,
        predicted_intent VARCHAR(100),
        predicted_confidence FLOAT,
        uncertainty_score FLOAT NOT NULL,
        sampling_strategy VARCHAR(50) NOT NULL,
        selected BOOLEAN DEFAULT FALSE,
        labeled BOOLEAN DEFAULT FALSE,
        correct_intent VARCHAR(100),
        labeled_by VARCHAR(100),
        labeled_at TIMESTAMP WITH TIME ZONE,
        priority INTEGER DEFAULT 3,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        CONSTRAINT valid_confidence CHECK (predicted_confidence >= 0 AND predicted_confidence <= 1),
        CONSTRAINT valid_uncertainty CHECK (uncertainty_score >= 0 AND uncertainty_score <= 1)
    );
    
    CREATE INDEX IF NOT EXISTS idx_samples_client ON active_learning_samples(client_id);
    CREATE INDEX IF NOT EXISTS idx_samples_uncertainty ON active_learning_samples(uncertainty_score);
    CREATE INDEX IF NOT EXISTS idx_samples_selected ON active_learning_samples(selected);
    """
    
    # Feedback Items Table
    create_feedback_items_table = """
    CREATE TABLE IF NOT EXISTS feedback_items (
        id SERIAL PRIMARY KEY,
        feedback_id VARCHAR(100) UNIQUE NOT NULL,
        sample_id VARCHAR(100) REFERENCES active_learning_samples(sample_id),
        client_id VARCHAR(50) NOT NULL,
        original_prediction VARCHAR(100),
        corrected_label VARCHAR(100) NOT NULL,
        source VARCHAR(50) NOT NULL,
        priority INTEGER DEFAULT 3,
        quality VARCHAR(20) DEFAULT 'medium',
        acknowledged BOOLEAN DEFAULT FALSE,
        acknowledged_by VARCHAR(100),
        acknowledged_at TIMESTAMP WITH TIME ZONE,
        notes TEXT,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        CONSTRAINT valid_priority CHECK (priority >= 1 AND priority <= 4),
        CONSTRAINT valid_quality CHECK (quality IN ('high', 'medium', 'low'))
    );
    
    CREATE INDEX IF NOT EXISTS idx_feedback_client ON feedback_items(client_id);
    CREATE INDEX IF NOT EXISTS idx_feedback_priority ON feedback_items(priority);
    """
    
    # Experiments Table
    create_experiments_table = """
    CREATE TABLE IF NOT EXISTS experiments (
        id SERIAL PRIMARY KEY,
        experiment_id VARCHAR(100) UNIQUE NOT NULL,
        name VARCHAR(200) NOT NULL,
        description TEXT,
        control_model VARCHAR(100) NOT NULL,
        treatment_model VARCHAR(100) NOT NULL,
        traffic_split FLOAT DEFAULT 0.10,
        min_sample_size INTEGER DEFAULT 1000,
        status VARCHAR(20) DEFAULT 'draft',
        started_at TIMESTAMP WITH TIME ZONE,
        ended_at TIMESTAMP WITH TIME ZONE,
        winner VARCHAR(20),
        results JSONB DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        CONSTRAINT valid_traffic_split CHECK (traffic_split >= 0 AND traffic_split <= 1),
        CONSTRAINT valid_status CHECK (status IN ('draft', 'running', 'paused', 'completed', 'stopped'))
    );
    
    CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
    """
    
    # Experiment Variants Table
    create_experiment_variants_table = """
    CREATE TABLE IF NOT EXISTS experiment_variants (
        id SERIAL PRIMARY KEY,
        variant_id VARCHAR(100) NOT NULL,
        experiment_id VARCHAR(100) REFERENCES experiments(experiment_id),
        variant_name VARCHAR(50) NOT NULL,
        model_version VARCHAR(100) NOT NULL,
        traffic_percentage FLOAT NOT NULL,
        accuracy FLOAT,
        sample_size INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        CONSTRAINT valid_variant_traffic CHECK (traffic_percentage >= 0 AND traffic_percentage <= 100),
        UNIQUE(experiment_id, variant_name)
    );
    
    CREATE INDEX IF NOT EXISTS idx_variants_experiment ON experiment_variants(experiment_id);
    """
    
    # Rollback Events Table
    create_rollback_events_table = """
    CREATE TABLE IF NOT EXISTS rollback_events (
        id SERIAL PRIMARY KEY,
        rollback_id VARCHAR(100) UNIQUE NOT NULL,
        trigger_type VARCHAR(50) NOT NULL,
        previous_version VARCHAR(100) NOT NULL,
        target_version VARCHAR(100) NOT NULL,
        success BOOLEAN NOT NULL,
        rollback_time_seconds FLOAT,
        drift_detected JSONB DEFAULT '{}',
        error_message TEXT,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        CONSTRAINT valid_trigger CHECK (trigger_type IN ('accuracy_drift', 'latency_degradation', 'error_rate_spike', 'manual', 'scheduled'))
    );
    
    CREATE INDEX IF NOT EXISTS idx_rollback_success ON rollback_events(success);
    CREATE INDEX IF NOT EXISTS idx_rollback_trigger ON rollback_events(trigger_type);
    """
    
    # Alerts Table
    create_alerts_table = """
    CREATE TABLE IF NOT EXISTS alerts (
        id SERIAL PRIMARY KEY,
        alert_id VARCHAR(100) UNIQUE NOT NULL,
        title VARCHAR(200) NOT NULL,
        message TEXT NOT NULL,
        severity VARCHAR(20) NOT NULL,
        channel VARCHAR(20) NOT NULL,
        acknowledged BOOLEAN DEFAULT FALSE,
        acknowledged_by VARCHAR(100),
        acknowledged_at TIMESTAMP WITH TIME ZONE,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        CONSTRAINT valid_severity CHECK (severity IN ('info', 'warning', 'error', 'critical')),
        CONSTRAINT valid_channel CHECK (channel IN ('log', 'email', 'slack', 'pagerduty', 'webhook'))
    );
    
    CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
    CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged);
    """
    
    # Model Versions Table (for tracking)
    create_model_versions_table = """
    CREATE TABLE IF NOT EXISTS model_versions (
        id SERIAL PRIMARY KEY,
        version VARCHAR(100) UNIQUE NOT NULL,
        model_type VARCHAR(50) NOT NULL,
        accuracy FLOAT,
        training_samples INTEGER DEFAULT 0,
        active BOOLEAN DEFAULT FALSE,
        deployed_at TIMESTAMP WITH TIME ZONE,
        rolled_back_at TIMESTAMP WITH TIME ZONE,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        CONSTRAINT valid_model_type CHECK (model_type IN ('general', 'ecommerce', 'saas', 'healthcare', 'financial'))
    );
    
    CREATE INDEX IF NOT EXISTS idx_model_versions_active ON model_versions(active);
    CREATE INDEX IF NOT EXISTS idx_model_versions_type ON model_versions(model_type);
    """
    
    # Insert default model version
    insert_default_version = """
    INSERT INTO model_versions (version, model_type, accuracy, active, deployed_at)
    VALUES ('v1.0.0', 'general', 0.88, true, NOW())
    ON CONFLICT (version) DO NOTHING;
    """
    
    # Execute all statements
    statements = [
        create_category_specialists_table,
        create_active_learning_samples_table,
        create_feedback_items_table,
        create_experiments_table,
        create_experiment_variants_table,
        create_rollback_events_table,
        create_alerts_table,
        create_model_versions_table,
        insert_default_version,
    ]
    
    for statement in statements:
        # In production, would execute via SQLAlchemy/Alembic
        print(f"Would execute: {statement[:100]}...")


def downgrade() -> None:
    """
    Reverse Phase 8 Week 28 schema changes.
    """
    tables = [
        "model_versions",
        "alerts",
        "rollback_events",
        "experiment_variants",
        "experiments",
        "feedback_items",
        "active_learning_samples",
        "category_specialists",
    ]
    
    for table in tables:
        drop_statement = f"DROP TABLE IF EXISTS {table} CASCADE;"
        print(f"Would execute: {drop_statement}")


def get_migration_info() -> dict:
    """Get migration information."""
    return {
        "revision": REVISION,
        "down_revision": DOWN_REVISION,
        "description": "Phase 8 Week 28: Category specialists, Active learning, A/B testing, Auto-rollback",
        "tables_created": [
            "category_specialists",
            "active_learning_samples",
            "feedback_items",
            "experiments",
            "experiment_variants",
            "rollback_events",
            "alerts",
            "model_versions",
        ],
        "created_at": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    print("Phase 8 Week 28 Migration")
    print("=" * 50)
    info = get_migration_info()
    for key, value in info.items():
        print(f"{key}: {value}")
