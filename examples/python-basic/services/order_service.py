from repositories.order_repository import OrderRepository


class OrderService:
    def __init__(self, repository: OrderRepository | None = None) -> None:
        self.repository = repository or OrderRepository()

    def get_order(self, order_id: str) -> dict[str, str] | None:
        return self.repository.find(order_id)
