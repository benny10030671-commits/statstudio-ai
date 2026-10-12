from pathlib import Path
from fastapi import FastAPI, UploadFile, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from .engine import METHODS
from .store import Store, MAX_BYTES
from . import __version__


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_id: str
    method: str
    options: dict


def create_app(root=None):
    store = Store(root)
    from .research import ResearchWorkspace
    research = ResearchWorkspace(root)
    app = FastAPI(title='StatStudio AI', docs_url=None, redoc_url=None)
    app.state.store = store

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        host = request.headers.get('host', '').split(':')[0]
        if host not in ('127.0.0.1', 'localhost'):
            return JSONResponse({'detail': '僅接受本機連線。'}, status_code=403)
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail': '不接受其他網站跨來源存取本機資料。'}, status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': '不接受跨網站存取。'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, error):
        return JSONResponse({'detail': str(error)}, status_code=400)

    @app.get('/api/methods')
    def methods():
        return {'methods': METHODS}

    @app.get('/api/health')
    def health():
        return {'app': 'statstudio-ai', 'version': __version__}

    @app.get('/api/datasets')
    def datasets():
        return {'datasets': store.list_datasets()}

    @app.get('/api/datasets/{identifier}')
    def dataset(identifier: str):
        return store.dataset(identifier)

    @app.post('/api/datasets/upload')
    async def upload(file: UploadFile):
        content = await file.read(MAX_BYTES + 1)
        await file.close()
        return store.import_bytes(file.filename or 'data.csv', content)

    @app.post('/api/demo')
    def demo():
        return store.demo()

    @app.post('/api/analyze')
    def analyze(request: AnalysisRequest):
        return store.analyze(request.dataset_id, request.method, request.options)

    @app.get('/api/results')
    def results():
        return {'results': store.list_results()}

    @app.get('/api/results/{identifier}')
    def result(identifier: str):
        return store.result(identifier)

    @app.get('/api/results/{identifier}/report')
    def report(identifier: str):
        return FileResponse(store.result_file(identifier, 'report.html'), media_type='text/html', filename=f'statstudio-{identifier[:8]}.html')

    @app.get('/api/results/{identifier}/json')
    def json_result(identifier: str):
        return FileResponse(store.result_file(identifier, 'result.json'), media_type='application/json', filename=f'statstudio-{identifier[:8]}.json')

    @app.get('/research')
    def research_page():
        return FileResponse(Path(__file__).parent / 'static' / 'research.html', media_type='text/html')

    @app.get('/api/research')
    def research_overview():
        return research.overview()

    @app.get('/api/research/plans/{identifier}/{kind}')
    def research_template(identifier: str, kind: str):
        names = {'template': 'data-template.csv', 'dictionary': 'data-dictionary.csv', 'json': 'plan.json'}
        if kind not in names:
            raise ValueError('Unknown plan artifact.')
        path = research.folder('plans', identifier) / names[kind]
        if not path.is_file():
            raise ValueError('找不到計畫。')
        return FileResponse(path, filename=path.name)

    @app.get('/api/research/runs/{identifier}/{kind}')
    def research_artifact(identifier: str, kind: str, interpretation: str | None = None):
        names = {'report': 'report.html', 'syntax': 'commands.sps', 'viewer': 'native.spv', 'json': 'result.json'}
        if kind not in names:
            raise ValueError('Unknown research artifact.')
        folder = research.folder('runs', identifier)
        if interpretation:
            if kind != 'report':
                raise ValueError('Interpretation is only supported for the report artifact.')
            folder = folder / 'interpretations' / Store.valid_id(interpretation)
        path = folder / names[kind]
        if not path.is_file():
            raise ValueError('找不到研究結果。')
        if kind == 'report':
            return FileResponse(path, media_type='text/html')
        return FileResponse(path, filename=path.name)

    app.mount('/static', StaticFiles(directory=Path(__file__).parent / 'static'), name='static')
    app.mount('/', StaticFiles(directory=Path(__file__).parent / 'static', html=True), name='ui')
    return app
