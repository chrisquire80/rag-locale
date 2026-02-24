"""
Entry point principale RAG Locale
Orchestration: setup → ingestion → interactive session

Uses centralized structured JSON logging (src/logging_config).
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config, print_config, DOCUMENTS_DIR, LOGS_DIR
from src.llm_service import get_llm_service
from src.document_ingestion import DocumentIngestionPipeline
from src.rag_engine import interactive_rag_session

# FASE 1-7: Performance Optimization Imports
from src.hardware_optimization import get_hardware_optimizer
from src.performance_profiler import get_profiler, profile_operation
from src.async_rag_engine import get_async_rag_engine

# Initialize structured logging (replaces basicConfig)
from src.logging_config import get_logger as _get_logger, configure_logging as _configure_logging

_log_level = os.getenv('LOG_LEVEL', config.log_level if hasattr(config, 'log_level') else 'INFO')
_log_file = str(LOGS_DIR / "rag_main.jsonl")
_configure_logging(level=_log_level, log_file=_log_file, console=True)

logger = _get_logger(__name__)


def print_banner():
    """Stampa banner di avvio"""
    banner = """
    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║           🚀 RAG LOCALE - Sistema Aziendale              ║
    ║                                                            ║
    ║    Zero-Cloud • Sovranità Dato • GDPR Compliant          ║
    ║                                                            ║
    ║    Hardware: HP ProBook 440 G11 (16GB RAM, CPU-only)    ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝
    """
    logger.info(banner)


@profile_operation("main_initialization")
def main():
    """Main entry point"""
    print_banner()
    print_config()

    logger.info("🔧 Inizializzazione sistema RAG...")

    # FASE 3: Hardware Optimization - Initialize optimizer
    logger.info("\n[OPTIMIZATION] Detecting hardware configuration...")
    optimizer = get_hardware_optimizer()
    logger.info(optimizer.print_optimization_report())

    # Step 1: Verifica Gemini API
    logger.info("\n[1/3] Verifica Gemini API (Hybrid RAG)...")
    llm = get_llm_service()

    if not llm.check_health():
        logger.error(
            "❌ Gemini API non disponibile!\n"
            "   Assicurati che:\n"
            "   1. La variabile GEMINI_API_KEY sia impostata (nel file .env o nel sistema)\n"
            "   2. La chiave sia valida\n"
            "   3. Ci sia connessione internet active"
        )
        return False

    # Step 2: Ingestion documenti
    logger.info("\n[2/3] Ingestione documenti...")
    
    pipeline = DocumentIngestionPipeline()

    # Verifica se documents_dir contiene file
    doc_files = list(DOCUMENTS_DIR.glob("*.*"))
    if not doc_files:
        logger.warning(
            f"⚠️  Nessun documento trovato in {DOCUMENTS_DIR}\n"
            "   Aggiungi file (.pdf, .txt, .md, .docx) nella cartella 'data/documents'"
        )

        # Crea documento di test per demo
        logger.info("Creazione documento di test...")
        create_sample_documents()

    # Ingestisci
    total_chunks = pipeline.ingest_from_directory()
    logger.info(f"Ingestione completata: {total_chunks} chunks")

    # Step 3: Sessione interattiva
    logger.info("\n[3/3] Avvio sessione interattiva...")
    logger.info("Sistema pronto!\n")

    try:
        interactive_rag_session()
    except KeyboardInterrupt:
        logger.info("\n👋 Interruzione utente")
    except Exception as e:
        logger.error(f"❌ Errore durante sessione: {e}", exc_info=True)
        return False
    finally:
        # FASE 2: Print profiling report on exit
        profiler = get_profiler()
        logger.info("\n" + profiler.print_report())

    return True


def create_sample_documents():
    """Crea documenti di test per demo"""
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

    # Policy Smart Working
    with open(DOCUMENTS_DIR / "policy_smartworking.txt", "w", encoding="utf-8") as f:
        f.write("""
POLICY SMART WORKING - VERSIONE 2024

1. PRINCIPI GENERALI
Lo smart working è una modalità di lavoro flessibile che consente ai dipendenti di svolgere le proprie attività lavorative in modalità remota, con accordo aziendale e nel rispetto dei vincoli normativi stabiliti dal CCNL e dalle direttive aziendali.

2. REQUISITI TECNICI
I dipendenti devono disporre di una connessione internet stabile e di un ambiente di lavoro adatto allo svolgimento delle proprie funzioni. La sicurezza informatica è prioritaria e deve essere garantita attraverso l'utilizzo di VPN aziendale e di dispositivi autorizzati.

3. FREQUENZA
La frequenza massima di smart working è stabilita in 3 giorni a settimana, salvo diverse disposizioni del management e del responsabile diretto del dipendente. Gli accordi individuali devono essere documentati per legge.

4. ORARI E DISPONIBILITÀ
Durante i giorni di smart working, i dipendenti devono garantire la piena disponibilità durante l'orario lavorativo standard (9:00-17:30). Le riunioni devono essere pianificate negli orari concordati.

5. EQUIPAGGIAMENTO
L'azienda fornisce equipaggiamento standard: notebook, mouse, webcam. I dipendenti sono responsabili della corretta manutenzione e della custodia dei dispositivi aziendali.
""")

    # Procedure Sicurezza IT
    with open(DOCUMENTS_DIR / "security_procedures.txt", "w", encoding="utf-8") as f:
        f.write("""
PROCEDURE SICUREZZA INFORMATICA

1. BACKUP GIORNALIERI
Il backup dei dati deve essere eseguito giornalmente secondo il piano di disaster recovery (DRP). I backup devono essere archiviati in locazioni geograficamente separate dai sistemi primari, in conformità a GDPR e ISO 27001.

2. PATCH MANAGEMENT
Tutti i sistemi IT devono essere aggiornati almeno mensilmente con le patch di sicurezza rilasciate dai vendor. Gli aggiornamenti di sicurezza critici devono essere applicati entro 48 ore da disponibilità.

3. PASSWORD POLICY
Le password devono contenere almeno 12 caratteri, includere maiuscole, minuscole, numeri e caratteri speciali. La modifica password è obbligatoria ogni 90 giorni. Non sono consentite password precedentemente utilizzate negli ultimi 12 mesi.

4. MULTI-FACTOR AUTHENTICATION (MFA)
L'MFA è obbligatoria per l'accesso a sistemi critici (AD, email, VPN). Sono supportati: TOTP, hardware token, e email verification. Le app di autenticazione non devono essere disabilitate.

5. INCIDENT RESPONSE
Qualsiasi sospetta violazione di sicurezza deve essere segnalata immediatamente al Security Operations Center (SOC). Il tempo di risposta massimo è di 4 ore per vulnerabilità critiche.
""")

    # Governance Dati
    with open(DOCUMENTS_DIR / "data_governance.txt", "w", encoding="utf-8") as f:
        f.write("""
GOVERNANCE DEI DATI

1. CLASSIFICAZIONE DATI
Tutti i dati aziendali devono essere classificati in base al livello di riservatezza:
- PUBLIC: Dati pubblicamente disponibili
- INTERNAL: Dati aziendali non critici
- CONFIDENTIAL: Dati sensibili (contratti, piani strategici)
- RESTRICTED: Dati ad accesso limitato (dati personali, finanziari)

2. RETENTION POLICY
I dati devono essere conservati secondo il periodo di retention stabilito:
- Dati transazionali: 7 anni
- Dati personali: Secondo GDPR (massimo tempo di legittimo interesse)
- Dati di sicurezza: Minimo 12 mesi
- Dati di audit: 10 anni per finanza, 5 anni per operazionale

3. DATA GOVERNANCE COMMITTEE
È costituito da: CIO, Chief Privacy Officer, responsabili dipartimentali. Si riunisce mensile per valutare rischi, implementare policy, verificare compliance.

4. GDPR COMPLIANCE
Tutti i trattamenti di dati personali devono avere una base legale esplicita (consenso, obbligo legale, interesse legittimo). È obbligatoria la documentazione del registro dei trattamenti (Data Processing Register).

5. CRITTOGRAFIA
I dati RESTRICTED devono essere crittografati sia in transito (TLS 1.2+) che a riposo (AES-256). Le chiavi di crittografia devono essere gestite tramite Key Management System aziendale.
""")

    logger.info(f"✓ Creati 3 documenti di test in {DOCUMENTS_DIR}")


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Errore fatale: {e}", exc_info=True)
        sys.exit(1)
