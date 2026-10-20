"""빌드된 React 화면과 API를 같은 주소에서 제공합니다."""
import os
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

def install(app):
    value = os.environ.get('BREAD_STATIC_DIR')
    if not value:
        return
    directory = Path(value).resolve()
    if not (directory / 'index.html').is_file():
        raise RuntimeError('BREAD_STATIC_DIR에 빌드된 index.html이 없습니다.')
    app.mount('/assets', StaticFiles(directory=directory/'assets', check_dir=True), name='web-assets')

    @app.get('/{path:path}', include_in_schema=False)
    def web(path: str):
        if path == 'api' or path.startswith('api/'):
            raise HTTPException(404, 'API를 찾을 수 없습니다.')
        target = (directory / path).resolve()
        if target.is_relative_to(directory) and target.is_file():
            return FileResponse(target)
        # 존재하지 않는 파일과 외부 경로를 SPA HTML로 위장하지 않습니다.
        if not target.is_relative_to(directory) or Path(path).suffix:
            raise HTTPException(404, '파일을 찾을 수 없습니다.')
        return FileResponse(directory/'index.html')
