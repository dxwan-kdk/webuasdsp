# DSP Web Pengolahan Citra (Python)

Fitur:
- Downsampling (dengan/ tanpa anti-aliasing)
- Upsampling (nearest / bilinear / bicubic)
- Aliasing demo (downsample tanpa anti-alias lalu up ke ukuran awal)
- Sharpen (unsharp mask)
- Contrast (+ brightness)

## Cara jalanin (Windows / PowerShell)
```bash
cd dsp_web_py
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Buka:
- http://127.0.0.1:5000
