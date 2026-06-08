FROM python:3.11-slim

WORKDIR /app

RUN apt-get update -qq && apt-get install -y -qq \
    git curl gnupg \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh && ln -sf /app/bin/trivy /usr/local/bin/trivy

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir semgrep bandit truffleHog lizard radon

COPY . .

RUN chmod +x run_audit.sh deploy.sh test_compliance.sh

EXPOSE 5000 5001 5002 5003

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app.dashboard.app:app"]
