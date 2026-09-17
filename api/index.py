import os
import traceback
from io import BytesIO

from flask import Flask, request, send_file, jsonify, Response

from pdf_resizer import resize_pdf

app = Flask(__name__)

MAX_CONTENT_LENGTH = 15 * 1024 * 1024  # 15 MB safety cap
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


INDEX_HTML = """<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>PDF Resizer &mdash; Ubah Ukuran &amp; Stretch PDF (mis. Label 100x100)</title>
<style>
  :root {
    --bg: #0f1220;
    --card: #171b2e;
    --border: #2a3050;
    --text: #eef0fb;
    --muted: #9aa1c4;
    --accent: #ff6a3d;
    --accent-dark: #e2531f;
    --ok: #3ddc97;
    --err: #ff5c7c;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: radial-gradient(1200px 600px at 20% -10%, #232a4d 0%, var(--bg) 60%);
    color: var(--text);
    min-height: 100vh;
    padding: 32px 16px 64px;
  }
  .wrap { max-width: 760px; margin: 0 auto; }
  header { text-align: center; margin-bottom: 28px; }
  header h1 { font-size: 1.7rem; margin: 0 0 8px; letter-spacing: -0.02em; }
  header p { color: var(--muted); margin: 0; font-size: 0.95rem; }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.25);
  }
  .dropzone {
    border: 2px dashed var(--border);
    border-radius: 12px;
    padding: 28px 16px;
    text-align: center;
    cursor: pointer;
    transition: border-color .15s, background .15s;
    color: var(--muted);
  }
  .dropzone.dragover, .dropzone:hover { border-color: var(--accent); background: rgba(255,106,61,0.06); }
  .dropzone strong { color: var(--text); }
  #fileInfo { margin-top: 10px; font-size: 0.9rem; color: var(--ok); display: none; }
  input[type=file] { display: none; }

  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 20px; }
  .full { grid-column: 1 / -1; }
  label { display: block; font-size: 0.82rem; color: var(--muted); margin-bottom: 6px; }
  input[type=number], select {
    width: 100%;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: #10142400;
    background-color: #0f1329;
    color: var(--text);
    font-size: 0.95rem;
  }
  input[type=number]:focus, select:focus { outline: none; border-color: var(--accent); }

  .mode-toggle { display: flex; gap: 8px; }
  .mode-toggle button {
    flex: 1;
    padding: 10px 8px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: #0f1329;
    color: var(--muted);
    cursor: pointer;
    font-size: 0.88rem;
    transition: all .15s;
  }
  .mode-toggle button.active { border-color: var(--accent); color: var(--text); background: rgba(255,106,61,0.12); }

  .presets { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
  .presets button {
    padding: 6px 12px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--muted);
    font-size: 0.8rem;
    cursor: pointer;
  }
  .presets button:hover { border-color: var(--accent); color: var(--text); }

  .checkbox-row { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
  .checkbox-row input { width: 16px; height: 16px; }
  .checkbox-row span { font-size: 0.85rem; color: var(--muted); }

  .submit-btn {
    margin-top: 22px;
    width: 100%;
    padding: 14px;
    border: none;
    border-radius: 10px;
    background: linear-gradient(180deg, var(--accent), var(--accent-dark));
    color: #fff;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: filter .15s, transform .05s;
  }
  .submit-btn:hover { filter: brightness(1.06); }
  .submit-btn:active { transform: translateY(1px); }
  .submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  #status { margin-top: 14px; font-size: 0.88rem; min-height: 1.2em; }
  #status.err { color: var(--err); }
  #status.ok { color: var(--ok); }

  footer { text-align: center; color: var(--muted); font-size: 0.78rem; margin-top: 28px; }
  footer a { color: var(--muted); }
  @media (max-width: 560px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>📐 PDF Resizer &amp; Stretch</h1>
    <p>Ubah ukuran halaman PDF (mis. label pengiriman) ke ukuran custom seperti 100&times;100&nbsp;mm, dengan opsi stretch atau fit + margin.</p>
  </header>

  <form id="form" class="card">
    <div class="dropzone" id="dropzone">
      <div>📄 Klik atau seret file <strong>PDF</strong> ke sini</div>
      <div id="fileInfo"></div>
      <input type="file" id="fileInput" name="file" accept="application/pdf" />
    </div>

    <div class="grid">
      <div>
        <label for="width">Lebar target (mm)</label>
        <input type="number" id="width" step="0.1" min="1" value="100" />
      </div>
      <div>
        <label for="height">Tinggi target (mm)</label>
        <input type="number" id="height" step="0.1" min="1" value="100" />
      </div>
      <div class="full">
        <div class="presets">
          <button type="button" data-w="100" data-h="100">100&times;100 mm</button>
          <button type="button" data-w="100" data-h="150">100&times;150 mm</button>
          <button type="button" data-w="10" data-h="10">10&times;10 cm</button>
          <button type="button" data-w="4" data-h="6" data-unit="in">4&times;6 in</button>
          <button type="button" data-w="210" data-h="297">A4</button>
        </div>
      </div>

      <div class="full">
        <label>Mode penyesuaian</label>
        <div class="mode-toggle">
          <button type="button" data-mode="stretch" class="active">Stretch (isi penuh)</button>
          <button type="button" data-mode="fit">Fit (jaga rasio + margin)</button>
        </div>
      </div>

      <div>
        <label for="margin">Margin (mm)</label>
        <input type="number" id="margin" step="0.1" min="0" value="0" />
      </div>
      <div>
        <label for="dpi">&nbsp;</label>
        <div class="checkbox-row" style="margin-top:10px;">
          <input type="checkbox" id="autocrop" checked />
          <span>Auto-crop area kosong sebelum resize</span>
        </div>
      </div>
    </div>

    <button type="submit" class="submit-btn" id="submitBtn">Convert &amp; Download PDF</button>
    <div id="status"></div>
  </form>

  <footer>
    Diproses langsung di server (Python + PyMuPDF) &middot; File tidak disimpan permanen.
  </footer>
</div>

<script>
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('fileInfo');
const form = document.getElementById('form');
const statusEl = document.getElementById('status');
const submitBtn = document.getElementById('submitBtn');
let mode = 'stretch';

dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  if (e.dataTransfer.files.length) {
    fileInput.files = e.dataTransfer.files;
    updateFileInfo();
  }
});
fileInput.addEventListener('change', updateFileInfo);

function updateFileInfo() {
  if (fileInput.files.length) {
    const f = fileInput.files[0];
    fileInfo.style.display = 'block';
    fileInfo.textContent = `✓ ${f.name} (${(f.size/1024).toFixed(0)} KB)`;
  }
}

document.querySelectorAll('.presets button').forEach(btn => {
  btn.addEventListener('click', () => {
    let w = parseFloat(btn.dataset.w);
    let h = parseFloat(btn.dataset.h);
    if (btn.dataset.unit === 'in') { w *= 25.4; h *= 25.4; }
    document.getElementById('width').value = w;
    document.getElementById('height').value = h;
  });
});

document.querySelectorAll('.mode-toggle button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.mode-toggle button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    mode = btn.dataset.mode;
  });
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  statusEl.className = '';
  statusEl.textContent = '';

  if (!fileInput.files.length) {
    statusEl.className = 'err';
    statusEl.textContent = 'Pilih file PDF terlebih dahulu.';
    return;
  }

  const fd = new FormData();
  fd.append('file', fileInput.files[0]);
  fd.append('width_mm', document.getElementById('width').value);
  fd.append('height_mm', document.getElementById('height').value);
  fd.append('margin_mm', document.getElementById('margin').value);
  fd.append('mode', mode);
  fd.append('auto_crop', document.getElementById('autocrop').checked ? '1' : '0');

  submitBtn.disabled = true;
  submitBtn.textContent = 'Memproses...';
  statusEl.textContent = 'Mengunggah dan memproses PDF...';

  try {
    const res = await fetch('/api/convert', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({error: 'Terjadi kesalahan.'}));
      throw new Error(err.error || 'Gagal memproses PDF.');
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const origName = fileInput.files[0].name.replace(/\\.pdf$/i, '');
    a.href = url;
    a.download = `${origName}_resized.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    statusEl.className = 'ok';
    statusEl.textContent = '✓ Selesai! PDF hasil sudah terunduh.';
  } catch (err) {
    statusEl.className = 'err';
    statusEl.textContent = err.message;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Convert & Download PDF';
  }
});
</script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
@app.route("/api", methods=["GET"])
def index():
    return Response(INDEX_HTML, mimetype="text/html")


@app.route("/api/convert", methods=["POST"])
def convert():
    try:
        if "file" not in request.files:
            return jsonify({"error": "Tidak ada file yang diunggah."}), 400

        f = request.files["file"]
        if f.filename == "":
            return jsonify({"error": "Nama file kosong."}), 400
        if not f.filename.lower().endswith(".pdf"):
            return jsonify({"error": "File harus berformat .pdf"}), 400

        data = f.read()
        if not data:
            return jsonify({"error": "File kosong atau gagal dibaca."}), 400

        def get_float(name, default):
            val = request.form.get(name, default)
            try:
                return float(val)
            except (TypeError, ValueError):
                return float(default)

        width_mm = get_float("width_mm", 100)
        height_mm = get_float("height_mm", 100)
        margin_mm = get_float("margin_mm", 0)
        mode = request.form.get("mode", "stretch")
        auto_crop = request.form.get("auto_crop", "1") == "1"

        result = resize_pdf(
            data,
            target_width_mm=width_mm,
            target_height_mm=height_mm,
            margin_mm=margin_mm,
            mode=mode,
            auto_crop=auto_crop,
        )

        base_name = os.path.splitext(f.filename)[0]
        out_name = f"{base_name}_resized.pdf"

        return send_file(
            BytesIO(result),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=out_name,
        )

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Terjadi kesalahan saat memproses PDF."}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# Local dev entrypoint: `python api/index.py`
if __name__ == "__main__":
    app.run(debug=True, port=5000)
