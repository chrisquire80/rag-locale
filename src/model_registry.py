"""
Phase 12.3: Model Registry & Version Management

Tracks fine-tuned model versions, performance metrics, and deployments.
Supports model rollback and A/B testing between versions.
"""

import logging
import json
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class ModelVersion:
    """A registered model version"""
    model_id: str
    version: str
    model_type: str  # "embeddings", "reranker", "prompt"
    created_at: str
    created_by: str
    description: str

    # Performance metrics
    quality_score: float  # 0-1
    latency_ms: float
    inference_cost_usd: float

    # Status
    is_production: bool = False
    is_stable: bool = False
    download_url: Optional[str] = None

    # Metadata
    training_samples: int = 0
    validation_accuracy: float = 0.0
    test_accuracy: float = 0.0
    improvement_percent: float = 0.0

@dataclass
class DeploymentRecord:
    """Record of a model deployment"""
    model_id: str
    version: str
    deployed_at: str
    deployed_by: str
    environment: str  # "staging", "production"
    traffic_percent: float  # 0-100 for canary deployments
    metrics_snapshot: Dict

class ModelRegistry:
    """
    Central registry for managing fine-tuned model versions.

    Responsibilities:
    1. Register new model versions with metadata
    2. Track performance metrics and improvements
    3. Manage production/staging deployments
    4. Support rollback to previous versions
    5. Enable A/B testing between versions
    """

    def __init__(self, registry_path: str = "models/registry.json"):
        """
        Initialize model registry.

        Args:
            registry_path: Path to store registry JSON file
        """
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        self.versions: list[ModelVersion] = []
        self.deployments: list[DeploymentRecord] = []

        # Load existing registry
        self._load_registry()

    def register_model(
        self,
        model_id: str,
        version: str,
        model_type: str,
        created_by: str,
        description: str,
        quality_score: float,
        latency_ms: float,
        inference_cost_usd: float,
        training_samples: int = 0,
        validation_accuracy: float = 0.0,
        improvement_percent: float = 0.0
    ) -> ModelVersion:
        """
        Register a new model version.

        Args:
            model_id: Model identifier (e.g., "embedding-v1", "reranker-v2")
            version: Version string (e.g., "1.0.0")
            model_type: Type of model ("embeddings", "reranker", "prompt")
            created_by: Name/ID of creator
            description: Human-readable description
            quality_score: Quality metric (0-1)
            latency_ms: Inference latency in milliseconds
            inference_cost_usd: Cost per inference in USD
            training_samples: Number of training samples used
            validation_accuracy: Validation accuracy (0-1)
            improvement_percent: Improvement over baseline

        Returns:
            Registered ModelVersion
        """
        model_version = ModelVersion(
            model_id=model_id,
            version=version,
            model_type=model_type,
            created_at=datetime.now().isoformat(),
            created_by=created_by,
            description=description,
            quality_score=quality_score,
            latency_ms=latency_ms,
            inference_cost_usd=inference_cost_usd,
            training_samples=training_samples,
            validation_accuracy=validation_accuracy,
            improvement_percent=improvement_percent,
        )

        self.versions.append(model_version)
        self._save_registry()

        logger.info(
            f"Registered {model_type} model {model_id}:{version} - "
            f"Quality: {quality_score:.2f}, Latency: {latency_ms:.0f}ms, "
            f"Improvement: {improvement_percent:.0f}%"
        )

        return model_version

    def get_model(self, model_id: str, version: Optional[str] = None) -> Optional[ModelVersion]:
        """
        Get a specific model version.

        Args:
            model_id: Model identifier
            version: Version string (if None, returns latest)

        Returns:
            ModelVersion or None if not found
        """
        matching = [v for v in self.versions if v.model_id == model_id]

        if not matching:
            return None

        if version is None:
            # Return latest version
            return max(matching, key=lambda m: m.created_at)

        # Return specific version
        for model in matching:
            if model.version == version:
                return model

        return None

    def get_production_model(self, model_id: str) -> Optional[ModelVersion]:
        """Get current production version of a model"""
        matching = [
            v for v in self.versions
            if v.model_id == model_id and v.is_production
        ]
        return matching[0] if matching else None

    def promote_to_production(
        self,
        model_id: str,
        version: str,
        canary_traffic_percent: float = 10.0
    ) -> bool:
        """
        Promote a model version to production.

        Args:
            model_id: Model identifier
            version: Version to promote
            canary_traffic_percent: Initial traffic percentage for canary deployment

        Returns:
            True if successful
        """
        model = self.get_model(model_id, version)

        if not model:
            logger.error(f"Model {model_id}:{version} not found")
            return False

        # Demote current production version
        current_prod = self.get_production_model(model_id)
        if current_prod:
            current_prod.is_production = False

        # Promote new version
        model.is_production = True

        # Record deployment
        deployment = DeploymentRecord(
            model_id=model_id,
            version=version,
            deployed_at=datetime.now().isoformat(),
            deployed_by="system",
            environment="production",
            traffic_percent=canary_traffic_percent,
            metrics_snapshot={
                "quality": model.quality_score,
                "latency": model.latency_ms,
                "cost": model.inference_cost_usd,
            }
        )
        self.deployments.append(deployment)

        self._save_registry()

        logger.info(
            f"Promoted {model_id}:{version} to production "
            f"({canary_traffic_percent:.0f}% traffic)"
        )

        return True

    def rollback(self, model_id: str) -> bool:
        """
        Rollback to previous production version.

        Args:
            model_id: Model to rollback

        Returns:
            True if successful
        """
        # Find all versions, sorted by creation time
        matching = sorted(
            [v for v in self.versions if v.model_id == model_id],
            key=lambda m: m.created_at,
            reverse=True
        )

        if len(matching) < 2:
            logger.warning(f"Not enough versions to rollback {model_id}")
            return False

        # Current production
        current = matching[0]
        current.is_production = False

        # Previous version
        previous = matching[1]
        previous.is_production = True

        self._save_registry()

        logger.info(
            f"Rolled back {model_id} from {current.version} to {previous.version}"
        )

        return True

    def get_model_stats(self, model_id: str) -> Dict:
        """Get statistics for a model across all versions"""
        versions = [v for v in self.versions if v.model_id == model_id]

        if not versions:
            return {}

        quality_scores = [v.quality_score for v in versions]
        latencies = [v.latency_ms for v in versions]

        return {
            "model_id": model_id,
            "total_versions": len(versions),
            "production_version": next(
                (v.version for v in versions if v.is_production),
                None
            ),
            "best_quality_score": max(quality_scores),
            "best_latency_ms": min(latencies),
            "avg_quality_score": sum(quality_scores) / len(quality_scores),
            "avg_latency_ms": sum(latencies) / len(latencies),
            "versions": [
                {
                    "version": v.version,
                    "quality": v.quality_score,
                    "latency": v.latency_ms,
                    "improvement": v.improvement_percent,
                    "is_production": v.is_production,
                }
                for v in sorted(versions, key=lambda v: v.created_at, reverse=True)
            ]
        }

    def _load_registry(self):
        """Load registry from file"""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r') as f:
                    data = json.load(f)

                # Load model versions
                for model_data in data.get('versions', []):
                    self.versions.append(ModelVersion(**model_data))

                # Load deployment records
                for deploy_data in data.get('deployments', []):
                    self.deployments.append(DeploymentRecord(**deploy_data))

                logger.info(
                    f"Loaded registry with {len(self.versions)} models, "
                    f"{len(self.deployments)} deployments"
                )
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")

    def _save_registry(self):
        """Save registry to file"""
        try:
            data = {
                'versions': [asdict(v) for v in self.versions],
                'deployments': [asdict(d) for d in self.deployments],
                'last_updated': datetime.now().isoformat(),
            }

            with open(self.registry_path, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

# Global instance
_registry = None

def get_model_registry() -> ModelRegistry:
    """Get or create global model registry"""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
