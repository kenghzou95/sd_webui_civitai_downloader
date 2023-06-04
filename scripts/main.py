import gradio as gr
import pandas as pd
import html
import sys
import json
import time
import requests
import os
import io
import hashlib
import shutil
import modules.scripts as scripts
from modules import script_callbacks


version = "1.6.4"

def_headers = {'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'}


proxies = None

available_extensions = {"items": []}

sort_ordering = [
   "Highest Rated", "Most Downloaded", "Newest"
]
model_ordering = [
   "Checkpoint", "TextualInversion", "LORA"
]
path_ordering =[
    "stable-diffusion-webui/models/Stable-diffusion", "stable-diffusion-webui\embeddings","stable-diffusion-webui/models/Lora"
]
nsfw_ordering = [
   "false", "true"
]
from modules import shared


# this is the default root path
root_path = os.getcwd()

# if command line arguement is used to change model folder, 
# then model folder is in absolute path, not based on this root path anymore.
# so to make extension work with those absolute model folder paths, model folder also need to be in absolute path
folders = [
   os.path.join(root_path, "models", "Stable-diffusion"),
   os.path.join(root_path, "embeddings"),
   os.path.join(root_path, "models", "Lora"),
   os.path.join(root_path, "models", "hypernetworks"),
]

exts = (".bin", ".pt", ".safetensors", ".ckpt")
info_ext = ".info"
vae_suffix = ".vae"

# print for debugging
def printD(msg):
    print(f"Civitai Downloader: {msg}")


def read_chunks(file, size=io.DEFAULT_BUFFER_SIZE):
    """Yield pieces of data from a file-like object until EOF."""
    while True:
        chunk = file.read(size)
        if not chunk:
            break
        yield chunk

# Now, hashing use the same way as pip's source code.
def gen_file_sha256(filname):
    printD("Use Memory Optimized SHA256")
    blocksize=1 << 20
    h = hashlib.sha256()
    length = 0
    with open(os.path.realpath(filname), 'rb') as f:
        for block in read_chunks(f, size=blocksize):
            length += len(block)
            h.update(block)

    hash_value =  h.hexdigest()
    printD("sha256: " + hash_value)
    printD("length: " + str(length))
    return hash_value



# get preview image
def download_file(url, path):
    printD("Downloading file from: " + url)
    # get file
    r = requests.get(url, stream=True, headers=def_headers, proxies=proxies)
    if not r.ok:
        printD("Get error code: " + str(r.status_code))
        printD(r.text)
        return
    
    # write to file
    with open(os.path.realpath(path), 'wb') as f:
        r.raw.decode_content = True
        shutil.copyfileobj(r.raw, f)

    printD("File downloaded to: " + path)

# get subfolder list
def get_subfolders(folder:str) -> list:
    printD("Get subfolder for: " + folder)
    if not folder:
        printD("folder can not be None")
        return
    
    if not os.path.isdir(folder):
        printD("path is not a folder")
        return
    
    prefix_len = len(folder)
    subfolders = []
    for root, dirs, files in os.walk(folder, followlinks=True):
        for dir in dirs:
            full_dir_path = os.path.join(root, dir)
            # get subfolder path from it
            subfolder = full_dir_path[prefix_len:]
            subfolders.append(subfolder)

    return subfolders


# get relative path
def get_relative_path(item_path:str, parent_path:str) -> str:
    # printD("item_path:"+item_path)
    # printD("parent_path:"+parent_path)
    # item path must start with parent_path
    if not item_path:
        return ""
    if not parent_path:
        return ""
    if not item_path.startswith(parent_path):
        return item_path

    relative = item_path[len(parent_path):]
    if relative[:1] == "/" or relative[:1] == "\\":
        relative = relative[1:]

    # printD("relative:"+relative)
    return relative
    
    
    

dl_ext = ".downloading"

# disable ssl warning info
requests.packages.urllib3.disable_warnings()

# output is downloaded file path
def dl(url, filepath):
    printD("Start downloading from: " + url)
    # get file_path
    file_path = ""
    if filepath:
        file_path = filepath
    else:
        printD("folder is none")
        return

    # first request for header
    rh = requests.get(url, stream=True, verify=False, headers=def_headers, proxies=proxies)
    # get file size
    total_size = 0
    total_size = int(rh.headers['Content-Length'])
    printD(f"File size: {total_size}")

    # if file_path is empty, need to get file name from download url's header
    if not file_path:
        filename = ""
        if "Content-Disposition" in rh.headers.keys():
            cd = rh.headers["Content-Disposition"]
            # Extract the filename from the header
            # content of a CD: "attachment;filename=FileName.txt"
            # in case "" is in CD filename's start and end, need to strip them out
            filename = cd.split("=")[1].strip('"')
            if not filename:
                printD("Fail to get file name from Content-Disposition: " + cd)
                return
            
        if not filename:
            printD("Can not get file name from download url's header")
            return
        
        # with folder and filename, now we have the full file path
        file_path = os.path.join(folder, filename)


    printD("Target file path: " + file_path)
    base, ext = os.path.splitext(file_path)

    # check if file is already exist
    count = 2
    new_base = base
    while os.path.isfile(file_path):
        printD("Target file already exist.")
        # re-name
        new_base = base + "_" + str(count)
        file_path = new_base + ext
        count += 1

    # use a temp file for downloading
    dl_file_path = new_base+dl_ext


    printD(f"Downloading to temp file: {dl_file_path}")

    # check if downloading file is exsited
    downloaded_size = 0
    if os.path.exists(dl_file_path):
        downloaded_size = os.path.getsize(dl_file_path)

    printD(f"Downloaded size: {downloaded_size}")

    # create header range
    headers = {'Range': 'bytes=%d-' % downloaded_size}
    headers['User-Agent'] = def_headers['User-Agent']

    # download with header
    r = requests.get(url, stream=True, verify=False, headers=headers, proxies=proxies)

    # write to file
    with open(dl_file_path, "ab") as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                downloaded_size += len(chunk)
                f.write(chunk)
                # force to write to disk
                f.flush()

                # progress
                progress = int(50 * downloaded_size / total_size)
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stdout.write("\r[%s%s] %d%%" % ('-' * progress, ' ' * (50 - progress), 100 * downloaded_size / total_size))
                sys.stdout.flush()

    print()

    # rename file
    os.rename(dl_file_path, file_path)
    printD(f"File Downloaded to: {file_path}")
    return file_path
    
def dl_model_new_version(msg, max_size_preview, skip_nsfw_preview):
    printD("Start dl_model_new_version")

    output = ""

    result = msg_handler.parse_js_msg(msg)
    if not result:
        output = "Parsing js ms failed"
        printD(output)
        return output
    
    model_path = result["model_path"]
    version_id = result["version_id"]
    download_url = result["download_url"]

    printD("model_path: " + model_path)
    printD("version_id: " + str(version_id))
    printD("download_url: " + download_url)

    # check data
    if not model_path:
        output = "model_path is empty"
        printD(output)
        return output

    if not version_id:
        output = "version_id is empty"
        printD(output)
        return output
    
    if not download_url:
        output = "download_url is empty"
        printD(output)
        return output

    if not os.path.isfile(model_path):
        output = "model_path is not a file: "+ model_path
        printD(output)
        return output

    # get model folder from model path
    model_folder = os.path.dirname(model_path)

    # no need to check when downloading new version, since checking new version is already checked
    # check if this model is already existed
    # r = civitai.search_local_model_info_by_version_id(model_folder, version_id)
    # if r:
    #     output = "This model version is already existed"
    #     printD(output)
    #     return output

    # download file
    new_model_path = dl(download_url, model_folder, None, None)
    if not new_model_path:
        output = "Download failed, check console log for detail. Download url: " + download_url
        printD(output)
        return output



    output = "Done. Model downloaded to: " + new_model_path
    printD(output)
    return output
    
def refresh_available_extensions_from_data(model_column,hide_tags, sort_column, filter_text=""):
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
        model_version = ext["modelVersions"]
        for mdl in model_version:
            files = mdl["files"]
            for file in files:
                url = file.get("downloadUrl","")
                name = file.get("name", "noname")
                type = ext.get("type", "")
                description = ext.get("nsfw", "")
                extension_tags = ext.get("tags", [])
                
                if url is None:
                    continue

                if len([x for x in extension_tags if x in tags_to_hide]) > 0:
                    hidden += 1
                    continue

                existing = None
                printD(url)
                printD(folders[model_column])
                install_code = f"""<button onclick="dl({html.escape(url)}, '{folders[model_column]}')" class="lg secondary gradio-button custom-button">Download</button>"""

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
    code, tags = refresh_available_extensions_from_data(model_column,hide_tags, sort_column)

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