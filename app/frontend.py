"""生产环境前端静态文件服务。"""

from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class SPAStaticFiles(StaticFiles):
    """为 Vue history 路由提供 index.html 回退。"""

    _NO_FALLBACK_PREFIXES = ("api", "assets")

    def __init__(self, directory: str | Path) -> None:
        self._frontend_directory = Path(directory)
        self._index_file = self._frontend_directory / "index.html"
        super().__init__(directory=str(self._frontend_directory), html=True, check_dir=True)

    async def get_response(self, path: str, scope: Scope) -> Response:
        """返回静态文件；前端客户端路由不存在时回退到入口页面。"""
        normalized_path = path.replace("\\", "/").rstrip("/")
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            no_fallback_prefixes = tuple(f"{prefix}/" for prefix in self._NO_FALLBACK_PREFIXES)
            is_non_client_path = normalized_path in self._NO_FALLBACK_PREFIXES or (
                normalized_path.startswith(no_fallback_prefixes)
            )
            if exc.status_code != 404 or is_non_client_path or not self._index_file.is_file():
                raise
            return FileResponse(self._index_file)
