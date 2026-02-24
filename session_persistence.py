"""
Session Persistence - Salva e recupera lo stato della sessione tra i reload
Persiste: documenti, cartella selezionata, topic, cache, history
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Path per persistenza
PERSISTENCE_DIR = Path("data/session_persistence")
PERSISTENCE_DIR.mkdir(parents=True, exist_ok=True)

SESSION_FILE = PERSISTENCE_DIR / "current_session.json"
DOCS_CACHE_FILE = PERSISTENCE_DIR / "documents_cache.json"
SETTINGS_FILE = PERSISTENCE_DIR / "user_settings.json"


class SessionPersistence:
    """Gestisce la persistenza della sessione tra i reload"""

    @staticmethod
    def save_documents_dir(docs_dir: str) -> None:
        """Salva la cartella documenti selezionata"""
        try:
            settings = SessionPersistence._load_settings()
            settings['last_documents_dir'] = docs_dir
            settings['last_updated'] = datetime.now().isoformat()
            settings['last_updated_timestamp'] = datetime.now().timestamp()

            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)

            logger.info(f"Cartella documenti salvata: {docs_dir}")
        except Exception as e:
            logger.error(f"Errore salvataggio cartella: {e}")

    @staticmethod
    def get_last_documents_dir() -> Optional[str]:
        """Recupera l'ultima cartella documenti selezionata"""
        try:
            settings = SessionPersistence._load_settings()
            docs_dir = settings.get('last_documents_dir')

            if docs_dir:
                # Verifica che il percorso esista, altrimenti ritorna None
                if Path(docs_dir).exists():
                    logger.info(f"Cartella recuperata da cache: {docs_dir}")
                    return docs_dir
                else:
                    logger.warning(f"Cartella in cache non esiste più: {docs_dir}")
        except Exception as e:
            logger.warning(f"Errore recupero cartella: {e}")

        return None

    @staticmethod
    def save_documents(documents: List[Dict], docs_dir: str) -> None:
        """Salva i documenti caricati in cache"""
        try:
            cache_data = {
                'documents': documents,
                'docs_dir': docs_dir,
                'count': len(documents),
                'saved_at': datetime.now().isoformat(),
                'timestamp': datetime.now().timestamp()
            }

            with open(DOCS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"Cache documenti salvato: {len(documents)} documenti da {docs_dir}")
        except Exception as e:
            logger.error(f"Errore salvataggio cache documenti: {e}")

    @staticmethod
    def get_cached_documents() -> Optional[Dict[str, Any]]:
        """Recupera i documenti dalla cache"""
        try:
            if not DOCS_CACHE_FILE.exists():
                return None

            with open(DOCS_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            logger.info(f"Cache documenti recuperato: {cache_data['count']} documenti")
            return cache_data
        except Exception as e:
            logger.warning(f"Errore recupero cache documenti: {e}")
            return None

    @staticmethod
    def save_session_state(session_state: Dict[str, Any]) -> None:
        """Salva lo stato della sessione (conversation, settings, ecc)"""
        try:
            # Seleziona gli elementi importanti da salvare
            state_to_save = {
                'conversation_history': session_state.get('conversation_history', []),
                'quality_scores': session_state.get('quality_scores', []),
                'conversation_id': session_state.get('conversation_id', ''),
                'last_docs_dir': session_state.get('last_docs_dir', 'documents'),
                'custom_docs_path': session_state.get('custom_docs_path', ''),
                'simulation_vars': session_state.get('simulation_vars', {}),
                'saved_at': datetime.now().isoformat(),
            }

            # Salva topic se presente
            if 'topic_grouped' in session_state:
                state_to_save['topic_grouped'] = session_state['topic_grouped']
            if 'topic_stats' in session_state:
                state_to_save['topic_stats'] = session_state['topic_stats']

            with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(state_to_save, f, ensure_ascii=False, indent=2, default=str)

            logger.info("Stato sessione salvato")
        except Exception as e:
            logger.error(f"Errore salvataggio stato sessione: {e}")

    @staticmethod
    def load_session_state() -> Optional[Dict[str, Any]]:
        """Carica lo stato della sessione precedente"""
        try:
            if not SESSION_FILE.exists():
                return None

            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            logger.info("Stato sessione caricato da cache")
            return session_data
        except Exception as e:
            logger.warning(f"Errore caricamento stato sessione: {e}")
            return None

    @staticmethod
    def clear_session_cache() -> None:
        """Pulisce la cache della sessione"""
        try:
            if SESSION_FILE.exists():
                SESSION_FILE.unlink()
            if DOCS_CACHE_FILE.exists():
                DOCS_CACHE_FILE.unlink()

            logger.info("Cache sessione pulita")
        except Exception as e:
            logger.error(f"Errore pulizia cache: {e}")

    @staticmethod
    def get_cache_info() -> Dict[str, Any]:
        """Restituisce informazioni sulla cache"""
        info = {
            'session_cached': SESSION_FILE.exists(),
            'docs_cached': DOCS_CACHE_FILE.exists(),
            'settings_exist': SETTINGS_FILE.exists(),
            'persistence_dir': str(PERSISTENCE_DIR),
        }

        if SESSION_FILE.exists():
            try:
                with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                info['session_saved_at'] = data.get('saved_at', 'unknown')
                info['conversation_turns'] = len(data.get('conversation_history', []))
            except:
                pass

        if DOCS_CACHE_FILE.exists():
            try:
                with open(DOCS_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                info['docs_count'] = data.get('count', 0)
                info['docs_dir'] = data.get('docs_dir', 'unknown')
                info['docs_saved_at'] = data.get('saved_at', 'unknown')
            except:
                pass

        return info

    @staticmethod
    def _load_settings() -> Dict[str, Any]:
        """Carica le impostazioni utente"""
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass

        return {
            'last_documents_dir': None,
            'last_updated': None,
        }


def get_persistence_manager() -> SessionPersistence:
    """Restituisce l'istanza singleton di SessionPersistence"""
    return SessionPersistence()
