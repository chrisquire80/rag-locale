
import sys
from pathlib import Path
from collections import Counter

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.config import DOCUMENTS_DIR
from src.vector_store import get_vector_store

def check_missing_files():
    print(f"\n🔍 Analisi Discrepanze Documenti vs Vector Store")
    print(f"==================================================")
    
    # 1. Get Physical Files
    extensions = {'.pdf', '.txt', '.md', '.docx'}
    physical_files = {
        f.name: f 
        for f in DOCUMENTS_DIR.glob('*') 
        if f.suffix.lower() in extensions
    }
    print(f"📂 File in cartella {DOCUMENTS_DIR.name}: {len(physical_files)}")
    
    # 2. Get Vector Store Files
    vs = get_vector_store()
    vs_files_counter = Counter()
    
    for doc_id, doc in vs.documents.items():
        source = doc.metadata.get('source', 'unknown')
        vs_files_counter[source] += 1
        
    vs_filenames = set(vs_files_counter.keys())
    print(f"💾 File nel Vector Store: {len(vs_filenames)}")
    print(f"🧩 Totale Chunk nel DB: {len(vs.documents)}")
    
    print(f"\n📊 Dettagli:")
    print(f"--------------------------------------------------")
    
    # 3. Find Missing
    missing = []
    for fname in physical_files:
        if fname not in vs_filenames:
            missing.append(fname)
            
    if missing:
        print(f"❌ {len(missing)} FILE MANCANTI (Presenti in cartella ma non nel DB):")
        for m in missing:
            print(f"   - {m}")
    else:
        print("✅ Tutti i file della cartella sono presenti nel DB.")

    # 4. Check for low chunk counts (potential read errors)
    print(f"\n⚠️ Controllo file con pochi chunk (<3):")
    low_chunk_files = [f for f, count in vs_files_counter.items() if count < 3]
    if low_chunk_files:
        for f in low_chunk_files:
            print(f"   - {f}: {vs_files_counter[f]} chunks")
    else:
        print("   Nessuna anomalia rilevata.")

if __name__ == "__main__":
    check_missing_files()
