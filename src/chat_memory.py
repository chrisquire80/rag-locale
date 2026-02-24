"""
Conversation Memory - FASE 20
Manages conversation context and history
"""

import json
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import deque

from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class ConversationTurn:
    """Single turn in conversation"""
    turn_id: int
    query: str
    response: str
    timestamp: str
    quality_score: Optional[float] = None
    sources: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)

class ConversationMemory:
    """Manages conversation history and context"""

    def __init__(self, max_turns: int = 50, max_age_minutes: int = 60):
        """
        Initialize conversation memory

        Args:
            max_turns: Maximum turns to keep in memory
            max_age_minutes: Maximum age of turns in minutes
        """
        self.turns: deque = deque(maxlen=max_turns)
        self.max_turns = max_turns
        self.max_age_minutes = max_age_minutes
        self.turn_counter = 0
        self.conversation_id = self._generate_conversation_id()

    def add_turn(
        self,
        query: str,
        response: str,
        quality_score: Optional[float] = None,
        sources: Optional[list[str]] = None,
        metadata: Optional[Dict] = None
    ) -> ConversationTurn:
        """
        Add a conversation turn

        Args:
            query: User query
            response: System response
            quality_score: Quality metric score
            sources: Source documents
            metadata: Additional metadata

        Returns:
            ConversationTurn object
        """
        self.turn_counter += 1

        turn = ConversationTurn(
            turn_id=self.turn_counter,
            query=query,
            response=response,
            timestamp=datetime.now().isoformat(),
            quality_score=quality_score,
            sources=sources or [],
            metadata=metadata or {}
        )

        self.turns.append(turn)

        logger.debug(f"Added turn {self.turn_counter}: {query[:50]}...")

        return turn

    def get_conversation_context(
        self,
        include_responses: bool = True,
        include_sources: bool = False,
        max_turns: Optional[int] = None
    ) -> str:
        """
        Get formatted conversation context

        Useful for passing conversation history to LLM

        Args:
            include_responses: Include assistant responses
            include_sources: Include source information
            max_turns: Limit number of recent turns

        Returns:
            Formatted conversation string
        """
        # Get turns to include
        turns_list = list(self.turns)
        if max_turns:
            turns_list = turns_list[-max_turns:]

        context_lines = []

        for turn in turns_list:
            # Add query
            context_lines.append(f"User: {turn.query}")

            # Add response if requested
            if include_responses:
                context_lines.append(f"Assistant: {turn.response[:200]}...")  # Truncate long responses

            # Add sources if requested
            if include_sources and turn.sources:
                context_lines.append(f"Sources: {', '.join(turn.sources[:3])}")

            context_lines.append("")

        context = "\n".join(context_lines)
        logger.debug(f"Generated context from {len(turns_list)} turns")

        return context

    def get_recent_turns(self, num_turns: int = 5) -> list[ConversationTurn]:
        """
        Get most recent conversation turns

        Args:
            num_turns: Number of recent turns to return

        Returns:
            List of recent ConversationTurn objects
        """
        return list(self.turns)[-num_turns:]

    def get_turn(self, turn_id: int) -> Optional[ConversationTurn]:
        """
        Get specific turn by ID

        Args:
            turn_id: Turn ID

        Returns:
            ConversationTurn or None if not found
        """
        for turn in self.turns:
            if turn.turn_id == turn_id:
                return turn
        return None

    def clear_old_turns(self, max_age_minutes: Optional[int] = None) -> int:
        """
        Remove turns older than specified time

        Args:
            max_age_minutes: Max age in minutes (uses default if None)

        Returns:
            Number of turns removed
        """
        max_age = max_age_minutes or self.max_age_minutes

        if max_age <= 0:
            return 0

        cutoff_time = datetime.now() - timedelta(minutes=max_age)
        initial_count = len(self.turns)

        # Filter out old turns
        new_turns = deque(
            (t for t in self.turns if datetime.fromisoformat(t.timestamp) > cutoff_time),
            maxlen=self.max_turns
        )

        self.turns = new_turns

        removed_count = initial_count - len(self.turns)
        logger.info(f"Cleared {removed_count} turns older than {max_age} minutes")

        return removed_count

    def export_conversation(
        self,
        include_all: bool = True
    ) -> dict[str, Any]:
        """
        Export full conversation

        Args:
            include_all: Include all metadata

        Returns:
            Dictionary with conversation data
        """
        turns_data = [turn.to_dict() for turn in self.turns]

        export = {
            "conversation_id": self.conversation_id,
            "created": datetime.now().isoformat(),
            "total_turns": len(self.turns),
            "turns": turns_data
        }

        if include_all:
            export["statistics"] = self.get_conversation_statistics()

        return export

    def import_conversation(self, data: dict[str, Any]) -> None:
        """
        Import conversation from exported data

        Args:
            data: Conversation data dictionary
        """
        self.conversation_id = data.get("conversation_id", self.conversation_id)

        turns_data = data.get("turns", [])
        self.turns.clear()
        self.turn_counter = 0

        for turn_data in turns_data:
            turn = ConversationTurn(
                turn_id=turn_data["turn_id"],
                query=turn_data["query"],
                response=turn_data["response"],
                timestamp=turn_data["timestamp"],
                quality_score=turn_data.get("quality_score"),
                sources=turn_data.get("sources", []),
                metadata=turn_data.get("metadata", {})
            )
            self.turns.append(turn)
            self.turn_counter = max(self.turn_counter, turn.turn_id)

        logger.info(f"Imported {len(self.turns)} turns")

    def get_conversation_statistics(self) -> dict[str, Any]:
        """
        Get conversation statistics

        Returns:
            Dictionary with statistics
        """
        if not self.turns:
            return {
                "total_turns": 0,
                "avg_query_length": 0,
                "avg_response_length": 0,
                "avg_quality_score": None
            }

        query_lengths = [len(t.query) for t in self.turns]
        response_lengths = [len(t.response) for t in self.turns]
        quality_scores = [t.quality_score for t in self.turns if t.quality_score]

        return {
            "total_turns": len(self.turns),
            "avg_query_length": sum(query_lengths) / len(query_lengths),
            "avg_response_length": sum(response_lengths) / len(response_lengths),
            "avg_quality_score": sum(quality_scores) / len(quality_scores) if quality_scores else None,
            "total_duration_minutes": self._calculate_duration(),
            "unique_sources": len(set(
                source for turn in self.turns for source in turn.sources
            ))
        }

    def search_conversation(
        self,
        query_text: str,
        search_in_responses: bool = True
    ) -> list[ConversationTurn]:
        """
        Search conversation history

        Args:
            query_text: Text to search for
            search_in_responses: Also search responses

        Returns:
            Matching turns
        """
        query_lower = query_text.lower()
        matches = []

        for turn in self.turns:
            if query_lower in turn.query.lower():
                matches.append(turn)
            elif search_in_responses and query_lower in turn.response.lower():
                matches.append(turn)

        logger.debug(f"Found {len(matches)} matching turns")
        return matches

    def get_topics_discussed(self) -> dict[str, int]:
        """
        Extract topics discussed in conversation

        Returns:
            Dictionary of topic -> frequency
        """
        topics = {}

        for turn in self.turns:
            # Extract key terms from query
            words = turn.query.lower().split()

            for word in words:
                if len(word) > 5:  # Only significant words
                    topics[word] = topics.get(word, 0) + 1

        # Sort by frequency
        return dict(sorted(topics.items(), key=lambda x: x[1], reverse=True))

    def clear_conversation(self) -> None:
        """Clear entire conversation history"""
        initial_count = len(self.turns)
        self.turns.clear()
        self.conversation_id = self._generate_conversation_id()
        logger.info(f"Cleared {initial_count} turns")

    def _generate_conversation_id(self) -> str:
        """Generate unique conversation ID"""
        from datetime import datetime
        return f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _calculate_duration(self) -> float:
        """Calculate conversation duration in minutes"""
        if not self.turns:
            return 0.0

        first_time = datetime.fromisoformat(list(self.turns)[0].timestamp)
        last_time = datetime.fromisoformat(list(self.turns)[-1].timestamp)

        duration = (last_time - first_time).total_seconds() / 60
        return duration

    def export_to_json(self, filepath: str) -> None:
        """
        Export conversation to JSON file

        Args:
            filepath: Path to save JSON
        """
        export_data = self.export_conversation()

        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported conversation to {filepath}")

    def import_from_json(self, filepath: str) -> None:
        """
        Import conversation from JSON file

        Args:
            filepath: Path to JSON file
        """
        with open(filepath, 'r') as f:
            data = json.load(f)

        self.import_conversation(data)
        logger.info(f"Imported conversation from {filepath}")

    def to_markdown(self) -> str:
        """
        Export conversation as Markdown

        Returns:
            Markdown formatted conversation
        """
        lines = [
            f"# Conversation {self.conversation_id}",
            f"*Created: {datetime.now().isoformat()}*",
            "",
        ]

        for turn in self.turns:
            lines.append(f"## Turn {turn.turn_id}")
            lines.append(f"**User:** {turn.query}")
            lines.append(f"**Assistant:** {turn.response}")
            if turn.quality_score:
                lines.append(f"*Quality: {turn.quality_score:.2f}*")
            if turn.sources:
                lines.append(f"**Sources:** {', '.join(turn.sources)}")
            lines.append("")

        return "\n".join(lines)
