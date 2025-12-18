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
Hai a disposizione una trascrizione approssimativa di una registrazione audio con gli eventi salienti di una partita di basket.

    Le azioni riportate nella trascrizione sono solo quelle della squadra Ponte Vecchio: tiri sbagliati, canestri, sostituzioni, falli.  Sono tutte importanti e non devi ignorarne nessuna.

    Per quanto riguarda la squadra avversaria, vengono indicati solo i canestri segnati.
    La trascrizione è in italiano.  
    Ogni riga della trascrizione comincia con un timestamp tra parentesi quadre nel formato [mm:ss] che indica il minuto e il secondo della registrazione: 
    questa informazione non è importante.
    Dopo le parentesi quadre c'è il testo della trascrizione dell'evento che comincia si solito con l'indicazione del quarto in cui l'evento è avvenuto 
    (es. Q1 per "Primo Quarto", Q2 per "Secondo Quarto", ecc.) e con il tempo rimanente da giocare in quel quarto (es. 09:15 per 9 minuti e 15 secondi rimanenti).  
    Segue la descrizione dell'evento ed eventualmente il numero del giocatore coinvolto nell'azione.
    Ad esempio: [09:15] Q1 09:15 Canestro da due della numero 15.

    Se un evento viene assegnato ad una giocatrice che non è in campo in quel momento, devi correggere l'errore e assegnare l'evento alla giocatrice 
    con il numero più vicino tra quelle effettivamente in campo in quel momento.

    A volte la trascrizione contiene indicazioni aggiuntive come il nome della squadra avversaria, 
    il punteggio parziale dopo l'azione, la formazione in campo della squadra Ponte Vecchio, ecc.
    Censisci anche queste informazioni come eventi separati nella lista finale in formato json indicandoli 
    con nome opportuni come "punteggio parziale", "formazione in campo", "squadra avversaria", ecc.
    Tieni presente che queste indicazioni aggiuntive sono più affidabili rispetto al calcolo dai singoli canestri e
    possono essere utili per correggere eventuali errori nella trascrizione principale.

    L'ordine temporale degli eventi nella trascrizione è dato dal tempo del quarto e non dall'ordine in cui compaiono nella trascrizione stessa: devi tenerne conto
    e ordinare gli eventi di conseguenza.
    
    La trascrizione può contenere errori.  Gli errori più comuni sono:
    - omissione di una sostituzione
    - nome della squadra avversaria errato
    - omissione di un canestro della squadra avversaria.
    Devi essere in grado di correggere gli errori e fornire l'interpretazione più accurata possibile.

    Il tuo compito è quello di analizzare la trascrizione e trasformarla in una lista di azioni in formato json.  Per ogni azione devi indicare:
    - il quarto, il minuto e il secondo in cui l'azione è avvenuta: chiave = "time", valore = stringa nel formato Q# mm:ss
    - il tipo di azione (es. canestro da due punti, tiro sbagliato da tre punti, fallo in difesa, sostituzione, punteggio parziale, squadra in campo, ecc.): chiave = "action_type", valore = stringa
    - il giocatore coinvolto (se applicabile): chiave = "player", valore = stringa
    - il punteggio parziale dopo l'azione per la pontevecchio: chiave = "score_ponte_vecchio", valore = intero
    - il punteggio parziale dopo l'azione per la squadra avversaria: chiave = "score_opponent", valore = intero
    - la formazione della squadra Ponte Vecchio dopo l'azione (elenco dei giocatori in campo): chiave = "formation_ponte_vecchio", valore = lista di stringhe

    Prima della lista in formato json, fornisci un'intestazione in italiano che presenti le squadre in campo e riporti tutti gli elementi di 
    contesto che riesci ad estrarre dalla trascrizione (data, tipo di partita, luogo, ecc.).

    ----------------------------------------------

    __INIZIO TRASCRIZIONE__
    {trascrizione}
"""

def main():
    # Initialize LLM inside main to avoid side-effects at import time
    llm = init_llm(
       model_name='gpt-4o',
       temperature=0.1,
       max_tokens=16384,
       system_prompt=("Sei un'esperta di calcolo di statistiche per partite di basket.")
    )

    # Get folder containing .txt transcription files from command line
    parser = argparse.ArgumentParser(description="Analyze concatenated transcription files in a folder")
    parser.add_argument("transcription_dir", nargs="?", default="/basket_stats_assistant/data", help="Path to folder containing .txt transcription files")
    args = parser.parse_args()

    from pathlib import Path
    transcription_dir = Path(args.transcription_dir)
    if not transcription_dir.exists() or not transcription_dir.is_dir():
        logging.error(f"Transcription directory does not exist or is not a directory: {transcription_dir}")
        sys.exit(1)

    # Read and concatenate all .txt files in the directory (non-recursive), sorted by name
    txt_files = sorted(transcription_dir.glob("*.txt"))
    if not txt_files:
        logging.warning(f"No .txt transcription files found in {transcription_dir}")
        loaded_transcription = ""
    else:
        parts = []
        for p in txt_files:
            try:
                text = p.read_text(encoding='utf-8')
                parts.append(text)
            except Exception as e:
                logging.error(f"Failed to read {p}: {e}")
        loaded_transcription = "\n\n".join(parts)

    # Build prompt using the loaded transcription
    prompt = prompt_template.format(trascrizione=loaded_transcription)

    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    response_content = response.content

    # Write the result to a single .result file in the same folder
    output_path = transcription_dir / f"{transcription_dir.name}.result"
    try:
        output_path.write_text(response_content, encoding='utf-8')
        logging.info(f"Wrote analysis result to {output_path}")
    except Exception as e:
        logging.error(f"Failed to write result file {output_path}: {e}")


if __name__ == '__main__':
    main()

