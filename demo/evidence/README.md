# Verification Evidence

`verification.txt` is a local printed verification record generated from the same commands used by CI:

- `scripts/setup.ps1`: dependency installation, frontend build, deterministic demo import/evaluation, and backend tests.
- `python -m pytest backend/tests -q`: API, deterministic metric, queue lease, and calibration statistic tests.
- `npm --prefix frontend run build`: production frontend build.
- `demo/run_calibration.py`: real provider diagnostic calibration when `backend/.env` contains a provider key.

The deterministic path is credential-free. The calibration report records provider, model, request count, MAE, within-sample repeat variance, and failed samples. The bundled labels are illustrative and explicitly not human-reviewed.
