from typing import List, Dict, Optional
from backend.models import Task

# Mock ChromaDB client
class ChromaDBClient:
    def query(
        self,
        collection: str,
        query_embedding: List[float],
        top_k: int = 3,
        threshold: float = 0.92,
    ) -> List[Task]:
        """
        Mock query for similar tasks in ChromaDB.
        In a real implementation, this would query the actual vector database.
        """
        # Mock response: Return similar tasks if the query matches
        mock_tasks = [
            Task(
                task_id="task_123",
                task="Complete pitch deck",
                owner="Rahul",
                deadline="2026-03-26T23:59:00+05:30",
                confidence=0.95,
                source_ref="sample_screenshot.png",
                team_id="team_alpha",
            ),
            Task(
                task_id="task_456",
                task="Review project plan",
                owner="Priya",
                deadline="2026-03-27T18:00:00+05:30",
                confidence=0.90,
                source_ref="sample_chat.txt",
                team_id="team_alpha",
            ),
        ]
        return mock_tasks