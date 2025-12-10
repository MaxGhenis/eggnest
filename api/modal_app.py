import modal

app = modal.App("eggnest-api")

# Create image with dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "numpy>=1.24.0",
        "numpy-financial>=1.0.0",
        "pandas>=2.0.0",
        "scipy>=1.10.0",
        "httpx>=0.26.0",
        "policyengine-us>=1.0.0",
    )
    .add_local_dir("eggnest", "/root/eggnest")
    .add_local_file("main.py", "/root/main.py")
)


@app.function(
    image=image,
    allow_concurrent_inputs=100,
    container_idle_timeout=300,
)
@modal.asgi_app()
def fastapi_app():
    import sys
    sys.path.insert(0, "/root")
    from main import app
    return app
