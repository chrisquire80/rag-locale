"""
Query Suggestions - FASE 20
Generates follow-up questions and related query suggestions
"""

import re
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from src.logging_config import get_logger

logger = get_logger(__name__)

class QueryIntent(Enum):
    """Types of query intent"""
    SEARCH = "search"           # Find information
    COMPARISON = "comparison"   # Compare items
    ANALYSIS = "analysis"       # Analyze something
    EXPLANATION = "explanation" # Explain something
    RECOMMENDATION = "recommendation"  # Get suggestions
    HOW_TO = "how_to"          # Instructions
    DEFINITION = "definition"   # Define something
    LISTING = "listing"        # List items
    PROBLEM_SOLVING = "problem_solving"  # Solve issue

@dataclass
class QuerySuggestion:
    """Represents a suggested query"""
    text: str
    type: str  # "followup", "related", "refinement"
    relevance_score: float = 0.8
    context: str = ""  # Why this suggestion

class QuerySuggestionEngine:
    """Generates query suggestions and follow-up questions"""

    def __init__(self):
        """Initialize suggestion engine"""
        # Common question patterns
        self.question_patterns = {
            "why": r"\bwhy\b",
            "how": r"\bhow\b",
            "what": r"\bwhat\b",
            "when": r"\bwhen\b",
            "where": r"\bwhere\b",
            "who": r"\bwho\b",
            "example": r"\bexample|instance\b",
        }

        # Common refinement templates
        self.refinement_templates = [
            "What are the specific details about {topic}?",
            "Can you explain {topic} in more depth?",
            "What are the implications of {topic}?",
            "How does {topic} relate to {context}?",
            "What are the pros and cons of {topic}?",
            "What is the current state of {topic}?",
        ]

        # Related topic suggestions
        self.topic_expansions = {
            "machine learning": [
                "neural networks", "deep learning", "supervised learning",
                "unsupervised learning", "reinforcement learning"
            ],
            "python": [
                "Python libraries", "Django", "Flask", "NumPy",
                "Pandas", "Python best practices"
            ],
            "database": [
                "SQL", "NoSQL", "indexing", "query optimization",
                "data modeling", "ACID properties"
            ],
        }

    def generate_followup_questions(
        self,
        query: str,
        answer: str,
        max_suggestions: int = 3
    ) -> list[str]:
        """
        Generate follow-up questions based on query and answer

        Args:
            query: Original query
            answer: Generated answer
            max_suggestions: Maximum suggestions to generate

        Returns:
            List of follow-up question suggestions
        """
        suggestions = []

        # 1. Analyze query intent
        intent = self.analyze_query_intent(query)

        # 2. Generate suggestions based on intent
        if intent == QueryIntent.EXPLANATION:
            suggestions.extend(self._suggest_for_explanation(query, answer))
        elif intent == QueryIntent.COMPARISON:
            suggestions.extend(self._suggest_for_comparison(query, answer))
        elif intent == QueryIntent.HOW_TO:
            suggestions.extend(self._suggest_for_how_to(query, answer))
        elif intent == QueryIntent.DEFINITION:
            suggestions.extend(self._suggest_for_definition(query, answer))
        else:
            suggestions.extend(self._suggest_general(query, answer))

        # 3. Remove duplicates and limit
        suggestions = list(set(suggestions))[:max_suggestions]

        logger.debug(f"Generated {len(suggestions)} follow-up questions")
        return suggestions

    def suggest_related_queries(
        self,
        query: str,
        max_suggestions: int = 5
    ) -> list[str]:
        """
        Suggest related queries on similar topics

        Args:
            query: Original query
            max_suggestions: Maximum suggestions

        Returns:
            List of related query suggestions
        """
        suggestions = []

        # Extract key topics
        topics = self._extract_key_topics(query)

        for topic in topics:
            # Look for expansions
            if topic.lower() in self.topic_expansions:
                expansions = self.topic_expansions[topic.lower()]
                for expansion in expansions[:2]:
                    suggestion = f"Tell me about {expansion}"
                    suggestions.append(suggestion)

            # Generate comparison queries
            suggestions.append(f"Compare {topic} with other similar concepts")

            # Generate deeper exploration
            suggestions.append(f"What are advanced applications of {topic}?")

        # Remove duplicates and limit
        suggestions = list(set(suggestions))[:max_suggestions]

        logger.debug(f"Generated {len(suggestions)} related queries")
        return suggestions

    def analyze_query_intent(self, query: str) -> QueryIntent:
        """
        Analyze the intent behind a query

        Args:
            query: Query string

        Returns:
            QueryIntent enum value
        """
        query_lower = query.lower()

        # Check for specific patterns
        if re.search(r"\bwhy\b", query_lower):
            return QueryIntent.EXPLANATION
        elif re.search(r"\bcompare|difference|vs\b", query_lower):
            return QueryIntent.COMPARISON
        elif re.search(r"\bhow\s+to|steps|procedure\b", query_lower):
            return QueryIntent.HOW_TO
        elif re.search(r"\bdefine|definition|what\s+is\b", query_lower):
            return QueryIntent.DEFINITION
        elif re.search(r"\bexample|instance\b", query_lower):
            return QueryIntent.SEARCH
        elif re.search(r"\brecommend|suggest|best\b", query_lower):
            return QueryIntent.RECOMMENDATION
        elif re.search(r"\blist|types|kinds\b", query_lower):
            return QueryIntent.LISTING
        elif re.search(r"\bproblem|issue|error\b", query_lower):
            return QueryIntent.PROBLEM_SOLVING
        else:
            return QueryIntent.ANALYSIS

    def _suggest_for_explanation(
        self,
        query: str,
        answer: str
    ) -> list[str]:
        """Generate follow-ups for explanation queries"""
        suggestions = []

        # Extract main topic
        topic = self._extract_main_topic(query)

        # Ask for examples
        suggestions.append(f"Can you provide examples of {topic}?")

        # Ask for implications
        suggestions.append(f"What are the implications of {topic}?")

        # Ask for counter-evidence
        suggestions.append(f"Are there any counterarguments to this explanation?")

        # Ask for related concepts
        suggestions.append(f"How does this relate to other similar concepts?")

        return suggestions

    def _suggest_for_comparison(
        self,
        query: str,
        answer: str
    ) -> list[str]:
        """Generate follow-ups for comparison queries"""
        suggestions = []

        # Extract compared items
        items = re.findall(r'\b\w+\b', query)
        if len(items) >= 2:
            item1, item2 = items[0], items[1]

            # Ask for advantages/disadvantages
            suggestions.append(f"What are the advantages of {item1} over {item2}?")

            # Ask for use cases
            suggestions.append(f"When should I use {item1} instead of {item2}?")

            # Ask for hybrid approach
            suggestions.append(f"Can {item1} and {item2} be used together?")

        return suggestions

    def _suggest_for_how_to(
        self,
        query: str,
        answer: str
    ) -> list[str]:
        """Generate follow-ups for how-to queries"""
        suggestions = []

        topic = self._extract_main_topic(query)

        # Ask for common mistakes
        suggestions.append(f"What are common mistakes when {topic}?")

        # Ask for best practices
        suggestions.append(f"What are best practices for {topic}?")

        # Ask for tools/resources
        suggestions.append(f"What tools can help with {topic}?")

        # Ask for advanced techniques
        suggestions.append(f"What are advanced techniques for {topic}?")

        return suggestions

    def _suggest_for_definition(
        self,
        query: str,
        answer: str
    ) -> list[str]:
        """Generate follow-ups for definition queries"""
        suggestions = []

        topic = self._extract_main_topic(query)

        # Ask for applications
        suggestions.append(f"How is {topic} applied in practice?")

        # Ask for history
        suggestions.append(f"What is the history and evolution of {topic}?")

        # Ask for related concepts
        suggestions.append(f"What concepts are related to {topic}?")

        # Ask for examples
        suggestions.append(f"Can you provide real-world examples of {topic}?")

        return suggestions

    def _suggest_general(
        self,
        query: str,
        answer: str
    ) -> list[str]:
        """Generate general follow-up suggestions"""
        suggestions = []

        topic = self._extract_main_topic(query)

        # Ask for more detail
        suggestions.append(f"Can you provide more details about {topic}?")

        # Ask for recent developments
        suggestions.append(f"What are recent developments in {topic}?")

        # Ask for expert opinion
        suggestions.append(f"What do experts say about {topic}?")

        return suggestions

    def _extract_key_topics(self, query: str) -> list[str]:
        """Extract key topics from query"""
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'is', 'are', 'was', 'were', 'what', 'how', 'why', 'when', 'where'
        }

        # Split into words
        words = re.findall(r'\b\w+\b', query.lower())

        # Filter stop words and short words
        topics = [
            w for w in words
            if w not in stop_words and len(w) > 3
        ]

        return topics[:3]  # Return top 3

    def _extract_main_topic(self, query: str) -> str:
        """Extract main topic from query"""
        topics = self._extract_key_topics(query)
        return topics[0] if topics else "this topic"

    def rank_suggestions(
        self,
        suggestions: list[str],
        query: str
    ) -> list[tuple[str, float]]:
        """
        Rank suggestions by relevance to original query

        Args:
            suggestions: List of suggestion strings
            query: Original query

        Returns:
            List of (suggestion, score) tuples sorted by relevance
        """
        query_terms = set(word.lower() for word in query.split())
        ranked = []

        for suggestion in suggestions:
            # Calculate relevance score
            suggestion_terms = set(word.lower() for word in suggestion.split())

            # Term overlap
            overlap = len(query_terms & suggestion_terms)
            score = overlap / max(len(query_terms), 1)

            # Boost for length (longer suggestions are often better)
            if len(suggestion) > 50:
                score *= 1.1

            ranked.append((suggestion, score))

        # Sort by score descending
        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked

    def get_suggestion_objects(
        self,
        query: str,
        answer: str,
        max_suggestions: int = 5
    ) -> list[QuerySuggestion]:
        """
        Get structured suggestion objects with metadata

        Args:
            query: Original query
            answer: Answer
            max_suggestions: Maximum suggestions

        Returns:
            List of QuerySuggestion objects
        """
        followups = self.generate_followup_questions(query, answer, max_suggestions // 2)
        related = self.suggest_related_queries(query, max_suggestions // 2)

        suggestions = []

        for idx, followup in enumerate(followups):
            suggestions.append(QuerySuggestion(
                text=followup,
                type="followup",
                relevance_score=0.9 - (idx * 0.1),
                context="Direct follow-up to explore further"
            ))

        for idx, related_q in enumerate(related):
            suggestions.append(QuerySuggestion(
                text=related_q,
                type="related",
                relevance_score=0.7 - (idx * 0.1),
                context="Related topic you might be interested in"
            ))

        return suggestions[:max_suggestions]
