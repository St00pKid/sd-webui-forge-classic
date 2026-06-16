import os
import sys

# Make the lora_manager package importable from within the extension directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import script_callbacks
from lora_manager.ui_components import build_lora_manager_tab

_EXT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CSS_PATH = os.path.join(_EXT_DIR, "style.css")


def on_ui_tabs():
    tab = build_lora_manager_tab()
    return [(tab, "LoRA Manager", "lora_manager_tab")]


script_callbacks.on_ui_tabs(on_ui_tabs)
