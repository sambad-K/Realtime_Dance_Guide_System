import torch
ckpt = torch.load("D:\Major project\A. MAIN\Learn mod\dance_eval_backend\checkpoints\encoder_best.pt", map_location="cpu", weights_only=False)
sd = ckpt["state_dict"] if isinstance(ckpt, dict) and "state_dict" in ckpt else ckpt
keys = [k for k in sd.keys() if k.startswith("encoder.fc") or k.startswith("fc.")]
print(keys[:50])
print("fc.0.weight shape:", sd.get("encoder.fc.0.weight", sd.get("fc.0.weight")).shape)
print("has encoder prefix:", any(k.startswith("encoder.") for k in sd.keys()))
print("some keys:", list(sd.keys())[:15])
