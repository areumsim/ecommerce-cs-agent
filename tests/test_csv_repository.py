"""CSV 저장소 테스트."""

import pytest
import os
import tempfile
import csv

from src.mock_system.storage.csv_repository import CSVRepository
from src.mock_system.storage.interfaces import CsvRepoConfig


class TestCSVRepository:
    """CSVRepository 테스트."""

    @pytest.fixture
    def temp_csv_dir(self):
        """임시 CSV 디렉토리 생성."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 테스트용 CSV 파일 생성
            test_data = [
                {"id": "1", "name": "Item 1", "price": "1000"},
                {"id": "2", "name": "Item 2", "price": "2000"},
                {"id": "3", "name": "Item 3", "price": "3000"},
            ]
            csv_path = os.path.join(tmpdir, "test_items.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["id", "name", "price"])
                writer.writeheader()
                writer.writerows(test_data)
            yield tmpdir

    @pytest.fixture
    def repo(self, temp_csv_dir):
        """테스트용 리포지토리."""
        config = CsvRepoConfig(
            data_dir=temp_csv_dir,
            filename="test_items.csv",
            key_field="id"
        )
        return CSVRepository(config)

    def test_query_all(self, repo):
        """전체 목록 조회."""
        items = repo.query()
        assert len(items) == 3
        assert items[0]["id"] == "1"

    def test_get_by_id_exists(self, repo):
        """존재하는 ID로 조회."""
        item = repo.get_by_id("2")
        assert item is not None
        assert item["name"] == "Item 2"
        assert item["price"] == "2000"

    def test_get_by_id_not_exists(self, repo):
        """존재하지 않는 ID로 조회."""
        item = repo.get_by_id("999")
        assert item is None

    def test_query_with_filter(self, repo):
        """필드 값으로 검색."""
        items = repo.query({"price": "2000"})
        assert len(items) == 1
        assert items[0]["id"] == "2"

    def test_query_with_filter_no_match(self, repo):
        """매칭되는 항목 없음."""
        items = repo.query({"price": "99999"})
        assert len(items) == 0


class TestRealCSVRepository:
    """실제 Mock CSV 데이터 테스트."""

    @pytest.fixture
    def orders_repo(self):
        """주문 리포지토리."""
        config = CsvRepoConfig(
            data_dir="data/mock_csv",
            filename="orders.csv",
            key_field="order_id"
        )
        return CSVRepository(config)

    @pytest.fixture
    def users_repo(self):
        """사용자 리포지토리."""
        config = CsvRepoConfig(
            data_dir="data/mock_csv",
            filename="users.csv",
            key_field="user_id"
        )
        return CSVRepository(config)

    def test_orders_csv_exists(self, orders_repo):
        """주문 CSV 파일 존재 확인."""
        orders = orders_repo.query()
        # 데이터가 있거나 빈 리스트 (파일 존재하면 성공)
        assert isinstance(orders, list)

    def test_users_csv_exists(self, users_repo):
        """사용자 CSV 파일 존재 확인."""
        users = users_repo.query()
        assert isinstance(users, list)

    @pytest.mark.skipif(
        not os.path.exists("data/mock_csv/orders.csv"),
        reason="Mock CSV 파일 없음"
    )
    def test_query_user_orders(self, orders_repo):
        """사용자별 주문 검색."""
        orders = orders_repo.query({"user_id": "user_001"})
        # 결과가 있거나 빈 리스트
        assert isinstance(orders, list)
