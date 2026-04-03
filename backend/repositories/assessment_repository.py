"""
Assessment Repository

Database operations for assessments and metadata
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime

from models.assessment import (
    Assessment,
    AssessmentDataset,
    AssessmentTable,
    AssessmentColumn,
    AssessmentView,
    AssessmentRoutine,
    AssessmentQueryStat,
    AssessmentMLModel,
    AssessmentSecurity
)
from models.assessment_log import AssessmentLog


class AssessmentRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def create_assessment(
        self,
        name: str,
        source_connection_id: int,
        target_connection_id: int,
        project_id: str,
        status: str = 'pending',
        created_by: str = None
    ) -> Assessment:
        """Create a new assessment record with auto-versioning.
        
        If an assessment with the same name and source_connection_id exists,
        the new one gets the next version number.
        """
        # Calculate next version for this name + source connection combo
        max_version = self.db.query(func.max(Assessment.version)).filter(
            Assessment.name == name,
            Assessment.source_connection_id == source_connection_id
        ).scalar() or 0
        
        next_version = max_version + 1
        
        assessment = Assessment(
            name=name,
            source_connection_id=source_connection_id,
            target_connection_id=target_connection_id,
            project_id=project_id,
            status=status,
            started_at=datetime.utcnow(),
            created_by=created_by,
            workspace_id=1,  # TODO: Get from auth context
            version=next_version,
            total_datasets=0,
            total_tables=0,
            total_views=0,
            total_routines=0,
            total_ml_models=0,
            total_size_mb=0.0
        )
        
        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)
        
        return assessment
    
    def get_by_id(self, assessment_id: int) -> Optional[Assessment]:
        """Get assessment by ID"""
        return self.db.query(Assessment).filter(
            Assessment.id == assessment_id
        ).first()
    
    def list_assessments(self) -> List[Assessment]:
        """List all assessments ordered by creation date"""
        return self.db.query(Assessment).order_by(
            Assessment.started_at.desc()
        ).all()
    
    def update_status(
        self,
        assessment_id: int,
        status: str,
        error_message: str = None
    ):
        """Update assessment status"""
        assessment = self.get_by_id(assessment_id)
        if assessment:
            assessment.status = status
            if error_message:
                assessment.error_message = error_message
            if status == 'completed':
                assessment.completed_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(assessment)
            print(f"[DEBUG] Assessment {assessment_id} status updated to: {status}")
    
    def update_totals(
        self,
        assessment_id: int,
        total_datasets: int = None,
        total_tables: int = None,
        total_views: int = None,
        total_routines: int = None,
        total_ml_models: int = None,
        total_size_mb: float = None
    ):
        """Update assessment totals"""
        assessment = self.get_by_id(assessment_id)
        if assessment:
            if total_datasets is not None:
                assessment.total_datasets = total_datasets
            if total_tables is not None:
                assessment.total_tables = total_tables
            if total_views is not None:
                assessment.total_views = total_views
            if total_routines is not None:
                assessment.total_routines = total_routines
            if total_ml_models is not None:
                assessment.total_ml_models = total_ml_models
            if total_size_mb is not None:
                assessment.total_size_mb = total_size_mb
            
            self.db.commit()

    def update_assessment_data(self, assessment_id: int, data: dict):
        """Update the assessment_data JSONB field."""
        assessment = self.get_by_id(assessment_id)
        if assessment:
            assessment.assessment_data = data
            self.db.commit()

    def delete_assessment(self, assessment_id: int):
        """Delete assessment (cascade will delete all related metadata)"""
        assessment = self.get_by_id(assessment_id)
        if assessment:
            self.db.delete(assessment)
            self.db.commit()
    
    def update_assessment(
        self,
        assessment_id: int,
        name: str = None,
        source_connection_id: int = None,
        target_connection_id: int = None
    ) -> Assessment:
        """Update assessment details"""
        assessment = self.get_by_id(assessment_id)
        if assessment:
            if name is not None:
                assessment.name = name
            if source_connection_id is not None:
                assessment.source_connection_id = source_connection_id
            if target_connection_id is not None:
                assessment.target_connection_id = target_connection_id
            
            self.db.commit()
            self.db.refresh(assessment)
        
        return assessment
    
    # Dataset operations
    def create_dataset(self, assessment_id: int, dataset_data: dict) -> AssessmentDataset:
        """Create dataset record with upsert logic to prevent duplicates"""
        # Check if dataset already exists
        existing = self.db.query(AssessmentDataset).filter(
            AssessmentDataset.assessment_id == assessment_id,
            AssessmentDataset.dataset_name == dataset_data['dataset_name']
        ).first()
        
        if existing:
            # Update existing record
            for key, value in dataset_data.items():
                setattr(existing, key, value)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new record
            dataset = AssessmentDataset(
                assessment_id=assessment_id,
                **dataset_data
            )
            self.db.add(dataset)
            self.db.commit()
            self.db.refresh(dataset)
            return dataset
    
    def get_dataset_summary(self, assessment_id: int) -> List[dict]:
        """Get dataset summary with table counts and sizes"""
        results = self.db.query(
            AssessmentDataset.dataset_name,
            AssessmentDataset.creation_time,
            AssessmentDataset.location,
            func.count(AssessmentTable.id).label('table_count'),
            func.coalesce(func.sum(AssessmentTable.size_mb), 0).label('total_size_mb')
        ).outerjoin(
            AssessmentTable,
            (AssessmentTable.assessment_id == AssessmentDataset.assessment_id) &
            (AssessmentTable.dataset_name == AssessmentDataset.dataset_name)
        ).filter(
            AssessmentDataset.assessment_id == assessment_id
        ).group_by(
            AssessmentDataset.dataset_name,
            AssessmentDataset.creation_time,
            AssessmentDataset.location
        ).all()
        
        return [
            {
                'dataset_name': r.dataset_name,
                'creation_time': r.creation_time,
                'location': r.location,
                'table_count': r.table_count,
                'total_size_mb': float(r.total_size_mb)
            }
            for r in results
        ]
    
    # Table operations
    def create_table(self, assessment_id: int, table_data: dict) -> AssessmentTable:
        """Create table record with upsert logic to prevent duplicates"""
        # Check if table already exists
        existing = self.db.query(AssessmentTable).filter(
            AssessmentTable.assessment_id == assessment_id,
            AssessmentTable.dataset_name == table_data['dataset_name'],
            AssessmentTable.table_name == table_data['table_name']
        ).first()
        
        if existing:
            # Update existing record
            for key, value in table_data.items():
                setattr(existing, key, value)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new record
            table = AssessmentTable(
                assessment_id=assessment_id,
                **table_data
            )
            self.db.add(table)
            self.db.commit()
            self.db.refresh(table)
            return table
    
    def bulk_create_tables(self, assessment_id: int, tables_data: List[dict]):
        """Bulk create table records with deduplication"""
        # Delete existing tables for this assessment to avoid duplicates
        self.db.query(AssessmentTable).filter(
            AssessmentTable.assessment_id == assessment_id
        ).delete()
        self.db.commit()
        
        # Create new records
        tables = [
            AssessmentTable(assessment_id=assessment_id, **data)
            for data in tables_data
        ]
        self.db.bulk_save_objects(tables)
        self.db.commit()
    
    # Column operations
    def bulk_create_columns(self, assessment_id: int, columns_data: List[dict]):
        """Bulk create column records with deduplication. Batched for large datasets."""
        # Delete existing columns for this assessment to avoid duplicates
        self.db.query(AssessmentColumn).filter(
            AssessmentColumn.assessment_id == assessment_id
        ).delete()
        self.db.commit()
        
        # Insert in batches of 5000
        BATCH_SIZE = 5000
        total = len(columns_data)
        for i in range(0, total, BATCH_SIZE):
            batch = columns_data[i:i + BATCH_SIZE]
            columns = [
                AssessmentColumn(assessment_id=assessment_id, **data)
                for data in batch
            ]
            self.db.bulk_save_objects(columns)
            self.db.commit()
    
    # View operations
    def bulk_create_views(self, assessment_id: int, views_data: List[dict]):
        """Bulk create view records with deduplication"""
        # Delete existing views for this assessment to avoid duplicates
        self.db.query(AssessmentView).filter(
            AssessmentView.assessment_id == assessment_id
        ).delete()
        self.db.commit()
        
        # Create new records
        views = [
            AssessmentView(assessment_id=assessment_id, **data)
            for data in views_data
        ]
        self.db.bulk_save_objects(views)
        self.db.commit()
    
    # Routine operations
    def bulk_create_routines(self, assessment_id: int, routines_data: List[dict], clear_existing: bool = True):
        """Bulk create routine records with optional deduplication"""
        if clear_existing:
            # Delete existing routines for this assessment to avoid duplicates
            self.db.query(AssessmentRoutine).filter(
                AssessmentRoutine.assessment_id == assessment_id
            ).delete()
            self.db.commit()
        
        # Create new records
        routines = [
            AssessmentRoutine(assessment_id=assessment_id, **data)
            for data in routines_data
        ]
        self.db.bulk_save_objects(routines)
        self.db.commit()
    
    # Query stats operations
    def bulk_create_query_stats(self, assessment_id: int, stats_data: List[dict]):
        """Bulk create query stats records with deduplication. Batched for large datasets."""
        # Delete existing query stats for this assessment to avoid duplicates
        self.db.query(AssessmentQueryStat).filter(
            AssessmentQueryStat.assessment_id == assessment_id
        ).delete()
        self.db.commit()
        
        # Insert in batches of 5000 to avoid memory issues with large datasets
        BATCH_SIZE = 5000
        total = len(stats_data)
        for i in range(0, total, BATCH_SIZE):
            batch = stats_data[i:i + BATCH_SIZE]
            stats = [
                AssessmentQueryStat(assessment_id=assessment_id, **data)
                for data in batch
            ]
            self.db.bulk_save_objects(stats)
            self.db.commit()
            if total > BATCH_SIZE:
                print(f"    ... inserted {min(i + BATCH_SIZE, total)}/{total} query stats")
    
    # ML Model operations
    def bulk_create_ml_models(self, assessment_id: int, models_data: List[dict]):
        """Bulk create ML model records with deduplication"""
        # Delete existing ML models for this assessment to avoid duplicates
        self.db.query(AssessmentMLModel).filter(
            AssessmentMLModel.assessment_id == assessment_id
        ).delete()
        self.db.commit()
        
        # Create new records
        models = [
            AssessmentMLModel(assessment_id=assessment_id, **data)
            for data in models_data
        ]
        self.db.bulk_save_objects(models)
        self.db.commit()
    
    # Security operations
    def bulk_create_security_policies(self, assessment_id: int, policies_data: List[dict]):
        """Bulk create security policy records with deduplication"""
        # Delete existing security policies for this assessment to avoid duplicates
        self.db.query(AssessmentSecurity).filter(
            AssessmentSecurity.assessment_id == assessment_id
        ).delete()
        self.db.commit()
        
        # Create new records
        policies = [
            AssessmentSecurity(assessment_id=assessment_id, **data)
            for data in policies_data
        ]
        self.db.bulk_save_objects(policies)
        self.db.commit()

    
    # Sharded table operations
    def bulk_create_sharded_tables(self, assessment_id: int, sharded_data: List[dict]):
        """Bulk create sharded table records with deduplication"""
        from models.assessment import AssessmentShardedTable
        
        # Delete existing sharded tables for this assessment to avoid duplicates
        self.db.query(AssessmentShardedTable).filter(
            AssessmentShardedTable.assessment_id == assessment_id
        ).delete()
        self.db.commit()
        
        # Create new records
        sharded_tables = [
            AssessmentShardedTable(assessment_id=assessment_id, **data)
            for data in sharded_data
        ]
        self.db.bulk_save_objects(sharded_tables)
        self.db.commit()

    def create_log(
        self,
        assessment_id: int,
        log_level: str,
        message: str,
        stage: str = None,
        error_code: str = None,
        stack_trace: str = None,
        log_metadata: dict = None
    ) -> AssessmentLog:
        """Create a log entry for an assessment"""
        log = AssessmentLog(
            assessment_id=assessment_id,
            log_level=log_level,
            message=message,
            stage=stage,
            error_code=error_code,
            stack_trace=stack_trace,
            log_metadata=log_metadata,
            created_at=datetime.utcnow()
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        print(f"[DEBUG] Created log for assessment {assessment_id}: {log_level} - {message}")
        return log
    
    def get_logs(self, assessment_id: int) -> List[AssessmentLog]:
        """Get all logs for an assessment"""
        logs = self.db.query(AssessmentLog).filter(
            AssessmentLog.assessment_id == assessment_id
        ).order_by(AssessmentLog.created_at.asc()).all()
        print(f"[DEBUG] Retrieved {len(logs)} logs for assessment {assessment_id}")
        return logs

    def get_datasets(self, assessment_id: int):
        """Get all datasets for an assessment"""
        from models.assessment import AssessmentDataset
        return self.db.query(AssessmentDataset).filter(
            AssessmentDataset.assessment_id == assessment_id
        ).all()
    
    def get_tables(self, assessment_id: int):
        """Get all tables for an assessment, eagerly loading columns."""
        from models.assessment import AssessmentTable
        from sqlalchemy.orm import joinedload
        return self.db.query(AssessmentTable).options(
            joinedload(AssessmentTable.columns)
        ).filter(
            AssessmentTable.assessment_id == assessment_id
        ).all()
    
    def get_columns(self, assessment_id: int):
        """Get all columns for an assessment"""
        from models.assessment import AssessmentColumn
        return self.db.query(AssessmentColumn).filter(
            AssessmentColumn.assessment_id == assessment_id
        ).all()
    
    def get_views(self, assessment_id: int):
        """Get all views for an assessment"""
        from models.assessment import AssessmentView
        return self.db.query(AssessmentView).filter(
            AssessmentView.assessment_id == assessment_id
        ).all()
    
    def get_routines(self, assessment_id: int):
        """Get all routines for an assessment"""
        from models.assessment import AssessmentRoutine
        return self.db.query(AssessmentRoutine).filter(
            AssessmentRoutine.assessment_id == assessment_id
        ).all()
    
    def get_ml_models(self, assessment_id: int):
        """Get all ML models for an assessment"""
        from models.assessment import AssessmentMLModel
        return self.db.query(AssessmentMLModel).filter(
            AssessmentMLModel.assessment_id == assessment_id
        ).all()
    
    def get_query_stats(self, assessment_id: int):
        """Get query statistics for an assessment"""
        from models.assessment import AssessmentQueryStat
        return self.db.query(AssessmentQueryStat).filter(
            AssessmentQueryStat.assessment_id == assessment_id
        ).order_by(AssessmentQueryStat.execution_time.desc()).all()
    
    def get_security_policies(self, assessment_id: int):
        """Get security policies for an assessment"""
        from models.assessment import AssessmentSecurity
        return self.db.query(AssessmentSecurity).filter(
            AssessmentSecurity.assessment_id == assessment_id
        ).all()
    
    def get_sharded_tables(self, assessment_id: int):
        """Get sharded table groups for an assessment"""
        from models.assessment import AssessmentShardedTable
        return self.db.query(AssessmentShardedTable).filter(
            AssessmentShardedTable.assessment_id == assessment_id
        ).all()

    def get_procedures(self, assessment_id: int):
        """Get stored procedures for an assessment"""
        from models.assessment import AssessmentRoutine
        return self.db.query(AssessmentRoutine).filter(
            AssessmentRoutine.assessment_id == assessment_id,
            AssessmentRoutine.routine_type == 'PROCEDURE'
        ).all()

    def get_functions(self, assessment_id: int):
        """Get functions for an assessment"""
        from models.assessment import AssessmentRoutine
        return self.db.query(AssessmentRoutine).filter(
            AssessmentRoutine.assessment_id == assessment_id,
            AssessmentRoutine.routine_type == 'FUNCTION'
        ).all()

    def get_triggers(self, assessment_id: int):
        """Get triggers for an assessment"""
        from models.assessment import AssessmentRoutine
        return self.db.query(AssessmentRoutine).filter(
            AssessmentRoutine.assessment_id == assessment_id,
            AssessmentRoutine.routine_type == 'TRIGGER'
        ).all()

    def get_indexes(self, assessment_id: int):
        """Get indexes for an assessment"""
        from models.assessment import AssessmentIndex
        return self.db.query(AssessmentIndex).filter(
            AssessmentIndex.assessment_id == assessment_id
        ).all()

    def bulk_create_indexes(self, assessment_id: int, indexes_data: List[dict]):
        """Bulk create index records with deduplication"""
        from models.assessment import AssessmentIndex

        # Delete existing indexes for this assessment to avoid duplicates
        self.db.query(AssessmentIndex).filter(
            AssessmentIndex.assessment_id == assessment_id
        ).delete()

        # Create new index records
        for index_data in indexes_data:
            index_record = AssessmentIndex(
                assessment_id=assessment_id,
                **index_data
            )
            self.db.add(index_record)

        self.db.commit()
