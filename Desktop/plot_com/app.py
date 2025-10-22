#只有bpxplot

from flask import Flask, render_template, request, send_from_directory, jsonify
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import os
import uuid
import zipfile
import time
import shutil

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ===== Home =====
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# ===== Upload file =====
@app.route("/upload_file", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{file.filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    df = pd.read_excel(filepath)
    columns = list(df.columns)
    return jsonify({"file_id": file_id, "columns": columns, "filename": file.filename})

# ===== Generate plots =====
@app.route("/generate_plot", methods=["POST"])
def generate_plot():
    data = request.json
    file_id = data.get("file_id")
    group_col = data.get("group_col")
    value_col = data.get("value_col")
    l2_col = data.get("l2_col")  # optional
    selected_groups = data.get("selected_groups", [])
    filename = data.get("filename")

    file_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
    df = pd.read_excel(file_path)

    output_subfolder = os.path.join(OUTPUT_FOLDER, file_id)
    shutil.rmtree(output_subfolder, ignore_errors=True)
    os.makedirs(output_subfolder, exist_ok=True)

    images = []
    timestamp = int(time.time() * 1000)

    # ✅ 如果沒有 group_col，整份資料視為一組
    if not group_col:
        group_col = "__ALL__"
        df[group_col] = "All Data"
        
    if selected_groups:
        df = df[df[group_col].isin(selected_groups)]

    if l2_col:
        for group_name, group_data in df.groupby(group_col):
            n_categories = group_data[l2_col].nunique()
            fig_width = max(10, n_categories * 0.5)
            plt.figure(figsize=(fig_width, 6))

            upper_bounds = []
            for cat, subdata in group_data.groupby(l2_col):
                y = subdata[value_col].dropna()
                if len(y) > 0:
                    Q1 = y.quantile(0.25)
                    Q3 = y.quantile(0.75)
                    IQR = Q3 - Q1
                    upper_bounds.append(Q3 + 1.5 * IQR)
            if not upper_bounds:
                continue

            y_max = max(upper_bounds)
            y_min = 0
            y_range = y_max - y_min
            y_max += 0.05 * y_range

            sns.boxplot(data=group_data, x=l2_col, y=value_col, palette="Set3", width=0.6, fliersize=2)

            plt.ylim(y_min, y_max)
            plt.title(f"Group {group_name}", fontsize=14)
            plt.xlabel(l2_col, fontsize=12)
            plt.ylabel(value_col, fontsize=12)
            plt.xticks(rotation=90)
            plt.tight_layout()

            img_name = f"{group_name}_boxplot_{timestamp}.png"
            plt.savefig(os.path.join(output_subfolder, img_name), dpi=300)
            plt.close()
            images.append(img_name)
    else:
        for group_name, group_data in df.groupby(group_col):
            values = group_data[value_col].dropna()
            Q1 = values.quantile(0.25)
            Q3 = values.quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            y_min = max(values.min(), lower)
            y_max = min(values.max(), upper)
            y_range = y_max - y_min
            y_min -= 0.1 * y_range
            y_max += 0.1 * y_range

            plt.figure(figsize=(5,6))
            sns.boxplot(data=group_data, y=value_col, color="lightblue", width=0.3, fliersize=2)

            plt.ylim(y_min, y_max)
            plt.ylabel(value_col, fontsize=12)
            plt.title(f"Group {group_name}", fontsize=14)
            plt.xticks([])
            plt.tight_layout()

            img_name = f"{group_name}_boxplot_{timestamp}.png"
            plt.savefig(os.path.join(output_subfolder, img_name), dpi=300)
            plt.close()
            images.append(img_name)

    # Create ZIP
    zip_name = f"{file_id}_boxplots_{timestamp}.zip"
    zip_path = os.path.join(OUTPUT_FOLDER, zip_name)
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for img in images:
            zf.write(os.path.join(output_subfolder, img), arcname=img)

    return jsonify({"images": images, "file_id": file_id, "zip_name": zip_name})

# ===== Serve single images =====
@app.route("/outputs/<file_id>/<filename>")
def output_file(file_id, filename):
    folder_path = os.path.join(OUTPUT_FOLDER, file_id)
    safe_name = os.path.basename(filename)
    return send_from_directory(folder_path, safe_name, as_attachment=True)

# ===== Download ZIP =====
@app.route("/download_zip/<zip_name>")
def download_zip(zip_name):
    safe_name = os.path.basename(zip_name)
    zip_path = os.path.join(OUTPUT_FOLDER, safe_name)
    if not os.path.exists(zip_path):
        return "File not found", 404
    return send_from_directory(OUTPUT_FOLDER, safe_name, as_attachment=True)


if __name__ == "__main__":
    app.run(host="10.100.8.143", port=5000, debug=True , use_reloader=False)
