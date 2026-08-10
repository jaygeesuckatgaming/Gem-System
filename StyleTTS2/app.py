INTROTXT = """# StyleTTS 2

[Paper](https://arxiv.org/abs/2306.07691) - [Samples](https://styletts2.github.io/) - [Code](https://github.com/yl4579/StyleTTS2) - [Discord](https://discord.gg/ha8sxdG2K4)

A free demo of StyleTTS 2. **I am not affiliated with the StyleTTS 2 Authors.**

**Before using this demo, you agree to inform the listeners that the speech samples are synthesized by the pre-trained models, unless you have the permission to use the voice you synthesize. That is, you agree to only use voices whose speakers grant the permission to have their voice cloned, either directly or by license before making synthesized voices public, or you have to publicly announce that these voices are synthesized if you do not have the permission to use these voices.**

Is there a long queue on this space? Duplicate it and add a more powerful GPU to skip the wait! **Note: Thank you to Hugging Face for their generous GPU grant program!**

**NOTE: StyleTTS 2 does better on longer texts.** For example, making it say "hi" will produce a lower-quality result than making it say a longer phrase.

**NOTE: StyleTTS 2 is _currently_ English-only. Join the Discord for updates on multilingual training.**
"""
import gradio as gr
import styletts2importable
import ljspeechimportable
import torch
import nltk
nltk.download('punkt_tab')
import os
from txtsplit import txtsplit
import numpy as np
import pickle
theme = gr.themes.Base(
    font=[gr.themes.GoogleFont('Libre Franklin'), gr.themes.GoogleFont('Public Sans'), 'system-ui', 'sans-serif'],
)
voicelist = ['f-us-1', 'f-us-2', 'f-us-3', 'f-us-4', 'm-us-1', 'm-us-2', 'm-us-3', 'm-us-4']
voices = {}
import phonemizer
global_phonemizer = phonemizer.backend.EspeakBackend(language='en-us', preserve_punctuation=True,  with_stress=True)
# todo: cache computed style, load using pickle
# if os.path.exists('voices.pkl'):
    # with open('voices.pkl', 'rb') as f:
        # voices = pickle.load(f)
# else:
for v in voicelist:
    voices[v] = styletts2importable.compute_style(f'voices/{v}.wav')
# def synthesize(text, voice, multispeakersteps):
#     if text.strip() == "":
#         raise gr.Error("You must enter some text")
#     # if len(global_phonemizer.phonemize([text])) > 300:
#     if len(text) > 300:
#         raise gr.Error("Text must be under 300 characters")
#     v = voice.lower()
#     # return (24000, styletts2importable.inference(text, voices[v], alpha=0.3, beta=0.7, diffusion_steps=7, embedding_scale=1))
#     return (24000, styletts2importable.inference(text, voices[v], alpha=0.3, beta=0.7, diffusion_steps=multispeakersteps, embedding_scale=1))
if not torch.cuda.is_available(): INTROTXT += "\n\n### You are on a CPU-only system, inference will be much slower.\n\nYou can use the [online demo](https://huggingface.co/spaces/styletts2/styletts2) for fast inference."
def synthesize(text, voice, lngsteps, password, progress=gr.Progress()):
    if text.strip() == "":
        raise gr.Error("You must enter some text")
    if len(text) > 50000:
        raise gr.Error("Text must be <50k characters")
    print("*** saying ***")
    print(text)
    print("*** end ***")
    texts = txtsplit(text)
    v = voice.lower()
    audios = []
    for t in progress.tqdm(texts):
        print(t)
        audios.append(styletts2importable.inference(t, voices[v], alpha=0.3, beta=0.7, diffusion_steps=lngsteps, embedding_scale=1))
    return (24000, np.concatenate(audios))
# def longsynthesize(text, voice, lngsteps, password, progress=gr.Progress()):
#     if password == os.environ['ACCESS_CODE']:
#         if text.strip() == "":
#             raise gr.Error("You must enter some text")
#         if lngsteps > 25:
#             raise gr.Error("Max 25 steps")
#         if lngsteps < 5:
#             raise gr.Error("Min 5 steps")
#         texts = split_and_recombine_text(text)
#         v = voice.lower()
#         audios = []
#         for t in progress.tqdm(texts):
#             audios.append(styletts2importable.inference(t, voices[v], alpha=0.3, beta=0.7, diffusion_steps=lngsteps, embedding_scale=1))
#         return (24000, np.concatenate(audios))
#     else:
#         raise gr.Error('Wrong access code')
def rn_clsynthesize(text, voice, vcsteps, embscale, alpha, beta, progress=gr.Progress()):
    # if text.strip() == "":
    #     raise gr.Error("You must enter some text")
    # # if global_phonemizer.phonemize([text]) > 300:
    # if len(text) > 400:
    #     raise gr.Error("Text must be under 400 characters")
    # # return (24000, styletts2importable.inference(text, styletts2importable.compute_style(voice), alpha=0.3, beta=0.7, diffusion_steps=20, embedding_scale=1))
    # return (24000, styletts2importable.inference(text, styletts2importable.compute_style(voice), alpha=0.3, beta=0.7, diffusion_steps=vcsteps, embedding_scale=1))
    if text.strip() == "":
        raise gr.Error("You must enter some text")
    if len(text) > 50000:
        raise gr.Error("Text must be <50k characters")
    if embscale > 1.3 and len(text) < 20:
        gr.Warning("WARNING: You entered short text, you may get static!")
    print("*** saying ***")
    print(text)
    print("*** end ***")
    texts = txtsplit(text)
    audios = []
    # vs = styletts2importable.compute_style(voice)
    vs = styletts2importable.compute_style(voice)
    # print(vs)
    for t in progress.tqdm(texts):
        audios.append(styletts2importable.inference(t, vs, alpha=alpha, beta=beta, diffusion_steps=vcsteps, embedding_scale=embscale))
        # audios.append(styletts2importable.inference(t, vs, diffusion_steps=10, alpha=0.3, beta=0.7, embedding_scale=5))
    return (24000, np.concatenate(audios))
def rn_ljsynthesize(text, steps, progress=gr.Progress()):
    # if text.strip() == "":
    #     raise gr.Error("You must enter some text")
    # # if global_phonemizer.phonemize([text]) > 300:
    # if len(text) > 400:
    #     raise gr.Error("Text must be under 400 characters")
    noise = torch.randn(1,1,256).to('cuda' if torch.cuda.is_available() else 'cpu')
    # return (24000, ljspeechimportable.inference(text, noise, diffusion_steps=7, embedding_scale=1))
    if text.strip() == "":
        raise gr.Error("You must enter some text")
    if len(text) > 150000:
        raise gr.Error("Text must be <150k characters")
    print("*** saying ***")
    print(text)
    print("*** end ***")
    texts = txtsplit(text)
    audios = []
    for t in progress.tqdm(texts):
        audios.append(ljspeechimportable.inference(t, noise, diffusion_steps=steps, embedding_scale=1))
    return (24000, np.concatenate(audios))


with gr.Blocks() as vctk:
    with gr.Row():
        with gr.Column(scale=1):
            inp = gr.Textbox(label="Text", info="What would you like StyleTTS 2 to read? It works better on full sentences.", interactive=True)
            voice = gr.Dropdown(voicelist, label="Voice", info="Select a default voice.", value='m-us-2', interactive=True)
            multispeakersteps = gr.Slider(minimum=3, maximum=15, value=3, step=1, label="Diffusion Steps", info="Theoretically, higher should be better quality but slower, but we cannot notice a difference. Try with lower steps first - it is faster", interactive=True)
            # use_gruut = gr.Checkbox(label="Use alternate phonemizer (Gruut) - Experimental")
        with gr.Column(scale=1):
            btn = gr.Button("Synthesize", variant="primary")
            audio = gr.Audio(interactive=False, label="Synthesized Audio", show_download_button=True, waveform_options={'waveform_progress_color': '#3C82F6'})
            btn.click(synthesize, inputs=[inp, voice, multispeakersteps], outputs=[audio], concurrency_limit=4)
with gr.Blocks() as clone:
    with gr.Row():
        with gr.Column(scale=1):
            clinp = gr.Textbox(label="Text", info="What would you like StyleTTS 2 to read? It works better on full sentences.", interactive=True)
            clvoice = gr.Audio(label="Voice", interactive=True, type='filepath', max_length=300, waveform_options={'waveform_progress_color': '#3C82F6'})
            vcsteps = gr.Slider(minimum=3, maximum=20, value=20, step=1, label="Diffusion Steps", info="Theoretically, higher should be better quality but slower, but we cannot notice a difference. Try with lower steps first - it is faster", interactive=True)
            embscale = gr.Slider(minimum=1, maximum=10, value=1, step=0.1, label="Embedding Scale (READ WARNING BELOW)", info="Defaults to 1. WARNING: If you set this too high and generate text that's too short you will get static!", interactive=True)
            alpha = gr.Slider(minimum=0, maximum=1, value=0.3, step=0.1, label="Alpha", info="Defaults to 0.3", interactive=True)
            beta = gr.Slider(minimum=0, maximum=1, value=0.7, step=0.1, label="Beta", info="Defaults to 0.7", interactive=True)
        with gr.Column(scale=1):
            clbtn = gr.Button("Synthesize", variant="primary")
            claudio = gr.Audio(interactive=False, label="Synthesized Audio", show_download_button=True, waveform_options={'waveform_progress_color': '#3C82F6'})
            clbtn.click(rn_clsynthesize, inputs=[clinp, clvoice, vcsteps, embscale, alpha, beta], outputs=[claudio], concurrency_limit=4)
# with gr.Blocks() as longText:
#     with gr.Row():
#         with gr.Column(scale=1):
#             lnginp = gr.Textbox(label="Text", info="What would you like StyleTTS 2 to read? It works better on full sentences.", interactive=True)
#             lngvoice = gr.Dropdown(voicelist, label="Voice", info="Select a default voice.", value='m-us-1', interactive=True)
#             lngsteps = gr.Slider(minimum=5, maximum=25, value=10, step=1, label="Diffusion Steps", info="Higher = better quality, but slower", interactive=True)
#             lngpwd = gr.Textbox(label="Access code", info="This feature is in beta. You need an access code to use it as it uses more resources and we would like to prevent abuse")
#         with gr.Column(scale=1):
#             lngbtn = gr.Button("Synthesize", variant="primary")
#             lngaudio = gr.Audio(interactive=False, label="Synthesized Audio")
#             lngbtn.click(longsynthesize, inputs=[lnginp, lngvoice, lngsteps, lngpwd], outputs=[lngaudio], concurrency_limit=4)
with gr.Blocks() as lj:
    with gr.Row():
        with gr.Column(scale=1):
            ljinp = gr.Textbox(label="Text", info="What would you like StyleTTS 2 to read? It works better on full sentences.", interactive=True)
            ljsteps = gr.Slider(minimum=3, maximum=20, value=3, step=1, label="Diffusion Steps", info="Theoretically, higher should be better quality but slower, but we cannot notice a difference. Try with lower steps first - it is faster", interactive=True)
        with gr.Column(scale=1):
            ljbtn = gr.Button("Synthesize", variant="primary")
            ljaudio = gr.Audio(interactive=False, label="Synthesized Audio", waveform_options={'waveform_progress_color': '#3C82F6'})
            ljbtn.click(rn_ljsynthesize, inputs=[ljinp, ljsteps], outputs=[ljaudio], concurrency_limit=4)
with gr.Blocks(title="StyleTTS 2", css="footer{display:none !important}", theme=theme) as demo:
    gr.Markdown(INTROTXT)
    gr.DuplicateButton("Duplicate Space")
    # gr.TabbedInterface([vctk, clone, lj, longText], ['Multi-Voice', 'Voice Cloning', 'LJSpeech', 'Long Text [Beta]'])
    gr.TabbedInterface([vctk, clone, lj], ['Multi-Voice', 'Voice Cloning', 'LJSpeech', 'Long Text [Beta]'])
    gr.Markdown("""
Demo by [mrfakename](https://twitter.com/realmrfakename). I am not affiliated with the StyleTTS 2 authors.

Run this demo locally using Docker:

```bash
docker run -it -p 7860:7860 --platform=linux/amd64 --gpus all registry.hf.space/styletts2-styletts2:latest python app.py
```
""") # Please do not remove this line.
if __name__ == "__main__":
    # demo.queue(api_open=False, max_size=15).launch(show_api=False)
    demo.queue(api_open=False, max_size=15).launch(show_api=False)

