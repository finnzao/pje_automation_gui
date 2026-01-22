"""
Servico de gerenciamento de etiquetas.
"""

from typing import List, Optional

from ..core import PJEHttpClient
from ..models import Etiqueta, Processo
from ..utils import delay, get_logger


class TagService:
    """Servico para etiquetas e processos por etiqueta."""
    
    def __init__(self, http_client: PJEHttpClient):
        self.client = http_client
        self.logger = get_logger()
    
    def buscar_etiquetas(self, busca: str = "", page: int = 0, max_results: int = 30) -> List[Etiqueta]:
        """Busca etiquetas pelo nome."""
        try:
            self.logger.debug(f"Buscando etiquetas: '{busca}'")
            resp = self.client.api_post(
                "painelUsuario/etiquetas",
                {"page": page, "maxResults": max_results, "tagsString": busca}
            )
            
            self.logger.debug(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                self.logger.debug(f"Resposta: {data}")
                
                etiquetas = [Etiqueta.from_dict(e) for e in data.get("entities", [])]
                self.logger.info(f"Encontradas {len(etiquetas)} etiquetas")
                return etiquetas
            else:
                self.logger.error(f"Erro ao buscar etiquetas: {resp.status_code}")
                self.logger.debug(f"Resposta: {resp.text[:500]}")
        except Exception as e:
            self.logger.error(f"Erro ao buscar etiquetas: {e}")
        return []
    
    def buscar_etiqueta_por_nome(self, nome: str) -> Optional[Etiqueta]:
        """Busca etiqueta especifica pelo nome."""
        etiquetas = self.buscar_etiquetas(nome)
        for et in etiquetas:
            if et.nome.lower() == nome.lower():
                return et
        return etiquetas[0] if etiquetas else None
    
    def listar_processos_etiqueta(self, id_etiqueta: int, limit: int = 100) -> List[Processo]:
        """Lista processos de uma etiqueta."""
        try:
            resp_total = self.client.api_get(f"painelUsuario/etiquetas/{id_etiqueta}/processos/total")
            total = int(resp_total.text) if resp_total.status_code == 200 else 0
            self.logger.info(f"Total de processos: {total}")
            
            delay()
            
            resp = self.client.api_get(
                f"painelUsuario/etiquetas/{id_etiqueta}/processos",
                params={"limit": limit}
            )
            
            self.logger.debug(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                processos = [Processo.from_dict(p) for p in resp.json()]
                self.logger.info(f"Retornados {len(processos)} processos")
                return processos
            else:
                self.logger.error(f"Erro ao listar processos: {resp.status_code}")
                self.logger.debug(f"Resposta: {resp.text[:500]}")
        except Exception as e:
            self.logger.error(f"Erro ao listar processos: {e}")
        return []