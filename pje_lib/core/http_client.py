"""
Cliente HTTP base para comunicacao com o PJE.
"""

import requests
from typing import Dict, Optional

from ..config import API_BASE, DEFAULT_HEADERS, DEFAULT_TIMEOUT
from ..models import Usuario


class PJEHttpClient:
    """Cliente HTTP configurado para o PJE."""
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.usuario: Optional[Usuario] = None
    
    def get_api_headers(self) -> Dict[str, str]:
        """Headers para API REST do PJE."""
        headers = {
            "Content-Type": "application/json",
            "X-pje-legacy-app": "pje-tjba-1g",
            "Origin": "https://frontend.cloud.pje.jus.br",
            "Referer": "https://frontend.cloud.pje.jus.br/",
        }
        
        cookies_str = "; ".join([f"{c.name}={c.value}" for c in self.session.cookies])
        if cookies_str:
            headers["X-pje-cookies"] = cookies_str
        
        if self.usuario and self.usuario.id_usuario_localizacao:
            headers["X-pje-usuario-localizacao"] = str(self.usuario.id_usuario_localizacao)
        
        return headers
    
    def get(self, url: str, params: Optional[Dict] = None, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.get(url, params=params, **kwargs)
    
    def post(self, url: str, data: Optional[Dict] = None, 
             json: Optional[Dict] = None, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self.session.post(url, data=data, json=json, **kwargs)
    
    def api_get(self, endpoint: str, params: Optional[Dict] = None) -> requests.Response:
        """GET request para API REST com headers corretos."""
        headers = self.get_api_headers()
        return self.get(f"{API_BASE}/{endpoint}", params=params, headers=headers)
    
    def api_post(self, endpoint: str, json_data: Optional[Dict] = None) -> requests.Response:
        """POST request para API REST com headers corretos."""
        headers = self.get_api_headers()
        return self.post(f"{API_BASE}/{endpoint}", json=json_data, headers=headers)
    
    def close(self):
        self.session.close()
