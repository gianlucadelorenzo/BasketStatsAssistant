from gen_ai_hub.proxy.native.google_vertexai.clients import GenerativeModel

import os
import mimetypes

imagePath = '/JupyterNotebooks/Colosseo_2020.jpg'

model = GenerativeModel(
    model_name="gemini-2.5-pro",
    generation_config={
        "temperature": 0,  #0 to 2
        "top_p": 0,  #0 to 1
        "top_k": 1,  #1 to 65
        "max_output_tokens": 65536, #1 to 65536,
    }
)

mime, _ = mimetypes.guess_type(imagePath)
with open(imagePath, "rb") as f:
    image = f.read()

response = model.generate_content(
        contents=[
                    {
                        "role": "user",
                        "parts": [
                            {"text": "mi descrivi l'immagine in poche parole?"},
                            {"inline_data": {"mime_type": mime, "data": image}}
                        ]
            }])

# Stampa la risposta
print(response)

################################################
################################################

from gen_ai_hub.proxy.native.google_vertexai.clients import GenerativeModel
import os
import mimetypes


imagePath = '/JupyterNotebooks/MiTE-2023-0001900.pdf'

model = GenerativeModel(
    model_name="gemini-2.5-pro",
    generation_config={
        "temperature": 0,  #0 to 2
        "top_p": 0,  #0 to 1
        "top_k": 1,  #1 to 65
        "max_output_tokens": 65536, #1 to 65536,
    }
)

mime, _ = mimetypes.guess_type(imagePath)
with open(imagePath, "rb") as f:
    image = f.read()

response = model.generate_content(
        contents=[
                    {
                        "role": "user",
                        "parts": [
                            {"text": """mi crei un json con il contenuto del documento allegato.
                            Il json deve avere i seguenti campi:
                            -pagina: pagina in cui inizia il testo
                            -posizione: sequenza di numeri in pagina
                            -tipologia: apice,pedice,titolo,paragrafo,immagine"
                            -contenuto: il testo parola per parola. in caso di immagine una descrizione dettagliata, in caso di tabella una tabella in formato json

                            se ci sono più macroparagrafi coerenti tra loro puoi raggrupparli nella cella contenuto. Possono essere capitoli o sottocapitoli del documento ad esempio
                            """
                            },
                            {"inline_data": {"mime_type": mime, "data": image}}
                        ]
            }])

# Stampa la risposta
print(response.text)

################################################
################################################


from gen_ai_hub.proxy.native.openai import chat

# For models supporting direct file handling
with open(imagePath, "rb") as image_file:
    messages = [
        {
            "role": "user", 
            "content": [
                {"type": "text", "text": "Describe this image in a few words."},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image_file.read()).decode()}}
            ]
        }
    ]

response = chat.completions.create(
    model_name="gpt-4o",
    messages=messages
)

