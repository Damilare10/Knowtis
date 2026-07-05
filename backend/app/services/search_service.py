"""
Semantic Search Service
Handles vector embedding queries for academic event retrieval,
supporting PostgreSQL pgvector in production and SQLite in-memory numpy fallback in development.
"""
import logging
import json
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models import AcademicEvent
from app.utils import generate_embedding, calculate_similarity
from app.config import settings

logger = logging.getLogger(__name__)

class SearchService:
    """Service to execute semantic vector similarity search queries on AcademicEvents"""

    @staticmethod
    def search_events(
        user_id,
        query_text: str,
        db: Session,
        limit: int = 10,
        threshold: Optional[float] = None
    ) -> List[Tuple[AcademicEvent, float]]:
        """
        Execute semantic search on academic events for a specific user.
        Returns a list of tuples containing (AcademicEvent, similarity_score).
        """
        if threshold is None:
            threshold = settings.similarity_threshold

        query_embedding = generate_embedding(query_text)
        if not query_embedding:
            logger.warning("Failed to generate embedding for query text.")
            return []

        # Detect database dialect
        is_postgres = "postgresql" in str(db.bind.url)

        if is_postgres:
            logger.info("Executing pgvector semantic search on PostgreSQL.")
            try:
                # Format vector list to string representation [val1, val2, ...]
                vector_str = f"[{','.join(map(str, query_embedding))}]"

                # Compute similarity once in a subquery; the WHERE clause
                # references the computed alias so PostgreSQL evaluates the
                # cosine distance a single time per row instead of twice.
                sql = text("""
                    SELECT id, user_id, group_id, event_type, course_code, title, description, venue,
                           date_time, urgency_score, confidence_score, relevance_score, actionability_score,
                           is_duplicate, canonical_event_id, source_message_id, source_group_jid,
                           is_archived, created_at, updated_at, similarity
                    FROM (
                        SELECT *,
                               (1.0 - (CAST(embedding AS vector) <=> CAST(:query_vector AS vector))) AS similarity
                        FROM academic_events
                        WHERE user_id = :user_id
                          AND is_duplicate = False
                          AND is_archived = False
                    ) AS scored
                    WHERE similarity >= :threshold
                    ORDER BY similarity DESC
                    LIMIT :limit
                """)

                result_set = db.execute(sql, {
                    "user_id": user_id,
                    "query_vector": vector_str,
                    "threshold": threshold,
                    "limit": limit
                }).all()

                results = []
                for row in result_set:
                    event = AcademicEvent(
                        id=row.id,
                        user_id=row.user_id,
                        group_id=row.group_id,
                        event_type=row.event_type,
                        course_code=row.course_code,
                        title=row.title,
                        description=row.description,
                        venue=row.venue,
                        date_time=row.date_time,
                        urgency_score=row.urgency_score,
                        confidence_score=row.confidence_score,
                        relevance_score=row.relevance_score,
                        actionability_score=row.actionability_score,
                        is_duplicate=row.is_duplicate,
                        canonical_event_id=row.canonical_event_id,
                        source_message_id=row.source_message_id,
                        source_group_jid=row.source_group_jid,
                        is_archived=row.is_archived,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                    results.append((event, float(row.similarity)))
                return results

            except Exception as e:
                logger.error(f"PostgreSQL pgvector search failed: {e}. Falling back to SQLite/Python path.")
                # Fall through to SQLite/Python fallback

        # Local SQLite / Python fallback
        logger.info("Executing SQLite/Python fallback semantic search.")
        events = db.query(AcademicEvent).filter(
            AcademicEvent.user_id == user_id,
            AcademicEvent.is_duplicate == False,
            AcademicEvent.is_archived == False
        ).all()

        matches = []
        for event in events:
            if not event.embedding:
                continue
            try:
                # Load embedding from DB string
                event_embedding = event.embedding
                if isinstance(event_embedding, str):
                    event_embedding = json.loads(event_embedding)
                
                similarity = calculate_similarity(query_embedding, event_embedding)
                if similarity >= threshold:
                    matches.append((event, similarity))
            except Exception as e:
                logger.error(f"Error comparing embedding for event {event.id}: {e}")
                continue

        # Sort matches by similarity score descending and slice
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:limit]
