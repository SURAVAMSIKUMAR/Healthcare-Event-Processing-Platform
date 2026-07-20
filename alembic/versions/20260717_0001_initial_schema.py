"""initial schema

Revision ID: 20260717_0001
Revises:
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260717_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.Enum("VITALS", "LAB_RESULT", "MEDICATION_ORDER", "PATIENT_ADMISSION", "PATIENT_DISCHARGE", name="event_type"), nullable=False),
        sa.Column("patient_id", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.Enum("RECEIVED", "ENQUEUED", "FAILED", name="ingestion_status"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_raw_events_event_id", "raw_events", ["event_id"], unique=False)
    op.create_index("ix_raw_events_patient_id", "raw_events", ["patient_id"], unique=False)
    op.create_index("ix_raw_events_status", "raw_events", ["status"], unique=False)
    op.create_index("ix_raw_events_patient_time", "raw_events", ["patient_id", "occurred_at"], unique=False)

    op.create_table(
        "patients",
        sa.Column("patient_id", sa.String(length=128), nullable=False),
        sa.Column("hospital", sa.String(length=128), nullable=True),
        sa.Column("department", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("patient_id"),
    )
    op.create_index("ix_patients_hospital", "patients", ["hospital"], unique=False)
    op.create_index("ix_patients_department", "patients", ["department"], unique=False)
    op.create_index("ix_patients_is_active", "patients", ["is_active"], unique=False)

    op.create_table(
        "admissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admission_id", sa.String(length=128), nullable=False),
        sa.Column("patient_id", sa.String(length=128), nullable=False),
        sa.Column("hospital", sa.String(length=128), nullable=True),
        sa.Column("department", sa.String(length=128), nullable=True),
        sa.Column("status", sa.Enum("ACTIVE", "DISCHARGED", name="admission_record_status"), nullable=False),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("discharged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.patient_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admissions_admission_id", "admissions", ["admission_id"], unique=False)
    op.create_index("ix_admissions_patient_id", "admissions", ["patient_id"], unique=False)
    op.create_index("ix_admissions_hospital", "admissions", ["hospital"], unique=False)
    op.create_index("ix_admissions_department", "admissions", ["department"], unique=False)
    op.create_index("ix_admissions_status", "admissions", ["status"], unique=False)
    op.create_index("ix_admissions_patient_admitted", "admissions", ["patient_id", "admitted_at"], unique=False)

    op.create_table(
        "processed_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("normalized_data", sa.JSON(), nullable=False),
        sa.Column("processing_status", sa.Enum("PROCESSED", "FAILED", name="processing_status"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["raw_event_id"], ["raw_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_processed_events_event_id", "processed_events", ["event_id"], unique=False)
    op.create_index("ix_processed_events_patient_id", "processed_events", ["patient_id"], unique=False)
    op.create_index("ix_processed_events_event_type", "processed_events", ["event_type"], unique=False)

    op.create_table(
        "observations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("patient_id", sa.String(length=128), nullable=False),
        sa.Column("heart_rate", sa.Integer(), nullable=True),
        sa.Column("systolic_bp", sa.Integer(), nullable=True),
        sa.Column("diastolic_bp", sa.Integer(), nullable=True),
        sa.Column("temperature_c", sa.Numeric(5, 2), nullable=True),
        sa.Column("respiratory_rate", sa.Integer(), nullable=True),
        sa.Column("oxygen_saturation", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.patient_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_observations_event_id", "observations", ["event_id"], unique=False)
    op.create_index("ix_observations_patient_id", "observations", ["patient_id"], unique=False)
    op.create_index("ix_observations_observed_at", "observations", ["observed_at"], unique=False)
    op.create_index("ix_observations_patient_observed", "observations", ["patient_id", "observed_at"], unique=False)

    op.create_table(
        "lab_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("patient_id", sa.String(length=128), nullable=False),
        sa.Column("test_name", sa.String(length=128), nullable=False),
        sa.Column("value", sa.String(length=128), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("reference_range", sa.String(length=64), nullable=False),
        sa.Column("abnormal_flag", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.patient_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lab_results_event_id", "lab_results", ["event_id"], unique=False)
    op.create_index("ix_lab_results_patient_id", "lab_results", ["patient_id"], unique=False)
    op.create_index("ix_lab_results_test_name", "lab_results", ["test_name"], unique=False)
    op.create_index("ix_lab_results_abnormal_flag", "lab_results", ["abnormal_flag"], unique=False)
    op.create_index("ix_lab_results_observed_at", "lab_results", ["observed_at"], unique=False)
    op.create_index("ix_lab_results_patient_observed", "lab_results", ["patient_id", "observed_at"], unique=False)

    op.create_table(
        "medication_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("patient_id", sa.String(length=128), nullable=False),
        sa.Column("medication_name", sa.String(length=128), nullable=False),
        sa.Column("dose", sa.String(length=64), nullable=False),
        sa.Column("route", sa.String(length=64), nullable=False),
        sa.Column("frequency", sa.String(length=64), nullable=False),
        sa.Column("ordered_by", sa.String(length=128), nullable=False),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.patient_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_medication_orders_event_id", "medication_orders", ["event_id"], unique=False)
    op.create_index("ix_medication_orders_patient_id", "medication_orders", ["patient_id"], unique=False)
    op.create_index("ix_medication_orders_ordered_at", "medication_orders", ["ordered_at"], unique=False)
    op.create_index("ix_medication_orders_patient_ordered", "medication_orders", ["patient_id", "ordered_at"], unique=False)

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("operator", sa.Enum("LT", "LTE", "GT", "GTE", "EQ", "BETWEEN", "OUTSIDE_RANGE", name="rule_operator"), nullable=False),
        sa.Column("value_num", sa.Float(), nullable=True),
        sa.Column("value_min", sa.Float(), nullable=True),
        sa.Column("value_max", sa.Float(), nullable=True),
        sa.Column("severity", sa.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="alert_severity"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_alert_rules_code", "alert_rules", ["code"], unique=False)
    op.create_index("ix_alert_rules_event_type", "alert_rules", ["event_type"], unique=False)

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("patient_id", sa.String(length=128), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="alert_severity_ref"), nullable=False),
        sa.Column("status", sa.Enum("OPEN", "ACKNOWLEDGED", "RESOLVED", name="alert_status"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=128), nullable=True),
        sa.Column("acknowledgement_note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_event_id", "alerts", ["event_id"], unique=False)
    op.create_index("ix_alerts_patient_id", "alerts", ["patient_id"], unique=False)
    op.create_index("ix_alerts_rule_code", "alerts", ["rule_code"], unique=False)
    op.create_index("ix_alerts_severity_status_time", "alerts", ["severity", "status", "triggered_at"], unique=False)

    op.create_table(
        "patient_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.String(length=128), nullable=False),
        sa.Column("hospital", sa.String(length=128), nullable=True),
        sa.Column("department", sa.String(length=128), nullable=True),
        sa.Column("admission_status", sa.Enum("UNKNOWN", "ADMITTED", "DISCHARGED", name="admission_status"), nullable=False),
        sa.Column("latest_event_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_clinical_values", sa.JSON(), nullable=False),
        sa.Column("active_critical_alert_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_id"),
    )
    op.create_index("ix_patient_states_patient_id", "patient_states", ["patient_id"], unique=False)
    op.create_index("ix_patient_states_hospital_department", "patient_states", ["hospital", "department"], unique=False)

    op.create_table(
        "failed_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("raw_event_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("error_type", sa.String(length=128), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("dead_letter_payload", sa.JSON(), nullable=False),
        sa.Column("moved_to_dead_letter_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["raw_event_id"], ["raw_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_failed_events_event_id", "failed_events", ["event_id"], unique=False)

    op.create_table(
        "processing_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("patient_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.Enum("STARTED", "SUCCESS", "FAILED", name="processing_history_status"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("processor", sa.String(length=128), nullable=False),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_history_event_id", "processing_history", ["event_id"], unique=False)
    op.create_index("ix_processing_history_patient_id", "processing_history", ["patient_id"], unique=False)
    op.create_index("ix_processing_history_status", "processing_history", ["status"], unique=False)
    op.create_index("ix_processing_history_created_at", "processing_history", ["created_at"], unique=False)

    op.create_table(
        "hospital_summary_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("summary_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hospital", sa.String(length=128), nullable=False),
        sa.Column("department", sa.String(length=128), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("active_patient_count", sa.Integer(), nullable=False),
        sa.Column("critical_alert_count", sa.Integer(), nullable=False),
        sa.Column("total_processing_time_ms", sa.Integer(), nullable=False),
        sa.Column("processed_event_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("summary_date", "hospital", "department", name="uq_summary_day_hosp_dept"),
    )
    op.create_index("ix_hospital_summary_daily_summary_date", "hospital_summary_daily", ["summary_date"], unique=False)
    op.create_index("ix_hospital_summary_daily_hospital", "hospital_summary_daily", ["hospital"], unique=False)
    op.create_index("ix_hospital_summary_daily_department", "hospital_summary_daily", ["department"], unique=False)
    op.create_index("ix_summary_day_hosp_dept", "hospital_summary_daily", ["summary_date", "hospital", "department"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_summary_day_hosp_dept", table_name="hospital_summary_daily")
    op.drop_index("ix_hospital_summary_daily_department", table_name="hospital_summary_daily")
    op.drop_index("ix_hospital_summary_daily_hospital", table_name="hospital_summary_daily")
    op.drop_index("ix_hospital_summary_daily_summary_date", table_name="hospital_summary_daily")
    op.drop_table("hospital_summary_daily")

    op.drop_index("ix_processing_history_created_at", table_name="processing_history")
    op.drop_index("ix_processing_history_status", table_name="processing_history")
    op.drop_index("ix_processing_history_patient_id", table_name="processing_history")
    op.drop_index("ix_processing_history_event_id", table_name="processing_history")
    op.drop_table("processing_history")

    op.drop_index("ix_failed_events_event_id", table_name="failed_events")
    op.drop_table("failed_events")

    op.drop_index("ix_patient_states_patient_id", table_name="patient_states")
    op.drop_index("ix_patient_states_hospital_department", table_name="patient_states")
    op.drop_table("patient_states")

    op.drop_index("ix_alerts_rule_code", table_name="alerts")
    op.drop_index("ix_alerts_severity_status_time", table_name="alerts")
    op.drop_index("ix_alerts_patient_id", table_name="alerts")
    op.drop_index("ix_alerts_event_id", table_name="alerts")
    op.drop_table("alerts")

    op.drop_index("ix_alert_rules_event_type", table_name="alert_rules")
    op.drop_index("ix_alert_rules_code", table_name="alert_rules")
    op.drop_table("alert_rules")

    op.drop_index("ix_medication_orders_patient_ordered", table_name="medication_orders")
    op.drop_index("ix_medication_orders_ordered_at", table_name="medication_orders")
    op.drop_index("ix_medication_orders_patient_id", table_name="medication_orders")
    op.drop_index("ix_medication_orders_event_id", table_name="medication_orders")
    op.drop_table("medication_orders")

    op.drop_index("ix_lab_results_patient_observed", table_name="lab_results")
    op.drop_index("ix_lab_results_observed_at", table_name="lab_results")
    op.drop_index("ix_lab_results_abnormal_flag", table_name="lab_results")
    op.drop_index("ix_lab_results_test_name", table_name="lab_results")
    op.drop_index("ix_lab_results_patient_id", table_name="lab_results")
    op.drop_index("ix_lab_results_event_id", table_name="lab_results")
    op.drop_table("lab_results")

    op.drop_index("ix_observations_patient_observed", table_name="observations")
    op.drop_index("ix_observations_observed_at", table_name="observations")
    op.drop_index("ix_observations_patient_id", table_name="observations")
    op.drop_index("ix_observations_event_id", table_name="observations")
    op.drop_table("observations")

    op.drop_index("ix_processed_events_event_type", table_name="processed_events")
    op.drop_index("ix_processed_events_patient_id", table_name="processed_events")
    op.drop_index("ix_processed_events_event_id", table_name="processed_events")
    op.drop_table("processed_events")

    op.drop_index("ix_admissions_patient_admitted", table_name="admissions")
    op.drop_index("ix_admissions_status", table_name="admissions")
    op.drop_index("ix_admissions_department", table_name="admissions")
    op.drop_index("ix_admissions_hospital", table_name="admissions")
    op.drop_index("ix_admissions_patient_id", table_name="admissions")
    op.drop_index("ix_admissions_admission_id", table_name="admissions")
    op.drop_table("admissions")

    op.drop_index("ix_patients_is_active", table_name="patients")
    op.drop_index("ix_patients_department", table_name="patients")
    op.drop_index("ix_patients_hospital", table_name="patients")
    op.drop_table("patients")

    op.drop_index("ix_raw_events_patient_time", table_name="raw_events")
    op.drop_index("ix_raw_events_status", table_name="raw_events")
    op.drop_index("ix_raw_events_patient_id", table_name="raw_events")
    op.drop_index("ix_raw_events_event_id", table_name="raw_events")
    op.drop_table("raw_events")
