"""Neo4j 연결 관리 모듈.

선택적 의존성: neo4j 패키지가 없으면 인메모리 그래프로 폴백.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# Neo4j 드라이버 (선택적 의존성)
_neo4j_available = False
_AsyncGraphDatabase = None
_GraphDatabase = None

try:
    from neo4j import AsyncGraphDatabase, GraphDatabase
    _neo4j_available = True
    _AsyncGraphDatabase = AsyncGraphDatabase
    _GraphDatabase = GraphDatabase
except ImportError:
    logger.info("neo4j 패키지 미설치 - 인메모리 그래프로 폴백")

# 인메모리 그래프 폴백
_inmemory_available = False
try:
    from .inmemory import InMemoryGraph, get_inmemory_graph, is_inmemory_available
    _inmemory_available = True
except ImportError:
    logger.info("인메모리 그래프 모듈 로드 실패")


@dataclass
class Neo4jConfig:
    """Neo4j 연결 설정."""
    
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    max_pool_size: int = 50
    acquisition_timeout: float = 60.0
    query_timeout: int = 30


def _load_neo4j_config() -> Neo4jConfig:
    """설정 파일에서 Neo4j 설정 로드."""
    config_path = Path("configs/neo4j.yaml")
    
    if not config_path.exists():
        logger.warning(f"Neo4j 설정 파일 없음: {config_path}")
        return Neo4jConfig()
    
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    
    neo4j_cfg = raw.get("neo4j", {})
    pool_cfg = neo4j_cfg.get("connection_pool", {})
    query_cfg = neo4j_cfg.get("query", {})
    
    # 환경변수 오버라이드
    uri = os.environ.get("NEO4J_URI", neo4j_cfg.get("uri", "bolt://localhost:7687"))
    user = os.environ.get("NEO4J_USER", neo4j_cfg.get("user", "neo4j"))
    password = os.environ.get("NEO4J_PASSWORD", neo4j_cfg.get("password", ""))
    database = os.environ.get("NEO4J_DATABASE", neo4j_cfg.get("database", "neo4j"))
    
    return Neo4jConfig(
        uri=uri,
        user=user,
        password=password,
        database=database,
        max_pool_size=pool_cfg.get("max_size", 50),
        acquisition_timeout=pool_cfg.get("acquisition_timeout", 60.0),
        query_timeout=query_cfg.get("timeout", 30),
    )


class GraphConnection:
    """Neo4j 연결 관리자.
    
    싱글톤 패턴으로 연결 풀 관리.
    비동기/동기 세션 모두 지원.
    """
    
    _instance: Optional["GraphConnection"] = None
    
    def __init__(self, config: Optional[Neo4jConfig] = None):
        """초기화.
        
        Args:
            config: Neo4j 설정. None이면 설정 파일에서 로드.
        """
        self.config = config or _load_neo4j_config()
        self._driver = None
        self._async_driver = None
        self._connected = False
        
    @classmethod
    def get_instance(cls) -> "GraphConnection":
        """싱글톤 인스턴스 반환."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """인스턴스 리셋 (테스트용)."""
        if cls._instance is not None:
            cls._instance.close()
            cls._instance = None
    
    def is_available(self) -> bool:
        """Neo4j 사용 가능 여부."""
        if not _neo4j_available:
            return False
        if not self.config.password:
            logger.debug("Neo4j 비밀번호 미설정")
            return False
        return True
    
    def connect(self) -> bool:
        """동기 연결 생성."""
        if not self.is_available():
            return False
        
        if self._driver is not None:
            return True
        
        try:
            self._driver = _GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
                max_connection_pool_size=self.config.max_pool_size,
                connection_acquisition_timeout=self.config.acquisition_timeout,
            )
            # 연결 테스트
            self._driver.verify_connectivity()
            self._connected = True
            logger.info(f"Neo4j 연결 성공: {self.config.uri}")
            return True
        except Exception as e:
            logger.error(f"Neo4j 연결 실패: {e}")
            self._driver = None
            return False
    
    async def connect_async(self) -> bool:
        """비동기 연결 생성."""
        if not self.is_available():
            return False
        
        if self._async_driver is not None:
            return True
        
        try:
            self._async_driver = _AsyncGraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
                max_connection_pool_size=self.config.max_pool_size,
                connection_acquisition_timeout=self.config.acquisition_timeout,
            )
            # 연결 테스트
            await self._async_driver.verify_connectivity()
            self._connected = True
            logger.info(f"Neo4j 비동기 연결 성공: {self.config.uri}")
            return True
        except Exception as e:
            logger.error(f"Neo4j 비동기 연결 실패: {e}")
            self._async_driver = None
            return False
    
    def get_session(self, database: Optional[str] = None):
        """동기 세션 반환.
        
        사용 예:
            with connection.get_session() as session:
                result = session.run("MATCH (n) RETURN n LIMIT 10")
        """
        if self._driver is None:
            if not self.connect():
                raise RuntimeError("Neo4j 연결 불가")
        
        return self._driver.session(database=database or self.config.database)
    
    async def get_async_session(self, database: Optional[str] = None):
        """비동기 세션 반환.
        
        사용 예:
            async with await connection.get_async_session() as session:
                result = await session.run("MATCH (n) RETURN n LIMIT 10")
        """
        if self._async_driver is None:
            if not await self.connect_async():
                raise RuntimeError("Neo4j 비동기 연결 불가")
        
        return self._async_driver.session(database=database or self.config.database)
    
    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """동기 쿼리 실행.
        
        Args:
            query: Cypher 쿼리
            parameters: 쿼리 파라미터
            database: 데이터베이스 이름
            
        Returns:
            결과 레코드 리스트
        """
        with self.get_session(database) as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]
    
    async def execute_query_async(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """비동기 쿼리 실행.
        
        Args:
            query: Cypher 쿼리
            parameters: 쿼리 파라미터
            database: 데이터베이스 이름
            
        Returns:
            결과 레코드 리스트
        """
        async with await self.get_async_session(database) as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records
    
    def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Tuple[int, int]:
        """동기 쓰기 쿼리 실행.
        
        Returns:
            (생성된 노드 수, 생성된 관계 수)
        """
        with self.get_session(database) as session:
            result = session.run(query, parameters or {})
            summary = result.consume()
            counters = summary.counters
            return (counters.nodes_created, counters.relationships_created)
    
    async def execute_write_async(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> Tuple[int, int]:
        """비동기 쓰기 쿼리 실행.
        
        Returns:
            (생성된 노드 수, 생성된 관계 수)
        """
        async with await self.get_async_session(database) as session:
            result = await session.run(query, parameters or {})
            summary = await result.consume()
            counters = summary.counters
            return (counters.nodes_created, counters.relationships_created)
    
    def close(self) -> None:
        """연결 종료."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
        if self._async_driver is not None:
            # 비동기 드라이버는 동기적으로 종료
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 이미 실행 중인 루프에서는 태스크로 스케줄
                    asyncio.create_task(self._async_driver.close())
                else:
                    loop.run_until_complete(self._async_driver.close())
            except Exception:
                pass
            self._async_driver = None
        self._connected = False
        logger.info("Neo4j 연결 종료")
    
    def __del__(self):
        """소멸자."""
        self.close()


# 편의 함수
def get_graph_connection() -> GraphConnection:
    """그래프 연결 인스턴스 반환."""
    return GraphConnection.get_instance()


def is_graph_available() -> bool:
    """그래프 DB 사용 가능 여부 (Neo4j 또는 인메모리)."""
    # Neo4j 먼저 체크
    if get_graph_connection().is_available():
        return True
    # 인메모리 폴백
    if _inmemory_available:
        return is_inmemory_available()
    return False


def get_graph_status() -> Dict[str, Any]:
    """그래프 백엔드 상태 조회."""
    neo4j_conn = get_graph_connection()
    
    if neo4j_conn.is_available():
        return {
            "backend": "neo4j",
            "connected": True,
            "uri": neo4j_conn.config.uri,
        }
    
    if _inmemory_available:
        inmem = get_inmemory_graph()
        return inmem.get_status()
    
    return {
        "backend": "none",
        "connected": False,
        "error": "Neo4j 미연결, 인메모리 그래프 미설치",
    }


class Neo4jConnection:
    """Neo4j 연결 래퍼 (UI 호환용).
    
    UI에서 사용하는 is_connected() 메서드 제공.
    """
    
    def __init__(self):
        """초기화."""
        self._conn = get_graph_connection()
    
    def is_connected(self) -> bool:
        """연결 상태."""
        return self._conn.is_available() and self._conn._connected
