"""健康检查 API 测试。"""

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    """健康检查不依赖数据库内容，应该始终返回 ok。"""

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
