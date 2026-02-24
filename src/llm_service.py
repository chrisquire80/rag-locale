"""
Service per interazione con Google Gemini API (Hybrid RAG)
Gestisce embedding e generazione testo via Cloud.
Con timeout aumentati e retry logic per ReadTimeoutError e ConnectionResetError.
"""

import time
import google.genai as genai
from typing import Any, Optional
from google.genai.types import HarmCategory, HarmBlockThreshold
from requests.exceptions import Timeout, ConnectionError, ReadTimeout

from src.config import config
from src.logging_config import get_logger

logger = get_logger(__name__)

class GeminiService:
    """Gestisce connessione e interazioni con Google Gemini"""

    def __init__(self):
        self.api_key = config.gemini.api_key.get_secret_value()
        self.model_name = config.gemini.model_name
        self.embedding_model = config.gemini.embedding_model

        # Initialize Client for google-genai (new non-deprecated API)
        self.client = genai.Client(api_key=self.api_key)
        self._health_checked = False

    def check_health(self) -> bool:
        """Verifica validità API Key con una chiamata leggera"""
        try:
            # Lista modelli come check rapido
            list(self.client.models.list())
            logger.info("✓ Connessione Gemini API: OK")
            self._health_checked = True
            return True
        except Exception as e:
            logger.error(f"✗ Errore connessione Gemini: {e}")
            return False

    def get_embedding(self, text: str) -> list[float]:
        """
        Ottieni embedding vettoriale per il testo con exponential backoff.
        Modello: models/text-embedding-004

        FIX TIMEOUT HANDLING: Gestisce ReadTimeoutError, ConnectionResetError
        - Max retries aumentati (da 3 a 5)
        - Timeout maggiore per embedding (300 secondi = 5 minuti)
        - Exponential backoff con delay progressivo
        - Gestione specifica di Timeout e ConnectionError
        """
        max_retries = config.gemini.max_retries
        base_delay = config.gemini.retry_base_delay

        for attempt in range(max_retries):
            try:
                # Exponential backoff PRIMA della richiesta
                # Sequenza: 1s, 2s, 4s, 8s, 16s
                delay = base_delay * (2 ** attempt)
                if attempt > 0:
                    logger.warning(f"Embedding retry {attempt}/{max_retries}, waiting {delay}s before retry...")
                    time.sleep(delay)

                # Clean text
                text_clean = text.replace("\n", " ")

                result = self.client.models.embed_content(
                    model=self.embedding_model,
                    contents=text_clean
                )

                # google-genai returns embeddings (plural) as a list of ContentEmbedding objects
                if result and hasattr(result, 'embeddings') and result.embeddings:
                    # Get first embedding's values
                    embedding_obj = result.embeddings[0]
                    if hasattr(embedding_obj, 'values'):
                        logger.debug(f"✓ Embedding successful on attempt {attempt+1}")
                        return list(embedding_obj.values)
                    else:
                        raise ValueError("Embedding values not found in response")
                else:
                    raise ValueError("Embedding result is empty")

            except (Timeout, ReadTimeout, ConnectionError) as e:
                # Timeout or connection errors - ALWAYS retry
                if attempt < max_retries - 1:
                    logger.warning(f"[TIMEOUT/CONNECTION ERROR] Embedding attempt {attempt+1}/{max_retries}: {type(e).__name__}: {str(e)[:80]}. Retrying with increased delay...")
                    continue
                else:
                    logger.error(f"✗ Failed to get embedding after {max_retries} retries (timeout/connection): {e}")
                    raise RuntimeError(f"Embedding generation failed after {max_retries} retries due to timeout/connection issues: {e}")

            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower()

                if is_rate_limit and attempt < max_retries - 1:
                    logger.warning(f"[429 RATE LIMITED] Embedding attempt {attempt+1}/{max_retries} failed. Retrying...")
                    continue
                elif attempt < max_retries - 1:
                    # Other errors - retry after delay
                    logger.warning(f"[Embedding Error] Attempt {attempt+1}/{max_retries}: {str(e)[:80]}... Retrying...")
                    continue
                else:
                    # Max retries exceeded
                    logger.error(f"✗ Failed to get embedding after {max_retries} retries: {e}")
                    raise RuntimeError(f"Embedding generation failed after {max_retries} retries: {e}")

    def get_embeddings_batch(self, texts: list[str], batch_size: int = 50) -> list[list[float]]:
        """
        Ottieni embeddings per lista di testi in batch (OPTIMIZATION 8.5).

        Batching API calls:
        - Process texts in chunks (default 50 per batch)
        - Reduce API call overhead (3-5x efficiency gain)
        - Maintain exponential backoff for rate-limiting
        - Enhanced timeout/connection error handling

        Args:
            texts: List of text strings to embed
            batch_size: Texts per batch (default 50, safe for Gemini API)

        Returns:
            List of embeddings in same order as input texts
        """
        all_embeddings = []
        total_texts = len(texts)

        for batch_start in range(0, total_texts, batch_size):
            batch_end = min(batch_start + batch_size, total_texts)
            batch_texts = texts[batch_start:batch_end]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (total_texts + batch_size - 1) // batch_size

            logger.info(f"Processing embedding batch {batch_num}/{total_batches} ({len(batch_texts)} texts)...")

            max_retries = config.gemini.max_retries
            base_delay = config.gemini.retry_base_delay

            for attempt in range(max_retries):
                try:
                    # Exponential backoff BEFORE request
                    delay = base_delay * (2 ** attempt)
                    if attempt > 0:
                        logger.warning(f"Batch {batch_num} retry {attempt}/{max_retries}, waiting {delay}s...")
                        time.sleep(delay)

                    # Clean texts
                    cleaned_texts = [t.replace("\n", " ") for t in batch_texts]

                    # Batch embedding call
                    result = self.client.models.embed_content(
                        model=self.embedding_model,
                        contents=cleaned_texts  # API accepts list
                    )

                    # Extract embeddings from response
                    if result and hasattr(result, 'embeddings') and result.embeddings:
                        batch_embeddings = []
                        for embedding_obj in result.embeddings:
                            if hasattr(embedding_obj, 'values'):
                                batch_embeddings.append(list(embedding_obj.values))
                            else:
                                raise ValueError("Embedding values not found in response")
                        all_embeddings.extend(batch_embeddings)
                        logger.info(f"✓ Batch {batch_num}/{total_batches} completed ({len(batch_embeddings)} embeddings)")
                        break  # Success, go to next batch
                    else:
                        raise ValueError("Embedding result is empty")

                except (Timeout, ReadTimeout, ConnectionError) as e:
                    # Timeout or connection errors - ALWAYS retry
                    if attempt < max_retries - 1:
                        logger.warning(f"[TIMEOUT/CONNECTION] Batch {batch_num} attempt {attempt+1}/{max_retries}: {type(e).__name__}: {str(e)[:80]}. Retrying...")
                        continue
                    else:
                        logger.error(f"✗ Batch {batch_num} failed after {max_retries} retries (timeout/connection): {e}")
                        raise RuntimeError(f"Batch embedding failed after {max_retries} retries due to timeout/connection issues: {e}")

                except Exception as e:
                    error_str = str(e)
                    is_rate_limit = "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower()

                    if is_rate_limit and attempt < max_retries - 1:
                        logger.warning(f"[429 RATE LIMITED] Batch {batch_num} attempt {attempt+1}/{max_retries}. Retrying...")
                        continue
                    elif attempt < max_retries - 1:
                        logger.warning(f"[Error] Batch {batch_num} attempt {attempt+1}/{max_retries}: {str(e)[:80]}... Retrying...")
                        continue
                    else:
                        logger.error(f"✗ Batch {batch_num} failed after {max_retries} retries: {e}")
                        raise RuntimeError(f"Batch embedding failed after {max_retries} retries: {e}")

        logger.info(f"✓ All {len(all_embeddings)} embeddings completed successfully")
        return all_embeddings

    def completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        enable_search: bool = False
    ) -> str:
        """
        Esegui completion (chat) sul modello Gemini.
        Con retry logic per timeout e connection errors.
        Supporta Grounding with Google Search (enable_search=True).
        """
        if not self._health_checked:
             if not self.check_health():
                raise RuntimeError("Gemini API non disponibile. Controlla API Key.")

        max_retries = config.gemini.max_retries
        base_delay = config.gemini.retry_base_delay

        for attempt in range(max_retries):
            try:
                # Exponential backoff per retry
                if attempt > 0:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Completion retry {attempt}/{max_retries}, waiting {delay}s...")
                    time.sleep(delay)

                # Build full prompt with system instruction if provided
                full_prompt = prompt
                if system_prompt:
                    full_prompt = f"{system_prompt}\n\n{prompt}"

                # Setup safety settings
                safety_settings = [
                    {
                        "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                        "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    },
                    {
                        "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    },
                    {
                        "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    },
                    {
                        "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                    },
                ]

                # Setup config for generation
                config_dict = {
                    "max_output_tokens": max_tokens or 2048,
                    "temperature": temperature if temperature is not None else 0.4,
                    "safety_settings": safety_settings,
                }
                
                # FASE 27: Add Google Search Tool if enabled
                if enable_search:
                    config_dict["tools"] = [{"google_search": {}}]

                # Generate content using google-genai client API
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt,
                    config=config_dict
                )

                logger.debug(f"✓ Completion successful on attempt {attempt+1}")
                
                # Retrieve grounding metadata if available (for future use/logging)
                # if response.candidates[0].grounding_metadata: ...
                
                return response.text

            except (Timeout, ReadTimeout, ConnectionError) as e:
                # Timeout or connection errors - ALWAYS retry
                if attempt < max_retries - 1:
                    logger.warning(f"[TIMEOUT/CONNECTION] Completion attempt {attempt+1}/{max_retries}: {type(e).__name__}: {str(e)[:80]}. Retrying...")
                    continue
                else:
                    logger.error(f"✗ Completion failed after {max_retries} retries (timeout/connection): {e}")
                    raise RuntimeError(f"Completion generation failed after {max_retries} retries due to timeout/connection issues: {e}")

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"[Completion Error] Attempt {attempt+1}/{max_retries}: {str(e)[:80]}... Retrying...")
                    continue
                else:
                    logger.error(f"✗ Errore generazione Gemini dopo {max_retries} tentativi: {e}")
                    raise

    def completion_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        enable_search: bool = False
    ):
        """
        Esegui completion (chat) in streaming sul modello Gemini.
        Yields chunks di testo man mano che vengono generati.
        Supporta Grounding with Google Search.
        """
        if not self._health_checked:
             if not self.check_health():
                raise RuntimeError("Gemini API non disponibile. Controlla API Key.")

        # Build full prompt with system instruction if provided
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Setup safety settings
        safety_settings = [
            {
                "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            },
            {
                "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            },
            {
                "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            },
            {
                "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            },
        ]

        # Setup config for generation
        config_dict = {
            "max_output_tokens": max_tokens or 2048,
            "temperature": temperature if temperature is not None else 0.4,
            "safety_settings": safety_settings,
        }
        
        # FASE 27: Add Google Search Tool if enabled
        if enable_search:
            config_dict["tools"] = [{"google_search": {}}]

        try:
             # Generate content stream using google-genai client API
            response_stream = self.client.models.generate_content_stream(
                model=self.model_name,
                contents=full_prompt,
                config=config_dict
            )

            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
                
                # Note: Grounding metadata usually comes in the final chunk or specific parts of stream.
                # Accessing it might require checking existing chunks for `grounding_metadata`.

        except Exception as e:
            logger.error(f"✗ Errore generazione stream Gemini: {e}")
            raise
# Singleton
_gemini_instance = None

def get_llm_service() -> GeminiService:
    global _gemini_instance
    if _gemini_instance is None:
        _gemini_instance = GeminiService()
    return _gemini_instance
