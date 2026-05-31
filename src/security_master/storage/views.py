"""
Database views for Portfolio Performance export and data consolidation.
These views aggregate institutional transaction data into PP-compatible formats.
"""

from sqlalchemy import Engine, text

# Portfolio Performance Group-level Holdings View
VIEW_HOLDINGS_BY_GROUP = text(
    """
CREATE OR REPLACE VIEW v_holdings_by_group AS
SELECT
    -- Group identification
    ct.pp_group,

    -- Security identification (linked to securities master)
    COALESCE(sm.id, -1) as security_master_id,
    COALESCE(sm.name, ct.security_name) as security_name,
    COALESCE(sm.isin, ct.isin) as isin,
    COALESCE(sm.symbol, ct.symbol) as symbol,
    COALESCE(sm.currency, ct.currency) as currency,

    -- Classification from securities master
    sm.sector,
    sm.asset_classes_level1,
    sm.type_of_security_level1,
    sm.industries_gics_sectors_level1,
    sm.brx_plus_level1,

    -- Aggregated position data
    SUM(
        CASE
            WHEN ct.transaction_type IN ('BUY', 'DEPOSIT', 'TRANSFER_IN') THEN ct.quantity
            WHEN ct.transaction_type IN ('SELL', 'WITHDRAWAL', 'TRANSFER_OUT') THEN -ct.quantity
            ELSE 0
        END
    ) as total_quantity,

    -- Weighted average cost calculation
    SUM(
        CASE
            WHEN ct.transaction_type IN ('BUY', 'DEPOSIT', 'TRANSFER_IN') THEN ct.gross_amount
            WHEN ct.transaction_type IN ('SELL', 'WITHDRAWAL', 'TRANSFER_OUT') THEN -ct.gross_amount
            ELSE 0
        END
    ) as total_cost_basis,

    -- Average cost per share
    CASE
        WHEN SUM(
            CASE
                WHEN ct.transaction_type IN ('BUY', 'DEPOSIT', 'TRANSFER_IN') THEN ct.quantity
                WHEN ct.transaction_type IN ('SELL', 'WITHDRAWAL', 'TRANSFER_OUT') THEN -ct.quantity
                ELSE 0
            END
        ) > 0 THEN
            SUM(
                CASE
                    WHEN ct.transaction_type IN ('BUY', 'DEPOSIT', 'TRANSFER_IN') THEN ct.gross_amount
                    WHEN ct.transaction_type IN ('SELL', 'WITHDRAWAL', 'TRANSFER_OUT') THEN -ct.gross_amount
                    ELSE 0
                END
            ) / SUM(
                CASE
                    WHEN ct.transaction_type IN ('BUY', 'DEPOSIT', 'TRANSFER_IN') THEN ct.quantity
                    WHEN ct.transaction_type IN ('SELL', 'WITHDRAWAL', 'TRANSFER_OUT') THEN -ct.quantity
                    ELSE 0
                END
            )
        ELSE 0
    END as average_cost_per_share,

    -- Transaction summary
    COUNT(*) as transaction_count,
    MIN(ct.transaction_date) as first_transaction_date,
    MAX(ct.transaction_date) as last_transaction_date,

    -- Data quality indicators
    AVG(ct.quality_score) as avg_quality_score,
    COUNT(CASE WHEN ct.has_validation_issues THEN 1 END) as validation_issues_count,

    -- Source institution summary
    STRING_AGG(DISTINCT ct.source_institution, ', ') as source_institutions,
    COUNT(DISTINCT ct.source_institution) as institution_count,

    -- Audit information
    MAX(ct.updated_at) as last_updated

FROM transactions_consolidated ct
LEFT JOIN securities_master sm ON ct.security_master_id = sm.id
WHERE ct.quantity IS NOT NULL
  AND ct.quantity != 0
GROUP BY
    ct.pp_group,
    COALESCE(sm.id, -1),
    COALESCE(sm.name, ct.security_name),
    COALESCE(sm.isin, ct.isin),
    COALESCE(sm.symbol, ct.symbol),
    COALESCE(sm.currency, ct.currency),
    sm.sector,
    sm.asset_classes_level1,
    sm.type_of_security_level1,
    sm.industries_gics_sectors_level1,
    sm.brx_plus_level1
HAVING SUM(
    CASE
        WHEN ct.transaction_type IN ('BUY', 'DEPOSIT', 'TRANSFER_IN') THEN ct.quantity
        WHEN ct.transaction_type IN ('SELL', 'WITHDRAWAL', 'TRANSFER_OUT') THEN -ct.quantity
        ELSE 0
    END
) > 0;
""",
)

# Portfolio Performance Account-level Holdings View
VIEW_HOLDINGS_BY_ACCOUNT = text(
    """
CREATE OR REPLACE VIEW v_holdings_by_account AS
SELECT
    -- Account identification
    ct.pp_group,
    ct.pp_account,

    -- Security identification (linked to securities master)
    COALESCE(sm.id, -1) as security_master_id,
    COALESCE(sm.name, ct.security_name) as security_name,
    COALESCE(sm.isin, ct.isin) as isin,
    COALESCE(sm.symbol, ct.symbol) as symbol,
    COALESCE(sm.currency, ct.currency) as currency,

    -- Classification from securities master
    sm.sector,
    sm.asset_classes_level1,
    sm.type_of_security_level1,
    sm.industries_gics_sectors_level1,
    sm.brx_plus_level1,

    -- Position data
    SUM(
        CASE
            WHEN ct.transaction_type IN ('BUY', 'DEPOSIT', 'TRANSFER_IN') THEN ct.quantity
            WHEN ct.transaction_type IN ('SELL', 'WITHDRAWAL', 'TRANSFER_OUT') THEN -ct.quantity
            ELSE 0
        END
    ) as quantity,

    -- Cost basis
    SUM(
        CASE
            WHEN ct.transaction_type IN ('BUY', 'DEPOSIT', 'TRANSFER_IN') THEN ct.gross_amount
            WHEN ct.transaction_type IN ('SELL', 'WITHDRAWAL', 'TRANSFER_OUT') THEN -ct.gross_amount
            ELSE 0
        END
    ) as cost_basis,

    -- Total fees paid
    SUM(COALESCE(ct.fees_total, 0)) as total_fees,

    -- Average cost per share
    CASE
        WHEN SUM(
            CASE
                WHEN ct.transaction_type IN ('BUY', 'DEPOSIT', 'TRANSFER_IN') THEN ct.quantity
                WHEN ct.transaction_type IN ('SELL', 'WITHDRAWAL', 'TRANSFER_OUT') THEN -ct.quantity
                ELSE 0
            END
        ) > 0 THEN
            SUM(
                CASE
                    WHEN ct.transaction_type IN ('BUY', 'DEPOSIT', 'TRANSFER_IN') THEN ct.gross_amount
                    WHEN ct.transaction_type IN ('SELL', 'WITHDRAWAL', 'TRANSFER_OUT') THEN -ct.gross_amount
                    ELSE 0
                END
            ) / SUM(
                CASE
                    WHEN ct.transaction_type IN ('BUY', 'DEPOSIT', 'TRANSFER_IN') THEN ct.quantity
                    WHEN ct.transaction_type IN ('SELL', 'WITHDRAWAL', 'TRANSFER_OUT') THEN -ct.quantity
                    ELSE 0
                END
            )
        ELSE 0
    END as average_cost,

    -- Transaction summary
    COUNT(*) as transaction_count,
    MIN(ct.transaction_date) as first_purchase_date,
    MAX(ct.transaction_date) as last_transaction_date,

    -- Data quality
    AVG(ct.quality_score) as quality_score,
    BOOL_OR(ct.has_validation_issues) as has_validation_issues,
    STRING_AGG(DISTINCT ct.validation_notes, '; ') as validation_notes,

    -- Source tracking
    ct.source_institution as primary_source,
    STRING_AGG(DISTINCT ct.source_institution, ', ') as all_sources,

    -- Export status
    BOOL_OR(ct.exported_to_pp) as exported_to_pp,
    MAX(ct.export_date) as last_export_date,

    -- Audit
    MAX(ct.updated_at) as last_updated

FROM transactions_consolidated ct
LEFT JOIN securities_master sm ON ct.security_master_id = sm.id
WHERE ct.quantity IS NOT NULL
  AND ct.quantity != 0
GROUP BY
    ct.pp_group,
    ct.pp_account,
    COALESCE(sm.id, -1),
    COALESCE(sm.name, ct.security_name),
    COALESCE(sm.isin, ct.isin),
    COALESCE(sm.symbol, ct.symbol),
    COALESCE(sm.currency, ct.currency),
    sm.sector,
    sm.asset_classes_level1,
    sm.type_of_security_level1,
    sm.industries_gics_sectors_level1,
    sm.brx_plus_level1,
    ct.source_institution
HAVING SUM(
    CASE
        WHEN ct.transaction_type IN ('BUY', 'DEPOSIT', 'TRANSFER_IN') THEN ct.quantity
        WHEN ct.transaction_type IN ('SELL', 'WITHDRAWAL', 'TRANSFER_OUT') THEN -ct.quantity
        ELSE 0
    END
) > 0;
""",
)

# Consolidated Transactions for Portfolio Performance Export
VIEW_TRANSACTIONS_FOR_PP_EXPORT = text(
    """
CREATE OR REPLACE VIEW v_transactions_for_pp_export AS
SELECT
    ct.id,
    ct.transaction_date,
    ct.settlement_date,

    -- Security information with master data enhancement
    COALESCE(sm.name, ct.security_name) as security_name,
    COALESCE(sm.isin, ct.isin) as isin,
    COALESCE(sm.symbol, ct.symbol) as symbol,
    sm.wkn,

    -- Portfolio Performance account mapping
    ct.pp_group,
    ct.pp_account,

    -- Transaction details
    ct.transaction_type,
    ct.quantity,
    ct.price,
    ct.gross_amount,
    ct.fees_total,
    ct.net_amount,
    ct.currency,

    -- Enhanced classification from securities master
    sm.sector,
    sm.asset_classes_level1,
    sm.type_of_security_level1,
    sm.industries_gics_sectors_level1,
    sm.brx_plus_level1,
    sm.ter,
    sm.vendor,

    -- Data quality and source
    ct.source_institution,
    ct.quality_score,
    ct.has_validation_issues,

    -- Export tracking
    ct.exported_to_pp,
    ct.export_batch_id,
    ct.export_date,

    -- Portfolio Performance XML format fields
    CASE
        WHEN ct.transaction_type = 'BUY' THEN 'Kauf'
        WHEN ct.transaction_type = 'SELL' THEN 'Verkauf'
        WHEN ct.transaction_type = 'DIV' THEN 'Dividende'
        WHEN ct.transaction_type = 'DEPOSIT' THEN 'Einlage'
        WHEN ct.transaction_type = 'WITHDRAWAL' THEN 'Entnahme'
        WHEN ct.transaction_type = 'TRANSFER_IN' THEN 'Einbuchung'
        WHEN ct.transaction_type = 'TRANSFER_OUT' THEN 'Ausbuchung'
        ELSE ct.transaction_type
    END as pp_transaction_type,

    -- Note field for Portfolio Performance
    CONCAT(
        'Source: ', ct.source_institution,
        CASE WHEN ct.has_validation_issues THEN ' [Validation Issues]' ELSE '' END,
        CASE WHEN ct.quality_score < 0.8 THEN ' [Low Quality]' ELSE '' END
    ) as pp_note

FROM transactions_consolidated ct
LEFT JOIN securities_master sm ON ct.security_master_id = sm.id
WHERE ct.exported_to_pp = false
  AND ct.has_validation_issues = false
ORDER BY ct.transaction_date DESC, ct.pp_group, ct.pp_account;
""",
)

# Data Quality Summary View
VIEW_DATA_QUALITY_SUMMARY = text(
    """
CREATE OR REPLACE VIEW v_data_quality_summary AS
WITH institution_stats AS (
    SELECT
        source_institution,
        COUNT(*) as total_transactions,
        COUNT(CASE WHEN has_validation_issues THEN 1 END) as validation_issues,
        COUNT(CASE WHEN quality_score < 0.8 THEN 1 END) as low_quality,
        AVG(quality_score) as avg_quality_score,
        COUNT(CASE WHEN security_master_id IS NULL THEN 1 END) as unmatched_securities,
        COUNT(DISTINCT pp_group) as groups_count,
        COUNT(DISTINCT pp_account) as accounts_count,
        MIN(transaction_date) as earliest_transaction,
        MAX(transaction_date) as latest_transaction,
        MAX(updated_at) as last_updated
    FROM transactions_consolidated
    GROUP BY source_institution
),
kubera_comparison AS (
    SELECT
        ct.pp_group,
        ct.pp_account,
        COUNT(CASE WHEN ct.source_institution != 'kubera' THEN 1 END) as institution_transactions,
        COUNT(CASE WHEN ct.source_institution = 'kubera' THEN 1 END) as kubera_transactions,
        ABS(COUNT(CASE WHEN ct.source_institution != 'kubera' THEN 1 END) -
            COUNT(CASE WHEN ct.source_institution = 'kubera' THEN 1 END)) as transaction_variance
    FROM transactions_consolidated ct
    GROUP BY ct.pp_group, ct.pp_account
)
SELECT
    'institution_summary' as metric_type,
    ist.source_institution as dimension,
    ist.total_transactions as value,
    ist.validation_issues,
    ist.low_quality,
    ROUND(ist.avg_quality_score, 3) as avg_quality_score,
    ist.unmatched_securities,
    ist.groups_count,
    ist.accounts_count,
    ist.earliest_transaction,
    ist.latest_transaction,
    ist.last_updated
FROM institution_stats ist

UNION ALL

SELECT
    'variance_summary' as metric_type,
    CONCAT(kc.pp_group, ' - ', kc.pp_account) as dimension,
    kc.transaction_variance as value,
    kc.institution_transactions,
    kc.kubera_transactions,
    NULL as avg_quality_score,
    NULL as unmatched_securities,
    NULL as groups_count,
    NULL as accounts_count,
    NULL as earliest_transaction,
    NULL as latest_transaction,
    CURRENT_TIMESTAMP as last_updated
FROM kubera_comparison kc
WHERE kc.transaction_variance > 0
ORDER BY metric_type, value DESC;
""",
)


# Create all views function
def create_all_views(engine: Engine) -> None:
    """Create all consolidation views in the database.

    Args:
        engine (Engine): SQLAlchemy Engine connected to the target database.
    """
    with engine.connect() as conn:
        conn.execute(VIEW_HOLDINGS_BY_GROUP)
        conn.execute(VIEW_HOLDINGS_BY_ACCOUNT)
        conn.execute(VIEW_TRANSACTIONS_FOR_PP_EXPORT)
        conn.execute(VIEW_DATA_QUALITY_SUMMARY)
        conn.commit()


# Drop all views function
def drop_all_views(engine: Engine) -> None:
    """Drop all consolidation views from the database.

    Args:
        engine (Engine): SQLAlchemy Engine connected to the target database.
    """
    drop_statements = [
        "DROP VIEW IF EXISTS v_holdings_by_group CASCADE;",
        "DROP VIEW IF EXISTS v_holdings_by_account CASCADE;",
        "DROP VIEW IF EXISTS v_transactions_for_pp_export CASCADE;",
        "DROP VIEW IF EXISTS v_data_quality_summary CASCADE;",
    ]

    with engine.connect() as conn:
        for stmt in drop_statements:
            conn.execute(text(stmt))
        conn.commit()
