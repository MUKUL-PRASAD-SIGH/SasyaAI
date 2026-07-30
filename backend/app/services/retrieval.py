"""Qdrant-backed, filtered retrieval for the production agent workflow."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid4, uuid5

from app.core.config import Settings
from app.models.advisory import KnowledgeHit
from app.services.resilience import CircuitBreaker, ProviderUnavailableError, retry_provider_call


class RetrievalUnavailableError(ProviderUnavailableError):
    """Raised when grounded evidence cannot be retrieved safely."""


class QdrantKnowledgeStore:
    """Owns vector retrieval and ingest; all query filters are server-controlled."""

    collections = ("crop_kb", "pest_kb", "scheme_kb", "farmer_memory")

    def __init__(self, settings: Settings) -> None:
        try:
            from fastembed import TextEmbedding
            from qdrant_client import QdrantClient, models
        except ImportError as error:  # pragma: no cover - only reached in a production install
            raise RetrievalUnavailableError(
                "qdrant-client and FastEmbed are required in production mode."
            ) from error

        self.models = models
        self.settings = settings
        self.client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        self.embedder = TextEmbedding(
            model_name=settings.embedding_model,
            cache_dir=settings.embedding_cache_dir or None,
        )
        self.breaker = CircuitBreaker()
        try:
            dimensions = len(next(iter(self.embedder.embed(["SasyaAI vector dimension"]))))
            existing = {item.name for item in self.client.get_collections().collections}
            for collection in self.collections:
                if collection not in existing:
                    self.client.create_collection(
                        collection_name=collection,
                        vectors_config=models.VectorParams(size=dimensions, distance=models.Distance.COSINE),
                    )
        except Exception as error:
            raise RetrievalUnavailableError("Qdrant collection initialisation failed.") from error

    def _vector(self, text: str) -> list[float]:
        try:
            return next(iter(self.embedder.embed([text]))).tolist()
        except Exception as error:
            raise RetrievalUnavailableError("The retrieval embedding model is unavailable.") from error

    def search(
        self,
        collection: str,
        query: str,
        *,
        filters: dict[str, str | list[str]] | None = None,
        limit: int = 5,
    ) -> list[KnowledgeHit]:
        if collection not in self.collections:
            raise ValueError(f"Unknown Qdrant collection: {collection}")
        vector = self._vector(query)
        conditions = [
            self.models.FieldCondition(
                key=key,
                match=(
                    self.models.MatchAny(any=value)
                    if isinstance(value, list)
                    else self.models.MatchValue(value=value)
                ),
            )
            for key, value in (filters or {}).items()
        ]
        query_filter = self.models.Filter(must=conditions) if conditions else None

        def call():
            # qdrant-client 1.10+ replaced ``search`` with the universal
            # ``query_points`` API. Retain the older call for deployments
            # pinned to this repository's original 1.9 minimum.
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=collection,
                    query=vector,
                    query_filter=query_filter,
                    limit=limit,
                    with_payload=True,
                )
                return response.points
            return self.client.search(
                collection_name=collection,
                query_vector=vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )

        try:
            results = retry_provider_call(
                call,
                breaker=self.breaker,
                retries=self.settings.tool_max_retries,
                retryable=(Exception,),
            )
        except ProviderUnavailableError as error:
            raise RetrievalUnavailableError("Qdrant retrieval is unavailable.") from error

        hits: list[KnowledgeHit] = []
        for point in results:
            payload = dict(point.payload or {})
            identifier = str(payload.pop("document_id", point.id))
            title = str(payload.pop("title", identifier))
            content = payload.pop("content", None)
            if content is not None:
                payload["excerpt"] = str(content)[:800]
            safe_metadata = {
                str(key): value
                for key, value in payload.items()
                if isinstance(value, (str, int, float, bool, list))
            }
            safe_metadata["document_id"] = identifier
            hits.append(
                KnowledgeHit(
                    source=collection,
                    title=title,
                    score=max(0.0, min(1.0, float(point.score))),
                    metadata=safe_metadata,
                )
            )
        return hits

    def upsert_document(
        self,
        collection: str,
        *,
        title: str,
        content: str,
        metadata: dict[str, str | int | float | bool | list[str]],
        document_id: str | None = None,
    ) -> str:
        """Add governed knowledge. Callers must complete source review before ingest."""

        if collection not in self.collections or collection == "farmer_memory":
            raise ValueError("Knowledge can only be ingested into a governed semantic collection.")
        identifier = document_id or str(uuid4())
        point_id = str(uuid5(NAMESPACE_URL, f"{collection}:{identifier}"))
        payload = {"document_id": identifier, "title": title, "content": content, **metadata}

        def call() -> None:
            self.client.upsert(
                collection_name=collection,
                points=[
                    self.models.PointStruct(
                        id=point_id,
                        vector=self._vector(f"{title}\n{content}"),
                        payload=payload,
                    )
                ],
                wait=True,
            )

        try:
            retry_provider_call(
                call,
                breaker=self.breaker,
                retries=self.settings.tool_max_retries,
                retryable=(Exception,),
            )
        except ProviderUnavailableError as error:
            raise RetrievalUnavailableError("Qdrant knowledge ingest failed.") from error
        return identifier

    def append_episode(self, episode: dict[str, object]) -> str:
        """Index a durable advisory episode under a mandatory farmer filter."""

        identifier = str(episode["request_id"])
        content = "\n".join(
            str(episode.get(field, ""))
            for field in ("query", "outcome", "recommendation", "explanation")
        )
        payload = {
            "document_id": identifier,
            "title": f"Advisory episode {identifier}",
            "content": content,
            "farmer_id": str(episode["farmer_id"]),
            "intent": str(episode.get("intent", "")),
            "created_at": str(episode.get("timestamp", "")),
        }

        def call() -> None:
            self.client.upsert(
                collection_name="farmer_memory",
                points=[
                    self.models.PointStruct(
                        id=identifier,
                        vector=self._vector(content),
                        payload=payload,
                    )
                ],
                wait=True,
            )

        try:
            retry_provider_call(
                call,
                breaker=self.breaker,
                retries=self.settings.tool_max_retries,
                retryable=(Exception,),
            )
        except ProviderUnavailableError as error:
            raise RetrievalUnavailableError("Qdrant episode indexing failed.") from error
        return identifier

    def delete_farmer_episodes(self, farmer_id: str) -> None:
        """Remove derived vector memory during an authorised deletion workflow."""

        selector = self.models.FilterSelector(
            filter=self.models.Filter(
                must=[
                    self.models.FieldCondition(
                        key="farmer_id", match=self.models.MatchValue(value=farmer_id)
                    )
                ]
            )
        )

        def call() -> None:
            self.client.delete(collection_name="farmer_memory", points_selector=selector, wait=True)

        try:
            retry_provider_call(
                call,
                breaker=self.breaker,
                retries=self.settings.tool_max_retries,
                retryable=(Exception,),
            )
        except ProviderUnavailableError as error:
            raise RetrievalUnavailableError("Qdrant episode deletion failed.") from error

    def stats(self) -> dict[str, object]:
        """Return bounded collection and coverage metadata for operations UI."""

        def call() -> dict[str, object]:
            counts: dict[str, int] = {}
            regions: set[str] = set()
            crops: set[str] = set()
            for collection in self.collections:
                if collection == "farmer_memory":
                    continue
                counts[collection] = int(
                    self.client.count(collection_name=collection, exact=True).count
                )
                offset = None
                while True:
                    points, offset = self.client.scroll(
                        collection_name=collection,
                        limit=256,
                        offset=offset,
                        with_payload=["state", "region", "crop"],
                        with_vectors=False,
                    )
                    for point in points:
                        payload = point.payload or {}
                        region = payload.get("state", payload.get("region"))
                        crop = payload.get("crop")
                        if region:
                            regions.add(str(region))
                        if crop:
                            crops.add(str(crop))
                    if offset is None:
                        break
            return {
                "collections": counts,
                "total_documents": sum(counts.values()),
                "regions": len(regions),
                "crops": len(crops),
            }

        try:
            return retry_provider_call(
                call,
                breaker=self.breaker,
                retries=self.settings.tool_max_retries,
                retryable=(Exception,),
            )
        except ProviderUnavailableError as error:
            raise RetrievalUnavailableError("Qdrant coverage statistics are unavailable.") from error
