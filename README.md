# CoffeeCare AI

CoffeeCare is an academic prototype that uses photos of coffee leaves and fruit to provide farmers with preliminary guidance. [Open CoffeeCare](https://coffeecare-ai.streamlit.app/)

Choose **Farmer** or **Administrator** at sign-in. Farmers can take or upload a photo, save an observation with consent, and read its review. Administrators can review private photos, record a classification, or request another photo. Supabase Auth verifies the account role and row-level policies enforce access to observations, reviews, and files. Public registration creates Farmer accounts.

Streamlit validates each image and calls FastAPI when configured. The API checks the Supabase session and runs the calibrated MobileNetV3-Small checkpoint in PyTorch on CPU. PostgreSQL stores observations and reviews. Supabase Storage holds photos in a private bucket.

## Local setup

1. Clone the repository. Create a virtual environment with Python 3.12.
2. Install the application dependencies with `python -m pip install -r requirements.txt`.
3. Use an existing CoffeeCare Supabase project or run the [bootstrap SQL](supabase/bootstrap.sql) once in a new project. Configure the Supabase Auth Site URL so confirmation links return to the app. Assign `app_metadata.role=admin` through trusted Supabase administration for authorized Administrator accounts.
4. Create `.streamlit/secrets.toml` with the project's `SUPABASE_URL` and `SUPABASE_KEY`. Use a publishable or anon key. Git ignores the secrets file.
5. Run `python -m streamlit run app.py` from the repository root.

## Prediction API

Install `requirements-api.txt`, set the same `SUPABASE_URL` and `SUPABASE_KEY` as environment variables, and run `python -m uvicorn api:app --host 127.0.0.1 --port 8000`. OpenAPI is available at `/docs`. `GET /health` returns the status and model version.

`POST /predict` accepts a JPEG, PNG, or WebP image up to 8 MiB. Send the user's access token as `Authorization: Bearer <token>`. The response includes the label, confidence, probabilities, abstention status, and model version. An abstained result has label `Uncertain` and an empty probabilities object.

```bash
curl --fail-with-body http://127.0.0.1:8000/predict \
  -H "Authorization: Bearer ${COFFEECARE_ACCESS_TOKEN}" \
  -H "Content-Type: image/jpeg" \
  --data-binary @photo.jpg
```

Set `PREDICTION_API_URL = "http://127.0.0.1:8000"` in local Streamlit secrets to use the API. Use its HTTPS URL in production. Streamlit uses the local checkpoint when this setting is absent. The included `render.yaml` describes the production API service. [Production API](https://coffeecare-api.onrender.com/docs)

## Tests and repository layout

Install both dependency sets and run `python -m unittest discover -s tests -v`. Set `COFFEECARE_VALIDATION_ZIP` to the audited CoffeeCare ZIP to exercise accepted and uncertain predictions on real photos. The tests use simulated Supabase authentication.

| Path | Purpose |
| --- | --- |
| `app.py`, `api.py` | Streamlit and FastAPI entry points |
| `coffeecare/` | Authentication UI, image validation, inference, and review workflow |
| `model/` | Calibrated PyTorch checkpoint |
| `supabase/` | Database and private storage policies for new installations |
| `tests/` | Authentication and API tests |
| `docs/` | Demonstration guide and evaluation evidence |

## Model results

Model A uses MobileNetV3-Small with Focal Loss. It classifies eight leaf and fruit conditions. The dataset combines BRACOL, an audited Project-AgML subset, and fruit images. Training used balanced batches after grouping related images and reserving separate validation, calibration, and test sets.

| Configuration | Validation accuracy | Validation macro F1 |
| --- | ---: | ---: |
| Reinforced control | 88.12% | 83.16% |
| **Model A, Focal Loss** | **91.09%** | 84.58% |
| Model B, 512-unit classifier | 90.10% | **85.52%** |

Model A classified 174 of 199 held-out photos correctly (87.44% accuracy, 79.32% macro F1). With its calibrated threshold of 61.03%, it returned a class for 180 photos and correctly classified 163 of those (90.56% accuracy at 90.45% coverage). The small Cercospora sample and the lack of an independent labeled Puerto Rico field set limit how broadly these results apply.

[Demonstration guide and evaluation figures](docs/demo.md) · [Training notebook](https://colab.research.google.com/drive/1Sz5M7k-PVridMZEGIxG9eCvAIcwcyUW6) · [Evaluation artifacts](https://drive.google.com/drive/folders/1FLFtL777bV7-6leB2OZk7sWA211-3DSU)
