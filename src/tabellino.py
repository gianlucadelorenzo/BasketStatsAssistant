import sys
import os
import logging
import json
import tiktoken
import argparse
import base64
from pydantic import BaseModel
from gen_ai_hub.proxy.langchain.init_models import init_llm
from langchain_core.prompts import PromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableSequence
from langchain_core.messages import AIMessage, HumanMessage
import boto3
from botocore.exceptions import ClientError
import re 
from hdbcli import dbapi
from dotenv import load_dotenv
from graphviz import Source
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global flag to track if context length errors occurred
context_length_errors_occurred = False

# Load environment variables from .env file (if present)
load_dotenv()

# --- AI Core configuration: use environment variables only ---
AICORE_BASE_URL = os.getenv("AICORE_BASE_URL")
AICORE_CLIENT_ID = os.getenv("AICORE_CLIENT_ID")
AICORE_CLIENT_SECRET = os.getenv("AICORE_CLIENT_SECRET")
AICORE_AUTH_URL = os.getenv("AICORE_AUTH_URL")
AICORE_RESOURCE_GROUP = os.getenv("AICORE_RESOURCE_GROUP")



# Prompt template (kept at module level so it can be imported/tested)
prompt_template = """
### Prompt per Analisi Statistica da Sorgente JSON

**Oggetto: Elaborazione Statistica Avanzata da Stream JSON – Basket**

"Agisci come un software di analisi dati sportivi. Riceverai in input un dataset in formato JSON che contiene la cronologia degli eventi di una partita di basket. 
Il tuo compito è aggregare questi dati per generare il box score finale.

**ISTRUZIONI DI CALCOLO:**

1. **Minutaggio (MIN):** Questa è l'operazione più critica.
* Ogni quarto dura esattamente 10:00 minuti (da 10:00 a 0:00).
* Utilizza gli eventi 'sostitution' per tracciare le entrate e le uscite delle giocatrici.
* Utilizza anche il campo `formation_ponte_vecchio` come cross check.
* Se una giocatrice è presente dall'inizio di un quarto e viene sostituita al minuto 5:36, conta 4:24 minuti giocati in quel quarto.
* Calcola il totale dei secondi giocati per ogni giocatrice e convertilo nel formato MM:SS.
* La somma totale dei minuti giocati dalla squadra deve essere esattamente: (Numero Quarti × 5 giocatrici × 10 minuti).


2. **Statistiche di Tiro:** Aggrega `action_type` per ogni `player` (2pt segnati/sbagliati, 3pt segnati/sbagliati, tiri liberi).
* FGM = Canestri da 2 segnati + Canestri da 3 segnati.
* FGA = Tutti i tiri dal campo tentati (segni e sbagliati).
* Calcola le percentuali (FG%, 2P%, 3P%, FT%) con un decimale.


3. **Valutazione (PIR EFF):** Applica la formula:
*(Punti + Rimbalzi + Assist + Recuperi + Stoppate + Falli Subiti) - (Tiri dal Campo Sbagliati + Liberi Sbagliati + Palle Perse + Falli Fatti)*.

**OUTPUT RICHIESTO:**

**1. Tabella Riepilogo Punteggio:**
Colonne: Squadra | Q1 | Q2 | Q3 | Q4 | Finale.
per ogni quarto, indica solo i punti segnati in quel quarto e fai la somma per il punteggio finale.
Se presenti, usa i dati di punteggio parziale dagli eventi per controllare la coerenza dei punti per quarto: questi dati sono più affidabili rispetto al calcolo dai singoli canestri.

**2. Box Score Individuale (Ponte Vecchio):**
Genera una tabella con le seguenti colonne:

* **NUM** (Numero) | **NOME** | 
* **MIN** (Minuti MM:SS) | **PTS** (Punti)
* **FGM/FGA** | **FG%**
* **2PM/2PA** | **2P%**
* **3PM/3PA** | **3P%**
* **FTM/FTA** | **FT%**
* **PF** (Falli Fatti) | **PFD** (Falli Subiti)
* **PIR EFF** (Valutazione)

Includi la riga dei **TOTALI** di squadra.

Alla fine dell'analisi controlla la correttezza dei risultati ricontando, per ogni giocatrice, 
i canestri realizzati facendo attenzione ai punti per ogni canestro, i tiri sbagliati anche qui facendo attenzione al tipo di tiro,
e i minuti giocati.  Sistema eventuali discrepanze trovate correggendo i tabellini di conseguenza.

Questi i nomi delle giocatrici della squadra Ponte Vecchio con i rispettivi numeri di maglia:
{rosa_ponte_vecchio}

**DATASET JSON DA ELABORARE:**
{trascrizione}
"""

def main():
    # Initialize LLM inside main to avoid side-effects at import time
    llm = init_llm(
       model_name='gemini-2.5-pro',
       temperature=0.1,
       max_tokens=65536,
       system_prompt=("Sei un'esperta di calcolo di statistiche per partite di basket.")
    )

    parser = argparse.ArgumentParser(description="Generate tabellino from a single .result file and a roster file")
    parser.add_argument('input_file', help='Path to the .result (or transcription) input file to analyze')
    parser.add_argument('--roster', dest='roster', default='/basket_stats_assistant/data/formazione_PV.txt', help='Path to roster file (default: /basket_stats_assistant/data/formazione_PV.txt)')
    args = parser.parse_args()

    from pathlib import Path
    input_path = Path(args.input_file)
    if not input_path.exists() or not input_path.is_file():
        logging.error(f"Input file does not exist or is not a file: {input_path}")
        sys.exit(1)

    roster_path = Path(args.roster)
    loaded_roster = ''
    if roster_path.exists() and roster_path.is_file():
        try:
            loaded_roster = roster_path.read_text(encoding='utf-8')
        except Exception as e:
            logging.error(f"Failed to read roster file {roster_path}: {e}")
            loaded_roster = ''
    else:
        logging.warning(f"Roster file not found, continuing with empty roster: {roster_path}")

    try:
        loaded_transcription = input_path.read_text(encoding='utf-8')
    except Exception as e:
        logging.error(f"Failed to read input file {input_path}: {e}")
        sys.exit(1)

    # Build prompt using the loaded transcription and roster
    prompt = prompt_template.format(trascrizione=loaded_transcription, rosa_ponte_vecchio=loaded_roster)

    logging.info("Invoking LLM...")
    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    response_content = response.content

    # Write the result to a .tabellino file with same basename as input
    output_path = input_path.with_suffix('.tabellino.md')
    try:
        output_path.write_text(response_content, encoding='utf-8')
        logging.info(f"Wrote tabellino result to {output_path}")
    except Exception as e:
        logging.error(f"Failed to write tabellino file {output_path}: {e}")


if __name__ == '__main__':
    main()

