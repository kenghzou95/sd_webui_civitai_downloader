import gradio as gr
import pandas as pd
import html
import sys
import json
import time
import requests
import os

import modules.scripts as scripts
from modules import script_callbacks

from . import util
available_extensions = {"items": []}

sort_ordering = [
   "Highest Rated", "Most Downloaded", "Newest"
]
model_ordering = [
   "Checkpoint", "TextualInversion", "LORA""
]
path_ordering =[
    "stable-diffusion-webui/models/Stable-diffusion", "stable-diffusion-webui\embeddings","stable-diffusion-webui/models/Lora"
]
nsfw_ordering = [
   "false", "true"
]
def refresh_available_extensions_from_data(hide_tags, sort_column, filter_text=""):
    extlist = available_extensions["items"]
    tags = available_extensions.get("tags", {})
    tags_to_hide = set(hide_tags)
    hidden = 0
  
    code = f"""<!-- {time.time()} -->
    <table id="available_extensions">
        <thead>
            <tr>
                <th>Extension</th>
                <th>Description</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
    """
    #sort_reverse, sort_function = sort_ordering[sort_column if 0 <= sort_column < len(sort_ordering) else 0]
   
    for ext in extlist:
        name = ext.get("name", "noname")
        url = ext.get("type", "")
        description = ext.get("nsfw", "")
        extension_tags = ext.get("tags", [])
        
        if url is None:
            continue

        if len([x for x in extension_tags if x in tags_to_hide]) > 0:
            hidden += 1
            continue

        existing = None
  
        install_code = f"""<button onclick="install_extension_from_index(this, '{html.escape(url)}')" {"disabled=disabled" if existing else ""} class="lg secondary gradio-button custom-button">{"Download" if not existing else "Installed"}</button>"""

        tags_text = ", ".join([f"<span class='extension-tag' title='{tags.get(x, '')}'>{x}</span>" for x in extension_tags])

        code += f"""
            <tr>
                <td><a href="{html.escape(url)}" target="_blank">{html.escape(name)}</a><br />{tags_text}</td>
                <td>{description}</td>
                <td>{install_code}</td>
            </tr>

        """

        for tag in [x for x in extension_tags if x not in tags]:
            tags[tag] = tag

    code += """
        </tbody>
    </table>
    """

 
    return code, list(tags)
   



def wrap_gradio_call(func, extra_outputs=None, add_stats=False):
    def f(*args, extra_outputs_array=extra_outputs, **kwargs):
        try:
            res = list(func(*args, **kwargs))
        except Exception as e:
            print("Error completing request", file=sys.stderr) 
            error_message = f'{type(e).__name__}: {e}'
   
        return tuple(res)

    return f
    
def refresh_available_extensions(model_column, hide_tags, sort_column):
    global available_extensions


    from urllib.request import Request, urlopen
   
    urlformat='https://civitai.com/api/v1/models?sort={sort}&limit=100&types={type}&nsfw={nsfwType}'.format(sort=sort_ordering[sort_column],type=model_ordering[model_column],nsfwType=nsfw_ordering[len(hide_tags)])
    urlformat = urlformat.replace(" ", "%20")
    print(urlformat)
    print(hide_tags)
    req = Request(
        url=urlformat, 
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urlopen(req) as response:
        print(response)
        text = response.read()
    
    available_extensions = json.loads(text)
    code, tags = refresh_available_extensions_from_data(hide_tags, sort_column)

    return code,  ''

def on_ui_tabs():
    with gr.Blocks() as ui_component:
            
        with gr.Row():
            #model_column = gr.Radio(value= "Most Downloaded", label="Order", choices=["Highest Rated", "Most Downloaded", "Newest" ], type="index")
            model_column = gr.Radio(value="Checkpoint", label="Hide extensions with tags", choices=["Checkpoint", "Textual Inversion","LORA"], type="index")
            hide_tags = gr.CheckboxGroup(value=[], label="Includes nsfw", choices=[ "Yes"])
            sort_column = gr.Radio(value= "Most Downloaded", label="Order", choices=["Highest Rated", "Most Downloaded", "Newest" ], type="index")
        with gr.Row():
            refresh_available_extensions_button = gr.Button(value="Load", variant="primary") 


        install_result = gr.HTML()
        available_extensions_table = gr.HTML()

        refresh_available_extensions_button.click(
            fn=refresh_available_extensions,
            inputs=[model_column, hide_tags, sort_column],
            outputs=[ available_extensions_table, install_result],
        )
        return [(ui_component, "Civitai Download", "Civitai_download_tab")]
script_callbacks.on_ui_tabs(on_ui_tabs)