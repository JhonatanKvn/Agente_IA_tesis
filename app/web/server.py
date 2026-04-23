import json
import os
import threading
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for
from PIL import UnidentifiedImageError

from app.db.repository import (
    init_db,
    list_evaluations,
    list_student_alerts,
    list_student_summary,
    save_evaluation,
)
from grader import evaluate_with_ocr_space
from app.services.image_processing import prepare_image_for_ocr


BASE_DIR = Path(__file__).resolve().parent

load_dotenv()
init_db()

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")


def _to_result_dict(result: Any) -> Dict[str, Any]:
    return {
        "score": result.score,
        "max_score": result.max_score,
        "feedback": result.feedback,
        "code_transcription": result.code_transcription,
        "strengths": result.strengths or [],
        "improvements": result.improvements or [],
        "rubric_breakdown": result.rubric_breakdown or [],
    }


@app.get("/")
def index():
    filter_name = request.args.get("filter_name", "").strip()
    history = list_evaluations(student_name=filter_name, limit=50)
    summary = list_student_summary(student_name=filter_name, limit=50)
    alerts = list_student_alerts(student_name=filter_name, limit=50)
    return render_template(
        "index.html",
        max_score=5.0,
        student_name="",
        student_code="",
        activity_name="Actividad 1",
        semester="2026-1",
        rubric_text=(
            "Criterio: Logica del algoritmo (40%)\n"
            "Criterio: Sintaxis y estructura en Python (30%)\n"
            "Criterio: Buenas practicas y legibilidad (30%)\n"
        ),
        result=None,
        eval_id=None,
        error=None,
        history=history,
        summary=summary,
        alerts=alerts,
        total_evaluations=len(history),
        total_students=len(summary),
        filter_name=filter_name,
    )


@app.post("/evaluate")
def evaluate():
    student_name = request.form.get("student_name", "").strip()
    student_code = request.form.get("student_code", "").strip()
    activity_name = request.form.get("activity_name", "").strip()
    semester = request.form.get("semester", "").strip()
    rubric_text = request.form.get("rubric_text", "").strip()
    filter_name = request.form.get("filter_name", "").strip()

    try:
        max_score = float(request.form.get("max_score", "5"))
    except ValueError:
        max_score = 5.0

    uploaded = request.files.get("code_image")
    error: Optional[str] = None
    result = None
    eval_id = None

    if not student_name:
        error = "Debes escribir el nombre del estudiante."
    elif not activity_name:
        error = "Debes escribir la actividad evaluada."
    elif not semester:
        error = "Debes escribir el semestre (ej: 2026-1)."
    elif not rubric_text:
        error = "Debes escribir las rubricas de evaluacion."
    elif not uploaded or not uploaded.filename:
        error = "Debes subir una imagen del codigo."

    if not error:
        try:
            api_key = os.getenv("OCRSPACE_API_KEY", "helloworld").strip()
            processed_bytes, processed_name = prepare_image_for_ocr(uploaded.read(), uploaded.filename)
            raw_result = evaluate_with_ocr_space(
                api_key=api_key,
                rubric_text=rubric_text,
                image_bytes=processed_bytes,
                filename=processed_name,
                max_score=max_score,
            )
            result = _to_result_dict(raw_result)
            eval_id = save_evaluation(
                {
                    "student_name": student_name,
                    "student_code": student_code,
                    "activity_name": activity_name,
                    "semester": semester,
                    "mode": "ocrspace",
                    "score": result["score"],
                    "max_score": result["max_score"],
                    "feedback": result["feedback"],
                    "code_transcription": result["code_transcription"],
                    "strengths_json": json.dumps(result["strengths"], ensure_ascii=False),
                    "improvements_json": json.dumps(result["improvements"], ensure_ascii=False),
                    "rubric_breakdown_json": json.dumps(result["rubric_breakdown"], ensure_ascii=False),
                    "rubric_text": rubric_text,
                    "image_filename": processed_name,
                }
            )
        except UnidentifiedImageError:
            error = "El archivo no es una imagen valida. Sube JPG, JPEG, PNG o WEBP."
        except Exception as exc:
            error = f"No se pudo evaluar la entrega: {exc}"

    history = list_evaluations(student_name=filter_name, limit=50)
    summary = list_student_summary(student_name=filter_name, limit=50)
    alerts = list_student_alerts(student_name=filter_name, limit=50)
    return render_template(
        "index.html",
        max_score=max_score,
        student_name=student_name,
        student_code=student_code,
        activity_name=activity_name,
        semester=semester,
        rubric_text=rubric_text,
        result=result,
        eval_id=eval_id,
        error=error,
        history=history,
        summary=summary,
        alerts=alerts,
        total_evaluations=len(history),
        total_students=len(summary),
        filter_name=filter_name,
    )


@app.get("/new")
def new_evaluation():
    return redirect(url_for("index"))


def run() -> None:
    debug_mode = True
    auto_open = os.getenv("AUTO_OPEN_BROWSER", "1").strip() == "1"
    if debug_mode:
        should_open_now = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    else:
        should_open_now = True
    if auto_open and should_open_now:
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=debug_mode)

