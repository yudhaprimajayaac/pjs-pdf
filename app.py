from flask import Flask, render_template, request, send_file
import fitz
import io

app = Flask(__name__)

def mm_to_pt(mm):
    return mm * 72 / 25.4

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/convert", methods=["POST"])
def convert():
    pdf_file = request.files["pdf"]
    target_w_mm = float(request.form["width"])
    target_h_mm = float(request.form["height"])
    mode = request.form.get("mode", "fit")
    custom_scale = float(request.form.get("custom_scale", 100))

    target_w = mm_to_pt(target_w_mm)
    target_h = mm_to_pt(target_h_mm)

    src = fitz.open(stream=pdf_file.read(), filetype="pdf")
    dst = fitz.open()

    for page_number in range(len(src)):
        src_page = src[page_number]
        src_rect = src_page.rect

        src_w = src_rect.width
        src_h = src_rect.height

        if mode == "fit":
            scale = min(target_w / src_w, target_h / src_h)
        elif mode == "fill":
            scale = max(target_w / src_w, target_h / src_h)
        elif mode == "custom":
            scale = custom_scale / 100
        else:
            scale = min(target_w / src_w, target_h / src_h)

        scaled_w = src_w * scale
        scaled_h = src_h * scale

        offset_x = (target_w - scaled_w) / 2
        offset_y = (target_h - scaled_h) / 2

        new_page = dst.new_page(width=target_w, height=target_h)

        target_rect = fitz.Rect(
            offset_x, offset_y,
            offset_x + scaled_w,
            offset_y + scaled_h
        )

        new_page.show_pdf_page(target_rect, src, page_number)

    output = io.BytesIO()
    dst.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="converted.pdf",
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    app.run(debug=True)
