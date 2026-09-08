"""
llminator.ui.server
────────────────────────────────────────────────────────────────────────────────
Flask backend that bridges the HTML frontend to `llminator scan --onnx`.

Entry points
  • python -m llminator.ui.server          (module run)
  • llminator-ui                           (installed console script)
  • llminator-ui --port 8080               (custom port)
  • llminator-ui --host 0.0.0.0            (network-accessible)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

# ── Optional import guard (flask may not be installed in core env) ─────────────
try:
    from flask import Flask, Response, jsonify, request, send_from_directory
except ImportError:
    def main() -> None:  # type: ignore[misc]
        print(
            "error: Flask is not installed in this environment.\n"
            "Re-run the installer with the --ui flag:\n\n"
            "  ./install.sh --ui\n",
            file=sys.stderr,
        )
        sys.exit(1)

    if __name__ == "__main__":
        main()
    # Stop module-level execution so the rest of the file doesn't error out.
    raise SystemExit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────
_THIS_DIR   = Path(__file__).parent
STATIC_DIR  = _THIS_DIR / "static"

# llminator binary: prefer the one next to the current Python interpreter so
# the UI always runs scans inside the same virtual environment.
_VENV_BIN       = Path(sys.executable).parent
_DEFAULT_BIN    = _VENV_BIN / "llminator"
LLMINATOR_BIN   = Path(os.environ.get("LLMINATOR_BIN", str(_DEFAULT_BIN)))

# Default reports directory: <cwd>/reports  (mirrors CLI behaviour)
DEFAULT_REPORTS = Path.cwd() / "reports"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")

# ── In-memory job store ────────────────────────────────────────────────────────
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ── Internal helpers ───────────────────────────────────────────────────────────

def _run_scan(job_id: str, onnx_path: str, deep: bool, output_path: str) -> None:
    """Execute llminator in a background thread; collect stdout lines + JSON report."""
    cmd: list[str] = [str(LLMINATOR_BIN), "scan", "--onnx", onnx_path, "--output", output_path]
    if deep:
        cmd.append("--deep")

    with _jobs_lock:
        _jobs[job_id]["cmd"] = " ".join(cmd)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:  # type: ignore[union-attr]
            with _jobs_lock:
                _jobs[job_id]["lines"].append(line.rstrip())
        proc.wait()

        report: dict = {}
        try:
            report = json.loads(Path(output_path).read_text())
        except Exception:
            pass

        with _jobs_lock:
            _jobs[job_id]["status"]      = "done" if proc.returncode == 0 else "error"
            _jobs[job_id]["returncode"]  = proc.returncode
            _jobs[job_id]["report"]      = report
            _jobs[job_id]["output_path"] = output_path

    except Exception as exc:
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["lines"].append(f"[server error] {exc}")


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index() -> Response:
    return send_from_directory(STATIC_DIR, "index.html")  # type: ignore[return-value]


@app.route("/api/scan", methods=["POST"])
def start_scan() -> Response:
    """Accept an ONNX file upload or a local path, start a background scan job."""
    deep = request.form.get("deep", "false").lower() == "true"

    # ── Uploaded file ──────────────────────────────────────────────────────────
    if "file" in request.files:
        f = request.files["file"]
        if not (f.filename or "").endswith(".onnx"):
            return jsonify({"error": "Only .onnx files are accepted."}), 400  # type: ignore[return-value]
        tmp_dir   = Path(tempfile.mkdtemp(prefix="llminator_ui_"))
        onnx_path = str(tmp_dir / (f.filename or "model.onnx"))
        f.save(onnx_path)

    # ── Local path ─────────────────────────────────────────────────────────────
    elif request.form.get("path"):
        onnx_path = request.form["path"]
        if not Path(onnx_path).exists():
            return jsonify({"error": f"Path not found: {onnx_path}"}), 400  # type: ignore[return-value]
        if not onnx_path.endswith(".onnx"):
            return jsonify({"error": "Only .onnx files are accepted."}), 400  # type: ignore[return-value]

    else:
        return jsonify({"error": "Provide a file upload or a local 'path' field."}), 400  # type: ignore[return-value]

    job_id      = str(uuid.uuid4())
    ts          = time.strftime("%Y%m%d-%H%M%S")
    model_stem  = Path(onnx_path).stem
    reports_dir = app.config.get("REPORTS_DIR", DEFAULT_REPORTS)
    Path(reports_dir).mkdir(parents=True, exist_ok=True)
    output_path = str(Path(reports_dir) / f"ui-{model_stem}-{ts}.json")

    with _jobs_lock:
        _jobs[job_id] = {
            "status":      "running",
            "lines":       [],
            "report":      {},
            "onnx_path":   onnx_path,
            "output_path": output_path,
            "returncode":  None,
        }

    t = threading.Thread(
        target=_run_scan,
        args=(job_id, onnx_path, deep, output_path),
        daemon=True,
    )
    t.start()
    return jsonify({"job_id": job_id})  # type: ignore[return-value]


@app.route("/api/jobs/<job_id>/stream")
def stream_job(job_id: str) -> Response:
    """Server-Sent Events: stream terminal lines as the scan runs."""
    def generate():
        sent = 0
        while True:
            with _jobs_lock:
                job = _jobs.get(job_id)
            if job is None:
                yield 'data: {"error":"unknown job"}\n\n'
                return
            lines = job["lines"]
            while sent < len(lines):
                yield f"data: {json.dumps({'line': lines[sent]})}\n\n"
                sent += 1
            if job["status"] in ("done", "error"):
                yield f"data: {json.dumps({'done': True, 'status': job['status']})}\n\n"
                return
            time.sleep(0.15)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/jobs/<job_id>")
def get_job(job_id: str) -> Response:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "unknown job"}), 404  # type: ignore[return-value]
    return jsonify(job)  # type: ignore[return-value]


@app.route("/api/reports")
def list_reports() -> Response:
    """Return the 20 most recent ONNX JSON reports from the configured reports dir."""
    reports_dir = Path(app.config.get("REPORTS_DIR", DEFAULT_REPORTS))
    reports = []
    if reports_dir.exists():
        for p in sorted(reports_dir.glob("*.json"), reverse=True)[:20]:
            try:
                data = json.loads(p.read_text())
                if data.get("target", {}).get("format") == "onnx":
                    reports.append({"filename": p.name, "data": data})
            except Exception:
                pass
    return jsonify(reports)  # type: ignore[return-value]


@app.route("/api/reports/<filename>")
def get_report(filename: str) -> Response:
    reports_dir = Path(app.config.get("REPORTS_DIR", DEFAULT_REPORTS))
    p = reports_dir / filename
    if not p.exists():
        return jsonify({"error": "not found"}), 404  # type: ignore[return-value]
    return jsonify(json.loads(p.read_text()))  # type: ignore[return-value]


# ── CLI entry point ────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    """Console-script entry point: llminator-ui."""
    parser = argparse.ArgumentParser(
        prog="llminator-ui",
        description="LLMinator ONNX Web UI — starts the local web server.",
    )
    parser.add_argument("--host",    default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port",    default=7474, type=int, help="Bind port (default: 7474)")
    parser.add_argument("--reports", default=str(DEFAULT_REPORTS),
                        help="Directory for scan reports (default: ./reports)")
    args = parser.parse_args(argv)

    reports_dir = Path(args.reports).expanduser().resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    app.config["REPORTS_DIR"] = str(reports_dir)

    print(f"  llminator binary : {LLMINATOR_BIN}")
    print(f"  reports dir      : {reports_dir}")
    print(f"  UI               : http://{args.host}:{args.port}")
    print("  Press Ctrl+C to stop.\n")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
