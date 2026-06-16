import torch
from modules import script_callbacks, shared

last_model = None

def on_model_loaded(checkpoint_info):
    """Offload VRAM when model changes"""
    global last_model
    current_model = checkpoint_info.filename  # Full path to the loaded model
    if last_model != current_model and last_model is not None:
        if hasattr(shared, 'sd_model') and shared.sd_model is not None:
            shared.sd_model.to('cpu')  # Offload to RAM
            torch.cuda.empty_cache()  # Clear VRAM
            print(f"Offloaded model {last_model} from VRAM")
        else:
            torch.cuda.empty_cache()  # Fallback if sd_model isn’t set
            print("Cleared VRAM (no model object available)")
    last_model = current_model

# Register the callback
script_callbacks.on_model_loaded(on_model_loaded)